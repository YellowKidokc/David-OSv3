"""Safe workflow model for the David-OS v3 FIS control surface.

This module deliberately separates preview data from execution.  A workflow may
index source files into SQLite, but no action here renames, moves, overwrites, or
deletes a source file.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_TARGET = Path(r"\\192.168.2.50\g_github\D_DRIVE_FULL\GitHub\faiththruphysics-site-data")


@dataclass(frozen=True)
class WorkflowAction:
    key: str
    label: str
    availability: str
    stage: str
    mutates_source: bool = False


ACTIONS = (
    WorkflowAction("scan", "Scan / index", "available", "apply"),
    WorkflowAction("tag", "Semantic and format tagging", "available", "apply"),
    WorkflowAction("classify", "FIS classification / review", "available", "preview"),
    WorkflowAction("name", "Master Equation naming", "proposal-only", "preview"),
    WorkflowAction("duplicates", "Duplicate-family review", "proposal-only", "preview"),
    WorkflowAction("canon", "Canon-status review", "proposal-only", "preview"),
)


def resolve_scope(root: Path, mode: str, selected: Iterable[Path] = ()) -> list[Path]:
    """Resolve a bounded scope without following selections outside *root*."""
    root = root.resolve()
    if mode in {"all", "current"}:
        return [root] if root.is_dir() else []
    result: list[Path] = []
    for item in selected:
        candidate = item.resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.exists() and candidate not in result:
            result.append(candidate)
    return result


def build_preview(root: Path, mode: str, selected: Iterable[Path], action_keys: Iterable[str]) -> dict:
    scope = resolve_scope(root, mode, selected)
    wanted = set(action_keys)
    actions = [a for a in ACTIONS if a.key in wanted]
    return {
        "root": str(root),
        "scope_mode": mode,
        "scope": [str(p) for p in scope],
        "actions": [asdict(a) for a in actions],
        "source_mutation": False,
        "notice": "Preview only. No source file will be renamed, moved, overwritten, or deleted.",
    }


def applyable_action_keys(preview: dict) -> set[str]:
    """Only implemented, non-source-mutating actions cross the Apply gate."""
    return {
        action["key"] for action in preview.get("actions", [])
        if action["availability"] == "available" and not action["mutates_source"]
    }
