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
    Legge Q126.

    Crea:

    {
        PRODOTTO:
            (
              INDI_CURVA,
              MG_CURVA
            )
    }
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

    unchanged = 0

    not_found = 0



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


            not_found += 1

            output.append(line)

            continue