"""lexicon_overlay.py — Load the canonical lexicon JSON and score deep_identify cards against it.

The lexicon adds:
  - 215 theophysics domain terms (vs 21 hardcoded) across 10 laws + fruits + coherence + wisdom
  - Article doc type (subscribe, blog, published, series, part N, read more)
  - Expanded paper markers (+ theorem, proof, lemma, methodology)
  - Expanded note markers (+ draft, idea, rough)
  - Claim strength scoring (weak_inference / moderate_claim / strong_claim with weights)
  - Per-law keyword detection (which of the 10 Laws does this document touch?)

Usage:
    from lexicon_overlay import LexiconOverlay
    lex = LexiconOverlay("path/to/lexicon_canonical.json")
    lex.score_card(card)          # mutates the FileCard in place
    lex.score_all(cards, stats)   # batch + update stats
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deep_identify import FileCard

_FENCE_RE = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)


def _strip_code_fences(text: str) -> str:
    """Remove fenced code blocks so their content doesn't trigger doc-type markers."""
    return _FENCE_RE.sub("", text)


class LexiconOverlay:
    def __init__(self, path: str | Path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))

        # Domain: build a single theophysics vocabulary from all law keywords + term sheets
        self.law_terms: dict[str, set[str]] = {}
        for law, terms in data.get("LAW_KEYWORDS", {}).items():
            self.law_terms[law] = set(t.lower() for t in terms)

        self.theophysics_vocab: set[str] = set()
        for terms in self.law_terms.values():
            self.theophysics_vocab |= terms
        for sheet in ["COHERENCE_TERMS", "WISDOM_TERMS", "KNOWLEDGE_TERMS", "FRUITS", "ANTI_FRUITS"]:
            self.theophysics_vocab |= set(t.lower() for t in data.get(sheet, []))

        # Doc type markers from lexicon
        self.doc_markers: dict[str, list[str]] = {}
        for dtype, markers in data.get("DOC_TYPE_PATTERNS", {}).items():
            self.doc_markers[dtype] = [m.lower() for m in markers]

        # Semantic buckets: term -> {bucket, subbucket, weight, danger_level}
        self.buckets: dict[str, dict] = {}
        for entry in data.get("SEMANTIC_BUCKETS", []):
            term = entry.get("term", "").lower()
            if term:
                self.buckets[term] = {
                    "bucket": entry.get("bucket", ""),
                    "subbucket": entry.get("subbucket", ""),
                    "weight": float(entry.get("weight", 1)),
                    "danger_level": entry.get("danger_level", ""),
                }

        # Claim/evidence/hedge terms for prose analysis
        self.claim_terms = set(t.lower() for t in data.get("CLAIM_TERMS", []))
        self.evidence_terms = set(t.lower() for t in data.get("EVIDENCE_TERMS", []))
        self.hedge_terms = set(t.lower() for t in data.get("HEDGE_TERMS", []))
        self.falsify_terms = set(t.lower() for t in data.get("FALSIFY_TERMS", []))
        self.bridge_terms = set(t.lower() for t in data.get("BRIDGE_TERMS", []))

    def _domain_score(self, tokens: list[str]) -> tuple[str, float, dict]:
        """Score tokens against the full lexicon domain vocabulary. Returns (domain, confidence, law_hits)."""
        token_set = set(tokens)
        hits = token_set & self.theophysics_vocab
        if not hits:
            return "unknown", 0.0, {}

        # Which laws are touched?
        law_hits = {}
        for law, terms in self.law_terms.items():
            overlap = token_set & terms
            if overlap:
                law_hits[law] = sorted(overlap)

        # Confidence: proportion of vocabulary hit, capped
        conf = min(len(hits) / 15.0, 1.0)  # 15+ hits = full confidence
        return "theophysics", round(conf, 4), law_hits

    def _doc_type_boost(self, text_lower: str, current_type: str, current_conf: float,
                        file_kind: str) -> tuple[str, float]:
        """Check lexicon doc_type_patterns against the text. Returns (type, confidence) if stronger.

        Priority rules:
        - Extension-based kinds (code, data, media, config, sidecar) are never overridden by content markers
        - A structural 'paper' call (abstract/introduction/conclusion found) is never demoted to 'code'
          by markers that appear inside code fences
        - Code markers (def, function, import, class, const) inside ``` fences don't count
        """
        # Extension-classified files: the structural classifier already got this right
        if file_kind in ("code", "data", "picture", "video", "audio", "archive", "config", "sidecar"):
            return current_type, current_conf

        # Strip code fences before checking code markers — a paper with code blocks is still a paper
        text_no_fences = _strip_code_fences(text_lower)

        best_type, best_score = current_type, current_conf
        for dtype, markers in self.doc_markers.items():
            # For code markers, use fence-stripped text
            check_text = text_no_fences if dtype == "code" else text_lower
            hits = sum(1 for m in markers if m in check_text)
            if hits == 0:
                continue
            score = min(hits / max(len(markers), 1) * 1.5, 1.0)

            # Paper-protection rule: if structural classifier found paper markers,
            # code/note/data can't override unless they score much higher
            if current_type == "paper" and current_conf >= 0.4 and dtype in ("code", "note", "data"):
                score *= 0.3  # heavy penalty — need overwhelming evidence to demote a paper

            if score > best_score:
                best_type, best_score = dtype, round(score, 4)
        return best_type, best_score

    def _claim_profile(self, text_lower: str) -> dict:
        """Profile the claim language in the text."""
        profile = {"claim_hits": 0, "evidence_hits": 0, "hedge_hits": 0,
                   "falsify_hits": 0, "bridge_hits": 0, "bucket_hits": []}
        for t in self.claim_terms:
            if t in text_lower:
                profile["claim_hits"] += 1
        for t in self.evidence_terms:
            if t in text_lower:
                profile["evidence_hits"] += 1
        for t in self.hedge_terms:
            if t in text_lower:
                profile["hedge_hits"] += 1
        for t in self.falsify_terms:
            if t in text_lower:
                profile["falsify_hits"] += 1
        for t in self.bridge_terms:
            if t in text_lower:
                profile["bridge_hits"] += 1
        # Semantic bucket matches
        for term, info in self.buckets.items():
            if term in text_lower:
                profile["bucket_hits"].append({
                    "term": term, "bucket": info["bucket"],
                    "subbucket": info["subbucket"], "weight": info["weight"],
                    "danger_level": info["danger_level"],
                })
        return profile

    def score_card(self, card: "FileCard", text_sample: str = "") -> dict:
        """Score one card against the lexicon. Mutates card in place. Returns the overlay evidence."""
        evidence = {"lexicon_version": "v2_2026-11-06"}
        tokens = card.content_tokens if hasattr(card, "content_tokens") else []

        # Domain boost
        domain, conf, law_hits = self._domain_score(tokens)
        if conf > card.domain_confidence:
            card.domain = domain
            card.domain_confidence = conf
            evidence["domain_boosted"] = True
        evidence["law_hits"] = law_hits

        # Doc type boost
        if text_sample and card.file_kind == "document":
            new_type, new_conf = self._doc_type_boost(text_sample.lower(), card.doc_type,
                                                      card.doc_type_confidence, card.file_kind)
            if new_conf > card.doc_type_confidence:
                evidence["doc_type_changed"] = {"from": card.doc_type, "to": new_type}
                card.doc_type = new_type
                card.doc_type_confidence = new_conf

        # Claim profile
        if text_sample:
            evidence["claim_profile"] = self._claim_profile(text_sample.lower())

        # Recalculate identity confidence with the boosted scores
        conf_signals = [
            card.domain_confidence,
            card.doc_type_confidence,
            1.0 if card.file_kind != "unknown" else 0.0,
            0.8 if getattr(card, "has_yaml_frontmatter", False) else 0.0,
            0.5 if getattr(card, "section_count", 0) > 0 else 0.0,
        ]
        new_conf = round(sum(conf_signals) / len(conf_signals), 4)
        if new_conf > card.identity_confidence:
            evidence["confidence_boosted"] = {"from": card.identity_confidence, "to": new_conf}
            card.identity_confidence = new_conf

        return evidence

    def score_all(self, cards: list["FileCard"], stats: dict, text_cache: dict[str, str] | None = None) -> list[dict]:
        """Score all cards. text_cache maps path -> text sample for doc_type and claim analysis."""
        cache = text_cache or {}
        results = []
        boosted_domain = 0
        boosted_type = 0
        boosted_conf = 0
        total_law_coverage: dict[str, int] = Counter()

        for card in cards:
            text = cache.get(card.path, "")
            ev = self.score_card(card, text)
            results.append(ev)
            if ev.get("domain_boosted"):
                boosted_domain += 1
            if ev.get("doc_type_changed"):
                boosted_type += 1
            if ev.get("confidence_boosted"):
                boosted_conf += 1
            for law in ev.get("law_hits", {}):
                total_law_coverage[law] += 1

        stats["lexicon_overlay"] = {
            "version": "v2_2026-11-06",
            "cards_scored": len(cards),
            "domain_boosted": boosted_domain,
            "doc_type_changed": boosted_type,
            "confidence_boosted": boosted_conf,
            "law_coverage": dict(total_law_coverage.most_common()),
        }
        # Recalculate aggregate stats
        stats["domain_distribution"] = dict(Counter(c.domain for c in cards).most_common())
        stats["doc_type_distribution"] = dict(Counter(c.doc_type for c in cards).most_common())
        stats["avg_identity_confidence"] = round(
            sum(c.identity_confidence for c in cards) / max(len(cards), 1), 4)
        return results
