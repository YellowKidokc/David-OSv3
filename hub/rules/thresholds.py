"""Deterministic thresholds for v1 review decisions."""
from __future__ import annotations

from pathlib import Path

from hub.config.folder_profiles import FolderProfile

AUTO_APPROVE_RENAME_CONFIDENCE = 0.98
RISKY_SUFFIXES = {".exe", ".dll", ".sh", ".bat", ".cmd", ".ps1"}


def rename_requires_review(
    suggestion: dict[str, object],
    *,
    folder_profile: FolderProfile | None = None,
) -> tuple[bool, str]:
    if folder_profile and folder_profile.protected:
        return True, "protected_folder"
    if folder_profile and folder_profile.review_only:
        return True, "folder_review_only"

    threshold = AUTO_APPROVE_RENAME_CONFIDENCE
    if folder_profile:
        threshold = float(folder_profile.thresholds.get("auto_approve_rename_confidence", threshold))

    confidence = float(suggestion.get("confidence", 0.0))
    source = Path(str(suggestion.get("source_path", "")))
    target = Path(str(suggestion.get("target_path", "")))
    if source.suffix.lower() in RISKY_SUFFIXES:
        return True, "risky_file_type"
    if target.exists():
        return True, "target_exists"
    if confidence < threshold:
        return True, "low_confidence"
    return False, "auto_approved_threshold"
