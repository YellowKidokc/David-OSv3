#!/usr/bin/env python3
"""
Codex Script Hub

A PySide6 launcher for PowerShell, Python, and batch scripts.
It discovers scripts from user-defined roots, groups them by folder,
and provides quick actions for running, opening, pinning, and copying paths.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from PySide6.QtCore import Qt, QProcess, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QFont, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


APP_DIR = Path(__file__).resolve().parent
CONFIG_DIR = APP_DIR / "config"
CONFIG_PATH = CONFIG_DIR / "script_hub.json"
DEFAULT_IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".cache",
    "coverage",
}
SCRIPT_EXTENSIONS = {".ps1", ".py", ".bat", ".cmd"}


@dataclass(frozen=True)
class ScriptEntry:
    path: Path
    root_label: str
    root_path: Path
    rel_dir: str
    extension: str

    @property
    def name(self) -> str:
        return self.path.stem

    @property
    def display_name(self) -> str:
        return self.path.stem.replace("-", " ").replace("_", " ").title()

    @property
    def kind(self) -> str:
        return self.extension.lstrip(".").upper()

    @property
    def folder_label(self) -> str:
        return self.rel_dir or "."


class ScriptHubConfig:
    def __init__(self, path: Path):
        self.path = path
        self.data = self._load()

    def _default_data(self) -> dict:
        roots: List[dict] = []
        seen: set[str] = set()
        for candidate, label in [
            (APP_DIR / "script_dump", "Script Dump"),
            (APP_DIR, "Project Root"),
            (Path(r"D:\DONT TOUCH BOOT UP\organize"), "Organize"),
        ]:
            if candidate.exists():
                resolved = str(candidate.resolve())
                if resolved in seen:
                    continue
                seen.add(resolved)
                roots.append({"label": label, "path": resolved})

        return {
            "roots": roots,
            "pinned": [],
            "filters": {
                "extensions": sorted(SCRIPT_EXTENSIONS),
            },
            "ui": {
                "window_width": 1480,
                "window_height": 920,
                "accent": "#8be9fd",
            },
        }

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass

        data = self._default_data()
        self.save(data)
        return data

    def save(self, data: Optional[dict] = None) -> None:
        if data is not None:
            self.data = data
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    @property
    def roots(self) -> List[dict]:
        return list(self.data.get("roots", []))

    @property
    def pinned(self) -> List[str]:
        return list(self.data.get("pinned", []))

    def add_root(self, label: str, path: str) -> None:
        roots = self.data.setdefault("roots", [])
        normalized = str(Path(path).resolve())
        for root in roots:
            if str(Path(root["path"]).resolve()) == normalized:
                root["label"] = label
                self.save()
                return
        roots.append({"label": label, "path": normalized})
        self.save()

    def remove_root(self, path: str) -> None:
        normalized = str(Path(path).resolve())
        self.data["roots"] = [
            root for root in self.data.get("roots", [])
            if str(Path(root["path"]).resolve()) != normalized
        ]
        self.save()

    def toggle_pin(self, script_path: str) -> None:
        pins = set(self.data.get("pinned", []))
        if script_path in pins:
            pins.remove(script_path)
        else:
            pins.add(script_path)
        self.data["pinned"] = sorted(pins)
        self.save()


class ConsolePane(QPlainTextEdit):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(2500)
        self.setFont(QFont("Consolas", 10))

    def write(self, text: str) -> None:
        self.moveCursor(QTextCursor.End)
        self.insertPlainText(text)
        self.moveCursor(QTextCursor.End)

    def banner(self, text: str) -> None:
        self.write("\n" + "=" * 78 + "\n")
        self.write(text + "\n")
        self.write("=" * 78 + "\n")


class ScriptHub(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = ScriptHubConfig(CONFIG_PATH)
        self.entries: List[ScriptEntry] = []
        self.entries_by_path: Dict[str, ScriptEntry] = {}
        self.current_filter = "all"
        self.current_root_filter = "all"
        self.current_entry: Optional[ScriptEntry] = None
        self._syncing_root_selection = False
        self.process: Optional[QProcess] = None

        self.setWindowTitle("Codex Script Hub")
        ui_cfg = self.config.data.get("ui", {})
        self.resize(ui_cfg.get("window_width", 1480), ui_cfg.get("window_height", 920))
        self._build_ui()
        self._apply_theme()
        self.refresh_library()

        QTimer.singleShot(0, self._show_first_run_hint)

    def _show_first_run_hint(self) -> None:
        if self.config.roots:
            return
        QMessageBox.information(
            self,
            "Add a script root",
            "Use Add Root to point the hub at any folder that contains PowerShell or Python scripts."
        )

    def _apply_theme(self) -> None:
        accent = self.config.data.get("ui", {}).get("accent", "#8be9fd")
        self.setStyleSheet(
            f"""
            QMainWindow {{
                background: #08111f;
            }}
            QWidget {{
                color: #e8eef8;
                font-family: Segoe UI;
                font-size: 11pt;
            }}
            QFrame#panel {{
                background: #101a2d;
                border: 1px solid #1e2a42;
                border-radius: 14px;
            }}
            QFrame#card {{
                background: #0d1728;
                border: 1px solid #20304b;
                border-radius: 12px;
            }}
            QLineEdit, QPlainTextEdit, QComboBox {{
                background: #0c1524;
                border: 1px solid #27405f;
                border-radius: 10px;
                padding: 8px 10px;
                selection-background-color: {accent};
                selection-color: #05131d;
            }}
            QTreeWidget {{
                background: #0b1422;
                border: 1px solid #223552;
                border-radius: 12px;
                alternate-background-color: #0d1828;
            }}
            QTreeWidget::item {{
                padding: 6px 4px;
            }}
            QTreeWidget::item:selected {{
                background: #1b2d47;
                color: #ffffff;
            }}
            QPushButton, QToolButton {{
                background: #17253b;
                border: 1px solid #2a4568;
                border-radius: 10px;
                padding: 8px 12px;
            }}
            QPushButton:hover, QToolButton:hover {{
                background: #20344f;
            }}
            QPushButton:pressed, QToolButton:pressed {{
                background: #132033;
            }}
            QPushButton#accent {{
                background: {accent};
                color: #04131d;
                font-weight: 600;
                border: 1px solid {accent};
            }}
            QLabel#title {{
                font-size: 22px;
                font-weight: 700;
                color: #f5fbff;
            }}
            QLabel#subtitle {{
                color: #99adca;
            }}
            """
        )

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        header = QFrame()
        header.setObjectName("panel")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(12)

        title_block = QVBoxLayout()
        title = QLabel("Codex Script Hub")
        title.setObjectName("title")
        subtitle = QLabel("Launch PowerShell, Python, and helper scripts from any folder you add.")
        subtitle.setObjectName("subtitle")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header_layout.addLayout(title_block, 1)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search scripts, folders, or roots...")
        self.search.textChanged.connect(self.refresh_library)
        self.search.setMinimumWidth(340)
        header_layout.addWidget(self.search, 1)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_library)
        header_layout.addWidget(self.refresh_button)

        self.add_root_button = QPushButton("Add Root")
        self.add_root_button.setObjectName("accent")
        self.add_root_button.clicked.connect(self.add_root_dialog)
        header_layout.addWidget(self.add_root_button)

        outer.addWidget(header)

        filter_bar = QFrame()
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(8)

        self.root_filter = QComboBox()
        self.root_filter.currentIndexChanged.connect(self.refresh_library)
        self.root_filter.setMinimumWidth(280)
        filter_layout.addWidget(self.root_filter)

        self.filter_buttons: Dict[str, QToolButton] = {}
        for key, label in [
            ("all", "All"),
            ("ps1", "PowerShell"),
            ("py", "Python"),
            ("batch", "Batch"),
            ("pinned", "Pinned"),
        ]:
            button = QToolButton()
            button.setText(label)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, k=key: self.set_filter(k))
            self.filter_buttons[key] = button
            filter_layout.addWidget(button)

        self.filter_buttons["all"].setChecked(True)
        filter_layout.addStretch(1)
        outer.addWidget(filter_bar)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_panel = QFrame()
        left_panel.setObjectName("panel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(10)

        left_header = QHBoxLayout()
        left_header.addWidget(QLabel("Roots and Library"))
        left_header.addStretch(1)
        self.root_status = QLabel("")
        self.root_status.setObjectName("subtitle")
        left_header.addWidget(self.root_status)
        left_layout.addLayout(left_header)

        self.root_list = QTreeWidget()
        self.root_list.setHeaderLabels(["Roots"])
        self.root_list.setIndentation(12)
        self.root_list.setAlternatingRowColors(True)
        self.root_list.itemSelectionChanged.connect(self._root_selection_changed)
        self.root_list.itemDoubleClicked.connect(self._open_root_from_item)
        left_layout.addWidget(self.root_list, 1)

        root_buttons = QHBoxLayout()
        self.remove_root_button = QPushButton("Remove Root")
        self.remove_root_button.clicked.connect(self.remove_selected_root)
        self.open_root_button = QPushButton("Open Root")
        self.open_root_button.clicked.connect(self.open_selected_root)
        root_buttons.addWidget(self.remove_root_button)
        root_buttons.addWidget(self.open_root_button)
        left_layout.addLayout(root_buttons)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Script", "Type", "Folder", "Root"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.itemSelectionChanged.connect(self._script_selection_changed)
        self.tree.itemDoubleClicked.connect(self._run_selected_script)
        splitter.addWidget(left_panel)
        splitter.addWidget(self.tree)

        right_panel = QSplitter(Qt.Vertical)
        right_panel.setChildrenCollapsible(False)

        details = QFrame()
        details.setObjectName("card")
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(14, 14, 14, 14)
        details_layout.setSpacing(10)

        self.details_title = QLabel("Select a script")
        self.details_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.details_path = QLabel("Path: -")
        self.details_root = QLabel("Root: -")
        self.details_folder = QLabel("Folder: -")
        self.details_kind = QLabel("Type: -")
        self.details_pin = QLabel("Pinned: no")
        for widget in [
            self.details_title,
            self.details_path,
            self.details_root,
            self.details_folder,
            self.details_kind,
            self.details_pin,
        ]:
            details_layout.addWidget(widget)

        button_row = QHBoxLayout()
        self.run_button = QPushButton("Run")
        self.run_button.setObjectName("accent")
        self.run_button.clicked.connect(self._run_selected_script)
        self.open_button = QPushButton("Open File")
        self.open_button.clicked.connect(self.open_selected_file)
        self.folder_button = QPushButton("Open Folder")
        self.folder_button.clicked.connect(self.open_selected_folder)
        self.copy_button = QPushButton("Copy Path")
        self.copy_button.clicked.connect(self.copy_selected_path)
        self.pin_button = QPushButton("Pin / Unpin")
        self.pin_button.clicked.connect(self.toggle_selected_pin)
        button_row.addWidget(self.run_button)
        button_row.addWidget(self.open_button)
        button_row.addWidget(self.folder_button)
        button_row.addWidget(self.copy_button)
        button_row.addWidget(self.pin_button)
        details_layout.addLayout(button_row)

        right_panel.addWidget(details)

        console_card = QFrame()
        console_card.setObjectName("card")
        console_layout = QVBoxLayout(console_card)
        console_layout.setContentsMargins(14, 14, 14, 14)
        console_layout.setSpacing(10)

        console_header = QHBoxLayout()
        console_header.addWidget(QLabel("Console"))
        console_header.addStretch(1)
        clear_console = QPushButton("Clear")
        clear_console.clicked.connect(lambda: self.console.clear())
        console_header.addWidget(clear_console)
        stop_button = QPushButton("Stop")
        stop_button.clicked.connect(self.stop_process)
        console_header.addWidget(stop_button)
        console_layout.addLayout(console_header)

        self.console = ConsolePane()
        console_layout.addWidget(self.console, 1)
        right_panel.addWidget(console_card)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 2)
        splitter.setSizes([360, 620, 500])
        outer.addWidget(splitter, 1)

        self.statusBar().showMessage("Ready")
        self._build_menu()

    def _build_menu(self) -> None:
        self.menuBar().setNativeMenuBar(False)
        file_menu = self.menuBar().addMenu("File")

        add_root = QAction("Add Root", self)
        add_root.setShortcut(QKeySequence("Ctrl+N"))
        add_root.triggered.connect(self.add_root_dialog)
        file_menu.addAction(add_root)

        refresh = QAction("Refresh", self)
        refresh.setShortcut(QKeySequence("F5"))
        refresh.triggered.connect(self.refresh_library)
        file_menu.addAction(refresh)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def set_filter(self, key: str) -> None:
        self.current_filter = key
        for name, button in self.filter_buttons.items():
            button.setChecked(name == key)
        self.refresh_library()

    def refresh_library(self) -> None:
        self.entries = self._discover_scripts()
        self.entries_by_path = {str(entry.path): entry for entry in self.entries}
        self._populate_root_filter()
        self._syncing_root_selection = True
        self._populate_root_list()
        self._syncing_root_selection = False
        self._populate_tree()
        self._update_summary()
        self.statusBar().showMessage(f"Indexed {len(self.entries)} scripts")

    def _discover_scripts(self) -> List[ScriptEntry]:
        entries: List[ScriptEntry] = []
        search_term = self.search.text().strip().lower()
        for root in self.config.roots:
            root_path = Path(root["path"]).expanduser()
            root_label = root.get("label") or root_path.name
            if not root_path.exists():
                continue
            if root_path.is_file():
                paths = [root_path]
            else:
                paths = self._walk_script_files(root_path)
            for path in paths:
                rel_dir = "."
                try:
                    rel = path.parent.relative_to(root_path)
                    rel_dir = "." if str(rel) == "." else str(rel)
                except Exception:
                    rel_dir = str(path.parent)

                entry = ScriptEntry(
                    path=path.resolve(),
                    root_label=root_label,
                    root_path=root_path.resolve(),
                    rel_dir=rel_dir,
                    extension=path.suffix.lower(),
                )
                if entry.extension not in SCRIPT_EXTENSIONS:
                    continue
                if self._matches_filters(entry, search_term):
                    entries.append(entry)
        entries.sort(key=lambda e: (e.root_label.lower(), e.rel_dir.lower(), e.name.lower(), e.extension))
        return entries

    def _walk_script_files(self, root_path: Path) -> Iterable[Path]:
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [
                d for d in dirnames
                if d not in DEFAULT_IGNORE_DIRS and not d.startswith(".")
            ]
            for filename in filenames:
                candidate = Path(dirpath) / filename
                if candidate.suffix.lower() in SCRIPT_EXTENSIONS:
                    yield candidate

    def _matches_filters(self, entry: ScriptEntry, search_term: str) -> bool:
        if search_term:
            haystacks = [
                str(entry.path).lower(),
                entry.display_name.lower(),
                entry.root_label.lower(),
                entry.folder_label.lower(),
            ]
            if not any(search_term in haystack for haystack in haystacks):
                return False

        if self.current_root_filter != "all" and entry.root_label != self.current_root_filter:
            return False

        if self.current_filter == "pinned" and str(entry.path) not in self.config.pinned:
            return False
        if self.current_filter == "ps1" and entry.extension != ".ps1":
            return False
        if self.current_filter == "py" and entry.extension != ".py":
            return False
        if self.current_filter == "batch" and entry.extension not in {".bat", ".cmd"}:
            return False

        return True

    def _populate_root_filter(self) -> None:
        self.root_filter.blockSignals(True)
        self.root_filter.clear()
        self.root_filter.addItem("All Roots", "all")
        for root in self.config.roots:
            label = root.get("label") or Path(root["path"]).name
            self.root_filter.addItem(f"{label}  ({root['path']})", label)
        index = self.root_filter.findData(self.current_root_filter)
        if index >= 0:
            self.root_filter.setCurrentIndex(index)
        self.root_filter.blockSignals(False)
        selected = self.root_filter.currentData()
        self.current_root_filter = "all" if selected in (None, "all") else str(selected)

    def _populate_root_list(self) -> None:
        self.root_list.clear()
        roots_item = QTreeWidgetItem(["All Roots"])
        roots_item.setData(0, Qt.UserRole, {"path": "all"})
        self.root_list.addTopLevelItem(roots_item)
        counts = self._counts_by_root()
        for root in self.config.roots:
            root_path = Path(root["path"]).expanduser()
            label = root.get("label") or root_path.name
            count = counts.get(label, 0)
            item = QTreeWidgetItem([f"{label}  ({count})"])
            item.setData(0, Qt.UserRole, {"path": str(root_path), "label": label})
            if not root_path.exists():
                item.setForeground(0, self.palette().color(self.palette().Disabled, self.palette().Text))
            self.root_list.addTopLevelItem(item)
        self.root_list.expandAll()
        self.root_status.setText(f"{len(self.config.roots)} roots")
        target_label = None if self.current_root_filter == "all" else self.current_root_filter
        for i in range(self.root_list.topLevelItemCount()):
            item = self.root_list.topLevelItem(i)
            data = item.data(0, Qt.UserRole) or {}
            label = data.get("label")
            if (target_label is None and data.get("path") == "all") or label == target_label:
                self.root_list.setCurrentItem(item)
                break
        if self.root_list.currentItem() is None and self.root_list.topLevelItemCount() > 0:
            self.root_list.setCurrentItem(self.root_list.topLevelItem(0))

    def _counts_by_root(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for entry in self.entries:
            counts[entry.root_label] = counts.get(entry.root_label, 0) + 1
        return counts

    def _populate_tree(self) -> None:
        self.tree.clear()
        grouped: Dict[str, Dict] = {}
        for entry in self.entries:
            grouped.setdefault(entry.root_label, {})
            bucket = grouped[entry.root_label]
            node = bucket
            if entry.rel_dir not in (".", ""):
                for segment in Path(entry.rel_dir).parts:
                    node = node.setdefault(segment, {})
            node.setdefault("__files__", []).append(entry)

        for root in self.config.roots:
            root_path = Path(root["path"]).expanduser()
            label = root.get("label") or root_path.name
            if label not in grouped:
                continue
            root_item = QTreeWidgetItem([label, "", str(root_path), "ROOT"])
            root_item.setExpanded(True)
            self.tree.addTopLevelItem(root_item)
            self._add_group_nodes(root_item, grouped[label], label, root_path)

        self.tree.expandToDepth(1)

    def _add_group_nodes(self, parent_item: QTreeWidgetItem, node: Dict, root_label: str, root_path: Path) -> None:
        for key, value in sorted(node.items(), key=lambda kv: kv[0]):
            if key == "__files__":
                for entry in value:
                    item = QTreeWidgetItem([
                        entry.display_name,
                        entry.kind,
                        entry.folder_label,
                        entry.root_label,
                    ])
                    item.setData(0, Qt.UserRole, str(entry.path))
                    if str(entry.path) in self.config.pinned:
                        item.setText(0, f"* {entry.display_name}")
                    parent_item.addChild(item)
                continue

            folder_item = QTreeWidgetItem([key, "", "", root_label])
            parent_item.addChild(folder_item)
            self._add_group_nodes(folder_item, value, root_label, root_path)

    def _update_summary(self) -> None:
        total = len(self.entries)
        pins = len(self.config.pinned)
        self.root_status.setText(f"{len(self.config.roots)} roots, {total} scripts, {pins} pinned")

    def _root_selection_changed(self) -> None:
        if self._syncing_root_selection:
            return
        item = self.root_list.currentItem()
        if not item:
            return
        data = item.data(0, Qt.UserRole) or {}
        root_path = data.get("path")
        if root_path == "all":
            self.current_root_filter = "all"
        else:
            self.current_root_filter = data.get("label", "all")
        self.root_filter.blockSignals(True)
        if root_path == "all":
            self.root_filter.setCurrentIndex(0)
        else:
            index = self.root_filter.findText(data.get("label", ""))
            if index >= 0:
                self.root_filter.setCurrentIndex(index)
        self.root_filter.blockSignals(False)
        self.refresh_library()

    def _script_selection_changed(self) -> None:
        item = self.tree.currentItem()
        if not item:
            self.current_entry = None
            self._clear_details()
            return
        path = item.data(0, Qt.UserRole)
        if not path or path == "ROOT" or not str(path).lower().endswith(tuple(SCRIPT_EXTENSIONS)):
            self.current_entry = None
            self._clear_details()
            return
        entry = self.entries_by_path.get(str(Path(path).resolve()))
        if not entry:
            self.current_entry = None
            self._clear_details()
            return
        self.current_entry = entry
        self._show_entry(entry)

    def _clear_details(self) -> None:
        self.details_title.setText("Select a script")
        self.details_path.setText("Path: -")
        self.details_root.setText("Root: -")
        self.details_folder.setText("Folder: -")
        self.details_kind.setText("Type: -")
        self.details_pin.setText("Pinned: no")

    def _show_entry(self, entry: ScriptEntry) -> None:
        self.details_title.setText(entry.display_name)
        self.details_path.setText(f"Path: {entry.path}")
        self.details_root.setText(f"Root: {entry.root_label}  ({entry.root_path})")
        self.details_folder.setText(f"Folder: {entry.folder_label}")
        self.details_kind.setText(f"Type: {entry.kind}")
        self.details_pin.setText(f"Pinned: {'yes' if str(entry.path) in self.config.pinned else 'no'}")

    def _run_selected_script(self) -> None:
        if not self.current_entry:
            self.statusBar().showMessage("Pick a script first")
            return
        self.run_script(self.current_entry)

    def run_script(self, entry: ScriptEntry) -> None:
        if self.process and self.process.state() != QProcess.NotRunning:
            QMessageBox.warning(self, "Script running", "A script is already running. Stop it first if you want to start another one.")
            return

        program, args = self._build_command(entry)
        if not program:
            QMessageBox.warning(self, "Unsupported script", f"Cannot launch {entry.extension}")
            return

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)
        self.process.setWorkingDirectory(str(entry.path.parent))

        self.console.banner(f"Running {entry.display_name}")
        self.console.write(f"Program: {program}\n")
        self.console.write(f"Args:    {' '.join(args)}\n")
        self.console.write(f"Folder:  {entry.path.parent}\n\n")
        self.statusBar().showMessage(f"Running {entry.display_name}...")
        self.process.start(program, args)

    def _build_command(self, entry: ScriptEntry) -> tuple[str, List[str]]:
        ext = entry.extension
        path = str(entry.path)
        if ext == ".py":
            return sys.executable, [path]
        if ext == ".ps1":
            shell = shutil.which("pwsh") or shutil.which("powershell") or "powershell.exe"
            return shell, ["-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path]
        if ext in {".bat", ".cmd"}:
            return "cmd.exe", ["/c", path]
        return "", []

    def _read_stdout(self) -> None:
        if not self.process:
            return
        data = bytes(self.process.readAllStandardOutput()).decode(errors="replace")
        if data:
            self.console.write(data)

    def _read_stderr(self) -> None:
        if not self.process:
            return
        data = bytes(self.process.readAllStandardError()).decode(errors="replace")
        if data:
            self.console.write(data)

    def _process_finished(self, exit_code: int, exit_status) -> None:
        self.console.write(f"\n[exit code: {exit_code}]\n")
        self.statusBar().showMessage(f"Finished with exit code {exit_code}")
        self.process = None

    def _process_error(self, error) -> None:
        self.console.write(f"\n[process error: {error}]\n")
        self.statusBar().showMessage("Process error")

    def stop_process(self) -> None:
        if self.process and self.process.state() != QProcess.NotRunning:
            self.process.kill()
            self.console.write("\n[process stopped]\n")

    def _selected_root_data(self) -> Optional[dict]:
        item = self.root_list.currentItem()
        if not item:
            return None
        return item.data(0, Qt.UserRole) or None

    def _open_root_from_item(self, item: QTreeWidgetItem, _column: int) -> None:
        data = item.data(0, Qt.UserRole) or {}
        if data.get("path") and data["path"] != "all":
            self._open_path(Path(data["path"]))

    def open_selected_root(self) -> None:
        data = self._selected_root_data()
        if not data or data.get("path") == "all":
            return
        self._open_path(Path(data["path"]))

    def remove_selected_root(self) -> None:
        data = self._selected_root_data()
        if not data or data.get("path") == "all":
            return
        path = data["path"]
        answer = QMessageBox.question(
            self,
            "Remove root",
            f"Remove root from hub?\n\n{path}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.config.remove_root(path)
            self.refresh_library()

    def add_root_dialog(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose a script root")
        if not chosen:
            return
        default_label = Path(chosen).name
        label, ok = QInputDialog.getText(self, "Label this root", "Root label:", text=default_label)
        if not ok:
            return
        label = label.strip() or default_label
        self.config.add_root(label, chosen)
        self.refresh_library()

    def open_selected_file(self) -> None:
        if self.current_entry:
            self._open_path(self.current_entry.path)

    def open_selected_folder(self) -> None:
        if self.current_entry:
            self._open_path(self.current_entry.path.parent)

    def copy_selected_path(self) -> None:
        if not self.current_entry:
            return
        QApplication.clipboard().setText(str(self.current_entry.path))
        self.statusBar().showMessage("Path copied to clipboard")

    def toggle_selected_pin(self) -> None:
        if not self.current_entry:
            return
        self.config.toggle_pin(str(self.current_entry.path))
        self.refresh_library()
        self._show_entry(self.current_entry)

    def _open_path(self, path: Path) -> None:
        if not path.exists():
            QMessageBox.warning(self, "Missing path", str(path))
            return
        try:
            os.startfile(str(path))
        except Exception:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def closeEvent(self, event) -> None:
        ui = self.config.data.setdefault("ui", {})
        ui["window_width"] = self.width()
        ui["window_height"] = self.height()
        self.config.save()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Codex Script Hub")
    app.setOrganizationName("Codex")
    window = ScriptHub()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
