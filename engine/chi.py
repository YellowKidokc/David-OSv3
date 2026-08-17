"""
chi.py — thin wrapper over the real chi_qi_v5 metric engine (chi_engine.py).

Exposes a single score_text() that returns the chi profile fields the classifier
needs: chi_vector (G/M/E/...), primary/secondary, a rough confidence, and the
evidence / fruit / anti-fruit scores. The heavy lexicon load happens once.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import config

try:
    import chi_engine as _ce
    CHI_OK = True
except Exception:
    CHI_OK = False


@lru_cache(maxsize=1)
def _lexicon():
    if not CHI_OK:
        return None
    lex_path = Path(config.LEXICON_PATH)
    return _ce.LexiconStore.load(lex_path if lex_path.exists() else None)


def _metric_score(file_id: str, text: str, collection: str,
                  support: list, counter: list) -> float:
    lex = _lexicon()
    full = _ce.TextUnit(file_id=file_id, unit_id=file_id, unit_type="file",
                        ordinal=0, text=text, anchor="", start_char=0, end_char=len(text))
    res = _ce.build_metric_from_terms(
        file_id, full, f"{collection}.score", collection, collection, "score",
        lex.terms([collection]), lex.terms(support), lex.terms(counter),
    )
    return round(res.score / 100.0, 4)


def score_text(text: str, file_id: str = "f") -> dict:
    """Return chi profile dict, or zeros if the engine/text is unavailable."""
    blank = {
        "chi_vector": {}, "chi_primary": None, "chi_secondary": None,
        "chi_confidence": 0.0, "domain_scores": {},
        "evidence": 0.0, "fruit": 0.0, "anti_fruit": 0.0,
    }
    if not CHI_OK or not text or len(text.strip()) < 20:
        return blank

    profiles = _ce.extract_profiles(file_id, text, _lexicon())
    chi_vec = profiles.get("chi_vector", {}) or {}
    ranked = sorted(chi_vec.items(), key=lambda kv: kv[1], reverse=True)
    primary = ranked[0][0] if ranked and ranked[0][1] > 0 else None
    secondary = ranked[1][0] if len(ranked) > 1 and ranked[1][1] > 0 else None
    # confidence: share of the dominant chi variable (vector sums to ~100)
    conf = round((ranked[0][1] / 100.0), 4) if ranked else 0.0

    return {
        "chi_vector": chi_vec,
        "chi_primary": primary,
        "chi_secondary": secondary,
        "chi_confidence": conf,
        "domain_scores": profiles.get("domain_vector", {}) or {},
        "evidence": _metric_score(file_id, text, "EVIDENCE_TERMS", ["BOUNDARY_TERMS"], []),
        "fruit": _metric_score(file_id, text, "FRUITS", ["BOUNDARY_TERMS"], ["ANTI_FRUITS"]),
        "anti_fruit": _metric_score(file_id, text, "ANTI_FRUITS", [], ["FRUITS"]),
    }
