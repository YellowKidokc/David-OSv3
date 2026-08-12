# fis-op: und
"""Corpus familiarization — learn a category's associated tag-words from YOUR corpus.

WordNet expansion gives dictionary synonyms. This gives the vernacular your
CORPUS actually uses: give it a seed term ("justice") and a body of work, and it
surfaces the words that travel with it ("mercy", "atonement", "judgment") by
co-occurrence — ranked by lift, so distinctive associations beat merely-frequent
words. Output is a PROPOSAL (inferred), for human approval before it joins a
lexicon — never auto-trusted. Format-agnostic: seeds come as {category: [terms]}.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

STOPWORDS = set("the a an and or of to in on for is are was were be this that with as at "
                "by from it its into we you they he she our your their not no will can may "
                "should would could i me my do does did has have had but if then so than "
                "which who what when where how all any some more most other such only own "
                "same very just also there here about over under out up down".split())

_TOK = re.compile(r"[a-zA-Z][a-zA-Z\-']{2,}")


def _paragraphs(text: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def _tokens(text: str) -> set[str]:
    return {w for w in (m.group().lower() for m in _TOK.finditer(text))
            if w not in STOPWORDS}


@dataclass
class Association:
    term: str
    co_count: int          # paragraphs where term co-occurs with a seed
    lift: float            # distinctiveness of the association

    def as_tuple(self):
        return (self.term, self.co_count, round(self.lift, 2))


def associated_terms(seeds: list[str], docs: list[str], min_count: int = 2,
                     top: int = 25) -> list[Association]:
    """Rank terms that travel with the seeds across the corpus (paragraph-level)."""
    seeds_l = {s.lower() for s in seeds}
    paras = [p for d in docs for p in _paragraphs(d)]
    total = len(paras) or 1
    seed_paras = 0
    term_paras: Counter = Counter()      # paras containing term (any)
    co_paras: Counter = Counter()        # paras containing term AND a seed
    for p in paras:
        toks = _tokens(p)
        has_seed = any(s in p.lower() for s in seeds_l)
        if has_seed:
            seed_paras += 1
        for t in toks:
            if t in seeds_l:
                continue
            term_paras[t] += 1
            if has_seed:
                co_paras[t] += 1
    out = []
    for t, co in co_paras.items():
        if co < min_count:
            continue
        # lift = P(term|seed) / P(term) = (co/seed_paras) / (term_paras/total)
        lift = (co / max(1, seed_paras)) / (term_paras[t] / total)
        out.append(Association(term=t, co_count=co, lift=lift))
    out.sort(key=lambda a: (a.lift, a.co_count), reverse=True)
    return out[:top]


def familiarize(seed_lexicon: dict[str, list[str]], docs: list[str],
                **kw) -> dict[str, list[tuple]]:
    """For each category, propose associated tag-words learned from the corpus."""
    return {cat: [a.as_tuple() for a in associated_terms(seeds, docs, **kw)]
            for cat, seeds in seed_lexicon.items()}


def familiarize_paths(seed_lexicon: dict[str, list[str]], roots: list[str],
                      exts=(".md", ".txt"), max_files: int = 5000, **kw) -> dict:
    docs, n = [], 0
    for root in roots:
        for p in Path(root).rglob("*"):
            if p.is_file() and p.suffix.lower() in exts:
                try:
                    docs.append(p.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    continue
                n += 1
                if n >= max_files:
                    break
    return {"corpus_files": n, "proposals": familiarize(seed_lexicon, docs, **kw),
            "tier": "inferred"}     # proposals need human approval before use
