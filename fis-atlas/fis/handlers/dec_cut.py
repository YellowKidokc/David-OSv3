"""# fis-op: dec
cut — collect a set of files INTO one target folder. Everything "cut" needs.

Flattens into the target (collision-safe), returns move/copy PROPOSALS. Never
touches disk. `mode` = "move" (cut) or "copy" (leave originals).

    cut(objects, target) -> [proposal]
"""
from __future__ import annotations

import os
from ..model import ObjectRecord


def cut(objects: list[ObjectRecord], target: str, mode: str = "move") -> list[dict]:
    proposals, seen = [], {}
    for o in objects:
        name = o.name
        if name in seen:
            seen[name] += 1
            stem, ext = os.path.splitext(name)
            name = f"{stem}_{seen[name]}{ext}"          # collision-safe
        else:
            seen[name] = 0
        proposals.append({"action": f"cut_{mode}", "from": o.full_path,
                          "to": f"{target}/{name}", "object_id": o.object_id})
    return proposals
