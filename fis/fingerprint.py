"""
fingerprint.py — stable file identity + near-duplicate evidence.

What this file DOES:   computes identity (size, dates, sha256) and similarity evidence (simhash, shingles, Jaccard).
What it does NOT do:   decide rename vs copy vs edit. That comparison lives in the caller (inventory_scan / consolidate_scan),
                       which compares these records across paths and over time.

Two near-duplicate methods:
  simhash()      ORIGINAL (kept unchanged; inventory_scan and consolidate_scan compare it at hamming <= 4).
                 Known faults, measured 2026-10-17 (tests/test_fingerprint.py): blind to word order, counts common
                 words, every empty file "matches" every other, ~18% false matches among documents sharing vocabulary.
  near_dup()     NEW, two-step: simhash_v2 finds candidates cheaply, shingle Jaccard confirms. Refuses texts too short
                 to compare. Returns its evidence, not just a yes/no, so every verdict can be audited.
Thresholds are provisional until calibrated on real pairs (gold set) — see CALIBRATION below.
Original file preserved as fingerprint.backup-2026-10-17.py.
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


# ---------------------------------------------------------------- ORIGINAL (unchanged; superseded by near_dup)
_TOKEN = re.compile(r"\w{3,}")


def simhash(text: str, hashbits: int = 64) -> str:
    """ORIGINAL cheap simhash (hamming distance over the bits). Kept for compatibility; see module docstring for faults."""
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


# ---------------------------------------------------------------- NEW
STOPWORDS = frozenset("""the and for that with this from are was were has have had not but its into their there than then they
them his her which when what who will would can could been also more most such only other over our your you about
these those some any each just like very upon onto within without between""".split())
MIN_WORDS = 30          # below this, a text is too short to compare honestly -> verdict TOO_SHORT
SHINGLE = 3             # 3-word sequences keep word order
# CALIBRATION (provisional, set from synthetic tests 2026-10-17; re-tune on a gold set of real pairs):
CANDIDATE_HAMMING = 24  # simhash_v2 distance at or under this -> worth confirming
DUP_JACCARD = 0.80      # shingle overlap at or above -> NEAR_DUPLICATE
RELATED_JACCARD = 0.50  # at or above -> RELATED_VERSION (keep both, flag for a human)


def content_words(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]


def shingles(text: str, k: int = SHINGLE) -> set[str]:
    w = content_words(text)
    return {" ".join(w[i:i + k]) for i in range(len(w) - k + 1)}


def simhash_v2(text: str, hashbits: int = 64, k: int = SHINGLE) -> Optional[int]:
    """Shingle simhash. None when the text is too short to compare (never a fake match)."""
    if len(content_words(text)) < MIN_WORDS:
        return None
    v = [0] * hashbits
    for g in shingles(text, k):
        hv = int(hashlib.md5(g.encode()).hexdigest(), 16)
        for i in range(hashbits):
            v[i] += 1 if (hv >> i) & 1 else -1
    return sum(1 << i for i in range(hashbits) if v[i] > 0)


def hamming_v2(a: Optional[int], b: Optional[int]) -> int:
    return 64 if a is None or b is None else bin(a ^ b).count("1")


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a or b) else 0.0


def near_dup(text_a: str, text_b: str) -> dict:
    """Two-step verdict WITH its evidence. Verdicts: EXACT | NEAR_DUPLICATE | RELATED_VERSION | DIFFERENT | TOO_SHORT."""
    ev = {"words_a": len(content_words(text_a)), "words_b": len(content_words(text_b)),
          "hamming_v2": None, "jaccard": None, "thresholds": {"candidate_hamming": CANDIDATE_HAMMING,
          "dup_jaccard": DUP_JACCARD, "related_jaccard": RELATED_JACCARD, "min_words": MIN_WORDS}}
    if text_a == text_b:
        return {"verdict": "EXACT", **ev}
    if min(ev["words_a"], ev["words_b"]) < MIN_WORDS:
        return {"verdict": "TOO_SHORT", **ev}
    ev["hamming_v2"] = hamming_v2(simhash_v2(text_a), simhash_v2(text_b))
    if ev["hamming_v2"] > CANDIDATE_HAMMING:
        return {"verdict": "DIFFERENT", **ev}
    ev["jaccard"] = round(jaccard(shingles(text_a), shingles(text_b)), 4)
    if ev["jaccard"] >= DUP_JACCARD:
        return {"verdict": "NEAR_DUPLICATE", **ev}
    if ev["jaccard"] >= RELATED_JACCARD:
        return {"verdict": "RELATED_VERSION", **ev}
    return {"verdict": "DIFFERENT", **ev}


def text_record(text: str) -> dict:
    """Everything worth leaving behind about a text, for sidecars/reports (cheap; no judgments)."""
    w = content_words(text)
    sh = simhash_v2(text)
    return {"chars": len(text), "content_words": len(w), "comparable": sh is not None,
            "simhash_v2": None if sh is None else format(sh, "016x"),
            "simhash_v1": simhash(text), "shingles": len(shingles(text))}
