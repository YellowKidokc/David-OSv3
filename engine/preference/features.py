"""
features.py — turn a naming proposal into features every engine can consume.

A "proposal" is the dict produced by rename_planner:
    {"proposed_name", "domain_code", "ct_code", "status_code", "tags": [...]}

Two views:
  featurize_binary() -> flat {feature: 0/1} dict   (River / VW / sklearn one-hot)
  featurize_text()   -> space-joined tokens        (text/TF-IDF style engines)
"""
from __future__ import annotations

from typing import List

import config

DOMAINS  = list(config.DOMAIN_LABELS.keys())
CTS      = ["DOC", "COD", "DAT", "NOT", "CFG", "PAP", "IMG", "VID", "AUD", "BIN"]
STATUSES = ["DR", "AC", "FN", "AR", "RV"]


def _tag_vocab() -> List[str]:
    try:
        import tagger
        return [c for _, c in tagger.TAG_ABBREVS]
    except Exception:
        return []


TAGS = _tag_vocab()


def featurize_binary(proposal: dict) -> dict:
    feats = {}
    dom = proposal.get("domain_code", "GN")
    ct  = proposal.get("ct_code", "DOC")
    st  = proposal.get("status_code", "AC")
    for d in DOMAINS:
        feats[f"dom_{d}"] = 1 if dom == d else 0
    for c in CTS:
        feats[f"ct_{c}"] = 1 if ct == c else 0
    for s in STATUSES:
        feats[f"st_{s}"] = 1 if st == s else 0
    tags = set(proposal.get("tags") or [])
    for t in TAGS:
        feats[f"tag_{t}"] = 1 if t in tags else 0
    return feats


def featurize_text(proposal: dict) -> str:
    parts = [
        f"dom_{proposal.get('domain_code', 'GN')}",
        f"ct_{proposal.get('ct_code', 'DOC')}",
        f"st_{proposal.get('status_code', 'AC')}",
    ]
    parts += [f"tag_{t}" for t in (proposal.get("tags") or [])]
    return " ".join(parts)


def feature_key(proposal: dict) -> tuple:
    """Coarse key for the frequency baseline: (domain, ct, status)."""
    return (proposal.get("domain_code", "GN"),
            proposal.get("ct_code", "DOC"),
            proposal.get("status_code", "AC"))
