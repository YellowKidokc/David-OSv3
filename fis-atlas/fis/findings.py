# fis-op: gov
"""The finding compiler (David's spec) — the missing middle between scanner and report.

Turns verified observations into arguments. Every finding uses the five-part
grammar: Claim · Evidence · Interpretation · Consequence · Action. Produces
`report_model.json` — the intermediate object every report sentence must trace to.

Deterministic code computes facts and candidate findings here. A local model
(later) only RANKS and EXPLAINS them; a validator ensures every claim resolves
to evidence. The model is the translator, never the source of facts.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

from .model import Atlas
from .anomaly import Anomaly, Question


@dataclass
class Finding:
    finding_id: str
    claim: str                 # what did we find?
    evidence_ids: list[str]    # what facts support it?
    interpretation: str        # what does it mean?
    consequence: str           # why should the reader care?
    recommended_action: str    # what should happen next?
    severity: str
    confidence: float
    automation_effect: str = ""

    def to_dict(self):
        return asdict(self)


def compile_findings(atlas: Atlas, anomalies: list[Anomaly]) -> list[Finding]:
    findings: list[Finding] = []
    n = len(atlas.objects)
    fold = len(atlas.folders)
    fid = 0

    def add(**kw):
        nonlocal fid
        fid += 1
        findings.append(Finding(finding_id=f"FND-{fid:03d}", **kw))

    # 1. Structure exists (facts: territory count)
    territories = [f for f in atlas.folders.values() if f.node_type == "research_territory"]
    if territories:
        add(claim="The corpus is already organized into meaningful territories.",
            evidence_ids=[t.object_id for t in territories[:20]],
            interpretation="The next task is reconciliation between overlapping systems, not generic sorting.",
            consequence="Generic auto-sorting would fight structure that is already intentional.",
            recommended_action="Classify each territory before proposing any moves.",
            severity="medium", confidence=0.9)

    # 2. Authority distributed (from the authority anomaly)
    auth = next((a for a in anomalies if a.family == "authority"), None)
    if auth:
        add(claim="Canonical authority is distributed across competing claims.",
            evidence_ids=auth.evidence_ids,
            interpretation="Several territories/files assert overlapping canonical/gold/final authority.",
            consequence="Auto rename/move/dedupe could separate a source from its derivative or elevate an obsolete version.",
            recommended_action="Run a non-mutating authority + dependency audit; produce a human ruling queue.",
            severity="high", confidence=0.94,
            automation_effect="Block path-changing automation until authority is resolved.")

    # 3. Canonical status not inferable from filenames
    if auth:
        add(claim="Canonical status cannot be inferred from filenames.",
            evidence_ids=auth.evidence_ids[:5],
            interpretation="GOLD / CANONICAL / SOURCE_OF_TRUTH / FINAL are evidence of intent, not proof, and several coexist.",
            consequence="Trusting a name would hard-code the wrong authority.",
            recommended_action="Establish authority via references, modification history, and a user ruling.",
            severity="high", confidence=0.9)

    # 4. Much may be generated/reproducible
    deriv = next((a for a in anomalies if a.family == "provenance"), None)
    if deriv:
        add(claim="A large share of the corpus may be generated or reproducible.",
            evidence_ids=deriv.evidence_ids or [],
            interpretation="Markdown sources appear alongside html/xlsx/pdf exports of the same stems.",
            consequence="Duplicate/archive decisions made before linking source→derivative would lose the source of truth.",
            recommended_action="Link derivatives to sources before any dedupe or archive.",
            severity="medium", confidence=0.6)

    # 5. Automation blast radius too high -> report-only (fact: mixed risk classes present)
    reds = [f for f in atlas.folders.values() if f.risk == "red"]
    if reds or auth:
        add(claim="Automatic reorganization currently has excessive blast radius.",
            evidence_ids=[f.object_id for f in reds[:10]],
            interpretation="Code, canonical material, generated outputs, and data coexist in scope.",
            consequence="A single automated pass could break dependencies across unrelated systems.",
            recommended_action="Operate report-only until dependencies and authority are mapped.",
            severity="high", confidence=0.9,
            automation_effect="mutating_automation_enabled = false")

    # 6. Duplicate reclaim (fact)
    dup = next((c for c in atlas.clusters if c.kind == "duplicates"), None)
    if dup and dup.members:
        add(claim=f"{len(dup.members)} files are exact duplicates.",
            evidence_ids=dup.members[:20],
            interpretation="Identical content exists in multiple locations.",
            consequence="Edits risk landing on the wrong copy; storage is wasted.",
            recommended_action="Choose a governing location per group, then quarantine the rest.",
            severity="low", confidence=0.95)

    return findings


def build_report_model(atlas: Atlas, findings: list[Finding],
                       questions: list[Question], audience: str = "owner") -> dict:
    model = {
        "report_question": "What is the condition of this corpus and what should happen next?",
        "audience": audience,
        "scope": {"files": len(atlas.objects), "folders": len(atlas.folders),
                  "bytes": sum(f.total_size for f in atlas.folders.values()
                               if f.node_type == "corpus_root") or
                           sum(o.size for o in atlas.objects.values())},
        "findings": [f.to_dict() for f in findings],
        "open_questions": [{"question_id": q.question_id, "question": q.text,
                            "priority": q.priority, "blocking": q.blocking,
                            "ruling_scope": q.ruling_scope,
                            "affected_count": q.affected_count,
                            "blocking_actions": q.affected_actions,
                            "options": q.options} for q in questions],
    }
    _validate(model)
    return model


def _validate(model: dict) -> None:
    """Every finding must trace to evidence — no free-floating claims (spec)."""
    for f in model["findings"]:
        if not f.get("evidence_ids"):
            f["_warning"] = "finding has no evidence — would be an invented narrative"
