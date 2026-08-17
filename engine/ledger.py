"""
ledger.py — append-only JSONL event ledger.

Every meaningful thing the pipeline does is appended here as one JSON object per
line. This is the audit trail: it is never rewritten, only appended. SQLite holds
current state; the ledger holds history.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _append(path: Path, record: dict) -> None:
    record = {"ts": _now(), **record}
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # ledger writes must never crash the pipeline
        pass


def log_event(event: str, path: str = "", **extra: Any) -> None:
    """File lifecycle event: scanned, fingerprinted, classified, copy/move/modify..."""
    _append(config.EVENTS_LOG, {"event": event, "path": path, **extra})


def log_rename(action: str, old: str, new: str, **extra: Any) -> None:
    """Rename-plan event: proposed / approved / rejected / applied / rolled_back."""
    _append(config.RENAME_LOG, {"action": action, "old": old, "new": new, **extra})


def log_error(script: str, error: str, **extra: Any) -> None:
    _append(config.ERRORS_LOG, {"script": script, "error": error, **extra})
