"""Similarity (sim) — group objects into diagnostic clusters.

Groups OVERLAP: an object can be a duplicate AND a markdown AND ambiguous.
Exact-dup only for now (hash). Near-dup / MinHash is a port target from
fis_near_dup.py into a sim/ handler.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .model import ObjectRecord, FolderRecord, Cluster

HASH_CAP = 8 * 1024 * 1024  # only hash files <= 8MB for the exact-dup pass


def _sha(path: str) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            h.update(fh.read())
        return h.hexdigest()
    except OSError:
        return None


def build_clusters(objects: dict[str, ObjectRecord], folders: dict[str, FolderRecord]) -> list[Cluster]:
    clusters: list[Cluster] = []
    objs = list(objects.values())

    def bucket(kind, label, pred, rule=""):
        members = [o.object_id for o in objs if pred(o)]
        if members:
            c = Cluster(cluster_id=f"C-{kind}", label=f"{label} ({len(members)})",
                        kind=kind, members=members, proposed_rule=rule)
            clusters.append(c)
            for oid in members:
                objects[oid].clusters.append(c.cluster_id)

    bucket("markdown", "Markdown documents", lambda o: o.content_type == "markdown")
    bucket("images", "Images", lambda o: o.content_type == "image",
           rule="images with auto-generated names -> Media/Unsorted")
    bucket("archives", "Archives", lambda o: o.content_type == "archive")
    bucket("protected", "Protected / sensitive", lambda o: o.risk == "red")
    bucket("ambiguous", "Ambiguous / unknown", lambda o: o.content_type == "unknown" or o.detected_role == "unknown")
    bucket("drafts", "Drafts / temporary", lambda o: o.detected_role in ("draft", "backup"))

    # exact duplicates (hash)
    by_hash: dict[str, list[str]] = {}
    for o in objs:
        if o.size and o.size <= HASH_CAP:
            hv = _sha(o.full_path)
            if hv:
                by_hash.setdefault(hv, []).append(o.object_id)
    dup_members = [oid for group in by_hash.values() if len(group) > 1 for oid in group]
    if dup_members:
        c = Cluster(cluster_id="C-duplicates", label=f"Exact duplicates ({len(dup_members)})",
                    kind="duplicates", members=dup_members,
                    proposed_rule="keep one per group, quarantine the rest")
        clusters.append(c)
        for oid in dup_members:
            objects[oid].clusters.append(c.cluster_id)
            objects[oid].relationships.append("duplicate")

    # empty / debris folders
    empty = [f.object_id for f in folders.values() if f.empty]
    if empty:
        clusters.append(Cluster(cluster_id="C-empty", label=f"Empty / debris folders ({len(empty)})",
                                kind="empty", members=empty, proposed_rule="review + delete-later"))

    # recognizable projects
    projects = [f.object_id for f in folders.values() if f.folder_class == "programming"]
    if projects:
        clusters.append(Cluster(cluster_id="C-projects", label=f"Recognizable projects ({len(projects)})",
                                kind="projects", members=projects,
                                proposed_rule="preserve intact — do not split"))
    return clusters
