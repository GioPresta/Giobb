#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
copy_curve.py

Legge i file .rpt presenti in Q126 e Q226.

Per ogni file con lo stesso nome:
- prende da Q126 la relazione:

    PRODOTTO -> INDI_CURVA, MG_CURVA

- sostituisce in Q226 i valori:
    INDI_CURVA
    MG_CURVA

- salva il risultato nella cartella Results

Approccio FORMAT PRESERVING:
non usa csv, non riscrive il file con normalizzazioni.
Mantiene:
- encoding
- delimitatori
- virgolette
- spazi
- zeri iniziali
- struttura del file

Modifica solamente:
INDI_CURVA
MG_CURVA
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

DELIMITER_CANDIDATES = [",", ";", "\t", "|"]

# ==================================================



def get_script_dir():
    try:
        return Path(__file__).resolve().parent
    except NameError:
        return Path.cwd()



def read_text_preserving_encoding(path):

    raw = path.read_bytes()

    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            pass

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

                if i + 1 < len(content) and content[i + 1] == quote_char:
                    current.append(content[i + 1])
                    i += 1

                else:
                    in_quotes = False

        else:

            if c in ('"', "'"):

                in_quotes = True
                quote_char = c
                current.append(c)

            elif c == delimiter:

                fields.append("".join(current))
                current = []

            else:

                current.append(c)

        i += 1


    fields.append("".join(current))

    return fields



def strip_quotes_and_space(field):

    f = field.strip()

    if len(f) >= 2:

        if f[0] == f[-1] and f[0] in ('"', "'"):
            f = f[1:-1]

    return f.strip()



def detect_delimiter(content):

    best = None
    best_score = -1

    targets = set(REQUIRED_COLS)

    for d in DELIMITER_CANDIDATES:

        fields = split_fields_raw(content, d)

        cleaned = [
            strip_quotes_and_space(x).upper()
            for x in fields
        ]

        score = sum(
            1 for x in targets if x in cleaned
        )

        if score > best_score:

            best_score = score
            best = d


    if best_score == len(REQUIRED_COLS):
        return best

    return None



def replace_field_value(raw_field, new_value):

    quote = ""

    inner = raw_field


    if len(raw_field) >= 2:

        if raw_field[0] == raw_field[-1]:
            if raw_field[0] in ('"', "'"):

                quote = raw_field[0]
                inner = raw_field[1:-1]


    leading = len(inner) - len(inner.lstrip())
    trailing = len(inner) - len(inner.rstrip())


    left_space = inner[:leading]

    right_space = ""

    if trailing:
        right_space = inner[len(inner)-trailing:]


    return (
        quote
        + left_space
        + str(new_value)
        + right_space
        + quote
    )



def find_header(content):

    delimiter = detect_delimiter(content)

    if delimiter is None:
        return None


    fields = split_fields_raw(content, delimiter)


    cleaned = [
        strip_quotes_and_space(x).upper()
        for x in fields
    ]


    indexes = {}

    for col in REQUIRED_COLS:

        if col not in cleaned:
            return None

        indexes[col] = cleaned.index(col)


    return delimiter, indexes, len(fields)



def load_reference(file_path):

    """
    Legge Q126 e crea:

    PRODOTTO:
        INDI_CURVA
        MG_CURVA
    """

    text, encoding = read_text_preserving_encoding(file_path)

    lines = text.splitlines()


    header = None
    reference = {}


    for line in lines:

        if not line.strip():
            continue


        if header is None:

            header = find_header(line)

            continue


        fields = split_fields_raw(
            line,
            header[0]
        )


        if len(fields) != header[2]:
            continue


        try:

            prodotto = strip_quotes_and_space(
                fields[header[1]["PRODOTTO"]]
            )


            indi = fields[
                header[1]["INDI_CURVA"]
            ]


            mg = fields[
                header[1]["MG_CURVA"]
            ]


            if prodotto not in reference:

                reference[prodotto] = (
                    indi,
                    mg
                )


        except Exception:
            continue


    return reference



def process_target(
        input_file,
        output_file,
        reference):


    text, encoding = read_text_preserving_encoding(
        input_file
    )


    lines = text.splitlines(
        keepends=True
    )


    header = None

    modified = 0


    output = []


    for line in lines:

        content, ending = split_line_ending(line)


        if not content.strip():

            output.append(line)
            continue



        if header is None:

            found = find_header(content)

            if found:

                header = found

            output.append(line)
            continue



        fields = split_fields_raw(
            content,
            header[0]
        )


        if len(fields) != header[2]:

            output.append(line)
            continue


        prodotto = strip_quotes_and_space(
            fields[
                header[1]["PRODOTTO"]
            ]
        )


        if prodotto in reference:

            indi, mg = reference[prodotto]


            fields[
                header[1]["INDI_CURVA"]
            ] = indi


            fields[
                header[1]["MG_CURVA"]
            ] = mg


            modified += 1


            new_content = header[0].join(fields)

            output.append(
                new_content + ending
            )


        else:

            output.append(line)



    output_file.write_bytes(
        "".join(output).encode(
            encoding if encoding != "utf-8-sig"
            else "utf-8"
        )
    )


    return modified



def main():

    base = get_script_dir()


    q126 = base / SOURCE_FOLDER
    q226 = base / TARGET_FOLDER
    results = base / RESULT_FOLDER


    results.mkdir(
        exist_ok=True
    )


    files = sorted(
        q126.glob("*" + EXTENSION)
    )


    print(
        f"Trovati {len(files)} file in Q126\n"
    )


    ok = 0
    missing = 0


    for source_file in files:


        target_file = q226 / source_file.name


        if not target_file.exists():

            print(
                f"{source_file.name}: manca in Q226"
            )

            missing += 1
            continue



        print(
            f"\nElaboro {source_file.name}"
        )


        try:

            reference = load_reference(
                source_file
            )


            output_file = (
                results / source_file.name
            )


            modified = process_target(
                target_file,
                output_file,
                reference
            )


            print(
                f"  Prodotti caricati: {len(reference)}"
            )

            print(
                f"  Righe modificate: {modified}"
            )


            ok += 1


        except Exception as e:

            print(
                f"  ERRORE: {e}"
            )



    print("\n==============================")
    print(
        f"Completato: {ok} file elaborati"
    )
    print(
        f"File mancanti: {missing}"
    )
    print("==============================")



if __name__ == "__main__":
    main()