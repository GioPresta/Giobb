#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
retrodata_fac.py

PENSATO PER SPYDER: mettilo nella STESSA CARTELLA dei file .rpt (o .fac)
e lancialo con F5 (Run). Non servono argomenti da riga di comando.

Cosa fa:
- Trova tutti i file con estensione EXTENSION nella cartella dello script
- Legge le colonne BIRTH_YEAR, ENTRY_YEAR, ENTRY_MONTH, BIRTH_MONTH
- Retrodata di MONTHS mesi le coppie (ENTRY_YEAR, ENTRY_MONTH) e
  (BIRTH_YEAR, BIRTH_MONTH), ragionando anno e mese INSIEME. Esempio:
      ENTRY_YEAR 2026, ENTRY_MONTH 3  ->  ENTRY_YEAR 2025, ENTRY_MONTH 9
      BIRTH_YEAR 1973, BIRTH_MONTH 1  ->  BIRTH_YEAR 1972, BIRTH_MONTH 7
- Sovrascrive ogni file originale (se OVERWRITE = True)
- Stampa un log per ogni file: "fatto" oppure il motivo per cui è saltato

Puoi cambiare le impostazioni qui sotto in CONFIGURAZIONE.
"""

import csv
from pathlib import Path

# ======================= CONFIGURAZIONE =======================

# Estensione dei file da processare. Metti None per processare TUTTI i
# file nella cartella (indipendentemente dall'estensione).
EXTENSION = ".rpt"

# Quanti mesi retrodatare (positivo = indietro nel tempo, come richiesto)
MONTHS = 6

# True  = sovrascrive i file originali
# False = crea una copia "nome_retro.rpt" accanto all'originale, senza
#         toccare quello originale
OVERWRITE = True

# ================================================================


def get_script_dir() -> Path:
    """Restituisce la cartella in cui si trova questo script.
    Funziona sia lanciato da terminale sia da Spyder (F5)."""
    try:
        return Path(__file__).resolve().parent
    except NameError:
        # __file__ non definito (es. eseguito riga per riga in console
        # interattiva): uso la cartella corrente di lavoro
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


def shift_year_month(year: int, month: int, months_delta: int):
    """
    Sposta indietro una coppia (anno, mese) di months_delta mesi,
    ragionando anno e mese insieme.
    Esempio: shift_year_month(2026, 3, 6) -> (2025, 9)
    """
    absolute_month = year * 12 + (month - 1)
    absolute_month -= months_delta
    new_year, new_month0 = divmod(absolute_month, 12)
    return new_year, new_month0 + 1


def process_file(input_path: Path, output_path: Path, months_delta: int) -> str:
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

    required_cols = ["BIRTH_YEAR", "ENTRY_YEAR", "ENTRY_MONTH", "BIRTH_MONTH"]
    missing = [c for c in required_cols if c not in normalized_header]
    if missing:
        return f"NO - colonne mancanti: {missing} (header trovato: {header})"

    idx_birth_year = normalized_header.index("BIRTH_YEAR")
    idx_entry_year = normalized_header.index("ENTRY_YEAR")
    idx_entry_month = normalized_header.index("ENTRY_MONTH")
    idx_birth_month = normalized_header.index("BIRTH_MONTH")

    # TYPE_ASSURED è opzionale: se presente e vale 1 sulla riga, non
    # retrodato BIRTH_YEAR/BIRTH_MONTH per quella riga
    idx_type_assured = (
        normalized_header.index("TYPE_ASSURED")
        if "TYPE_ASSURED" in normalized_header else None
    )

    new_rows = [header]

    for row_num, row in enumerate(data_rows, start=2):
        if not row or all(cell.strip() == "" for cell in row):
            new_rows.append(row)
            continue

        if len(row) != len(header):
            return (f"NO - riga {row_num} ha {len(row)} campi, "
                     f"attesi {len(header)}: {row}")

        new_row = list(row)
        try:
            entry_year = int(row[idx_entry_year].strip())
            entry_month = int(row[idx_entry_month].strip())
            birth_year = int(row[idx_birth_year].strip())
            birth_month = int(row[idx_birth_month].strip())
        except ValueError as e:
            return f"NO - riga {row_num}: valore non numerico ({e})"

        new_entry_year, new_entry_month = shift_year_month(entry_year, entry_month, months_delta)
        new_row[idx_entry_year] = str(new_entry_year)
        new_row[idx_entry_month] = str(new_entry_month)

        # Controllo se questa riga ha TYPE_ASSURED = 1: in quel caso
        # BIRTH_YEAR/BIRTH_MONTH restano invariati
        skip_birth = False
        if idx_type_assured is not None:
            type_assured_val = row[idx_type_assured].strip()
            if type_assured_val == "1":
                skip_birth = True

        if not skip_birth:
            new_birth_year, new_birth_month = shift_year_month(birth_year, birth_month, months_delta)
            new_row[idx_birth_year] = str(new_birth_year)
            new_row[idx_birth_month] = str(new_birth_month)

        new_rows.append(new_row)

    # Scrivo su file temporaneo e poi sostituisco (scrittura sicura anche
    # quando sto sovrascrivendo il file originale)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with tmp_path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f, delimiter=delimiter).writerows(new_rows)
    tmp_path.replace(output_path)

    return f"fatto (delimitatore: {delimiter!r}, {len(data_rows)} righe)"


def main():
    script_dir = get_script_dir()
    print(f"Cartella di lavoro: {script_dir}")

    if EXTENSION:
        candidates = sorted(script_dir.glob(f"*{EXTENSION}"))
    else:
        candidates = sorted(p for p in script_dir.iterdir() if p.is_file())

    # Escludo lo script stesso e eventuali file temporanei
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
