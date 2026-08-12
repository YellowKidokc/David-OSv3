"""The symptom registry as orchestration (David's spec).

Every folder passes through this: if it matches a symptom's description, the
symptom fires with a severity + a recommended action. Recommended actions are
then GATED by the folder's permission tiers — a symptom can suggest, never force.

Detectors are DATA (id, category, severity, recommended_action) + a predicate.
This is a working subset of the 40-symptom registry; the rest port in the same
shape. severity: low | medium | high | critical (critical never auto-fixes).
"""
from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .model import FolderRecord, ObjectRecord

NOW = time.time()
DAY = 86400


@dataclass
class SymptomHit:
    id: str
    category: str
    name: str
    severity: str
    recommended_action: str
    evidence: str
    permitted: bool = True          # after permission-tier gating

    def to_dict(self):
        return self.__dict__


# ---- detectors: (id, category, name, severity, recommended_action, predicate) ----
def _ext_swamp(f, objs):
    exts = {Path(o.name).suffix.lower() for o in objs if o.ext}
    return (len(exts) > 8, f"{len(exts)} distinct extensions in one folder")


def _flat_overload(f, objs):
    return (len(objs) > 200, f"{len(objs)} files directly in one folder")


def _version_sprawl(f, objs):
    import re
    hits = [o.name for o in objs if re.search(r"(_v\d|_final|_copy|\(\d\)|FINAL)", o.name, re.I)]
    return (len(hits) >= 3, f"{len(hits)} versioned/duplicate-looking names")


def _media_dump(f, objs):
    import re
    hits = [o for o in objs if re.match(r"(IMG_|Screenshot|DSC_|Clipto|ShareX|comet_)", o.name, re.I)]
    return (len(hits) >= 5, f"{len(hits)} auto-named media files")


def _download_purgatory(f, objs):
    installers = [o for o in objs if o.ext in (".exe", ".msi", ".dmg", ".zip")]
    docs = [o for o in objs if o.content_type in ("document", "markdown", "pdf")]
    return (installers and docs, f"{len(installers)} installers/archives mixed with {len(docs)} docs")


def _name_rot(f, objs):
    import re
    hits = [o for o in objs if re.search(r"(untitled|new document|screenshot_\d)", o.name, re.I)]
    return (len(hits) >= 1, f"{len(hits)} auto-generated names")


def _tiny_debris(f, objs):
    return (f.empty, "empty folder (nothing real inside)")


def _program_root(f, objs):
    return (f.folder_class == "programming", "program/project root — protect")


def _config_leak(f, objs):
    hits = [o for o in objs if any(p in o.name.lower() for p in (".env", "secret", "token", "apikey", "credential"))]
    return (bool(hits), f"{len(hits)} secret/credential-looking files")


def _time_bomb(f, objs):
    old = [o for o in objs if o.modified and (NOW - o.modified) / DAY > 180]
    return (len(old) >= max(3, len(objs) // 2) and len(objs) > 0, f"{len(old)} files untouched >6 months")


def _document_chaos(f, objs):
    types = Counter(o.content_type for o in objs)
    mixed = sum(1 for t in ("document", "spreadsheet", "presentation", "pdf") if types.get(t))
    return (mixed >= 3, "mixed document types with no grouping")


REGISTRY = [
    ("S01", "Structural", "Extension swamp", "medium", "split_by_content_family", _ext_swamp),
    ("S04", "Structural", "Flat overload", "medium", "classify_and_split", _flat_overload),
    ("S02", "Structural", "Version sprawl", "medium", "keep_latest_archive_old", _version_sprawl),
    ("C05", "Content", "Media dump", "low", "sort_by_type_date", _media_dump),
    ("C04", "Content", "Document chaos", "medium", "sort_by_topic_project", _document_chaos),
    ("N01", "Naming", "Name rot", "low", "content_based_rename", _name_rot),
    ("N02", "Naming", "Download purgatory", "medium", "separate_installers", _download_purgatory),
    ("N03", "Naming", "Tiny-folder debris", "low", "review_delete_empty", _tiny_debris),
    ("I01", "Infrastructure", "Program-root danger", "critical", "protect_never_touch", _program_root),
    ("I03", "Infrastructure", "Config leak", "critical", "alert_and_secure", _config_leak),
    ("T01", "Temporal", "Time bomb", "low", "flag_for_archive_review", _time_bomb),
]


def run_symptoms(f: FolderRecord, objs: list[ObjectRecord]) -> list[SymptomHit]:
    """Run every applicable detector, gate recommended actions by permission."""
    hits = []
    allowed = set(f.allowed_actions) | set(
        f.permissions.get("without_approval", []) + f.permissions.get("as_proposals", [])
    )
    forbidden = set(f.forbidden_actions)
    for sid, cat, name, sev, action, pred in REGISTRY:
        try:
            matched, evidence = pred(f, objs)
        except Exception:
            matched, evidence = False, ""
        if matched:
            # a critical protect symptom is always permitted (it only seals);
            # mutating recommendations are gated.
            mutating = action not in ("protect_never_touch", "alert_and_secure",
                                      "flag_for_archive_review", "review_delete_empty")
            permitted = not (mutating and forbidden & {"move", "rename", "archive"})
            hits.append(SymptomHit(sid, cat, name, sev, action, evidence, permitted))
    # severity order
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    hits.sort(key=lambda h: order.get(h.severity, 9))
    return hits
