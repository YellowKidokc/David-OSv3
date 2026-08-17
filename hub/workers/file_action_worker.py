"""Execute explicit file actions requested through the local control-plane API."""
from __future__ import annotations

import os
import shutil
from pathlib import Path


def execute_file_action(payload: dict[str, object]) -> dict[str, object]:
    action = str(payload["action"])
    if action == "write_text":
        return _write_text(payload, append=False)
    if action == "append_text":
        return _write_text(payload, append=True)
    if action == "touch":
        return _touch(payload)
    if action == "copy":
        return _copy(payload)
    if action == "move":
        return _move(payload)
    if action == "archive":
        return _archive(payload)
    if action == "delete":
        return _delete(payload)
    if action == "open":
        return _open(payload)
    raise ValueError(f"unsupported file action: {action}")


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
    text = str(payload.get("text", ""))
    encoding = str(payload.get("encoding", "utf-8"))
    _ensure_parent(target, payload)
    mode = "a" if append else "w"
    with target.open(mode, encoding=encoding, newline="") as handle:
        handle.write(text)
    return {"action": "append_text" if append else "write_text", "target_path": str(target), "bytes_written": len(text.encode(encoding))}


def _touch(payload: dict[str, object]) -> dict[str, object]:
    target = _target(payload)
    _ensure_parent(target, payload)
    target.touch(exist_ok=bool(payload.get("exist_ok", True)))
    return {"action": "touch", "target_path": str(target), "exists": target.exists()}


def _copy(payload: dict[str, object]) -> dict[str, object]:
    source = _source(payload)
    target = _target(payload)
    if not source.exists():
        raise FileNotFoundError(source)
    if target.exists() and not bool(payload.get("overwrite", False)):
        raise FileExistsError(target)
    _ensure_parent(target, payload)
    shutil.copy2(source, target)
    return {"action": "copy", "source_path": str(source), "target_path": str(target), "copied": True}


def _move(payload: dict[str, object]) -> dict[str, object]:
    source = _source(payload)
    target = _target(payload)
    if not source.exists():
        raise FileNotFoundError(source)
    if target.exists() and not bool(payload.get("overwrite", False)):
        raise FileExistsError(target)
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
    source = _source(payload)
    if not source.exists():
        raise FileNotFoundError(source)
    if source.is_dir():
        source.rmdir()
    else:
        source.unlink()
    return {"action": "delete", "source_path": str(source), "deleted": True}


def _open(payload: dict[str, object]) -> dict[str, object]:
    source = _source(payload)
    if not source.exists():
        raise FileNotFoundError(source)
    if os.name != "nt":
        raise OSError("open action is only implemented with os.startfile on Windows")
    os.startfile(str(source))  # type: ignore[attr-defined]
    return {"action": "open", "source_path": str(source), "started": True}
