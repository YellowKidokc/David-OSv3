"""# fis-op: sim
dedupe — the independent dedupe primitive. Everything dedupe needs.

Exact-content grouping by SHA-256, keep-newest, propose quarantining the rest.
Near-duplicate (MinHash/LSH) is the documented port target from fis_near_dup.
Returns (keepers, proposals). Read-only.

    dedupe(objects) -> (keepers, [proposal])
"""
from __future__ import annotations

import hashlib
from ..model import ObjectRecord

HASH_CAP = 16_000_000


def _sha(path: str) -> str | None:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def dedupe(objects: list[ObjectRecord], keep: str = "newest"):
    groups: dict[str, list[ObjectRecord]] = {}
    for o in objects:
        if o.size and o.size <= HASH_CAP:
            h = _sha(o.full_path)
            if h:
                groups.setdefault(h, []).append(o)
    keepers, proposals = [], []
    for group in groups.values():
        if len(group) == 1:
            keepers.append(group[0]); continue
        chooser = (max if keep == "newest" else min)
        keeper = chooser(group, key=lambda x: x.modified or 0)
        keepers.append(keeper)
        for o in group:
            if o is not keeper:
                proposals.append({"action": "quarantine_duplicate",
                                  "path": o.full_path, "keeper": keeper.full_path})
    # objects too large to hash are kept as-is
    hashed = {o.object_id for g in groups.values() for o in g}
    keepers += [o for o in objects if o.object_id not in hashed]
    return keepers, proposals
