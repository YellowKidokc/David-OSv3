#!/usr/bin/env python3
"""
Chi Pipeline — Modular classification pipeline.
================================================
Each stage is independent. Run one, run all, swap pieces.
Works for claims AND files — same logic, different vocabulary.

Usage:
  # Full pipeline
  python chi_pipeline.py "path/to/file.md" --all

  # Just jurisdiction (What/How/Why)
  python chi_pipeline.py "path/to/file.md" --jurisdiction

  # Just chi classification (Master Equation)
  python chi_pipeline.py "path/to/file.md" --chi

  # Jurisdiction + Law 5 only
  python chi_pipeline.py "path/to/file.md" --jurisdiction --law5

  # File mode (classify files, not claims)
  python chi_pipeline.py "path/to/folder" --file-mode --chi

  # Config file
  python chi_pipeline.py "path" --config pipeline.yaml

Stages:
  1. jurisdiction  — What / How / Why classifier
  2. chi           — Master Equation (G M E S T K R Q F C)
  3. domain        — Domain classifier (physics, theology, etc.)
  4. law5          — Justice / Mercy / Cost-bearer
  5. evidence      — Citation / source / data checker
  6. fruit         — Fruit / anti-fruit presence
  7. audit         — Corpus-level statistics + report
"""
import argparse, json, os, sqlite3, sys, importlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Stage Interface ──
# Every stage implements: name, enabled, process(record) -> record
# A record is a dict that flows through the pipeline.
# Each stage ADDS to the record, never removes.

@dataclass
class StageResult:
    stage: str
    enabled: bool
    ran: bool
    duration_ms: float = 0
    items_processed: int = 0
    error: str = ""

@dataclass
class PipelineRecord:
    """Flows through all stages. Each stage adds its key."""
    source_path: str
    source_type: str           # "file" | "claim" | "sentence"
    text: str
    text_length: int = 0
    word_count: int = 0

    # Stage outputs — each is None until that stage runs
    jurisdiction: Optional[Dict] = None    # What/How/Why
    chi: Optional[Dict] = None             # Master Equation
    domains: Optional[Dict] = None         # Domain composition
    law5: Optional[Dict] = None            # Justice/Mercy/Cost-bearer
    evidence: Optional[Dict] = None        # Citation/source check
    fruit: Optional[Dict] = None           # Fruit/anti-fruit
    audit: Optional[Dict] = None           # Corpus stats

    metadata: Dict = field(default_factory=dict)
    stages_run: List[str] = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        # Strip None stages for clean output
        return {k: v for k, v in d.items() if v is not None}

# ── Stage Implementations ──
# Each stage is a function: process(record: PipelineRecord) -> PipelineRecord
# Stages import from existing scripts when available, fall back to inline.

import re, hashlib, html as html_mod, time

STOP = set("the a an and or of to in is it for on with as by at from this that be are "
    "was were will would can could should not no but if then else your our their his "
    "her its my me us them which who what when where how why all any some more most "
    "other into over under out up down off than too very just have has had do does did "
    "been being about also such only there here".split())

HTML_STRIP = re.compile(r"(?is)<(script|style).*?>.*?</\1>")
HTML_TAGS = re.compile(r"(?s)<[^>]+>")

def clean_text(text, ext=""):
    if ext in (".html", ".htm"):
        text = HTML_STRIP.sub(" ", text)
        text = re.sub(r"(?is)</(p|div|section|article|li|h[1-6]|tr)>", "\n", text)
        text = HTML_TAGS.sub(" ", text)
        text = html_mod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()

def word_tokens(text):
    return [w for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in STOP]

def score_terms(text, phrases, terms):
    low = text.lower()
    s = 0.0
    for p in phrases:
        if p in low: s += 2.5
    found = set()
    for t in terms:
        if re.search(rf"\b{re.escape(t)}\b", low) and t not in found:
            s += 1.0; found.add(t)
    return s

def normalize_scores(scores):
    total = sum(scores.values())
    if total <= 0:
        n = len(scores)
        return {k: round(100/n, 1) for k in scores}
    return {k: round(v / total * 100, 1) for k, v in scores.items()}

# ── STAGE 1: Jurisdiction (What/How/Why) ──
WHAT_PH = ["data shows","study found","measured at","observed that","according to",
    "rates increased","percent of","correlation between","peer-reviewed","sample size"]
WHAT_TM = ["observed","measured","counted","detected","data","evidence","citation",
    "source","reference","percent","ratio","rate","count","documented","reported"]

HOW_PH = ["works by","mechanism is","leads to","follows from","derived from",
    "results in","defined as","cohere when","cost-bearing","resolves through",
    "isomorphic to","predicts that","would falsify","kill condition","if and only if"]
HOW_TM = ["mechanism","process","structure","model","equation","formula","operator",
    "constraint","derivation","proof","theorem","axiom","because","causes",
    "produces","algorithm","pipeline","conservation","isomorphism","falsifiable"]

WHY_PH = ["means that","reveals that","ultimately","the purpose of","god intended",
    "christ is","the cross is","spiritually","theologically","reality is grounded",
    "matters because","kingdom of god","moral order","divine architecture"]
WHY_TM = ["meaning","purpose","significance","sacred","divine","spiritual","god",
    "christ","jesus","logos","trinity","grace","sin","salvation","redemption",
    "moral","ought","should","good","evil","holy","destiny","calling"]

def stage_jurisdiction(rec):
    text = rec.text
    w = score_terms(text, WHAT_PH, WHAT_TM)
    h = score_terms(text, HOW_PH, HOW_TM)
    y = score_terms(text, WHY_PH, WHY_TM)
    scores = {"WHAT": w, "HOW": h, "WHY": y}
    pcts = normalize_scores(scores)
    primary = max(pcts, key=pcts.get)
    vals = sorted(pcts.values(), reverse=True)
    rec.jurisdiction = {
        "what_pct": pcts["WHAT"], "how_pct": pcts["HOW"], "why_pct": pcts["WHY"],
        "primary": primary, "mixed": vals[0] < 60,
        "confidence": round(vals[0] - vals[1], 1),
        "unscoped": vals[0] < 45,
    }
    return rec

# ── STAGE 2: Chi Classification (Master Equation) ──
CHI_TERMS = {
    "G": ["grace","mercy","restore","redemption","forgive","draw","attract"],
    "M": ["will","repentance","moral","alignment","choice","conversion","decision"],
    "E": ["truth","evidence","source","measure","citation","data","observation"],
    "S": ["entropy","judgment","decay","consequence","collapse","disorder","heat"],
    "T": ["time","kairos","sequence","history","threshold","epoch","timeline"],
    "K": ["knowledge","information","logos","signal","model","channel","encoding"],
    "R": ["relationship","family","covenant","binding","community","love","neighbor"],
    "Q": ["quantum","faith","observer","measurement","uncertainty","collapse","wave"],
    "F": ["force","action","motion","momentum","conservation","moral force"],
    "C": ["coherence","christ","integration","shalom","kingdom","unity","wholeness"],
}

def stage_chi(rec):
    toks = set(word_tokens(rec.text))
    raw = {}
    for var, terms in CHI_TERMS.items():
        raw[var] = sum(1 for t in terms if t in toks or t in rec.text.lower())
    rec.chi = {"raw": raw, "vector": normalize_scores(raw),
               "primary": max(raw, key=raw.get) if any(raw.values()) else "UC"}
    return rec

# ── STAGE 3: Domain Classification ──
DOMAIN_TERMS = {
    "physics": ["physics","quantum","field","entropy","relativity","gravity","mass","energy"],
    "theology": ["god","christ","jesus","spirit","grace","sin","salvation","scripture","logos"],
    "epistemology": ["truth","knowledge","ground","regress","assumption","falsifiability","method"],
    "formal_math": ["equation","theorem","proof","lean","operator","function","variable","axiom"],
    "information": ["information","signal","noise","channel","shannon","compression","encoding"],
    "ethics": ["good","evil","justice","ought","virtue","responsibility","accountability"],
    "psychology": ["behavior","emotion","anxiety","habit","trauma","identity","willpower"],
    "sociology": ["society","institution","culture","community","family","civilization"],
    "history": ["historical","century","document","record","timeline","era","period"],
}

def stage_domain(rec):
    toks = set(word_tokens(rec.text))
    low = rec.text.lower()
    raw = {}
    for dom, terms in DOMAIN_TERMS.items():
        raw[dom] = sum(1 for t in terms if t in toks or t in low)
    rec.domains = {"raw": raw, "composition": normalize_scores(raw),
                   "primary": max(raw, key=raw.get) if any(raw.values()) else "unknown"}
    return rec

# ── STAGE 4: Law 5 — Justice / Mercy / Cost-Bearer ──
JUSTICE_TERMS = ["accountability","consequence","judgment","restitution","boundary",
    "violation","debt","responsibility","sentence","penalty","punishment","standard"]
MERCY_TERMS = ["grace","mercy","forgiveness","patience","restoration","reconciliation",
    "repair","compassion","dignity","healing","redemption","second chance"]
COST_TERMS = ["pay","cost","absorb","bear","carry","sacrifice","restitution","atone",
    "repair","compensate","substitute","mediator","voluntary","cross","price"]
COERCION_TERMS = ["force","coerce","dominate","manipulate","scapegoat","blame",
    "externalize","displace","demand","compel"]

def stage_law5(rec):
    low = rec.text.lower()
    j = sum(1 for t in JUSTICE_TERMS if t in low)
    m = sum(1 for t in MERCY_TERMS if t in low)
    c = sum(1 for t in COST_TERMS if t in low)
    x = sum(1 for t in COERCION_TERMS if t in low)
    j_s = min(100, j * 12)
    m_s = min(100, m * 12)
    c_s = min(100, c * 14)
    x_s = min(100, x * 16)
    coherence = min(j_s, m_s) + c_s - x_s
    coherence = max(0, min(100, coherence))
    if j_s > 60 and m_s < 20: diag = "terminal justice — mercy absent"
    elif m_s > 60 and j_s < 20: diag = "false mercy — justice absent"
    elif j_s > 40 and m_s > 40 and c_s < 15: diag = "contradiction — no cost-bearer"
    elif j_s > 40 and m_s > 40 and c_s > 30: diag = "coherent — valid resolution path"
    elif x_s > 40: diag = "coercive — forced cost displacement"
    else: diag = "low signal"
    rec.law5 = {
        "justice": j_s, "mercy": m_s, "cost_bearer": c_s,
        "coercion": x_s, "coherence": coherence, "diagnosis": diag,
    }
    return rec

# ── STAGE 5: Evidence Check ──
EVIDENCE_TERMS = ["source","citation","data","study","measurement","observed","figure",
    "table","peer-reviewed","replication","statistical","sample","empirical"]
OVERCLAIM_TERMS = ["proves","undeniable","impossible","always","never","every",
    "no one can deny","without exception","absolute","definitively"]

def stage_evidence(rec):
    low = rec.text.lower()
    ev = sum(1 for t in EVIDENCE_TERMS if t in low)
    oc = sum(1 for t in OVERCLAIM_TERMS if t in low)
    ev_s = min(100, ev * 12)
    oc_s = min(100, oc * 18)
    rec.evidence = {
        "evidence_score": ev_s, "overclaim_score": oc_s,
        "balance": max(0, ev_s - oc_s),
        "risk": "high" if oc_s > ev_s + 20 else "medium" if oc_s > ev_s else "low",
    }
    return rec

# ── STAGE 6: Fruit / Anti-Fruit ──
FRUITS = ["love","joy","peace","patience","kindness","goodness","faithfulness",
    "gentleness","self-control","hope","humility","unity","dignity","forgive"]
ANTI_FRUITS = ["hatred","despair","anxiety","impatience","cruelty","corruption",
    "betrayal","harshness","addiction","rage","domination","coercion","contempt",
    "dehumanization","manipulation","panic"]

def stage_fruit(rec):
    toks = set(word_tokens(rec.text))
    f = sum(1 for t in FRUITS if t in toks)
    a = sum(1 for t in ANTI_FRUITS if t in toks)
    f_s = min(100, f * 12)
    a_s = min(100, a * 12)
    rec.fruit = {
        "fruit_score": f_s, "anti_fruit_score": a_s,
        "balance": f_s - a_s,
        "signal": "healthy" if f_s > a_s + 20 else "mixed" if abs(f_s - a_s) < 20 else "concerning",
    }
    return rec

# ── Pipeline Orchestrator ──
STAGES = {
    "jurisdiction": stage_jurisdiction,
    "chi": stage_chi,
    "domain": stage_domain,
    "law5": stage_law5,
    "evidence": stage_evidence,
    "fruit": stage_fruit,
}

DEFAULT_ORDER = ["jurisdiction", "chi", "domain", "law5", "evidence", "fruit"]

def run_pipeline(text: str, source_path: str = "", source_type: str = "file",
                 enabled_stages: List[str] = None, ext: str = "") -> PipelineRecord:
    """Run enabled stages on text. Returns enriched record."""
    cleaned = clean_text(text, ext)
    rec = PipelineRecord(
        source_path=source_path,
        source_type=source_type,
        text=cleaned,
        text_length=len(cleaned),
        word_count=len(word_tokens(cleaned)),
    )
    stages = enabled_stages or DEFAULT_ORDER
    for stage_name in stages:
        fn = STAGES.get(stage_name)
        if fn:
            t0 = time.time()
            rec = fn(rec)
            rec.stages_run.append(stage_name)
    return rec

def process_file(path: Path, enabled_stages: List[str] = None) -> Dict:
    """Process a single file through the pipeline."""
    ext = path.suffix.lower()
    text = path.read_text(encoding="utf-8", errors="replace")
    rec = run_pipeline(text, str(path), "file", enabled_stages, ext)
    return rec.to_dict()

def process_text(text: str, label: str = "input",
                 enabled_stages: List[str] = None) -> Dict:
    """Process raw text (for claim-level or stdin usage)."""
    rec = run_pipeline(text, label, "claim", enabled_stages)
    return rec.to_dict()

# ── Output ──
def print_report(result: Dict, path: str = ""):
    print(f"\n{'='*60}")
    print(f"  CHI PIPELINE REPORT")
    if path: print(f"  {path}")
    print(f"  Stages: {', '.join(result.get('stages_run', []))}")
    print(f"  Words: {result.get('word_count', 0)}")
    print(f"{'='*60}")

    if result.get("jurisdiction"):
        j = result["jurisdiction"]
        print(f"\n  JURISDICTION (What / How / Why):")
        print(f"    WHAT  {j['what_pct']:5.1f}%")
        print(f"    HOW   {j['how_pct']:5.1f}%")
        print(f"    WHY   {j['why_pct']:5.1f}%")
        print(f"    Primary: {j['primary']}  |  Mixed: {j['mixed']}  |  Unscoped: {j.get('unscoped', False)}")

    if result.get("chi"):
        c = result["chi"]
        print(f"\n  CHI VECTOR (Master Equation):")
        print(f"    Primary: {c['primary']}")
        top3 = sorted(c['vector'].items(), key=lambda x: -x[1])[:3]
        for var, pct in top3:
            print(f"    [{var}] {pct:5.1f}%")

    if result.get("domains"):
        d = result["domains"]
        print(f"\n  DOMAIN COMPOSITION:")
        top4 = sorted(d['composition'].items(), key=lambda x: -x[1])[:4]
        for dom, pct in top4:
            print(f"    {dom:15s} {pct:5.1f}%")

    if result.get("law5"):
        l = result["law5"]
        print(f"\n  LAW 5 (Justice / Mercy / Cost-Bearer):")
        print(f"    Justice:     {l['justice']}")
        print(f"    Mercy:       {l['mercy']}")
        print(f"    Cost-bearer: {l['cost_bearer']}")
        print(f"    Coercion:    {l['coercion']}")
        print(f"    Coherence:   {l['coherence']}")
        print(f"    Diagnosis:   {l['diagnosis']}")

    if result.get("evidence"):
        e = result["evidence"]
        print(f"\n  EVIDENCE:")
        print(f"    Evidence:  {e['evidence_score']}  |  Overclaim: {e['overclaim_score']}  |  Risk: {e['risk']}")

    if result.get("fruit"):
        f = result["fruit"]
        print(f"\n  FRUIT:")
        print(f"    Fruit: {f['fruit_score']}  |  Anti-fruit: {f['anti_fruit_score']}  |  Signal: {f['signal']}")

    print(f"\n{'='*60}\n")

# ── Main ──
def main():
    ap = argparse.ArgumentParser(
        description="Chi Pipeline — modular classification. Each stage independent.")
    ap.add_argument("path", nargs="?", help="File, folder, or - for stdin")
    ap.add_argument("--all", action="store_true", help="Run all stages")
    ap.add_argument("--jurisdiction", action="store_true", help="What/How/Why")
    ap.add_argument("--chi", action="store_true", help="Master Equation")
    ap.add_argument("--domain", action="store_true", help="Domain composition")
    ap.add_argument("--law5", action="store_true", help="Justice/Mercy/Cost-bearer")
    ap.add_argument("--evidence", action="store_true", help="Evidence/overclaim")
    ap.add_argument("--fruit", action="store_true", help="Fruit/anti-fruit")
    ap.add_argument("--output", help="Write JSON to this path")
    ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--max-files", type=int, default=0)
    ap.add_argument("--text", help="Classify raw text instead of file")
    a = ap.parse_args()

    # Build stage list from flags
    stages = []
    if a.all:
        stages = list(DEFAULT_ORDER)
    else:
        if a.jurisdiction: stages.append("jurisdiction")
        if a.chi: stages.append("chi")
        if a.domain: stages.append("domain")
        if a.law5: stages.append("law5")
        if a.evidence: stages.append("evidence")
        if a.fruit: stages.append("fruit")
    if not stages:
        stages = list(DEFAULT_ORDER)  # default: all

    # Text mode
    if a.text:
        result = process_text(a.text, "cli-input", stages)
        print_report(result, "cli-input")
        if a.output:
            Path(a.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 0

    if not a.path:
        ap.error("Provide a file/folder path or --text")

    target = Path(a.path)
    if target.is_file():
        files = [target]
    elif target.is_dir():
        glob = target.rglob("*") if a.recursive else target.glob("*")
        files = [f for f in glob if f.suffix.lower() in
                 {".md",".txt",".html",".htm",".tex",".rst",".lean"}]
    else:
        print(f"Not found: {a.path}")
        return 1

    if a.max_files:
        files = files[:a.max_files]

    results = []
    for f in files:
        result = process_file(f, stages)
        results.append(result)
        print_report(result, str(f))

    if a.output and results:
        report = {
            "engine": "chi_pipeline v1.0",
            "stages": stages,
            "generated": datetime.now().isoformat(),
            "files": len(results),
            "results": results,
        }
        Path(a.output).write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"JSON: {a.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
