"""# fis-op: und
χ classifier — Level 2 (ten Master-Equation factors, 0-3). Supervised.

Rates a file on G M E S T K R Q F C, picks the primary factor, guesses entity +
state, and PROPOSES a MEQS filename. It never renames — rename_allowed is False
until approvals train it. This is a lexical first pass; the local model/LLM
refines it later. Plugs into the engine's understand stage.

    0 absent · 1 weak trace · 2 active/supporting · 3 dominant/primary
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

FACTORS = ["G", "M", "E", "S", "T", "K", "R", "Q", "F", "C"]
LAW_CODE = {"G": "L01", "M": "L02", "E": "L03", "S": "L05", "T": "L00",
            "K": "L06", "R": "L04", "Q": "L07", "F": "L09", "C": "L10"}

LEXICON = {
    "G": ["ground", "authority", "source", "grace", "canon", "foundation", "premise", "substrate"],
    "M": ["mechanism", "process", "procedure", "workflow", "algorithm", "alignment", "action", "operation"],
    "E": ["entropy", "disorder", "corrupt", "redact", "fragment", "noise", "contradiction", "instability"],
    "S": ["identity", "self", "personhood", "autobiograph", "first-person", "who i am", "lineage"],
    "T": ["time", "sequence", "chronolog", "timeline", "prophecy", "before", "after", "history", "version"],
    "K": ["knowledge", "information", "logos", "shannon", "equation", "definition", "proof", "data", "kolmogorov"],
    "R": ["relation", "covenant", "bond", "dependency", "network", "reference", "obligation", "body"],
    "Q": ["quantum", "uncertainty", "collapse", "probability", "experience", "felt", "perception"],
    "F": ["faith", "trust", "commitment", "belief", "reliance", "nonlocal", "entanglement", "prayer"],
    "C": ["coherence", "integration", "unity", "synthesis", "reconcil", "christ", "resurrection", "master equation"],
}


@dataclass
class ChiResult:
    scores: dict = field(default_factory=dict)
    primary_factor: str = "C"
    secondary_factors: list = field(default_factory=list)
    entity_guess: str = "X"
    state_guess: str = "U"
    suggested_filename: str = ""
    confidence: float = 0.0
    needs_review: bool = True
    rename_allowed: bool = False        # supervised — never auto until trained

    def vector(self) -> str:
        return "".join(f"{f}{self.scores.get(f,0)}" for f in FACTORS)

    def to_dict(self):
        d = dict(self.__dict__); d["vector"] = self.vector(); return d


def _score_hits(hits: int) -> int:
    return 0 if hits == 0 else 1 if hits == 1 else 2 if hits <= 3 else 3


def classify(name: str, text: str = "", entities: dict | None = None,
             ext: str = ".md") -> ChiResult:
    blob = (name + "\n" + text).lower()
    scores = {f: _score_hits(sum(blob.count(k) for k in LEXICON[f])) for f in FACTORS}
    # primary = highest score; C breaks ties (integration bias per standard)
    primary = max(FACTORS, key=lambda f: (scores[f], f == "C"))
    if scores[primary] == 0:
        primary, scores[primary] = "K", max(scores["K"], 1)   # default: knowledge
    secondary = [f for f in FACTORS if f != primary and scores[f] >= 2]

    entity = _entity_guess(name, blob, entities)
    state = _state_guess(name)
    total = sum(scores.values())
    conf = round(min(0.95, 0.4 + total / 25), 2)
    stamp = date.today().strftime("%Y%m%d")
    fname = f"{primary}__{entity}__{state}__{stamp}__{LAW_CODE[primary]}{ext}"

    return ChiResult(scores=scores, primary_factor=primary, secondary_factors=secondary,
                     entity_guess=entity, state_guess=state, suggested_filename=fname,
                     confidence=conf, needs_review=conf < 0.75, rename_allowed=False)


def _entity_guess(name: str, blob: str, entities: dict | None) -> str:
    if entities:
        for canon, meta in entities.items():
            aliases = [canon] + [a.lower() for a in (meta.get("aliases") or [])]
            if any(a.lower() in blob for a in aliases):
                return canon
    stem = re.sub(r"\.\w+$", "", name)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", stem).strip("_").upper()
    return slug or "X"


def _state_guess(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ("final", "_f_", "publish")):
        return "F"
    if any(k in n for k in ("draft", "wip", "working")):
        return "W"
    if any(k in n for k in ("archive", "old", "deprecated")):
        return "A"
    return "U"        # unknown — needs human ruling
