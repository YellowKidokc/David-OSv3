"""# fis-op: sim
Cross-format visual matching — group the SAME slide across pdf-page / png / webp.

LOAD-BEARING DISTINCTION: a PDF is a multi-slide CONTAINER, so document identity
(a whole deck = D-code) is separate from visual identity (one page + its images
= G-code). A PDF never gets renamed as a group member; the group references
(document, page) as a pdf_page POINTER. Only images are copied/renamed.

pHash proposes candidate groups (it under-merges — decks share template chrome);
a group is only DECLARED after confirmation. Nothing moves on discovery.
Escalation is a VISION model (visual equivalence), not NLP (which reads words).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .visual import hamming

FORMAT_CODE = {"pdf_page": "P", "png": "N", "webp": "W", "jpg": "J", "jpeg": "J"}
ROLE = {"pdf_page": "source_page", "png": "render", "webp": "derivative"}


@dataclass
class Document:
    """A PDF deck — document identity (D-code). Never a visual-group member itself."""
    doc_id: str
    path: str
    pages: int = 1


@dataclass
class VisualItem:
    object_id: str
    representation: str          # pdf_page | png | webp
    phash: int
    page: int = 1
    path: str = ""               # for images
    document_id: str = ""        # for pdf_page: which deck it belongs to


@dataclass
class VisualGroup:
    group_id: str                # e.g. G011  (visual identity — one slide)
    members: list[VisualItem] = field(default_factory=list)
    confirmed: bool = False      # True only after SSIM/embedding confirmation

    def manifest(self) -> dict:
        """Identity lives HERE. pdf_page members point to (document, page)."""
        out = []
        for m in self.members:
            rec = {"object_id": m.object_id, "representation": m.representation,
                   "role": ROLE.get(m.representation, "representation"), "phash": m.phash}
            if m.representation == "pdf_page":
                rec.update(document=m.document_id, page=m.page)   # POINTER, not a copy
            else:
                rec.update(path=m.path)
            out.append(rec)
        return {"group_id": self.group_id, "confirmed": self.confirmed, "members": out}

    def names(self) -> dict[str, str]:
        """Projection (display only). pdf_page -> a pointer file, images -> copies."""
        out, letters = {}, "ABCDEFGH"
        for i, m in enumerate(sorted(self.members, key=lambda x: x.representation)):
            letter = letters[i]
            if m.representation == "pdf_page":
                out[m.object_id] = f"{self.group_id}-{letter}.pdf-page.json"   # pointer
            else:
                out[m.object_id] = f"{self.group_id}-{letter}.{m.representation}"
        return out


def _uf_group(items: list[VisualItem], threshold: int) -> list[list[VisualItem]]:
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if hamming(items[i].phash, items[j].phash) <= threshold:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[ri] = rj
    groups: dict[int, list[VisualItem]] = {}
    for idx in range(len(items)):
        groups.setdefault(find(idx), []).append(items[idx])
    return list(groups.values())


def build_groups(items: list[VisualItem], threshold: int = 10,
                 prefix: str = "G") -> list[VisualGroup]:
    """Group visual items. A group needs >=2 members across representations."""
    out, n = [], 1
    for grp in _uf_group(items, threshold):
        if len(grp) < 2:
            continue
        out.append(VisualGroup(group_id=f"{prefix}{n:03d}",
                               members=sorted(grp, key=lambda m: (m.page, m.representation))))
        n += 1
    return out


def stage_plan(groups: list[VisualGroup], out_root: str) -> list[dict]:
    """Preview-only. Images are copied; a pdf_page becomes a POINTER, never a
    copy of the whole multi-page deck. Mutation happens later at act, once."""
    plan = []
    for g in groups:
        names = g.names()
        for m in g.members:
            dest = f"{out_root}/Matched/{g.group_id}/{names[m.object_id]}"
            if m.representation == "pdf_page":
                plan.append({"action": "write_pointer", "to": dest,
                             "points_to": {"document": m.document_id, "page": m.page},
                             "group": g.group_id})
            else:
                plan.append({"action": "copy", "from": m.path, "to": dest,
                             "group": g.group_id, "role": ROLE.get(m.representation)})
    return plan
