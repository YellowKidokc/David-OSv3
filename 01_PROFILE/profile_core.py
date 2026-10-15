#!/usr/bin/env python3
"""profile_core — headless heart of the 01_PROFILE wizard.

Pure stdlib. Everything except write_profile is a pure function, so the GUI stays
thin and the Rust port can mirror it. write_profile is the ONLY disk write, called
once, when the user confirms.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from collections import Counter
from pathlib import Path

QUESTIONNAIRE = "onboarding_questions.v1.json"
MARKER = ".folder.fmeta"

# questions the user always sees, no matter how confident the suggestion
ALWAYS_SHOW = {"do_not_touch", "important_files", "sensitive_classes",
               "public_private_boundary", "automation_comfort", "allowed_roots_first"}

PROJECT_MARKERS = {".git", "pyproject.toml", "package.json", "cargo.toml", "requirements.txt"}


def load_questionnaire(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def scan_evidence(root) -> dict:
    """Read-only look at a folder. Returns plain JSON-shaped facts."""
    root = Path(root)
    names = {p.name.lower() for p in root.iterdir()} if root.is_dir() else set()
    exts = Counter(p.suffix.lower() for p in root.rglob("*") if p.is_file())
    return {
        "has_obsidian": ".obsidian" in names,
        "has_project_markers": bool(names & PROJECT_MARKERS),
        "has_api_records": any(p.is_dir() and p.name == "_API" for p in root.iterdir()) if root.is_dir() else False,
        "top_extensions": exts.most_common(8),
        "file_count": sum(exts.values()),
    }


def suggest_answers(questionnaire: dict, evidence: dict) -> dict:
    """question_id -> {"value": ..., "confidence": 0..1, "source": "evidence"|"default"}"""
    out: dict = {}
    for q in questionnaire.get("core_questions", []):
        qid = q["id"]
        if q.get("default") is not None:
            out[qid] = {"value": q["default"], "confidence": 0.5, "source": "default"}
    if evidence.get("has_obsidian"):
        out.setdefault("primary_domains", {})["value"] = ["research"]
        out["primary_domains"].update(confidence=0.8, source="evidence")
    if evidence.get("has_project_markers"):
        out["project_roots"] = {"value": ["this folder"], "confidence": 0.9, "source": "evidence"}
    if evidence.get("has_api_records"):
        out["primary_domains"] = {"value": ["research"], "confidence": 0.7, "source": "evidence"}
    return out


def build_profile(root, answers: dict, questionnaire: dict) -> dict:
    """Map questionnaire answers onto folder_profiles.json fields (Task 2 shape)."""
    env = answers.get("environment_type", "mixed")
    comfort = answers.get("automation_comfort", "approval_required")
    floor = {"report_only": "preview_only", "suggest_actions": "suggest_only",
             "approval_required": "approval_required", "require_approval": "approval_required",
             "allow_safe_rules": "auto_after_threshold"}.get(comfort, "approval_required")
    profile = {
        "path": str(root),
        "folder_role": env,
        "review_only": floor != "auto_after_threshold",
        "protected": bool(answers.get("sensitive_classes")),
        "approval_floor": floor,
        "thresholds": {"auto_approve_rename_confidence": 0.98},
        "routing_hints": {},
        "parser_preferences": ["deterministic"],
    }
    dnt = answers.get("do_not_touch")
    items = ([x.strip() for x in dnt.split(",")] if isinstance(dnt, str) else list(dnt or []))
    items = [x for x in items if x and x.lower() not in ("none", "nothing", "n/a", "no", "-")]
    if items:
        # a path/pattern list, not a blanket block on the folder — the gate reads
        # routing_hints when per-path do-not-touch enforcement lands
        profile["routing_hints"]["do_not_touch"] = items
    return profile


def write_profile(root, profile: dict, profiles_path, answers: dict, evidence: dict) -> None:
    """The only writer. Appends/updates the registry entry (atomically, deduped
    case-insensitively); writes the marker unless the folder is a project root
    (marker contract: never write inside those)."""
    root = Path(root)
    profiles_path = Path(profiles_path)
    data = {"profiles": []}
    if profiles_path.exists():
        try:
            data = json.loads(profiles_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"folder profile registry is corrupt: {profiles_path}: {e}") from e
    root_key = os.path.normcase(str(root))
    data["profiles"] = [p for p in data["profiles"]
                        if os.path.normcase(str(p.get("path", ""))) != root_key]
    data["profiles"].append(profile)
    tmp = profiles_path.with_name(profiles_path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, profiles_path)

    names = {p.name.lower() for p in root.iterdir()} if root.is_dir() else set()
    if not (names & PROJECT_MARKERS):
        marker = {"schema": "fis.folder_profile/1.0",
                  "profiled_at": dt.datetime.now().isoformat(timespec="seconds"),
                  "folder_role": profile.get("folder_role", "general"),
                  "answers": answers, "evidence": evidence}
        (root / MARKER).write_text(json.dumps(marker, indent=1) + "\n", encoding="utf-8")
