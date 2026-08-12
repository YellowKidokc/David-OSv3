"""Series ownership by corroboration (David's insight).

If the same file appears across many folders that all look like a series, that
REPETITION is evidence. A file seen in 12 GTQ folders is almost certainly a
member; a lone weak match is not. We accumulate evidence across instances and
assign an ownership probability — supported over multiple instances.

    ownership = 1 - (1 - base_score) * decay^(distinct_folders - 1)

More corroborating folders -> probability climbs toward certainty (capped .99).
Aliases (GTQ == "Genesis to Quantum") are treated as the same series signal.
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field

from .model import ObjectRecord

DECAY = 0.55          # each extra corroborating folder pushes probability up


# ---- alias-aware matcher builder (GTQ == genesis to quantum) ----
def series_matcher(aliases: dict[str, float]):
    """aliases: {term: weight}. Returns matcher(name, text) -> score in [0,1]."""
    def matcher(name: str, text: str) -> float:
        blob = (name + "\n" + text).lower()
        return min(1.0, sum(w for t, w in aliases.items() if t in blob))
    return matcher


GTQ_ALIASES = {"genesis to quantum": 0.5, "gtq": 0.5, "genesis": 0.2, "quantum": 0.2}


def _identity(o: ObjectRecord) -> str:
    """Content hash if cheap, else normalized name — 'the same file' across folders."""
    if o.size and o.size <= 16_000_000:
        try:
            with open(o.full_path, "rb") as fh:
                return "h:" + hashlib.sha256(fh.read()).hexdigest()[:16]
        except OSError:
            pass
    return "n:" + re.sub(r"[^a-z0-9]+", "_", re.sub(r"\.\w+$", "", o.name).lower()).strip("_")


@dataclass
class SeriesMember:
    identity: str
    representative_name: str
    instances: list[str] = field(default_factory=list)   # full paths
    n_instances: int = 0
    n_folders: int = 0
    base_score: float = 0.0
    ownership_prob: float = 0.0
    verdict: str = "candidate"       # member | likely | candidate | weak

    def to_dict(self):
        return {**self.__dict__}


def assess(hits: list[tuple[ObjectRecord, float]]) -> list[SeriesMember]:
    """Group scattered matches by identity, accumulate corroboration, rank."""
    groups: dict[str, SeriesMember] = {}
    for o, score in hits:
        ident = _identity(o)
        m = groups.get(ident)
        if m is None:
            m = SeriesMember(identity=ident, representative_name=o.name)
            groups[ident] = m
        m.instances.append(o.full_path)
        m.base_score = max(m.base_score, score)
    for m in groups.values():
        m.n_instances = len(m.instances)
        m.n_folders = len({os.path.dirname(p) for p in m.instances})
        # corroboration: more distinct folders -> higher confidence
        m.ownership_prob = round(min(0.99, 1 - (1 - m.base_score) * (DECAY ** (m.n_folders - 1))), 3)
        m.verdict = ("member" if m.ownership_prob >= 0.85 else
                     "likely" if m.ownership_prob >= 0.6 else
                     "candidate" if m.ownership_prob >= 0.35 else "weak")
    return sorted(groups.values(), key=lambda m: m.ownership_prob, reverse=True)


def signature_set(members: list[SeriesMember], min_prob: float = 0.85) -> list[SeriesMember]:
    """The recurring core — the ~10-15 files that ARE the series (high corroboration)."""
    return [m for m in members if m.ownership_prob >= min_prob]
