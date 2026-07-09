        indi_q126, mg_q126 = reference[prodotto]


        indi_q226 = fields[
            header[1]["INDI_CURVA"]
        ]


        mg_q226 = fields[
            header[1]["MG_CURVA"]
        ]



        # confronto Q226 contro Q126

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



        # Se già uguali:
        # lascio la riga originale identica

        if stesso_indi and stesso_mg:


            unchanged += 1

            output.append(line)

            continue




        # Altrimenti sostituisco

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



    return (
        modified,
        unchanged,
        not_found
    )





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



    elaborati = 0

    mancanti = 0




    for source_file in files:



        target_file = (
            q226 /
            source_file.name
        )




        if not target_file.exists():


            print(
                f"\n{source_file.name}: "
                "NON PRESENTE in Q226"
            )


            mancanti += 1

            continue





        print(
            "\n=============================="
        )


        print(
            "File:",
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



            modified, unchanged, not_found = process_target(
                target_file,
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
                "Righe già corrette (non modificate):",
                unchanged
            )


            print(
                "Prodotti non trovati in Q126:",
                not_found
            )


            print(
                "Creato:",
                output_file.name
            )



            elaborati += 1



        except Exception as e:


            print(
                "ERRORE:",
                e
            )




    print(
        "\n=============================="
    )

    print(
        "FINE ELABORAZIONE"
    )

    print(
        "File elaborati:",
        elaborati
    )

    print(
        "File mancanti:",
        mancanti
    )

    print(
        "Cartella risultati:",
        results
    )

    print(
        "=============================="
    )




if __name__ == "__main__":

    main()