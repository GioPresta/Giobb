#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
compare_curve.py

Confronta file .rpt omonimi tra:

Q126/
Q226/

Usa PRODOTTO come chiave.

Da Q126 prende:
    INDI_CURVA
    MG_CURVA

Su Q226:
    - se INDI_CURVA e MG_CURVA sono uguali:
        lascia la riga originale

    - se almeno uno è diverso:
        sostituisce solo quei due campi con i valori di Q126


Output:
    Results/


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

FOLDER_Q126 = "Q126"
FOLDER_Q226 = "Q226"
FOLDER_RESULTS = "Results"


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

def detect_header_for_line(content):

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



def load_q126_reference(file_path):

    """
    Legge il file Q126.

    Restituisce:

    {
        PRODOTTO:
            {
              "INDI_CURVA": valore,
              "MG_CURVA": valore
            }
    }
    """

    text, encoding = read_text_preserving_encoding(
        file_path
    )


    lines = text.splitlines(
        keepends=False
    )


    reference = {}

    active_header = None



    for line in lines:


        if not line.strip():
            continue



        header = detect_header_for_line(line)


        # gestione header ripetuti
        if header is not None:

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



            # ogni prodotto ha sempre gli stessi valori
            # salvo solo il primo trovato

            if prodotto not in reference:

                reference[prodotto] = (
                    indi,
                    mg
                )



        except Exception:

            continue



    return reference



def process_q226_file(
        q226_file,
        output_file,
        reference):


    text, encoding = read_text_preserving_encoding(
        q226_file
    )


    lines = text.splitlines(
        keepends=True
    )


    output = []


    active_header = None


    modified = 0

    already_equal = 0

    not_found = 0



    for line in lines:


        content, ending = split_line_ending(line)



        if not content.strip():

            output.append(line)

            continue



        header = detect_header_for_line(content)



        # gestione header ripetuti Q226
        if header is not None:

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



        try:


            prodotto = strip_quotes_and_space(
                fields[
                    active_header[1]["PRODOTTO"]
                ]
            )



        except Exception:


            output.append(line)

            continue



        if prodotto not in reference:

            not_found += 1

            output.append(line)

            continue



        indi_q126, mg_q126 = reference[prodotto]



        indi_q226 = fields[
            active_header[1]["INDI_CURVA"]
        ]


        mg_q226 = fields[
            active_header[1]["MG_CURVA"]
        ]



        # confronto Q226 contro Q126

        same_indi = (
            strip_quotes_and_space(indi_q226)
            ==
            strip_quotes_and_space(indi_q126)
        )


        same_mg = (
            strip_quotes_and_space(mg_q226)
            ==
            strip_quotes_and_space(mg_q126)
        )



        # già uguali:
        # lascio la riga IDENTICA

        if same_indi and same_mg:

            already_equal += 1

            output.append(line)

            continue



        # diversi:
        # sostituisco solo i due campi

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


    return (
        modified,
        already_equal,
        not_found
    )





def main():

    base = get_script_dir()


    q126_folder = base / FOLDER_Q126

    q226_folder = base / FOLDER_Q226

    results_folder = base / FOLDER_RESULTS



    results_folder.mkdir(
        exist_ok=True
    )



    q126_files = sorted(
        q126_folder.glob("*" + EXTENSION)
    )



    print(
        f"Trovati {len(q126_files)} file in Q126"
    )



    total_modified = 0

    total_equal = 0

    total_not_found = 0



    for q126_file in q126_files:


        q226_file = (
            q226_folder /
            q126_file.name
        )



        if not q226_file.exists():

            print(
                f"\n{q126_file.name}: "
                "manca in Q226"
            )

            continue



        print(
            "\n=============================="
        )

        print(
            "FILE:",
            q126_file.name
        )



        reference = load_q126_reference(
            q126_file
        )



        output_file = (
            results_folder /
            q126_file.name
        )



        modified, equal, not_found = process_q226_file(
            q226_file,
            output_file,
            reference
        )



        print(
            "Prodotti caricati da Q126:",
            len(reference)
        )


        print(
            "Righe modificate:",
            modified
        )


        print(
            "Righe già uguali:",
            equal
        )


        print(
            "Prodotti non trovati:",
            not_found
        )



        total_modified += modified

        total_equal += equal

        total_not_found += not_found




    print(
        "\n=============================="
    )

    print(
        "FINE"
    )

    print(
        "Totale righe modificate:",
        total_modified
    )

    print(
        "Totale righe già uguali:",
        total_equal
    )

    print(
        "Totale prodotti non trovati:",
        total_not_found
    )

    print(
        "Output:",
        results_folder
    )

    print(
        "=============================="
    )





if __name__ == "__main__":

    main()