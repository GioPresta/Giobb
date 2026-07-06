#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_ann_prem_st_m_tup.py

TOOL SEPARATO, stessa logica del tool di retrodatazione.
PENSATO PER SPYDER: mettilo nella STESSA CARTELLA dei file .rpt e lancialo
con F5 (Run). Non servono argomenti da riga di comando.

Cosa fa:
- Trova tutti i file con estensione EXTENSION nella cartella dello script
- Legge la colonna ANN_PREM_ST_M_TUP
- Sostituisce OLD_VALUE con NEW_VALUE in quella colonna (default: 7 -> 1)
- Sovrascrive ogni file originale (se OVERWRITE = True)
- Stampa un log per ogni file: "fatto" (con quante righe modificate)
  oppure il motivo per cui è saltato

Puoi cambiare le impostazioni qui sotto in CONFIGURAZIONE.
"""

import csv
from pathlib import Path

# ======================= CONFIGURAZIONE =======================

# Estensione dei file da processare. Metti None per processare TUTTI i
# file nella cartella (indipendentemente dall'estensione).
EXTENSION = ".rpt"

# Nome della colonna da modificare
COLUMN_NAME = "ANN_PREM_ST_M_TUP"

# Valore da cercare e valore con cui sostituirlo
OLD_VALUE = "7"
NEW_VALUE = "1"

# True  = sovrascrive i file originali
# False = crea una copia "nome_fix.rpt" accanto all'originale, senza
#         toccare quello originale
OVERWRITE = True

# ================================================================


def get_script_dir() -> Path:
    """Restituisce la cartella in cui si trova questo script.
    Funziona sia lanciato da terminale sia da Spyder (F5)."""
    try:
        return Path(__file__).resolve().parent
    except NameError:
        return Path.cwd()


def detect_delimiter(sample: str) -> str:
    """Prova a rilevare il delimitatore del file CSV."""
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
        return dialect.delimiter
    except csv.Error:
        candidates = [",", ";", "\t", "|"]
        counts = {d: sample.count(d) for d in candidates}
        best = max(counts, key=counts.get)
        return best if counts[best] > 0 else ","


def process_file(input_path: Path, output_path: Path) -> str:
    """Elabora un singolo file. Ritorna una stringa di esito da stampare."""
    with input_path.open("r", newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        delimiter = detect_delimiter(sample)
        rows = list(csv.reader(f, delimiter=delimiter))

    if not rows:
        return "NO - file vuoto"

    header = rows[0]
    data_rows = rows[1:]
    normalized_header = [h.strip().upper() for h in header]

    if COLUMN_NAME.upper() not in normalized_header:
        return f"NO - colonna '{COLUMN_NAME}' non trovata (header: {header})"

    idx_col = normalized_header.index(COLUMN_NAME.upper())

    new_rows = [header]
    changed_count = 0
    other_values_found = set()

    for row_num, row in enumerate(data_rows, start=2):
        if not row or all(cell.strip() == "" for cell in row):
            new_rows.append(row)
            continue

        if len(row) != len(header):
            return (f"NO - riga {row_num} ha {len(row)} campi, "
                     f"attesi {len(header)}: {row}")

        new_row = list(row)
        current_value = row[idx_col].strip()

        if current_value == OLD_VALUE:
            new_row[idx_col] = NEW_VALUE
            changed_count += 1
        elif current_value != NEW_VALUE:
            # valore diverso sia da quello atteso originale sia da quello
            # nuovo: lo segnalo ma non lo tocco
            other_values_found.add(current_value)

        new_rows.append(new_row)

    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with tmp_path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f, delimiter=delimiter).writerows(new_rows)
    tmp_path.replace(output_path)

    esito = f"fatto ({changed_count}/{len(data_rows)} righe modificate {OLD_VALUE}->{NEW_VALUE})"
    if other_values_found:
        esito += f" [ATTENZIONE: trovati anche valori diversi non toccati: {sorted(other_values_found)}]"
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

    print(f"Trovati {len(candidates)} file. Colonna: {COLUMN_NAME}, "
          f"{OLD_VALUE} -> {NEW_VALUE}. Overwrite = {OVERWRITE}\n")

    ok_count = 0
    err_count = 0

    for input_path in candidates:
        if OVERWRITE:
            output_path = input_path
        else:
            output_path = input_path.with_name(input_path.stem + "_fix" + input_path.suffix)

        try:
            esito = process_file(input_path, output_path)
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
