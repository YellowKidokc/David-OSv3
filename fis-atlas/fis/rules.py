# fis-op: dec
"""Decide (dec) — the rule grammar. Rules are DATA, not hardcoded.

Grammar (one rule per line, '#' comments):
    WHEN <field> <op> <value> [AND <field> <op> <value> ...] THEN <action> [= <param>]

fields   = any ObjectRecord attribute (content_type, risk, sensitivity, name, ext, activity, detected_role, size)
op       = is | is_not | contains | matches | gt | lt
action   = keep | rename | move | archive | protect | quarantine | review   (+ optional '= destination')

The engine is dumb and stable; behaviour changes by editing the sidecar, never
the code. A red/forbidden object is never overridden by a rule (fail closed).
"""
from __future__ import annotations

import re
from pathlib import Path

from .model import ObjectRecord

_OPS = {
    "is": lambda a, b: str(a).lower() == b.lower(),
    "is_not": lambda a, b: str(a).lower() != b.lower(),
    "contains": lambda a, b: b.lower() in str(a).lower(),
    "matches": lambda a, b: re.search(b, str(a), re.I) is not None,
    "gt": lambda a, b: _num(a) > _num(b),
    "lt": lambda a, b: _num(a) < _num(b),
}


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


class Rule:
    def __init__(self, conditions, action, param):
        self.conditions = conditions   # list of (field, op, value)
        self.action = action
        self.param = param

    def matches(self, o: ObjectRecord) -> bool:
        for field, op, value in self.conditions:
            actual = getattr(o, field, "")
            if op not in _OPS or not _OPS[op](actual, value):
                return False
        return True


def parse_rules(text: str) -> list[Rule]:
    rules = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line.upper().startswith("WHEN"):
            continue
        try:
            when, then = re.split(r"\bTHEN\b", line, flags=re.I)
            cond_str = re.sub(r"^\s*WHEN\s+", "", when, flags=re.I)
            conds = []
            for clause in re.split(r"\bAND\b", cond_str, flags=re.I):
                parts = clause.strip().split(None, 2)
                if len(parts) == 3:
                    conds.append((parts[0], parts[1], parts[2].strip().strip('"')))
            act = then.strip()
            param = ""
            if "=" in act:
                act, param = [x.strip() for x in act.split("=", 1)]
            rules.append(Rule(conds, act.lower(), param.strip('"')))
        except ValueError:
            continue
    return rules


def load_rules(path: str | Path) -> list[Rule]:
    p = Path(path)
    return parse_rules(p.read_text(encoding="utf-8")) if p.exists() else []


def apply_rules(objects: dict[str, ObjectRecord], rules: list[Rule]) -> int:
    """Apply rules to objects. Never overrides a forbidden action. Returns hits."""
    hits = 0
    for o in objects.values():
        for r in rules:
            if r.matches(o):
                # fail closed: a rule cannot do something the object forbids
                if r.action in o.forbidden_actions:
                    o.evidence.add(f"rule wanted '{r.action}' but it is forbidden here")
                    continue
                o.proposed_treatment = r.action
                if r.param:
                    o.probable_destination = r.param
                o.evidence.add(f"rule: {r.action}" + (f" -> {r.param}" if r.param else ""))
                hits += 1
                break
    return hits
