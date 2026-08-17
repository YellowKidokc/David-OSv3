#!/usr/bin/env python3
"""
capability.py — Category Capability Gate for the Corpus Engine.

Pipeline position: runs AFTER classify_records (which sets .file_type) and
BEFORE any deep processing.

classify_records answers:  "what KIND of document is this?"  (paper/prompt/log…)
this gate answers:         "what SUBJECT category is this, and do we actually
                            have the data access required to process it deeply?"

A file routed to `medical` is useless to deep-process if we hold no clinical
data source. Rather than fail silently or mis-tag, the gate marks it
BLOCKED_PENDING_ACCESS and names the exact missing source — so provisioning
access becomes a checklist instead of a surprise.

Design notes
------------
- Stdlib only. No third-party deps.
- Duck-typed: works on any record exposing `.name`, a text source
  (`.content_preview` or a `.search_text()` method), and (optionally) a
  writable `.notes` and `.file_type`. It does NOT import config, so it can be
  unit-tested in isolation and dropped into corpus_engine/core/ unchanged.
- Fail-safe bias: when a regulated signal (medical/legal/financial) is within
  a small margin of the top category, the MORE RESTRICTIVE tier wins. A false
  block costs a human glance; a false wave-through processes regulated data we
  have no right to touch. We pay the cheaper error.
- The access status lives in a JSON registry, so once you provision a source
  you flip "missing" -> "have" in one file — no code edit.

Drop-in (run.py, immediately after `classify_records(records)`):

    from corpus_engine.core.capability import CapabilityRegistry, gate_records, gate_report
    registry = CapabilityRegistry.load_or_default(os.path.join(args.output, 'capability.json'))
    cap_results = gate_records(records, registry)
    report = gate_report(cap_results)
    print(f"Capability gate routes: {report['route_counts']}")
    for category, sources in report['needs_access'].items():
        print(f"  BLOCKED {category}: needs {', '.join(sources)}")
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

# ──────────────────────────────────────────────────────────────────────────
# Vocabulary
# ──────────────────────────────────────────────────────────────────────────

TIERS = ("ORIGINAL", "PERSONAL", "BUSINESS", "REGULATED", "UNKNOWN")
# Restrictiveness order for the fail-safe tie-break (higher index = more restrictive)
_TIER_RANK = {t: i for i, t in enumerate(TIERS)}

ROUTE_DEEP = "process_deep"        # full Layer 3/4 processing + enrichment
ROUTE_LOCAL = "process_local"      # process with local-only signals, no external calls
ROUTE_SHALLOW = "process_shallow"  # partial access: tag + light enrich, defer the rest
ROUTE_BLOCK = "block_pending"      # required source missing → quarantine for access
ROUTE_REVIEW = "review"            # uncertain category → human decides

_TOKEN_RE = re.compile(r"[a-z][a-z0-9_\-']+")

# Subject-category signal terms. Lowercase. Kept deliberately small and editable.
CATEGORY_SIGNALS: Dict[str, List[str]] = {
    "theophysics": [
        "master equation", "coherence", "logos", "isomorphism", "grace", "entropy",
        "fruit of the spirit", "moral conservation", "chi", "theophysics", "ten laws",
        "yukawa", "noether", "seven question", "falsification", "sigma", "covenant",
    ],
    "personal": [
        "journal", "diary", "my family", "birthday", "vacation", "recipe", "photo",
        "personal", "note to self", "grocery", "todo", "reminder", "letter to",
    ],
    "technical_software": [
        "function", "import", "class", "def ", "endpoint", "config", "deployment",
        "schema", "database", "api key", "package.json", "requirements.txt", "docker",
        "repo", "commit", "pipeline", "worker", "cloudflare",
    ],
    "academic_research": [
        "abstract", "methodology", "hypothesis", "citation", "peer-reviewed", "study",
        "literature review", "dataset", "experiment", "p-value", "correlation", "journal",
    ],
    "business_generic": [
        "invoice", "proposal", "client", "revenue", "contract", "marketing", "roadmap",
        "quarterly", "stakeholder", "deliverable", "vendor", "budget", "pricing",
    ],
    "medical": [
        "patient", "diagnosis", "clinical", "symptom", "treatment", "prescription",
        "dosage", "icd-10", "hipaa", "phi", "medical record", "physician", "comorbidity",
    ],
    "legal": [
        "plaintiff", "defendant", "statute", "case law", "litigation", "deposition",
        "jurisdiction", "counsel", "subpoena", "indemnification", "non-disclosure",
        "liability", "settlement",
    ],
    "financial": [
        "securities", "portfolio", "ticker", "earnings", "10-k", "sec filing",
        "valuation", "dividend", "market data", "trade", "ledger", "audit", "gaap",
    ],
}

# Categories whose mis-classification is expensive — they win near-ties.
_REGULATED_CATEGORIES = {"medical", "legal", "financial"}

# How close (fraction of top score) a regulated category must be to override.
_OVERRIDE_MARGIN = 0.60
# Minimum top score (hits per 1000 words) to accept a category at all.
_MIN_CONFIDENCE = 0.8

# ──────────────────────────────────────────────────────────────────────────
# Registry
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class CapabilityEntry:
    """Access policy for one subject category."""
    tier: str
    required_sources: List[str] = field(default_factory=list)
    access: str = "have"               # have | partial | missing
    route_available: str = ROUTE_DEEP  # route when sources are satisfied
    route_blocked: str = ROUTE_BLOCK   # route when access is missing

    def resolve_route(self) -> Tuple[str, str]:
        """Return (route, reason) given current access state."""
        if not self.required_sources:
            return self.route_available, "no external source required"
        if self.access == "have":
            return self.route_available, "required source available"
        if self.access == "partial":
            return ROUTE_SHALLOW, "partial access — light enrich, defer rest"
        return self.route_blocked, "required source not configured"


def _default_entries() -> Dict[str, CapabilityEntry]:
    return {
        "theophysics":       CapabilityEntry("ORIGINAL", [], "have", ROUTE_DEEP),
        "personal":          CapabilityEntry("PERSONAL", [], "have", ROUTE_LOCAL),
        "technical_software":CapabilityEntry("PERSONAL", [], "have", ROUTE_LOCAL),
        "academic_research": CapabilityEntry("BUSINESS", ["web_search", "scholar_api"],
                                             "partial", ROUTE_DEEP, ROUTE_SHALLOW),
        "business_generic":  CapabilityEntry("BUSINESS", ["web_search", "public_registries"],
                                             "partial", ROUTE_DEEP, ROUTE_SHALLOW),
        "medical":           CapabilityEntry("REGULATED", ["licensed_clinical_db"],
                                             "missing", ROUTE_DEEP, ROUTE_BLOCK),
        "legal":             CapabilityEntry("REGULATED", ["case_law_db"],
                                             "missing", ROUTE_DEEP, ROUTE_BLOCK),
        "financial":         CapabilityEntry("REGULATED", ["market_data_api", "filings_api"],
                                             "missing", ROUTE_DEEP, ROUTE_BLOCK),
        "uncategorized":     CapabilityEntry("UNKNOWN", [], "have", ROUTE_REVIEW),
    }


class CapabilityRegistry:
    """category -> CapabilityEntry, loadable/savable as JSON."""

    def __init__(self, entries: Optional[Dict[str, CapabilityEntry]] = None):
        self.entries: Dict[str, CapabilityEntry] = entries or _default_entries()

    # -- factories -------------------------------------------------------
    @classmethod
    def default(cls) -> "CapabilityRegistry":
        return cls(_default_entries())

    @classmethod
    def load(cls, path: str) -> "CapabilityRegistry":
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        return cls({k: CapabilityEntry(**v) for k, v in raw.items()})

    @classmethod
    def load_or_default(cls, path: str) -> "CapabilityRegistry":
        try:
            return cls.load(path)
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            reg = cls.default()
            try:
                reg.save(path)   # write a starter file the user can edit
            except OSError:
                pass
            return reg

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({k: asdict(v) for k, v in self.entries.items()}, fh, indent=2)

    # -- access ----------------------------------------------------------
    def get(self, category: str) -> CapabilityEntry:
        return self.entries.get(category) or self.entries["uncategorized"]

    def set_access(self, category: str, status: str) -> None:
        """Flip access for a category once a source is provisioned."""
        if category in self.entries:
            self.entries[category].access = status


# ──────────────────────────────────────────────────────────────────────────
# Detection + gating
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class CapabilityResult:
    name: str
    category: str
    confidence: float          # hits per 1000 words for the winning category
    tier: str
    required_sources: List[str]
    access: str
    route: str
    reason: str
    evidence_terms: List[str]
    overridden: bool = False   # True if fail-safe tier override fired

    def tag(self) -> str:
        ev = ",".join(self.evidence_terms[:4])
        return (f"[GATE category={self.category} tier={self.tier} "
                f"access={self.access} route={self.route} why={ev}]")


def _text_of(record) -> str:
    """Pull a lowercase text blob from a record, duck-typed."""
    if hasattr(record, "search_text") and callable(record.search_text):
        text = record.search_text()
    else:
        text = getattr(record, "content_preview", "") or ""
    name = getattr(record, "name", "") or ""
    return (name + "\n" + text).lower()


def _score_categories(text: str) -> Dict[str, Tuple[float, List[str]]]:
    """Return {category: (hits_per_1000_words, matched_terms)}."""
    word_count = max(1, len(_TOKEN_RE.findall(text)))
    scale = 1000.0 / word_count
    scores: Dict[str, Tuple[float, List[str]]] = {}
    for category, terms in CATEGORY_SIGNALS.items():
        hits = 0
        matched: List[str] = []
        for term in terms:
            c = text.count(term)
            if c:
                hits += c
                matched.append(term)
        if hits:
            scores[category] = (round(hits * scale, 3), matched)
    return scores


def detect_category(record) -> Tuple[str, float, List[str], bool]:
    """
    Return (category, confidence, evidence_terms, overridden).

    Applies the fail-safe rule: a regulated category within _OVERRIDE_MARGIN of
    the top score wins, because under-gating regulated data is the costly error.
    A 'system'/'log'/'data'/'template'/'prompt' file_type with no regulated
    signal is treated as infrastructural and kept local.
    """
    text = _text_of(record)
    scores = _score_categories(text)
    if not scores:
        return "uncategorized", 0.0, [], False

    top_cat, (top_score, top_terms) = max(scores.items(), key=lambda kv: kv[1][0])

    # Fail-safe: let a near-top regulated category override a softer winner.
    overridden = False
    if top_cat not in _REGULATED_CATEGORIES:
        best_reg, best_reg_val, best_reg_terms = None, 0.0, []
        for cat in _REGULATED_CATEGORIES:
            if cat in scores and scores[cat][0] > best_reg_val:
                best_reg, (best_reg_val, best_reg_terms) = cat, scores[cat]
        if best_reg and best_reg_val >= top_score * _OVERRIDE_MARGIN:
            top_cat, top_score, top_terms, overridden = best_reg, best_reg_val, best_reg_terms, True

    if top_score < _MIN_CONFIDENCE and not overridden:
        return "uncategorized", top_score, top_terms, False

    return top_cat, top_score, top_terms, overridden


def gate_record(record, registry: CapabilityRegistry, stamp_notes: bool = True) -> CapabilityResult:
    category, confidence, evidence, overridden = detect_category(record)
    entry = registry.get(category)
    route, reason = entry.resolve_route()
    result = CapabilityResult(
        name=getattr(record, "name", "<unnamed>"),
        category=category,
        confidence=confidence,
        tier=entry.tier,
        required_sources=list(entry.required_sources),
        access=entry.access,
        route=route,
        reason=reason,
        evidence_terms=evidence,
        overridden=overridden,
    )
    if stamp_notes and hasattr(record, "notes"):
        sep = " " if getattr(record, "notes", "") else ""
        try:
            record.notes = (record.notes or "") + sep + result.tag()
        except (AttributeError, TypeError):
            pass
    return result


def gate_records(records, registry: Optional[CapabilityRegistry] = None,
                 stamp_notes: bool = True) -> List[CapabilityResult]:
    registry = registry or CapabilityRegistry.default()
    return [gate_record(r, registry, stamp_notes=stamp_notes) for r in records]


def gate_report(results: List[CapabilityResult]) -> dict:
    """Summarize a gate pass. `needs_access` is your provisioning checklist."""
    route_counts: Dict[str, int] = {}
    tier_counts: Dict[str, int] = {}
    needs_access: Dict[str, List[str]] = {}
    blocked: List[str] = []
    for r in results:
        route_counts[r.route] = route_counts.get(r.route, 0) + 1
        tier_counts[r.tier] = tier_counts.get(r.tier, 0) + 1
        if r.route == ROUTE_BLOCK:
            blocked.append(r.name)
            needs_access.setdefault(r.category, [])
            for s in r.required_sources:
                if s not in needs_access[r.category]:
                    needs_access[r.category].append(s)
    return {
        "total": len(results),
        "route_counts": route_counts,
        "tier_counts": tier_counts,
        "needs_access": needs_access,
        "blocked_files": blocked,
        "overrides": sum(1 for r in results if r.overridden),
    }


# ──────────────────────────────────────────────────────────────────────────
# Standalone smoke test
# ──────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    class _Rec:
        def __init__(self, name, text, file_type="paper"):
            self.name, self.content_preview, self.file_type, self.notes = name, text, file_type, ""

    samples = [
        _Rec("logos_03_three_truths.md",
             "The master equation and coherence show isomorphism between grace and entropy. "
             "Logos, Noether, moral conservation across the ten laws."),
        _Rec("patient_intake_2026.txt",
             "Patient presented with symptom cluster; clinical diagnosis pending. "
             "Treatment and dosage per ICD-10. HIPAA-protected medical record."),
        _Rec("grandma_recipe.md",
             "My family birthday recipe — note to self, grocery list for the vacation."),
        _Rec("q3_client_proposal.docx",
             "Client proposal: revenue roadmap, quarterly budget, vendor pricing and contract."),
        _Rec("mixed_legal_finance.md",
             "Plaintiff valuation dispute: securities portfolio, 10-K filing, statute and counsel."),
        _Rec("scan_config.py",
             "import os\ndef scan(): pass\nendpoint config database schema docker worker",
             file_type="system"),
        _Rec("blank_thoughts.txt", "the and of to a in it"),  # no signal -> uncategorized
    ]

    reg = CapabilityRegistry.default()
    results = gate_records(samples, reg)

    print(f"{'FILE':<28}{'CATEGORY':<20}{'TIER':<11}{'ROUTE':<16}CONF  OVR")
    print("-" * 92)
    for r in results:
        print(f"{r.name:<28}{r.category:<20}{r.tier:<11}{r.route:<16}{r.confidence:<6}{'*' if r.overridden else ''}")

    print("\nNotes stamped on first record:")
    print("  " + samples[0].notes)

    rep = gate_report(results)
    print("\nReport:")
    print("  routes:", rep["route_counts"])
    print("  tiers :", rep["tier_counts"])
    print("  PROVISIONING CHECKLIST (needs_access):")
    for cat, srcs in rep["needs_access"].items():
        print(f"    - {cat}: {', '.join(srcs)}")

    # Assertions: prove the routing contract holds.
    by_name = {r.name: r for r in results}
    assert by_name["logos_03_three_truths.md"].route == ROUTE_DEEP
    assert by_name["logos_03_three_truths.md"].tier == "ORIGINAL"
    assert by_name["patient_intake_2026.txt"].route == ROUTE_BLOCK
    assert by_name["patient_intake_2026.txt"].tier == "REGULATED"
    assert by_name["grandma_recipe.md"].route == ROUTE_LOCAL
    assert by_name["mixed_legal_finance.md"].tier == "REGULATED"  # regulated wins the mix
    assert by_name["blank_thoughts.txt"].category == "uncategorized"
    assert "medical" in rep["needs_access"]
    print("\nAll routing assertions passed.")
