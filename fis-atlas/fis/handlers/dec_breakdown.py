"""# fis-op: dec
breakdown — strip a folder tree down to its individual files.

Walks a root, proposes moving every file up to the target root (flatten),
collision-safe, and proposes removing the emptied subfolders afterward.
Independent of cut/search — usable on any messy tree. Read-only (proposals).

    breakdown(root, target) -> [proposal]
"""
from __future__ import annotations

import os
from pathlib import Path


def breakdown(root: str, target: str | None = None) -> list[dict]:
    target = target or root
    proposals, seen, dirs = [], {}, set()
    for dp, _subdirs, files in os.walk(root):
        if os.path.abspath(dp) != os.path.abspath(target):
            dirs.add(dp)
        for fn in files:
            name = fn
            if name in seen:
                seen[name] += 1
                stem, ext = os.path.splitext(name)
                name = f"{stem}_{seen[name]}{ext}"
            else:
                seen[name] = 0
            src = os.path.join(dp, fn)
            if os.path.dirname(src) == os.path.abspath(target):
                continue                                 # already at root
            proposals.append({"action": "flatten_move", "from": src, "to": f"{target}/{name}"})
    # empty-folder cleanup proposals (deepest first)
    for d in sorted(dirs, key=lambda p: p.count(os.sep), reverse=True):
        proposals.append({"action": "remove_emptied_folder", "path": d})
    return proposals
