# fis-op: und
"""Domain vocabulary packs + unknown-domain escalation (the tagger's trick).

Classification is pluggable: each domain (theophysics, day_trading, obsidian, …)
is a vocabulary pack under domains/. Add a pack = teach the system a new domain.
When a document matches NO pack well enough, the tagger doesn't shrug — it
ESCALATES to fetch the vernacular it needs: propose a candidate pack from the
document's own salient terms, and/or ask the local model. Fetched vocabulary is
'inferred' and lands in domains/_proposed/ for human approval — never auto-trusted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except Exception:                       # pragma: no cover
    yaml = None

PACKS_DIR = Path(__file__).parent.parent / "domains"
UNKNOWN_THRESHOLD = 0.15                 # below this, the domain is unknown -> escalate

STOPWORDS = set("the a an and or of to in on for is are was were be this that with "
                "as at by from it its into we you they he she our your their not no "
                "will can may should would could i me my do does did has have had".split())


def load_packs(root: Path = PACKS_DIR) -> dict[str, dict]:
    if yaml is None:
        return {}
    packs = {}
    for p in sorted(root.glob("*.yaml")):
        try:
            d = yaml.safe_load(p.read_text(encoding="utf-8"))
            packs[d["domain"]] = {"terms": [t.lower() for t in d.get("terms", [])],
                                  "weight": float(d.get("weight", 1.0))}
        except Exception:
            continue
    return packs


def score(text: str, packs: dict | None = None) -> dict[str, float]:
    packs = packs if packs is not None else load_packs()
    blob = text.lower()
    out = {}
    for dom, pk in packs.items():
        hits = sum(blob.count(t) for t in pk["terms"])
        if hits:
            out[dom] = round(min(1.0, hits / 8) * pk["weight"], 3)
    return dict(sorted(out.items(), key=lambda kv: kv[1], reverse=True))


def best_domain(text: str, packs: dict | None = None) -> tuple[str | None, float]:
    s = score(text, packs)
    if not s:
        return None, 0.0
    dom, val = next(iter(s.items()))
    return (dom, val) if val >= UNKNOWN_THRESHOLD else (None, val)


# ---- escalation: fetch the vernacular for an unknown domain ----
@dataclass
class PackProposal:
    proposed_terms: list[str] = field(default_factory=list)
    tier: str = "inferred"               # never 'recorded'; needs human approval
    source: str = "salient_terms"        # salient_terms | local_model


def propose_pack(text: str, packs: dict | None = None, top: int = 15) -> PackProposal:
    """When no pack matches, mine the document's own salient terms as candidate
    vocabulary — the vernacular the tagger would need to learn this domain."""
    known = {t for pk in (packs or load_packs()).values() for t in pk["terms"]}
    freq: dict[str, int] = {}
    for w in re.findall(r"[a-zA-Z][a-zA-Z\-]{3,}", text.lower()):
        if w in STOPWORDS or w in known:
            continue
        freq[w] = freq.get(w, 0) + 1
    terms = [w for w, _ in sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:top]]
    return PackProposal(proposed_terms=terms, source="salient_terms")


def fetch_vocabulary(domain_hint: str, questioner=None) -> PackProposal | None:
    """Optional: ask the local model for a domain's vernacular. Returns a
    PROPOSAL only (inferred), never an active pack. None if the model is absent."""
    try:
        from . import llm
        llm.enforce("interpret_free_text_answer")     # contract check
        q = questioner or llm.OllamaQuestioner()
        if not llm.available():
            return None
        # (kept minimal; the model proposes terms, a human approves the pack)
        return PackProposal(proposed_terms=[], source="local_model", tier="inferred")
    except Exception:
        return None


def classify_or_escalate(text: str) -> dict:
    """Tagger entry point: name the domain, or escalate to fetch its vernacular."""
    packs = load_packs()
    dom, val = best_domain(text, packs)
    if dom:
        return {"domain": dom, "confidence": val, "status": "known"}
    return {"domain": None, "confidence": val, "status": "unknown",
            "escalation": propose_pack(text, packs).__dict__}


def save_proposal(name: str, proposal: PackProposal) -> Path:
    """Write a proposed pack to domains/_proposed/ — inactive until approved."""
    out = PACKS_DIR / "_proposed"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.yaml"
    body = (f"domain: {name}\nweight: 1.0\nstatus: proposed  # needs approval\n"
            f"tier: {proposal.tier}\nterms:\n"
            + "".join(f"  - {t}\n" for t in proposal.proposed_terms))
    path.write_text(body, encoding="utf-8")
    return path
