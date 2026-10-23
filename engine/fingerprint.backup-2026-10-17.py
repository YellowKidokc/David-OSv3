"""
fingerprint.py — stable file identity.

Identity is content + size + timestamps, NOT the name. This is what lets the
system tell a rename (same hash, new path) from a copy (same hash, extra path)
from a modification (same path, new hash).
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def sha256_file(path: str, chunk: int = 1 << 20) -> str:
    """Streaming sha256 so large files don't blow memory."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _iso(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().isoformat(timespec="seconds")
    except Exception:
        return ""


def fingerprint(path: str) -> dict:
    """Return the minimal stable identity for a file."""
    p = Path(path)
    st = p.stat()
    return {
        "path": str(p),
        "name": p.name,
        "extension": p.suffix.lower(),
        "size_bytes": st.st_size,
        "sha256": sha256_file(str(p)),
        "modified_at": _iso(st.st_mtime),
        "created_at": _iso(getattr(st, "st_ctime", st.st_mtime)),
        "mtime": st.st_mtime,
    }


_TOKEN = re.compile(r"\w{3,}")


def simhash(text: str, hashbits: int = 64) -> str:
    """Cheap simhash for near-duplicate detection (hamming distance over the bits)."""
    v = [0] * hashbits
    for token in _TOKEN.findall(text.lower()):
        hv = int(hashlib.md5(token.encode()).hexdigest(), 16)
        for i in range(hashbits):
            v[i] += 1 if hv & (1 << i) else -1
    out = 0
    for i in range(hashbits):
        if v[i] > 0:
            out |= (1 << i)
    return format(out, f"0{hashbits}b")


def hamming(a: str, b: str) -> int:
    return sum(c1 != c2 for c1, c2 in zip(a, b)) if a and b else 64
