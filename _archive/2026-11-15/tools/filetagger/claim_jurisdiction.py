#!/usr/bin/env python3
"""
Claim Jurisdiction Classifier — What / How / Why
=================================================
First pass on any text. Tags every sentence as:
  WHAT  = observation, measurement, data, count, citation
  HOW   = mechanism, structure, process, model, derivation
  WHY   = meaning, purpose, theology, interpretation

Usage:
  python claim_jurisdiction.py "path/to/file.md"
  python claim_jurisdiction.py "path/to/file.html" --output claims.json
  python claim_jurisdiction.py "path/to/folder" --recursive --db claims.db

Every claim must declare whether it describes what is observed,
explains how a structure works, or interprets why it matters.
"""
import argparse, hashlib, html, json, os, re, sqlite3, sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# POS validation layer
try:
    import nltk
    from nltk import word_tokenize, pos_tag
    _HAS_NLTK = True
except ImportError:
    _HAS_NLTK = False

# ── Jurisdiction Signals ──
# Each list: terms that strongly indicate a claim type.
# Multi-word phrases checked first, then single words.

WHAT_SIGNALS = {
    # Phrases
    "phrases": [
        "data shows", "study found", "measured at", "observed that",
        "according to", "rates increased", "rates decreased", "percent of",
        "correlation between", "survey of", "census data", "historical record",
        "files classified", "files scanned", "word count", "appears in",
        "source shows", "published in", "documented in", "recorded in",
        "statistically significant", "p-value", "confidence interval",
        "sample size", "peer-reviewed", "replicated in",
    ],
    # Single words (weighted lower)
    "terms": [
        "observed", "measured", "counted", "detected", "found",
        "recorded", "documented", "cited", "reported", "surveyed",
        "data", "dataset", "measurement", "observation", "evidence",
        "census", "statistic", "frequency", "occurrence", "instance",
        "source", "citation", "reference", "figure", "table",
        "percent", "ratio", "rate", "count", "total",
    ],
}

HOW_SIGNALS = {
    "phrases": [
        "works by", "mechanism is", "because of", "leads to",
        "transforms into", "follows from", "derived from", "results in",
        "if and only if", "necessary condition", "sufficient condition",
        "conserved under", "breaks when", "fails when", "requires that",
        "defined as", "modeled by", "operates through", "classified by",
        "cohere when", "cohere only", "cost-bearing", "resolves through",
        "formally verified", "compiles with", "zero sorry",
        "isomorphic to", "maps onto", "structurally equivalent",
        "predicts that", "would falsify", "kill condition",
    ],
    "terms": [
        "mechanism", "process", "structure", "model", "system",
        "equation", "formula", "operator", "function", "variable",
        "constraint", "invariant", "derivation", "proof", "theorem",
        "axiom", "lemma", "implies", "entails", "therefore",
        "because", "causes", "produces", "generates", "transforms",
        "algorithm", "pipeline", "classifier", "scanner", "engine",
        "conservation", "symmetry", "isomorphism", "mapping",
        "falsifiable", "testable", "reproducible", "prediction",
    ],
}

WHY_SIGNALS = {
    "phrases": [
        "means that", "reveals that", "points to", "ultimately",
        "the purpose of", "the meaning of", "god intended",
        "christ is", "jesus is", "the cross is", "logos is",
        "spiritually", "theologically", "morally significant",
        "reality is grounded", "divine order", "sacred",
        "salvation means", "redemption means", "grace means",
        "the reason is", "matters because", "significance of",
        "image of god", "kingdom of god", "will of god",
        "truth of", "ground of being", "final purpose",
        "moral order", "created order", "divine architecture",
    ],
    "terms": [
        "meaning", "purpose", "significance", "interpretation",
        "sacred", "divine", "spiritual", "transcendent", "eternal",
        "god", "christ", "jesus", "spirit", "logos", "trinity",
        "grace", "sin", "salvation", "redemption", "atonement",
        "worship", "prayer", "faith", "hope", "love",
        "revelation", "scripture", "biblical", "theological",
        "moral", "ought", "should", "must", "duty",
        "good", "evil", "righteous", "holy", "sanctified",
        "destiny", "calling", "vocation", "mission",
    ],
}

# ── Data Classes ──
@dataclass
class ClaimTag:
    claim_id: str
    file_path: str
    sentence_index: int
    text: str
    what_score: float
    how_score: float
    why_score: float
    what_pct: float
    how_pct: float
    why_pct: float
    primary: str          # WHAT | HOW | WHY
    mixed: bool           # True if no single type > 60%
    confidence: float     # margin between primary and runner-up
    overreach_risk: str   # none | low | medium | high
    jurisdiction_note: str
    # POS validation
    pos_noun: float = 0.0
    pos_verb: float = 0.0
    pos_adj: float = 0.0
    pos_adv: float = 0.0
    pos_mismatch: bool = False
    pos_note: str = ""

# ── Text Processing ──
SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style).*?>.*?</\1>")
HTML_TAG_RE = re.compile(r"(?s)<[^>]+>")
SENT_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\'\u201c])')

def read_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in {".html", ".htm"}:
        raw = SCRIPT_STYLE_RE.sub(" ", raw)
        raw = re.sub(r"(?is)</(p|div|section|article|li|h[1-6]|tr)>", "\n", raw)
        raw = HTML_TAG_RE.sub(" ", raw)
        raw = html.unescape(raw)
    return raw.replace("\r\n", "\n").replace("\r", "\n")

def split_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    sents = SENT_SPLIT.split(text)
    return [s.strip() for s in sents if len(s.strip()) > 20]

# ── Scoring ──
def score_signals(text: str, signals: dict) -> float:
    low = text.lower()
    score = 0.0
    # Phrases worth more (2.5 points each)
    for phrase in signals["phrases"]:
        if phrase in low:
            score += 2.5
    # Single terms (1.0 each, but only count unique hits)
    found = set()
    for term in signals["terms"]:
        if re.search(rf"\b{re.escape(term)}\b", low) and term not in found:
            score += 1.0
            found.add(term)
    return score

def classify_sentence(text: str) -> Tuple[float, float, float]:
    what = score_signals(text, WHAT_SIGNALS)
    how = score_signals(text, HOW_SIGNALS)
    why = score_signals(text, WHY_SIGNALS)
    return what, how, why

# ── POS Validation Layer ──
def pos_profile(text: str) -> Dict[str, float]:
    """Get part-of-speech percentages for a sentence."""
    if not _HAS_NLTK:
        return {"noun": 0, "verb": 0, "adj": 0, "adv": 0}
    try:
        tokens = word_tokenize(text)
        tagged = pos_tag(tokens)
    except Exception:
        return {"noun": 0, "verb": 0, "adj": 0, "adv": 0}
    counts = {"noun": 0, "verb": 0, "adj": 0, "adv": 0, "other": 0}
    for _, tag in tagged:
        if tag.startswith("NN"): counts["noun"] += 1
        elif tag.startswith("VB"): counts["verb"] += 1
        elif tag.startswith("JJ"): counts["adj"] += 1
        elif tag.startswith("RB"): counts["adv"] += 1
        else: counts["other"] += 1
    total = max(1, sum(counts.values()))
    return {k: round(v / total * 100, 1) for k, v in counts.items() if k != "other"}

def pos_validation(primary: str, pos: Dict[str, float]) -> Tuple[bool, str]:
    """Check if POS profile matches the keyword classification."""
    noun_pct = pos.get("noun", 0)
    verb_pct = pos.get("verb", 0)
    adj_pct = pos.get("adj", 0)
    adv_pct = pos.get("adv", 0)

    # WHY claim but looks like WHAT (heavy nouns, no interpretive adjectives)
    if primary == "WHY" and adj_pct < 5 and noun_pct > 40:
        return True, "POS suggests WHAT (high nouns, no adjectives) — possible miscategorization"
    # WHAT claim but looks like WHY (heavy adjectives/adverbs, interpretive)
    if primary == "WHAT" and adj_pct > 20 and noun_pct < 25:
        return True, "POS suggests WHY (heavy adjectives) — possible miscategorization"
    # HOW claim but no verbs (mechanism should have process words)
    if primary == "HOW" and verb_pct < 5 and noun_pct > 45:
        return True, "POS suggests WHAT (no verbs for mechanism) — possible miscategorization"
    return False, ""

def normalize(what: float, how: float, why: float) -> Tuple[float, float, float]:
    total = what + how + why
    if total <= 0:
        return 33.3, 33.3, 33.4
    return (
        round(what / total * 100, 1),
        round(how / total * 100, 1),
        round(why / total * 100, 1),
    )

def detect_overreach(what_pct, how_pct, why_pct, primary) -> str:
    """Flag when a claim might be crossing jurisdiction."""
    if primary == "WHAT" and why_pct > 25:
        return "medium"  # data claim with heavy theological language
    if primary == "WHY" and what_pct > 30:
        return "high"    # theological claim pretending to be empirical
    if primary == "HOW" and why_pct > 40:
        return "medium"  # mechanism claim drifting into interpretation
    if primary == "WHY" and how_pct > 40:
        return "low"     # theological claim with structural support (ok)
    return "none"

def jurisdiction_note(primary, overreach) -> str:
    if overreach == "high":
        return "This claim may be crossing jurisdiction. A WHY claim with heavy WHAT language risks implying empirical proof of theological interpretation."
    if overreach == "medium":
        return "Mixed jurisdiction detected. Consider splitting into separate WHAT/HOW/WHY subclaims."
    return ""

# ── Process File ──
def process_file(path: Path) -> List[ClaimTag]:
    text = read_text(path)
    sentences = split_sentences(text)
    claims = []
    for i, sent in enumerate(sentences):
        what, how, why = classify_sentence(sent)
        w_pct, h_pct, y_pct = normalize(what, how, why)
        scores = {"WHAT": w_pct, "HOW": h_pct, "WHY": y_pct}
        primary = max(scores, key=scores.get)
        sorted_scores = sorted(scores.values(), reverse=True)
        margin = sorted_scores[0] - sorted_scores[1]
        mixed = sorted_scores[0] < 60
        overreach = detect_overreach(w_pct, h_pct, y_pct, primary)
        note = jurisdiction_note(primary, overreach)
        # POS validation
        pos = pos_profile(sent)
        mismatch, pos_note_text = pos_validation(primary, pos)
        if mismatch and not note:
            note = pos_note_text
        elif mismatch:
            note += " | " + pos_note_text
        cid = hashlib.sha1(f"{path}|{i}|{sent[:50]}".encode()).hexdigest()[:12]
        claims.append(ClaimTag(
            claim_id=cid,
            file_path=str(path),
            sentence_index=i,
            text=sent[:500],
            what_score=what, how_score=how, why_score=why,
            what_pct=w_pct, how_pct=h_pct, why_pct=y_pct,
            primary=primary,
            mixed=mixed,
            confidence=round(margin, 1),
            overreach_risk=overreach,
            jurisdiction_note=note,
            pos_noun=pos.get("noun", 0),
            pos_verb=pos.get("verb", 0),
            pos_adj=pos.get("adj", 0),
            pos_adv=pos.get("adv", 0),
            pos_mismatch=mismatch,
            pos_note=pos_note_text,
        ))
    return claims

def file_composition(claims: List[ClaimTag]) -> Dict[str, float]:
    if not claims:
        return {"WHAT": 33.3, "HOW": 33.3, "WHY": 33.4}
    w = sum(c.what_pct for c in claims) / len(claims)
    h = sum(c.how_pct for c in claims) / len(claims)
    y = sum(c.why_pct for c in claims) / len(claims)
    total = w + h + y
    return {
        "WHAT": round(w / total * 100, 1),
        "HOW": round(h / total * 100, 1),
        "WHY": round(y / total * 100, 1),
    }

# ── Output ──
def print_summary(path: str, claims: List[ClaimTag]):
    comp = file_composition(claims)
    total = len(claims)
    whats = sum(1 for c in claims if c.primary == "WHAT")
    hows = sum(1 for c in claims if c.primary == "HOW")
    whys = sum(1 for c in claims if c.primary == "WHY")
    mixed = sum(1 for c in claims if c.mixed)
    overreach = sum(1 for c in claims if c.overreach_risk in ("medium","high"))
    pos_mismatches = sum(1 for c in claims if c.pos_mismatch)

    print(f"\n{'='*60}")
    print(f"  CLAIM JURISDICTION REPORT")
    print(f"  {path}")
    print(f"{'='*60}")
    print(f"\n  Composition (normalized to 100%):")
    print(f"    WHAT  {comp['WHAT']:5.1f}%  (observation / evidence)")
    print(f"    HOW   {comp['HOW']:5.1f}%  (mechanism / structure)")
    print(f"    WHY   {comp['WHY']:5.1f}%  (meaning / theology)")
    print(f"\n  Sentences: {total}")
    print(f"    WHAT-primary: {whats}")
    print(f"    HOW-primary:  {hows}")
    print(f"    WHY-primary:  {whys}")
    print(f"    Mixed (no type >60%): {mixed}")
    print(f"    Overreach flags: {overreach}")
    print(f"    POS mismatches: {pos_mismatches}")

    if pos_mismatches:
        print(f"\n  POS VALIDATION MISMATCHES:")
        for c in claims:
            if c.pos_mismatch:
                print(f"    [{c.primary}->???] N:{c.pos_noun:.0f}% V:{c.pos_verb:.0f}% A:{c.pos_adj:.0f}%  {c.text[:70].encode('ascii','replace').decode()}...")

    if overreach:
        print(f"\n  OVERREACH WARNINGS:")
        for c in claims:
            if c.overreach_risk in ("medium", "high"):
                print(f"    [{c.overreach_risk.upper()}] {c.primary} claim: {c.text[:80].encode('ascii','replace').decode()}...")
    print(f"{'='*60}\n")

def write_json(claims: List[ClaimTag], path: str, out: Path):
    comp = file_composition(claims)
    report = {
        "file": path,
        "engine": "claim_jurisdiction v1.0",
        "generated": datetime.now().isoformat(),
        "composition": comp,
        "total_claims": len(claims),
        "claims": [asdict(c) for c in claims],
    }
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

SCHEMA = """CREATE TABLE IF NOT EXISTS claims(
    claim_id TEXT PRIMARY KEY, file_path TEXT, sentence_index INTEGER,
    text TEXT, what_score REAL, how_score REAL, why_score REAL,
    what_pct REAL, how_pct REAL, why_pct REAL,
    [primary] TEXT, mixed INTEGER, confidence REAL,
    overreach_risk TEXT, jurisdiction_note TEXT,
    pos_noun REAL, pos_verb REAL, pos_adj REAL, pos_adv REAL,
    pos_mismatch INTEGER, pos_note TEXT);
CREATE INDEX IF NOT EXISTS idx_claims_primary ON claims([primary]);
CREATE INDEX IF NOT EXISTS idx_claims_file ON claims(file_path);
CREATE INDEX IF NOT EXISTS idx_claims_overreach ON claims(overreach_risk);
CREATE INDEX IF NOT EXISTS idx_claims_mismatch ON claims(pos_mismatch);"""

def write_db(claims: List[ClaimTag], db_path: Path):
    db = sqlite3.connect(db_path)
    db.executescript(SCHEMA)
    db.executemany(
        "INSERT OR REPLACE INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(c.claim_id, c.file_path, c.sentence_index, c.text,
          c.what_score, c.how_score, c.why_score,
          c.what_pct, c.how_pct, c.why_pct,
          c.primary, int(c.mixed), c.confidence,
          c.overreach_risk, c.jurisdiction_note,
          c.pos_noun, c.pos_verb, c.pos_adj, c.pos_adv,
          int(c.pos_mismatch), c.pos_note) for c in claims]
    )
    db.commit()
    db.close()

# ── Main ──
def main():
    ap = argparse.ArgumentParser(description="Claim Jurisdiction Classifier — What/How/Why")
    ap.add_argument("path", help="File or folder to classify")
    ap.add_argument("--output", help="Write JSON report to this path")
    ap.add_argument("--db", help="Write to SQLite database")
    ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--max-files", type=int, default=0)
    a = ap.parse_args()

    target = Path(a.path)
    if target.is_file():
        files = [target]
    elif target.is_dir():
        glob = target.rglob("*") if a.recursive else target.glob("*")
        files = [f for f in glob if f.suffix.lower() in
                 {".md",".txt",".html",".htm",".tex",".rst"}]
    else:
        print(f"Not found: {a.path}")
        return 1

    if a.max_files:
        files = files[:a.max_files]

    all_claims = []
    for i, f in enumerate(files, 1):
        claims = process_file(f)
        all_claims.extend(claims)
        print_summary(str(f), claims)

    if len(files) > 1:
        comp = file_composition(all_claims)
        total = len(all_claims)
        print(f"\n{'='*60}")
        print(f"  CORPUS COMPOSITION ({len(files)} files, {total} claims)")
        print(f"{'='*60}")
        print(f"    WHAT  {comp['WHAT']:5.1f}%")
        print(f"    HOW   {comp['HOW']:5.1f}%")
        print(f"    WHY   {comp['WHY']:5.1f}%")
        overreach = sum(1 for c in all_claims if c.overreach_risk in ("medium","high"))
        print(f"    Overreach flags: {overreach} / {total}")
        print(f"{'='*60}\n")

    if a.output:
        write_json(all_claims, str(target), Path(a.output))
        print(f"JSON: {a.output}")

    if a.db:
        write_db(all_claims, Path(a.db))
        print(f"DB: {a.db}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
