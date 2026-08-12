"""The folder-level interview (spec) — ask about the WHOLE folder, then cluster,
never 200 questions. These configure scope + permission before the scan acts.
"""
from __future__ import annotations

QUESTIONS = [
    ("purpose", "What was this folder originally meant to be?"),
    ("arrival", "How did material usually arrive here — downloads, saves, exports, backups, several?"),
    ("active", "Is anything still actively used from it?"),
    ("sensitive", "Could it contain work, personal, financial, legal, code, credentials, or irreplaceable material?"),
    ("organized_subs", "Are any existing subfolders already correctly organized?"),
    ("preserve_projects", "Should FIS preserve recognizable projects as intact units?"),
    ("keep_criteria", "What makes something worth keeping even if not opened recently?"),
    ("categories", "What categories should emerge from the cleanup?"),
    ("may_touch", "What may FIS rename or move after preview?"),
    ("never_touch", "What must remain untouched regardless of confidence?"),
]


def blank_answers() -> dict:
    return {key: "" for key, _ in QUESTIONS}
