# fis-op: dec
"""Anomaly + question engine (David's spec).

    symptom -> anomaly -> hypothesis -> question -> (ruling -> policy)

An anomaly = observed pattern vs expected relationship. FIS never concludes
authority from filenames; it forms candidate interpretations, BLOCKS the
affected actions, and asks the smallest highest-value question.

Priority (active learning / uncertainty sampling / information gain):
    Q_p = S x B x U x I
      S = severity weight (cost if answered wrong)
      B = blast radius (files the answer controls, log-damped)
      U = uncertainty (1 - confidence the anomaly's meaning is known)
      I = expected information gain (breadth of actions/decisions settled)
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .model import Atlas

SEV_W = {"critical": 4, "high": 3, "medium": 2, "low": 1}
CANON_MARK = ("CANONICAL", "SOURCE_OF_TRUTH", "GOLD", "FINAL", "MASTER", "CONSOLIDATED")

# customer-facing templates (spec)
TEMPLATES = {
    "Q-AUTH-001": "These territories/files all appear to claim authority. Which description is closest?",
    "Q-DERIV-001": "These appear to be generated from another source. Which is the editable source?",
    "Q-MIRROR-001": "The same material appears in several locations. Is that intentional mirroring?",
    "Q-LIFE-001": "These files have been inactive a long time. Completed, abandoned, or preserved?",
    "Q-ROLE-001": "FIS sees several possible purposes for this folder. Which is closest?",
}


@dataclass
class Anomaly:
    anomaly_id: str
    family: str                 # authority|duplication|structure|lifecycle|provenance|safety
    observed_condition: str
    possible_meanings: list[str]
    default_assumption: str
    affected_count: int
    affected_actions: list[str]
    severity: str
    confidence: float           # confidence the anomaly EXISTS
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class Question:
    question_id: str
    template_id: str
    text: str
    options: list[str]
    answer_type: str            # choice|yes_no|path_selection|free_text
    blocking: bool
    ruling_scope: str           # file|cluster|folder|project|corpus
    affected_count: int
    affected_actions: list[str]
    priority: float
    anomaly_id: str


def _priority(a: Anomaly) -> float:
    S = SEV_W.get(a.severity, 1)
    B = math.log10(1 + a.affected_count)
    U = 1.0 - a.confidence_meaning if hasattr(a, "confidence_meaning") else 0.6
    I = max(1, len(a.affected_actions))
    return round(S * (B or 0.1) * U * I, 3)


def detect(atlas: Atlas) -> tuple[list[Anomaly], list[Question]]:
    anomalies: list[Anomaly] = []
    aid = 0

    def new(**kw) -> Anomaly:
        nonlocal aid
        aid += 1
        return Anomaly(anomaly_id=f"ANOM-{aid:03d}", **kw)

    # 1. AUTHORITY conflict — multiple canonical/gold/final claims (never auto-conclude)
    canon = [o for o in atlas.objects.values()
             if any(m in o.name.upper() for m in CANON_MARK)]
    canon_terr = [f for f in atlas.folders.values()
                  if any(m in f.name.upper() for m in CANON_MARK)]
    if len(canon) + len(canon_terr) >= 2:
        a = new(family="authority",
                observed_condition=f"{len(canon_terr)} territories + {len(canon)} files assert canonical/gold/final authority",
                possible_meanings=[
                    "One territory governs the complete corpus",
                    "Each territory governs its own domain",
                    "GOLD folders are publication outputs, not sources",
                    "None of these names reliably indicate current authority",
                ],
                default_assumption="authority unresolved — treat all as candidates",
                affected_count=len(canon) + len(canon_terr),
                affected_actions=["rename", "move", "archive", "dedupe", "publish"],
                severity="high", confidence=0.9,
                evidence_ids=[o.object_id for o in canon[:20]] + [f.object_id for f in canon_terr])
        a.confidence_meaning = 0.35     # we are quite UNSURE what it means
        anomalies.append(a)

    # 2. DERIVATIVE families — same stem across markdown + html/xlsx (likely generated)
    by_stem: dict[str, set] = {}
    for o in atlas.objects.values():
        stem = re.sub(r"\.\w+$", "", o.name).lower()
        by_stem.setdefault(stem, set()).add(o.content_type)
    deriv = [s for s, types in by_stem.items()
             if "markdown" in types and (types & {"code", "spreadsheet", "pdf", "data"})]
    if len(deriv) >= 3:
        a = new(family="provenance",
                observed_condition=f"{len(deriv)} stems appear in Markdown AND a generated format (html/xlsx/pdf)",
                possible_meanings=["Markdown is the editable source, others are generated",
                                   "The source varies by project",
                                   "These are independent documents"],
                default_assumption="treat Markdown as source, others as derivatives",
                affected_count=len(deriv),
                affected_actions=["dedupe", "archive", "rename"],
                severity="medium", confidence=0.6)
        a.confidence_meaning = 0.5
        anomalies.append(a)

    # 3. DUPLICATION governance — exact-dup clusters
    dup = next((c for c in atlas.clusters if c.kind == "duplicates"), None)
    if dup and dup.members:
        a = new(family="duplication",
                observed_condition=f"{len(dup.members)} files are exact duplicates across locations",
                possible_meanings=["Intentional mirrors (working/backup/publication)",
                                   "One location should govern; the rest are stale"],
                default_assumption="keep all; do not delete until a location is chosen",
                affected_count=len(dup.members),
                affected_actions=["dedupe", "archive"],
                severity="medium", confidence=0.95)
        a.confidence_meaning = 0.55
        anomalies.append(a)

    # build questions, gate by blocking, score priority
    questions = []
    tmpl = {"authority": "Q-AUTH-001", "provenance": "Q-DERIV-001",
            "duplication": "Q-MIRROR-001", "lifecycle": "Q-LIFE-001", "structure": "Q-ROLE-001"}
    for a in anomalies:
        a.priority = _priority(a)
        tid = tmpl.get(a.family, "Q-ROLE-001")
        opts = list(a.possible_meanings) + ["I'm not sure — show me three examples"]
        blocking = a.family in ("authority",) or a.severity in ("critical", "high")
        scope = "corpus" if a.family == "authority" else "cluster"
        questions.append(Question(
            question_id=f"Q-{a.anomaly_id}", template_id=tid, text=TEMPLATES[tid],
            options=opts, answer_type="choice", blocking=blocking, ruling_scope=scope,
            affected_count=a.affected_count, affected_actions=a.affected_actions,
            priority=a.priority, anomaly_id=a.anomaly_id))
    questions.sort(key=lambda q: q.priority, reverse=True)
    return anomalies, questions
