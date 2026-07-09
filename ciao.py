#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
compare_curve.py

Confronta file .rpt omonimi:

Q126  --->  Q226

Usa:
    PRODOTTO

Da Q126 prende:
    INDI_CURVA
    MG_CURVA

In Q226:
    - se uguali -> lascia la riga identica
    - se diversi -> sostituisce solo i due campi


Output:

Results/
    file.rpt
    LOG_MODIFICHE.txt


Il log contiene:
    - prodotto modificato
    - valore precedente
    - valore nuovo


FORMAT PRESERVING:
    - niente csv
    - mantiene encoding
    - mantiene separatori
    - mantiene virgolette
    - mantiene spazi
"""


from pathlib import Path



# ================= CONFIGURAZIONE =================


EXTENSION = ".rpt"

Q126_FOLDER = "Q126"
Q226_FOLDER = "Q226"
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




def load_q126(file_path):

    """
    Crea la mappa:

    PRODOTTO:
        INDI_CURVA
        MG_CURVA
    """


    text, encoding = read_text_preserving_encoding(
        file_path
    )


    lines = text.splitlines()


    reference = {}

    active_header = None



    for line in lines:


        if not line.strip():
            continue



        header = detect_header(line)


        if header:

            active_header = header

            continue



        if active_header is None:

            continue



        fields = split_fields_raw(
            line,
            active_header[0]
        )


        if len(fields) != active_header[2]:

            continue



        try:


            prodotto = strip_quotes_and_space(
                fields[
                    active_header[1]["PRODOTTO"]
                ]
            )


            indi = fields[
                active_header[1]["INDI_CURVA"]
            ]


            mg = fields[
                active_header[1]["MG_CURVA"]
            ]



            if prodotto not in reference:

                reference[prodotto] = (
                    indi,
                    mg
                )



        except Exception:

            continue



    return reference





def process_q226(
        file_q226,
        output_file,
        reference,
        log_file):


    text, encoding = read_text_preserving_encoding(
        file_q226
    )


    lines = text.splitlines(
        keepends=True
    )


    output = []


    active_header = None


    modified = 0

    same = 0

    missing = 0



    modifications = []



    for line in lines:


        content, ending = split_line_ending(line)



        if not content.strip():

            output.append(line)

            continue




        header = detect_header(content)



        if header:

            active_header = header

            output.append(line)

            continue



        if active_header is None:

            output.append(line)

            continue



        fields = split_fields_raw(
            content,
            active_header[0]
        )


        if len(fields) != active_header[2]:

            output.append(line)

            continue



        prodotto = strip_quotes_and_space(
            fields[
                active_header[1]["PRODOTTO"]
            ]
        )



        if prodotto not in reference:

            missing += 1

            output.append(line)

            continue


        indi_q126, mg_q126 = reference[prodotto]


        indi_q226 = fields[
            active_header[1]["INDI_CURVA"]
        ]


        mg_q226 = fields[
            active_header[1]["MG_CURVA"]
        ]



        stesso_indi = (
            strip_quotes_and_space(indi_q126)
            ==
            strip_quotes_and_space(indi_q226)
        )


        stesso_mg = (
            strip_quotes_and_space(mg_q126)
            ==
            strip_quotes_and_space(mg_q226)
        )



        # già uguali:
        # lascio la riga esattamente com'è

        if stesso_indi and stesso_mg:

            same += 1

            output.append(line)

            continue




        # registro modifica

        modifications.append(
            {
                "PRODOTTO": prodotto,

                "INDI_VECCHIO":
                    strip_quotes_and_space(
                        indi_q226
                    ),

                "INDI_NUOVO":
                    strip_quotes_and_space(
                        indi_q126
                    ),

                "MG_VECCHIO":
                    strip_quotes_and_space(
                        mg_q226
                    ),

                "MG_NUOVO":
                    strip_quotes_and_space(
                        mg_q126
                    )
            }
        )



        fields[
            active_header[1]["INDI_CURVA"]
        ] = indi_q126



        fields[
            active_header[1]["MG_CURVA"]
        ] = mg_q126



        new_content = active_header[0].join(fields)


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



    with open(
        log_file,
        "a",
        encoding="utf-8"
    ) as f:


        f.write(
            "\n==============================\n"
        )

        f.write(
            f"FILE: {file_q226.name}\n"
        )

        f.write(
            "==============================\n\n"
        )



        for item in modifications:


            f.write(
                f"PRODOTTO: {item['PRODOTTO']}\n"
            )


            f.write(
                "INDI_CURVA\n"
            )

            f.write(
                f"  Prima: {item['INDI_VECCHIO']}\n"
            )

            f.write(
                f"  Dopo : {item['INDI_NUOVO']}\n\n"
            )


            f.write(
                "MG_CURVA\n"
            )

            f.write(
                f"  Prima: {item['MG_VECCHIO']}\n"
            )

            f.write(
                f"  Dopo : {item['MG_NUOVO']}\n\n"
            )



    return (
        modified,
        same,
        missing
    )





def main():


    base = get_script_dir()


    q126_folder = base / Q126_FOLDER

    q226_folder = base / Q226_FOLDER

    results = base / RESULT_FOLDER



    results.mkdir(
        exist_ok=True
    )



    log_file = (
        results /
        "LOG_MODIFICHE.txt"
    )


    with open(
        log_file,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            "LOG MODIFICHE INDI_CURVA MG_CURVA\n"
        )



    files = sorted(
        q126_folder.glob(
            "*" + EXTENSION
        )
    )



    for file_q126 in files:


        file_q226 = (
            q226_folder /
            file_q126.name
        )



        if not file_q226.exists():

            print(
                file_q126.name,
                "manca in Q226"
            )

            continue



        print(
            "\nFILE:",
            file_q126.name
        )



        reference = load_q126(
            file_q126
        )



        modified, same, missing = process_q226(
            file_q226,
            results / file_q226.name,
            reference,
            log_file
        )



        print(
            "Prodotti caricati:",
            len(reference)
        )

        print(
            "Modificati:",
            modified
        )

        print(
            "Già uguali:",
            same
        )

        print(
            "Non trovati:",
            missing
        )



    print(
        "\nFine elaborazione"
    )

    print(
        "Log creato:",
        log_file
    )





if __name__ == "__main__":

    main()