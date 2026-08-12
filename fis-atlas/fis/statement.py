"""FIS Statements — the readable, reversible operational sentence.

    S:2:B442:RS04/OS91>Q1:W7:P2:D14:V3

> Under schema 2, batch B442 searched root set RS04, operated on the objects in
> OS91, collected them into Q1, ran workflow W7 under policy P2 and ruling D14
> with verified result V3.

A statement is decompressible through the registry. It is NOT a fingerprint —
that is the History Capsule (history.py). The two never share a field.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Statement:
    schema: str
    batch: str
    root_set: str
    object_set: str
    destination: str
    workflow: str
    policy: str
    decision: str
    result: str

    def encode(self) -> str:
        sel = f"{self.root_set}/{self.object_set}" if self.object_set else self.root_set
        return (f"S:{self.schema}:{self.batch}:{sel}>{self.destination}:"
                f"{self.workflow}:{self.policy}:{self.decision}:{self.result}")


def parse(text: str) -> Statement:
    if not text.startswith("S:"):
        raise ValueError("not a FIS statement")
    _, schema, batch, rest = text.split(":", 3)
    sel_dest, workflow, policy, decision, result = rest.split(":", 4)
    selection, destination = sel_dest.split(">", 1)
    root_set, _, object_set = selection.partition("/")
    return Statement(schema, batch, root_set, object_set, destination,
                     workflow, policy, decision, result)


def decompress(reg, text: str) -> str:
    """Plain English via the registry (reversible)."""
    s = parse(text)

    def safe(kind, code):
        try:
            return reg.lookup(kind, code)
        except Exception:
            return f"?{code}"

    def num(code):                       # "P2" -> "2", "V3" -> "3"
        digits = "".join(ch for ch in code if ch.isdigit())
        return digits or code

    roots = safe("root_sets", s.root_set)
    return (f"schema {s.schema}: batch {s.batch} searched {roots}"
            + (f", operated on object-set {s.object_set}" if s.object_set else "")
            + f", collected into {safe('paths', s.destination)}"
            + f", workflow {safe('workflows', s.workflow)}"
            + f", policy {safe('policies', num(s.policy))}"
            + f", ruling {s.decision}"
            + f", result {safe('results', num(s.result))}")
