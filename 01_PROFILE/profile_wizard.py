#!/usr/bin/env python3
"""profile_wizard — 01_PROFILE GUI. Thin shell over profile_core."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))          # profile_core
sys.path.insert(0, str(REPO))                                     # hub package

from PySide6.QtWidgets import (QApplication, QWizard, QWizardPage, QVBoxLayout,
                               QLabel, QLineEdit, QMessageBox)     # noqa: E402
import profile_core as pc                                          # noqa: E402


class QuestionPage(QWizardPage):
    def __init__(self, q: dict, suggestion: dict | None, parent=None):
        super().__init__(parent)
        self.qid = q["id"]
        self.setTitle(q["question"])
        lay = QVBoxLayout(self)
        self.edit = QLineEdit()
        if suggestion:
            val = suggestion.get("value", "")
            self.edit.setText(", ".join(val) if isinstance(val, list) else str(val))
            lay.addWidget(QLabel(f"suggested ({suggestion['source']}, "
                                 f"{suggestion['confidence']:.0%}) — edit if wrong"))
        lay.addWidget(self.edit)


class ProfileWizard(QWizard):
    def __init__(self, root: Path):
        super().__init__()
        self.root = root
        self.setWindowTitle(f"Profile this folder — {root.name}")
        self.quiz = pc.load_questionnaire(REPO / "config/rules" / pc.QUESTIONNAIRE)
        self.evidence = pc.scan_evidence(root)
        self.sugg = pc.suggest_answers(self.quiz, self.evidence)
        self.pages: list[QuestionPage] = []
        for q in sorted(self.quiz["core_questions"], key=lambda x: x["order"]):
            page = QuestionPage(q, self.sugg.get(q["id"]))
            self.pages.append(page)
            self.addPage(page)

    def accept(self):  # Finish — the ONLY write
        answers = {p.qid: p.edit.text().strip() for p in self.pages if p.edit.text().strip()}
        profile = pc.build_profile(self.root, answers, self.quiz)
        try:
            pc.write_profile(self.root, profile, REPO / "config" / "folder_profiles.json",
                             answers, self.evidence)
        except ValueError as e:
            QMessageBox.critical(self, "Profile not written", str(e))
            return
        QMessageBox.information(self, "Profiled",
                                f"{self.root} is now profiled as '{profile['folder_role']}'.")
        super().accept()


def main() -> int:
    folder = sys.argv[1] if len(sys.argv) > 1 else None
    app = QApplication(sys.argv)
    if not folder:
        from PySide6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(None, "Pick a folder to profile")
        if not folder:
            return 0
    w = ProfileWizard(Path(folder))
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
