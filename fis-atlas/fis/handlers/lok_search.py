"""# fis-op: lok
search — the independent search primitive. Everything search needs, nothing else.

Walk one or more roots, read each file's content, score it with a caller-supplied
matcher, and return ranked matches. Generic: the matcher IS the query, so this
one function serves GTQ, "find all invoices", "find scattered projects", etc.
Read-only.

    search(roots, matcher) -> [(ObjectRecord, score)]  ranked high->low
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Callable

from .. import scan
from ..model import ObjectRecord

READABLE = {"markdown", "text", "code", "data"}
SAMPLE = 6000


def _read(path: str, ctype: str) -> str:
    if ctype not in READABLE:
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(SAMPLE)
    except OSError:
        return ""


def search(roots: list[str], matcher: Callable[[str, str], float],
           min_score: float = 0.2, max_files: int = 50000) -> list[tuple[ObjectRecord, float]]:
    """matcher(filename, sampled_text) -> score in [0,1]. Returns ranked matches."""
    out: list[tuple[ObjectRecord, float]] = []
    count = 0
    for root in roots:
        for dp, _dirs, files in os.walk(root):
            for fn in files:
                fp = os.path.join(dp, fn)
                ct = scan.content_type_for(fn, False)
                score = matcher(fn, _read(fp, ct))
                if score >= min_score:
                    try:
                        st = os.stat(fp)
                    except OSError:
                        continue
                    out.append((ObjectRecord(
                        object_id="O-" + hashlib.sha1(fp.encode()).hexdigest()[:12],
                        name=fn, ext=Path(fn).suffix.lower(), full_path=fp, is_dir=False,
                        parent=dp, size=st.st_size, modified=st.st_mtime, content_type=ct), score))
                count += 1
                if count >= max_files:
                    return sorted(out, key=lambda x: x[1], reverse=True)
    return sorted(out, key=lambda x: x[1], reverse=True)
