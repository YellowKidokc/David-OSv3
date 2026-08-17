"""
wordnet_expander.py — WordNet query expansion (trimmed from filetagger/wordnet_expander.py).

Used as a PRE-PASS before TF-IDF matching in the enricher: a handful of filename
words become a broader vocabulary (synonyms + parent concepts), so a low-confidence
file still matches similar already-classified files even when the exact words differ.

Fully defensive: if nltk or the WordNet corpus is missing, expand_term_list() just
returns the original seeds — the enricher still works, only less broadly.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List, Set

try:
    from nltk.corpus import wordnet as wn
    _HAS_WN = True
except Exception:
    _HAS_WN = False

_WARMED = False


def _ensure_corpus() -> bool:
    """Confirm the WordNet data is actually downloaded (find_spec lies about data)."""
    global _WARMED
    if not _HAS_WN:
        return False
    if _WARMED:
        return True
    try:
        wn.synsets("test")
        _WARMED = True
        return True
    except LookupError:
        try:
            import nltk
            nltk.download("wordnet", quiet=True)
            nltk.download("omw-1.4", quiet=True)
            wn.synsets("test")
            _WARMED = True
            return True
        except Exception:
            return False
    except Exception:
        return False


@lru_cache(maxsize=4096)
def _expand_one(word: str, max_per_source: int = 6) -> tuple:
    out: Set[str] = set()
    try:
        for ss in wn.synsets(word)[:4]:
            for lemma in ss.lemmas():
                nm = lemma.name().replace("_", " ").lower()
                if nm != word and len(nm) > 2:
                    out.add(nm)
            for hyp in ss.hypernyms()[:2]:
                for lemma in hyp.lemmas():
                    out.add(lemma.name().replace("_", " ").lower())
            if len(out) >= max_per_source * 2:
                break
    except Exception:
        return tuple()
    return tuple(sorted(out)[: max_per_source * 2])


def expand_term_list(seeds: List[str], max_total: int = 20) -> List[str]:
    """Expand seed words into a richer term list (seeds always included first)."""
    base = [s.lower() for s in seeds if s]
    if not base or not _ensure_corpus():
        return base[:max_total]
    terms: Set[str] = set(base)
    for seed in base:
        terms.update(_expand_one(seed))
    # seeds first, then expansions sorted by length (shorter = more general/common)
    extra = sorted(terms - set(base), key=lambda t: (len(t), t))
    return (base + extra)[:max_total]
