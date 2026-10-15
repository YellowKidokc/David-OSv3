"""Find a card's source paper by its `source_file` name, so tagging can read the paper itself.

The AXIOM canon papers were never lost: 47 sit loose at the top of Folders\\AXIOM and 4 at the top of
the canon folder WITHOUT "(1)" (found 2026-10-14). Searched top-level only, in this order; extra
roots can be added with SOURCE_PAPER_ROOTS (";"-separated). Never writes anything.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

ROOTS = [
    "//192.168.2.50/h_hp/Desktop/Folders/AXIOM",
    "//192.168.2.50/h_hp/Desktop/Folders/AXIOM_CLASSIFICATION_CANON_2026-07-25",
]


@lru_cache(maxsize=1)
def _index() -> dict[str, Path]:
    roots = [r for r in os.environ.get("SOURCE_PAPER_ROOTS", "").split(";") if r] + ROOTS
    idx: dict[str, Path] = {}
    for r in roots:
        try:
            for p in Path(r).iterdir():
                if p.is_file():
                    idx.setdefault(p.name.lower(), p)
        except OSError:
            continue
    return idx


def find(source_file: str) -> Path | None:
    return _index().get(Path(source_file.strip().strip('"')).name.lower()) if source_file else None


def excerpt(source_file: str, head: int = 9000, tail: int = 1500) -> str:
    """Start of the paper (where status/version lines live) plus its last lines (conclusions,
    'next steps', open questions). Empty string when the paper can't be found or read."""
    p = find(source_file)
    if not p:
        return ""
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if len(text) <= head + tail:
        return text
    return text[:head] + f"\n\n[… {len(text) - head - tail:,} characters skipped …]\n\n" + text[-tail:]
