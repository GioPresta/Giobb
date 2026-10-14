from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP, localcontext
from collections import defaultdict
from datetime import datetime
from time import perf_counter
import re

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.workbook.properties import CalcProperties

INPUT = Path('input')
OUTPUT = Path('output')
XLSX_ORIGINALI = OUTPUT / 'xlsx_originali'
XLSX_MODIFICATI = OUTPUT / 'xlsx_modificati'
DECIMALI_TOPUP = 9
OGNI_RIGHE = 10000
MAX_RIGHE_EXCEL = 1048576
# Se tutti gli RPT modificati e gli XLSX sono gia' presenti, esegue solo i check.
SOLO_CHECK_SE_OUTPUT_COMPLETI = True

PERCENTUALI = {
    'PTEVPJ': Decimal('0.025034000'),
    'PTEVPJ_75': Decimal('0.025034000'),
    'PTPVPI': Decimal('0.004571000'),
    'PTPVPK': Decimal('0.004571000'),
    'PTPMUG': Decimal('0.024120000'),
    'PTEVPK': Decimal('0.031878501'),
    'PTPVPL': Decimal('0.004404654'),
    'PTQVPA': Decimal('0.000000000'),
    'PTOP18': Decimal('0.004500000'),
    'PTOP19': Decimal('0.004500000'),
    'PTOP21': Decimal('0.000000000'),
    'PTRVPA': Decimal('0.033802741'),
    'PTPVPM': Decimal('0.004200000'),
    'PTOP22': Decimal('0.000000000'),
    'PTPVPN': Decimal('0.004710510'),
}
COLONNE_MU = [f'MF_INIT_UNITS({i})' for i in range(1, 7)]
NUMERICHE = {'INIT_UNITS', 'TOPUP_PREM', *COLONNE_MU}
START = perf_counter()


def log(m):
    print(f'[{datetime.now():%H:%M:%S}] [+{perf_counter()-START:.1f}s] {m}', flush=True)


def tipo_mp(nome):
    nome = nome.upper()
    mo, mu = 'MO' in nome, 'MU' in nome
    if mo == mu:
        raise ValueError(f'Impossibile distinguere MO/MU nel nome {nome}')
    return 'MO' if mo else 'MU'


def split_line(raw):
    for end in (b'\r\n', b'\n', b'\r'):
        if raw.endswith(end):
            return raw[:-len(end)], end
    return raw, b''


def txt(b):
    return b.decode('utf-8').strip()


def decimal_value(b):
    s = txt(b)
    return Decimal(s) if s else Decimal(0)


def read_lines(path):
    return path.read_bytes().splitlines(keepends=True)


def structure(lines):
    for i, raw in enumerate(lines):
        body, _ = split_line(raw)
        cols = [txt(x).upper() for x in body.split(b',')]
        if 'PRODOTTO' in cols and 'TOPUP_PREM' in cols:
            if len(cols) != len(set(cols)):
                raise ValueError('Intestazioni duplicate')
            return i, cols
    raise ValueError('Intestazione PRODOTTO/TOPUP_PREM non trovata')


def indices(cols, tipo):
    required = ['PRODOTTO', 'TOPUP_PREM'] + (['INIT_UNITS'] if tipo == 'MO' else COLONNE_MU)
    missing = [c for c in required if c not in cols]
    if missing:
        raise ValueError('Colonne mancanti: ' + ', '.join(missing))
    return cols.index('PRODOTTO'), cols.index('TOPUP_PREM'), [cols.index(c) for c in required[2:]]


def calc_topup(units, rate):
    with localcontext() as ctx:
        ctx.prec = 60
        v = (units * rate).quantize(Decimal(1).scaleb(-DECIMALI_TOPUP), rounding=ROUND_HALF_UP)
        return f'{v:.{DECIMALI_TOPUP}f}'


def replace_value(original, value):
    left = len(original) - len(original.lstrip(b' '))
    right = len(original) - len(original.rstrip(b' '))
    return b' ' * left + value.encode('ascii') + b' ' * right


def free_path(path):
    if not path.exists():
        return path
    n = 2
    while True:
        candidate = path.with_name(f'{path.stem}_{n}{path.suffix}')
        if not candidate.exists():
            return candidate
        n += 1


def save_excel(wb, path):
    created = False
    try:
        with path.open('xb') as f:
            created = True
            wb.save(f)
    except Exception:
        if created:
            path.unlink(missing_ok=True)
        raise


def style_header(ws):
    for c in ws[1]:
        c.font = Font(bold=True, color='FFFFFF')
        c.fill = PatternFill(fill_type='solid', fgColor='17365D')
    ws.freeze_panes = 'A2'


def append_header_writeonly(ws, headers):
    row = []
    for title in headers:
        c = WriteOnlyCell(ws, value=title)
        c.font = Font(bold=True, color='FFFFFF')
        c.fill = PatternFill(fill_type='solid', fgColor='17365D')
        row.append(c)
    ws.append(row)


def excel_value(b, col):
    s = txt(b)
    if col in NUMERICHE:
        try:
            return float(Decimal(s)) if s else 0
        except Exception:
            return s
    return s


def modify_rpt(src, dst):
    tipo = tipo_mp(src.stem)
    lines = read_lines(src)
    header, cols = structure(lines)
    ip, it, iu = indices(cols, tipo)
    changed = list(lines)
    stats = defaultdict(lambda: {'righe': 0, 'prima': Decimal(0), 'dopo': Decimal(0)})
    count = 0
    for i in range(header+1, len(lines)):
        body, ending = split_line(lines[i])
        if not body.strip():
            continue
        fields = body.split(b',')
        if len(fields) != len(cols):
            raise ValueError(f'Riga {i+1}: colonne incoerenti')
        prod = txt(fields[ip])
        if prod not in PERCENTUALI:
            continue
        try:
            units = sum((decimal_value(fields[j]) for j in iu), Decimal(0))
            before = decimal_value(fields[it])
            result = calc_topup(units, PERCENTUALI[prod])
            fields[it] = replace_value(fields[it], result)
            changed[i] = b','.join(fields) + ending
            s = stats[prod]
            s['righe'] += 1
            s['prima'] += before
            s['dopo'] += Decimal(result)
            count += 1
            if count % OGNI_RIGHE == 0:
                log(f'  RPT: {count:,} righe')
        except Exception as exc:
            raise ValueError(f'Riga {i+1}, tariffa {prod}: {exc}') from exc
    with dst.open('xb') as f:
        f.write(b''.join(changed))
    return stats, count


def make_report(stats, errors, created, existing, modified):
    path = free_path(OUTPUT / 'report_modifiche.txt')
    with path.open('x', encoding='utf-8') as f:
        f.write(f'REPORT MODELPOINT - {datetime.now():%d/%m/%Y %H:%M:%S}\n')
        f.write(f'RPT nuovi: {created}\nRPT esistenti: {existing}\nRighe modificate: {modified}\n')
        f.write(f'Decimali TOPUP: {DECIMALI_TOPUP}\nErrori: {len(errors)}\n')
        f.write('Le statistiche riguardano solo i nuovi RPT creati in questa esecuzione.\n')
        for prod in sorted(stats):
            entries = stats[prod]
            f.write(f'\nTARIFFA {prod} - EJ {PERCENTUALI[prod]*100}%\n')
            total_rows = 0
            total_before = Decimal(0)
            total_after = Decimal(0)
            for name, tipo, s in entries:
                f.write(f'  {name} ({tipo}): righe={s["righe"]}, TOPUP prima={s["prima"]}, TOPUP dopo={s["dopo"]}\n')
                total_rows += s['righe']
                total_before += s['prima']
                total_after += s['dopo']
            f.write(f'  TOTALI: righe={total_rows}, prima={total_before}, dopo={total_after}\n')
        if errors:
            f.write('\nERRORI\n')
            for name, msg in errors:
                f.write(f'{name}: {msg}\n')
    return path


def verify_structure(old, new, name, tipo):
    if len(old) != len(new):
        raise ValueError(f'{name}: numero righe differente')
    h, cols = structure(old)
    hn, colsn = structure(new)
    if h != hn or cols != colsn:
        raise ValueError(f'{name}: intestazioni differenti')
    ip, it, iu = indices(cols, tipo)
    for i, (a_raw, b_raw) in enumerate(zip(old, new)):
        if i <= h:
            if a_raw != b_raw:
                raise ValueError(f'{name}: preambolo/intestazione modificato alla riga {i+1}')
            continue
        a, ea = split_line(a_raw)
        b, eb = split_line(b_raw)
        if not a.strip():
            if a_raw != b_raw:
                raise ValueError(f'{name}: riga vuota modificata alla riga {i+1}')
            continue
        fa, fb = a.split(b','), b.split(b',')
        if len(fa) != len(cols) or len(fb) != len(cols):
            raise ValueError(f'{name}: colonne incoerenti alla riga {i+1}')
        if ea != eb:
            raise ValueError(f'{name}: fine riga modificato alla riga {i+1}')
        for j in range(len(cols)):
            if j != it and fa[j] != fb[j]:
                raise ValueError(f'{name}: colonna {cols[j]} modificata alla riga {i+1}')
        if txt(fa[ip]) not in PERCENTUALI and fa[it] != fb[it]:
            raise ValueError(f'{name}: TOPUP di tariffa esclusa modificato alla riga {i+1}')
    return h, cols, ip, it, iu


CHECK_HEADERS = [
    'MODELPOINT', 'RIGA RPT', 'TIPO', 'PRODOTTO', 'INIT_UNITS',
    *COLONNE_MU, 'TOTALE UNITS', 'PERCENTUALE EJ',
    'TOPUP ORIGINALE', 'CALCOLO EXCEL', 'TOPUP NUOVO RPT',
    'DIFFERENZA', 'ESITO EXCEL', 'CHECK PYTHON'
]


def make_check(pairs, path, upstream_errors):
    wb = Workbook(write_only=True)  # SOLO CHECK
    wb.calculation = CalcProperties(calcMode='auto', fullCalcOnLoad=True, forceFullCalc=True)
    summary = wb.create_sheet('RIEPILOGO')
    detail = wb.create_sheet('DETTAGLIO')
    tariffs_sheet = wb.create_sheet('TARIFFE_MODELPOINT')
    detail.freeze_panes = 'E2'
    for j, width in enumerate([32, 12, 10, 18, 18, 20, 20, 20, 20, 20, 20, 20, 19, 21, 21, 21, 19, 17, 17], 1):
        detail.column_dimensions[get_column_letter(j)].width = width
    append_header_writeonly(detail, CHECK_HEADERS)
    row_no = 2
    checked = 0
    py_errors = 0
    structural_errors = []
    excel_precheck_errors = 0
    files_ok = 0
    # Censimento completo di tutte le tariffe dai RPT originali.
    tariff_locations = defaultdict(lambda: defaultdict(int))
    for original in sorted(INPUT.rglob('*')):
        if not original.is_file() or original.suffix.lower() != '.rpt':
            continue
        try:
            original_lines = read_lines(original)
            header_idx, original_cols = structure(original_lines)
            product_idx = original_cols.index('PRODOTTO')
            mp_name = str(original.relative_to(INPUT))
            mp_type = tipo_mp(original.stem)
            for raw in original_lines[header_idx + 1:]:
                body, _ = split_line(raw)
                if not body.strip():
                    continue
                fields = body.split(b',')
                if len(fields) != len(original_cols):
                    raise ValueError('numero di colonne non coerente')
                product = txt(fields[product_idx])
                if product:
                    tariff_locations[product][(mp_name, mp_type)] += 1
        except Exception as exc:
            structural_errors.append(f'CENSIMENTO TARIFFE {original.name}: {exc}')

    for n, (original, modified) in enumerate(pairs, 1):
        name = str(original.relative_to(INPUT))
        log(f'  CHECK [{n}/{len(pairs)}] {name}')
        try:
            tipo = tipo_mp(original.stem)
            old, new = read_lines(original), read_lines(modified)
            h, cols, ip, it, iu = verify_structure(old, new, name, tipo)
            files_ok += 1
        except Exception as exc:
            structural_errors.append(str(exc))
            log(f'    ERRORE STRUTTURA: {exc}')
            continue
        for i in range(h+1, len(old)):
            a, _ = split_line(old[i])
            b, _ = split_line(new[i])
            if not a.strip():
                continue
            fa, fb = a.split(b','), b.split(b',')
            prod = txt(fa[ip])
            if prod not in PERCENTUALI:
                continue
            try:
                units = [decimal_value(fa[j]) for j in iu]
                total_units = sum(units, Decimal(0))
                rate = PERCENTUALI[prod]
                before = decimal_value(fa[it])
                actual = decimal_value(fb[it])
                expected = Decimal(calc_topup(total_units, rate))
            except Exception as exc:
                structural_errors.append(f'{name}, riga {i+1}: {exc}')
                continue
            py_ok = expected == actual
            if not py_ok:
                py_errors += 1
            # Precheck independently checks the numerical comparison used in Excel.
            # For Excel's ~15 significant digit limit, mark potentially unsafe values
            # as errors rather than silently trusting rounded floats.
            numeric_inputs = [total_units, rate, actual]
            excel_safe = all(len(x.copy_abs().as_tuple().digits) <= 15 for x in numeric_inputs)
            if not excel_safe:
                excel_precheck_errors += 1
            if row_no > MAX_RIGHE_EXCEL:
                raise ValueError('CHECK: superato il limite di righe Excel')
            r = row_no
            formula_units = f'=IF(C{r}="MO",E{r},SUM(F{r}:K{r}))'
            formula_calc = f'=ROUND(L{r}*M{r},{DECIMALI_TOPUP})'
            formula_diff = f'=ROUND(O{r}-P{r},{DECIMALI_TOPUP})'
            # Excel's binary floating-point is rounded before comparing.
            formula_excel = (f'=IF(ROUND(O{r},{DECIMALI_TOPUP})='
                             f'ROUND(P{r},{DECIMALI_TOPUP}),"OK","ERRORE")')
            init = float(units[0]) if tipo == 'MO' else None
            mf = [None]*6 if tipo == 'MO' else [float(v) for v in units]
            detail.append([
                name, i+1, tipo, prod, init, *mf,
                formula_units, float(rate), float(before), formula_calc,
                float(actual), formula_diff, formula_excel,
                'OK' if py_ok else 'ERRORE'
            ])
            row_no += 1
            checked += 1
            if checked % OGNI_RIGHE == 0:
                log(f'    CHECK: {checked:,} righe; errori Python: {py_errors}')
    last = row_no - 1
    structural_count = len(structural_errors)
    upstream_count = len(upstream_errors)
    preliminary = 'OK' if not (py_errors or structural_count or upstream_count or excel_precheck_errors or not checked) else 'NON OK'
    summary.column_dimensions['A'].width = 39
    summary.column_dimensions['B'].width = 90
    append_header_writeonly(summary, ['CONTROLLO', 'RISULTATO'])
    # The formula evaluates Excel outcomes, Python outcomes, structural and upstream errors.
    # COUNTIF counts both OK and ERRORE so blank/noncalculated outcomes cannot pass.
    general_formula = (
        f'=IF(AND({checked}>0,'
        f'COUNTIF(DETTAGLIO!R2:R{last},"OK")={checked},'
        f'COUNTIF(DETTAGLIO!S2:S{last},"OK")={checked},'
        f'{structural_count}=0,{upstream_count}=0,{excel_precheck_errors}=0),"OK","NON OK")'
    )
    summary.append(['ESITO GENERALE (DOPO RICALCOLO EXCEL)', general_formula])
    summary.append(['ESITO PRELIMINARE PYTHON', preliminary])
    summary.append(['FILE CONFRONTATI', len(pairs)])
    summary.append(['FILE STRUTTURALMENTE OK', files_ok])
    summary.append(['RIGHE CONTROLLATE', checked])
    summary.append(['ERRORI CHECK PYTHON', py_errors])
    summary.append(['ERRORI STRUTTURALI', structural_count])
    summary.append(['ERRORI MODIFICA RPT', upstream_count])
    summary.append(['RIGHE CON PRECISIONE EXCEL NON GARANTITA', excel_precheck_errors])
    summary.append(['DECIMALI TOPUP', DECIMALI_TOPUP])
    summary.append(['NOTA', 'Aprire in Excel e attendere il ricalcolo delle formule per ESITO GENERALE.'])
    summary.append(['NOTA', 'Excel usa numeri a precisione limitata; CHECK PYTHON usa Decimal.'])
    summary.append(['NOTA', 'Se Excel mostra ERRORE ma Python OK, verificare i limiti numerici di Excel.'])
    summary.append(['', ''])
    append_header_writeonly(summary, ['PROBLEMI', 'DETTAGLIO'])
    for issue in structural_errors:
        summary.append(['STRUTTURA', issue])
    for name, issue in upstream_errors:
        summary.append(['MODIFICA RPT', f'{name}: {issue}'])
    if not structural_errors and not upstream_errors:
        summary.append(['NESSUNO', 'Nessun problema strutturale o di modifica'])
    # Tutte le tariffe presenti nei file, senza colonna percentuale EJ.
    tariffs_sheet.freeze_panes = 'B2'
    for letter, width in [('A', 22), ('B', 48), ('C', 12), ('D', 20), ('E', 25)]:
        tariffs_sheet.column_dimensions[letter].width = width
    append_header_writeonly(tariffs_sheet,
        ['TARIFFA', 'MODELPOINT', 'TIPO', 'RIGHE TARIFFA', 'MODELPOINT PER TARIFFA'])
    for prod in sorted(tariff_locations):
        locations = tariff_locations[prod]
        for (mp_name, mp_tipo), count in sorted(locations.items()):
            tariffs_sheet.append([prod, mp_name, mp_tipo, count, len(locations)])
    log('  Salvataggio CHECK...')
    save_excel(wb, path)
    return {'checked': checked, 'py_errors': py_errors, 'structural_errors': structural_errors, 'preliminary': preliminary}


def convert_individual(src, dst):
    lines = read_lines(src)
    h, cols = structure(lines)
    wb = Workbook()  # NORMALE
    ws = wb.active
    ws.title = 'MODELPOINT'
    ws.append(cols)
    style_header(ws)
    count = 0
    for raw in lines[h+1:]:
        body, _ = split_line(raw)
        if not body.strip():
            continue
        fields = body.split(b',')
        if len(fields) != len(cols):
            raise ValueError(f'{src.name}: numero colonne incoerente')
        if count+2 > MAX_RIGHE_EXCEL:
            raise ValueError('Limite righe Excel superato')
        ws.append([excel_value(v, cols[j]) for j, v in enumerate(fields)])
        count += 1
        if count % OGNI_RIGHE == 0:
            log(f'    XLSX: {count:,} righe')
    ws.auto_filter.ref = f'A1:{get_column_letter(len(cols))}{ws.max_row}'
    for j, col in enumerate(cols, 1):
        ws.column_dimensions[get_column_letter(j)].width = min(max(len(col)+2, 13), 28)
    save_excel(wb, dst)
    return count


def make_combined(tipo, pairs, dst):
    selected = [new for old, new in pairs if tipo_mp(old.stem) == tipo]
    if not selected:
        return 0, 0
    reference = None
    for src in selected:
        h, cols = structure(read_lines(src))
        if reference is None:
            reference = cols
        elif cols != reference:
            raise ValueError(f'Intestazioni diverse nel {tipo}: {src.name}')
    wb = Workbook()  # NORMALE
    ws = wb.active
    ws.title = 'MONO' if tipo == 'MO' else 'MULTI'
    ws.append(reference)
    style_header(ws)
    count = 0
    for n, src in enumerate(selected, 1):
        log(f'  {tipo} [{n}/{len(selected)}] {src.name}')
        lines = read_lines(src)
        h, cols = structure(lines)
        for raw in lines[h+1:]:
            body, _ = split_line(raw)
            if not body.strip():
                continue
            fields = body.split(b',')
            if len(fields) != len(cols):
                raise ValueError(f'{src.name}: colonne incoerenti')
            if count+2 > MAX_RIGHE_EXCEL:
                raise ValueError(f'{tipo}: limite righe Excel superato')
            ws.append([excel_value(v, cols[j]) for j, v in enumerate(fields)])
            count += 1
            if count % OGNI_RIGHE == 0:
                log(f'    {tipo} COMPLESSIVO: {count:,} righe')
    ws.auto_filter.ref = f'A1:{get_column_letter(len(reference))}{ws.max_row}'
    for j, col in enumerate(reference, 1):
        ws.column_dimensions[get_column_letter(j)].width = min(max(len(col)+2, 13), 28)
    log(f'  Salvataggio {tipo} complessivo...')
    save_excel(wb, dst)
    return len(selected), count



def report_from_existing(pairs, missing):
    """Statistiche aggiornate dagli RPT esistenti, senza modificarli."""
    stats = defaultdict(list)
    errors = [(str(p.relative_to(INPUT)), 'RPT modificato mancante') for p in missing]
    total = 0
    for src, dst in pairs:
        name = str(src.relative_to(INPUT))
        try:
            tipo = tipo_mp(src.stem)
            old, new = read_lines(src), read_lines(dst)
            h, cols, ip, it, iu = verify_structure(old, new, name, tipo)
            by_tariff = defaultdict(lambda: {'righe': 0, 'prima': Decimal(0), 'dopo': Decimal(0)})
            for a_raw, b_raw in zip(old[h+1:], new[h+1:]):
                a, _ = split_line(a_raw)
                b, _ = split_line(b_raw)
                if not a.strip():
                    continue
                fa, fb = a.split(b','), b.split(b',')
                prod = txt(fa[ip])
                if prod not in PERCENTUALI:
                    continue
                entry = by_tariff[prod]
                entry['righe'] += 1
                entry['prima'] += decimal_value(fa[it])
                entry['dopo'] += decimal_value(fb[it])
                total += 1
            for prod, entry in by_tariff.items():
                stats[prod].append((name, tipo, entry))
        except Exception as exc:
            errors.append((name, str(exc)))
    return stats, errors, total


def output_completi(files):
    if not all((OUTPUT / p.relative_to(INPUT)).is_file() for p in files):
        return False
    if not all((XLSX_ORIGINALI / p.relative_to(INPUT)).with_suffix('.xlsx').is_file()
                   and (XLSX_MODIFICATI / p.relative_to(INPUT)).with_suffix('.xlsx').is_file()
                   for p in files):
        return False
    tipi = {tipo_mp(p.stem) for p in files}
    return all((OUTPUT / ('MONO_COMPLESSIVO.xlsx' if t == 'MO' else 'MULTI_COMPLESSIVO.xlsx')).is_file()
               for t in tipi)


def main():
    log('=' * 65)
    log('ATTENZIONE - PRIMA DI RIFARE I CALCOLI, CANCELLARE O SPOSTARE')
    log('I VECCHI FILE NELLA CARTELLA OUTPUT (MAI QUELLI IN INPUT).')
    log('IL PROGRAMMA NON SOVRASCRIVE GLI OUTPUT ESISTENTI.')
    log('SE GLI OUTPUT SONO COMPLETI, IL CALCOLO SARA SKIPPATO:')
    log('VERRANNO CREATI SOLO REPORT TXT E CHECK XLSX A TRE FOGLI.')
    log('=' * 65)
    log('=== AVVIO MODELPOINT ===')
    if not INPUT.is_dir():
        log('ERRORE: cartella input non trovata')
        return
    for folder in (OUTPUT, XLSX_ORIGINALI, XLSX_MODIFICATI):
        folder.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in INPUT.rglob('*') if p.is_file() and p.suffix.lower() == '.rpt')
    if not files:
        log('Nessun RPT in input')
        return
    log(f'RPT trovati: {len(files)} | Decimali TOPUP: {DECIMALI_TOPUP}')
    if SOLO_CHECK_SE_OUTPUT_COMPLETI and output_completi(files):
        log('=' * 65)
        log('CALCOLO SKIPPATO - OUTPUT GIA PRESENTI E COMPLETI')
        log('TOPUP_PREM NON RICALCOLATO; RPT NON MODIFICATI')
        log('XLSX INDIVIDUALI E MONO/MULTI NON RICREATI')
        log('SI ESEGUONO SOLTANTO REPORT TXT E CHECK XLSX (3 FOGLI)')
        log('PER RICALCOLARE, SPOSTARE O CANCELLARE I VECCHI OUTPUT')
        log('=' * 65)
        pairs = [(src, OUTPUT / src.relative_to(INPUT)) for src in files]
        stats, errors, total = report_from_existing(pairs, [])
        report = make_report(stats, errors, 0, len(files), total)
        log(f'REPORT TXT CREATO: {report}')
        check_path = free_path(OUTPUT / 'CHECK_CALCOLI.xlsx')
        try:
            result = make_check(pairs, check_path, errors)
            log(f'CHECK XLSX CREATO: {check_path}')
            log(f'ESITO PRELIMINARE: {result["preliminary"]} | Righe: {result["checked"]:,}')
            log('ESITO GENERALE: aprire in Excel per ricalcolare le formule')
        except Exception as exc:
            log(f'ERRORE CHECK: {exc}')
        log('FINE MODALITA SOLO CHECK: nessun RPT o XLSX precedente modificato')
        return
    stats = defaultdict(list)
    errors = []
    created = existing = modified_count = 0

    log('FASE 1/5 - MODIFICA RPT')
    log('Se un RPT esiste gia, il calcolo di quel file viene SKIPPATO.')
    for n, src in enumerate(files, 1):
        rel = src.relative_to(INPUT)
        dst = OUTPUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        log(f'[{n}/{len(files)}] {rel}')
        if dst.exists():
            existing += 1
            log('  CALCOLO SKIPPATO: RPT gia presente, TOPUP_PREM non ricalcolato')
            continue
        try:
            file_stats, count = modify_rpt(src, dst)
            created += 1
            modified_count += count
            tipo = tipo_mp(src.stem)
            for prod, s in file_stats.items():
                stats[prod].append((str(rel), tipo, s))
            log(f'  RPT creato: {count:,} righe')
        except Exception as exc:
            errors.append((str(rel), str(exc)))
            log(f'  ERRORE: {exc}')

    log('FASE 2/5 - REPORT TXT')
    report = make_report(stats, errors, created, existing, modified_count)
    log(f'REPORT CREATO: {report}')

    pairs = [(src, OUTPUT / src.relative_to(INPUT)) for src in files if (OUTPUT / src.relative_to(INPUT)).exists()]
    log('FASE 3/5 - CHECK EXCEL')
    check_path = free_path(OUTPUT / 'CHECK_CALCOLI.xlsx')
    try:
        result = make_check(pairs, check_path, errors)
        log(f'CHECK CREATO: {check_path}')
        log(f'ESITO PRELIMINARE: {result["preliminary"]} | Righe: {result["checked"]:,}')
        log('ESITO GENERALE DEFINITIVO: aprire il file in Excel per ricalcolare le formule')
    except Exception as exc:
        log(f'ERRORE CHECK: {exc}')

    log('FASE 4/5 - EXCEL INDIVIDUALI')
    for n, (src, new) in enumerate(pairs, 1):
        rel = src.relative_to(INPUT)
        log(f'[{n}/{len(pairs)}] {rel}')
        for source, dest, label in [
            (src, (XLSX_ORIGINALI / rel).with_suffix('.xlsx'), 'ORIGINALE'),
            (new, (XLSX_MODIFICATI / rel).with_suffix('.xlsx'), 'MODIFICATO')
        ]:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                log(f'  {label}: esiste gia\', non sovrascritto')
                continue
            try:
                count = convert_individual(source, dest)
                log(f'  {label}: creato ({count:,} righe)')
            except Exception as exc:
                log(f'  ERRORE {label}: {exc}')

    log('FASE 5/5 - EXCEL COMPLESSIVI')
    for tipo, filename in [('MO', 'MONO_COMPLESSIVO.xlsx'), ('MU', 'MULTI_COMPLESSIVO.xlsx')]:
        dest = free_path(OUTPUT / filename)
        try:
            nfiles, count = make_combined(tipo, pairs, dest)
            if nfiles:
                log(f'CREATO {dest}: {nfiles} RPT, {count:,} righe')
            else:
                log(f'Nessun RPT {tipo}')
        except Exception as exc:
            log(f'ERRORE COMPLESSIVO {tipo}: {exc}')

    log(f'FINE - RPT nuovi: {created}, gia\' presenti: {existing}, righe modificate: {modified_count:,}')
    log(f'Tempo totale: {perf_counter()-START:.1f} secondi')


if __name__ == '__main__':
    main()
