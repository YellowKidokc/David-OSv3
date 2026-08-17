"""Normalize watcher-specific file events into hub events."""
from __future__ import annotations

from pathlib import Path
from typing import Any

VALID_EVENTS = {"created", "modified", "moved", "deleted"}


def normalize_file_event(raw_event: dict[str, Any], *, source: str = "watcher") -> dict[str, Any]:
    event_type = str(raw_event.get("event_type") or raw_event.get("type") or "created").lower()
    if event_type not in VALID_EVENTS:
        event_type = "modified"
    path = raw_event.get("path") or raw_event.get("src_path")
    if not path:
        raise ValueError("file event requires path or src_path")
    normalized = {
        "source": source,
        "event_type": event_type,
        "path": str(Path(path)),
        "is_directory": bool(raw_event.get("is_directory", False)),
    }
    if raw_event.get("dest_path"):
        normalized["dest_path"] = str(Path(raw_event["dest_path"]))
    return normalized
