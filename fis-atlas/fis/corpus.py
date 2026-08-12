# fis-op: und
"""Corpus-scale node model (David's spec).

A large research root becomes a `corpus_root` whose note is the CONSTITUTION +
territory map — it does NOT enumerate every file. Direct child folders become
`research_territory` nodes that inherit the root policy and add local
distinctives. Permission is expressed in four tiers, and canonical/gold/
source-of-truth filename claims are surfaced as OPEN QUESTIONS, never auto-trusted.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from .model import Atlas, FolderRecord


def _norm(p: str) -> str:
    return os.path.normcase(os.path.normpath(p))


def _parent(p: str) -> str:
    return _norm(str(Path(p).parent))

CORPUS_MIN_DESCENDANTS = 3000            # above this a research root is a corpus
CANON_MARKERS = ("CANONICAL", "SOURCE_OF_TRUTH", "PUBLICATION_GOLD",
                 "UNIFICATION_GOLD", "GOLD", "FINAL", "MASTER")

# permission tiers, keyed by risk posture
TIERS = {
    "corpus_protected": {
        "without_approval": ["scan", "build_cache", "hash", "classify", "detect_symptoms", "report"],
        "as_proposals": ["tag", "create_sidecar", "update_sidecar", "compare", "link_hub",
                         "suggest_rename", "suggest_move", "suggest_archive"],
        "require_approval": ["rename", "move", "copy", "archive", "quarantine", "dedupe",
                             "backup", "restore", "publish", "unpublish", "sync"],
        "prohibited": ["direct_delete", "automatic_rename", "automatic_move",
                       "automatic_archive", "automatic_publish", "run_untrusted_script"],
    },
}


def _node_id(root_slug: str, rel: str) -> str:
    if not rel or rel == ".":
        return f"fis:{root_slug}"
    seg = re.sub(r"[^a-z0-9]+", "-", rel.split("\\")[0].split("/")[0].lower()).strip("-")
    return f"fis:{root_slug}:{seg}"


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "corpus"


def _numbered(child_names: list[str]) -> bool:
    hits = sum(1 for n in child_names if re.match(r"^\d{2}[_\-]", n) or re.match(r"^O-\d", n))
    return hits >= 3


def apply_corpus_model(atlas: Atlas) -> None:
    root_path = _norm(atlas.root)
    root = next((f for f in atlas.folders.values() if _norm(f.full_path) == root_path), None)
    if root is None:
        return
    root_slug = _slug(root.name)

    # is this a corpus?
    md_heavy = root.total_descendants and \
        sum(1 for o in atlas.objects.values() if o.content_type in ("markdown", "text", "code")) \
        >= 0.3 * max(1, len(atlas.objects))
    is_corpus = root.total_descendants >= CORPUS_MIN_DESCENDANTS and md_heavy

    # canonical-marker candidates across the corpus
    canon = [o.rel_path for o in atlas.objects.values()
             if any(m in o.name.upper() for m in CANON_MARKERS)]

    for f in atlas.folders.values():
        rel = f.rel_path
        f.node_id = _node_id(root_slug, rel)
        f.inherited_policy = "corpus_protected"
        f.permissions = TIERS["corpus_protected"]
        # node type
        if _norm(f.full_path) == root_path:
            f.node_type = "corpus_root" if is_corpus else "folder"
        elif _parent(f.full_path) == root_path and is_corpus:
            f.node_type = "research_territory"
            f.parent_node = f"fis:{root_slug}"
        else:
            f.node_type = "folder"
            f.parent_node = _node_id(root_slug, str(Path(rel).parent)) if rel else f"fis:{root_slug}"
        # ordering scheme
        child_names = [g.name for g in atlas.folders.values()
                       if _parent(g.full_path) == _norm(f.full_path)]
        child_names += [o.name for o in atlas.objects.values() if _norm(o.parent) == _norm(f.full_path)]
        if _numbered(child_names):
            f.ordering_scheme = "numbered_document_sequence"

    if is_corpus:
        root.folder_class = "research_corpus"
        root.risk = "amber"                       # report-only posture, not red-sealed
        root.behaves_like = "corpus"
        root.canonical_candidates = canon[:50]
        root.purpose = (f"Primary research corpus — {len(atlas.objects)} files across "
                        f"{root.direct_children} territories. Root is the constitution + map, "
                        f"not a file list.")
        root.open_questions = [
            "Which territory is the governing source of truth for the entire corpus?",
            "Are the *_GOLD territories authoritative or candidate outputs?",
            "Which of the CANONICAL / SOURCE_OF_TRUTH / FINAL claims actually govern?",
            "Which files are sources vs reproducible derivatives?",
        ]
        root.evidence.add(f"{root.total_descendants} descendants, research-heavy → corpus_root")
        root.evidence.add(f"{len(canon)} files carry canonical/gold/final markers (claims, not proof)")
