#!/usr/bin/env python3
"""Companion Paper Stats Engine — POF 2828 Pipeline Tool.

20 analysis modes over the companion .md corpus. Reuses the parser
from companion_cluster.py (must be in the same folder).

USAGE:
    python companion_stats.py                        # run all 20 modes
    python companion_stats.py --mode scoreboard      # run one mode
    python companion_stats.py --mode scoreboard --mode domain_breakdown
    python companion_stats.py --list                 # list available modes
    python companion_stats.py --json                 # machine-readable
    python companion_stats.py /path/to/outbox        # override root

All 20 modes:
     1. scoreboard          — Overall score distribution (histogram + percentiles)
     2. grade_curve         — Grade distribution (A/B/C/D/F counts)
     3. domain_breakdown    — Papers per primary domain
     4. domain_cross        — Domain co-occurrence matrix
     5. tag_frequency       — Most common weighted tags
     6. tag_heatmap         — Tag × domain frequency table
     7. evidence_balance    — Evidence support vs counter distribution
     8. weakest_claims      — Papers ranked by weakest claim (lowest evd_balance)
     9. strongest_claims    — Papers ranked by strongest evidence
    10. section_scores      — Average score per section (S01–S10) across all papers
    11. build_next_priority — build_next items ranked by frequency/urgency
    12. argument_density    — Papers ranked by argument step count
    13. framework_key_map   — Which framework keys appear most, and in which papers
    14. coherence_ranking   — Papers ranked by coherence score
    15. content_type_dist   — Distribution of content types (ct-reference-index, etc.)
    16. stale_candidates    — Low-score papers that might need retirement or rewrite
    17. bridge_audit        — Papers where bridge integrity (S08) scored 0 or below
    18. formal_gaps         — Papers where formal/math (S07) scored lowest
    19. honesty_chain       — Papers where the honesty chain sections score below 3
    20. progress_dashboard  — Summary: total papers, avg score, coverage, readiness
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# Import parser from companion_cluster.py (same folder)
try:
    from companion_cluster import (
        OUTBOX_ROOT as DEFAULT_ROOT,
        CompanionRecord,
        scan_outbox,
    )
except ImportError:
    print("ERROR: companion_cluster.py must be in the same folder.")
    print("  This script reuses its parser.")
    sys.exit(1)

OUTBOX_ROOT = DEFAULT_ROOT


# ──────────────────────────────────────────────────────────────────
# SECTION SCORE EXTRACTOR
# ──────────────────────────────────────────────────────────────────

def extract_section_scores(filepath: str) -> dict[str, dict[str, int]]:
    """Extract S01–S10 pos/neg/net scores from the YAML frontmatter."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception:
        return {}

    scores = {}
    for i in range(1, 11):
        key = f"s{i:02d}"
        pos_m = re.search(rf"{key}_pos:\s*(\d+)", text)
        neg_m = re.search(rf"{key}_neg:\s*(\d+)", text)
        net_m = re.search(rf"{key}_net:\s*(-?\d+)", text)
        if pos_m and neg_m and net_m:
            scores[key] = {
                "pos": int(pos_m.group(1)),
                "neg": int(neg_m.group(1)),
                "net": int(net_m.group(1)),
            }
    return scores


SECTION_NAMES = {
    "s01": "Classification & Routing",
    "s02": "Claim Definition",
    "s03": "Argument Structure",
    "s04": "Evidence & Support",
    "s05": "Objections & Survival",
    "s06": "Boundaries & Honesty",
    "s07": "Formal & Math",
    "s08": "Bridge Integrity",
    "s09": "Falsifiability & Predictions",
    "s10": "Audit & Provenance",
}

# S05, S06, S08, S09 are "honesty chain"; S02, S03, S04, S07 are "load-bearing"
HONESTY_SECTIONS = {"s05", "s06", "s08", "s09"}
LOADBEARING_SECTIONS = {"s02", "s03", "s04", "s07"}


# ──────────────────────────────────────────────────────────────────
# 20 ANALYSIS MODES
# ──────────────────────────────────────────────────────────────────

def mode_scoreboard(records: list[CompanionRecord], **kw):
    """1. Overall score distribution."""
    scores = sorted([r.score_total for r in records])
    n = len(scores)
    if not n:
        print("  No papers.")
        return

    avg = sum(scores) / n
    median = scores[n // 2]
    p25 = scores[n // 4] if n >= 4 else scores[0]
    p75 = scores[3 * n // 4] if n >= 4 else scores[-1]
    top = scores[-1]
    bottom = scores[0]

    print(f"  Papers: {n}")
    print(f"  Score range: {bottom} – {top} (ceiling 100)")
    print(f"  Mean: {avg:.1f}  Median: {median}  P25: {p25}  P75: {p75}")
    print()

    # Histogram buckets: 0-10, 11-20, ..., 91-100
    buckets = [0] * 10
    for s in scores:
        idx = min(s // 10, 9)
        buckets[idx] += 1

    max_bar = max(buckets) if buckets else 1
    for i, count in enumerate(buckets):
        lo, hi = i * 10, (i + 1) * 10
        bar = "█" * int(count / max_bar * 30) if max_bar else ""
        print(f"  {lo:3d}–{hi:3d} │ {bar} {count}")


def mode_grade_curve(records: list[CompanionRecord], **kw):
    """2. Grade distribution."""
    grades = Counter(r.grade for r in records if r.grade)
    order = ["A", "B", "C", "D", "F"]
    total = sum(grades.values())
    for g in order:
        count = grades.get(g, 0)
        pct = count / total * 100 if total else 0
        bar = "█" * int(pct / 2)
        print(f"  {g} │ {bar} {count} ({pct:.0f}%)")
    ungraded = len([r for r in records if not r.grade])
    if ungraded:
        print(f"  ? │ {ungraded} ungraded")


def mode_domain_breakdown(records: list[CompanionRecord], **kw):
    """3. Papers per primary domain."""
    domains = Counter()
    for r in records:
        d = re.sub(r"\s*\(.*?\)\s*", "", r.domain_primary).strip() if r.domain_primary else "(none)"
        domains[d] += 1
    for domain, count in domains.most_common():
        bar = "█" * count
        print(f"  {bar} {count:3d}  {domain}")


def mode_domain_cross(records: list[CompanionRecord], **kw):
    """4. Domain co-occurrence matrix."""
    pairs = Counter()
    for r in records:
        ds = sorted(r.domain_set)
        for i in range(len(ds)):
            for j in range(i + 1, len(ds)):
                pairs[(ds[i], ds[j])] += 1
    print(f"  {'Domain A':<30s}  {'Domain B':<30s}  Count")
    print(f"  {'─' * 30}  {'─' * 30}  ─────")
    for (a, b), count in pairs.most_common(20):
        print(f"  {a:<30s}  {b:<30s}  {count}")


def mode_tag_frequency(records: list[CompanionRecord], **kw):
    """5. Most common weighted tags."""
    tag_counts = Counter()
    tag_total_weight = defaultdict(int)
    for r in records:
        for t in r.tags_weighted:
            if isinstance(t, dict) and "tag" in t:
                tag_counts[t["tag"]] += 1
                tag_total_weight[t["tag"]] += int(t.get("weight", 1))
    print(f"  {'Tag':<35s}  Papers  Total Weight")
    print(f"  {'─' * 35}  ──────  ────────────")
    for tag, count in tag_counts.most_common(30):
        tw = tag_total_weight[tag]
        print(f"  {tag:<35s}  {count:5d}   {tw:5d}")


def mode_tag_heatmap(records: list[CompanionRecord], **kw):
    """6. Tag × domain frequency table (top 10 tags × top 5 domains)."""
    tag_counts = Counter()
    domain_counts = Counter()
    cross = Counter()
    for r in records:
        d = re.sub(r"\s*\(.*?\)\s*", "", r.domain_primary).strip() if r.domain_primary else "(none)"
        domain_counts[d] += 1
        for t in r.tags_weighted:
            if isinstance(t, dict) and "tag" in t:
                tag_counts[t["tag"]] += 1
                cross[(t["tag"], d)] += 1

    top_tags = [t for t, _ in tag_counts.most_common(10)]
    top_domains = [d for d, _ in domain_counts.most_common(5)]

    # Header
    header = f"  {'Tag':<25s}"
    for d in top_domains:
        header += f"  {d[:12]:>12s}"
    print(header)
    print(f"  {'─' * 25}" + "  ────────────" * len(top_domains))

    for tag in top_tags:
        row = f"  {tag:<25s}"
        for d in top_domains:
            c = cross.get((tag, d), 0)
            row += f"  {c:12d}" if c else f"  {'·':>12s}"
        print(row)


def mode_evidence_balance(records: list[CompanionRecord], **kw):
    """7. Evidence support vs counter distribution."""
    balances = sorted([(r.evd_balance, r.clean_title, r.score_total) for r in records])
    neg = [b for b in balances if b[0] < 0]
    zero = [b for b in balances if b[0] == 0]
    pos = [b for b in balances if b[0] > 0]

    print(f"  Negative balance: {len(neg)} papers")
    print(f"  Zero balance:     {len(zero)} papers")
    print(f"  Positive balance: {len(pos)} papers")
    print()

    if neg:
        print("  WEAKEST evidence balance:")
        for bal, title, score in neg[:10]:
            print(f"    {bal:+d}  [{score}/100]  {title[:60]}")
    print()
    if pos:
        print("  STRONGEST evidence balance:")
        for bal, title, score in reversed(pos[-10:]):
            print(f"    {bal:+d}  [{score}/100]  {title[:60]}")


def mode_weakest_claims(records: list[CompanionRecord], **kw):
    """8. Papers ranked by weakest claim."""
    ranked = sorted(records, key=lambda r: r.evd_balance)
    print(f"  {'Score':>5s}  {'Bal':>4s}  {'Title':<50s}  Weakest Claim")
    print(f"  {'─' * 5}  {'─' * 4}  {'─' * 50}  {'─' * 40}")
    for r in ranked[:20]:
        weak = r.evd_weakest_claim[:60] + "..." if len(r.evd_weakest_claim) > 60 else r.evd_weakest_claim
        print(f"  {r.score_total:5d}  {r.evd_balance:+4d}  {r.clean_title[:50]:<50s}  {weak}")


def mode_strongest_claims(records: list[CompanionRecord], **kw):
    """9. Papers ranked by strongest evidence."""
    ranked = sorted(records, key=lambda r: (-r.evd_balance, -r.score_total))
    print(f"  {'Score':>5s}  {'Bal':>4s}  {'Coh':>4s}  Title")
    print(f"  {'─' * 5}  {'─' * 4}  {'─' * 4}  {'─' * 50}")
    for r in ranked[:20]:
        print(f"  {r.score_total:5d}  {r.evd_balance:+4d}  {r.coherence:4.1f}  {r.clean_title[:60]}")


def mode_section_scores(records: list[CompanionRecord], **kw):
    """10. Average score per section (S01–S10) across all papers."""
    section_totals = defaultdict(lambda: {"pos": 0, "neg": 0, "net": 0, "count": 0})

    for r in records:
        ss = extract_section_scores(r.filepath)
        for key, vals in ss.items():
            section_totals[key]["pos"] += vals["pos"]
            section_totals[key]["neg"] += vals["neg"]
            section_totals[key]["net"] += vals["net"]
            section_totals[key]["count"] += 1

    print(f"  {'Section':<35s}  {'Avg Net':>7s}  {'Avg Pos':>7s}  {'Avg Neg':>7s}  Papers")
    print(f"  {'─' * 35}  {'─' * 7}  {'─' * 7}  {'─' * 7}  ──────")
    for key in sorted(section_totals.keys()):
        s = section_totals[key]
        n = s["count"] or 1
        name = SECTION_NAMES.get(key, key)
        chain = " HON" if key in HONESTY_SECTIONS else " LB" if key in LOADBEARING_SECTIONS else ""
        print(f"  {key.upper()} {name:<30s}{chain:>3s}  {s['net']/n:7.1f}  {s['pos']/n:7.1f}  {s['neg']/n:7.1f}  {s['count']:5d}")


def mode_build_next_priority(records: list[CompanionRecord], **kw):
    """11. build_next items ranked by frequency/urgency."""
    # Cluster build_next texts by keyword overlap
    builds = [(r.build_next, r.score_total, r.clean_title) for r in records if r.build_next]
    if not builds:
        print("  No build_next items found.")
        return

    # Extract key phrases (simple: first 80 chars as the "theme")
    print(f"  {len(builds)} papers have build_next directives:\n")

    # Sort by score ascending — lowest-scoring papers need the most work
    builds.sort(key=lambda x: x[1])
    for build, score, title in builds[:20]:
        short = build[:100] + "..." if len(build) > 100 else build
        print(f"  [{score:3d}/100] {title[:40]}")
        print(f"           → {short}")
        print()


def mode_argument_density(records: list[CompanionRecord], **kw):
    """12. Papers ranked by argument step count."""
    ranked = sorted(records, key=lambda r: -len(r.primary_argument))
    print(f"  {'Steps':>5s}  {'Premises':>8s}  {'Score':>5s}  Title")
    print(f"  {'─' * 5}  {'─' * 8}  {'─' * 5}  {'─' * 50}")
    for r in ranked[:25]:
        print(f"  {len(r.primary_argument):5d}  {len(r.hidden_premises):8d}  {r.score_total:5d}  {r.clean_title[:55]}")


def mode_framework_key_map(records: list[CompanionRecord], **kw):
    """13. Which framework keys appear most."""
    fk_counts = Counter()
    fk_papers = defaultdict(list)
    for r in records:
        for fk in r.framework_keys:
            fk_counts[fk] += 1
            fk_papers[fk].append(r.clean_title[:40])

    for fk, count in fk_counts.most_common(20):
        print(f"  {fk:<10s}  {count:3d} papers")
        for title in fk_papers[fk][:5]:
            print(f"    · {title}")
        if count > 5:
            print(f"    · ... and {count - 5} more")
        print()


def mode_coherence_ranking(records: list[CompanionRecord], **kw):
    """14. Papers ranked by coherence score."""
    ranked = sorted(records, key=lambda r: -r.coherence)
    print(f"  {'Coh':>5s}  {'Score':>5s}  {'Grade':>5s}  Title")
    print(f"  {'─' * 5}  {'─' * 5}  {'─' * 5}  {'─' * 50}")
    for r in ranked[:25]:
        print(f"  {r.coherence:5.1f}  {r.score_total:5d}  {r.grade:>5s}  {r.clean_title[:55]}")


def mode_content_type_dist(records: list[CompanionRecord], **kw):
    """15. Distribution of content types."""
    types = Counter(r.content_type for r in records if r.content_type)
    for ct, count in types.most_common():
        bar = "█" * count
        print(f"  {bar} {count:3d}  {ct}")


def mode_stale_candidates(records: list[CompanionRecord], **kw):
    """16. Low-score papers that might need retirement or rewrite."""
    stale = sorted([r for r in records if r.score_total <= 25], key=lambda r: r.score_total)
    if not stale:
        print("  No papers scoring ≤25. Nice.")
        return
    print(f"  {len(stale)} papers scoring ≤25/100 (rewrite or retire candidates):\n")
    for r in stale:
        print(f"  [{r.score_total:3d}] {r.grade or '?'}  {r.clean_title[:55]}")
        if r.build_next:
            short = r.build_next[:80] + "..." if len(r.build_next) > 80 else r.build_next
            print(f"        → {short}")


def mode_bridge_audit(records: list[CompanionRecord], **kw):
    """17. Papers where bridge integrity (S08) scored 0 or below."""
    flagged = []
    for r in records:
        ss = extract_section_scores(r.filepath)
        s08 = ss.get("s08", {})
        if s08 and s08.get("net", 99) <= 0:
            flagged.append((s08["net"], r))

    flagged.sort(key=lambda x: x[0])
    if not flagged:
        print("  No papers with S08 (Bridge Integrity) ≤ 0.")
        return
    print(f"  {len(flagged)} papers with broken or absent bridge:\n")
    for net, r in flagged:
        print(f"  S08 net={net:+d}  [{r.score_total}/100]  {r.clean_title[:55]}")


def mode_formal_gaps(records: list[CompanionRecord], **kw):
    """18. Papers where formal/math (S07) scored lowest."""
    scored = []
    for r in records:
        ss = extract_section_scores(r.filepath)
        s07 = ss.get("s07", {})
        if s07:
            scored.append((s07["net"], r))

    scored.sort(key=lambda x: x[0])
    print(f"  {'S07 Net':>7s}  {'Score':>5s}  Title")
    print(f"  {'─' * 7}  {'─' * 5}  {'─' * 50}")
    for net, r in scored[:20]:
        print(f"  {net:+7d}  {r.score_total:5d}  {r.clean_title[:55]}")


def mode_honesty_chain(records: list[CompanionRecord], **kw):
    """19. Papers where the honesty chain sections average below 3."""
    flagged = []
    for r in records:
        ss = extract_section_scores(r.filepath)
        hon_nets = [ss[k]["net"] for k in HONESTY_SECTIONS if k in ss]
        if hon_nets:
            avg = sum(hon_nets) / len(hon_nets)
            if avg < 3.0:
                flagged.append((avg, r, hon_nets))

    flagged.sort(key=lambda x: x[0])
    if not flagged:
        print("  No papers with honesty-chain average below 3. Solid.")
        return
    print(f"  {len(flagged)} papers with weak honesty chain (S05+S06+S08+S09 avg < 3):\n")
    for avg, r, nets in flagged[:15]:
        print(f"  avg={avg:.1f}  sections={nets}  [{r.score_total}/100]  {r.clean_title[:50]}")


def mode_progress_dashboard(records: list[CompanionRecord], **kw):
    """20. Summary dashboard."""
    n = len(records)
    if not n:
        print("  No papers.")
        return

    scores = [r.score_total for r in records]
    avg_score = sum(scores) / n
    grades = Counter(r.grade for r in records if r.grade)
    domains = Counter(re.sub(r"\s*\(.*?\)\s*", "", r.domain_primary).strip() for r in records if r.domain_primary)
    has_arguments = sum(1 for r in records if r.primary_argument)
    has_build_next = sum(1 for r in records if r.build_next)
    avg_coherence = sum(r.coherence for r in records) / n
    avg_evd_balance = sum(r.evd_balance for r in records) / n

    print(f"  ┌─────────────────────────────────────────────────┐")
    print(f"  │  COMPANION PAPER CORPUS — PROGRESS DASHBOARD    │")
    print(f"  ├─────────────────────────────────────────────────┤")
    print(f"  │  Total papers:        {n:>6d}                    │")
    print(f"  │  Average score:       {avg_score:>6.1f} / 100              │")
    print(f"  │  Average coherence:   {avg_coherence:>6.1f}                    │")
    print(f"  │  Avg evidence balance:{avg_evd_balance:>+6.1f}                    │")
    print(f"  │  With arguments:      {has_arguments:>6d} ({has_arguments/n*100:.0f}%)              │")
    print(f"  │  With build_next:     {has_build_next:>6d} ({has_build_next/n*100:.0f}%)              │")
    print(f"  ├─────────────────────────────────────────────────┤")
    print(f"  │  Grade distribution:                            │")
    for g in ["A", "B", "C", "D", "F"]:
        c = grades.get(g, 0)
        bar = "█" * min(c, 20)
        print(f"  │    {g}: {bar:<20s} {c:>4d}               │")
    print(f"  ├─────────────────────────────────────────────────┤")
    print(f"  │  Top domains:                                   │")
    for d, c in domains.most_common(5):
        print(f"  │    {c:4d}  {d[:40]:<40s} │")
    print(f"  └─────────────────────────────────────────────────┘")


# ──────────────────────────────────────────────────────────────────
# REGISTRY
# ──────────────────────────────────────────────────────────────────

MODES = {
    "scoreboard":          ("1.  Score distribution (histogram + percentiles)", mode_scoreboard),
    "grade_curve":         ("2.  Grade distribution (A/B/C/D/F)", mode_grade_curve),
    "domain_breakdown":    ("3.  Papers per primary domain", mode_domain_breakdown),
    "domain_cross":        ("4.  Domain co-occurrence matrix", mode_domain_cross),
    "tag_frequency":       ("5.  Most common weighted tags", mode_tag_frequency),
    "tag_heatmap":         ("6.  Tag × domain frequency table", mode_tag_heatmap),
    "evidence_balance":    ("7.  Evidence support vs counter", mode_evidence_balance),
    "weakest_claims":      ("8.  Papers ranked by weakest claim", mode_weakest_claims),
    "strongest_claims":    ("9.  Papers ranked by strongest evidence", mode_strongest_claims),
    "section_scores":      ("10. Average S01–S10 scores across corpus", mode_section_scores),
    "build_next_priority": ("11. build_next directives by urgency", mode_build_next_priority),
    "argument_density":    ("12. Papers ranked by argument step count", mode_argument_density),
    "framework_key_map":   ("13. Framework key frequency map", mode_framework_key_map),
    "coherence_ranking":   ("14. Papers ranked by coherence", mode_coherence_ranking),
    "content_type_dist":   ("15. Content type distribution", mode_content_type_dist),
    "stale_candidates":    ("16. Low-score rewrite/retire candidates", mode_stale_candidates),
    "bridge_audit":        ("17. Papers with broken bridge (S08 ≤ 0)", mode_bridge_audit),
    "formal_gaps":         ("18. Papers with weakest formal/math (S07)", mode_formal_gaps),
    "honesty_chain":       ("19. Weak honesty chain (S05+S06+S08+S09)", mode_honesty_chain),
    "progress_dashboard":  ("20. Summary progress dashboard", mode_progress_dashboard),
}


# ──────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────

def main():
    global OUTBOX_ROOT

    json_mode = "--json" in sys.argv
    list_mode = "--list" in sys.argv
    selected_modes = []

    args = []
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--mode" and i + 1 < len(sys.argv):
            selected_modes.append(sys.argv[i + 1])
            i += 2
        elif sys.argv[i].startswith("--"):
            i += 1
        else:
            args.append(sys.argv[i])
            i += 1

    if args:
        OUTBOX_ROOT = args[0]

    if list_mode:
        print("Available analysis modes:\n")
        for name, (desc, _) in MODES.items():
            print(f"  {name:<25s}  {desc}")
        print(f"\nUsage: python companion_stats.py --mode <name> [--mode <name2> ...]")
        return

    print(f"Scanning: {OUTBOX_ROOT}")
    records = scan_outbox(OUTBOX_ROOT)
    print(f"Parsed {len(records)} companion papers.\n")

    if not records:
        print("No companion papers found. Check path.")
        sys.exit(1)

    modes_to_run = selected_modes if selected_modes else list(MODES.keys())

    if json_mode:
        # Capture output as structured data (simplified — prints still go to stdout)
        pass

    for mode_name in modes_to_run:
        if mode_name not in MODES:
            print(f"  Unknown mode: {mode_name}")
            print(f"  Run with --list to see available modes.")
            continue

        desc, func = MODES[mode_name]
        print(f"{'═' * 72}")
        print(f"  {desc}")
        print(f"{'═' * 72}")
        func(records)
        print()


if __name__ == "__main__":
    main()
