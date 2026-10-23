#!/usr/bin/env python3
"""Drive Harvester — David-OS v3 GUI.

Search every drive for any concept (axiom, master equation, grace, ...),
score each document with a confidence value, filter / select / dedupe,
then export FLATTENED into one folder with a 3-tier sidecar per file.

Run:  python D:\\GitHub\\David-OSv3\\gui\\drive_harvester.py
Deps: PySide6, openpyxl (optional, for .xlsx content)

Confidence (0-100) = filename hit (40) + heading/title hit (15)
                   + body mentions (up to 30) + "displays it" structure (up to 15)

Sidecar schema (<exported name>.sidecar.json), three tiers deep:
  tier1_identity   — where it came from, hash, size, dates
  tier2_class      — code (AX/ME/...), confidence, signals, level
                     level ∈ SEED < INTRODUCED < DEVELOPED < CANON
  tier3_placement  — vault, status ∈ DRAFT / WORKING / FINISHED / CANONICAL
Export naming: {CODE}-{NNNN}__{slug}.{ext}
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import string
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from . import canon_pins as pins, fingerprint as fpr
except ImportError:
    import canon_pins as pins
    import fingerprint as fpr
from engine.symptoms.content import detect_duplicates, detect_thin_content
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QFileDialog,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QDialog, QDialogButtonBox, QFormLayout, QMainWindow, QMenu, QMessageBox, QPushButton, QSlider, QSplitter,
    QInputDialog, QScrollArea,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

# ── Colors — Consilience Atlas palette (matches axiom_search_export) ──
DEEP = "#0a0a0a"
SURFACE = "#111111"
SURFACE2 = "#1a1816"
GOLD = "#d4af37"
GOLD_DIM = "#3d2e0f"
CREAM = "#e8e0cc"
CREAM_DIM = "#6b6456"
SAGE = "#7a8c6e"
SLATE = "#6b8fbf"
COPPER = "#c17f3e"
RED_DIM = "#8b3a3a"

EXTENSIONS = [".md", ".txt", ".html", ".htm", ".csv", ".xlsx", ".xls"]
LEVELS = ["SEED", "INTRODUCED", "DEVELOPED", "CANON"]
STATUSES = ["DRAFT", "WORKING", "FINISHED", "PUBLISHED", "CANONICAL"]

SKIP_DIRS = {
    "windows", "program files", "program files (x86)", "programdata", "$recycle.bin",
    "system volume information", "appdata", "node_modules", ".git", ".venv", "venv",
    "__pycache__", "site-packages", ".cache", ".obsidian", ".trash", "recovery",
}
MAX_BYTES = 25 * 1024 * 1024

# Known concepts: short code + synonyms + "displays it without saying it" patterns.
# Any other term still works — it gets a code from its initials and generic patterns.
PROFILES = {
    "axiom": {
        "code": "AX",
        "synonyms": ["axioms", "axiomatic", "postulate", "first principle", "primitive assumption"],
        "structure": [
            r"^\s*(?:#+\s*)?(?:A|Ax|Axiom)\s*[-.]?\s*\d+\s*[:.)]",   # A1: / Axiom 3.
            r"\b(?:we\s+)?(?:assume|posit|stipulate)\s+that\b",
            r"\bself[- ]evident\b",
            r"\bcannot\s+be\s+(?:derived|proven)\b",
            r"\btaken\s+as\s+given\b",
            r"\biron\s+chain\b",
        ],
    },
    "master equation": {
        "code": "ME",
        "synonyms": ["master-equation", "χ =", "chi =", "coherence equation"],
        "structure": [
            r"χ\s*\(?\w*\)?\s*=",
            r"\bchi\s*=\s*",
            r"∭|∫∫∫",
            r"\bten\s+variables\b|\b10\s+variables\b",
        ],
    },
}

GENERIC_STRUCTURE = [
    r"^\s*(?:#+\s*)?definition\s*[:.]",
    r"^\s*(?:#+\s*)?(?:theorem|lemma|principle|law)\s*\d*\s*[:.]",
]


def profile_for(term: str, extra_syn: list[str]) -> dict:
    key = term.strip().lower()
    base = PROFILES.get(key)
    if base:
        p = {**base, "synonyms": base["synonyms"] + extra_syn}
    else:
        words = re.findall(r"[A-Za-z0-9]+", term)
        code = ("".join(w[0] for w in words)[:3] if len(words) > 1 else term[:2]).upper() or "XX"
        p = {"code": code, "synonyms": extra_syn, "structure": GENERIC_STRUCTURE}
    p["term"] = term.strip()
    return p


# ── Text extraction ────────────────────────────────────

def read_text(path: Path, limit_chars: int = 400_000) -> str:
    ext = path.suffix.lower()
    try:
        if ext == ".xlsx":
            try:
                import openpyxl
            except ImportError:
                return ""
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            parts, n = [], 0
            for ws in wb.worksheets:
                parts.append(f"# {ws.title}")
                for row in ws.iter_rows(values_only=True):
                    parts.append(" ".join(str(c) for c in row if c is not None))
                    n += 1
                    if n > 5000:
                        break
            wb.close()
            return "\n".join(parts)[:limit_chars]
        if ext == ".xls":
            return ""  # legacy binary: filename-only scoring
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(limit_chars)
    except Exception:
        return ""


def headings_of(text: str, ext: str) -> list[str]:
    heads = []
    if ext in (".html", ".htm"):
        heads += re.findall(r"<(?:title|h[1-3])[^>]*>(.*?)</", text, re.I | re.S)
    else:
        heads += re.findall(r"^\s*#{1,3}\s+(.+)$", text, re.M)
        heads += re.findall(r"^title:\s*(.+)$", text[:2000], re.M | re.I)
    first = text.strip().splitlines()[:1]
    return heads + first


def metadata_text(path: Path) -> str:
    """Read file-specific metadata only; a folder tag is not a tag on every child."""
    candidates = [Path(str(path) + suffix) for suffix in (".sidecar.json", ".fmeta", ".chi")]
    candidates.append(path.with_suffix(".fmeta"))
    return "\n".join(read_text(p, 100_000) for p in dict.fromkeys(candidates) if p.is_file())


def tag_text(text: str) -> str:
    """Frontmatter tag lists, HTML keyword metadata, and inline hashtags."""
    front = re.match(r"\A\ufeff?---\s*\n(.*?)\n---", text, re.S)
    parts = []
    if front:
        parts += re.findall(r"^(?:tags?|keywords):[^\n]*(?:\n[ \t]+[^\n]*)*", front[1], re.M | re.I)
    parts += re.findall(r"(?<!\w)#[\w/-]+", text)
    parts += re.findall(r'<meta\b[^>]*(?:keywords|tags)[^>]*>', text, re.I)
    return " ".join(parts)


def score_file(path: Path, prof: dict) -> dict | None:
    fields = set(prof.get("fields", ("filename", "heading", "body", "sidecar", "tags")))
    normalize = lambda value: value.casefold().replace("_", " ").replace("-", " ")
    terms = tuple(dict.fromkeys(normalize(t.strip()) for t in [prof["term"], *prof["synonyms"]] if t.strip()))
    contains = lambda value: any(t in normalize(value) for t in terms)
    signals, score, mentions = [], 0, 0
    if "filename" in fields and contains(path.stem):
        score += 40
        signals.append("filename")
    text = read_text(path) if fields & {"heading", "body", "tags"} else ""
    if "heading" in fields and contains(" ".join(headings_of(text, path.suffix.lower()))):
        score += 40
        signals.append("heading")
    if "tags" in fields and contains(tag_text(text)):
        score += 40
        signals.append("tags")
    if "sidecar" in fields and contains(metadata_text(path)):
        score += 40
        signals.append("sidecar")
    if "body" in fields:
        low = normalize(text)
        mentions = sum(low.count(t) for t in terms)
        if mentions:
            score += min(30, mentions * 5)
            signals.append(f"mentions\u00d7{mentions}")
    # Generic theorem/definition headings can strengthen a topic match, never create one.
    if not signals:
        return None
    if text and "body" in fields:
        struct = sum(len(re.findall(p, text, re.I | re.M)) for p in prof["structure"])
        if struct:
            score += min(15, struct * 5)
            signals.append(f"structure\u00d7{struct}")
    try:
        row = bare_row(path)
    except OSError:
        return None
    row.update(confidence=min(100, score), mentions=mentions, signals=signals)
    return row


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def available_drives() -> list[str]:
    if os.name != "nt":
        return ["/"]
    return [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]


# ── Scanner thread ─────────────────────────────────────

class Scanner(QThread):
    found = Signal(dict)
    progress = Signal(int, str)
    done = Signal(int)

    def __init__(self, roots, exts, prof, pin_list=()):
        super().__init__()
        self.roots, self.exts, self.prof = roots, set(exts), prof
        self.pins = list(pin_list)
        self._stop = False
        self.errors = []
        self.skipped = 0

    def stop(self):
        self._stop = True

    def run(self):
        seen = 0
        visited = set()
        for root in self.roots:
            for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: self.errors.append(str(e)), followlinks=False):
                if self._stop:
                    self.done.emit(seen)
                    return
                dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS and not d.startswith("$")
                               and not (Path(dirpath) / d).is_symlink()
                               and not getattr(Path(dirpath) / d, "is_junction", lambda: False)()]
                for fn in filenames:
                    if os.path.splitext(fn)[1].lower() not in self.exts:
                        continue
                    p = Path(dirpath) / fn
                    if self._stop:
                        self.done.emit(seen)
                        return
                    if p.is_symlink():
                        continue
                    identity = os.path.normcase(os.path.abspath(p))
                    if identity in visited:
                        continue
                    visited.add(identity)
                    seen += 1
                    if seen % 200 == 0:
                        self.progress.emit(seen, dirpath)
                    try:
                        if p.stat().st_size > MAX_BYTES:
                            self.skipped += 1
                            continue
                    except OSError as exc:
                        self.errors.append(str(exc))
                        continue
                    r = score_file(p, self.prof)
                    pin = pins.pin_for_path(str(p), self.pins) if self.pins else None
                    if pin:
                        r = apply_pin(r or bare_row(p), pin, p)
                    if r:
                        r["scan_root"] = str(Path(root).resolve())
                        self.found.emit(r)
        self.done.emit(seen)


def bare_row(p: Path) -> dict:
    st = p.stat()
    return {"path": str(p), "name": p.name, "ext": p.suffix.lower(), "size": st.st_size,
            "mtime": st.st_mtime, "confidence": 0, "mentions": 0, "signals": [],
            "sha256": "", "dup_of": "", "reclass": "", "match": None}


def apply_pin(r: dict, pin: dict, p: Path) -> dict:
    """Pinned canon: always included, ranked top, level/status taken from the pin."""
    ids = pins.frontmatter_ids(read_text(p, 3000)) if p.suffix.lower() == ".md" else {}
    tag = ids.get("canonical_id") or ids.get("legacy_id")
    r["text_score"] = r["confidence"]
    r["confidence"] = 100
    r["pin"] = pin
    r["signals"] = [f"★ PINNED {pin['level']}" + (f" {tag}" if tag else "")] + r["signals"]
    r["reclass"] = f"{pin['code']} · {pin['level']}"
    return r


# ── Heuristic sidecar guesses ─────────────────────────

def guess_level(r: dict) -> str:
    p = r["path"].lower()
    if "canon" in p:
        return "CANON"
    c = r["confidence"]
    return "DEVELOPED" if c >= 80 else "INTRODUCED" if c >= 50 else "SEED"


def guess_status(r: dict) -> str:
    p = r["path"].lower()
    if "canon" in p:
        return "CANONICAL"
    if any(k in p for k in ("final", "published", "finished")):
        return "FINISHED"
    if any(k in p for k in ("draft", "scratch", "dump", "inbox")):
        return "DRAFT"
    return "WORKING"


def guess_vault(r: dict) -> str:
    parts = Path(r["path"]).parts
    for i, part in enumerate(parts):
        if "vault" in part.lower() or part.lower() in ("00_canon", "opus", "theophysics"):
            return str(Path(*parts[: i + 1]))
    return str(Path(*parts[:2]))


def slugify(s: str, n: int = 60) -> str:
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    return re.sub(r"[\s_-]+", "-", s)[:n].strip("-") or "untitled"



class ReviewWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)
    progress = Signal(int, str)

    def __init__(self, root, kind, selected=(), profile=None, layout="flat"):
        super().__init__()
        self.root, self.kind, self.selected = Path(root), kind, list(selected)
        self.cancelled = False
        self.profile, self.layout = profile, layout

    def stop(self):
        self.cancelled = True

    def run(self):
        try:
            if self.kind == "export":
                manifest = export_files(self.selected, self.profile, self.root, self.layout,
                                        stop=lambda: self.cancelled, progress=self.progress.emit)
                self.completed.emit({"kind": "export", "manifest": manifest, "root": str(self.root),
                                     "requested": len(self.selected), "cancelled": self.cancelled})
                return
            files, empty_dirs, errors = [], [], []
            last_progress = 0
            if self.selected:
                files = [Path(r["path"]) for r in self.selected]
            else:
                if not self.root.is_dir():
                    raise NotADirectoryError(self.root)
                for folder, dirs, names in os.walk(self.root, followlinks=False, onerror=lambda e: errors.append(str(e))):
                    if self.cancelled:
                        return self.completed.emit({"cancelled": True})
                    here = Path(folder)
                    if not dirs and not names:
                        empty_dirs.append(str(here))
                    dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS and not d.startswith("$")
                               and not (here / d).is_symlink()
                               and not getattr(here / d, "is_junction", lambda: False)()]
                    files.extend(here / n for n in names if not (here / n).is_symlink())
                    if len(files) - last_progress >= 200:
                        self.progress.emit(len(files), folder)
                        last_progress = len(files)
            if self.kind == "duplicates":
                findings = [r.to_dict() for r in detect_duplicates(self.root, files=files,
                            stop=lambda: self.cancelled, progress=self.progress.emit)]
            else:
                findings = [{"path": path, "message": "Empty folder", "evidence": {}} for path in empty_dirs]
                zero = set()
                for f in files:
                    if self.cancelled:
                        break
                    try:
                        if f.stat().st_size == 0:
                            zero.add(str(f))
                            findings.append({"path": str(f), "message": "Empty file (0 bytes)", "evidence": {}})
                    except OSError as exc:
                        errors.append(str(exc))
                findings += [r.to_dict() for r in detect_thin_content(self.root, min_words=1, files=files,
                              stop=lambda: self.cancelled) if str(r.path) not in zero]
            self.completed.emit({"kind": self.kind, "findings": findings, "errors": errors,
                                 "files": len(files), "root": str(self.root), "cancelled": self.cancelled})
        except Exception as exc:
            self.failed.emit(str(exc))


# ── Main window ────────────────────────────────────────

COLS = ["✓", "Conf", "Name", "Ext", "Size KB", "Modified", "Signals", "Class", "Dup", "Match %", "Path"]


class Harvester(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Drive Harvester — David-OS v3")
        self.resize(1500, 900)
        self.rows: list[dict] = []
        self.review_worker = None
        self.scan_root = None
        self.prof = profile_for("axiom", [])
        self.scanner: Scanner | None = None
        self._build()
        self._style()

    # UI
    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        split = QSplitter(Qt.Horizontal)
        outer.addWidget(split)

        # Left: controls
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.addWidget(self._h("1. WHAT ARE YOU LOOKING FOR?"))
        self.term = QLineEdit("axiom")
        self.term.setPlaceholderText("any term: axiom, master equation, grace …")
        lv.addWidget(self.term)
        note = QLabel("Text search reads the first 400,000 characters; files over 25 MB are skipped.")
        note.setWordWrap(True)
        lv.addWidget(note)
        lv.addWidget(QLabel("Also counts as (comma separated)"))
        self.syn = QLineEdit()
        self.syn.setPlaceholderText("postulate, premise …")
        lv.addWidget(self.syn)

        lv.addWidget(QLabel("Look in:"))
        self.field_boxes = {}
        for key, label in [("filename", "Filename"), ("heading", "Title / headings"),
                           ("sidecar", "File sidecar"), ("tags", "Tags"), ("body", "Document body")]:
            box = QCheckBox(label)
            box.setChecked(True)
            self.field_boxes[key] = box
            lv.addWidget(box)
        lv.addWidget(self._h("2. ONE DRIVE OR FOLDER"))
        self.roots = QListWidget()
        self.roots.setMaximumHeight(145)
        for d in available_drives():
            it = QListWidgetItem(d)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            self.roots.addItem(it)
        reg = pins.load()
        listed = set()
        for pin in reg["pins"]:
            if pin["folder"] in listed:
                continue
            listed.add(pin["folder"])
            it = QListWidgetItem(pin["folder"])
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            it.setToolTip(f"★ pinned {pin['term']} · {pin['level']} · {pin['status']}")
            it.setForeground(QColor(GOLD))
            self.roots.addItem(it)
        for f in reg.get("recent_folders", []):
            if f not in listed:
                listed.add(f)
                it = QListWidgetItem(f)
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Unchecked)
                it.setToolTip("recent folder")
                self.roots.addItem(it)
        lv.addWidget(self.roots)
        pin_btn = QPushButton("★ Pin folder as canon…")
        pin_btn.clicked.connect(self._pin_dialog)
        lv.addWidget(pin_btn)
        pins_btn = QPushButton("Manage pins…")
        pins_btn.clicked.connect(self._manage_pins)
        lv.addWidget(pins_btn)
        add = QPushButton("+ Add folder")
        add.clicked.connect(self._add_root)
        lv.addWidget(add)

        lv.addWidget(self._h("FILE TYPES"))
        self.ext_boxes = {}
        grid = QHBoxLayout()
        col = QVBoxLayout()
        for i, e in enumerate(EXTENSIONS):
            cb = QCheckBox(e)
            cb.setChecked(True)
            cb.stateChanged.connect(self._refilter)
            self.ext_boxes[e] = cb
            col.addWidget(cb)
            if i == 3:
                grid.addLayout(col)
                col = QVBoxLayout()
        grid.addLayout(col)
        lv.addLayout(grid)

        lv.addWidget(self._h("CONFIDENCE THRESHOLD"))
        self.thresh_lbl = QLabel("Minimum score: 5")
        self.thresh = QSlider(Qt.Horizontal)
        self.thresh.setRange(0, 100)
        self.thresh.setValue(5)
        self.thresh.valueChanged.connect(lambda v: (self.thresh_lbl.setText(f"Minimum score: {v}"), self._refilter()))
        lv.addWidget(self.thresh_lbl)
        lv.addWidget(self.thresh)

        self.scan_btn = QPushButton("▶  SCAN")
        self.scan_btn.setObjectName("primary")
        self.scan_btn.clicked.connect(self._scan)
        lv.addWidget(self.scan_btn)
        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.clicked.connect(self._stop_work)
        lv.addWidget(self.stop_btn)
        lv.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(left)
        split.addWidget(scroll)

        # Right: results
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.addWidget(self._h("3. SELECT RESULTS   >   4. REVIEW   >   5. EXPORT"))
        bar = QHBoxLayout()
        advanced_bar = QHBoxLayout()
        self.action_buttons = []
        for label, fn in [
            ("Select all", lambda: self._check_all(True)),
            ("Select none", lambda: self._check_all(False)),
            ("Review duplicates...", self._dedupe),
            ("Review empty items...", self._review_empty),
            ("Classify again", self._reclassify),
            ("Learn fingerprint", self._learn_fp),
            ("Match fingerprint…", self._match_fp),
            ("Save list CSV", self._save_list),
            ("EXPORT...", self._export),
        ]:
            b = QPushButton(label)
            if label.startswith("EXPORT"):
                b.setObjectName("primary")
            b.clicked.connect(fn)
            self.action_buttons.append(b)
            (advanced_bar if label in ("Classify again", "Learn fingerprint", "Match fingerprint\u2026", "Save list CSV") else bar).addWidget(b)
        rv.addLayout(bar)
        rv.addLayout(advanced_bar)

        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setSectionResizeMode(10, QHeaderView.Stretch)
        for i, w in enumerate([30, 50, 280, 50, 70, 120, 200, 110, 45]):
            self.table.setColumnWidth(i, w)
        self.table.itemSelectionChanged.connect(self._preview)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._menu)

        vsplit = QSplitter(Qt.Vertical)
        vsplit.addWidget(self.table)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        vsplit.addWidget(self.preview)
        vsplit.setSizes([650, 200])
        rv.addWidget(vsplit)
        split.addWidget(right)
        split.setSizes([340, 1160])

        self.status = self.statusBar()

    def _h(self, t):
        l = QLabel(t)
        l.setWordWrap(True)
        l.setStyleSheet(f"color:{GOLD};font-weight:600;letter-spacing:2px;margin-top:10px;")
        return l

    def _style(self):
        self.setStyleSheet(f"""
            QWidget {{ background:{DEEP}; color:{CREAM}; font-family:'Segoe UI'; font-size:12px; }}
            QLineEdit, QListWidget, QTextEdit, QTableWidget {{ background:{SURFACE}; border:1px solid {GOLD_DIM}; padding:4px; }}
            QHeaderView::section {{ background:{SURFACE2}; color:{GOLD}; border:none; padding:4px; }}
            QTableWidget::item:selected {{ background:{GOLD_DIM}; }}
            QPushButton {{ background:{SURFACE2}; border:1px solid {GOLD_DIM}; padding:6px 10px; }}
            QPushButton:hover {{ border-color:{GOLD}; }}
            QPushButton#primary {{ background:{GOLD_DIM}; color:{GOLD}; font-weight:700; }}
            QSlider::handle:horizontal {{ background:{GOLD}; width:12px; }}
            QStatusBar {{ color:{CREAM_DIM}; }}
        """)

    # Scanning
    def _add_root(self):
        d = QFileDialog.getExistingDirectory(self, "Add folder")
        if d:
            pins.remember_folder(d)
            it = QListWidgetItem(d)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked)
            self.roots.addItem(it)

    def _scan(self):
        term = self.term.text().strip()
        if not term:
            return
        roots = [self.roots.item(i).text() for i in range(self.roots.count())
                 if self.roots.item(i).checkState() == Qt.Checked]
        exts = [e for e, cb in self.ext_boxes.items() if cb.isChecked()]
        if not roots or not exts:
            QMessageBox.warning(self, "Nothing to scan", "Pick at least one location and one file type.")
            return
        syn = [s.strip() for s in self.syn.text().split(",") if s.strip()]
        profile = profile_for(term, syn)
        if len(roots) != 1:
            QMessageBox.information(self, "One location at a time", "Check one drive or one folder for this pass.")
            return
        profile["fields"] = [key for key, cb in self.field_boxes.items() if cb.isChecked()]
        if not profile["fields"]:
            QMessageBox.information(self, "Search fields", "Choose at least one search field.")
            return
        if not Path(roots[0]).is_dir():
            QMessageBox.warning(self, "Location unavailable", "The selected drive or folder is not accessible.")
            return
        self.prof = profile
        self.term_pins = pins.pins_for_term(term, profile["synonyms"])
        self.scan_root = roots[0]
        self._seen_paths = set()
        self.rows.clear()
        self.table.setRowCount(0)
        self._busy(True)
        self.scanner = Scanner(roots, exts, self.prof, self.term_pins)
        self.scanner.found.connect(self._on_found)
        self.scanner.progress.connect(lambda n, d: self.status.showMessage(f"{n:,} files checked · {len(self.rows):,} hits · {d}"))
        self.scanner.done.connect(self._on_done)
        self.scanner.start()

    def _on_found(self, r):
        key = os.path.normcase(r["path"])
        if key in self._seen_paths:      # overlapping roots
            return
        self._seen_paths.add(key)
        r["checked"] = False
        self.rows.append(r)
        if len(self.rows) % 50 == 0:
            self._refilter()

    def _on_done(self, n):
        self._busy(False)
        self._refilter()
        self.table.sortItems(1, Qt.DescendingOrder)
        label = "Stopped (partial)" if self.scanner._stop else "Scan complete"
        self.status.showMessage(f"{label}: {n:,} checked | {len(self.rows):,} matches | "
                                f"{self.scanner.skipped} oversized | {len(self.scanner.errors)} access errors. "
                                "Select results, then review duplicates / empty items before export.")

    # Table
    def _visible(self):
        t = self.thresh.value()
        exts = {e for e, cb in self.ext_boxes.items() if cb.isChecked()}
        if ".html" in exts:
            exts.add(".htm")
        return [r for r in self.rows if r["confidence"] >= t and r["ext"] in exts]

    def _sync_checks(self):
        for i in range(self.table.rowCount()):
            it = self.table.item(i, 0)
            if it:
                self.rows[it.data(Qt.UserRole)]["checked"] = it.checkState() == Qt.Checked

    def _refilter(self):
        self._sync_checks()
        vis = self._visible()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(vis))
        idx = {id(r): i for i, r in enumerate(self.rows)}
        for i, r in enumerate(vis):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk.setCheckState(Qt.Checked if r["checked"] else Qt.Unchecked)
            chk.setData(Qt.UserRole, idx[id(r)])
            self.table.setItem(i, 0, chk)
            c = r["confidence"]
            vals = [c, r["name"], r["ext"], round(r["size"] / 1024, 1),
                    datetime.fromtimestamp(r["mtime"]).strftime("%Y-%m-%d %H:%M"),
                    ", ".join(r["signals"]), r["reclass"], "DUP" if r["dup_of"] else "",
                    -1 if r.get("match") is None else r["match"], r["path"]]
            for j, v in enumerate(vals, start=1):
                it = QTableWidgetItem()
                it.setData(Qt.DisplayRole, v)
                if j == 1:
                    it.setForeground(QColor(GOLD if c >= 80 else SAGE if c >= 50 else CREAM_DIM))
                elif j == 8 and v:
                    it.setForeground(QColor(RED_DIM))
                elif j == 7:
                    it.setForeground(QColor(COPPER))
                elif j == 9:
                    if v == -1:
                        it.setData(Qt.DisplayRole, "")
                        it.setData(Qt.UserRole, -1)
                    else:
                        it.setForeground(QColor(GOLD if v >= 80 else SAGE if v >= 50 else CREAM_DIM))
                elif j == 10:
                    it.setForeground(QColor(SLATE))
                self.table.setItem(i, j, it)
        self.table.setSortingEnabled(True)
        n_chk = sum(r["checked"] for r in self.rows)
        self.status.showMessage(f"{len(vis):,} shown of {len(self.rows):,} hits · {n_chk:,} selected")

    def _check_all(self, on):
        vis = {id(r) for r in self._visible()}
        for r in self.rows:
            if id(r) in vis:
                r["checked"] = on
        self.table.setRowCount(0)
        self._refilter()

    def _checked(self):
        self._sync_checks()
        return [r for r in self.rows if r["checked"]]

    def _preview(self):
        sel = self.table.selectedItems()
        if not sel:
            return
        row = self.table.item(sel[0].row(), 0)
        r = self.rows[row.data(Qt.UserRole)]
        text = read_text(Path(r["path"]), 6000)
        self.preview.setPlainText(f"{r['path']}\nconfidence {r['confidence']} · {', '.join(r['signals'])}\n\n{text}")

    def _menu(self, pos):
        m = QMenu(self)
        m.addAction("Check highlighted rows", lambda: self._set_highlighted(True))
        m.addAction("Uncheck highlighted rows", lambda: self._set_highlighted(False))
        m.addAction("Open file", lambda: self._open(False))
        m.addAction("Open containing folder", lambda: self._open(True))
        m.exec(self.table.viewport().mapToGlobal(pos))

    def _highlighted(self):
        rows = {i.row() for i in self.table.selectedItems()}
        return [self.rows[self.table.item(i, 0).data(Qt.UserRole)] for i in rows]

    def _set_highlighted(self, on):
        self._sync_checks()
        for r in self._highlighted():
            r["checked"] = on
        self._refilter()

    def _open(self, folder):
        for r in self._highlighted()[:1]:
            os.startfile(os.path.dirname(r["path"]) if folder else r["path"])

    # Actions
    def _busy(self, busy):
        self.scan_btn.setEnabled(not busy)
        for button in self.action_buttons:
            button.setEnabled(not busy)

    def _stop_work(self):
        if self.scanner and self.scanner.isRunning():
            self.scanner.stop()
        if self.review_worker and self.review_worker.isRunning():
            self.review_worker.stop()

    def closeEvent(self, event):
        if ((self.scanner and self.scanner.isRunning()) or
                (self.review_worker and self.review_worker.isRunning())):
            self._stop_work()
            self.status.showMessage("Stopping work; close again when it finishes.")
            event.ignore()
        else:
            event.accept()

    def _dedupe(self):
        self._start_review("duplicates")

    def _review_empty(self):
        self._start_review("empty")

    def _start_review(self, kind):
        options = ["Selected results", "Choose a root folder (all descendants)", "Whole drive from this scan"]
        scope, ok = QInputDialog.getItem(self, "Review scope", "Where should this check run?", options, 0, False)
        if not ok:
            return
        chosen, root = [], self.scan_root
        if scope == options[0]:
            chosen = self._checked()
            if not chosen:
                QMessageBox.information(self, "Select results", "Select files first, or choose a folder / drive scope.")
                return
            root = root or str(Path(chosen[0]["path"]).parent)
        elif scope == options[1]:
            root = QFileDialog.getExistingDirectory(self, "Review this folder and its subfolders", root or str(Path.home()))
            if not root:
                return
        else:
            if not root:
                QMessageBox.information(self, "Scan first", "Run a scan to choose the drive.")
                return
            root = Path(root).anchor
        self._busy(True)
        self.review_worker = ReviewWorker(root, kind, chosen)
        self.review_worker.progress.connect(lambda n, p: self.status.showMessage(f"Review: {n:,} files | {p}"))
        self.review_worker.completed.connect(self._show_review)
        self.review_worker.failed.connect(self._review_failed)
        self.review_worker.start()

    def _review_failed(self, message):
        self._busy(False)
        QMessageBox.warning(self, "Review failed", message)

    def _show_review(self, payload):
        self._busy(False)
        if payload.get("cancelled"):
            self.status.showMessage("Review cancelled. Selection unchanged.")
            return
        self.last_review = payload
        dialog = QDialog(self)
        dialog.setWindowTitle("Duplicate review" if payload["kind"] == "duplicates" else "Empty-item review")
        dialog.resize(1050, 650)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"Scope: {payload['root']}\n{payload['files']:,} files checked; "
                                f"{len(payload['findings'])} findings; {len(payload['errors'])} access errors.\n"
                                "Exclude acts on the export selection. Source files stay in place."))
        report = QTextEdit()
        report.setReadOnly(True)
        lines = []
        exclusions = {}
        chosen = {r["path"]: r for r in self._checked()}
        for finding in payload["findings"]:
            paths = finding.get("evidence", {}).get("files", [])
            if paths:
                # Keep a selected copy for export even when another copy exists elsewhere.
                candidates = [chosen[p] for p in paths if p in chosen]
                candidates.sort(key=lambda r: (r["confidence"], r["mtime"], r["path"]), reverse=True)
                keeper = candidates[0]["path"] if candidates else paths[0]
                lines.append("KEEP FOR EXPORT: " + keeper)
                lines.extend("  COPY: " + p for p in paths if p != keeper)
                exclusions.update({r["path"]: keeper for r in candidates[1:]})
            else:
                lines.append(f"{finding['message']}: {finding['path']}")
                if finding['path'] in chosen:
                    exclusions[finding['path']] = ""
        report.setPlainText("\n".join(lines + payload['errors']) or "No findings in this scope.")
        layout.addWidget(report)
        buttons = QHBoxLayout()
        exclude = QPushButton(f"Exclude {len(exclusions)} selected copies / empty files")
        exclude.setEnabled(bool(exclusions))
        def apply():
            for row in self.rows:
                if row["path"] in exclusions:
                    row["checked"] = False
                    row["dup_of"] = exclusions[row["path"]]
            self.table.setRowCount(0)
            self._refilter()
            dialog.accept()
        exclude.clicked.connect(apply)
        buttons.addWidget(exclude)
        save = QPushButton("Save review JSON...")
        def save_report():
            name, _ = QFileDialog.getSaveFileName(dialog, "Save review", str(Path.home() / "Documents" / "harvest_review.json"), "JSON (*.json)")
            if name:
                Path(name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        save.clicked.connect(save_report)
        buttons.addWidget(save)
        close = QPushButton("Keep selection / Close")
        close.clicked.connect(dialog.reject)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        dialog.exec()

    def _reclassify(self):
        """Second, stricter pass: must hit the term in more than one way."""
        chosen = self._checked()
        kept = 0
        for r in chosen:
            kinds = {s.split("×")[0] for s in r["signals"]}
            strong = "filename" in kinds or "heading" in kinds
            if strong and len(kinds) >= 2:
                r["reclass"] = f"{self.prof['code']} · primary"
                kept += 1
            elif r["mentions"] >= 3 or "structure" in kinds:
                r["reclass"] = f"{self.prof['code']} · discusses"
                kept += 1
            else:
                r["reclass"] = "passing mention"
                r["checked"] = False
        self.table.setRowCount(0)
        self._refilter()
        self.status.showMessage(f"Classified {len(chosen)} → {kept} kept, {len(chosen) - kept} passing mentions unchecked")

    # Canon pins
    def _pin_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Pin folder as canon")
        form = QFormLayout(dlg)
        folder = QComboBox()
        folder.setEditable(True)
        folder.addItems(pins.load().get("recent_folders", []))

        def browse_for():
            d = QFileDialog.getExistingDirectory(dlg, "Folder to pin", folder.currentText())
            if d:
                folder.setEditText(d)
        browse = QPushButton("Browse…")
        browse.clicked.connect(browse_for)
        row = QHBoxLayout()
        row.addWidget(folder, 1)
        row.addWidget(browse)
        form.addRow("Folder (includes subfolders)", row)
        term = QLineEdit(self.term.text().strip() or "axiom")
        form.addRow("Classified as (term)", term)
        code = QLineEdit(profile_for(term.text(), [])["code"])
        term.textChanged.connect(lambda t: code.setText(profile_for(t, [])["code"]))
        form.addRow("Code", code)
        level = QComboBox()
        level.addItems(LEVELS)
        level.setCurrentText("CANON")
        form.addRow("Level", level)
        status = QComboBox()
        status.addItems(STATUSES)
        status.setCurrentText("PUBLISHED")
        form.addRow("Status", status)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec() != QDialog.Accepted or not folder.currentText().strip():
            return
        f = folder.currentText().strip()
        if not os.path.isdir(f):
            QMessageBox.warning(self, "Pin", f"Not a folder:\n{f}")
            return
        pin = pins.add_pin(f, term.text().strip(), code.text().strip().upper() or "XX",
                           level.currentText(), status.currentText())
        it = QListWidgetItem(pin["folder"])
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(Qt.Checked)
        it.setForeground(QColor(GOLD))
        self.roots.addItem(it)
        self.status.showMessage(f"★ Pinned {pin['folder']} as {pin['term']} · {pin['level']} · {pin['status']} — rescan to apply")

    def _manage_pins(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Canon pins")
        dlg.resize(900, 400)
        v = QVBoxLayout(dlg)
        lst = QListWidget()
        lst.setSelectionMode(QAbstractItemView.ExtendedSelection)

        def fill():
            lst.clear()
            for p in pins.load()["pins"]:
                it = QListWidgetItem(f"[{p['code']}] {p['term']} · {p['level']} · {p['status']}   —   {p['folder']}")
                it.setData(Qt.UserRole, p)
                lst.addItem(it)

        def remove():
            for i in lst.selectedItems():
                p = i.data(Qt.UserRole)
                pins.remove_pin(p["folder"], p["term"])
            fill()
        fill()
        v.addWidget(lst)
        rm = QPushButton("Remove selected pins")
        rm.clicked.connect(remove)
        v.addWidget(rm)
        v.addWidget(QLabel(f"Registry: {pins.REGISTRY}"))
        dlg.exec()

    # Reverse fingerprint
    def _learn_fp(self):
        examples = self._checked()
        if len(examples) < 2:
            QMessageBox.information(self, "Fingerprint", "Tick at least 2 documents that belong together, then Learn.")
            return
        ex_paths = {r["path"] for r in examples}
        bg = [r for r in self.rows if r["path"] not in ex_paths][:300]
        self.status.showMessage(f"Learning from {len(examples)} examples vs {len(bg)} background docs …")
        QApplication.processEvents()
        name = slugify(getattr(self, "prof", {}).get("term", "set")) + f"_{len(examples)}ex"
        try:
            self.fp = fpr.learn([read_text(Path(r["path"])) for r in examples],
                                [read_text(Path(r["path"])) for r in bg], name=name)
        except ValueError as e:
            QMessageBox.warning(self, "Fingerprint", str(e))
            return
        fp_dir = Path.home() / "Documents" / "Harvest" / "fingerprints"
        fp_dir.mkdir(parents=True, exist_ok=True)
        fpr.save(self.fp, fp_dir / f"{name}.json")
        for r in self.rows:
            r["match"] = fpr.similarity(self.fp, read_text(Path(r["path"])))
        self.table.setRowCount(0)
        self._refilter()
        traits = "\n".join(f"  {t:<32} in {int(share*100)}% of examples" for t, _, share in self.fp["traits"][:25])
        self.preview.setPlainText(
            f"FINGERPRINT '{name}' — learned from {len(examples)} examples\n"
            f"saved: {fp_dir / (name + '.json')}\n\nWhat they have in common:\n{traits}\n\n"
            "Match % column now filled for every hit. Use 'Match fingerprint…' to test another folder.")

    def _match_fp(self):
        if not getattr(self, "fp", None):
            path, _ = QFileDialog.getOpenFileName(self, "Load fingerprint",
                                                  str(Path.home() / "Documents" / "Harvest" / "fingerprints"), "JSON (*.json)")
            if not path:
                return
            self.fp = fpr.load(path)
        folder = QFileDialog.getExistingDirectory(self, f"Match '{self.fp['name']}' against folder")
        if not folder:
            return
        exts = {e for e, cb in self.ext_boxes.items() if cb.isChecked()}
        self.rows.clear()
        self.table.setRowCount(0)
        n = 0
        for dirpath, dirnames, filenames in os.walk(folder):
            dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS]
            for fn in filenames:
                p = Path(dirpath) / fn
                if p.suffix.lower() not in exts:
                    continue
                try:
                    st = p.stat()
                    if st.st_size > MAX_BYTES:
                        continue
                except OSError:
                    continue
                text = read_text(p)
                m = fpr.similarity(self.fp, text)
                self.rows.append({
                    "path": str(p), "name": p.name, "ext": p.suffix.lower(), "size": st.st_size,
                    "mtime": st.st_mtime, "confidence": m, "mentions": 0, "match": m,
                    "signals": ["shares: " + ", ".join(fpr.shared_traits(self.fp, text, 5))] if m else [],
                    "sha256": "", "dup_of": "", "reclass": "", "checked": False,
                })
                n += 1
                if n % 50 == 0:
                    self.status.showMessage(f"Matching … {n} files")
                    QApplication.processEvents()
        self.table.setRowCount(0)
        self._refilter()
        self.table.sortItems(9, Qt.DescendingOrder)
        strong = sum(1 for r in self.rows if r["match"] >= 80)
        self.status.showMessage(f"Matched {n} files against '{self.fp['name']}' · {strong} at ≥80% · Conf column = match % here")

    def _save_list(self):
        chosen = self._checked() or self._visible()
        path, _ = QFileDialog.getSaveFileName(self, "Save list", str(Path.home() / "Documents" / "harvest_list.csv"), "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["confidence", "name", "ext", "size", "modified", "signals", "class", "dup_of", "match_pct", "path"])
            for r in chosen:
                w.writerow([r["confidence"], r["name"], r["ext"], r["size"],
                            datetime.fromtimestamp(r["mtime"]).isoformat(), "|".join(r["signals"]),
                            r["reclass"], r["dup_of"], r.get("match"), r["path"]])
        self.status.showMessage(f"Saved {len(chosen)} rows → {path}")

    def _export(self):
        chosen = self._checked()
        if not chosen:
            QMessageBox.information(self, "Export", "Select the files to export first.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("5. Export selected files")
        dialog.resize(850, 650)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"{len(chosen)} selected files. Copies and source receipts will be exported."))
        destination = QLineEdit(str(Path.home() / "Documents"))
        browse = QPushButton("Choose existing destination...")
        def pick():
            value = QFileDialog.getExistingDirectory(dialog, "Export destination", destination.text())
            if value:
                destination.setText(value)
        browse.clicked.connect(pick)
        layout.addWidget(destination)
        layout.addWidget(browse)
        mode = QComboBox()
        mode.addItem("Flatten - all selected files in this destination", "flat")
        mode.addItem("Preserve source subfolders", "tree")
        mode.addItem("Group files into folders by file type", "extension")
        layout.addWidget(mode)
        layout.addWidget(QLabel("Optional new collection folder (leave blank to use destination directly):"))
        collection = QLineEdit()
        layout.addWidget(collection)
        report = QTextEdit()
        report.setReadOnly(True)
        layout.addWidget(report)
        export = QPushButton("Copy selected files")
        export.setEnabled(False)
        preview = QPushButton("Preview destinations")
        state = {}
        def invalidate(*_):
            state.clear()
            export.setEnabled(False)
        def prepare():
            try:
                base = Path(destination.text()).expanduser().resolve()
                if not base.is_dir():
                    raise ValueError("Choose an existing destination directory.")
                folder = collection.text().strip()
                if folder and (folder in (".", "..") or any(c in folder for c in '/\\<>:"|?*')):
                    raise ValueError("Enter a single folder name, without path separators.")
                target = base / folder if folder else base
                plan = plan_export(chosen, self.prof, target, mode.currentData())
                state.update(dest=target, mode=mode.currentData())
                report.setPlainText("\n\n".join(f"{row['path']}\n  -> {out}" for row, out in plan))
                export.setEnabled(True)
            except (OSError, ValueError) as exc:
                invalidate()
                report.setPlainText(str(exc))
        preview.clicked.connect(prepare)
        destination.textChanged.connect(invalidate)
        collection.textChanged.connect(invalidate)
        mode.currentIndexChanged.connect(invalidate)
        export.clicked.connect(dialog.accept)
        layout.addWidget(preview)
        layout.addWidget(export)
        if dialog.exec() != QDialog.Accepted or not state:
            return
        self._busy(True)
        self.review_worker = ReviewWorker(state['dest'], "export", chosen, dict(self.prof), state['mode'])
        self.review_worker.progress.connect(lambda n, p: self.status.showMessage(f"Exporting {n}/{len(chosen)} | {p}"))
        self.review_worker.completed.connect(self._export_done)
        self.review_worker.failed.connect(self._review_failed)
        self.review_worker.start()

    def _export_done(self, payload):
        self._busy(False)
        ok = sum(bool(row.get("exported_as")) for row in payload['manifest'])
        state = "Stopped" if payload['cancelled'] else "Complete"
        QMessageBox.information(self, "Export " + state.lower(),
            f"{state}: {ok}/{payload['requested']} copied.\n{payload['root']}\n"
            "The manifest records each source and any errors.")


def plan_export(chosen, prof, dest, layout="flat"):
    """Plan destinations in the existing harvester, without writing anything."""
    dest = Path(dest).resolve()
    if layout not in {"flat", "tree", "extension"}:
        raise ValueError("Unknown export layout")
    plan, reserved = [], set()
    for row in sorted(chosen, key=lambda r: (-r["confidence"], r["path"])):
        src = Path(row["path"]).resolve()
        if layout == "tree":
            root = Path(row.get("scan_root", src.parent)).resolve()
            relative = src.relative_to(root)
        elif layout == "extension":
            relative = Path(src.suffix.lstrip(".").lower() or "no-extension") / src.name
        else:
            relative = Path(src.name)
        target = dest / relative
        base, number = target, 1
        while (any(os.path.normcase(str(target)+suffix) in reserved
                   for suffix in ("", ".sidecar.json", ".source_metadata.json")) or target.exists()
               or Path(str(target) + ".sidecar.json").exists()
               or Path(str(target) + ".source_metadata.json").exists()):
            target = base.with_name(f"{base.stem}__{number}{base.suffix}")
            number += 1
        if not target.resolve().is_relative_to(dest):
            raise ValueError("Export path escapes destination")
        for output in (target, Path(str(target)+".sidecar.json"), Path(str(target)+".source_metadata.json")):
            reserved.add(os.path.normcase(str(output)))
        plan.append((row, target))
    return plan


def export_files(chosen, prof, dest, layout="flat", *, stop=None, progress=None):
    """Copy and verify an explicitly requested export; never mutate the sources."""
    dest = Path(dest).resolve()
    plan = plan_export(chosen, prof, dest, layout)
    dest.mkdir(parents=True, exist_ok=True)
    manifest = []
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    for n, (row, target) in enumerate(plan, 1):
        src = Path(row["path"])
        try:
            if stop and stop():
                raise InterruptedError("Export cancelled")
            if progress:
                progress(n, str(src))
            before = src.stat()
            target.parent.mkdir(parents=True, exist_ok=True)
            h = hashlib.sha256()
            # Exclusive creation also protects files arriving after the preview.
            with src.open("rb") as inp, target.open("xb") as out:
                for chunk in iter(lambda: inp.read(1024 * 1024), b""):
                    if stop and stop():
                        raise InterruptedError("Export cancelled; partial copy requires review")
                    out.write(chunk)
                    h.update(chunk)
            after = src.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise OSError("Source changed during export; copy requires review")
            checksum = h.hexdigest()
            if sha256(str(target)) != checksum:
                raise OSError("Export checksum verification failed")
            shutil.copystat(src, target)
            name = target.relative_to(dest).as_posix()
            level = row["pin"]["level"] if row.get("pin") else guess_level(row)
            status = row["pin"]["status"] if row.get("pin") else guess_status(row)
            sidecar = {
                "schema": "david-os.sidecar/v1",
                "tier1_identity": {"id": f"{prof['code']}-{stamp}-{n:04d}", "exported_as": name,
                    "original_name": src.name, "original_path": str(src), "sha256": checksum,
                    "ext": src.suffix, "size_bytes": before.st_size,
                    "modified": datetime.fromtimestamp(before.st_mtime).isoformat(),
                    "harvested_at": datetime.now().isoformat(timespec="seconds")},
                "tier2_class": {"code": prof['code'], "term": prof['term'], "confidence": row['confidence'],
                    "signals": row['signals'], "classification": row['reclass'] or "unclassified",
                    "level": level, "level_options": LEVELS, "level_source": "pinned" if row.get('pin') else "heuristic"},
                "tier3_placement": {"vault": guess_vault(row), "status": status, "status_options": STATUSES,
                    "status_source": "pinned" if row.get('pin') else "heuristic"},
            }
            # Preserve original metadata separately from the generated export receipt.
            metadata = metadata_text(src)
            if metadata:
                with Path(str(target)+".source_metadata.json").open("x", encoding="utf-8") as stream:
                    json.dump({"original_path": str(src), "source_metadata_text": metadata}, stream, ensure_ascii=False, indent=2)
            with Path(str(target)+".sidecar.json").open("x", encoding="utf-8") as stream:
                json.dump(sidecar, stream, ensure_ascii=False, indent=2)
            manifest.append({"exported_as": name, "confidence": row['confidence'], "level": level,
                             "status": status, "original_path": str(src), "sha256": checksum})
        except (OSError, ValueError) as exc:
            manifest.append({"exported_as": "", "original_path": str(src), "error": str(exc),
                             "attempted_path": str(target)})
    with (dest / f"_harvest_manifest_{stamp}.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["exported_as", "confidence", "level", "status", "original_path", "sha256", "error", "attempted_path"])
        writer.writeheader()
        writer.writerows(manifest)
    return manifest


def main():
    app = QApplication(sys.argv)
    w = Harvester()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
