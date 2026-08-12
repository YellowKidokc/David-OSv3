"""# fis-op: sim
Cross-format visual matching — group PDF pages / PNG / WebP that are the SAME image.

pHash proposes candidate families (union-find over perceptual-hash distance).
A family is a registry object-set manifest; the filename is a PROJECTION of it
(registry owns identity, filename re-derives). Deterministic; nothing moves.

    W9 pipeline: search(scoped) -> render+phash -> group -> [confirm] -> stage
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .visual import hamming

FORMAT_CODE = {"pdf": "P", "png": "N", "webp": "W", "jpg": "J", "jpeg": "J"}
ROLE = {"pdf": "source", "png": "render", "webp": "derivative"}


@dataclass
class VisualItem:
    object_id: str
    path: str
    fmt: str                 # pdf|png|webp
    phash: int
    page: int = 1            # slide/page number (1 for standalone images)


@dataclass
class Family:
    family_id: str           # e.g. A011  (object-set identity)
    members: list[VisualItem] = field(default_factory=list)
    confirmed: bool = False   # True only after SSIM/embedding confirmation

    def manifest(self) -> dict:
        """The object-set manifest — identity lives HERE, not in the filename."""
        return {"family_id": self.family_id, "confirmed": self.confirmed,
                "members": [{"object_id": m.object_id, "path": m.path, "fmt": m.fmt,
                             "page": m.page, "role": ROLE.get(m.fmt, "representation"),
                             "phash": m.phash} for m in self.members]}

    def names(self) -> dict[str, str]:
        """Projection: A011-01P.pdf / A011-01N.png / A011-01W.webp. Display only."""
        out = {}
        for m in self.members:
            code = FORMAT_CODE.get(m.fmt, m.fmt[:1].upper())
            out[m.object_id] = f"{self.family_id}-{m.page:02d}{code}.{m.fmt}"
        return out


def _uf_group(items: list[VisualItem], threshold: int) -> list[list[VisualItem]]:
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if hamming(items[i].phash, items[j].phash) <= threshold:
                union(i, j)
    groups: dict[int, list[VisualItem]] = {}
    for idx, it in enumerate(items):
        groups.setdefault(find(idx), []).append(it)
    return list(groups.values())


def build_families(items: list[VisualItem], threshold: int = 10,
                   prefix: str = "A") -> list[Family]:
    """Group visual items into candidate families. Singletons are NOT families."""
    families = []
    n = 1
    for group in _uf_group(items, threshold):
        if len(group) < 2:
            continue                       # a lone image is not a match family
        fam = Family(family_id=f"{prefix}{n:03d}",
                     members=sorted(group, key=lambda m: (m.page, m.fmt)))
        families.append(fam)
        n += 1
    return families


def stage_plan(families: list[Family], out_root: str) -> list[dict]:
    """Preview-only: propose where each member goes, keeping formats together
    but separate. Nothing moves until act, under policy, once."""
    plan = []
    for fam in families:
        names = fam.names()
        for m in fam.members:
            plan.append({"action": "copy", "from": m.path,
                         "to": f"{out_root}/Matched/{fam.family_id}/{names[m.object_id]}",
                         "family": fam.family_id, "role": ROLE.get(m.fmt, "representation")})
    return plan
