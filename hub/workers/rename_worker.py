"""Rename suggestion and execution worker."""
from __future__ import annotations

import re
from pathlib import Path

SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def suggest_rename(path: str, classification: dict[str, object], hash_result: dict[str, object]) -> dict[str, object]:
    source = Path(path)
    stem = SAFE_CHARS.sub("_", source.stem).strip("._-") or "file"
    label = str(classification.get("label", "unknown"))
    digest = str(hash_result["digest"])[:12]
    target = source.with_name(f"{stem}__{label}__{digest}{source.suffix.lower()}")
    confidence = min(float(classification.get("confidence", 0.0)), 0.95)
    return {"source_path": str(source), "target_path": str(target), "confidence": confidence, "strategy": "stem_label_hash"}


def execute_rename(suggestion: dict[str, object]) -> dict[str, object]:
    source = Path(str(suggestion["source_path"]))
    target = Path(str(suggestion["target_path"]))
    if not source.exists():
        raise FileNotFoundError(source)
    if target.exists():
        raise FileExistsError(target)
    source.rename(target)
    return {"source_path": str(source), "target_path": str(target), "renamed": True}
