"""FIS Search Workbench - rough GUI over the FIS registry (feel-it-out build).

Read-only against the registry. It builds its OWN full-text index at
.data/fis_search_index.sqlite so the registry (fis_folder_memory.sqlite) is never modified.

Features
  Search tab : FTS5 (with snippets + bm25 ranking) | LIKE | regex | fuzzy
               filters: doc_type, format, law, chi factor, domain, folder prefix,
               min type confidence, modified-after, include file content
               facet counts for the current result set, sortable columns, CSV export
               detail: every registry field, type scores, evidence, content preview with hits
               actions: open file / open folder / copy path / find similar / same fingerprint
                        live re-classify (fis_classifier + structural_evidence) / propose name
  Tools tab  : build/refresh content index, registry stats, duplicates, missing files,
               stale scans, run fis_folder_memory.py scan on a folder (streamed log)
  Hub tab    : hub memory text/vector search, desktop file cache search, folder search
"""
from __future__ import annotations

import csv
import difflib
import json
import os
import queue
import re
import sqlite3
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parents[1]
FIS_DIR = ROOT / "file-intelligence-system"
REGISTRY_DB = FIS_DIR / "fis_folder_memory.sqlite"
INDEX_DB = ROOT / ".data" / "fis_search_index.sqlite"
HUB_DB = Path(os.environ.get("FIHUB_DB_PATH", ROOT / ".data" / "file-intelligence-hub.sqlite3"))

sys.path.insert(0, str(FIS_DIR))
sys.path.insert(0, str(ROOT))

TEXT_EXT = {"md", "txt", "html", "htm", "json", "py", "js", "ts", "yaml", "yml", "csv", "tex",
            "lean", "sh", "bat", "ps1", "toml", "ini", "xml", "rst", "sql", "css", "chi", "fmeta", "c"}
CONTENT_CAP = 200_000
STALE_DAYS = 30

COLS = ("name", "doc_type", "conf", "law", "chi", "format", "size", "modified", "scanned", "path")


# ---------------------------------------------------------------- data layer
def registry() -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{REGISTRY_DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def jload(s, default=None):
    try:
        return json.loads(s) if s else default
    except Exception:
        return default


def classification(row) -> dict:
    return jload(row["local_classification_json"], {}) or {}


def law_of(row) -> str:
    law = classification(row).get("law")
    return (law.get("name") if isinstance(law, dict) else law) or ""


def chi_of(row) -> str:
    return classification(row).get("chi_factor") or ""


def cls_domain_of(row) -> str:
    d = classification(row).get("domain")
    return (d.get("name") if isinstance(d, dict) else d) or ""


def age_days(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    except Exception:
        return None


def read_text(path: str, cap: int = CONTENT_CAP) -> str:
    try:
        with open(path, "rb") as f:
            raw = f.read(cap)
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""


def index_conn() -> sqlite3.Connection:
    INDEX_DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(INDEX_DB)
    c.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(
        file_id UNINDEXED, name, path, keywords, address, proposed, doc_type, law, chi, domain,
        content, tokenize='unicode61 remove_diacritics 2')""")
    c.execute("CREATE TABLE IF NOT EXISTS meta(file_id TEXT PRIMARY KEY, fingerprint TEXT, indexed_at TEXT, has_content INT)")
    return c


def build_index(with_content: bool, log, stop: threading.Event) -> None:
    reg = registry()
    idx = index_conn()
    known = {r[0]: r[1] for r in idx.execute("SELECT file_id, fingerprint||'|'||has_content FROM meta")}
    rows = reg.execute("SELECT * FROM file_memory").fetchall()
    live_ids = set()
    done = updated = 0
    for row in rows:
        if stop.is_set():
            log("stopped")
            break
        fid = row["file_id"]
        live_ids.add(fid)
        want_content = with_content and row["format"] in TEXT_EXT
        sig = f"{row['content_fingerprint']}|{int(want_content)}"
        done += 1
        if known.get(fid) == sig:
            continue
        content = read_text(row["path"]) if want_content else ""
        idx.execute("DELETE FROM docs WHERE file_id=?", (fid,))
        idx.execute("INSERT INTO docs VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            fid, row["name"], row["path"], row["keywords_text"] or "", row["lossless_address"] or "",
            row["proposed_name"] or "", row["doc_type"] or "", law_of(row), chi_of(row), cls_domain_of(row), content))
        idx.execute("INSERT OR REPLACE INTO meta VALUES (?,?,?,?)",
                    (fid, row["content_fingerprint"], datetime.now(timezone.utc).isoformat(), int(want_content)))
        updated += 1
        if updated % 100 == 0:
            idx.commit()
            log(f"indexed {done}/{len(rows)} (updated {updated})")
    gone = [k for k in known if k not in live_ids] if not stop.is_set() else []
    for fid in gone:
        idx.execute("DELETE FROM docs WHERE file_id=?", (fid,))
        idx.execute("DELETE FROM meta WHERE file_id=?", (fid,))
    idx.commit()
    idx.close()
    log(f"index done: {done} seen, {updated} updated, {len(gone)} removed -> {INDEX_DB}")


def fts_query(text: str) -> str:
    """Pass through if user wrote FTS syntax, otherwise AND of prefix terms."""
    if re.search(r'["*()]|\b(AND|OR|NOT|NEAR)\b|\w+:', text):
        return text
    terms = re.findall(r"\w+", text)
    return " ".join(f'"{t}"*' for t in terms)


# ---------------------------------------------------------------- GUI
class Workbench(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FIS Search Workbench (rough)")
        self.geometry("1500x900")
        self.rows: dict[str, sqlite3.Row] = {}
        self.snippets: dict[str, str] = {}
        self.current: list[str] = []
        self.logq: queue.Queue = queue.Queue()
        self.stop_evt = threading.Event()

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self.tab_search = ttk.Frame(nb); nb.add(self.tab_search, text="Search")
        self.tab_tools = ttk.Frame(nb); nb.add(self.tab_tools, text="Tools / Index / Scan")
        self.tab_hub = ttk.Frame(nb); nb.add(self.tab_hub, text="Hub memory")
        self.build_search()
        self.build_tools()
        self.build_hub()
        self.load_registry()
        self.after(200, self.drain_log)

    # ------------------------------------------------------------ search tab
    def build_search(self):
        top = ttk.Frame(self.tab_search); top.pack(fill="x", padx=4, pady=4)
        self.q = tk.StringVar()
        e = ttk.Entry(top, textvariable=self.q, width=60); e.pack(side="left")
        e.bind("<Return>", lambda _: self.run_search())
        self.mode = tk.StringVar(value="fts")
        for m in ("fts", "like", "regex", "fuzzy"):
            ttk.Radiobutton(top, text=m, value=m, variable=self.mode).pack(side="left")
        self.use_content = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="search content", variable=self.use_content).pack(side="left", padx=6)
        ttk.Button(top, text="Search", command=self.run_search).pack(side="left")
        ttk.Button(top, text="Clear filters", command=self.clear_filters).pack(side="left")
        ttk.Button(top, text="Export CSV", command=self.export_csv).pack(side="left")
        self.status = ttk.Label(top, text=""); self.status.pack(side="left", padx=10)

        flt = ttk.Frame(self.tab_search); flt.pack(fill="x", padx=4)
        self.f = {}
        for key in ("doc_type", "format", "law", "chi", "domain"):
            ttk.Label(flt, text=key).pack(side="left")
            cb = ttk.Combobox(flt, width=14, values=[""]); cb.pack(side="left", padx=(0, 6))
            self.f[key] = cb
        ttk.Label(flt, text="folder contains").pack(side="left")
        self.f_folder = ttk.Entry(flt, width=24); self.f_folder.pack(side="left", padx=(0, 6))
        ttk.Label(flt, text="min conf").pack(side="left")
        self.f_conf = ttk.Entry(flt, width=5); self.f_conf.pack(side="left", padx=(0, 6))
        ttk.Label(flt, text="modified after (YYYY-MM-DD)").pack(side="left")
        self.f_after = ttk.Entry(flt, width=11); self.f_after.pack(side="left")
        ttk.Label(flt, text="limit").pack(side="left", padx=(6, 0))
        self.f_limit = ttk.Entry(flt, width=6); self.f_limit.insert(0, "500"); self.f_limit.pack(side="left")

        pan = ttk.PanedWindow(self.tab_search, orient="horizontal"); pan.pack(fill="both", expand=True, padx=4, pady=4)
        # facets
        left = ttk.Frame(pan); pan.add(left, weight=1)
        ttk.Label(left, text="Facets (current results) - double-click to filter").pack(anchor="w")
        self.facets = ttk.Treeview(left, columns=("n",), show="tree headings", height=30)
        self.facets.heading("#0", text="value"); self.facets.heading("n", text="n")
        self.facets.column("n", width=50)
        self.facets.pack(fill="both", expand=True)
        self.facets.bind("<Double-1>", self.facet_click)
        # results
        mid = ttk.Frame(pan); pan.add(mid, weight=4)
        self.tree = ttk.Treeview(mid, columns=COLS, show="headings")
        widths = dict(name=260, doc_type=90, conf=45, law=45, chi=35, format=50, size=70, modified=85, scanned=70, path=500)
        for c in COLS:
            self.tree.heading(c, text=c, command=lambda c=c: self.sort_by(c))
            self.tree.column(c, width=widths[c], anchor="w")
        ys = ttk.Scrollbar(mid, command=self.tree.yview); self.tree.configure(yscrollcommand=ys.set)
        self.tree.pack(side="left", fill="both", expand=True); ys.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.show_detail)
        self.tree.bind("<Double-1>", lambda _: self.open_file())
        self.tree.tag_configure("stale", foreground="#b36b00")
        self.tree.tag_configure("missing", foreground="#b00000")
        # detail
        right = ttk.Frame(pan); pan.add(right, weight=3)
        act = ttk.Frame(right); act.pack(fill="x")
        for label, fn in [("Open", self.open_file), ("Folder", self.open_folder), ("Copy path", self.copy_path),
                          ("Similar", self.find_similar), ("Same fingerprint", self.same_fp),
                          ("Re-classify live", self.reclassify), ("Propose name", self.propose)]:
            ttk.Button(act, text=label, command=fn).pack(side="left")
        self.detail = tk.Text(right, wrap="word", font=("Consolas", 9))
        self.detail.tag_configure("hit", background="#ffe066")
        self.detail.tag_configure("h", font=("Consolas", 10, "bold"))
        self.detail.pack(fill="both", expand=True)

    def load_registry(self):
        try:
            reg = registry()
            rows = reg.execute("SELECT * FROM file_memory").fetchall()
        except Exception as e:
            messagebox.showerror("Registry", f"Cannot open {REGISTRY_DB}\n{e}")
            return
        self.rows = {r["file_id"]: r for r in rows}
        vals = {k: set() for k in self.f}
        for r in rows:
            vals["doc_type"].add(r["doc_type"] or ""); vals["format"].add(r["format"] or "")
            vals["law"].add(law_of(r)); vals["chi"].add(chi_of(r)); vals["domain"].add(cls_domain_of(r))
        for k, cb in self.f.items():
            cb["values"] = [""] + sorted(v for v in vals[k] if v)
        idx_state = "content index present" if INDEX_DB.exists() else "NO content index yet - build it in Tools (FTS falls back to metadata LIKE)"
        self.status.config(text=f"registry: {len(rows)} files | {idx_state}")
        self.show_ids(list(self.rows)[:500])

    def clear_filters(self):
        for cb in self.f.values(): cb.set("")
        for w in (self.f_folder, self.f_conf, self.f_after): w.delete(0, "end")

    def passes(self, r) -> bool:
        fv = {k: cb.get() for k, cb in self.f.items()}
        if fv["doc_type"] and r["doc_type"] != fv["doc_type"]: return False
        if fv["format"] and r["format"] != fv["format"]: return False
        if fv["law"] and law_of(r) != fv["law"]: return False
        if fv["chi"] and chi_of(r) != fv["chi"]: return False
        if fv["domain"] and cls_domain_of(r) != fv["domain"]: return False
        fol = self.f_folder.get().strip().lower()
        if fol and fol not in (r["path"] or "").lower(): return False
        try:
            if self.f_conf.get() and (r["type_confidence"] or 0) < float(self.f_conf.get()): return False
        except ValueError:
            pass
        if self.f_after.get() and (r["last_modified"] or "") < self.f_after.get(): return False
        return True

    def run_search(self):
        text = self.q.get().strip()
        mode = self.mode.get()
        limit = int(self.f_limit.get() or 500)
        self.snippets = {}
        ids: list[str] = []
        try:
            if not text:
                ids = list(self.rows)
            elif mode == "fts" and INDEX_DB.exists():
                idx = index_conn()
                cols = "{name path keywords address proposed doc_type law chi domain content}" if self.use_content.get() \
                    else "{name path keywords address proposed doc_type law chi domain}"
                sql = (f"SELECT file_id, snippet(docs, 10, '[[', ']]', ' ... ', 18) FROM docs "
                       f"WHERE docs MATCH ? ORDER BY bm25(docs, 0, 8, 2, 4, 3, 3, 2, 2, 2, 2, 1) LIMIT 5000")
                for fid, snip in idx.execute(sql, (f"{cols} : ({fts_query(text)})",)):
                    ids.append(fid); self.snippets[fid] = snip
                idx.close()
            elif mode in ("fts", "like"):
                t = text.lower()
                ids = [k for k, r in self.rows.items() if t in " ".join(
                    str(r[c] or "") for c in ("name", "path", "keywords_text", "lossless_address", "proposed_name", "doc_type")).lower()]
            elif mode == "regex":
                rx = re.compile(text, re.I)
                for k, r in self.rows.items():
                    hay = " ".join(str(r[c] or "") for c in ("name", "path", "keywords_text", "lossless_address", "proposed_name"))
                    if rx.search(hay):
                        ids.append(k)
                    elif self.use_content.get() and r["format"] in TEXT_EXT and INDEX_DB.exists():
                        pass  # content regex done below on index to avoid SMB reads
                if self.use_content.get() and INDEX_DB.exists():
                    idx = index_conn()
                    have = set(ids)
                    for fid, content in idx.execute("SELECT file_id, content FROM docs WHERE content != ''"):
                        if fid not in have and rx.search(content):
                            m = rx.search(content); ids.append(fid)
                            self.snippets[fid] = content[max(0, m.start() - 80): m.end() + 80]
                    idx.close()
            elif mode == "fuzzy":
                t = text.lower()
                scored = []
                for k, r in self.rows.items():
                    name = Path(r["name"]).stem.lower()
                    s = max(difflib.SequenceMatcher(None, t, name).ratio(),
                            max((difflib.SequenceMatcher(None, t, w.lower()).ratio()
                                 for w in (r["keywords_text"] or "").split(",")[:30]), default=0))
                    if s >= 0.72:
                        scored.append((s, k))
                ids = [k for _, k in sorted(scored, reverse=True)]
        except Exception as e:
            messagebox.showerror("Search", str(e))
            return
        ids = [i for i in ids if i in self.rows and self.passes(self.rows[i])]
        self.status.config(text=f"{len(ids)} hits ({mode}){' - showing ' + str(limit) if len(ids) > limit else ''}")
        self.fill_facets(ids)
        self.show_ids(ids[:limit])

    def show_ids(self, ids):
        self.current = ids
        self.tree.delete(*self.tree.get_children())
        for fid in ids:
            r = self.rows[fid]
            sc = age_days(r["last_scanned"])
            tags = ("stale",) if sc is not None and sc > STALE_DAYS else ()
            self.tree.insert("", "end", iid=fid, tags=tags, values=(
                r["name"], r["doc_type"], f"{(r['type_confidence'] or 0):.2f}", law_of(r), chi_of(r), r["format"],
                r["size_bytes"], (r["last_modified"] or "")[:10], f"{sc:.0f}d" if sc is not None else "?", r["path"]))

    def fill_facets(self, ids):
        self.facets.delete(*self.facets.get_children())
        groups = {"doc_type": lambda r: r["doc_type"], "format": lambda r: r["format"], "law": law_of,
                  "chi": chi_of, "domain": cls_domain_of,
                  "top folder": lambda r: str(Path(r["path"]).parent.name)}
        for g, fn in groups.items():
            counts: dict[str, int] = {}
            for i in ids:
                v = fn(self.rows[i]) or "(none)"
                counts[v] = counts.get(v, 0) + 1
            node = self.facets.insert("", "end", text=g, open=g in ("doc_type", "law"))
            for v, n in sorted(counts.items(), key=lambda x: -x[1])[:40]:
                self.facets.insert(node, "end", text=v, values=(n,))

    def facet_click(self, _):
        sel = self.facets.focus()
        parent = self.facets.parent(sel)
        if not parent:
            return
        g, v = self.facets.item(parent, "text"), self.facets.item(sel, "text")
        if g in self.f:
            self.f[g].set("" if v == "(none)" else v)
        elif g == "top folder":
            self.f_folder.delete(0, "end"); self.f_folder.insert(0, v)
        self.run_search()

    def sort_by(self, col):
        data = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        num = col in ("conf", "size")
        data.sort(key=lambda x: float(x[0] or 0) if num else x[0].lower(), reverse=getattr(self, "_rev", False))
        self._rev = not getattr(self, "_rev", False)
        for i, (_, k) in enumerate(data):
            self.tree.move(k, "", i)

    def export_csv(self):
        p = filedialog.asksaveasfilename(defaultextension=".csv")
        if not p:
            return
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(COLS)
            for k in self.tree.get_children(""):
                w.writerow(self.tree.item(k, "values"))

    # ------------------------------------------------------------ detail + actions
    def sel(self):
        s = self.tree.focus()
        return self.rows.get(s) if s else None

    def show_detail(self, _=None):
        r = self.sel()
        if not r:
            return
        d = self.detail
        d.delete("1.0", "end")
        d.insert("end", r["name"] + "\n", "h")
        exists = os.path.exists(r["path"])
        d.insert("end", f"{r['path']}\n{'EXISTS' if exists else '!! MISSING ON DISK'}"
                        f"   scanned {age_days(r['last_scanned']) or 0:.0f} days ago\n\n")
        if r["file_id"] in self.snippets:
            d.insert("end", "Match snippet\n", "h")
            self._insert_hl(self.snippets[r["file_id"]].replace("[[", "").replace("]]", "") + "\n\n")
        d.insert("end", "Type scores\n", "h")
        for k, v in sorted((jload(r["type_scores_json"], {}) or {}).items(), key=lambda x: -x[1]):
            d.insert("end", f"  {k:<13} {v:.3f} {'#' * int(v * 40)}\n")
        d.insert("end", "\nType evidence\n", "h")
        d.insert("end", json.dumps(jload(r["type_evidence_json"], []), indent=1)[:2000] + "\n")
        d.insert("end", "\nAll registry fields\n", "h")
        for k in r.keys():
            v = r[k]
            if isinstance(v, str) and v[:1] in "[{":
                v = json.dumps(jload(v, v), indent=1)
            d.insert("end", f"{k}: {v}\n")
        if exists and r["format"] in TEXT_EXT:
            d.insert("end", "\nContent preview (first 4000 chars)\n", "h")
            self._insert_hl(read_text(r["path"], 4000))

    def _insert_hl(self, text):
        start = self.detail.index("end-1c")
        self.detail.insert("end", text)
        terms = [t for t in re.findall(r"\w{3,}", self.q.get()) if t.upper() not in ("AND", "OR", "NOT", "NEAR")]
        for t in terms:
            pos = start
            while True:
                pos = self.detail.search(t, pos, "end", nocase=True)
                if not pos:
                    break
                endp = f"{pos}+{len(t)}c"
                self.detail.tag_add("hit", pos, endp)
                pos = endp

    def open_file(self):
        r = self.sel()
        if r:
            try: os.startfile(r["path"])
            except Exception as e: messagebox.showerror("Open", str(e))

    def open_folder(self):
        r = self.sel()
        if r:
            subprocess.Popen(["explorer", "/select,", r["path"]])

    def copy_path(self):
        r = self.sel()
        if r:
            self.clipboard_clear(); self.clipboard_append(r["path"])

    def find_similar(self):
        r = self.sel()
        if not r:
            return
        kws = [k.strip() for k in (r["keywords_text"] or "").split(",") if len(k.strip()) > 3][:12]
        law, chi = law_of(r), chi_of(r)
        if INDEX_DB.exists() and kws:
            q = " OR ".join(f'"{k}"' for k in kws)
            idx = index_conn()
            ids = [fid for (fid,) in idx.execute(
                "SELECT file_id FROM docs WHERE docs MATCH ? ORDER BY bm25(docs) LIMIT 300", (q,)) if fid != r["file_id"]]
            idx.close()
        else:
            ids = [k for k, x in self.rows.items() if k != r["file_id"] and law_of(x) == law and chi_of(x) == chi]
        self.status.config(text=f"similar to {r['name']}: {len(ids)}")
        self.fill_facets(ids); self.show_ids(ids)

    def same_fp(self):
        r = self.sel()
        if not r:
            return
        ids = [k for k, x in self.rows.items() if x["content_fingerprint"] == r["content_fingerprint"]]
        self.status.config(text=f"same content fingerprint: {len(ids)}")
        self.show_ids(ids)

    def reclassify(self):
        r = self.sel()
        if not r:
            return
        out = {}
        try:
            import fis_classifier as fc
            text = read_text(r["path"], 60000)
            out["classify_file"] = fc.classify_file(r["path"], text[:6000])
            out["classify_document_type"] = fc.classify_document_type(text, r["name"], r["path"])
        except Exception as e:
            out["classifier_error"] = repr(e)
        try:
            import structural_evidence as se
            out["structural_evidence"] = se.score_structural_evidence(read_text(r["path"], 60000))
        except Exception as e:
            out["structural_evidence_error"] = repr(e)
        self.popup(f"Live classification - {r['name']}", json.dumps(out, indent=1, default=str))

    def propose(self):
        r = self.sel()
        if not r:
            return
        try:
            import fis_namer
            cls = classification(r)
            rec = {"name": r["name"], "path": r["path"], "ext": "." + r["format"],
                   "mtime": os.path.getmtime(r["path"]) if os.path.exists(r["path"]) else 0,
                   "content_type": cls.get("content_type", ""), "chi_domain": cls_domain_of(r),
                   "chi_confidence": r["type_confidence"] or 0, "dominant_chi": chi_of(r), "law": law_of(r)}
            res = fis_namer.propose_name(rec)
        except Exception as e:
            res = {"error": repr(e)}
        self.popup(f"Proposed name - {r['name']}",
                   f"registry proposed: {r['proposed_name']}\nlossless address: {r['lossless_address']}\n\nlive:\n"
                   + json.dumps(res, indent=1, default=str))

    def popup(self, title, text):
        w = tk.Toplevel(self); w.title(title); w.geometry("900x700")
        t = tk.Text(w, wrap="word", font=("Consolas", 9)); t.pack(fill="both", expand=True)
        t.insert("end", text)

    # ------------------------------------------------------------ tools tab
    def build_tools(self):
        f = ttk.Frame(self.tab_tools); f.pack(fill="x", padx=6, pady=6)
        self.idx_content = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="include file content (reads text files, slow over NAS first time)",
                        variable=self.idx_content).pack(side="left")
        ttk.Button(f, text="Build / refresh search index", command=self.start_index).pack(side="left", padx=4)
        ttk.Button(f, text="Stop", command=self.stop_evt.set).pack(side="left")
        ttk.Button(f, text="Reload registry", command=self.load_registry).pack(side="left", padx=12)

        g = ttk.Frame(self.tab_tools); g.pack(fill="x", padx=6)
        for label, fn in [("Registry stats", self.stats), ("Duplicates (fingerprint)", self.dupes),
                          ("Missing on disk (checks paths)", self.missing), (f"Stale scans > {STALE_DAYS}d", self.stale),
                          ("Low-confidence types", self.lowconf)]:
            ttk.Button(g, text=label, command=fn).pack(side="left", padx=2, pady=4)

        h = ttk.Frame(self.tab_tools); h.pack(fill="x", padx=6, pady=4)
        ttk.Label(h, text="Run FIS scan on folder:").pack(side="left")
        self.scan_dir = ttk.Entry(h, width=70); self.scan_dir.pack(side="left")
        ttk.Button(h, text="...", command=lambda: (self.scan_dir.delete(0, "end"),
                   self.scan_dir.insert(0, filedialog.askdirectory() or ""))).pack(side="left")
        self.scan_ai = tk.BooleanVar(value=False)
        ttk.Checkbutton(h, text="local AI (Ollama)", variable=self.scan_ai).pack(side="left")
        self.scan_types = tk.BooleanVar(value=True)
        ttk.Checkbutton(h, text="doc types", variable=self.scan_types).pack(side="left")
        ttk.Button(h, text="Run scan", command=self.run_scan).pack(side="left", padx=4)
        ttk.Label(self.tab_tools, text="(scan writes FIS.html views + updates the registry, per fis_folder_memory.py)").pack(anchor="w", padx=6)

        self.log = tk.Text(self.tab_tools, font=("Consolas", 9)); self.log.pack(fill="both", expand=True, padx=6, pady=6)

    def logmsg(self, m):
        self.logq.put(m)

    def drain_log(self):
        try:
            while True:
                self.log.insert("end", str(self.logq.get_nowait()) + "\n"); self.log.see("end")
        except queue.Empty:
            pass
        self.after(200, self.drain_log)

    def start_index(self):
        self.stop_evt.clear()
        wc = self.idx_content.get()
        threading.Thread(target=lambda: self._safe(build_index, wc, self.logmsg, self.stop_evt), daemon=True).start()

    def _safe(self, fn, *a):
        try:
            fn(*a)
        except Exception as e:
            self.logmsg(f"ERROR: {e!r}")

    def stats(self):
        reg = registry()
        out = [f"registry {REGISTRY_DB}", f"files {len(self.rows)}  folders {reg.execute('select count(*) from folder_memory').fetchone()[0]}"]
        for label, fn in [("doc_type", lambda r: r["doc_type"]), ("format", lambda r: r["format"]),
                          ("law", law_of), ("chi", chi_of), ("domain(classifier)", cls_domain_of)]:
            c: dict[str, int] = {}
            for r in self.rows.values():
                c[fn(r) or "(none)"] = c.get(fn(r) or "(none)", 0) + 1
            out.append(f"\n{label}: " + ", ".join(f"{k}={v}" for k, v in sorted(c.items(), key=lambda x: -x[1])[:25]))
        ai = sum(1 for r in self.rows.values() if (r["ai_enrichment_json"] or "{}") != "{}")
        out.append(f"\nAI-enriched: {ai}")
        if INDEX_DB.exists():
            idx = index_conn()
            out.append(f"index docs {idx.execute('select count(*) from meta').fetchone()[0]}, "
                       f"with content {idx.execute('select count(*) from meta where has_content=1').fetchone()[0]}")
        self.logmsg("\n".join(out))

    def _to_search(self, ids, label):
        self.status.config(text=f"{label}: {len(ids)}")
        self.fill_facets(ids); self.show_ids(ids)
        self.nametowidget(self.tab_search.winfo_parent()).select(self.tab_search)

    def dupes(self):
        by: dict[str, list[str]] = {}
        for k, r in self.rows.items():
            if r["content_fingerprint"]:
                by.setdefault(r["content_fingerprint"], []).append(k)
        groups = [v for v in by.values() if len(v) > 1]
        ids = [i for g in sorted(groups, key=len, reverse=True) for i in g]
        self.logmsg(f"{len(groups)} duplicate groups, {len(ids)} files")
        self._to_search(ids, "duplicates")

    def missing(self):
        def work():
            ids = [k for k, r in self.rows.items() if not os.path.exists(r["path"])]
            self.logmsg(f"{len(ids)} registry paths missing on disk")
            self.after(0, lambda: self._to_search(ids, "missing on disk"))
        threading.Thread(target=work, daemon=True).start()
        self.logmsg("checking paths...")

    def stale(self):
        ids = [k for k, r in self.rows.items() if (age_days(r["last_scanned"]) or 0) > STALE_DAYS]
        self._to_search(ids, f"stale > {STALE_DAYS}d")

    def lowconf(self):
        ids = sorted((k for k, r in self.rows.items() if (r["type_confidence"] or 0) < 0.3),
                     key=lambda k: self.rows[k]["type_confidence"] or 0)
        self._to_search(ids, "type confidence < 0.30")

    def run_scan(self):
        folder = self.scan_dir.get().strip()
        if not folder:
            return
        cmd = [sys.executable, "-u", str(FIS_DIR / "fis_folder_memory.py"), folder]
        cmd.append("--local-ai" if self.scan_ai.get() else "--no-local-ai")
        if self.scan_types.get():
            cmd.append("--doc-types")
        self.logmsg("RUN " + " ".join(cmd))

        def work():
            p = subprocess.Popen(cmd, cwd=FIS_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace")
            for line in p.stdout:
                self.logmsg(line.rstrip())
            self.logmsg(f"scan exit {p.wait()} - click Reload registry, then refresh index")
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------ hub tab
    def build_hub(self):
        f = ttk.Frame(self.tab_hub); f.pack(fill="x", padx=6, pady=6)
        self.hq = ttk.Entry(f, width=50); self.hq.pack(side="left")
        self.hmode = tk.StringVar(value="memory-text")
        for m in ("memory-text", "memory-vector", "file-cache", "folders"):
            ttk.Radiobutton(f, text=m, value=m, variable=self.hmode).pack(side="left")
        ttk.Button(f, text="Search hub", command=self.hub_search).pack(side="left", padx=4)
        ttk.Button(f, text="Embed pending", command=self.hub_embed).pack(side="left")
        ttk.Label(self.tab_hub, text=f"hub db: {HUB_DB}  (currently empty tables are normal until the hub is fed)").pack(anchor="w", padx=6)
        self.hout = tk.Text(self.tab_hub, font=("Consolas", 9)); self.hout.pack(fill="both", expand=True, padx=6, pady=6)

    def _hub(self):
        from hub.storage.db import Database
        return Database(HUB_DB)

    def hub_search(self):
        self.hout.delete("1.0", "end")
        q, m = self.hq.get(), self.hmode.get()
        try:
            with self._hub() as db:
                conn = db.conn if hasattr(db, "conn") else db.connection
                if m.startswith("memory"):
                    from hub.storage.memory_repo import MemoryRepo
                    repo = MemoryRepo(conn)
                    res = repo.vector_search(q) if m == "memory-vector" else repo.search(q)
                elif m == "file-cache":
                    from hub.storage.desktop_file_cache_repo import DesktopFileCacheRepo
                    res = DesktopFileCacheRepo(conn).search(q)
                else:
                    from hub.storage.folder_repo import FolderRepo
                    res = FolderRepo(conn).search_folders(q)
            self.hout.insert("end", f"{len(res)} results\n" + json.dumps(res, indent=1, default=str))
        except Exception as e:
            self.hout.insert("end", f"hub error: {e!r}")

    def hub_embed(self):
        try:
            with self._hub() as db:
                from hub.storage.memory_repo import MemoryRepo
                conn = db.conn if hasattr(db, "conn") else db.connection
                res = MemoryRepo(conn).embed_pending()
            self.hout.insert("end", f"\nembedded {len(res)}\n")
        except Exception as e:
            self.hout.insert("end", f"hub error: {e!r}")


if __name__ == "__main__":
    Workbench().mainloop()
