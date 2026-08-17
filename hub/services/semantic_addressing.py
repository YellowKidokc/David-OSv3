"""Bridge to the promoted legacy FIS semantic addressing worker."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    configured = os.environ.get("TOP_AI_FIS_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[4]


def _worker_dir() -> Path:
    return _repo_root() / "agents" / "labelers" / "semantic_addressing"


def score_semantic_address(path: str | Path, *, text: str | None = None) -> dict[str, Any]:
    """Score a file or text sample with the old deterministic FIS scorer.

    The promoted worker intentionally lives outside the API package so it can be
    used by CLI/watchers too. This bridge keeps the import local and explicit.
    """
    worker_dir = _worker_dir()
    if not worker_dir.exists():
        raise FileNotFoundError(f"Semantic addressing worker folder not found: {worker_dir}")
    worker_dir_text = str(worker_dir)
    if worker_dir_text not in sys.path:
        sys.path.insert(0, worker_dir_text)

    from semantic_address_worker import score_path  # type: ignore[import-not-found]

    target = Path(path)
    if text is None and not target.exists():
        raise FileNotFoundError(f"Cannot score missing file without text: {target}")
    return score_path(target, text=text)
