#!/usr/bin/env python3
"""Axiom Search & Export — David-OS v3 GUI.

Search, filter, inspect, and export axioms from the FIS registry.
Reads fis_folder_memory.sqlite (read-only). Exports to JSON / CSV / Markdown.

Run:  python D:\\GitHub\\David-OSv3\\gui\\axiom_search_export.py
Deps: pip install PySide6 --break-system-packages
"""
from __future__ import annotations

import csv
import json
import os
import sqlite3
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QSortFilterProxyModel, Signal, Slot
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
    QPushButton, QSlider, QSplitter, QStatusBar, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

# ── Paths ──────────────────────────────────────────────
REPO = Path(__file__).resolve().parents[1] if Path(__file__).resolve().parents[1].name == "David-OSv3" else Path(__file__).resolve().parent
FIS_DIR = REPO / "file-intelligence-system"
REGISTRY_DB = FIS_DIR / "fis_folder_memory.sqlite"

# Fallback if running from a different location
if not REGISTRY_DB.exists():
    for candidate in [
        Path(r"D:\GitHub\David-OSv3\file-intelligence-system\fis_folder_memory.sqlite"),
        Path(r"D:\GitHub\David-OS\file-intelligence-system\fis_folder_memory.sqlite"),
    ]:
        if candidate.exists():
            REGISTRY_DB = candidate
            break

# ── Colors — Consilience Atlas palette ─────────────────
VOID = "#050505"
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
GREEN_DIM = "#3a6b3a"

# ── Doc types with glyphs ─────────────────────────────
DOC_GLYPHS = {
    "AXIOM": "Α",
    "CANON": "☉",
    "DERIVATION": "⟐",
    "NARRATIVE": "✍",
    "BRIDGE": "≅",
    "EVIDENCE": "E",
    "WORKING_NOTE": "◌",
    "ARTICLE": "✎",
    "DUMP": "⬒",
    "UNCLASSIFIED": "?",
}

LAW_NAMES = {
    "L01": "L01 · Gravitation",
    "L02": "L02 · Motion",
    "L03": "L03 · Electromagnetism",
    "L04": "L04 · Strong Force",
    "L05": "L05 · Thermodynamics",
    "L06": "L06 · Information",
    "L07": "L07 · Quantum",
    "L08": "L08 · Relativity",
    "L09": "L09 · Weak Force",
    "L10": "L10 · Coherence",
    "none": "(none)",
}


def jload(s, default=None):
    try:
        return json.loads(s) if s else default
    except Exception:
        return default


def registry_conn() -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{REGISTRY_DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


# ── Data helpers ───────────────────────────────────────

def extract_cls(row) -> dict:
    return jload(row["local_classification_json"], {}) or {}


def law_of(row) -> str:
    law = extract_cls(row).get("law")
    if isinstance(law, dict):
        return law.get("name", "")
    return law or ""


def law_score(row) -> int:
    law = extract_cls(row).get("law")
    if isinstance(law, dict):
        return law.get("score", 0)
    return 0


def chi_of(row) -> str:
    return extract_cls(row).get("chi_factor") or ""


def domain_of(row) -> str:
    d = extract_cls(row).get("domain")
    if isinstance(d, dict):
        return d.get("name", "")
    return d or ""


def evidence_score(row) -> float:
    cls = extract_cls(row)
    se = cls.get("structural_evidence", {})
    return se.get("total_score", 0.0) if isinstance(se, dict) else 0.0


def chi_sum(row) -> int:
    cls = extract_cls(row)
    return cls.get("chi_sum", 0)


def fruit_score(row) -> float:
    return extract_cls(row).get("fruit", 0.0)


# ── Main Window ────────────────────────────────────────

class AxiomSearchExport(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Axiom Search & Export — David-OS v3")
        self.setMinimumSize(1400, 800)
        self._rows: list[dict] = []
        self._selected_ids: set[int] = set()
        self._apply_theme()
        self._build_ui()
        self._load_data()

    # ── Theme ──────────────────────────────────────────
    def _apply_theme(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background: {DEEP}; color: {CREAM}; }}
            QGroupBox {{
                border: 1px solid {GOLD_DIM};
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 18px;
                font-family: 'JetBrains Mono', 'Consolas', monospace;
                font-size: 10px;
                color: {GOLD};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }}
            QLineEdit, QComboBox, QTextEdit {{
                background: {SURFACE};
                border: 1px solid {GOLD_DIM};
                border-radius: 4px;
                padding: 6px 10px;
                color: {CREAM};
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: 12px;
                selection-background-color: {GOLD_DIM};
            }}
            QLineEdit:focus, QComboBox:focus {{
                border-color: {GOLD};
            }}
            QPushButton {{
                background: {SURFACE2};
                border: 1px solid {GOLD_DIM};
                border-radius: 4px;
                padding: 6px 16px;
                color: {CREAM};
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: 11px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {GOLD_DIM};
                border-color: {GOLD};
                color: {GOLD};
            }}
            QPushButton:pressed {{
                background: {GOLD};
                color: {VOID};
            }}
            QPushButton#export_btn {{
                background: {GOLD_DIM};
                border-color: {GOLD};
                color: {GOLD};
                font-weight: 600;
            }}
            QPushButton#export_btn:hover {{
                background: {GOLD};
                color: {VOID};
            }}
            QTableWidget {{
                background: {SURFACE};
                alternate-background-color: {SURFACE2};
                border: 1px solid {GOLD_DIM};
                border-radius: 4px;
                gridline-color: {GOLD_DIM};
                color: {CREAM};
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: 11px;
                selection-background-color: {GOLD_DIM};
                selection-color: {GOLD};
            }}
            QTableWidget::item:selected {{
                background: {GOLD_DIM};
                color: {GOLD};
            }}
            QHeaderView::section {{
                background: {VOID};
                color: {GOLD};
                border: none;
                border-bottom: 1px solid {GOLD_DIM};
                padding: 6px 8px;
                font-family: 'JetBrains Mono', 'Consolas', monospace;
                font-size: 10px;
                letter-spacing: 1px;
                text-transform: uppercase;
            }}
            QLabel {{
                color: {CREAM_DIM};
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: 11px;
            }}
            QLabel#title {{
                color: {GOLD};
                font-family: 'Cinzel', 'Playfair Display', Georgia, serif;
                font-size: 18px;
                font-weight: 700;
            }}
            QLabel#stat {{
                color: {GOLD};
                font-family: 'JetBrains Mono', 'Consolas', monospace;
                font-size: 22px;
                font-weight: 600;
            }}
            QLabel#stat_label {{
                color: {CREAM_DIM};
                font-family: 'JetBrains Mono', 'Consolas', monospace;
                font-size: 9px;
                letter-spacing: 2px;
            }}
            QCheckBox {{
                color: {CREAM_DIM};
                font-size: 11px;
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 14px; height: 14px;
                border: 1px solid {GOLD_DIM};
                border-radius: 3px;
                background: {SURFACE};
            }}
            QCheckBox::indicator:checked {{
                background: {GOLD};
                border-color: {GOLD};
            }}
            QStatusBar {{
                background: {VOID};
                color: {CREAM_DIM};
                font-family: 'JetBrains Mono', monospace;
                font-size: 10px;
                border-top: 1px solid {GOLD_DIM};
            }}
            QTextEdit#detail {{
                background: {VOID};
                border: 1px solid {GOLD_DIM};
                border-radius: 4px;
                color: {CREAM};
                font-family: 'JetBrains Mono', 'Consolas', monospace;
                font-size: 11px;
                padding: 12px;
            }}
            QSplitter::handle {{
                background: {GOLD_DIM};
                width: 2px;
            }}
        """)

    # ── UI ─────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 8)
        root.setSpacing(10)

        # Title bar
        title_row = QHBoxLayout()
        title = QLabel("AXIOM SEARCH & EXPORT")
        title.setObjectName("title")
        title_row.addWidget(title)
        title_row.addStretch()

        # Stats placeholders
        self.stat_total = QLabel("—")
        self.stat_total.setObjectName("stat")
        self.stat_total_label = QLabel("TOTAL")
        self.stat_total_label.setObjectName("stat_label")
        self.stat_axioms = QLabel("—")
        self.stat_axioms.setObjectName("stat")
        self.stat_axioms_label = QLabel("AXIOMS")
        self.stat_axioms_label.setObjectName("stat_label")
        self.stat_results = QLabel("—")
        self.stat_results.setObjectName("stat")
        self.stat_results_label = QLabel("RESULTS")
        self.stat_results_label.setObjectName("stat_label")
        self.stat_selected = QLabel("0")
        self.stat_selected.setObjectName("stat")
        self.stat_selected_label = QLabel("SELECTED")
        self.stat_selected_label.setObjectName("stat_label")

        for lbl, sub in [
            (self.stat_total, self.stat_total_label),
            (self.stat_axioms, self.stat_axioms_label),
            (self.stat_results, self.stat_results_label),
            (self.stat_selected, self.stat_selected_label),
        ]:
            box = QVBoxLayout()
            box.setAlignment(Qt.AlignCenter)
            box.addWidget(lbl, alignment=Qt.AlignCenter)
            box.addWidget(sub, alignment=Qt.AlignCenter)
            title_row.addLayout(box)
            title_row.addSpacing(24)

        root.addLayout(title_row)

        # ── Filters ────────────────────────────────────
        filters = QGroupBox("FILTERS")
        fg = QHBoxLayout(filters)

        # Search
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name, path, keywords…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filters)
        fg.addWidget(self.search, 2)

        # Doc type
        fg.addWidget(QLabel("Type:"))
        self.type_filter = QComboBox()
        self.type_filter.addItem("All types", "")
        for dt, glyph in DOC_GLYPHS.items():
            self.type_filter.addItem(f"{glyph} {dt}", dt)
        self.type_filter.currentIndexChanged.connect(self._apply_filters)
        fg.addWidget(self.type_filter)

        # Law
        fg.addWidget(QLabel("Law:"))
        self.law_filter = QComboBox()
        self.law_filter.addItem("All laws", "")
        for code, name in LAW_NAMES.items():
            self.law_filter.addItem(name, code)
        self.law_filter.currentIndexChanged.connect(self._apply_filters)
        fg.addWidget(self.law_filter)

        # Domain
        fg.addWidget(QLabel("Domain:"))
        self.domain_filter = QComboBox()
        self.domain_filter.addItem("All domains", "")
        self.domain_filter.currentIndexChanged.connect(self._apply_filters)
        fg.addWidget(self.domain_filter)

        # Confidence threshold
        fg.addWidget(QLabel("Min conf:"))
        self.conf_slider = QSlider(Qt.Horizontal)
        self.conf_slider.setRange(0, 100)
        self.conf_slider.setValue(0)
        self.conf_slider.setMaximumWidth(120)
        self.conf_slider.valueChanged.connect(self._apply_filters)
        self.conf_label = QLabel("0%")
        self.conf_label.setFixedWidth(35)
        fg.addWidget(self.conf_slider)
        fg.addWidget(self.conf_label)

        # Axiom only checkbox
        self.axiom_only = QCheckBox("Axioms only")
        self.axiom_only.setChecked(True)
        self.axiom_only.stateChanged.connect(self._apply_filters)
        fg.addWidget(self.axiom_only)

        root.addWidget(filters)

        # ── Main splitter: table + detail ──────────────
        splitter = QSplitter(Qt.Horizontal)

        # Table
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.selectionModel = None  # will be set after setColumnCount

        cols = ["✓", "Glyph", "Name", "Type", "Conf", "Law", "Domain",
                "χ", "Evidence", "Fruit", "Size", "Modified"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 30)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 35)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        for i in range(3, len(cols)):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        self.table.itemSelectionChanged.connect(self._on_selection)
        self.table.cellClicked.connect(self._on_cell_click)

        splitter.addWidget(self.table)

        # Detail panel
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)

        self.detail_title = QLabel("Select an axiom")
        self.detail_title.setStyleSheet(f"color: {GOLD}; font-size: 14px; font-weight: 600; font-family: 'Playfair Display', Georgia, serif;")
        self.detail_title.setWordWrap(True)
        detail_layout.addWidget(self.detail_title)

        self.detail_text = QTextEdit()
        self.detail_text.setObjectName("detail")
        self.detail_text.setReadOnly(True)
        detail_layout.addWidget(self.detail_text)

        splitter.addWidget(detail_widget)
        splitter.setSizes([900, 500])

        root.addWidget(splitter, 1)

        # ── Bottom bar: export ─────────────────────────
        bottom = QHBoxLayout()

        self.select_all_btn = QPushButton("Select All Visible")
        self.select_all_btn.clicked.connect(self._select_all)
        bottom.addWidget(self.select_all_btn)

        self.deselect_btn = QPushButton("Deselect All")
        self.deselect_btn.clicked.connect(self._deselect_all)
        bottom.addWidget(self.deselect_btn)

        bottom.addStretch()

        bottom.addWidget(QLabel("Export as:"))
        self.export_format = QComboBox()
        self.export_format.addItems(["JSON (atom-envelope)", "CSV", "Markdown"])
        bottom.addWidget(self.export_format)

        export_btn = QPushButton("EXPORT SELECTED")
        export_btn.setObjectName("export_btn")
        export_btn.clicked.connect(self._export)
        bottom.addWidget(export_btn)

        root.addLayout(bottom)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage(f"Registry: {REGISTRY_DB}")

    # ── Data ───────────────────────────────────────────
    def _load_data(self):
        if not REGISTRY_DB.exists():
            self.status.showMessage(f"ERROR: Registry not found at {REGISTRY_DB}")
            return

        conn = registry_conn()
        rows = conn.execute("""
            SELECT file_id, path, name, doc_type, type_confidence,
                   local_classification_json, keywords_text,
                   size_bytes, last_modified, format
            FROM file_memory
            WHERE doc_type IS NOT NULL
            ORDER BY name
        """).fetchall()
        conn.close()

        # Collect domains for filter
        domains = set()

        self._rows = []
        for r in rows:
            cls = jload(r["local_classification_json"], {}) or {}
            law = cls.get("law", {})
            law_name = law.get("name", "") if isinstance(law, dict) else (law or "")
            law_sc = law.get("score", 0) if isinstance(law, dict) else 0

            dom = cls.get("domain", {})
            dom_name = dom.get("name", "") if isinstance(dom, dict) else (dom or "")
            if dom_name:
                domains.add(dom_name)

            se = cls.get("structural_evidence", {})
            ev_total = se.get("total_score", 0.0) if isinstance(se, dict) else 0.0

            self._rows.append({
                "id": r["file_id"],
                "path": r["path"],
                "name": r["name"],
                "doc_type": r["doc_type"] or "",
                "confidence": r["type_confidence"] or 0.0,
                "law": law_name,
                "law_score": law_sc,
                "domain": dom_name,
                "chi_factor": cls.get("chi_factor", ""),
                "chi_sum": cls.get("chi_sum", 0),
                "evidence": ev_total,
                "fruit": cls.get("fruit", 0.0),
                "anti_fruit": cls.get("anti_fruit", 0.0),
                "size": r["size_bytes"] or 0,
                "modified": r["last_modified"] or "",
                "keywords": r["keywords_text"] or "",
                "format": r["format"] or "",
                "cls": cls,
            })

        # Populate domain filter
        for d in sorted(domains):
            self.domain_filter.addItem(d.title(), d)

        # Stats
        total = len(self._rows)
        axiom_count = sum(1 for r in self._rows if r["doc_type"] == "AXIOM")
        self.stat_total.setText(str(total))
        self.stat_axioms.setText(str(axiom_count))

        self._apply_filters()

    # ── Filtering ──────────────────────────────────────
    def _apply_filters(self):
        search = self.search.text().lower().strip()
        type_f = self.type_filter.currentData()
        law_f = self.law_filter.currentData()
        domain_f = self.domain_filter.currentData()
        min_conf = self.conf_slider.value() / 100.0
        axiom_only = self.axiom_only.isChecked()

        self.conf_label.setText(f"{self.conf_slider.value()}%")

        filtered = []
        for r in self._rows:
            if axiom_only and r["doc_type"] != "AXIOM":
                continue
            if type_f and r["doc_type"] != type_f:
                continue
            if law_f and r["law"] != law_f:
                continue
            if domain_f and r["domain"] != domain_f:
                continue
            if r["confidence"] < min_conf:
                continue
            if search:
                haystack = f"{r['name']} {r['path']} {r['keywords']} {r['domain']} {r['law']}".lower()
                if search not in haystack:
                    continue
            filtered.append(r)

        self._display(filtered)

    # ── Table display ──────────────────────────────────
    def _display(self, rows: list[dict]):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        self._visible_rows = rows

        for i, r in enumerate(rows):
            # Checkbox column
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Checked if r["id"] in self._selected_ids else Qt.Unchecked)
            chk.setData(Qt.UserRole, r["id"])
            self.table.setItem(i, 0, chk)

            # Glyph
            glyph = DOC_GLYPHS.get(r["doc_type"], "?")
            g_item = QTableWidgetItem(glyph)
            g_item.setTextAlignment(Qt.AlignCenter)
            g_item.setForeground(QColor(GOLD))
            self.table.setItem(i, 1, g_item)

            # Name
            n_item = QTableWidgetItem(r["name"])
            n_item.setForeground(QColor(CREAM))
            self.table.setItem(i, 2, n_item)

            # Type
            t_item = QTableWidgetItem(r["doc_type"])
            t_item.setForeground(QColor(GOLD if r["doc_type"] == "AXIOM" else CREAM_DIM))
            self.table.setItem(i, 3, t_item)

            # Confidence
            conf_pct = f"{r['confidence']:.0%}"
            c_item = QTableWidgetItem(conf_pct)
            c_item.setData(Qt.UserRole, r["confidence"])
            c_item.setTextAlignment(Qt.AlignCenter)
            if r["confidence"] >= 0.9:
                c_item.setForeground(QColor(GOLD))
            elif r["confidence"] >= 0.5:
                c_item.setForeground(QColor(SAGE))
            else:
                c_item.setForeground(QColor(CREAM_DIM))
            self.table.setItem(i, 4, c_item)

            # Law
            law_display = LAW_NAMES.get(r["law"], r["law"])
            l_item = QTableWidgetItem(law_display)
            l_item.setForeground(QColor(COPPER))
            self.table.setItem(i, 5, l_item)

            # Domain
            d_item = QTableWidgetItem(r["domain"].title() if r["domain"] else "")
            d_item.setForeground(QColor(SLATE))
            self.table.setItem(i, 6, d_item)

            # Chi sum
            chi_item = QTableWidgetItem(str(r["chi_sum"]) if r["chi_sum"] else "")
            chi_item.setData(Qt.UserRole, r["chi_sum"])
            chi_item.setTextAlignment(Qt.AlignCenter)
            chi_item.setForeground(QColor(GOLD if r["chi_sum"] >= 15 else CREAM_DIM))
            self.table.setItem(i, 7, chi_item)

            # Evidence
            ev_item = QTableWidgetItem(f"{r['evidence']:.0f}" if r["evidence"] else "")
            ev_item.setData(Qt.UserRole, r["evidence"])
            ev_item.setTextAlignment(Qt.AlignCenter)
            ev_item.setForeground(QColor(SAGE if r["evidence"] >= 10 else CREAM_DIM))
            self.table.setItem(i, 8, ev_item)

            # Fruit
            fr_item = QTableWidgetItem(f"{r['fruit']:.0f}" if r["fruit"] else "")
            fr_item.setData(Qt.UserRole, r["fruit"])
            fr_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 9, fr_item)

            # Size
            sz = r["size"]
            sz_str = f"{sz/1024:.0f}K" if sz >= 1024 else f"{sz}B"
            sz_item = QTableWidgetItem(sz_str)
            sz_item.setData(Qt.UserRole, sz)
            sz_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            sz_item.setForeground(QColor(CREAM_DIM))
            self.table.setItem(i, 10, sz_item)

            # Modified
            mod = r["modified"][:10] if r["modified"] else ""
            m_item = QTableWidgetItem(mod)
            m_item.setForeground(QColor(CREAM_DIM))
            self.table.setItem(i, 11, m_item)

        self.table.setSortingEnabled(True)
        self.stat_results.setText(str(len(rows)))
        self._update_selected_count()

    # ── Selection ──────────────────────────────────────
    def _on_cell_click(self, row, col):
        if col == 0:
            item = self.table.item(row, 0)
            rid = item.data(Qt.UserRole)
            if item.checkState() == Qt.Checked:
                self._selected_ids.add(rid)
            else:
                self._selected_ids.discard(rid)
            self._update_selected_count()

    def _on_selection(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if idx < len(self._visible_rows):
            self._show_detail(self._visible_rows[idx])

    def _select_all(self):
        for r in self._visible_rows:
            self._selected_ids.add(r["id"])
        self._apply_filters()

    def _deselect_all(self):
        self._selected_ids.clear()
        self._apply_filters()

    def _update_selected_count(self):
        self.stat_selected.setText(str(len(self._selected_ids)))

    # ── Detail panel ───────────────────────────────────
    def _show_detail(self, row: dict):
        self.detail_title.setText(row["name"])

        cls = row["cls"]
        lines = []

        # Identity
        lines.append(f"{'─' * 50}")
        lines.append(f"  PATH     {row['path']}")
        lines.append(f"  TYPE     {row['doc_type']}  (confidence: {row['confidence']:.1%})")
        lines.append(f"  FORMAT   {row['format']}")
        lines.append(f"  SIZE     {row['size']:,} bytes")
        lines.append(f"  MODIFIED {row['modified']}")
        lines.append(f"{'─' * 50}")

        # Classification
        lines.append("")
        lines.append("CLASSIFICATION")
        lines.append(f"  Law         {LAW_NAMES.get(row['law'], row['law'])}  (score: {row['law_score']})")
        lines.append(f"  Domain      {row['domain']}")
        lines.append(f"  χ factor    {row['chi_factor']}")
        lines.append(f"  χ sum       {row['chi_sum']}")
        lines.append(f"  File role   {cls.get('file_role', '')}")

        # Chi vector
        chi = cls.get("chi", {})
        if chi:
            vec = " ".join(f"{k}:{v}" for k, v in chi.items())
            lines.append(f"  χ vector    {vec}")

        # Fruit
        lines.append(f"  Fruit       {row['fruit']:.1f}")
        lines.append(f"  Anti-fruit  {row['anti_fruit']:.1f}")

        # Type scores
        ts = cls.get("type_scores", {})
        if ts:
            lines.append("")
            lines.append("TYPE SCORES")
            for t, s in sorted(ts.items(), key=lambda x: -x[1]):
                bar = "█" * int(s * 20)
                lines.append(f"  {t:<15} {s:.3f}  {bar}")

        # Structural evidence
        se = cls.get("structural_evidence", {})
        if se and isinstance(se, dict):
            lines.append("")
            lines.append(f"STRUCTURAL EVIDENCE  (total: {se.get('total_score', 0):.1f})")
            channels = se.get("channels", {})
            for ch, val in channels.items():
                lines.append(f"  {ch:<15} {val:.1f}")
            artifacts = se.get("detected_artifacts", [])
            if artifacts:
                lines.append("  Artifacts:")
                for a in artifacts:
                    lines.append(f"    · {a}")
            gaps = se.get("proof_gaps", [])
            if gaps:
                lines.append("  Proof gaps:")
                for g in gaps:
                    lines.append(f"    ⚠ {g}")

        # Type evidence
        te = cls.get("type_evidence", [])
        if te:
            lines.append("")
            lines.append("TYPE EVIDENCE")
            for e in te:
                lines.append(f"  {e.get('signal', '')}  ×{e.get('count', 0)}  (w={e.get('weight', 0)})")

        # Keywords
        if row["keywords"]:
            lines.append("")
            lines.append(f"KEYWORDS  {row['keywords']}")

        # Lossless address
        la = cls.get("lossless_address", "")
        if la:
            lines.append("")
            lines.append(f"LOSSLESS ADDRESS  {la}")

        # Safe actions
        sa = cls.get("safe_actions", [])
        if sa:
            lines.append(f"SAFE ACTIONS  {', '.join(sa)}")

        self.detail_text.setPlainText("\n".join(lines))

    # ── Context menu ───────────────────────────────────
    def _context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background: {SURFACE}; border: 1px solid {GOLD_DIM}; color: {CREAM}; }}
            QMenu::item:selected {{ background: {GOLD_DIM}; color: {GOLD}; }}
        """)
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return

        open_act = menu.addAction("Open file location")
        copy_path = menu.addAction("Copy path")
        copy_json = menu.addAction("Copy classification JSON")
        menu.addSeparator()
        select_act = menu.addAction("Select for export")

        action = menu.exec_(self.table.viewport().mapToGlobal(pos))
        idx = rows[0].row()
        if idx >= len(self._visible_rows):
            return
        r = self._visible_rows[idx]

        if action == copy_path:
            QApplication.clipboard().setText(r["path"])
            self.status.showMessage(f"Copied: {r['path']}", 3000)
        elif action == copy_json:
            QApplication.clipboard().setText(json.dumps(r["cls"], indent=2))
            self.status.showMessage("Classification JSON copied", 3000)
        elif action == open_act:
            folder = str(Path(r["path"]).parent)
            os.startfile(folder) if sys.platform == "win32" else os.system(f'xdg-open "{folder}"')
        elif action == select_act:
            self._selected_ids.add(r["id"])
            self._apply_filters()

    # ── Export ─────────────────────────────────────────
    def _export(self):
        selected = [r for r in self._rows if r["id"] in self._selected_ids]
        if not selected:
            QMessageBox.warning(self, "Nothing selected", "Select at least one axiom to export.")
            return

        fmt = self.export_format.currentText()

        if "JSON" in fmt:
            ext = "json"
            content = self._export_json(selected)
        elif "CSV" in fmt:
            ext = "csv"
            content = self._export_csv(selected)
        else:
            ext = "md"
            content = self._export_markdown(selected)

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Axioms",
            str(Path.home() / f"axiom_export_{datetime.now():%Y%m%d_%H%M}.{ext}"),
            f"{'JSON' if ext == 'json' else ext.upper()} files (*.{ext});;All files (*.*)"
        )
        if not path:
            return

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        self.status.showMessage(f"Exported {len(selected)} axioms to {path}", 5000)

    def _export_json(self, rows: list[dict]) -> str:
        """Export in atom-envelope-compatible JSON."""
        atoms = []
        for r in rows:
            cls = r["cls"]
            chi = cls.get("chi", {})
            se = cls.get("structural_evidence", {})

            atom = {
                "schema_version": "atom-envelope/1.1.0",
                "identity": {
                    "id": f"axiom-{r['id']}",
                    "object_type": "CLAIM",
                    "version": "1.0.0",
                    "content_hash": None,
                    "title": r["name"],
                },
                "provenance": {
                    "source_uri": r["path"],
                    "source_span": None,
                    "ai_contribution_declared": True,
                },
                "axes": {
                    "lifecycle_state": "CLASSIFIED",
                    "proof_class": "NOT_ATTEMPTED",
                    "register": cls.get("content_type", ""),
                    "ic_grade": "IC-0",
                    "why_outcome": "NOT_APPLICABLE",
                },
                "classification": {
                    "doc_type": r["doc_type"],
                    "type_confidence": r["confidence"],
                    "law": r["law"],
                    "law_score": r["law_score"],
                    "domain": r["domain"],
                    "chi_factor": r["chi_factor"],
                    "chi_vector": chi,
                    "chi_sum": r["chi_sum"],
                    "fruit_score": r["fruit"],
                    "anti_fruit_score": r["anti_fruit"],
                    "file_role": cls.get("file_role", ""),
                    "keywords": r["keywords"],
                },
                "structural_evidence": se if isinstance(se, dict) else {},
                "type_scores": cls.get("type_scores", {}),
                "type_evidence": cls.get("type_evidence", []),
            }
            atoms.append(atom)

        return json.dumps({"atoms": atoms, "exported_at": datetime.now().isoformat(), "count": len(atoms)}, indent=2)

    def _export_csv(self, rows: list[dict]) -> str:
        buf = StringIO()
        w = csv.writer(buf)
        w.writerow(["name", "path", "doc_type", "confidence", "law", "law_score",
                     "domain", "chi_factor", "chi_sum", "evidence", "fruit",
                     "anti_fruit", "size", "modified", "keywords", "file_role"])
        for r in rows:
            w.writerow([
                r["name"], r["path"], r["doc_type"], f"{r['confidence']:.3f}",
                r["law"], r["law_score"], r["domain"], r["chi_factor"],
                r["chi_sum"], f"{r['evidence']:.1f}", f"{r['fruit']:.1f}",
                f"{r['anti_fruit']:.1f}", r["size"], r["modified"],
                r["keywords"], r["cls"].get("file_role", ""),
            ])
        return buf.getvalue()

    def _export_markdown(self, rows: list[dict]) -> str:
        lines = [
            "# Axiom Export",
            f"Exported: {datetime.now():%Y-%m-%d %H:%M}",
            f"Count: {len(rows)}",
            "",
            "| Name | Type | Conf | Law | Domain | χ | Evidence |",
            "|------|------|------|-----|--------|---|----------|",
        ]
        for r in rows:
            lines.append(
                f"| {r['name']} | {r['doc_type']} | {r['confidence']:.0%} | "
                f"{r['law']} | {r['domain']} | {r['chi_sum']} | {r['evidence']:.0f} |"
            )
        return "\n".join(lines)


# ── Entry point ────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette base
    pal = app.palette()
    pal.setColor(QPalette.Window, QColor(DEEP))
    pal.setColor(QPalette.WindowText, QColor(CREAM))
    pal.setColor(QPalette.Base, QColor(SURFACE))
    pal.setColor(QPalette.AlternateBase, QColor(SURFACE2))
    pal.setColor(QPalette.Text, QColor(CREAM))
    pal.setColor(QPalette.Button, QColor(SURFACE2))
    pal.setColor(QPalette.ButtonText, QColor(CREAM))
    pal.setColor(QPalette.Highlight, QColor(GOLD_DIM))
    pal.setColor(QPalette.HighlightedText, QColor(GOLD))
    app.setPalette(pal)

    win = AxiomSearchExport()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
