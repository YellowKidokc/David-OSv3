# fis-op: und
"""Understand (und) — infer role, sensitivity, activity, risk, permission.

Red flags are checked FIRST and fail closed (spec): a programming/system/secret
folder is sealed before any other classification runs.
"""
from __future__ import annotations

import time
from pathlib import Path

from .model import ObjectRecord, FolderRecord

NOW = time.time()
DAY = 86400

PROGRAM_MARKERS = {
    ".git", "package.json", "node_modules", "venv", ".venv", "requirements.txt",
    "cargo.toml", "go.mod", "pom.xml", "tsconfig.json", "pyproject.toml",
    "makefile", "gemfile", "composer.json", "yarn.lock", "package-lock.json",
    "poetry.lock", ".sln", ".csproj",
}
SECRET_PAT = ("secret", "token", "credential", "password", "apikey", "api_key", ".env")
FINANCIAL_PAT = ("tax", "invoice", "receipt", "bank", "statement", "budget", "payroll", "1099", "w2")
LEGAL_PAT = ("contract", "nda", "agreement", "legal", "lawsuit", "deed", "will")
PERSONAL_PAT = ("family", "personal", "medical", "health", "diary", "photo")
BUSINESS_PAT = ("client", "proposal", "report", "meeting", "project")

CODE_TYPES = {"code"}
DOC_TYPES = {"document", "spreadsheet", "presentation", "pdf"}
MEDIA_TYPES = {"image", "video", "audio"}


def _has(patterns, text: str) -> bool:
    t = text.lower()
    return any(p in t for p in patterns)


# ---------------------------------------------------------------- folders
def classify_folder(f: FolderRecord, child_names: list[str], child_objects: list[ObjectRecord]) -> None:
    lower_children = {c.lower() for c in child_names}
    ev = f.evidence
    path_l = f.full_path.lower()

    # 1. PROGRAMMING / PROJECT ROOT -> RED (checked first, fail closed)
    prog_hit = ([m for m in PROGRAM_MARKERS if m in lower_children]
                or [c.name for c in child_objects if c.content_type in CODE_TYPES][:1])
    code_share = _share(child_objects, CODE_TYPES)
    if prog_hit or code_share >= 0.5:
        f.folder_class = "programming"; f.risk = "red"
        f.red_flags.append("program_root")
        f.behaves_like = "project"
        ev.add(f"program markers: {prog_hit}" if prog_hit else f"code files {code_share:.0%}")
        _seal(f); f.class_confidence = 0.9
        _purpose(f, child_objects); return

    # 2. SYSTEM -> RED
    if any(seg in path_l for seg in ("\\windows\\", "\\program files", "\\programdata", "\\appdata")):
        f.folder_class = "system"; f.risk = "red"; f.red_flags.append("system_path")
        ev.add("under a system path"); _seal(f); f.class_confidence = 0.95
        _purpose(f, child_objects); return

    # 3. SECRETS present -> RED (item-level, seal the folder too)
    if any(_has(SECRET_PAT, c.name) for c in child_objects):
        f.folder_class = "mixed"; f.risk = "red"; f.red_flags.append("secrets")
        ev.add("contains secret/credential-looking files"); _seal(f); f.class_confidence = 0.8
        _purpose(f, child_objects); return

    # 4+. non-red classes by dominant content
    doc_share = _share(child_objects, DOC_TYPES)
    media_share = _share(child_objects, MEDIA_TYPES)
    md_share = _share(child_objects, {"markdown"})
    archive_share = _share(child_objects, {"archive"})

    if archive_share >= 0.5:
        f.folder_class, f.behaves_like = "archive", "archive"; ev.add(f"archives {archive_share:.0%}")
    elif md_share >= 0.4:
        f.folder_class, f.behaves_like = "research", "collection"; ev.add(f"markdown {md_share:.0%}")
    elif doc_share >= 0.4:
        f.folder_class, f.behaves_like = "office", "collection"; ev.add(f"documents {doc_share:.0%}")
    elif media_share >= 0.5:
        f.folder_class, f.behaves_like = "media", "collection"; ev.add(f"media {media_share:.0%}")
    elif f.empty:
        f.folder_class, f.behaves_like = "debris", "accidental"; ev.add("empty folder")
    else:
        f.folder_class, f.behaves_like = "mixed", "inbox"; ev.add("no dominant type")

    f.risk = "amber" if _has(FINANCIAL_PAT + LEGAL_PAT, f.full_path) else "green"
    _permit(f)
    f.class_confidence = 0.6 if f.folder_class == "mixed" else 0.75
    _purpose(f, child_objects)


def _share(objs, types: set) -> float:
    if not objs:
        return 0.0
    return sum(1 for o in objs if o.content_type in types) / len(objs)


def _seal(f: FolderRecord):
    f.forbidden_actions = ["move", "rename", "delete", "archive", "publish"]
    f.allowed_actions = ["tag", "report", "protect"]


def _permit(f: FolderRecord):
    if f.risk == "amber":
        f.allowed_actions = ["rename", "tag", "report", "move_with_approval"]
        f.forbidden_actions = ["delete", "publish"]
    else:
        f.allowed_actions = ["rename", "tag", "dedupe", "move_with_approval", "report"]
        f.forbidden_actions = ["delete"]


def _purpose(f: FolderRecord, objs: list[ObjectRecord]):
    """Cheap templated purpose. Upgrade to local NLP (fis_nlp_light) later."""
    n = len(objs)
    top = max(f.type_distribution, key=f.type_distribution.get) if f.type_distribution else "empty"
    f.purpose = f"{f.folder_class} folder — {n} items, mostly {top}; behaves like {f.behaves_like}."


# ---------------------------------------------------------------- objects
def classify_object(o: ObjectRecord, folder: FolderRecord) -> None:
    ev = o.evidence
    text = (o.rel_path or o.name)

    # sensitivity (ancestral context: whole path, not just the name)
    if _has(SECRET_PAT, text):
        o.sensitivity = "secret"; o.risk = "red"; o.red_flags.append("secret")
        ev.add("name/path matches secret pattern")
    elif _has(FINANCIAL_PAT, text):
        o.sensitivity = "financial"; ev.add("financial pattern in path")
    elif _has(LEGAL_PAT, text):
        o.sensitivity = "legal"; ev.add("legal pattern in path")
    elif _has(PERSONAL_PAT, text):
        o.sensitivity = "personal"; ev.add("personal pattern in path")
    elif _has(BUSINESS_PAT, text):
        o.sensitivity = "business"; ev.add("business pattern in path")
    else:
        o.sensitivity = "unknown"

    # detected role
    name_l = o.name.lower()
    if any(k in name_l for k in ("draft", "wip", "untitled", "copy", "(1)", "(2)", "(3)", "temp", "~")):
        o.detected_role = "draft"; ev.add("draft/temp name pattern")
    elif any(k in name_l for k in ("backup", ".bak", ".old", "_old")):
        o.detected_role = "backup"; ev.add("backup name pattern")
    elif any(k in name_l for k in ("export", "dump", "output")):
        o.detected_role = "export"; ev.add("export name pattern")
    elif o.content_type in CODE_TYPES:
        o.detected_role = "project_file"
    elif o.content_type == "markdown":
        o.detected_role = "reference"
    else:
        o.detected_role = "unknown"

    # activity from access/modify age
    ref = o.accessed or o.modified
    if ref:
        age = (NOW - ref) / DAY
        o.activity = ("recently_used" if age < 30 else
                      "inactive" if age < 180 else "abandoned")
        ev.add(f"last touched ~{int(age)}d ago")
    else:
        o.activity = "indeterminate"

    # risk inherits from folder unless already red
    if o.risk != "red":
        o.risk = folder.risk
        o.red_flags = list(folder.red_flags)

    # authorization (independent of certainty!)
    if o.risk == "red":
        o.authorized_actions = ["tag", "report"]
        o.forbidden_actions = ["move", "rename", "delete", "archive"]
        o.proposed_treatment = "protect"
        o.action_confidence = 0.95
    elif o.risk == "amber":
        o.authorized_actions = ["rename", "tag", "report", "move_with_approval"]
        o.forbidden_actions = ["delete"]
        o.proposed_treatment = "review"
        o.action_confidence = 0.5
    else:
        o.authorized_actions = ["rename", "tag", "move_with_approval", "dedupe", "report"]
        o.forbidden_actions = []
        o.proposed_treatment = "rename" if _messy(o.name) else "keep"
        o.action_confidence = 0.7 if _messy(o.name) else 0.4

    # class confidence: how sure are we WHAT it is (separate number)
    o.class_confidence = 0.85 if o.content_type not in ("unknown", "binary") else 0.3
    if o.content_type == "unknown":
        ev.add("unrecognized type — needs review")


def _messy(name: str) -> bool:
    stem = Path(name).stem
    return (" " in stem or stem != stem.lower()
            or any(k in name.lower() for k in ("untitled", "copy", "(1)", "(2)", "(3)", "screenshot", "img_")))
