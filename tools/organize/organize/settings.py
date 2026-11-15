"""Persistent GUI settings for the Organize desktop app.

Stored as plain JSON at ~/.organize_gui/settings.json so the user's choices
(especially the NLP-escalation confidence threshold) survive restarts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

RENAMING_PROCESSES = ["File Intelligence", "Offline cleanup"]

DEFAULTS: Dict[str, Any] = {
    # below this certainty a file is NOT auto-named; it is routed to NLP/review
    "nlp_threshold": 50,
    # at/above this certainty FIS considers a name safe to auto-apply
    "auto_apply_threshold": 85,
    # which engine proposes names by default
    "renaming_process": "File Intelligence",
}


def settings_path() -> Path:
    return Path.home() / ".organize_gui" / "settings.json"


def _clamp_pct(value: Any, default: int) -> int:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return int(max(0, min(100, value)))


def _normalize(data: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(DEFAULTS)
    for key in DEFAULTS:
        if key in data:
            out[key] = data[key]
    out["nlp_threshold"] = _clamp_pct(out["nlp_threshold"], DEFAULTS["nlp_threshold"])
    out["auto_apply_threshold"] = _clamp_pct(out["auto_apply_threshold"], DEFAULTS["auto_apply_threshold"])
    if out["renaming_process"] not in RENAMING_PROCESSES:
        out["renaming_process"] = DEFAULTS["renaming_process"]
    return out


def load_settings() -> Dict[str, Any]:
    path = settings_path()
    if path.exists():
        try:
            return _normalize(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULTS)


def save_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    data = load_settings()
    data.update(updates)
    data = _normalize(data)
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data
