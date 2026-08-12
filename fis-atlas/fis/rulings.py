"""Ruling -> policy -> future prediction (David's spec).

Closes the loop: a customer answer to a high-value question becomes a bounded,
reusable POLICY. On the next run, policies resolve matching anomalies (so FIS
stops re-asking) and PREDICT similar cases. Append-only JSONL — history sacred.

    symptom -> anomaly -> question -> RULING -> POLICY -> prediction
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

from .anomaly import Anomaly, Question


@dataclass
class Ruling:
    decision_id: str
    question_id: str
    anomaly_id: str
    selected_answer: str
    scope: str                       # object|cluster|folder|project|corpus|global
    applies_to_pattern: str = ""     # regex over names, "" = only this anomaly
    exceptions: list[str] = field(default_factory=list)
    edited_answer: str = ""
    confidence_after: float = 1.0
    approved_by: str = "user"
    timestamp: str = ""
    supersedes: str = ""


@dataclass
class Policy:
    policy_id: str
    from_decision: str
    family: str                      # which anomaly family it resolves
    pattern: str                     # regex over evidence names; "" = family-wide at scope
    verdict: str                     # the chosen meaning
    scope: str
    predicts: str = ""               # optional learned label for future items

    def covers(self, a: Anomaly, names: list[str]) -> bool:
        if a.family != self.family:
            return False
        if self.scope in ("corpus", "global") and not self.pattern:
            return True
        if self.pattern:
            return any(re.search(self.pattern, n, re.I) for n in names)
        return False


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_ruling(q: Question, a: Anomaly, chosen_index: int, scope: str = "",
                applies_to_pattern: str = "") -> tuple[Ruling, Policy]:
    answer = q.options[chosen_index] if 0 <= chosen_index < len(q.options) else ""
    did = "DEC-" + datetime.now().strftime("%Y%m%d%H%M%S")
    ruling = Ruling(decision_id=did, question_id=q.question_id, anomaly_id=a.anomaly_id,
                    selected_answer=answer, scope=scope or q.ruling_scope,
                    applies_to_pattern=applies_to_pattern, timestamp=_now())
    policy = Policy(policy_id="POL-" + did[4:], from_decision=did, family=a.family,
                    pattern=applies_to_pattern, verdict=answer, scope=ruling.scope)
    return ruling, policy


class RulingStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.rulings: list[Ruling] = []
        self.policies: list[Policy] = []
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("_t") == "ruling":
                self.rulings.append(Ruling(**{k: v for k, v in rec.items() if k != "_t"}))
            elif rec.get("_t") == "policy":
                self.policies.append(Policy(**{k: v for k, v in rec.items() if k != "_t"}))

    def record(self, ruling: Ruling, policy: Policy):
        self.rulings.append(ruling)
        self.policies.append(policy)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"_t": "ruling", **asdict(ruling)}) + "\n")
            fh.write(json.dumps({"_t": "policy", **asdict(policy)}) + "\n")

    def apply(self, anomalies: list[Anomaly], name_lookup) -> tuple[list[Anomaly], list[dict]]:
        """Return (unresolved anomalies, resolved notes). Suppresses already-ruled ones."""
        survivors, resolved = [], []
        for a in anomalies:
            names = name_lookup(a)
            hit = next((p for p in self.policies if p.covers(a, names)), None)
            if hit:
                resolved.append({"anomaly_id": a.anomaly_id, "policy_id": hit.policy_id,
                                 "verdict": hit.verdict, "family": a.family})
            else:
                survivors.append(a)
        return survivors, resolved

    def predict(self, name: str) -> list[str]:
        """Learned labels a policy would assign to a future item by name."""
        out = []
        for p in self.policies:
            if p.pattern and re.search(p.pattern, name, re.I):
                out.append(p.verdict)
        return out
