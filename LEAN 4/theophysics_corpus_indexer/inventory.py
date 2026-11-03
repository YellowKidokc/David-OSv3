"""Read-only file scanner and hasher."""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Iterator

from config import INDEX_EXTS, SKIP_DIRS, SOURCE_ROOTS

logger = logging.getLogger(__name__)


def _norm(path: str) -> str:
    return path.replace("\\", "/").lower()


def _hash_only(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _hash_and_sample(path: str, sample_bytes: int | None = 8192) -> tuple[str, str]:
    """Return (sha256, text_sample). For .lean set sample_bytes=None to read all."""
    h = hashlib.sha256()
    sample = bytearray()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
            if sample_bytes is None or len(sample) < sample_bytes:
                take = chunk if sample_bytes is None else chunk[: max(0, sample_bytes - len(sample))]
                sample.extend(take)
    return h.hexdigest(), sample.decode("utf-8", errors="ignore")


def _read_sample(path: str, sample_bytes: int = 8192) -> str:
    try:
        with open(path, "rb") as f:
            data = f.read(sample_bytes)
        return data.decode("utf-8", errors="ignore")
    except OSError:
        return ""


def scan_roots(
    roots: list[str] = SOURCE_ROOTS,
    skip_dirs: set[str] = SKIP_DIRS,
    exts: set[str] = INDEX_EXTS,
    manifest: dict[str, dict[str, Any]] | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield file records from all source roots.

    If a file's absolute path matches a manifest NewPath, the manifest hash is
    used instead of recomputing it.
    """
    manifest = manifest or {}
    # Build a path -> sha lookup from the manifest.
    manifest_by_path: dict[str, str] = {
        _norm(entry["new_path"]): sha for sha, entry in manifest.items() if entry.get("new_path")
    }

    for root in roots:
        if not os.path.isdir(root):
            logger.warning("Source root missing: %s", root)
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in exts:
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    size = os.path.getsize(path)
                    mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
                except OSError as exc:
                    logger.warning("Cannot stat %s: %s", path, exc)
                    continue

                norm_path = _norm(path)
                manifest_entry = manifest.get(manifest_by_path.get(norm_path)) if norm_path in manifest_by_path else None
                if manifest_entry is not None:
                    sha256 = manifest_entry["hash"]
                    # Only .lean files need full content for declaration parsing/classification.
                    text = _read_sample(path, sample_bytes=None if ext == ".lean" else 0)
                else:
                    if ext == ".lean":
                        sha256, text = _hash_and_sample(path, sample_bytes=None)
                    else:
                        # Non-lean files are hashed; content is not read for classification
                        # (the v1 keyword rules target Lean declarations).
                        sha256 = _hash_only(path)
                        text = ""

                yield {
                    "path": path,
                    "sha256": sha256,
                    "ext": ext,
                    "size": size,
                    "mtime": mtime,
                    "text": text,
                    "manifest_entry": manifest_entry,
                }
