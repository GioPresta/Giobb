#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cerca_prodotto.py

TOOL SEPARATO, stessa logica degli altri due.
PENSATO PER SPYDER: mettilo nella STESSA CARTELLA dei file .rpt e lancialo
con F5 (Run). Non servono argomenti da riga di comando.

Cosa fa:
- Trova tutti i file con estensione EXTENSION nella cartella dello script
- Legge la colonna COLUMN_NAME (default "Prodotto")
- Cerca il valore SEARCH_VALUE (scrivilo qui sotto in CONFIGURAZIONE)
- Stampa, per ogni corrispondenza trovata: nome del file e numero di riga
- Non modifica NESSUN file: è solo una ricerca

Puoi cambiare le impostazioni qui sotto in CONFIGURAZIONE.
"""

import csv
from pathlib import Path

# ======================= CONFIGURAZIONE =======================

# Estensione dei file da processare. Metti None per processare TUTTI i
# file nella cartella (indipendentemente dall'estensione).
EXTENSION = ".rpt"

# Nome della colonna in cui cercare
COLUMN_NAME = "Prodotto"

# Valore da cercare -> SCRIVILO QUI
SEARCH_VALUE = "SCRIVI_QUI_IL_VALORE"

# True  = confronto esatto (case-insensitive, spazi ignorati)
# False = corrispondenza "contiene" (utile se non sai il valore esatto)
EXACT_MATCH = True

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


def search_file(input_path: Path, search_value: str, exact_match: bool):
    """
    Cerca il valore nel file. Ritorna (esito_str, lista_di_match)
    dove ogni match è (numero_riga, riga_completa).
    """
    with input_path.open("r", newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        delimiter = detect_delimiter(sample)
        rows = list(csv.reader(f, delimiter=delimiter))

    if not rows:
        return "NO - file vuoto", []

    header = rows[0]
    data_rows = rows[1:]
    normalized_header = [h.strip().upper() for h in header]

    if COLUMN_NAME.upper() not in normalized_header:
        return f"NO - colonna '{COLUMN_NAME}' non trovata (header: {header})", []

    idx_col = normalized_header.index(COLUMN_NAME.upper())

    target = search_value.strip().lower()
    matches = []

    for row_num, row in enumerate(data_rows, start=2):  # 2 = prima riga dati (dopo header)
        if not row or all(cell.strip() == "" for cell in row):
            continue
        if idx_col >= len(row):
            continue

        cell_value = row[idx_col].strip().lower()

        if exact_match:
            found = cell_value == target
        else:
            found = target in cell_value

        if found:
            matches.append((row_num, row))

    if matches:
        return f"trovato {len(matches)} corrispondenze", matches
    return "nessuna corrispondenza", []


def main():
    script_dir = get_script_dir()
    print(f"Cartella di lavoro: {script_dir}")

    if SEARCH_VALUE == "SCRIVI_QUI_IL_VALORE":
        print("ATTENZIONE: devi impostare SEARCH_VALUE in CONFIGURAZIONE "
              "prima di lanciare lo script.")
        return

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

    print(f"Trovati {len(candidates)} file da esaminare. "
          f"Cerco '{SEARCH_VALUE}' nella colonna '{COLUMN_NAME}' "
          f"(exact_match={EXACT_MATCH}).\n")

    total_matches = 0

    for input_path in candidates:
        try:
            esito, matches = search_file(input_path, SEARCH_VALUE, EXACT_MATCH)
        except Exception as e:
            esito, matches = f"NO - errore imprevisto: {e}", []

        print(f"{input_path.name}: {esito}")
        for row_num, row in matches:
            print(f"    -> riga {row_num}: {row}")
        total_matches += len(matches)

    print(f"\nCompletato: {total_matches} corrispondenze totali trovate "
          f"in {len(candidates)} file esaminati.")


if __name__ == "__main__":
    main()
