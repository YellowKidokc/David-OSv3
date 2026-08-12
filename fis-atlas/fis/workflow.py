# fis-op: dec
"""Workflows (routines) — compose independent primitives into one backend op.

A workflow does NOT reimplement search/cut/dedupe. It CALLS the isolated
handlers on the shelf. That is the whole point: the same primitives serve every
future recipe. Everything is preview-only — a workflow returns a PLAN.

Reference recipe "File Aggregation Separation Sort" (GTQ):
    search(GTQ) -> cut into target -> dedupe -> categorize (ask one question)
                -> flag out-of-range (ask keep/drop)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .handlers import lok_search, dec_cut, sim_dedupe

# GTQ series signature — the matcher IS the query passed to the generic search.
GTQ_TERMS = ["genesis to quantum", "gtq", "genesis", "quantum"]
GTQ_STRONG = {"genesis to quantum", "gtq"}
IN_RANGE = 0.6
BORDERLINE = 0.2


def gtq_matcher(name: str, text: str) -> float:
    blob = (name + "\n" + text).lower()
    score = sum((0.5 if t in GTQ_STRONG else 0.2) for t in GTQ_TERMS if t in blob)
    return min(1.0, score)


@dataclass
class WorkflowPlan:
    name: str
    matched: list[str] = field(default_factory=list)
    out_of_range: list[dict] = field(default_factory=list)
    proposals: list[dict] = field(default_factory=list)
    questions: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def run_gtq_aggregation(roots: list[str], target: str,
                        categorize_mode: str | None = None,
                        matcher=gtq_matcher) -> WorkflowPlan:
    plan = WorkflowPlan(name="File Aggregation Separation Sort (GTQ)")

    # 1. SEARCH (primitive)
    hits = lok_search.search(roots, matcher, min_score=BORDERLINE)
    in_range = [o for o, s in hits if s >= IN_RANGE]
    borderline = [(o, s) for o, s in hits if s < IN_RANGE]

    # 2. CUT into the target, flattened (primitive)
    plan.proposals += dec_cut.cut(in_range, target, mode="move")
    plan.matched = [o.object_id for o in in_range]

    # 3. DEDUPE (primitive)
    keepers, dup_proposals = sim_dedupe.dedupe(in_range)
    plan.proposals += dup_proposals

    # 4. CATEGORIZE — the one decision we can't infer
    if categorize_mode is None:
        plan.questions.append({
            "question_id": "Q-GTQ-CAT", "text": "How should the aggregated GTQ files be organized?",
            "options": ["Custom / close categorizations (by sub-topic)", "By file extension",
                        "Flat — no subfolders, just deduped", "Show me a sample of each first"],
            "answer_type": "choice", "blocking": False, "ruling_scope": "workflow",
            "affected_count": len(plan.matched)})
    else:
        for o in keepers:
            bucket = (o.ext.lstrip(".") or "misc") if categorize_mode == "extension" else "gtq"
            plan.proposals.append({"action": "categorize", "path": o.full_path, "bucket": bucket})

    # 5. OUT OF RANGE (primitive result -> question)
    plan.out_of_range = [{"id": o.object_id, "name": o.name, "score": round(s, 2)}
                         for o, s in borderline]
    if borderline:
        plan.questions.append({
            "question_id": "Q-GTQ-RANGE",
            "text": f"{len(borderline)} files loosely match GTQ but fell below the threshold. Keep or drop?",
            "options": ["Keep them in the aggregation", "Drop them", "Show me these examples"],
            "answer_type": "choice", "blocking": False, "ruling_scope": "cluster",
            "affected_count": len(borderline)})

    plan.summary = {"scanned_roots": roots, "in_range": len(in_range),
                    "out_of_range": len(borderline),
                    "duplicates_to_quarantine": len(dup_proposals),
                    "after_dedupe": len(keepers), "questions": len(plan.questions),
                    "mutations": 0}
    return plan
