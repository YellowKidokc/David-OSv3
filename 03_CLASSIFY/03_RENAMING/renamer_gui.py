"""Renamer review window — A ✓ · B original · C proposed · D engine · E why · F your override.

Click the ✓ column (or press Space) to check/uncheck. Double-click a row to type your own name.
Nothing renames until "Apply checked", which previews first, logs every row to the ledger and
can be undone run-by-run. Rules: rename_rules.yaml (clue words), edited by hand.

    python renamer_gui.py ["S:\\PROCESSED"]
"""
from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "00_SHARED"))
import rename_engine as eng   # noqa: E402
import notify                 # noqa: E402

COLS = ("check", "original", "proposed", "engine", "why", "override", "flag")
HEAD = {"check": "✓", "original": "B · Original name", "proposed": "C · Proposed name",
        "engine": "D · Engine", "why": "E · Why (clue words)", "override": "F · Your override", "flag": "Flag"}
WIDTH = {"check": 34, "original": 300, "proposed": 380, "engine": 70, "why": 420, "override": 220, "flag": 150}
FILTERS = ["All", "Checked", "Unchecked", "Flagged", "Low confidence (< 0.5)", "Has links"]


class Renamer(tk.Tk):
    def __init__(self, folder: str = r"S:\PROCESSED"):
        super().__init__()
        self.title("03 · Renamer")
        self.geometry("1500x820")
        self.props: dict[str, eng.Proposal] = {}
        self.checked: set[str] = set()
        self.rejected: set[str] = set()
        self.override: dict[str, str] = {}
        self._inbox: queue.Queue = queue.Queue()
        self.sort_col, self.sort_rev = "original", False

        top = ttk.Frame(self, padding=6); top.pack(fill="x")
        ttk.Label(top, text="Folder").pack(side="left")
        self.var_folder = tk.StringVar(value=folder)
        ttk.Entry(top, textvariable=self.var_folder, width=60).pack(side="left", padx=4)
        ttk.Button(top, text="…", width=3, command=self.pick).pack(side="left")
        self.var_rec = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="include subfolders", variable=self.var_rec).pack(side="left", padx=6)
        ttk.Button(top, text="Scan", command=self.scan).pack(side="left")
        self.lbl_score = ttk.Label(top, text=""); self.lbl_score.pack(side="right")

        bar = ttk.Frame(self, padding=(6, 0)); bar.pack(fill="x")
        ttk.Label(bar, text="Show").pack(side="left")
        self.var_filter = tk.StringVar(value=FILTERS[0])
        cb = ttk.Combobox(bar, textvariable=self.var_filter, values=FILTERS, state="readonly", width=22)
        cb.pack(side="left", padx=4); cb.bind("<<ComboboxSelected>>", lambda e: self.render())
        ttk.Label(bar, text="Search").pack(side="left", padx=(10, 0))
        self.var_q = tk.StringVar(); self.var_q.trace_add("write", lambda *a: self.render())
        ttk.Entry(bar, textvariable=self.var_q, width=24).pack(side="left", padx=4)
        for text, cmd in (("Check all shown", lambda: self.set_checked(True)),
                          ("Uncheck all shown", lambda: self.set_checked(False)),
                          ("Check ≥ auto", self.check_auto),
                          ("Reject selected", self.reject)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        ttk.Button(bar, text="Apply checked…", command=self.apply).pack(side="right", padx=2)
        ttk.Button(bar, text="Undo a run…", command=self.undo).pack(side="right", padx=2)
        ttk.Button(bar, text="Export to Excel", command=self.export).pack(side="right", padx=2)

        body = ttk.Frame(self, padding=6); body.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(body, columns=COLS, show="headings", selectmode="extended")
        for c in COLS:
            self.tree.heading(c, text=HEAD[c], command=lambda c=c: self.sort(c))
            self.tree.column(c, width=WIDTH[c], stretch=c in ("proposed", "why"), anchor="center" if c in ("check", "engine") else "w")
        ys = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(body, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0, column=0, sticky="nsew"); ys.grid(row=0, column=1, sticky="ns"); xs.grid(row=1, column=0, sticky="ew")
        body.rowconfigure(0, weight=1); body.columnconfigure(0, weight=1)
        self.tree.tag_configure("flag", foreground="#a15c00")
        self.tree.tag_configure("low", foreground="#b00020")
        self.tree.tag_configure("rejected", foreground="#888888")
        self.tree.bind("<Button-1>", self.on_click)
        self.tree.bind("<Double-1>", self.edit)
        self.tree.bind("<space>", lambda e: self.toggle(self.tree.selection()))

        self.status = ttk.Label(self, padding=6, text="Pick a folder and press Scan. Nothing is renamed until Apply.")
        self.status.pack(fill="x")
        self.update_score()
        self.after(100, self._poll)

    # ---- data ---------------------------------------------------------
    def pick(self):
        d = filedialog.askdirectory(initialdir=self.var_folder.get())
        if d:
            self.var_folder.set(d)

    def scan(self):
        root = Path(self.var_folder.get().strip())
        if not root.is_dir():
            messagebox.showerror("Scan", f"Not a folder: {root}"); return
        self.status.config(text=f"Scanning {root} … (reading every file, checking duplicates and links)")
        threading.Thread(target=lambda: self._inbox.put((self._scanned, (root, eng.propose(root, self.var_rec.get())))),
                         daemon=True).start()

    def _poll(self):
        try:
            while True:
                fn, args = self._inbox.get_nowait()
                fn(*args)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _scanned(self, root: Path, props: list[eng.Proposal]):
        self.root_folder = root
        auto = eng.load_rules()["auto_check"]
        self.props = {str(p.path): p for p in props}
        self.checked = {k for k, p in self.props.items() if not p.flag and p.confidence >= auto}
        self.rejected, self.override = set(), {}
        self.render()
        flagged = sum(1 for p in props if p.flag)
        self.status.config(text=f"{len(props)} files · {len(self.checked)} pre-checked (confidence ≥ {auto}) · "
                                f"{flagged} flagged (duplicates/collisions are never pre-checked)")

    def final(self, key: str) -> str:
        return self.override.get(key) or self.props[key].proposed

    # ---- view ---------------------------------------------------------
    def visible(self) -> list[str]:
        f, q = self.var_filter.get(), self.var_q.get().lower().strip()
        out = []
        for k, p in self.props.items():
            if f == "Checked" and k not in self.checked: continue
            if f == "Unchecked" and k in self.checked: continue
            if f == "Flagged" and not p.flag: continue
            if f.startswith("Low") and p.confidence >= 0.5: continue
            if f == "Has links" and not p.links_in: continue
            if q and q not in (p.path.name + " " + self.final(k) + " " + " ".join(p.why)).lower(): continue
            out.append(k)
        key = {"original": lambda k: self.props[k].path.name.lower(), "proposed": lambda k: self.final(k).lower(),
               "engine": lambda k: self.props[k].confidence, "flag": lambda k: self.props[k].flag,
               "check": lambda k: k in self.checked, "why": lambda k: " ".join(self.props[k].why),
               "override": lambda k: self.override.get(k, "")}[self.sort_col]
        return sorted(out, key=key, reverse=self.sort_rev)

    def render(self):
        self.tree.delete(*self.tree.get_children())
        for k in self.visible():
            self.tree.insert("", "end", iid=k, values=self.values(k), tags=self.tags(k))
        self.status.config(text=f"showing {len(self.tree.get_children())} of {len(self.props)} · "
                                f"{len(self.checked)} checked · {len(self.rejected)} rejected")

    def values(self, k):
        p = self.props[k]
        return ("✔" if k in self.checked else ("✗" if k in self.rejected else ""), p.path.name, self.final(k),
                f"{p.confidence:.0%}", "; ".join(p.why), self.override.get(k, ""), p.flag)

    def tags(self, k):
        p = self.props[k]
        return ("rejected",) if k in self.rejected else ("flag",) if p.flag else ("low",) if p.confidence < 0.5 else ()

    def refresh(self, keys):
        for k in keys:
            if self.tree.exists(k):
                self.tree.item(k, values=self.values(k), tags=self.tags(k))
        self.status.config(text=f"{len(self.checked)} checked · {len(self.rejected)} rejected · {len(self.props)} files")

    def sort(self, col):
        self.sort_rev = not self.sort_rev if self.sort_col == col else False
        self.sort_col = col
        self.render()

    # ---- actions ------------------------------------------------------
    def on_click(self, e):
        if self.tree.identify("region", e.x, e.y) == "cell" and self.tree.identify_column(e.x) == "#1":
            row = self.tree.identify_row(e.y)
            if row:
                self.toggle((row,))
                return "break"

    def toggle(self, keys):
        for k in keys:
            if k in self.checked:
                self.checked.discard(k)
            else:
                self.checked.add(k); self.rejected.discard(k)
        self.refresh(keys)

    def set_checked(self, on: bool):
        keys = list(self.tree.get_children())
        for k in keys:
            if on and not self.props[k].flag.startswith(("duplicate", "already")):
                self.checked.add(k); self.rejected.discard(k)
            elif not on:
                self.checked.discard(k)
        self.refresh(keys)

    def check_auto(self):
        auto = eng.load_rules()["auto_check"]
        keys = list(self.tree.get_children())
        for k in keys:
            if not self.props[k].flag and self.props[k].confidence >= auto:
                self.checked.add(k)
        self.refresh(keys)

    def reject(self):
        keys = self.tree.selection()
        for k in keys:
            self.rejected.add(k); self.checked.discard(k)
        self.refresh(keys)

    def edit(self, e):
        k = self.tree.identify_row(e.y)
        if not k or self.tree.identify_column(e.x) == "#1":
            return
        p = self.props[k]
        new = simpledialog.askstring("Your name", f"{p.path.name}\n\nEngine proposed:\n{p.proposed}\n\nYour name (blank = use the engine's):",
                                     initialvalue=self.final(k), parent=self)
        if new is None:
            return
        new = new.strip()
        if new and Path(new).suffix.lower() != p.path.suffix.lower():
            new += p.path.suffix.lower()
        if new and new != p.proposed:
            self.override[k] = new
        else:
            self.override.pop(k, None)
        self.checked.add(k); self.rejected.discard(k)
        self.refresh((k,))

    def apply(self):
        todo = [k for k in self.checked if self.final(k) != self.props[k].path.name]
        if not todo and not self.rejected:
            messagebox.showinfo("Apply", "Nothing checked to rename."); return
        finals = [self.final(k) for k in todo]
        dupes = {n for n in finals if finals.count(n) > 1}
        if dupes:
            messagebox.showerror("Apply", "Two checked rows would get the same name:\n" + "\n".join(sorted(dupes)[:10])); return
        gdec = eng._gate_decision("rename", [self.props[k].path for k in todo], Path(self.root_folder)) if todo else None
        if gdec and gdec.verdict == "block":
            messagebox.showerror("Blocked by rules",
                                 "This batch breaks hard rules and cannot run:\n\n"
                                 + "\n".join(f"{r['rule_id']}: {r['reason']}" for r in gdec.fired_rules))
            return
        warning = ""
        if gdec and gdec.verdict == "ask":
            warning = ("These rules fired:\n"
                       + "\n".join(f"• {r['rule_id']}: {r['reason']}" for r in gdec.fired_rules)
                       + "\n\nYes = approve this once · No = cancel\n\n")
        preview = "\n".join(f"{self.props[k].path.name}\n   → {self.final(k)}" for k in todo[:12])
        links = sum(self.props[k].links_in for k in todo)
        if not messagebox.askyesno("Apply — preview",
                                   warning +
                                   f"Rename {len(todo)} file(s)?  ({len(self.rejected)} rejection(s) will be logged)\n"
                                   f"{links} [[link]](s) inside the folder will be updated to match.\n\n{preview}"
                                   + ("\n…" if len(todo) > 12 else "") + "\n\nEvery rename is logged and can be undone."):
            return
        if gdec and gdec.verdict == "ask":
            eng._ledger.log_event("gate_override", path=str(self.root_folder),
                                  folder=str(self.root_folder), action_id="rename",
                                  verdict="ask", choice="approve_once")
        rows = [(self.props[k], self.final(k), "rename") for k in todo]
        rows += [(self.props[k], "", "reject") for k in self.rejected]
        run, done, errors = eng.apply(self.root_folder, rows, override=True)
        msg = f"Renamed {done} file(s). Run id: {run}"
        if errors:
            msg += "\n\nErrors:\n" + "\n".join(errors[:15])
        self.update_score()
        notify.toast("Renamer finished", f"Renamed {done} file(s)" + (f", {len(errors)} error(s)" if errors else "")
                     + ". Click to open the folder.", self.root_folder)
        messagebox.showinfo("Apply", msg + "\n\nRescanning…")
        self.scan()

    def undo(self):
        runs = eng.runs()
        if not runs:
            messagebox.showinfo("Undo", "No runs in the ledger yet."); return
        run = simpledialog.askstring("Undo a run", "Run ids, newest first:\n" + "\n".join(runs[:15]) + "\n\nUndo which run?",
                                     initialvalue=runs[0], parent=self)
        if not run or run not in runs:
            return
        if not messagebox.askyesno("Undo", f"Rename every file from run {run} back, and restore the notes whose links changed?"):
            return
        n, errors = eng.undo_run(run)
        messagebox.showinfo("Undo", f"Undid {n} rename(s)." + ("\n\nErrors:\n" + "\n".join(errors[:15]) if errors else ""))
        if self.props:
            self.scan()

    def export(self):
        if not self.props:
            messagebox.showinfo("Export", "Scan a folder first."); return
        dst = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile="rename_review.xlsx",
                                           initialdir=str(HERE / "data"), filetypes=[("Excel", "*.xlsx")])
        if dst:
            eng.export_xlsx(list(self.props.values()), {k: self.final(k) for k in self.props}, self.checked, Path(dst))
            self.status.config(text=f"Exported to {dst}")

    def update_score(self):
        right, total = eng.scoreboard()
        self.lbl_score.config(text=f"Engine right {right}/{total} ({right / total:.0%})" if total
                              else "Engine score: no decisions yet")


if __name__ == "__main__":
    Renamer(sys.argv[1] if len(sys.argv) > 1 else r"S:\PROCESSED").mainloop()
