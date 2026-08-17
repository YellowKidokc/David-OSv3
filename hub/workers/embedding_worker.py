"""Small local embedding utilities for memory search.

This is intentionally provider-free so the hub can vectorize immediately. A real
embedding provider can replace this behind the same repository/API shape later.
"""
from __future__ import annotations

import hashlib
import math
import re

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
DIMENSIONS = 64


def embed_text(text: str, *, dimensions: int = DIMENSIONS) -> list[float]:
    vector = [0.0] * dimensions
    tokens = TOKEN_RE.findall(text.lower())
    if not tokens:
        return vector
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [round(value / norm, 6) for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))
