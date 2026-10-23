"""Execute explicit file actions requested through the local control-plane API.

Every mutating action is:
  * refused inside a protected root (engine.path_write_policy),
  * a no-op when ``dry_run`` is set — it reports what it would do,
  * journalled to ``runs/file_actions/journal-<date>.jsonl`` so it can be undone.

``undo`` replays the journal backwards. This is the v2 ``phase2_merge`` discipline
(dry run first, never lose the old location) applied to every action, not one job.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

try:
    # Always the package module, never a second copy imported as a bare name:
    # two copies mean two PROTECTED_ROOTS lists and a guard that silently passes.
    from engine.path_write_policy import require_write_allowed
except Exception:  # policy module optional for minimal installs
    def require_write_allowed(path):  # type: ignore[misc]
        return None

JOURNAL_DIR = REPO / "runs" / "file_actions"
REVERSIBLE = {"move", "archive", "rename"}


def journal_path(when: datetime | None = None) -> Path:
    return JOURNAL_DIR / f"journal-{(when or datetime.now()).strftime('%Y-%m-%d')}.jsonl"


def _record(entry: dict[str, object]) -> None:
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    entry = {"ts": time.time(), "when": datetime.now().isoformat(timespec="seconds"), **entry}
    with journal_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_journal(day: datetime | None = None) -> list[dict[str, object]]:
    path = journal_path(day)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def execute_file_action(payload: dict[str, object]) -> dict[str, object]:
    action = str(payload["action"])
    if action == "undo":
        return undo_last(payload)
    handlers = {
        "write_text": lambda: _write_text(payload, append=False),
        "append_text": lambda: _write_text(payload, append=True),
        "touch": lambda: _touch(payload),
        "copy": lambda: _copy(payload),
        "move": lambda: _move(payload),
        "rename": lambda: _move(payload),
        "archive": lambda: _archive(payload),
        "delete": lambda: _delete(payload),
        "open": lambda: _open(payload),
    }
    if action not in handlers:
        raise ValueError(f"unsupported file action: {action}")
    result = handlers[action]()
    if action != "open" and not result.get("dry_run"):
        _record({k: v for k, v in result.items() if k != "text"})
    return result


def _dry(payload: dict[str, object]) -> bool:
    return bool(payload.get("dry_run", False))


def _target(payload: dict[str, object]) -> Path:
    value = payload.get("target_path") or payload.get("source_path")
    if not value:
        raise ValueError("target_path or source_path is required")
    return Path(str(value))


def _source(payload: dict[str, object]) -> Path:
    value = payload.get("source_path")
    if not value:
        raise ValueError("source_path is required")
    return Path(str(value))


def _ensure_parent(path: Path, payload: dict[str, object]) -> None:
    if bool(payload.get("create_parent_dirs", True)):
        path.parent.mkdir(parents=True, exist_ok=True)


def _write_text(payload: dict[str, object], *, append: bool) -> dict[str, object]:
    target = _target(payload)
    require_write_allowed(target)
    text = str(payload.get("text", ""))
    encoding = str(payload.get("encoding", "utf-8"))
    action = "append_text" if append else "write_text"
    if _dry(payload):
        return {"action": action, "target_path": str(target), "dry_run": True,
                "bytes_written": len(text.encode(encoding))}
    _ensure_parent(target, payload)
    with target.open("a" if append else "w", encoding=encoding, newline="") as handle:
        handle.write(text)
    return {"action": action, "target_path": str(target), "bytes_written": len(text.encode(encoding))}


def _touch(payload: dict[str, object]) -> dict[str, object]:
    target = _target(payload)
    require_write_allowed(target)
    if _dry(payload):
        return {"action": "touch", "target_path": str(target), "dry_run": True}
    _ensure_parent(target, payload)
    target.touch(exist_ok=bool(payload.get("exist_ok", True)))
    return {"action": "touch", "target_path": str(target), "exists": target.exists()}


def _copy(payload: dict[str, object]) -> dict[str, object]:
    source, target = _source(payload), _target(payload)
    require_write_allowed(target)
    if not source.exists():
        raise FileNotFoundError(source)
    if target.exists() and not bool(payload.get("overwrite", False)):
        raise FileExistsError(target)
    if _dry(payload):
        return {"action": "copy", "source_path": str(source), "target_path": str(target), "dry_run": True}
    _ensure_parent(target, payload)
    shutil.copy2(source, target)
    return {"action": "copy", "source_path": str(source), "target_path": str(target), "copied": True}


def _move(payload: dict[str, object]) -> dict[str, object]:
    source, target = _source(payload), _target(payload)
    require_write_allowed(target)
    require_write_allowed(source)
    if not source.exists():
        raise FileNotFoundError(source)
    if target.exists() and not bool(payload.get("overwrite", False)):
        raise FileExistsError(target)
    if _dry(payload):
        return {"action": "move", "source_path": str(source), "target_path": str(target), "dry_run": True}
    _ensure_parent(target, payload)
    shutil.move(str(source), str(target))
    return {"action": "move", "source_path": str(source), "target_path": str(target), "moved": True}


def _archive(payload: dict[str, object]) -> dict[str, object]:
    source = _source(payload)
    archive_root = _target(payload)
    target = archive_root / source.name if archive_root.suffix == "" else archive_root
    result = _move({**payload, "target_path": str(target)})
    result["action"] = "archive"
    return result


def _delete(payload: dict[str, object]) -> dict[str, object]:
    """Deletion is a move into the run's recycle folder, so it stays reversible."""
    source = _source(payload)
    require_write_allowed(source)
    if not source.exists():
        raise FileNotFoundError(source)
    if bool(payload.get("permanent", False)):
        if _dry(payload):
            return {"action": "delete", "source_path": str(source), "dry_run": True, "permanent": True}
        source.rmdir() if source.is_dir() else source.unlink()
        return {"action": "delete", "source_path": str(source), "deleted": True, "permanent": True}
    recycle = Path(str(payload.get("recycle_dir") or (JOURNAL_DIR / "recycled" / datetime.now().strftime("%Y-%m-%d"))))
    target = recycle / source.name
    result = _move({**payload, "target_path": str(target), "overwrite": True})
    result["action"] = "delete"
    return result


def _open(payload: dict[str, object]) -> dict[str, object]:
    source = _source(payload)
    if not source.exists():
        raise FileNotFoundError(source)
    if os.name != "nt":
        raise OSError("open action is only implemented with os.startfile on Windows")
    os.startfile(str(source))  # type: ignore[attr-defined]
    return {"action": "open", "source_path": str(source), "started": True}


def undo_last(payload: dict[str, object] | None = None) -> dict[str, object]:
    """Reverse the most recent reversible actions, newest first."""
    payload = payload or {}
    count = int(payload.get("count", 1))
    dry = _dry(payload)
    entries = [e for e in read_journal(payload.get("day")) if e.get("action") in REVERSIBLE and not e.get("undone")]
    picked, restored = entries[-count:][::-1], []
    for entry in picked:
        source, target = Path(str(entry["source_path"])), Path(str(entry["target_path"]))
        if not target.exists():
            restored.append({"source_path": str(source), "status": "missing"})
            continue
        if dry:
            restored.append({"source_path": str(source), "status": "would_restore"})
            continue
        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(source))
        _record({"action": "undo", "source_path": str(target), "target_path": str(source), "undone": True})
        restored.append({"source_path": str(source), "status": "restored"})
    return {"action": "undo", "dry_run": dry, "count": len(restored), "restored": restored}
