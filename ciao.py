#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
copy_curve.py

Confronta i file .rpt presenti in Q126 e Q226.

Chiave:
    PRODOTTO

Da Q126 prende:
    INDI_CURVA
    MG_CURVA

Su Q226:
    - se INDI_CURVA e MG_CURVA sono uguali:
        NON MODIFICA LA RIGA

    - se diversi:
        sostituisce solo INDI_CURVA e MG_CURVA

Output:
    Results/

Statistiche:
    - prodotti caricati da Q126
    - righe modificate
    - righe già corrette (non modificate)
    - prodotti non trovati in Q126


Approccio FORMAT PRESERVING:
    - niente csv
    - mantiene encoding
    - mantiene delimitatore
    - mantiene virgolette
    - mantiene spazi
    - modifica solo i campi necessari
"""


from pathlib import Path



# ================= CONFIGURAZIONE =================


EXTENSION = ".rpt"

SOURCE_FOLDER = "Q126"
TARGET_FOLDER = "Q226"
RESULT_FOLDER = "Results"


REQUIRED_COLS = [
    "PRODOTTO",
    "INDI_CURVA",
    "MG_CURVA"
]


DELIMITER_CANDIDATES = [
    ",",
    ";",
    "\t",
    "|"
]


# ==================================================



def get_script_dir():

    try:
        return Path(__file__).resolve().parent

    except NameError:
        return Path.cwd()



def read_text_preserving_encoding(path):

    raw = path.read_bytes()

    for enc in (
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin-1"
    ):

        try:
            return raw.decode(enc), enc

        except UnicodeDecodeError:
            continue


    return raw.decode("latin-1"), "latin-1"



def split_line_ending(line):

    if line.endswith("\r\n"):
        return line[:-2], "\r\n"

    if line.endswith("\n"):
        return line[:-1], "\n"

    if line.endswith("\r"):
        return line[:-1], "\r"

    return line, ""



def split_fields_raw(content, delimiter):

    fields = []

    current = []

    in_quotes = False

    quote_char = None


    i = 0


    while i < len(content):

        c = content[i]


        if in_quotes:

            current.append(c)


            if c == quote_char:

                if (
                    i + 1 < len(content)
                    and content[i + 1] == quote_char
                ):

                    current.append(
                        content[i + 1]
                    )

                    i += 1

                else:

                    in_quotes = False


        else:

            if c in ('"', "'"):

                in_quotes = True

                quote_char = c

                current.append(c)


            elif c == delimiter:

                fields.append(
                    "".join(current)
                )

                current = []


            else:

                current.append(c)


        i += 1


    fields.append(
        "".join(current)
    )


    return fields



def strip_quotes_and_space(field):

    f = field.strip()


    if len(f) >= 2:

        if (
            f[0] == f[-1]
            and f[0] in ('"', "'")
        ):

            f = f[1:-1]


    return f.strip()