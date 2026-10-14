"""Conversione veloce TXT delimitato da ; in XLSX, anche per file grandi.
Dipendenza: py -m pip install XlsxWriter
"""
import csv
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import xlsxwriter

MAX_ROWS = 1_048_576

def convert(source, update):
    target = os.path.splitext(source)[0] + '.xlsx'
    if os.path.abspath(source).lower() == os.path.abspath(target).lower():
        raise ValueError('Percorso di destinazione non valido')
    workbook = xlsxwriter.Workbook(target, {'constant_memory': True, 'strings_to_urls': False, 'strings_to_formulas': False})
    count = 0
    sheet = None
    try:
        with open(source, 'r', encoding='utf-8-sig', errors='replace', newline='') as infile:
            reader = csv.reader(infile, delimiter=';', quoting=csv.QUOTE_NONE)
            for fields in reader:
                if count % MAX_ROWS == 0:
                    sheet = workbook.add_worksheet(f'Dati_{count // MAX_ROWS + 1}')
                row = count % MAX_ROWS
                for col, field in enumerate(fields):
                    if col >= 16_384:
                        raise ValueError(f'Troppe colonne alla riga {count + 1}')
                    if field:
                        sheet.write_string(row, col, field)
                count += 1
                if count % 10000 == 0:
                    update(count)
        if sheet is None:
            workbook.add_worksheet('Dati_1')
        workbook.close()
    except Exception:
        try:
            workbook.close()
        except Exception:
            pass
        if os.path.exists(target):
            os.remove(target)
        raise
    return target, count


def main():
    root = tk.Tk()
    root.title('TXT → XLSX veloce')
    root.geometry('580x190')
    selected = tk.StringVar()
    status = tk.StringVar(value='Seleziona un file TXT')
    frame = ttk.Frame(root, padding=15)
    frame.pack(fill='both', expand=True)
    ttk.Entry(frame, textvariable=selected).pack(fill='x', pady=4)

    def choose():
        path = filedialog.askopenfilename(filetypes=[('File TXT', '*.txt'), ('Tutti i file', '*.*')])
        if path:
            selected.set(path)

    def update(n):
        root.after(0, lambda: status.set(f'Elaborate {n:,} righe...'.replace(',', '.')))

    def run():
        source = selected.get()
        if not os.path.isfile(source):
            messagebox.showerror('Errore', 'Seleziona un file valido.')
            return
        start_button.config(state='disabled')
        status.set('Conversione in corso...')
        def worker():
            try:
                target, n = convert(source, update)
                root.after(0, lambda: (status.set(f'Completato: {n:,} righe'.replace(',', '.')), messagebox.showinfo('Completato', f'File creato:\n{target}')))
            except Exception as exc:
                error = str(exc)
                root.after(0, lambda: messagebox.showerror('Errore', error))
                root.after(0, lambda: status.set('Conversione non completata'))
            finally:
                root.after(0, lambda: start_button.config(state='normal'))
        threading.Thread(target=worker, daemon=True).start()

    ttk.Button(frame, text='Sfoglia...', command=choose).pack(pady=5)
    start_button = ttk.Button(frame, text='CONVERTI IN XLSX', command=run)
    start_button.pack(pady=5)
    ttk.Label(frame, textvariable=status).pack(pady=5)
    root.mainloop()

if __name__ == '__main__':
    main()
