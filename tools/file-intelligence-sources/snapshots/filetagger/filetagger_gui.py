#!/usr/bin/env python3
"""Small popup GUI for filetagger.py.

This intentionally stays lightweight: Tkinter + subprocess only.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


APP_DIR = Path(__file__).resolve().parent
TAGGER = APP_DIR / "filetagger.py"
DEFAULT_DB = APP_DIR / "catalog.db"


class FileTaggerPopup(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("FileTagger")
        self.geometry("760x520")
        self.minsize(660, 430)

        self.process: subprocess.Popen[str] | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()

        self.folder_var = tk.StringVar(value="")
        self.db_var = tk.StringVar(value=str(DEFAULT_DB))
        self.quickhash_var = tk.BooleanVar(value=True)
        self.sidecar_var = tk.BooleanVar(value=False)
        self.force_var = tk.BooleanVar(value=False)
        self.workers_var = tk.IntVar(value=max(1, min(4, (os.cpu_count() or 2) // 2)))
        self.status_var = tk.StringVar(value="Idle")

        self._build()
        self.after(100, self._drain_log)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        path_box = ttk.LabelFrame(outer, text="Scan")
        path_box.pack(fill="x")

        ttk.Label(path_box, text="Folder").grid(row=0, column=0, sticky="w", padx=8, pady=(10, 6))
        folder_entry = ttk.Entry(path_box, textvariable=self.folder_var)
        folder_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=(10, 6))
        ttk.Button(path_box, text="Browse", command=self._choose_folder).grid(row=0, column=2, padx=8, pady=(10, 6))

        ttk.Label(path_box, text="Database").grid(row=1, column=0, sticky="w", padx=8, pady=(0, 10))
        db_entry = ttk.Entry(path_box, textvariable=self.db_var)
        db_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=(0, 10))
        ttk.Button(path_box, text="Save As", command=self._choose_db).grid(row=1, column=2, padx=8, pady=(0, 10))
        path_box.columnconfigure(1, weight=1)

        opts = ttk.Frame(outer)
        opts.pack(fill="x", pady=10)

        ttk.Checkbutton(opts, text="Quick hash", variable=self.quickhash_var).pack(side="left", padx=(0, 14))
        ttk.Checkbutton(opts, text=".fmeta sidecars", variable=self.sidecar_var).pack(side="left", padx=(0, 14))
        ttk.Checkbutton(opts, text="Force rescan", variable=self.force_var).pack(side="left", padx=(0, 14))
        ttk.Label(opts, text="Workers").pack(side="left", padx=(4, 6))
        ttk.Spinbox(opts, from_=1, to=max(1, os.cpu_count() or 4), width=5, textvariable=self.workers_var).pack(side="left")

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(0, 10))
        self.start_btn = ttk.Button(actions, text="Start Scan", command=self._start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(actions, text="Stop", command=self._stop, state="disabled")
        self.stop_btn.pack(side="left", padx=8)
        ttk.Button(actions, text="Open DB Folder", command=self._open_db_folder).pack(side="left", padx=8)
        ttk.Label(actions, textvariable=self.status_var).pack(side="right")

        log_box = ttk.LabelFrame(outer, text="Readout")
        log_box.pack(fill="both", expand=True)

        self.log = tk.Text(log_box, wrap="word", height=14, state="disabled")
        self.log.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        scroll = ttk.Scrollbar(log_box, orient="vertical", command=self.log.yview)
        scroll.pack(side="right", fill="y", padx=(0, 8), pady=8)
        self.log.configure(yscrollcommand=scroll.set)

    def _choose_folder(self) -> None:
        folder = filedialog.askdirectory(title="Folder to scan")
        if folder:
            self.folder_var.set(folder)

    def _choose_db(self) -> None:
        db = filedialog.asksaveasfilename(
            title="Catalog database",
            defaultextension=".db",
            filetypes=[("SQLite database", "*.db"), ("All files", "*.*")],
            initialdir=str(APP_DIR),
            initialfile="catalog.db",
        )
        if db:
            self.db_var.set(db)

    def _command(self) -> list[str]:
        py = sys.executable or "python"
        cmd = [
            py,
            str(TAGGER),
            self.folder_var.get(),
            "--db",
            self.db_var.get(),
            "--workers",
            str(max(1, int(self.workers_var.get()))),
        ]
        if self.quickhash_var.get():
            cmd.append("--quickhash")
        if self.sidecar_var.get():
            cmd.append("--sidecar")
        if self.force_var.get():
            cmd.append("--force")
        return cmd

    def _start(self) -> None:
        folder = self.folder_var.get().strip()
        db = self.db_var.get().strip()
        if not folder or not Path(folder).is_dir():
            messagebox.showerror("FileTagger", "Choose a real folder first.")
            return
        if not db:
            messagebox.showerror("FileTagger", "Choose a database path.")
            return
        if not TAGGER.exists():
            messagebox.showerror("FileTagger", f"Missing {TAGGER}")
            return

        self._clear_log()
        self._append_log("Running:\n" + " ".join(f'"{x}"' if " " in x else x for x in self._command()) + "\n\n")
        self.status_var.set("Running")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        threading.Thread(target=self._run_process, daemon=True).start()

    def _run_process(self) -> None:
        try:
            self.process = subprocess.Popen(
                self._command(),
                cwd=str(APP_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert self.process.stdout is not None
            for line in self.process.stdout:
                self.log_queue.put(line)
            code = self.process.wait()
            self.log_queue.put(f"\nExited with code {code}\n")
            self.log_queue.put("__DONE__")
        except Exception as exc:
            self.log_queue.put(f"\nERROR: {exc}\n")
            self.log_queue.put("__DONE__")

    def _stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.status_var.set("Stopping")

    def _open_db_folder(self) -> None:
        db = Path(self.db_var.get() or DEFAULT_DB)
        folder = db.parent if db.parent.exists() else APP_DIR
        os.startfile(str(folder))

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _drain_log(self) -> None:
        try:
            while True:
                item = self.log_queue.get_nowait()
                if item == "__DONE__":
                    self.process = None
                    self.start_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                    self.status_var.set("Done")
                else:
                    self._append_log(item)
        except queue.Empty:
            pass
        self.after(100, self._drain_log)

    def _close(self) -> None:
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("FileTagger", "A scan is running. Stop it and close?"):
                return
            self._stop()
        self.destroy()


def main() -> None:
    FileTaggerPopup().mainloop()


if __name__ == "__main__":
    main()

