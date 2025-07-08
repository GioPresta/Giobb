import os
import re

# Regex per rilevare la riga di fine sezione (es. *****...)
END_SECTION_PATTERN = re.compile(r'^\s*\*{5,}\s*$')
# Righe di decorazione (es. ----, ===, ...)
DECORATION_PATTERN = re.compile(r'^[\s\-\*=_\.]{4,}$')
# Righe che iniziano con LIVELLO (ignora maiuscole)
START_HEADER_PATTERN = re.compile(r'^\s*LIVELLO\b', re.IGNORECASE)

def extract_error_lines(file_path, header_collected):
    with open(file_path, 'r', encoding='utf-8') as f:
        in_section = False
        collected = []
        for line in f:
            if not in_section:
                if START_HEADER_PATTERN.match(line):
                    in_section = True
                    if not header_collected[0]:
                        header_collected[0] = line.strip()  # salva una sola intestazione
            else:
                if END_SECTION_PATTERN.match(line):
                    break
                elif not DECORATION_PATTERN.match(line) and line.strip():
                    collected.append(line.rstrip())
        return collected

def merge_all_reports(output_file='riepilogo.txt'):
    current_dir = os.getcwd()
    txt_files = [f for f in os.listdir(current_dir)
                 if f.endswith('.txt') and f != output_file]

    all_lines = []
    header = [None]  # lista con un solo elemento mutabile (trucchetto Python)

    for txt_file in txt_files:
        file_path = os.path.join(current_dir, txt_file)
        lines = extract_error_lines(file_path, header)
        all_lines.extend(lines)

    with open(output_file, 'w', encoding='utf-8') as out:
        if header[0]:
            out.write(header[0] + '\n')  # scrive una sola intestazione
        out.write('\n'.join(all_lines))
        out.write('\n')

    print(f"✔ Report unificato salvato in '{output_file}'.")

if __name__ == "__main__":
    merge_all_reports()
