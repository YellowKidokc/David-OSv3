"""# fis-op: dec
Conservative name normalizer — PROPOSES a clean name, never applies it.

Chain: lowercase · spaces->underscore · strip junk · small typo map · collapse.
Ported spirit of fis_normalize.py. Returns the proposal string only.
"""
from __future__ import annotations

import re
from pathlib import Path

TYPO = {"teh": "the", "seperate": "separate", "recieve": "receive",
        "fisics": "physics", "adn": "and", "waht": "what"}


def propose(name: str) -> str:
    p = Path(name)
    stem, ext = p.stem, p.suffix.lower()
    s = stem.lower()
    s = re.sub(r"\((\d+)\)", r"_\1", s)          # (3) -> _3
    s = re.sub(r"[^\w]+", "_", s)                # non-word -> _
    s = re.sub(r"_+", "_", s).strip("_")          # collapse
    words = [TYPO.get(w, w) for w in s.split("_")]
    s = "_".join(w for w in words if w)
    return f"{s or 'file'}{ext}"
