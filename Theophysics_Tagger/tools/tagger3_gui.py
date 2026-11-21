#!/usr/bin/env python3
"""Theophysics Convergence Tagger v3 - desktop window.

Run tab:    pick folders, tick options, Scan / Watch / Catalog. Output streams live.
Browse tab: every tagged document in the database - filter by text, tag or category,
            double-click to open the file, right-click to open its folder.
Tags tab:   how many documents each tag landed on; double-click a tag to browse it.

The window only launches tagger3.py; all work happens there, so the CLI and the window
always behave the same.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from collections import Counter
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
TAGGER = TOOLS / "tagger3.py"
SETTINGS = ROOT / "tagger3_gui.json"
NO_WINDOW = 0x08000000 if os.name == "nt" else 0

OPTIONS = [
    ("semantic", "Meaning layer (needs Ollama running)", "--semantic", False),
    ("catalog", "Catalog every file + find duplicates", "--catalog", True),
    ("sidecars", "Write .fmeta sidecar beside each document", "--write-sidecars", False),
    ("markers", "Write .folder.fmeta into folders", "--write-folder-markers", False),
    ("paragraphs", "Export paragraph-level hits", "--export-paragraphs", False),
    ("copy", "COPY files into 03_TAGGED by primary tag", "--copy-by-primary-tag", False),
    ("frontmatter", "WRITE auto_tags into .md frontmatter (edits files)", "--write-frontmatter", False),
]


def load_settings() -> dict:
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except Exception:
        return {}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Theophysics Convergence Tagger v3")
        self.geometry("1100x720")
        self.minsize(820, 520)
        self.proc: subprocess.Popen | None = None
        self.q: queue.Queue = queue.Queue()
        self.results: dict = {}
        st = load_settings()

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.nb = nb
        run, browse, tagsf = ttk.Frame(nb, padding=8), ttk.Frame(nb, padding=8), ttk.Frame(nb, padding=8)
        nb.add(run, text="  Run  ")
        nb.add(browse, text="  Browse  ")
        nb.add(tagsf, text="  Tags  ")

        # ---------------------------------------------------------------- run tab
        left = ttk.Frame(run)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="Sources", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.src = tk.Listbox(left, width=52, height=9, selectmode="extended")
        self.src.pack(fill="x", pady=(2, 4))
        for s in st.get("sources", []):
            self.src.insert("end", s)
        row = ttk.Frame(left)
        row.pack(fill="x")
        ttk.Button(row, text="Add folder", command=self.add_folder).pack(side="left")
        ttk.Button(row, text="Add file", command=self.add_file).pack(side="left", padx=4)
        ttk.Button(row, text="Remove", command=lambda: [self.src.delete(i) for i in reversed(self.src.curselection())]
                   ).pack(side="left")

        ttk.Label(left, text="Options", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(12, 0))
        self.opt = {}
        for key, label, _, default in OPTIONS:
            v = tk.BooleanVar(value=st.get("options", {}).get(key, default))
            self.opt[key] = v
            ttk.Checkbutton(left, text=label, variable=v).pack(anchor="w")

        ttk.Label(left, text="Actions", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(12, 0))
        acts = ttk.Frame(left)
        acts.pack(fill="x")
        self.scan_btn = ttk.Button(acts, text="Scan", command=lambda: self.launch("scan"))
        self.scan_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=2)
        self.watch_btn = ttk.Button(acts, text="Watch", command=self.toggle_watch)
        self.watch_btn.grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        ttk.Button(acts, text="Catalog only", command=lambda: self.launch("catalog")).grid(row=0, column=2, sticky="ew", pady=2)
        ttk.Button(acts, text="Gold template", command=lambda: self.launch("gold-template")).grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=2)
        ttk.Button(acts, text="Eval", command=lambda: self.launch("eval")).grid(row=1, column=1, sticky="ew", padx=4, pady=2)
        ttk.Button(acts, text="Tune", command=lambda: self.launch("tune")).grid(row=1, column=2, sticky="ew", pady=2)
        ttk.Button(acts, text="Stop", command=self.stop).grid(row=2, column=0, sticky="ew", padx=(0, 4), pady=2)
        ttk.Button(acts, text="Open results folder", command=lambda: os.startfile(ROOT / "02_INDEX")
                   ).grid(row=2, column=1, columnspan=2, sticky="ew", pady=2)
        for c in range(3):
            acts.columnconfigure(c, weight=1)
        self.status = ttk.Label(left, text="Ready.", foreground="#555", wraplength=380)
        self.status.pack(anchor="w", pady=(12, 0))

        logf = ttk.Frame(run)
        logf.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.log = tk.Text(logf, wrap="word", font=("Consolas", 9), state="disabled")
        sb = ttk.Scrollbar(logf, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True)

        # ------------------------------------------------------------- browse tab
        bar = ttk.Frame(browse)
        bar.pack(fill="x")
        ttk.Label(bar, text="Filter").pack(side="left")
        self.filter = tk.StringVar()
        e = ttk.Entry(bar, textvariable=self.filter, width=40)
        e.pack(side="left", padx=4)
        e.bind("<KeyRelease>", lambda _e: self.fill_browse())
        ttk.Label(bar, text="Category").pack(side="left", padx=(12, 0))
        self.cat = tk.StringVar(value="(all)")
        self.cat_box = ttk.Combobox(bar, textvariable=self.cat, width=34, state="readonly")
        self.cat_box.pack(side="left", padx=4)
        self.cat_box.bind("<<ComboboxSelected>>", lambda _e: self.fill_browse())
        ttk.Button(bar, text="Refresh from database", command=self.refresh).pack(side="right")
        self.count = ttk.Label(bar, text="")
        self.count.pack(side="right", padx=8)

        cols = ("name", "primary", "category", "tags", "folder")
        self.tree = ttk.Treeview(browse, columns=cols, show="headings")
        for c, w in zip(cols, (300, 140, 170, 380, 260)):
            self.tree.heading(c, text=c.title(), command=lambda c=c: self.sort_by(c))
            self.tree.column(c, width=w, anchor="w")
        vs = ttk.Scrollbar(browse, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y", pady=(6, 0))
        self.tree.pack(fill="both", expand=True, pady=(6, 0))
        self.tree.bind("<Double-1>", lambda _e: self.open_selected(folder=False))
        self.tree.bind("<Button-3>", lambda _e: self.open_selected(folder=True))
        self.sort_col, self.sort_rev = "name", False

        # --------------------------------------------------------------- tags tab
        ttk.Label(tagsf, text="Documents per tag (double-click a tag to browse it)").pack(anchor="w")
        self.tag_tree = ttk.Treeview(tagsf, columns=("tag", "docs", "primary", "category"), show="headings")
        for c, w in (("tag", 260), ("docs", 80), ("primary", 120), ("category", 300)):
            self.tag_tree.heading(c, text={"primary": "As primary"}.get(c, c.title()))
            self.tag_tree.column(c, width=w, anchor="w")
        ts = ttk.Scrollbar(tagsf, command=self.tag_tree.yview)
        self.tag_tree.configure(yscrollcommand=ts.set)
        ts.pack(side="right", fill="y")
        self.tag_tree.pack(fill="both", expand=True)
        self.tag_tree.bind("<Double-1>", self.browse_tag)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self.pump)
        self.after(300, self.refresh)

    # ------------------------------------------------------------------ run helpers
    def add_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.src.insert("end", str(Path(d)))

    def add_file(self):
        for f in filedialog.askopenfilenames(filetypes=[("Documents", "*.md *.txt *.pdf *.docx *.html *.htm"),
                                                        ("All", "*.*")]):
            self.src.insert("end", str(Path(f)))

    def save(self):
        data = {"sources": list(self.src.get(0, "end")), "options": {k: v.get() for k, v in self.opt.items()}}
        try:
            SETTINGS.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def write(self, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def launch(self, cmd: str):
        if self.proc and self.proc.poll() is None:
            messagebox.showinfo("Busy", "Something is already running. Press Stop first.")
            return
        sources = list(self.src.get(0, "end"))
        argv = [sys.executable, "-u", str(TAGGER), cmd]
        if cmd in ("scan", "watch", "catalog"):
            if not sources:
                messagebox.showwarning("No sources", "Add a folder or file first.")
                return
            for s in sources:
                argv += ["--source", s]
        if self.opt["semantic"].get():
            argv.append("--semantic")
        if cmd in ("scan", "watch"):
            if self.opt["frontmatter"].get() and not messagebox.askyesno(
                    "Edit your files?", "'Write auto_tags into frontmatter' changes your .md files. Continue?"):
                return
            argv += [flag for key, _, flag, _ in OPTIONS if key != "semantic" and self.opt[key].get()]
        self.save()
        self.write(f"\n$ tagger3 {' '.join(argv[3:])}\n")
        self.status.configure(text=f"Running {cmd} ...")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        self.proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                     encoding="utf-8", errors="replace", cwd=str(TOOLS), env=env,
                                     creationflags=NO_WINDOW)
        self.running_cmd = cmd
        threading.Thread(target=self.reader, args=(self.proc,), daemon=True).start()

    def reader(self, proc):
        for line in proc.stdout:
            self.q.put(line)
        proc.wait()
        self.q.put(("__done__", proc.returncode))

    def pump(self):
        try:
            while True:
                item = self.q.get_nowait()
                if isinstance(item, tuple):
                    code = item[1]
                    self.status.configure(text="Done." if code == 0 else f"Stopped (exit {code}).")
                    self.watch_btn.configure(text="Watch")
                    if code == 0 and getattr(self, "running_cmd", "") in ("scan", "catalog"):
                        self.refresh()
                else:
                    self.write(item)
        except queue.Empty:
            pass
        self.after(100, self.pump)

    def toggle_watch(self):
        if self.proc and self.proc.poll() is None and getattr(self, "running_cmd", "") == "watch":
            self.stop()
            return
        self.launch("watch")
        if self.proc and self.proc.poll() is None:
            self.watch_btn.configure(text="Stop watching")
            self.status.configure(text="Watching for changes - results go to 02_INDEX/latest_*.csv")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

    def on_close(self):
        self.save()
        self.stop()
        self.destroy()

    # --------------------------------------------------------------- browse helpers
    def refresh(self):
        self.count.configure(text="loading ...")

        def work():
            try:
                sys.path.insert(0, str(TOOLS))
                import tagger3 as T3
                args = T3.build_parser().parse_args(["eval"] + (["--semantic"] if self.opt["semantic"].get() else []))
                if args.exclusions and not Path(args.exclusions).exists():
                    args.exclusions = None
                res = T3.all_results(Path(args.db), args)
                res = {p: r for p, r in res.items() if Path(p).exists()}
                self.after(0, lambda: self.set_results(res))
            except Exception as exc:
                self.after(0, lambda: self.count.configure(text=f"could not load: {exc}"))

        threading.Thread(target=work, daemon=True).start()

    def set_results(self, res: dict):
        self.results = res
        cats = sorted({r["primary_category"] for r in res.values() if r["primary_category"]})
        self.cat_box["values"] = ["(all)", *cats]
        self.fill_browse()
        tag_docs, tag_primary, tag_cat = Counter(), Counter(), {}
        for r in res.values():
            for a in r["accepted"]:
                tag_docs[a["tag"]] += 1
            if r["primary_tag"]:
                tag_primary[r["primary_tag"]] += 1
        sys.path.insert(0, str(TOOLS))
        self.tag_tree.delete(*self.tag_tree.get_children())
        try:
            import tagger3 as T3
            args = T3.build_parser().parse_args(["eval"])
            tag_cat = {t.tag: t.category for t in T3.T2.load_registry(Path(args.registry), None)}
        except Exception:
            pass
        for tag, n in tag_docs.most_common():
            self.tag_tree.insert("", "end", values=(tag, n, tag_primary.get(tag, 0), tag_cat.get(tag, "")))

    def fill_browse(self):
        f = self.filter.get().strip().lower()
        cat = self.cat.get()
        rows = []
        for p, r in self.results.items():
            tags = "; ".join(a["tag"] for a in r["accepted"])
            if cat not in ("", "(all)") and r["primary_category"] != cat:
                continue
            if f and f not in p.lower() and f not in tags.lower() and f not in r["primary_category"].lower():
                continue
            pp = Path(p)
            rows.append((pp.name, r["primary_tag"], r["primary_category"], tags, str(pp.parent), p))
        idx = {"name": 0, "primary": 1, "category": 2, "tags": 3, "folder": 4}[self.sort_col]
        rows.sort(key=lambda x: x[idx].lower(), reverse=self.sort_rev)
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            self.tree.insert("", "end", iid=row[5], values=row[:5])
        self.count.configure(text=f"{len(rows)} of {len(self.results)} documents")

    def sort_by(self, col: str):
        self.sort_rev = not self.sort_rev if self.sort_col == col else False
        self.sort_col = col
        self.fill_browse()

    def open_selected(self, folder: bool):
        sel = self.tree.focus() or (self.tree.selection() or [None])[0]
        if not sel:
            return
        try:
            if folder:
                subprocess.Popen(["explorer", "/select,", sel])
            else:
                os.startfile(sel)
        except Exception as exc:
            messagebox.showerror("Could not open", str(exc))

    def browse_tag(self, _e):
        sel = self.tag_tree.focus()
        if sel:
            self.filter.set(self.tag_tree.item(sel, "values")[0])
            self.cat.set("(all)")
            self.fill_browse()
            self.nb.select(1)


if __name__ == "__main__":
    App().mainloop()
