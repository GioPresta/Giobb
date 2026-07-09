#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
copy_curve.py

COPIA INDI_CURVA e MG_CURVA da Q126 verso Q226
usando PRODOTTO come chiave.

Struttura:

cartella_script/
│
├── copy_curve.py
├── Q126/
│   ├── file1.rpt
│   └── file2.rpt
│
├── Q226/
│   ├── file1.rpt
│   └── file2.rpt
│
└── Results/
    └── output .rpt


Approccio FORMAT PRESERVING:
- non usa csv
- mantiene encoding
- mantiene delimitatore
- mantiene virgolette
- mantiene spazi
- modifica solo INDI_CURVA e MG_CURVA
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



def detect_header(content):

    for delimiter in DELIMITER_CANDIDATES:

        fields = split_fields_raw(
            content,
            delimiter
        )


        cleaned = [
            strip_quotes_and_space(x).upper()
            for x in fields
        ]


        score = sum(
            1
            for col in REQUIRED_COLS
            if col in cleaned
        )


        if score == len(REQUIRED_COLS):

            indexes = {}

            for col in REQUIRED_COLS:

                indexes[col] = cleaned.index(col)


            return (
                delimiter,
                indexes,
                len(fields)
            )


    return None

def load_reference(file_path):

    """
    Legge Q126 e crea il dizionario:

    PRODOTTO:
        INDI_CURVA
        MG_CURVA
    """

    text, encoding = read_text_preserving_encoding(
        file_path
    )


    lines = text.splitlines()


    header = None

    reference = {}


    for line in lines:

        if not line.strip():
            continue


        if header is None:

            header = detect_header(line)

            continue


        fields = split_fields_raw(
            line,
            header[0]
        )


        if len(fields) != header[2]:
            continue


        try:

            prodotto = strip_quotes_and_space(
                fields[
                    header[1]["PRODOTTO"]
                ]
            )


            indi = fields[
                header[1]["INDI_CURVA"]
            ]


            mg = fields[
                header[1]["MG_CURVA"]
            ]


            # stesso prodotto può ripetersi migliaia di volte,
            # salvo solo il primo valore trovato

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

    output = []

    modified = 0


    for line in lines:

        content, ending = split_line_ending(line)


        if not content.strip():

            output.append(line)
            continue



        if header is None:

            found = detect_header(content)


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



        if prodotto not in reference:

            output.append(line)

            continue



        indi_q126, mg_q126 = reference[prodotto]



        indi_q226 = fields[
            header[1]["INDI_CURVA"]
        ]


        mg_q226 = fields[
            header[1]["MG_CURVA"]
        ]



        # controllo se sono già uguali

        stesso_indi = (
            strip_quotes_and_space(indi_q226)
            ==
            strip_quotes_and_space(indi_q126)
        )


        stesso_mg = (
            strip_quotes_and_space(mg_q226)
            ==
            strip_quotes_and_space(mg_q126)
        )



        # se già uguali lascio la riga originale

        if stesso_indi and stesso_mg:

            output.append(line)

            continue



        # altrimenti sostituisco

        fields[
            header[1]["INDI_CURVA"]
        ] = indi_q126


        fields[
            header[1]["MG_CURVA"]
        ] = mg_q126



        new_content = header[0].join(fields)


        output.append(
            new_content + ending
        )


        modified += 1



    output_file.write_bytes(
        "".join(output).encode(
            encoding
            if encoding != "utf-8-sig"
            else "utf-8"
        )
    )


    return modified



def main():

    base = get_script_dir()


    q126 = base / SOURCE_FOLDER

    q226 = base / TARGET_FOLDER

    results = base / RESULT_FOLDER



    if not q126.exists():

        print(
            "ERRORE: cartella Q126 non trovata"
        )

        return



    if not q226.exists():

        print(
            "ERRORE: cartella Q226 non trovata"
        )

        return



    results.mkdir(
        exist_ok=True
    )



    files = sorted(
        q126.glob("*" + EXTENSION)
    )



    print(
        f"Trovati {len(files)} file in Q126"
    )



    ok = 0

    missing = 0



    for source_file in files:


        target_file = (
            q226 / source_file.name
        )



        if not target_file.exists():

            print(
                f"{source_file.name}: "
                "manca in Q226"
            )

            missing += 1

            continue



        print(
            "\nElaboro:",
            source_file.name
        )



        try:


            reference = load_reference(
                source_file
            )


            output_file = (
                results /
                source_file.name
            )


            modified = process_target(
                target_file,
                output_file,
                reference
            )



            print(
                "  Prodotti caricati:",
                len(reference)
            )


            print(
                "  Righe realmente modificate:",
                modified
            )


            ok += 1



        except Exception as e:


            print(
                "  ERRORE:",
                e
            )



    print(
        "\n=============================="
    )

    print(
        "File elaborati:",
        ok
    )

    print(
        "File mancanti:",
        missing
    )

    print(
        "Output:",
        results
    )

    print(
        "=============================="
    )



if __name__ == "__main__":

    main()