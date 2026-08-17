#!/usr/bin/env python3
"""
FIS Scanner GUI — PySide6 control panel for File Intelligence System.
D:\\GitHub\\David-OS-v2\\gui\\fis_scanner_gui.py

Run:  python D:\\GitHub\\David-OS-v2\\gui\\fis_scanner_gui.py
Deps: pip install PySide6 --break-system-packages
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
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QSlider, QFileDialog,
    QLineEdit, QListWidget, QListWidgetItem, QGroupBox, QSplitter,
    QTextEdit,
)
from PySide6.QtGui import QFont, QColor

# ── Add engine to path ──────────────────────────
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "engine"))


# ── Lightweight per-file processing ─────────────
# We don't import the full scan() — we build a parallel pipeline
# that calls the engine modules directly.

def _safe_import_engine():
    """Try to import engine modules; fall back to stubs if missing deps."""
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

# ── SQLite setup ────────────────────────────────

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
            keywords TEXT,
            topic_slug TEXT,
            status TEXT DEFAULT 'unclassified',
            sha256 TEXT,
            size_bytes INTEGER,
            modified_at TEXT,
            scanned_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS folders (
            folder_id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            name TEXT NOT NULL,
            file_count INTEGER,
            scanned_at TEXT,
            approved INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    return conn


# ── Per-file processing function ────────────────

SKIP_DIRS = {".git", ".lake", "__pycache__", "node_modules", ".fis", ".obsidian"}
SKIP_EXTS = {".pyc", ".pyo", ".exe", ".dll", ".so", ".dylib"}

def process_one_file(fpath: Path) -> dict:
    """Process a single file: extract text, tag, fingerprint. Thread-safe."""
    name = fpath.name
    ext = fpath.suffix.lower()
    stat = fpath.stat()
    text = ""
    try:
        text = ENGINE["extract_text"](fpath)
    except Exception:
        try:
            if ext in (".md", ".txt", ".html", ".json", ".csv", ".lean", ".py"):
                text = fpath.read_text(errors="replace")[:50_000]
        except Exception:
            pass

    tags = ENGINE["extract_tags"](name, text)
    slug = ENGINE["topic_slug"](name)
    sha = ENGINE["sha256_file"](fpath)
    fid = f"FIL-{sha[:12]}"

    return {
        "file_id": fid,
        "path": str(fpath),
        "folder_path": str(fpath.parent),
        "name": name,
        "format": ext.lstrip(".") or "unknown",
        "domain": "",
        "keywords": ",".join(tags),
        "topic_slug": slug,
        "sha256": sha,
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "scanned_at": datetime.now().isoformat(),
    }

def walk_tree(root: Path):
    """Yield all scannable files under root."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        dp = Path(dirpath)
        for fn in filenames:
            fp = dp / fn
            if fp.suffix.lower() in SKIP_EXTS:
                continue
            if fn.startswith(".fisnote"):
                continue
            yield fp


# ── Scanner thread ──────────────────────────────

class ScanWorker(QThread):
    progress = Signal(int, int, str)      # done, total, current_file
    file_done = Signal(str, str)          # filename, tags
    folder_done = Signal(str)             # folder path
    scan_complete = Signal(int, float)    # total_files, elapsed_seconds
    error = Signal(str)

    def __init__(self, root: Path, db_path: Path, workers: int = 4):
        super().__init__()
        self.root = root
        self.db_path = db_path
        self.workers = max(1, workers)
        self._stop = False
        self._pause = False

    def stop(self):
        self._stop = True

    def pause(self):
        self._pause = not self._pause

    def run(self):
        t0 = time.time()
        try:
            conn = init_db(self.db_path)
            # Phase 1: walk
            all_files = list(walk_tree(self.root))
            total = len(all_files)
            if total == 0:
                self.scan_complete.emit(0, 0.0)
                return

            done = 0
            folders_seen = set()

            # Phase 2: parallel process
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                futures = {pool.submit(process_one_file, fp): fp for fp in all_files}
                for future in as_completed(futures):
                    if self._stop:
                        pool.shutdown(wait=False, cancel_futures=True)
                        return
                    while self._pause:
                        time.sleep(0.2)
                        if self._stop:
                            return

                    fp = futures[future]
                    try:
                        result = future.result()
                        # Write to SQLite
                        conn.execute("""
                            INSERT OR REPLACE INTO files
                            (file_id, path, folder_path, name, format, domain,
                             keywords, topic_slug, sha256, size_bytes,
                             modified_at, scanned_at)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            result["file_id"], result["path"],
                            result["folder_path"], result["name"],
                            result["format"], result["domain"],
                            result["keywords"], result["topic_slug"],
                            result["sha256"], result["size_bytes"],
                            result["modified_at"], result["scanned_at"],
                        ))

                        # Track folders
                        folder = result["folder_path"]
                        if folder not in folders_seen:
                            folders_seen.add(folder)
                            self.folder_done.emit(folder)

                        done += 1
                        self.progress.emit(done, total, result["name"])
                        self.file_done.emit(
                            result["name"],
                            result["keywords"] or result["topic_slug"]
                        )

                        # Commit every 50 files
                        if done % 50 == 0:
                            conn.commit()

                    except Exception as e:
                        done += 1
                        self.progress.emit(done, total, f"ERROR: {fp.name}")
                        self.error.emit(f"{fp.name}: {e}")

            conn.commit()

            # Phase 3: record folders
            for folder in folders_seen:
                fp = Path(folder)
                count = len([f for f in all_files if str(f).startswith(folder)])
                conn.execute("""
                    INSERT OR REPLACE INTO folders
                    (folder_id, path, name, file_count, scanned_at)
                    VALUES (?,?,?,?,?)
                """, (
                    f"FOL-{hashlib.md5(folder.encode()).hexdigest()[:12]}",
                    folder, fp.name, count, datetime.now().isoformat(),
                ))
            conn.commit()
            conn.close()

            elapsed = time.time() - t0
            self.scan_complete.emit(total, elapsed)

        except Exception as e:
            self.error.emit(str(e))


# ── Main Window ─────────────────────────────────

class FISScannerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FIS Scanner — David-OS v2")
        self.setMinimumSize(700, 750)
        self.worker: Optional[ScanWorker] = None
        self._start_time = 0.0

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)

        # ── Target folder ───────────────────
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Target Folder:"))
        self.folder_input = QLineEdit(r"H:\Desktop")
        self.folder_input.setMinimumWidth(350)
        folder_row.addWidget(self.folder_input)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse)
        folder_row.addWidget(browse_btn)
        layout.addLayout(folder_row)

        # ── Speed slider ────────────────────
        speed_box = QGroupBox("Speed (concurrent workers)")
        speed_lay = QHBoxLayout(speed_box)
        self.speed_label = QLabel("4")
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, os.cpu_count() or 8)
        self.speed_slider.setValue(4)
        self.speed_slider.valueChanged.connect(
            lambda v: self.speed_label.setText(str(v))
        )
        speed_lay.addWidget(QLabel("1"))
        speed_lay.addWidget(self.speed_slider)
        speed_lay.addWidget(QLabel(str(os.cpu_count() or 8)))
        speed_lay.addWidget(QLabel("  Current:"))
        speed_lay.addWidget(self.speed_label)
        layout.addWidget(speed_box)

        # ── Controls ────────────────────────
        ctrl_row = QHBoxLayout()
        self.start_btn = QPushButton("START")
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

        # ── Progress ────────────────────────
        prog_box = QGroupBox("Progress")
        prog_lay = QVBoxLayout(prog_box)
        self.progress_bar = QProgressBar()
        prog_lay.addWidget(self.progress_bar)
        self.progress_label = QLabel("Ready")
        prog_lay.addWidget(self.progress_label)
        self.stats_label = QLabel("")
        prog_lay.addWidget(self.stats_label)
        layout.addWidget(prog_box)

        # ── Recent files ────────────────────
        recent_box = QGroupBox("Recent")
        recent_lay = QVBoxLayout(recent_box)
        self.recent_list = QListWidget()
        self.recent_list.setMaximumHeight(150)
        self.recent_list.setFont(QFont("Consolas", 9))
        recent_lay.addWidget(self.recent_list)
        layout.addWidget(recent_box)


        # ── Folders with FIS pages ──────────
        fis_box = QGroupBox("FIS Pages (click to open)")
        fis_lay = QVBoxLayout(fis_box)
        self.fis_list = QListWidget()
        self.fis_list.setMaximumHeight(120)
        self.fis_list.itemDoubleClicked.connect(self._open_fis)
        fis_lay.addWidget(self.fis_list)
        layout.addWidget(fis_box)

        # ── SQLite info ─────────────────────
        self.db_label = QLabel("DB: —")
        layout.addWidget(self.db_label)

        # ── Errors ──────────────────────────
        self.error_box = QTextEdit()
        self.error_box.setMaximumHeight(80)
        self.error_box.setReadOnly(True)
        self.error_box.setVisible(False)
        layout.addWidget(self.error_box)

    # ── Slots ───────────────────────────────

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Select folder to scan")
        if d:
            self.folder_input.setText(d)

    def _start(self):
        root = Path(self.folder_input.text())
        if not root.is_dir():
            self.progress_label.setText(f"Not a directory: {root}")
            return

        db_path = root / ".fis" / "fis_index.sqlite"
        workers = self.speed_slider.value()

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
        self.recent_list.clear()
        self.fis_list.clear()
        self.error_box.clear()
        self.error_box.setVisible(False)
        self.db_label.setText(f"DB: {db_path}")
        self._start_time = time.time()

        self.worker.start()

    def _pause(self):
        if self.worker:
            self.worker.pause()
            paused = self.worker._pause
            self.pause_btn.setText("RESUME" if paused else "PAUSE")

    def _stop(self):
        if self.worker:
            self.worker.stop()
            self.start_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.progress_label.setText("Stopped by user")

    def _on_progress(self, done: int, total: int, current: str):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(done)
        elapsed = time.time() - self._start_time
        if done > 0:
            rate = elapsed / done
            remaining = rate * (total - done)
            elapsed_str = time.strftime("%H:%M:%S", time.gmtime(elapsed))
            remain_str = time.strftime("%H:%M:%S", time.gmtime(remaining))
        else:
            elapsed_str = "00:00:00"
            remain_str = "—"
        self.progress_label.setText(f"{done:,} / {total:,}  │  {current}")
        self.stats_label.setText(
            f"Elapsed: {elapsed_str}  │  Remaining: {remain_str}  │  "
            f"Rate: {done / max(elapsed, 0.1):.0f} files/sec"
        )

    def _on_file_done(self, name: str, tags: str):
        item = QListWidgetItem(f"✓ {name}  →  {tags}")
        self.recent_list.insertItem(0, item)
        if self.recent_list.count() > 50:
            self.recent_list.takeItem(50)

    def _on_folder_done(self, folder: str):
        item = QListWidgetItem(f"📁 {folder}")
        self.fis_list.addItem(item)

    def _open_fis(self, item: QListWidgetItem):
        folder = item.text().replace("📁 ", "")
        fis_html = Path(folder) / "FIS.html"
        if fis_html.exists():
            webbrowser.open(str(fis_html))
        else:
            webbrowser.open(str(folder))

    def _on_complete(self, total: int, elapsed: float):
        elapsed_str = time.strftime("%H:%M:%S", time.gmtime(elapsed))
        self.progress_label.setText(
            f"DONE — {total:,} files in {elapsed_str}"
        )
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        # Update DB size
        db_path = Path(self.folder_input.text()) / ".fis" / "fis_index.sqlite"
        if db_path.exists():
            size_mb = db_path.stat().st_size / (1024 * 1024)
            self.db_label.setText(
                f"DB: {db_path}  │  Records: {total:,}  │  Size: {size_mb:.1f} MB"
            )

    def _on_error(self, msg: str):
        self.error_box.setVisible(True)
        self.error_box.append(msg)


# ── Entry point ─────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # Dark palette
    from PySide6.QtGui import QPalette
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
