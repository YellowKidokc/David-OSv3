#!/usr/bin/env python3
"""David-OS v3 launcher — one place to start every GUI in this folder.

Run:  python D:\\GitHub\\David-OSv3\\gui\\launcher.py   (or START_HERE.bat)
Add a tool: append to TOOLS below.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

HERE = Path(__file__).resolve().parent

# (label, file relative to gui/, description)
TOOLS = [
    ("01 · Profile — the doorway wizard", "../01_PROFILE/PROFILE.bat",
     "20 questions · evidence pre-fill · writes the folder's rules"),
    ("03 · Document Classifier — Review sidecars", "../03_CLASSIFY/REVIEW.bat", "Every card · engine + DeepSeek suggestions · accept / reject / edit, one or all"),
    ("03 · Classify — Validate sidecars", "../03_CLASSIFY/VALIDATE.bat", "Check the AXIOM canon sidecars against TAG_TAXONOMY_v0.4"),
    ("04 · Adapt — old cards → mim.v1", "../04_ADAPT/ADAPT.bat",
     "Glossary/legacy cards get their stamp · mechanical fields only · judgment stays yours"),
    ("Drive Harvester", "drive_harvester.py", "Search all drives for a term · canon pins · fingerprint · flatten + sidecars"),
    ("Axiom Search & Export", "axiom_search_export.py", "Browse axioms already in the FIS registry"),
    ("FIS Search Workbench", "fis_search_workbench.py", "Search the FIS catalog"),
    ("FIS Scanner", "fis_scanner_gui.py", "Scan folders, multi-tag, speed slider"),
    ("Operations Panel", "operations_panel.py", "Folder health, links, quality, canon sidecars, file actions"),
    ("Master Equation Intake", "master_equation_intake_gui.py", "Observe-only Master Equation intake"),
    ("File Tagger", "filetagger_gui.py", "Small tagging popup"),
    ("FIS Vault Intelligence (HTML)", "html/fis_vault_intelligence_v3.html", "Opens in browser"),
    ("FIS Reference v2.1.0 (HTML)", "html/FIS_REFERENCE_v2.1.0.html", "Opens in browser"),
]


def launch(rel: str) -> None:
    path = HERE / rel
    if path.suffix == ".py":
        subprocess.Popen([sys.executable, str(path)], cwd=str(HERE))
    else:
        os.startfile(path)


def main():
    app = QApplication(sys.argv)
    w = QWidget()
    w.setWindowTitle("David-OS v3 — Launcher")
    w.setStyleSheet("""
        QWidget { background:#0a0a0a; color:#e8e0cc; font-family:'Segoe UI'; font-size:12px; }
        QPushButton { background:#1a1816; border:1px solid #3d2e0f; padding:8px; text-align:left; color:#d4af37; font-weight:600; }
        QPushButton:hover { border-color:#d4af37; }
        QLabel { color:#6b6456; margin-bottom:6px; }
    """)
    v = QVBoxLayout(w)
    for label, rel, desc in TOOLS:
        b = QPushButton(label)
        exists = (HERE / rel).exists()
        b.setEnabled(exists)
        b.clicked.connect(lambda _=False, r=rel: launch(r))
        v.addWidget(b)
        v.addWidget(QLabel(desc if exists else f"missing: {rel}"))
    w.resize(460, 0)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
