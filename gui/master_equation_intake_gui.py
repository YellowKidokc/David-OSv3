#!/usr/bin/env python3
"""Independent GUI for observe-only Master Equation intake analysis."""
from __future__ import annotations

import csv
import json
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from engine.master_equation_intake import analyze  # noqa: E402


DEFAULT_SOURCE = Path(r"C:\theophysics\OPUS\Master Equation")
DEFAULT_OUTPUT = REPO / "runs" / "master_equation_gui"


class MasterEquationIntakeGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Master Equation Intake Workbench — Observe Only")
        self.geometry("1120x760")
        self.minsize(900, 620)
        self._events: queue.Queue = queue.Queue()
        self._build()
        self.after(150, self._poll)

    def _build(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        self.source = tk.StringVar(value=str(DEFAULT_SOURCE))
        self.output = tk.StringVar(value=str(DEFAULT_OUTPUT))
        ttk.Label(top, text="Source corpus").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.source).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(top, text="Browse", command=self._browse_source).grid(row=0, column=2)
        ttk.Label(top, text="Output receipts").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(top, textvariable=self.output).grid(row=1, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Button(top, text="Browse", command=self._browse_output).grid(row=1, column=2, pady=(8, 0))
        top.columnconfigure(1, weight=1)

        controls = ttk.Frame(self, padding=(10, 0, 10, 8))
        controls.pack(fill="x")
        self.run_button = ttk.Button(controls, text="ANALYZE — NO SOURCE CHANGES", command=self._start)
        self.run_button.pack(side="left")
        ttk.Button(controls, text="Load Existing Results", command=self._load_existing).pack(side="left", padx=8)
        ttk.Button(controls, text="Open Output Folder", command=self._open_output).pack(side="left")
        self.progress = ttk.Progressbar(controls, mode="indeterminate", length=260)
        self.progress.pack(side="right")

        self.status = tk.StringVar(value="Ready. This workbench never edits the source corpus.")
        ttk.Label(self, textvariable=self.status, padding=(10, 0, 10, 8)).pack(fill="x")

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.summary_text = self._text_tab("Summary")
        self.variable_tree = self._tree_tab("Ten Variables", ("Variable", "Files"))
        self.lane_tree = self._tree_tab("Source Lanes", ("Lane", "Files"))
        self.role_tree = self._tree_tab("Roles", ("Role", "Files"))
        self.duplicate_tree = self._tree_tab(
            "Exact Duplicates", ("Content ID", "Instances", "Lane", "Relative Path"), widths=(170, 80, 110, 650)
        )
        self.error_tree = self._tree_tab("Scan Errors", ("Path", "Error"), widths=(520, 520))

    def _text_tab(self, title):
        frame = ttk.Frame(self.tabs)
        text = tk.Text(frame, wrap="word", font=("Consolas", 10))
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tabs.add(frame, text=title)
        return text

    def _tree_tab(self, title, columns, widths=None):
        frame = ttk.Frame(self.tabs)
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        widths = widths or tuple(220 for _ in columns)
        for col, width in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor="w")
        y = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        x = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.tabs.add(frame, text=title)
        return tree

    def _browse_source(self):
        value = filedialog.askdirectory(initialdir=self.source.get() or str(DEFAULT_SOURCE))
        if value:
            self.source.set(value)

    def _browse_output(self):
        value = filedialog.askdirectory(initialdir=self.output.get() or str(DEFAULT_OUTPUT))
        if value:
            self.output.set(value)

    def _start(self):
        source, output = Path(self.source.get()), Path(self.output.get())
        if not source.is_dir():
            messagebox.showerror("Invalid source", f"Folder does not exist:\n{source}")
            return
        self.run_button.configure(state="disabled")
        self.progress.start(10)
        self.status.set(f"Analyzing {source} — source remains untouched…")

        def work():
            try:
                summary = analyze(source, output)
                self._events.put(("complete", summary))
            except Exception as exc:
                self._events.put(("error", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, payload = self._events.get_nowait()
                self.progress.stop()
                self.run_button.configure(state="normal")
                if kind == "error":
                    self.status.set("Analysis failed; source was not changed.")
                    messagebox.showerror("Analysis failed", payload)
                else:
                    self.status.set(
                        f"Complete: {payload['file_instances']:,} instances; "
                        f"{payload['unique_content_objects']:,} unique objects; "
                        f"{payload['scan_errors']:,} read errors."
                    )
                    self._load_results(Path(payload["output_root"]))
        except queue.Empty:
            pass
        self.after(150, self._poll)

    def _load_existing(self):
        value = filedialog.askdirectory(initialdir=self.output.get() or str(DEFAULT_OUTPUT))
        if value:
            self.output.set(value)
            self._load_results(Path(value))

    def _load_results(self, output: Path):
        summary_path = output / "summary.json"
        if not summary_path.exists():
            messagebox.showerror("No results", f"summary.json not found in:\n{output}")
            return
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        start = output / "START_HERE_MASTER_EQUATION_INTAKE.md"
        self.summary_text.delete("1.0", "end")
        self.summary_text.insert("1.0", start.read_text(encoding="utf-8") if start.exists() else json.dumps(summary, indent=2))
        self._fill_pairs(self.variable_tree, summary.get("variable_coverage", {}))
        self._fill_pairs(self.lane_tree, summary.get("source_lanes", {}))
        self._fill_pairs(self.role_tree, summary.get("roles", {}))
        self._clear(self.duplicate_tree)
        dup = output / "exact_duplicate_groups.csv"
        if dup.exists():
            with dup.open(encoding="utf-8-sig") as handle:
                for row in csv.DictReader(handle):
                    self.duplicate_tree.insert("", "end", values=(
                        row["content_id"], row["instance_count"], row["source_lane"], row["relative_path"]))
        self._clear(self.error_tree)
        err = output / "scan_errors.csv"
        if err.exists():
            with err.open(encoding="utf-8-sig") as handle:
                for row in csv.DictReader(handle):
                    self.error_tree.insert("", "end", values=(row["path"], row["error"]))

    def _fill_pairs(self, tree, values):
        self._clear(tree)
        for key, value in values.items():
            tree.insert("", "end", values=(key, f"{value:,}"))

    @staticmethod
    def _clear(tree):
        tree.delete(*tree.get_children())

    def _open_output(self):
        output = Path(self.output.get())
        output.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(output)  # type: ignore[attr-defined]


def main():
    MasterEquationIntakeGUI().mainloop()


if __name__ == "__main__":
    main()

