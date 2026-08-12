# fis-op: aut
"""Node agent — the per-folder wake/scan/escalate/ping loop.

This is the "every folder wakes up and handles itself" feeling you wanted,
done SAFELY: it is ONE tiny runtime that VISITS each folder-node. No Python
lives inside your folders (that would be arbitrary-code-execution risk).

A node can:
  * wake()  — small-scale scan of JUST this folder (non-recursive), classify,
              comprehend, run local symptoms, update its .fisnote + the store.
  * needs_help — flags objects it can't understand for the NLP / local LLM.
  * ping(action, targets) — accept a task (move/delete/archive). It NEVER
              mutates: it emits a PROPOSAL gated by the folder's permissions.
              Real execution waits for the approved executor (act stage).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import scan, classify, understand, symptoms
from .model import FolderRecord, ObjectRecord


@dataclass
class NodeReport:
    path: str
    folder_class: str
    risk: str
    purpose: str
    n_files: int
    needs_help: list[str] = field(default_factory=list)     # objects it couldn't understand
    symptoms: list[dict] = field(default_factory=list)
    proposals: list[dict] = field(default_factory=list)


class NodeAgent:
    def __init__(self, folder_path: str, store=None, comprehender=None):
        self.path = str(Path(folder_path))
        self.store = store
        self.comp = comprehender or understand.get_comprehender()
        self.folder: FolderRecord | None = None
        self.objects: list[ObjectRecord] = []

    def wake(self) -> NodeReport:
        """Small-scale local scan of just this folder. Read-only."""
        p = Path(self.path)
        objs, folder = [], FolderRecord(object_id="N-" + p.name, name=p.name, full_path=self.path)
        child_names = []
        for entry in os.scandir(self.path):
            if entry.is_dir():
                child_names.append(entry.name)
                continue
            try:
                st = entry.stat()
            except OSError:
                continue
            o = ObjectRecord(object_id="O-" + entry.name, name=entry.name,
                             ext=Path(entry.name).suffix.lower(), full_path=entry.path,
                             is_dir=False, parent=self.path, size=st.st_size,
                             modified=st.st_mtime, accessed=st.st_atime,
                             content_type=scan.content_type_for(entry.name, False))
            objs.append(o)
            folder.type_distribution[o.content_type] = folder.type_distribution.get(o.content_type, 0) + 1
        folder.direct_children = len(objs) + len(child_names)
        folder.empty = folder.direct_children == 0
        classify.classify_folder(folder, child_names, objs)
        for o in objs:
            classify.classify_object(o, folder)
        profile = understand.comprehend_folder(self.comp, objs)
        if profile.domains:
            folder.purpose = understand.purpose_sentence(folder.folder_class, profile, len(objs))
        folder.symptoms = [h.to_dict() for h in symptoms.run_symptoms(folder, objs)]
        self.folder, self.objects = folder, objs

        needs_help = [o.name for o in objs
                      if o.content_type in ("unknown", "binary") or o.class_confidence < 0.4]
        if self.store:
            self.store.event("node_wake", self.path,
                             {"class": folder.folder_class, "risk": folder.risk,
                              "needs_help": len(needs_help)})
        return NodeReport(path=self.path, folder_class=folder.folder_class, risk=folder.risk,
                          purpose=folder.purpose, n_files=len(objs), needs_help=needs_help,
                          symptoms=folder.symptoms)

    def seek_help(self, object_name: str) -> str:
        """Escalate an object it can't understand to the NLP/LLM tier.
        Today: re-read with the comprehender; port target: the local LLM."""
        o = next((x for x in self.objects if x.name == object_name), None)
        if not o:
            return "unknown object"
        c = self.comp.read(o.full_path, o.content_type)
        return (f"domains={c.domains} signals={c.signals}" if c.domains
                else "still unclear — would escalate to the local LLM")

    def ping(self, action: str, targets: list[str]) -> dict:
        """Accept a task. NEVER mutates — emits a permission-gated proposal."""
        if self.folder is None:
            self.wake()
        forbidden = set(self.folder.forbidden_actions)
        if action in forbidden or (action in ("delete",) and self.folder.risk == "red"):
            result = {"action": action, "status": "refused",
                      "reason": f"'{action}' is forbidden for a {self.folder.risk} "
                                f"{self.folder.folder_class} folder"}
        else:
            result = {"action": action, "status": "proposed", "targets": targets,
                      "note": "written as a proposal; the approved executor performs it later"}
        if self.store:
            self.store.event("node_ping", self.path, result)
        return result


def sweep(root: str, store=None) -> list[NodeReport]:
    """The wake scheme: visit every folder-node under root (one runner, not per-folder code)."""
    reports = []
    for dirpath, _dirs, _files in os.walk(root):
        reports.append(NodeAgent(dirpath, store=store).wake())
    return reports
