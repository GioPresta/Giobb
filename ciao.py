#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
retrodata_fac.py

PENSATO PER SPYDER: mettilo nella STESSA CARTELLA dei file .rpt (o .fac)
e lancialo con F5 (Run). Non servono argomenti da riga di comando.

APPROCCIO "FORMAT PRESERVING":
Non usa il modulo csv per riscrivere il file (che normalizza virgolette,
spazi, zeri iniziali, ecc.). Invece legge il file riga per riga e modifica
SOLO i campi BIRTH_YEAR, BIRTH_MONTH, ENTRY_YEAR, ENTRY_MONTH, lasciando
tutto il resto del file (altre colonne, virgolette, delimitatori, a-capo,
eventuali righe di metadati/intestazioni ripetute) ESATTAMENTE come
nell'originale.

Logica di retrodatazione (anno e mese ragionati insieme):
    ENTRY_YEAR 2026, ENTRY_MONTH 3  ->  ENTRY_YEAR 2025, ENTRY_MONTH 9
    BIRTH_YEAR 1973, BIRTH_MONTH 1  ->  BIRTH_YEAR 1972, BIRTH_MONTH 7

ECCEZIONE: se su una riga BIRTH_MONTH = 0, quella riga NON viene toccata
per BIRTH_YEAR/BIRTH_MONTH (restano invariati). ENTRY_YEAR/ENTRY_MONTH
vengono comunque retrodatati normalmente.

Puoi cambiare le impostazioni qui sotto in CONFIGURAZIONE.
"""

from pathlib import Path

# ======================= CONFIGURAZIONE =======================

EXTENSION = ".rpt"
MONTHS = 6
OVERWRITE = True

REQUIRED_COLS = ["BIRTH_YEAR", "ENTRY_YEAR", "ENTRY_MONTH", "BIRTH_MONTH"]

DELIMITER_CANDIDATES = [",", ";", "\t", "|"]

# ================================================================


def get_script_dir() -> Path:
    try:
        return Path(__file__).resolve().parent
    except NameError:
        return Path.cwd()


def read_text_preserving_encoding(path: Path):
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1"), "latin-1"


def split_line_ending(line: str):
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    if line.endswith("\r"):
        return line[:-1], "\r"
    return line, ""


def split_fields_raw(content: str, delimiter: str):
    fields = []
    cur = []
    in_quotes = False
    quote_char = None
    i = 0
    n = len(content)
    while i < n:
        c = content[i]
        if in_quotes:
            cur.append(c)
            if c == quote_char:
                if i + 1 < n and content[i + 1] == quote_char:
                    cur.append(content[i + 1])
                    i += 1
                else:
                    in_quotes = False
        else:
            if c in ('"', "'"):
                in_quotes = True
                quote_char = c
                cur.append(c)
            elif c == delimiter:
                fields.append("".join(cur))
                cur = []
            else:
                cur.append(c)
        i += 1
    fields.append("".join(cur))
    return fields


def strip_quotes_and_space(field: str) -> str:
    f = field.strip()
    if len(f) >= 2 and f[0] == f[-1] and f[0] in ('"', "'"):
        f = f[1:-1]
    return f.strip()


def detect_delimiter_for_line(content: str, normalized_targets):
    best = None
    best_score = -1
    for d in DELIMITER_CANDIDATES:
        fields = split_fields_raw(content, d)
        if len(fields) < 2:
            continue
        cleaned = [strip_quotes_and_space(f).upper() for f in fields]
        score = sum(1 for t in normalized_targets if t in cleaned)
        if score > best_score:
            best_score = score
            best = d
    return best, best_score


def shift_year_month(year: int, month: int, months_delta: int):
    absolute_month = year * 12 + (month - 1)
    absolute_month -= months_delta
    new_year, new_month0 = divmod(absolute_month, 12)
    return new_year, new_month0 + 1


def replace_numeric_field(raw_field: str, new_value: int) -> str:
    quote_char = ""
    inner = raw_field
    if len(raw_field) >= 2 and raw_field[0] == raw_field[-1] and raw_field[0] in ('"', "'"):
        quote_char = raw_field[0]
        inner = raw_field[1:-1]

    stripped = inner.strip()
    if stripped:
        leading_len = len(inner) - len(inner.lstrip())
        trailing_len = len(inner) - len(inner.rstrip())
        leading_ws = inner[:leading_len]
        trailing_ws = inner[len(inner) - trailing_len:] if trailing_len else ""
    else:
        leading_ws = inner
        trailing_ws = ""

    width = len(stripped)
    if stripped.startswith("0") and len(stripped) > 1:
        new_str = str(new_value).zfill(width)
    else:
        new_str = str(new_value)

    return f"{quote_char}{leading_ws}{new_str}{trailing_ws}{quote_char}"


def process_file(input_path: Path, output_path: Path, months_delta: int) -> str:
    text, encoding = read_text_preserving_encoding(input_path)
    lines = text.splitlines(keepends=True)

    if not lines:
        return "NO - file vuoto"

    normalized_targets = set(REQUIRED_COLS)

    active_header_indices = None
    active_delimiter = None
    active_num_fields = None

    out_lines = []
    rows_modified = 0
    rows_skipped_birth = 0
    header_found = False

    for line in lines:
        content, ending = split_line_ending(line)

        if content.strip() == "":
            out_lines.append(line)
            continue

        delim_try, score = detect_delimiter_for_line(content, normalized_targets)

        if delim_try is not None and score == len(REQUIRED_COLS):
            fields = split_fields_raw(content, delim_try)
            cleaned = [strip_quotes_and_space(f).upper() for f in fields]
            idx_map = {}
            for col in REQUIRED_COLS:
                idx_map[col] = cleaned.index(col)

            active_header_indices = idx_map
            active_delimiter = delim_try
            active_num_fields = len(fields)
            header_found = True

            out_lines.append(line)  # l'header resta invariato
            continue

        if active_header_indices is None:
            out_lines.append(line)
            continue

        fields = split_fields_raw(content, active_delimiter)

        if len(fields) != active_num_fields:
            out_lines.append(line)
            continue

        try:
            entry_year = int(strip_quotes_and_space(fields[active_header_indices["ENTRY_YEAR"]]))
            entry_month = int(strip_quotes_and_space(fields[active_header_indices["ENTRY_MONTH"]]))
            birth_year = int(strip_quotes_and_space(fields[active_header_indices["BIRTH_YEAR"]]))
            birth_month = int(strip_quotes_and_space(fields[active_header_indices["BIRTH_MONTH"]]))
        except ValueError:
            out_lines.append(line)
            continue

        # ECCEZIONE: se BIRTH_MONTH = 0, non tocco BIRTH_YEAR/BIRTH_MONTH
        skip_birth = (birth_month == 0)
        if skip_birth:
            rows_skipped_birth += 1

        new_entry_year, new_entry_month = shift_year_month(entry_year, entry_month, months_delta)
        fields[active_header_indices["ENTRY_YEAR"]] = replace_numeric_field(
            fields[active_header_indices["ENTRY_YEAR"]], new_entry_year)
        fields[active_header_indices["ENTRY_MONTH"]] = replace_numeric_field(
            fields[active_header_indices["ENTRY_MONTH"]], new_entry_month)

        if not skip_birth:
            new_birth_year, new_birth_month = shift_year_month(birth_year, birth_month, months_delta)
            fields[active_header_indices["BIRTH_YEAR"]] = replace_numeric_field(
                fields[active_header_indices["BIRTH_YEAR"]], new_birth_year)
            fields[active_header_indices["BIRTH_MONTH"]] = replace_numeric_field(
                fields[active_header_indices["BIRTH_MONTH"]], new_birth_month)

        new_content = active_delimiter.join(fields)
        out_lines.append(new_content + ending)
        rows_modified += 1

    if not header_found:
        return f"NO - intestazione non trovata (colonne richieste: {REQUIRED_COLS})"

    new_text = "".join(out_lines)

    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_bytes(new_text.encode(encoding if encoding != "utf-8-sig" else "utf-8"))
    tmp_path.replace(output_path)

    esito = f"fatto ({rows_modified} righe modificate, encoding: {encoding})"
    if rows_skipped_birth:
        esito += f" [BIRTH non toccato su {rows_skipped_birth} righe con BIRTH_MONTH=0]"
    return esito


def main():
    script_dir = get_script_dir()
    print(f"Cartella di lavoro: {script_dir}")

    if EXTENSION:
        candidates = sorted(script_dir.glob(f"*{EXTENSION}"))
    else:
        candidates = sorted(p for p in script_dir.iterdir() if p.is_file())

    candidates = [
        p for p in candidates
        if not p.name.endswith(".tmp") and not p.name.endswith(".py")
    ]

    if not candidates:
        print(f"Nessun file trovato con estensione '{EXTENSION}' in {script_dir}")
        return

    print(f"Trovati {len(candidates)} file. Retrodatazione di {MONTHS} mesi. "
          f"Overwrite = {OVERWRITE}\n")

    ok_count = 0
    err_count = 0

    for input_path in candidates:
        if OVERWRITE:
            output_path = input_path
        else:
            output_path = input_path.with_name(input_path.stem + "_retro" + input_path.suffix)

        try:
            esito = process_file(input_path, output_path, MONTHS)
        except Exception as e:
            esito = f"NO - errore imprevisto: {e}"

        print(f"{input_path.name}: {esito}")

        if esito.startswith("fatto"):
            ok_count += 1
        else:
            err_count += 1

    print(f"\nCompletato: {ok_count} fatti, {err_count} non fatti (su {len(candidates)} file totali).")


if __name__ == "__main__":
    main()