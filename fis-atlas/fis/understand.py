"""Understand (und) — intelligence at the source.

A light comprehender each node can call to READ enough of its files to know
"this is theophysics, it's talking about governing equations / derivations."
NOT a frontier model — enough understanding to classify, no more.

Tiered, pluggable (spec):
  1. LexiconComprehender   — offline, stdlib, always works (the default floor).
  2. NlpLightComprehender  — wraps fis_nlp_light embeddings when present (port target).
  3. ApiComprehender       — optional remote fallback for hard cases.

Only the lexicon tier is implemented here; the others are declared seams so the
engine degrades gracefully and upgrades without touching callers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

READABLE = {"markdown", "text", "code", "data"}
SAMPLE_BYTES = 6000

# domain lexicons — cheap but real recognition
LEXICONS = {
    "theophysics": ["theophysics", "chi field", "master equation", "ten laws", "logos",
                    "coherence field", "covenant", "resurrection", "divine", "χ", "∇"],
    "physics": ["quantum", "entropy", "thermodynamic", "lagrangian", "field equation",
                "energy", "momentum", "relativity", "hamiltonian", "wavefunction"],
    "mathematics": ["theorem", "lemma", "proof", "derivation", "integral", "manifold",
                    "eigen", "topology", "isomorphism", "governing equation"],
    "theology": ["god", "christ", "scripture", "grace", "gospel", "sin", "prophecy",
                 "genesis", "trinity", "salvation"],
    "philosophy": ["ontology", "epistemic", "metaphysic", "consciousness", "morality", "teleolog"],
    "information": ["information theory", "shannon", "bit", "encoding", "signal", "entropy of"],
}
# structural signals — what KIND of document
SIGNALS = {
    "governing_equation": ["governing equation", "master equation", "lagrangian", "field equation", "="],
    "derivation": ["derivation", "we derive", "it follows", "therefore", "q.e.d", "proof"],
    "axiom": ["axiom", "postulate", "first principle"],
    "law_mapping": ["law 0", "ten laws", "law_01", "l01", "law one"],
}


@dataclass
class Comprehension:
    domains: list[str] = field(default_factory=list)     # ranked
    signals: list[str] = field(default_factory=list)     # governing_equation, derivation, ...
    topics: list[str] = field(default_factory=list)      # salient keywords
    confidence: float = 0.0


class LexiconComprehender:
    """The always-available floor. Reads a sample, scores domains + signals."""
    name = "lexicon"

    def read(self, path: str, content_type: str) -> Comprehension:
        text = ""
        if content_type in READABLE:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read(SAMPLE_BYTES)
            except OSError:
                pass
        blob = (Path(path).name + "\n" + text).lower()
        return self.comprehend(blob)

    def comprehend(self, blob: str) -> Comprehension:
        blob = blob.lower()
        domain_scores = {}
        for dom, terms in LEXICONS.items():
            hits = sum(blob.count(t.lower()) for t in terms)
            if hits:
                domain_scores[dom] = hits
        domains = sorted(domain_scores, key=domain_scores.get, reverse=True)
        signals = [s for s, terms in SIGNALS.items()
                   if sum(blob.count(t.lower()) for t in terms) >= 1 and s != "governing_equation"
                   or (s == "governing_equation" and any(t in blob for t in SIGNALS[s][:-1]))]
        # salient topics = top domain terms actually present
        topics = []
        for dom in domains[:2]:
            for t in LEXICONS[dom]:
                if t.lower() in blob and len(t) > 3:
                    topics.append(t)
        total = sum(domain_scores.values())
        conf = min(1.0, total / 12) if total else 0.0
        return Comprehension(domains=domains, signals=signals, topics=topics[:6], confidence=conf)


def get_comprehender():
    """Return best available comprehender. Port target: try fis_nlp_light, then API."""
    return LexiconComprehender()


def comprehend_folder(comp, files) -> Comprehension:
    """Aggregate a folder's readable files into one domain/signal profile."""
    dom_tally, sig_tally, topics = {}, set(), []
    scored = 0
    for o in files:
        c = comp.read(o.full_path, o.content_type)
        if c.domains:
            scored += 1
            for i, d in enumerate(c.domains[:3]):
                dom_tally[d] = dom_tally.get(d, 0) + (3 - i)
            sig_tally.update(c.signals)
            topics.extend(c.topics)
            o.domains = c.domains[:2]
    domains = sorted(dom_tally, key=dom_tally.get, reverse=True)
    seen, uniq = set(), []
    for t in topics:
        if t not in seen:
            seen.add(t); uniq.append(t)
    conf = min(1.0, scored / max(1, len(files)))
    return Comprehension(domains=domains, signals=sorted(sig_tally), topics=uniq[:8], confidence=conf)


def purpose_sentence(folder_class: str, comp: Comprehension, n_items: int) -> str:
    if not comp.domains:
        return f"{folder_class} folder — {n_items} items."
    dom = " / ".join(comp.domains[:2])
    sig = (", discussing " + ", ".join(s.replace("_", " ") for s in comp.signals[:3])) if comp.signals else ""
    return f"{folder_class} — {n_items} items on {dom}{sig}."
