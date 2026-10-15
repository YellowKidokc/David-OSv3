"""Sidecar Review — walk every mim.v1 card, see what's stuck, accept or fix the
engines' suggestions in bulk or one at a time (TAG_TAXONOMY_v0.4, Parts B + D).

  Top:     folder, facet (standing | domain | ct), driver engine, Load
  Filter:  view + search; "Select ALL n" selects every row that matches, not just
           what's on screen
  Table:   card · current · suggested · conf · problems · decision · final
  Bottom:  details for the clicked row — problems, every engine's answer, the card

Stuck rows (problems, no suggestion, low confidence, or a disagreement) can be
sent to DeepSeek; it explains where it stopped, proposes a value, and may ask
you a question you answer in the window. Its answers are suggestions only.

Nothing touches a card until you press "Write accepted to cards". Before writing,
every changed card is copied to sidecars/.review_backup/<timestamp>/.
Every decision (accept, reject, edit) resolves the ledger, so the scoreboard
learns which engine to trust. Ledger: data/classify_<facet>.db — kept apart
from the YouTube ledger so the two never train on each other.
The engines live in 02_CLASSIFICATION (harness/, engines/) — vendored from the
old Prediction_GUI repo (PREDICTION_GUI env var still overrides, default: local).
"""
from __future__ import annotations

import csv
import datetime as dt
import os
import queue
import re
import shutil
import sys
import threading
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
from typing import Any

ROOT = Path(__file__).resolve().parents[2]             # 03_CLASSIFY
SHARED = ROOT / "00_SHARED"                            # rulebook, validator, DeepSeek, data
# The prediction harness is vendored into 02_CLASSIFICATION; env var override kept for emergencies.
PGUI = Path(os.environ.get("PREDICTION_GUI", str(ROOT / "02_CLASSIFICATION")))
if not (PGUI / "harness").is_dir():
    raise SystemExit(f"Prediction harness not found at {PGUI} (expected 02_CLASSIFICATION\\harness)")
sys.path.insert(0, str(PGUI))
sys.path.insert(0, str(SHARED))

import deepseek_triage as ds                              # noqa: E402  (00_SHARED)
import notify                                             # noqa: E402  (00_SHARED)
import source_papers                                      # noqa: E402  (00_SHARED)
from harness.adapters import sidecars as sc_adapter      # noqa: E402
from harness.contract import Prediction, Candidate        # noqa: E402
from harness.registry import sync                        # noqa: E402
from harness.runner import Runner                        # noqa: E402

DEFAULT_FOLDER = "//192.168.2.50/h_hp/Desktop/Folders/AXIOM_CLASSIFICATION_CANON_2026-07-25 (1)/sidecars"

VALID = {
    "standing": ["declaration", "canon", "freeze-candidate", "proposed",
                 "draft", "reference", "superseded", "inert"],
    "domain": ["Theophysics", "Theology", "Philosophy", "Mathematics", "Physics",
               "Information Theory", "Cognitive Science", "Social Sciences",
               "Methodology", "Computer Science"],
    "ct": ["ct-argument", "ct-narrative", "ct-overview", "ct-equation", "ct-method",
           "ct-reference", "ct-implications", "ct-status", "ct-outline", "ct-source"],
}
REQUIRED = ("sidecar", "subject", "source", "source_file", "standing", "folder_class")
VIEWS = ("All", "Needs attention", "Stuck (send to DeepSeek)", "Disagrees with current",
         "Missing value", "DeepSeek answered", "DeepSeek has a question", "Undecided", "Decided")
STUCK_CONF = 0.6     # below this the driver engine is "unsure" and the row counts as stuck


@dataclass
class Row:
    path: Path
    subject: str
    fields: dict[str, str]
    tags: list[str]
    current: str = ""
    problems: list[str] = field(default_factory=list)
    suggested: str = ""
    conf: float | None = None
    why: str = ""
    predictions: list[Any] = field(default_factory=list)
    decision: str = ""          # "" | accept | reject | edit
    final: str = ""             # value that will be written
    written: bool = False
    ai: dict[str, Any] = field(default_factory=dict)     # last DeepSeek answer
    reply: str = ""                                       # your answer to its question

    @property
    def readable(self) -> bool:
        return bool(self.fields)

    @property
    def stuck(self) -> bool:
        conf = self.conf or 0
        return (bool(self.problems) or not self.suggested
                or (not self.current and conf < STUCK_CONF)                     # nothing to fall back on
                or (bool(self.current) and self.current != self.suggested
                    and conf >= STUCK_CONF))                                    # a confident disagreement

    @property
    def iid(self) -> str:
        return str(self.path)

    @property
    def attention(self) -> bool:
        return bool(self.problems) or not self.suggested


# ---- card reading / writing -------------------------------------------------

def current_value(facet: str, fields: dict[str, str], tags: list[str]) -> str:
    if facet in ("standing", "domain"):
        return fields.get(facet, "")
    return next((t for t in tags if t.startswith(f"{facet}-")), "")


def card_problems(path: Path, fields: dict[str, str], tags: list[str], facet: str) -> list[str]:
    if not fields:
        return [sc_adapter.card_diagnosis(path)]
    out = [f"missing field: {f}" for f in REQUIRED if not fields.get(f)]
    st = fields.get("standing", "")
    if st and st not in VALID["standing"]:
        out.append(f"standing '{st}' not in closed list"
                   + (" — that's a version number" if re.match(r"^v?\d", st) else ""))
    if fields.get("subject") and fields["subject"] != path.stem:
        out.append(f"subject '{fields['subject']}' ≠ filename '{path.stem}'")
    for t in ("sidecar", "subject"):
        if t not in tags:
            out.append(f"missing reserved tag: {t}")
    cur = current_value(facet, fields, tags)
    if cur and facet != "standing" and cur not in VALID[facet]:   # standing already checked above
        out.append(f"{facet} '{cur}' not in closed list")
    return out


def write_value(path: Path, facet: str, value: str) -> None:
    raw = path.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    fm = lines[1:end]
    if facet in ("standing", "domain"):
        idx = next((i for i, l in enumerate(fm) if l.startswith(f"{facet}:")), None)
        if idx is not None:
            fm[idx] = f"{facet}: {value}"
        else:
            at = next((i for i, l in enumerate(fm) if l.startswith("tags:")), len(fm))
            fm.insert(at, f"{facet}: {value}")
    else:
        tag_line = next((i for i, l in enumerate(fm) if l.startswith("tags:")), None)
        if tag_line is None:
            fm += ["tags:", f"  - {value}"]
        else:
            j = tag_line + 1
            replaced = False
            while j < len(fm) and fm[j].strip().startswith("- "):
                if fm[j].strip()[2:].strip().startswith(f"{facet}-"):
                    fm[j] = f"  - {value}"; replaced = True
                j += 1
            if not replaced:
                fm.insert(j, f"  - {value}")
    lines = [lines[0]] + fm + lines[end:]
    path.write_bytes(nl.join(lines).encode("utf-8"))


# ---- the window -------------------------------------------------------------

class Review(tk.Tk):
    COLS = ("card", "current", "suggested", "conf", "deepseek", "problems", "decision", "final")
    WIDTHS = (220, 100, 115, 45, 130, 300, 70, 105)

    def __init__(self, folder: str = DEFAULT_FOLDER) -> None:
        super().__init__()
        self.title("Sidecar Review — 03_CLASSIFY")
        self.geometry("1300x820")
        self.rows: dict[str, Row] = {}
        self.runner: Runner | None = None
        self.sort_col, self.sort_rev = "card", False
        self.var_folder = tk.StringVar(value=folder)
        self.var_facet = tk.StringVar(value="standing")
        self.var_driver = tk.StringVar(value="name_words")
        self.var_view = tk.StringVar(value="All")
        self.var_search = tk.StringVar()
        self.var_blind = tk.BooleanVar(value=False)
        self._inbox: queue.Queue = queue.Queue()   # worker thread -> UI thread (tk is not thread-safe)
        self._build()
        self.after(100, self._poll)

    def _poll(self) -> None:
        while not self._inbox.empty():
            fn, args = self._inbox.get_nowait()
            fn(*args)
        self.after(100, self._poll)

    def _build(self) -> None:
        top = ttk.Frame(self, padding=6); top.pack(fill="x")
        ttk.Label(top, text="Sidecars folder:").pack(side="left")
        ttk.Entry(top, textvariable=self.var_folder, width=70).pack(side="left", padx=4)
        ttk.Button(top, text="…", width=3, command=self.pick_folder).pack(side="left")
        ttk.Label(top, text="  Facet:").pack(side="left")
        ttk.Combobox(top, textvariable=self.var_facet, values=list(VALID), width=10,
                     state="readonly").pack(side="left")
        ttk.Label(top, text="  Suggest from:").pack(side="left")
        self.cb_driver = ttk.Combobox(top, textvariable=self.var_driver, width=18, state="readonly")
        self.cb_driver.pack(side="left")
        self.cb_driver.bind("<<ComboboxSelected>>", lambda e: self.apply_driver())
        ttk.Button(top, text="Load / Re-predict", command=self.load).pack(side="left", padx=6)

        flt = ttk.Frame(self, padding=(6, 0)); flt.pack(fill="x")
        ttk.Label(flt, text="Show:").pack(side="left")
        cb = ttk.Combobox(flt, textvariable=self.var_view, values=VIEWS, width=22, state="readonly")
        cb.pack(side="left", padx=4); cb.bind("<<ComboboxSelected>>", lambda e: self.render())
        ttk.Label(flt, text="Search:").pack(side="left", padx=(10, 0))
        ent = ttk.Entry(flt, textvariable=self.var_search, width=30); ent.pack(side="left", padx=4)
        self.var_search.trace_add("write", lambda *_: self.render())
        self.btn_all = ttk.Button(flt, text="Select ALL", command=self.select_all); self.btn_all.pack(side="left", padx=(16, 2))
        ttk.Button(flt, text="Select none", command=lambda: self.tree.selection_set(())).pack(side="left")

        act = ttk.Frame(self, padding=6); act.pack(fill="x")
        ttk.Button(act, text="✔ Accept suggestion (selected)", command=lambda: self.decide("accept")).pack(side="left")
        ttk.Button(act, text="✘ Reject — keep current (selected)", command=lambda: self.decide("reject")).pack(side="left", padx=4)
        ttk.Button(act, text="✎ Set value… (selected)", command=self.edit).pack(side="left")
        ttk.Button(act, text="↺ Clear decision (selected)", command=lambda: self.decide("")).pack(side="left", padx=4)
        ds_bar = ttk.Frame(self, padding=(6, 0, 6, 4)); ds_bar.pack(fill="x", after=act)
        ttk.Label(ds_bar, text="DeepSeek:").pack(side="left")
        ttk.Button(ds_bar, text="🔎 Ask about selected",
                   command=lambda: self.ask_ai(self.selected())).pack(side="left", padx=4)
        ttk.Button(ds_bar, text="🔎 Ask about ALL stuck",
                   command=lambda: self.ask_ai([r for r in self.rows.values() if r.stuck])).pack(side="left")
        ttk.Button(ds_bar, text="✔ Accept DeepSeek's value (selected)", command=self.accept_ai).pack(side="left", padx=4)
        ttk.Button(ds_bar, text="💬 Answer its question…", command=self.reply_ai).pack(side="left")
        ttk.Checkbutton(ds_bar, text="blind (hide current value — a real prediction, not a check)",
                        variable=self.var_blind).pack(side="left", padx=8)
        self.lbl_ai = ttk.Label(ds_bar, foreground="#666",
                                text="key found" if ds.available() else "no DEEPSEEK_API_KEY — buttons will report it")
        self.lbl_ai.pack(side="left", padx=10)
        ttk.Button(act, text="Open card", command=self.open_card).pack(side="left", padx=(16, 0))
        ttk.Button(act, text="Scoreboard", command=self.show_scoreboard).pack(side="left", padx=4)
        ttk.Button(act, text="💾 Write accepted to cards", command=self.commit).pack(side="right")

        pane = ttk.Panedwindow(self, orient="vertical"); pane.pack(fill="both", expand=True, padx=6)
        tf = ttk.Frame(pane); pane.add(tf, weight=3)
        self.tree = ttk.Treeview(tf, columns=self.COLS, show="headings", selectmode="extended")
        for c, w in zip(self.COLS, self.WIDTHS):
            self.tree.heading(c, text=c, command=lambda c=c: self.sort_by(c))
            self.tree.column(c, width=w, anchor="w", stretch=c == "problems")
        ys = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ys.set)
        self.tree.pack(side="left", fill="both", expand=True); ys.pack(side="right", fill="y")
        self.tree.tag_configure("problem", background="#fde2e2")
        self.tree.tag_configure("nosugg", background="#fff4d6")
        self.tree.tag_configure("accept", background="#e2f5e2")
        self.tree.tag_configure("edit", background="#e2ecfd")
        self.tree.tag_configure("reject", foreground="#888888")
        self.tree.tag_configure("question", background="#f1e2fd")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.show_detail())
        self.tree.bind("<Double-1>", lambda e: self.edit())
        self.tree.bind("<Control-a>", lambda e: (self.select_all(), "break")[1])
        self.tree.bind("<a>", lambda e: self.decide("accept"))
        self.tree.bind("<r>", lambda e: self.decide("reject"))

        df = ttk.Labelframe(pane, text="Details — where it stopped, what every engine said, the card", padding=4)
        pane.add(df, weight=2)
        self.detail = tk.Text(df, wrap="word", height=12, font=("Consolas", 9))
        self.detail.pack(fill="both", expand=True)

        self.status = ttk.Label(self, padding=4, anchor="w", text="Pick a folder and press Load.")
        self.status.pack(fill="x")

    # ---- loading ------------------------------------------------------
    def pick_folder(self) -> None:
        d = filedialog.askdirectory(initialdir=self.var_folder.get() or ".")
        if d:
            self.var_folder.set(d)

    def load(self) -> None:
        if any(r.decision for r in self.rows.values()) and not messagebox.askyesno(
                "Reload", "You have unwritten decisions. Reload and drop them?"):
            return
        folder = Path(self.var_folder.get().strip().replace("\\", "/"))
        if not folder.is_dir():
            messagebox.showerror("Folder", f"Not a folder (or not reachable):\n{folder}"); return
        self.status.config(text="Loading cards and asking every engine…")
        self.config(cursor="watch")
        threading.Thread(target=self._load_worker, args=(folder, self.var_facet.get()), daemon=True).start()

    def _load_worker(self, folder: Path, facet: str) -> None:
        try:
            rows: dict[str, Row] = {}
            for p in sorted(folder.glob("*.md")):
                try:
                    fields, tags = sc_adapter.parse_card(p)
                    if not fields:   # could be the index, or broken
                        head = p.read_text(encoding="utf-8", errors="replace")[:400]
                        if "type: subject-index" in head:
                            continue
                except Exception as e:  # noqa: BLE001
                    fields, tags = {}, []
                    head = f"unreadable: {e}"
                r = Row(path=p, subject=fields.get("subject", p.stem), fields=fields, tags=tags)
                r.current = current_value(facet, fields, tags)
                r.problems = card_problems(p, fields, tags, facet)
                rows[r.iid] = r
            runner = Runner(db_path=PGUI / "data" / f"classify_{facet}.db", context_keys=("paper",))
            src = f"sidecar:{folder.parent.name}"
            runner.ledger.conn.execute("DELETE FROM events WHERE source=? AND action=?", (src, f"classify:{facet}"))
            runner.ledger.conn.commit()
            # never learn from values that aren't on the closed list
            evs = [e for e in sc_adapter.read(folder, facet) if e.subject in VALID[facet]]
            runner.ingest(evs, refit=False); runner.refit()
            sync(runner.ledger)
            runner.ledger.register_engine("deepseek", ds.URL, "service", "next_subject",
                                          {"describe": "DeepSeek triage on stuck cards (harness/deepseek_triage.py)"})
            for r in rows.values():
                ctx = {"paper": r.subject, "folder_class": r.fields.get("folder_class", ""),
                       "words": r.subject.lower()}
                runner.ledger.conn.execute(
                    "DELETE FROM predictions WHERE context_key=? AND resolved_at IS NULL", (f"paper={r.subject}",))
                r.predictions = runner.shadow(ctx)
            runner.ledger.conn.close()   # sqlite connections can't cross threads; the UI opens its own
            self._inbox.put((self._loaded, (rows, runner.ledger.path, len(evs))))
        except Exception as e:  # noqa: BLE001
            self._inbox.put((self._failed, (e,)))

    def _failed(self, e: Exception) -> None:
        self.config(cursor="")
        self.status.config(text=f"Load failed: {e}")
        messagebox.showerror("Load failed", str(e))

    def _loaded(self, rows: dict[str, Row], db_path: Path, n_events: int) -> None:
        self.config(cursor="")
        runner = Runner(db_path=db_path, context_keys=("paper",))
        self.rows, self.runner = rows, runner
        engines = sorted(runner.engines)
        self.cb_driver["values"] = engines
        if self.var_driver.get() not in engines and engines:
            self.var_driver.set("name_words" if "name_words" in engines else engines[0])
        self.apply_driver()
        bad = {n: e for n, e in runner.errors.items()}
        msg = f"Loaded {len(rows)} cards · trained on {n_events} labelled '{self.var_facet.get()}' values"
        if bad:
            msg += " · engine errors: " + "; ".join(f"{k}: {v}" for k, v in bad.items())
        self.status_base = msg
        self.render()

    def apply_driver(self) -> None:
        drv = self.var_driver.get()
        for r in self.rows.values():
            p = next((p for p in r.predictions if p.engine == drv), None)
            top = p.top if p else None
            r.suggested = top.value if top else ""
            r.conf = top.confidence if top else None
            r.why = (top.reason if top else (p.guidance if p else "engine did not answer"))
            if r.decision == "accept":
                r.final = r.suggested
        self.render()

    # ---- table --------------------------------------------------------
    def visible(self) -> list[Row]:
        view, q = self.var_view.get(), self.var_search.get().strip().lower()
        out = []
        for r in self.rows.values():
            if view == "Needs attention" and not r.attention: continue
            if view == "Stuck (send to DeepSeek)" and not r.stuck: continue
            if view == "DeepSeek answered" and not r.ai: continue
            if view == "DeepSeek has a question" and not r.ai.get("question"): continue
            if view == "Disagrees with current" and (not r.suggested or r.suggested == r.current): continue
            if view == "Missing value" and r.current: continue
            if view == "Undecided" and r.decision: continue
            if view == "Decided" and not r.decision: continue
            if q and q not in f"{r.subject} {r.current} {r.suggested} {' '.join(r.problems)}".lower(): continue
            out.append(r)
        key = {"card": lambda r: r.subject.lower(), "current": lambda r: r.current,
               "suggested": lambda r: r.suggested, "conf": lambda r: r.conf or 0,
               "problems": lambda r: len(r.problems), "decision": lambda r: r.decision,
               "deepseek": lambda r: r.ai.get("value") or "",
               "final": lambda r: r.final}[self.sort_col]
        return sorted(out, key=key, reverse=self.sort_rev)

    def _values(self, r: Row) -> tuple:
        probs = "; ".join(r.problems) if r.problems else ("" if r.suggested else f"no suggestion — {r.why}")
        if r.ai.get("_error"):
            ai = "error"
        elif r.ai.get("_pending"):
            ai = "asking…"
        elif r.ai:
            ai = f"{r.ai.get('value') or '?'} {r.ai.get('confidence', 0):.2f}" + (" ❓" if r.ai.get("question") else "")
        else:
            ai = ""
        return (r.subject, r.current or "—", r.suggested or "—",
                f"{r.conf:.2f}" if r.conf is not None else "", ai, probs,
                r.decision + (" ✓" if r.written else ""), r.final)

    def _tag(self, r: Row) -> tuple:
        if r.decision in ("accept", "edit", "reject"): return (r.decision,)
        if r.ai.get("question"): return ("question",)
        if r.problems: return ("problem",)
        if not r.suggested: return ("nosugg",)
        return ()

    def render(self) -> None:
        keep = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        vis = self.visible()
        for r in vis:
            self.tree.insert("", "end", iid=r.iid, values=self._values(r), tags=self._tag(r))
        self.tree.selection_set([i for i in keep if self.tree.exists(i)])
        self.btn_all.config(text=f"Select ALL {len(vis)}")
        self.update_status()

    def refresh_rows(self, rows: list[Row]) -> None:
        for r in rows:
            if self.tree.exists(r.iid):
                self.tree.item(r.iid, values=self._values(r), tags=self._tag(r))
        self.update_status()

    def sort_by(self, col: str) -> None:
        self.sort_rev = (not self.sort_rev) if self.sort_col == col else False
        self.sort_col = col
        self.render()

    def select_all(self) -> None:
        self.tree.selection_set(self.tree.get_children())

    def selected(self) -> list[Row]:
        return [self.rows[i] for i in self.tree.selection() if i in self.rows]

    def update_status(self) -> None:
        rs = list(self.rows.values())
        c = lambda d: sum(1 for r in rs if r.decision == d)
        att = sum(1 for r in rs if r.attention)
        self.status.config(text=f"{getattr(self, 'status_base', '')}   |   showing {len(self.tree.get_children())} of {len(rs)}"
                                f" · selected {len(self.tree.selection())} · needs attention {att}"
                                f" · accepted {c('accept')} · edited {c('edit')} · rejected {c('reject')}")

    # ---- decisions ----------------------------------------------------
    def decide(self, how: str) -> None:
        sel = self.selected()
        if not sel:
            return
        skipped = 0
        for r in sel:
            if how == "accept" and not r.readable:
                skipped += 1; continue
            if how == "accept":
                if not r.suggested:
                    skipped += 1; continue
                r.decision, r.final = "accept", r.suggested
            elif how == "reject":
                r.decision, r.final = "reject", r.current
            else:
                r.decision, r.final = "", ""
        self.refresh_rows(sel)
        if skipped:
            self.status.config(text=self.status.cget("text") + f"   ({skipped} skipped: no suggestion, or the card is unreadable — fix it first)")

    def edit(self) -> None:
        sel = [r for r in self.selected() if r.readable]
        if not sel:
            if self.selected():
                messagebox.showinfo("Set value", "Those cards are unreadable (no frontmatter). Open and fix them first.")
            return
        facet = self.var_facet.get()
        dlg = tk.Toplevel(self); dlg.title("Set value"); dlg.transient(self); dlg.grab_set()
        ttk.Label(dlg, padding=8, text=f"Set '{facet}' for {len(sel)} card(s)"
                  + (f":  {sel[0].subject}" if len(sel) == 1 else "")).pack(anchor="w")
        var = tk.StringVar(value=sel[0].final or sel[0].suggested or sel[0].current)
        cb = ttk.Combobox(dlg, textvariable=var, values=VALID.get(facet, []), width=30)
        cb.pack(padx=8, fill="x"); cb.focus_set()
        ttk.Label(dlg, padding=(8, 2), foreground="#666",
                  text="Closed list shown. Typing something else is allowed but will be flagged.").pack(anchor="w")

        def ok(_=None):
            v = var.get().strip()
            if not v:
                return
            if facet in VALID and v not in VALID[facet] and not messagebox.askyesno(
                    "Not on the closed list", f"'{v}' is not in the {facet} vocabulary. Use it anyway?", parent=dlg):
                return
            for r in sel:
                r.decision, r.final = "edit", v
            dlg.destroy(); self.refresh_rows(sel)

        bf = ttk.Frame(dlg, padding=8); bf.pack(fill="x")
        ttk.Button(bf, text="OK", command=ok).pack(side="right")
        ttk.Button(bf, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
        dlg.bind("<Return>", ok); dlg.bind("<Escape>", lambda e: dlg.destroy())

    # ---- details ------------------------------------------------------
    def show_detail(self) -> None:
        sel = self.selected()
        self.update_status()
        self.detail.delete("1.0", "end")
        if len(sel) != 1:
            if sel:
                self.detail.insert("end", f"{len(sel)} cards selected.")
            return
        r = sel[0]
        out = [f"{r.subject}    ({r.path.name})",
               f"current {self.var_facet.get()}: {r.current or '—'}    decision: {r.decision or '—'}    final: {r.final or '—'}", ""]
        out.append("WHERE IT STOPPED:" if r.problems else "PROBLEMS: none")
        out += [f"  ✘ {p}" for p in r.problems]
        if not r.suggested:
            out.append(f"  ? no suggestion from {self.var_driver.get()}: {r.why}")
        if r.ai and not r.ai.get("_pending"):
            out += ["", "DEEPSEEK:"]
            if r.ai.get("_error"):
                out.append(f"  error: {r.ai['_error']}")
            else:
                out.append(f"  stuck at:  {r.ai.get('stuck_at', '')}")
                out.append(f"  diagnosis: {r.ai.get('diagnosis', '')}")
                out.append(f"  value:     {r.ai.get('value')}  ({r.ai.get('confidence', 0):.2f})  — {r.ai.get('reason', '')}")
                if r.ai.get("question"):
                    out.append(f"  ❓ asks you: {r.ai['question']}")
                if r.reply:
                    out.append(f"  your answer: {r.reply}")
                out.append("  (from cache, free)" if r.ai.get("_cached") else f"  tokens: {r.ai.get('_tokens')}")
        out += ["", "ENGINES:"]
        for p in r.predictions:
            if p.candidates:
                alts = ", ".join(f"{c.value} {c.confidence:.2f}" for c in p.candidates[:4])
                out.append(f"  {p.engine:18s} {alts}")
                out.append(f"  {'':18s} └ {p.top.reason}")
            else:
                out.append(f"  {p.engine:18s} (nothing) — {p.guidance}")
        out += ["", "CARD:"]
        try:
            out.append(r.path.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:  # noqa: BLE001
            out.append(f"(cannot read: {e})")
        self.detail.insert("end", "\n".join(out))

    def open_card(self) -> None:
        for r in self.selected()[:5]:
            try:
                os.startfile(str(r.path))  # noqa: S606 — user-initiated
            except Exception as e:  # noqa: BLE001
                messagebox.showerror("Open", str(e))

    def show_scoreboard(self) -> None:
        if not self.runner:
            return
        lines = [f"{'engine':20s} {'scored':>6s} {'hits':>5s} {'rate':>6s} {'pending':>7s}"]
        for s in self.runner.scoreboard():
            rate = f"{s['hit_rate']:.2f}" if s["hit_rate"] is not None else "—"
            lines.append(f"{s['engine']:20s} {s['scored']:6d} {s['hits']:5d} {rate:>6s} {s['pending']:7d}")
        win = tk.Toplevel(self); win.title(f"Scoreboard — {self.var_facet.get()}")
        t = tk.Text(win, width=60, height=14, font=("Consolas", 10)); t.pack(fill="both", expand=True)
        t.insert("end", "\n".join(lines) + "\n\nEvery accept / reject / edit you write scores every engine.")

    # ---- DeepSeek -----------------------------------------------------
    def ask_ai(self, rows: list[Row], confirm: bool = True) -> None:
        if not rows:
            messagebox.showinfo("DeepSeek", "Nothing selected / nothing stuck."); return
        if confirm and len(rows) > 1 and not messagebox.askyesno(
                "DeepSeek", f"Ask DeepSeek about {len(rows)} card(s)?\n"
                            f"Cards already asked (unchanged) come from cache for free.\n"
                            f"deepseek-chat, roughly 1-2k tokens per card."):
            return
        facet = self.var_facet.get()
        jobs = []
        for r in rows:
            try:
                text = r.path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:  # noqa: BLE001
                text = f"(cannot read card: {e})"
            answers = [f"{p.engine}: {p.top.value} {p.top.confidence:.2f} ({p.top.reason})" if p.top
                       else f"{p.engine}: nothing ({p.guidance})" for p in r.predictions]
            jobs.append((r.iid, text, list(r.problems), answers, r.reply))
            r.ai = {"_pending": True}
        self.refresh_rows(rows)
        self.lbl_ai.config(text=f"asking about {len(jobs)} card(s)…")
        threading.Thread(target=self._ai_worker, args=(jobs, facet, self.var_blind.get()), daemon=True).start()

    def _ai_worker(self, jobs: list[tuple], facet: str, blind: bool = False) -> None:
        import concurrent.futures as cf
        allowed = VALID[facet]
        with cf.ThreadPoolExecutor(max_workers=8) as pool:
            def ask(text, probs, answers, reply):   # reads the source paper (NAS) off the UI thread
                m = re.search(r'^source_file:\s*"?([^"\n]+)"?\s*$', text, re.M)
                paper = source_papers.excerpt(m.group(1)) if m else ""
                return ds.triage(text, facet, allowed, probs, answers, reply, blind=blind, paper=paper)
            futs = {pool.submit(ask, text, probs, answers, reply): iid
                    for iid, text, probs, answers, reply in jobs}
            for n, fut in enumerate(cf.as_completed(futs), 1):
                self._inbox.put((self._ai_done, (futs[fut], fut.result(), n, len(jobs))))

    def _ai_done(self, iid: str, ans: dict[str, Any], n: int, total: int) -> None:
        r = self.rows.get(iid)
        if not r:
            return
        r.ai = ans
        if self.runner and ans.get("value") and not ans.get("_error"):
            key = f"paper={r.subject}"
            self.runner.ledger.conn.execute(
                "DELETE FROM predictions WHERE engine='deepseek' AND context_key=? AND resolved_at IS NULL", (key,))
            self.runner.ledger.add_prediction(Prediction(
                engine="deepseek", target="next_subject", context_key=key,
                candidates=[Candidate(ans["value"], ans.get("confidence", 0), ans.get("reason", ""))],
                markers={k: ans.get(k) for k in ("stuck_at", "diagnosis", "question")},
                guidance=ans.get("diagnosis", "")))
        self.refresh_rows([r])
        errs = sum(1 for x in self.rows.values() if x.ai.get("_error"))
        self.lbl_ai.config(text=f"answered {n}/{total}" + (f" · {errs} error(s) — see details" if errs else ""))
        if n == total and total > 1:
            asks = sum(1 for x in self.rows.values() if x.ai.get("question"))
            threading.Thread(target=notify.toast, daemon=True, args=(
                "DeepSeek finished", f"Answered {total} card(s)"
                + (f", {asks} with a question for you" if asks else "") + ". Back in the review window.")).start()
        if self.tree.selection() == (iid,):
            self.show_detail()

    def accept_ai(self) -> None:
        sel = [r for r in self.selected() if r.readable and r.ai.get("value")]
        for r in sel:
            r.decision, r.final = "edit", r.ai["value"]
        self.refresh_rows(sel)
        if not sel:
            messagebox.showinfo("DeepSeek", "None of the selected cards has a DeepSeek value yet.")

    def reply_ai(self) -> None:
        sel = self.selected()
        if len(sel) != 1 or not sel[0].ai or sel[0].ai.get("_pending"):
            messagebox.showinfo("DeepSeek", "Select one card that DeepSeek has answered."); return
        r = sel[0]
        dlg = tk.Toplevel(self); dlg.title(f"Answer DeepSeek — {r.subject}"); dlg.transient(self); dlg.grab_set()
        ttk.Label(dlg, padding=8, wraplength=520,
                  text=f"It asked: {r.ai.get('question') or '(no question — add context anyway)'}").pack(anchor="w")
        box = tk.Text(dlg, width=70, height=5, wrap="word"); box.pack(padx=8)
        box.insert("1.0", r.reply); box.focus_set()

        def send():
            r.reply = box.get("1.0", "end").strip()
            dlg.destroy()
            self.ask_ai([r], confirm=False)

        bf = ttk.Frame(dlg, padding=8); bf.pack(fill="x")
        ttk.Button(bf, text="Send and re-ask", command=send).pack(side="right")
        ttk.Button(bf, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)

    # ---- write --------------------------------------------------------
    def commit(self) -> None:
        facet = self.var_facet.get()
        decided = [r for r in self.rows.values() if r.decision and not r.written]
        changes = {r.iid for r in decided if r.decision in ("accept", "edit") and r.final and r.final != r.current}
        if not decided:
            messagebox.showinfo("Write", "No decisions yet."); return
        if not messagebox.askyesno("Write to cards",
                                   f"{len(changes)} card(s) will change '{facet}'.\n"
                                   f"{len(decided) - len(changes)} decision(s) keep the current value.\n\n"
                                   f"Originals are backed up to sidecars/.review_backup/ first.\nGo?"):
            return
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        folder = Path(self.var_folder.get().strip().replace("\\", "/"))
        backup = folder / ".review_backup" / stamp
        log_path = SHARED / "data" / "review_log.csv"
        new_log = not log_path.exists()
        errors, scored, wrote = [], 0, 0
        with open(log_path, "a", newline="", encoding="utf-8") as lf:
            w = csv.writer(lf)
            if new_log:
                w.writerow(["when", "folder", "card", "facet", "current", "suggested", "driver", "decision", "final"])
            for r in decided:
                try:
                    if r.iid in changes:
                        backup.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(r.path, backup / r.path.name)
                        write_value(r.path, facet, r.final)
                        wrote += 1
                    outcome = r.final or r.current
                    if outcome and self.runner:
                        scored += self.runner.resolve({"paper": r.subject}, outcome)
                    w.writerow([stamp, str(folder), r.subject, facet, r.current, r.suggested,
                                self.var_driver.get(), r.decision, outcome])
                    r.written = True
                    r.current = outcome or r.current
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{r.subject}: {e}")
        self.render()
        threading.Thread(target=self._report_and_notify, args=(folder, facet, wrote, len(errors)),
                         daemon=True).start()
        msg = f"Wrote {wrote} card(s). Scored {scored} prediction(s)."
        if changes:
            msg += f"\nBackup: {backup}"
        if errors:
            msg += "\n\nErrors:\n" + "\n".join(errors[:20])
        messagebox.showinfo("Done", msg + "\n\nPress Load / Re-predict to retrain on the new values.")

    @staticmethod
    def _report_and_notify(folder: Path, facet: str, wrote: int, errors: int) -> None:
        """Rebuild the classifications page, then a Windows toast that opens it when clicked."""
        page = None
        try:
            sys.path.insert(0, str(ROOT / "01_SIDECARS"))
            import sidecar_report
            page = sidecar_report.main(folder).with_suffix(".html")
        except Exception as e:  # noqa: BLE001
            print(f"report rebuild failed: {e}", file=sys.stderr)
        body = f"{wrote} card(s) changed '{facet}'." + (f" {errors} error(s)." if errors else "")
        notify.toast("Classifications written", body + (" Click to open the report." if page else ""), page)


if __name__ == "__main__":
    Review(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FOLDER).mainloop()
