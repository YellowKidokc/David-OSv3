"""
domain_classifier.py — assign the 5 tags to a file.

Tags: (1) domain code, (2) content_type, (3) status, (4) date, (5) topic slug,
plus the chi profile (chi_vector / evidence / fruit). Config-driven: domain
keyword maps come from config/domains.yaml. Combines keyword evidence with the
chi engine; nothing is a black box — every score traces to keyword hits.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import config
import chi as chi_mod

# domain keyword maps: {CODE: {"name": str, "keywords": [..]}}
_DOMAINS = config._load_yaml("domains.yaml", {"domains": {}}).get("domains", {})


def _score_domains(text: str) -> dict:
    low = text.lower()
    scores = {}
    for code, spec in _DOMAINS.items():
        kws = spec.get("keywords", []) or []
        hits = sum(low.count(k) for k in kws if k)
        if hits:
            scores[code] = hits
    return scores


def _content_type(ext: str, text: str) -> str:
    ct = config.EXT_CONTENT_TYPE.get(ext.lower())
    if ct == "document" and text:
        low = text.lower()
        if any(k in low for k in ("abstract", "references", "doi:", "et al", "we show that")):
            return "paper"
    return ct or ("note" if text else "binary")


def _status(name: str, mtime: float) -> str:
    low = name.lower()
    if any(k in low for k in ("draft", "wip", "temp", "tmp", "working", "scratch")):
        return "draft"
    if any(k in low for k in ("final", "done", "complete", "publish", "release")):
        return "final"
    if any(k in low for k in ("archive", "old", "backup", "bak", "_old", "deprecated")):
        return "archive"
    if any(k in low for k in ("review", "check", "todo", "pending", "flag")):
        return "review"
    age_days = (time.time() - mtime) / 86400 if mtime else 0
    return "archive" if age_days > 180 else "active"


def classify(rec: "config.FileRecord", text: str) -> None:
    """Mutates rec in place with the 5 tags + chi profile + confidence."""
    name_path = f"{rec.name} {rec.path}"
    blob = (name_path + "\n" + (text or ""))[:200_000]

    # chi profile from the real engine
    prof = chi_mod.score_text(text or name_path, file_id=rec.sha256[:16] or "f")
    rec.chi_vector     = prof["chi_vector"]
    rec.chi_primary    = prof["chi_primary"]
    rec.chi_secondary  = prof["chi_secondary"]
    rec.chi_confidence = prof["chi_confidence"]
    rec.evidence       = prof["evidence"]
    rec.fruit          = prof["fruit"]
    rec.anti_fruit     = prof["anti_fruit"]

    # domain: keyword evidence first, chi domain_vector as a tiebreak
    dom_scores = _score_domains(blob)
    rec.domain_scores = dom_scores
    if dom_scores:
        rec.domain = max(dom_scores, key=dom_scores.get)
        top = max(dom_scores.values())
        kw_conf = min(1.0, 0.4 + 0.1 * top)        # 1 hit ~0.5, scales up
    else:
        rec.domain = _chi_domain_to_code(prof.get("domain_scores", {}))
        kw_conf = 0.35
    rec.domain_label = config.DOMAIN_LABELS.get(rec.domain, "General")

    rec.content_type = _content_type(rec.extension, text)
    mtime = _mtime(rec)
    rec.status = _status(rec.name, mtime)
    rec.date = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d") if mtime else ""

    # overall confidence: blend domain keyword strength with chi confidence
    rec.confidence = round(0.6 * kw_conf + 0.4 * (rec.chi_confidence or 0.0), 4)


# chi engine domain_vector keys (theology/physics/...) -> our 2-letter codes
_CHI_DOMAIN_MAP = {
    "theology": "TH", "physics": "PH", "information_theory": "IF",
    "formal_math": "MT", "history": "GN", "epistemology": "EP",
    "ethics_moral_philosophy": "MR", "sociology_culture": "GN",
    "psychology": "CS", "ai_methodology": "AI",
}


def _chi_domain_to_code(domain_vector: dict) -> str:
    if not domain_vector:
        return "GN"
    top = max(domain_vector, key=domain_vector.get)
    return _CHI_DOMAIN_MAP.get(top, "GN")


def _mtime(rec: "config.FileRecord") -> float:
    try:
        return Path(rec.path).stat().st_mtime
    except Exception:
        return 0.0
