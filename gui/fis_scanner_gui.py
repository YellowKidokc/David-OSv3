#!/usr/bin/env python3
"""
FIS Scanner GUI v2 — PySide6 control panel for File Intelligence System.
D:\\GitHub\\David-OSv3\\gui\\fis_scanner_gui.py

Run:  python D:\\GitHub\\David-OSv3\\gui\\fis_scanner_gui.py
Deps: pip install PySide6 --break-system-packages

Features:
 - Scan any folder (local or network drive)
 - Multi-tag support (semantic, domain, series, format tags)
 - Speed slider (1 → max cores)
 - SQLite database location picker (default Z:\\.fis\\fis_master.sqlite)
 - Multi-folder aggregate view (scan multiple folders into one DB)
 - FIS.html links with browser open
 - Live progress, rate, ETA
"""
from __future__ import annotations

import os
import sys
import time
import sqlite3
import hashlib
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QSlider, QFileDialog,
    QLineEdit, QListWidget, QListWidgetItem, QGroupBox,
    QTextEdit, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox,
)
from PySide6.QtGui import QFont, QColor, QPalette

# ── Add engine to path ──────────────────────────
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "engine"))

# ── Lightweight engine imports with fallbacks ────

def _safe_import_engine():
    mods = {}
    try:
        from tagger import extract_tags, topic_slug
        mods["extract_tags"] = extract_tags
        mods["topic_slug"] = topic_slug
    except Exception:
        mods["extract_tags"] = lambda n, t="", **kw: []
        mods["topic_slug"] = lambda n, **kw: Path(n).stem.lower()[:30]
    try:
        from text_extractor import extract_text
        mods["extract_text"] = extract_text
    except Exception:
        mods["extract_text"] = lambda p: ""
    try:
        from fingerprint import sha256_file
        mods["sha256_file"] = sha256_file
    except Exception:
        def _sha(p):
            h = hashlib.sha256()
            try:
                with open(p, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        h.update(chunk)
            except Exception:
                return "ERROR"
            return h.hexdigest()
        mods["sha256_file"] = _sha
    return mods

ENGINE = _safe_import_engine()

# ── Extended tag tables ─────────────────────────
# Multiple tag layers so near-misses still find the file

SEMANTIC_TAGS = [
    (["consciousness","aware","sentien","mirror","phenomenal"], "consciousness"),
    (["coherence","coher","decoher"], "coherence"),
    (["grace","agape","shalom","charis"], "grace"),
    (["entropy","disorder","decay","thermodynamic"], "entropy"),
    (["moral","virtue","fruit","ethical"], "moral"),
    (["faith","belief","trust","pistis"], "faith"),
    (["quantum","superposit","wavefunction","measurement"], "quantum"),
    (["logos","scripture","gospel","word"], "logos"),
    (["trinity","triune","perichoresis","father son spirit"], "trinity"),
    (["axiom","foundational","primitive","postulate"], "axiom"),
    (["proof","theorem","lemma","qed","lean"], "proof"),
    (["isomorphism","isomorphic","functor","transport"], "isomorphism"),
    (["watcher","observer","von neumann","measurement problem"], "watcher"),
    (["master equation","chi","χ"], "master-equation"),
    (["identity","personhood","person","haecceity"], "identity"),
    (["law 1","gravitation","sin","curvature"], "law-1"),
    (["law 2","motion","force","will"], "law-2"),
    (["law 3","electromagnetism","truth","deception"], "law-3"),
    (["law 4","strong force","love","captivity"], "law-4"),
    (["law 5","thermodynamics","judgment","justice","mercy"], "law-5"),
    (["law 6","information","shannon","chaos"], "law-6"),
    (["law 7","quantum","faith","doubt"], "law-7"),
    (["law 8","relativity","grace","frame"], "law-8"),
    (["law 9","weak force","moral conservation","noether"], "law-9"),
    (["law 10","coherence","christ","kingdom"], "law-10"),
    (["hawking","brief history","cosmology"], "hawking"),
    (["principia","moralia","pmm"], "principia"),
    (["cantor","diagonal","uncountable"], "cantor"),
    (["gödel","incompleteness","undecidable"], "godel"),
    (["tarski","definability","truth predicate"], "tarski"),
]

FORMAT_TAGS = {
    ".md": "markdown", ".html": "html", ".json": "json", ".csv": "csv",
    ".py": "python", ".lean": "lean4", ".js": "javascript", ".ts": "typescript",
    ".pdf": "pdf", ".docx": "word", ".xlsx": "excel", ".pptx": "powerpoint",
    ".png": "image", ".jpg": "image", ".svg": "svg", ".mp3": "audio",
    ".mp4": "video", ".txt": "text", ".yaml": "yaml", ".toml": "toml",
}

def multi_tag(name: str, text: str = "", ext: str = "") -> dict:
    """Return multiple tag layers for a file."""
    blob = (name + " " + (text or ""))[:50_000].lower()
    # Semantic tags (all matches, not just first 3)
    semantic = [tag for keywords, tag in SEMANTIC_TAGS
                if any(k in blob for k in keywords)]
    # Engine tags (compressed codes)
    engine_tags = ENGINE["extract_tags"](name, text, max_tags=5)
    # Format tag
    fmt = FORMAT_TAGS.get(ext.lower(), "other")
    # Topic slug
    slug = ENGINE["topic_slug"](name)
    return {
        "semantic": semantic,
        "engine": engine_tags,
        "format": fmt,
        "slug": slug,
        "all_tags": ",".join(set(semantic + engine_tags + [fmt])),
    }

# ── SQLite setup (expanded schema) ──────────────

def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            file_id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            folder_path TEXT NOT NULL,
            name TEXT NOT NULL,
            format TEXT,
            domain TEXT,
            semantic_tags TEXT,
            engine_tags TEXT,
            format_tag TEXT,
            topic_slug TEXT,
            all_tags TEXT,
            status TEXT DEFAULT 'unclassified',
            sha256 TEXT,
            size_bytes INTEGER,
            modified_at TEXT,
            scanned_at TEXT,
            scan_source TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS folders (
            folder_id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            name TEXT NOT NULL,
            file_count INTEGER,
            scanned_at TEXT,
            scan_source TEXT,
            approved INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_all_tags ON files(all_tags)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_folder ON files(folder_path)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_scan_source ON files(scan_source)")
    conn.commit()
    return conn

# ── Per-file processing ─────────────────────────

SKIP_DIRS = {".git", ".lake", "__pycache__", "node_modules", ".fis", ".obsidian"}
SKIP_EXTS = {".pyc", ".pyo", ".exe", ".dll", ".so", ".dylib"}

def process_one_file(fpath: Path, scan_source: str = "") -> dict:
    name = fpath.name
    ext = fpath.suffix.lower()
    stat = fpath.stat()
    text = ""
    try:
        text = ENGINE["extract_text"](fpath)
    except Exception:
        try:
            if ext in (".md",".txt",".html",".json",".csv",".lean",".py",".js",".ts",".yaml",".toml"):
                text = fpath.read_text(errors="replace")[:50_000]
        except Exception:
            pass

    tags = multi_tag(name, text, ext)
    sha = ENGINE["sha256_file"](fpath)
    fid = f"FIL-{sha[:12]}"

    return {
        "file_id": fid, "path": str(fpath), "folder_path": str(fpath.parent),
        "name": name, "format": ext.lstrip(".") or "unknown", "domain": "",
        "semantic_tags": ",".join(tags["semantic"]),
        "engine_tags": ",".join(tags["engine"]),
        "format_tag": tags["format"], "topic_slug": tags["slug"],
        "all_tags": tags["all_tags"], "sha256": sha,
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "scanned_at": datetime.now().isoformat(),
        "scan_source": scan_source,
    }

def walk_tree(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        dp = Path(dirpath)
        for fn in filenames:
            fp = dp / fn
            if fp.suffix.lower() in SKIP_EXTS or fn.startswith(".fisnote"):
                continue
            yield fp

# ── Scanner thread ──────────────────────────────

class ScanWorker(QThread):
    progress = Signal(int, int, str)
    file_done = Signal(str, str)
    folder_done = Signal(str)
    scan_complete = Signal(int, float)
    error = Signal(str)

    def __init__(self, root: Path, db_path: Path, workers: int = 4):
        super().__init__()
        self.root = root
        self.db_path = db_path
        self.workers = max(1, workers)
        self._stop = False
        self._pause = False

    def stop(self): self._stop = True
    def pause(self): self._pause = not self._pause

    def run(self):
        t0 = time.time()
        source = str(self.root)
        try:
            conn = init_db(self.db_path)
            all_files = list(walk_tree(self.root))
            total = len(all_files)
            if total == 0:
                self.scan_complete.emit(0, 0.0)
                return
            done = 0
            folders_seen = set()

            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                futures = {pool.submit(process_one_file, fp, source): fp for fp in all_files}
                for future in as_completed(futures):
                    if self._stop:
                        pool.shutdown(wait=False, cancel_futures=True)
                        return
                    while self._pause:
                        time.sleep(0.2)
                        if self._stop: return

                    fp = futures[future]
                    try:
                        r = future.result()
                        conn.execute("""
                            INSERT OR REPLACE INTO files
                            (file_id,path,folder_path,name,format,domain,
                             semantic_tags,engine_tags,format_tag,topic_slug,
                             all_tags,sha256,size_bytes,modified_at,scanned_at,scan_source)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (r["file_id"],r["path"],r["folder_path"],r["name"],
                              r["format"],r["domain"],r["semantic_tags"],
                              r["engine_tags"],r["format_tag"],r["topic_slug"],
                              r["all_tags"],r["sha256"],r["size_bytes"],
                              r["modified_at"],r["scanned_at"],r["scan_source"]))
                        folder = r["folder_path"]
                        if folder not in folders_seen:
                            folders_seen.add(folder)
                            self.folder_done.emit(folder)
                        done += 1
                        self.progress.emit(done, total, r["name"])
                        self.file_done.emit(r["name"], r["all_tags"])
                        if done % 50 == 0: conn.commit()
                    except Exception as e:
                        done += 1
                        self.progress.emit(done, total, f"ERROR: {fp.name}")
                        self.error.emit(f"{fp.name}: {e}")

            conn.commit()
            for folder in folders_seen:
                fp = Path(folder)
                count = sum(1 for f in all_files if str(f.parent) == folder)
                conn.execute("""
                    INSERT OR REPLACE INTO folders
                    (folder_id,path,name,file_count,scanned_at,scan_source)
                    VALUES (?,?,?,?,?,?)
                """, (f"FOL-{hashlib.md5(folder.encode()).hexdigest()[:12]}",
                      folder, fp.name, count, datetime.now().isoformat(), source))
            conn.commit()
            conn.close()
            self.scan_complete.emit(total, time.time() - t0)
        except Exception as e:
            self.error.emit(str(e))

# ── Main Window with Tabs ───────────────────────

class FISScannerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FIS Scanner v2 — David-OS v3")
        self.setMinimumSize(800, 800)
        self.worker: Optional[ScanWorker] = None
        self._start_time = 0.0
        self._scan_folders: List[str] = []

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        tabs = QTabWidget()
        main_layout.addWidget(tabs)

        # ═══ TAB 1: SCANNER ═══════════════════
        scan_tab = QWidget()
        layout = QVBoxLayout(scan_tab)
        layout.setSpacing(8)

        # Target folders (multi-folder support)
        folder_box = QGroupBox("Scan Targets (one per line, or browse)")
        folder_lay = QVBoxLayout(folder_box)
        self.folder_input = QTextEdit()
        self.folder_input.setMaximumHeight(80)
        self.folder_input.setPlainText("H:\\Desktop")
        self.folder_input.setFont(QFont("Consolas", 10))
        folder_lay.addWidget(self.folder_input)
        browse_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Folder")
        add_btn.clicked.connect(self._browse_add)
        browse_row.addWidget(add_btn)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(lambda: self.folder_input.clear())
        browse_row.addWidget(clear_btn)
        browse_row.addStretch()
        folder_lay.addLayout(browse_row)
        layout.addWidget(folder_box)

        # SQLite location
        db_row = QHBoxLayout()
        db_row.addWidget(QLabel("SQLite DB:"))
        self.db_input = QLineEdit(r"Z:\.fis\fis_master.sqlite")
        self.db_input.setMinimumWidth(350)
        db_row.addWidget(self.db_input)
        db_browse = QPushButton("Browse")
        db_browse.clicked.connect(self._browse_db)
        db_row.addWidget(db_browse)
        layout.addLayout(db_row)

        # Speed slider
        speed_box = QGroupBox("Speed (concurrent workers)")
        speed_lay = QHBoxLayout(speed_box)
        self.speed_label = QLabel("4")
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, os.cpu_count() or 8)
        self.speed_slider.setValue(4)
        self.speed_slider.valueChanged.connect(lambda v: self.speed_label.setText(str(v)))
        speed_lay.addWidget(QLabel("1"))
        speed_lay.addWidget(self.speed_slider)
        speed_lay.addWidget(QLabel(str(os.cpu_count() or 8)))
        speed_lay.addWidget(QLabel("  Workers:"))
        speed_lay.addWidget(self.speed_label)
        layout.addWidget(speed_box)

        # Controls
        ctrl_row = QHBoxLayout()
        self.start_btn = QPushButton("START SCAN")
        self.start_btn.setStyleSheet("background:#2d7d46;color:white;font-weight:bold;padding:8px 24px")
        self.start_btn.clicked.connect(self._start)
        ctrl_row.addWidget(self.start_btn)
        self.pause_btn = QPushButton("PAUSE")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._pause)
        ctrl_row.addWidget(self.pause_btn)
        self.stop_btn = QPushButton("STOP")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background:#8b2020;color:white;padding:8px 24px")
        self.stop_btn.clicked.connect(self._stop)
        ctrl_row.addWidget(self.stop_btn)
        layout.addLayout(ctrl_row)

        # Progress
        prog_box = QGroupBox("Progress")
        prog_lay = QVBoxLayout(prog_box)
        self.progress_bar = QProgressBar()
        prog_lay.addWidget(self.progress_bar)
        self.progress_label = QLabel("Ready")
        prog_lay.addWidget(self.progress_label)
        self.stats_label = QLabel("")
        prog_lay.addWidget(self.stats_label)
        layout.addWidget(prog_box)

        # Recent files
        recent_box = QGroupBox("Recent")
        recent_lay = QVBoxLayout(recent_box)
        self.recent_list = QListWidget()
        self.recent_list.setMaximumHeight(120)
        self.recent_list.setFont(QFont("Consolas", 9))
        recent_lay.addWidget(self.recent_list)
        layout.addWidget(recent_box)

        # FIS pages
        fis_box = QGroupBox("FIS Pages (double-click to open)")
        fis_lay = QVBoxLayout(fis_box)
        self.fis_list = QListWidget()
        self.fis_list.setMaximumHeight(100)
        self.fis_list.itemDoubleClicked.connect(self._open_fis)
        fis_lay.addWidget(self.fis_list)
        layout.addWidget(fis_box)

        self.db_label = QLabel("DB: —")
        layout.addWidget(self.db_label)

        self.error_box = QTextEdit()
        self.error_box.setMaximumHeight(60)
        self.error_box.setReadOnly(True)
        self.error_box.setVisible(False)
        layout.addWidget(self.error_box)

        tabs.addTab(scan_tab, "Scanner")

        # ═══ TAB 2: AGGREGATE VIEW ═══════════
        agg_tab = QWidget()
        agg_layout = QVBoxLayout(agg_tab)

        agg_ctrl = QHBoxLayout()
        agg_ctrl.addWidget(QLabel("DB:"))
        self.agg_db_input = QLineEdit(r"Z:\.fis\fis_master.sqlite")
        agg_ctrl.addWidget(self.agg_db_input)
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self._load_aggregate)
        agg_ctrl.addWidget(load_btn)
        agg_layout.addLayout(agg_ctrl)

        # Filter
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter tags:"))
        self.tag_filter = QLineEdit()
        self.tag_filter.setPlaceholderText("e.g. grace, quantum, lean4")
        self.tag_filter.returnPressed.connect(self._filter_aggregate)
        filter_row.addWidget(self.tag_filter)
        filter_btn = QPushButton("Search")
        filter_btn.clicked.connect(self._filter_aggregate)
        filter_row.addWidget(filter_btn)
        agg_layout.addLayout(filter_row)

        # Stats row
        self.agg_stats = QLabel("")
        agg_layout.addWidget(self.agg_stats)

        # Results table
        self.agg_table = QTableWidget()
        self.agg_table.setColumnCount(6)
        self.agg_table.setHorizontalHeaderLabels(
            ["Name", "Folder", "Format", "Semantic Tags", "Engine Tags", "Slug"])
        self.agg_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.agg_table.setAlternatingRowColors(True)
        self.agg_table.setFont(QFont("Consolas", 9))
        agg_layout.addWidget(self.agg_table)

        # Folder breakdown
        self.folder_breakdown = QListWidget()
        self.folder_breakdown.setMaximumHeight(120)
        agg_layout.addWidget(QLabel("Folders scanned:"))
        agg_layout.addWidget(self.folder_breakdown)

        tabs.addTab(agg_tab, "Aggregate View")

    # ── Scanner Slots ───────────────────────

    def _browse_add(self):
        d = QFileDialog.getExistingDirectory(self, "Add folder to scan")
        if d:
            current = self.folder_input.toPlainText().strip()
            if current:
                self.folder_input.setPlainText(current + "\n" + d)
            else:
                self.folder_input.setPlainText(d)

    def _browse_db(self):
        f, _ = QFileDialog.getSaveFileName(self, "SQLite location", "", "SQLite (*.sqlite *.db)")
        if f:
            self.db_input.setText(f)

    def _start(self):
        lines = self.folder_input.toPlainText().strip().splitlines()
        roots = [Path(l.strip()) for l in lines if l.strip()]
        roots = [r for r in roots if r.is_dir()]
        if not roots:
            self.progress_label.setText("No valid directories found")
            return

        db_path = Path(self.db_input.text())
        workers = self.speed_slider.value()
        self._scan_folders = [str(r) for r in roots]

        # Scan first folder, queue the rest
        self._remaining_roots = list(roots[1:])
        self._current_db = db_path
        self._current_workers = workers
        self._start_one(roots[0], db_path, workers)

    def _start_one(self, root: Path, db_path: Path, workers: int):
        self.worker = ScanWorker(root, db_path, workers)
        self.worker.progress.connect(self._on_progress)
        self.worker.file_done.connect(self._on_file_done)
        self.worker.folder_done.connect(self._on_folder_done)
        self.worker.scan_complete.connect(self._on_complete)
        self.worker.error.connect(self._on_error)
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.db_label.setText(f"DB: {db_path}  |  Scanning: {root}")
        self._start_time = time.time()
        self.worker.start()

    def _pause(self):
        if self.worker:
            self.worker.pause()
            self.pause_btn.setText("RESUME" if self.worker._pause else "PAUSE")

    def _stop(self):
        if self.worker:
            self.worker.stop()
        self._remaining_roots.clear()
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.progress_label.setText("Stopped")

    def _on_progress(self, done, total, current):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(done)
        elapsed = time.time() - self._start_time
        rate = done / max(elapsed, 0.1)
        remaining = (total - done) / max(rate, 0.01)
        self.progress_label.setText(f"{done:,} / {total:,}  |  {current}")
        self.stats_label.setText(
            f"Elapsed: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}  |  "
            f"Remaining: {time.strftime('%H:%M:%S', time.gmtime(remaining))}  |  "
            f"Rate: {rate:.0f} files/sec")

    def _on_file_done(self, name, tags):
        item = QListWidgetItem(f"✓ {name}  →  {tags}")
        self.recent_list.insertItem(0, item)
        if self.recent_list.count() > 50:
            self.recent_list.takeItem(50)

    def _on_folder_done(self, folder):
        self.fis_list.addItem(QListWidgetItem(f"📁 {folder}"))

    def _open_fis(self, item):
        folder = item.text().replace("📁 ", "")
        fis = Path(folder) / "FIS.html"
        webbrowser.open(str(fis) if fis.exists() else str(folder))

    def _on_complete(self, total, elapsed):
        # Check for more folders to scan
        if self._remaining_roots:
            nxt = self._remaining_roots.pop(0)
            self.progress_label.setText(f"Done with previous. Starting: {nxt}")
            self._start_one(nxt, self._current_db, self._current_workers)
            return
        self.progress_label.setText(f"ALL DONE — {total:,} files in {time.strftime('%H:%M:%S', time.gmtime(elapsed))}")
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        db = Path(self.db_input.text())
        if db.exists():
            sz = db.stat().st_size / (1024*1024)
            self.db_label.setText(f"DB: {db}  |  Size: {sz:.1f} MB")

    def _on_error(self, msg):
        self.error_box.setVisible(True)
        self.error_box.append(msg)

    # ── Aggregate Tab Slots ─────────────────

    def _load_aggregate(self):
        db = Path(self.agg_db_input.text())
        if not db.exists():
            self.agg_stats.setText(f"DB not found: {db}")
            return
        self._show_aggregate(db)

    def _filter_aggregate(self):
        db = Path(self.agg_db_input.text())
        if not db.exists():
            return
        filt = self.tag_filter.text().strip()
        self._show_aggregate(db, filt)

    def _show_aggregate(self, db: Path, tag_filter: str = ""):
        conn = sqlite3.connect(str(db))
        if tag_filter:
            terms = [t.strip() for t in tag_filter.split(",") if t.strip()]
            where = " AND ".join(f"all_tags LIKE '%{t}%'" for t in terms)
            rows = conn.execute(
                f"SELECT name,folder_path,format,semantic_tags,engine_tags,topic_slug FROM files WHERE {where} ORDER BY name"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT name,folder_path,format,semantic_tags,engine_tags,topic_slug FROM files ORDER BY folder_path,name"
            ).fetchall()

        self.agg_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                self.agg_table.setItem(i, j, QTableWidgetItem(str(val or "")))

        # Folder breakdown
        folders = conn.execute(
            "SELECT path, file_count, scan_source FROM folders ORDER BY path"
        ).fetchall()
        self.folder_breakdown.clear()
        total_files = 0
        for path, count, source in folders:
            count = count or 0
            total_files += count
            self.folder_breakdown.addItem(f"{path}  ({count} files)")

        self.agg_stats.setText(
            f"Total files: {len(rows):,}  |  "
            f"Folders: {len(folders)}  |  "
            f"DB size: {db.stat().st_size / (1024*1024):.1f} MB"
            + (f"  |  Filter: {tag_filter}" if tag_filter else "")
        )
        conn.close()


# ── Entry point ─────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.WindowText, QColor(210, 210, 210))
    palette.setColor(QPalette.Base, QColor(20, 20, 20))
    palette.setColor(QPalette.AlternateBase, QColor(40, 40, 40))
    palette.setColor(QPalette.Text, QColor(210, 210, 210))
    palette.setColor(QPalette.Button, QColor(45, 45, 45))
    palette.setColor(QPalette.ButtonText, QColor(210, 210, 210))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)
    win = FISScannerWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
