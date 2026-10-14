
import os
import csv
import time
import queue
import threading
import traceback
import tempfile
import tkinter as tk

from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import xlsxwriter


MAX_ROWS = 1_048_576
UPDATE_EVERY = 5000


def convert_txt(source, progress):
    source = Path(source)
    total_bytes = source.stat().st_size
    processed = 0
    row_count = 0
    sheet_count = 1
    started = time.perf_counter()

    output = source.with_name(
        source.stem + "_CONVERTITO.xlsx"
    )

    if output.exists():
        output = source.with_name(
            source.stem + "_" +
            time.strftime("%Y%m%d_%H%M%S") +
            ".xlsx"
        )

    # File temporaneo nella cartella di destinazione.
    # Il file finale compare solo a conversione conclusa.
    fd, temp_path = tempfile.mkstemp(
        prefix="txt_excel_",
        suffix=".xlsx",
        dir=str(source.parent)
    )
    os.close(fd)

    workbook = None

    try:
        workbook = xlsxwriter.Workbook(
            temp_path,
            {
                "constant_memory": True,
                "strings_to_numbers": False,
                "strings_to_formulas": False,
                "strings_to_urls": False,
                "tmpdir": str(source.parent),
            }
        )

        worksheet = workbook.add_worksheet("Dati_1")
        sheet_row = 0

        with open(
            source,
            "r",
            encoding="utf-8-sig",
            errors="replace",
            newline=""
        ) as file:

            reader = csv.reader(
                file,
                delimiter=";",
                quotechar='"'
            )

            for fields in reader:

                if sheet_row >= MAX_ROWS:
                    sheet_count += 1
                    worksheet = workbook.add_worksheet(
                        f"Dati_{sheet_count}"
                    )
                    sheet_row = 0

                for col, value in enumerate(fields):
                    if col >= 16384:
                        raise ValueError(
                            "Superato il limite di colonne Excel."
                        )

                    # Tutto viene scritto come testo:
                    # conserva 000123, codici e date originali.
                    worksheet.write_string(
                        sheet_row,
                        col,
                        value
                    )

                sheet_row += 1
                row_count += 1

                if row_count % UPDATE_EVERY == 0:
                    # tell() non è disponibile sul file
                    # durante l'iterazione CSV.
                    elapsed = time.perf_counter() - started
                    speed = row_count / max(elapsed, 0.001)

                    progress.put((
                        "progress",
                        row_count,
                        speed,
                        sheet_count
                    ))

        # La chiusura comprime e completa il file XLSX.
        progress.put(("status", "Finalizzazione XLSX..."))
        workbook.close()
        workbook = None

        os.replace(temp_path, output)

        elapsed = time.perf_counter() - started

        progress.put((
            "done",
            str(output),
            row_count,
            elapsed
        ))

    except Exception:
        error = traceback.format_exc()

        if workbook is not None:
            try:
                workbook.close()
            except Exception:
                pass

        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass

        progress.put(("error", error))


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("TXT → XLSX TURBO")
        self.root.geometry("650x330")
        self.root.resizable(False, False)

        self.path = tk.StringVar()
        self.status = tk.StringVar(
            value="Seleziona un file TXT."
        )

        self.events = queue.Queue()

        frame = ttk.Frame(root, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Convertitore TXT → Excel",
            font=("Segoe UI", 17, "bold")
        ).pack(pady=(0, 15))

        ttk.Entry(
            frame,
            textvariable=self.path,
            width=75
        ).pack(pady=5)

        ttk.Button(
            frame,
            text="Seleziona TXT",
            command=self.select_file
        ).pack(pady=7)

        self.start_button = ttk.Button(
            frame,
            text="CONVERTI IN XLSX",
            command=self.start
        )
        self.start_button.pack(pady=10)

        self.bar = ttk.Progressbar(
            frame,
            mode="indeterminate",
            length=550
        )
        self.bar.pack(pady=10)

        ttk.Label(
            frame,
            textvariable=self.status,
            wraplength=590
        ).pack(pady=10)

        self.root.after(150, self.check_events)

    def select_file(self):
        selected = filedialog.askopenfilename(
            title="Seleziona TXT",
            filetypes=[
                ("File TXT", "*.txt"),
                ("Tutti i file", "*.*")
            ]
        )

        if selected:
            self.path.set(selected)

    def start(self):
        source = self.path.get().strip()

        if not os.path.isfile(source):
            messagebox.showerror(
                "Errore",
                "Seleziona un file valido."
            )
            return

        self.start_button.config(state="disabled")
        self.bar.start(12)
        self.status.set("Conversione in corso...")

        threading.Thread(
            target=convert_txt,
            args=(source, self.events),
            daemon=True
        ).start()

    def check_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]

                if kind == "progress":
                    _, rows, speed, sheets = event
                    self.status.set(
                        f"Righe: {rows:,} | "
                        f"Velocità: {speed:,.0f} righe/s | "
                        f"Fogli: {sheets}"
                    )

                elif kind == "status":
                    self.status.set(event[1])

                elif kind == "done":
                    _, output, rows, seconds = event

                    self.bar.stop()
                    self.start_button.config(state="normal")

                    self.status.set(
                        f"Completato: {rows:,} righe "
                        f"in {seconds:.1f} secondi."
                    )

                    messagebox.showinfo(
                        "Conversione completata",
                        f"Righe: {rows:,}\n"
                        f"Tempo: {seconds:.1f} secondi\n\n"
                        f"File:\n{output}"
                    )

                elif kind == "error":
                    self.bar.stop()
                    self.start_button.config(state="normal")
                    self.status.set("Errore di conversione.")

                    log_path = Path(
                        self.path.get()
                    ).with_name("errore_conversione.log")

                    log_path.write_text(
                        event[1],
                        encoding="utf-8"
                    )

                    messagebox.showerror(
                        "Errore",
                        "Conversione interrotta.\n\n"
                        f"Dettagli salvati in:\n{log_path}"
                    )

        except queue.Empty:
            pass

        self.root.after(150, self.check_events)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
