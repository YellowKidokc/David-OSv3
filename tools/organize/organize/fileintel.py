"""File Intelligence client for the Organize GUI.

This talks to the FIS (File Intelligence Station) REST API, which is the
documented integration seam ("Any system can pipe data in"). FIS itself owns
the NLP engines, the preference kernel (PPK) bridge, and Postgres; we only
speak HTTP to it so the GUI stays light and never imports that stack.

Contract (from fis/api.py):
    GET  /health   -> {"status": "ok", "service": "fis"}
    POST /classify {"path": <file>} -> {original_name, proposed_name,
                                         confidence, status, file_id, ...}
    POST /approve  {"file_id": <id>} -> {"status": "approved", "new_name": ...}

When FIS is unreachable we fall back to a dumb offline name cleanup so the
spreadsheet is still usable. Offline rows are clearly marked source="offline"
and carry confidence 0 -- they are NOT intelligence, just tidy-up.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

FIS_DEFAULT_URL = "http://localhost:8420"

# Mirror fis/pipeline.py thresholds so the GUI can colour rows the same way the
# station would route them: >=85 auto, >=50 pending, otherwise kickout.
AUTO_THRESHOLD = 85.0
PROPOSE_THRESHOLD = 50.0


class FISClient:
    def __init__(self, base_url: str = FIS_DEFAULT_URL, timeout: float = 60.0) -> None:
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str) -> Any:
        req = urllib.request.Request(self.base + path, method="GET")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post(self, path: str, payload: Dict[str, Any]) -> Any:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base + path,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def health(self) -> bool:
        """True only if a real FIS service answers (not just any HTTP server)."""
        try:
            data = self._get("/health")
        except Exception:
            return False
        return isinstance(data, dict) and data.get("status") == "ok" and data.get("service") == "fis"

    def classify(self, file_path: str) -> Dict[str, Any]:
        return self._post("/classify", {"path": str(file_path)})

    def approve(self, file_id: Any) -> Dict[str, Any]:
        return self._post("/approve", {"file_id": file_id})


def slugify(stem: str, maxlen: int = 48) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", stem.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    slug = slug[:maxlen].rstrip("_")
    return slug or "file"


def offline_proposal(file_path: str) -> Dict[str, Any]:
    """A basic, honest name cleanup used only when FIS is unavailable."""
    path = Path(file_path)
    proposed = slugify(path.stem) + path.suffix.lower()
    return {
        "original_name": path.name,
        "file_path": str(path),
        "proposed_name": proposed,
        "confidence": 0.0,
        "status": "offline",
        "file_id": None,
        "source": "offline",
        "error": None,
    }


def row_from_fis(result: Dict[str, Any], file_path: str) -> Dict[str, Any]:
    """Normalise a FIS /classify response into a spreadsheet row."""
    path = Path(file_path)
    error = result.get("error")
    proposed = result.get("proposed_name") or ""
    if result.get("status") == "duplicate":
        proposed = proposed or "(duplicate — already known)"
    return {
        "original_name": result.get("original_name", path.name),
        "file_path": str(path),
        "proposed_name": proposed,
        "confidence": float(result.get("confidence", 0.0) or 0.0),
        "status": result.get("status", "error" if error else "?"),
        "file_id": result.get("file_id"),
        "source": "fis",
        "error": error,
    }


def confidence_band(status: str, confidence: float) -> str:
    """Bucket a row for colouring: 'auto', 'pending', 'low', or 'offline'."""
    if status == "offline":
        return "offline"
    if status in {"auto"} or confidence >= AUTO_THRESHOLD:
        return "auto"
    if status in {"pending"} or confidence >= PROPOSE_THRESHOLD:
        return "pending"
    return "low"  # kickout / duplicate / needs NLP / no text


def apply_local_rename(file_path: str, proposed_name: str) -> Optional[str]:
    """Rename on disk without FIS (offline apply). Returns the final name."""
    src = Path(file_path)
    if not src.exists() or not proposed_name.strip():
        return None
    target = src.parent / proposed_name
    if target == src:
        return src.name
    stem, ext = target.stem, target.suffix
    counter = 1
    while target.exists():
        target = src.parent / f"{stem}_{counter}{ext}"
        counter += 1
    src.rename(target)
    return target.name
