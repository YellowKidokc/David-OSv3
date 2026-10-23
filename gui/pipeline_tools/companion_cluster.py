#!/usr/bin/env python3
"""Companion Paper Clustering — POF 2828 Pipeline Tool.

Scans a folder tree of companion .md files (CKG_RECORD format),
extracts YAML frontmatter + argument sections, and clusters papers
by overlapping claims, tags, domains, and argument structure.

Presents ranked clusters so David can pick which to merge.

USAGE:
    python companion_cluster.py                  # uses default OUTBOX_ROOT
    python companion_cluster.py /path/to/outbox  # override root
    python companion_cluster.py --json           # machine-readable output
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────────────
# CONFIG — change this one line when you copy the folder elsewhere
# ──────────────────────────────────────────────────────────────────
OUTBOX_ROOT = r"\\192.168.2.50\h_hp\Desktop\_____pipeline-workflows-main\EVIDENCE_CHAIN_INTAKE\OUTBOX\01_CLASSIFIED_LIBRARY"

# Minimum similarity score (0–1) for two papers to be considered related
CLUSTER_THRESHOLD = 0.25

# ──────────────────────────────────────────────────────────────────
# DATA MODEL
# ──────────────────────────────────────────────────────────────────

@dataclass
class CompanionRecord:
    """Parsed companion paper."""
    filepath: str
    filename: str
    paper_id: str = ""
    clean_title: str = ""
    source_file: str = ""

    # Domains
    domain_primary: str = ""
    domain_primary_pct: int = 0
    domain_secondary: str = ""
    domain_secondary_pct: int = 0
    domain_tertiary: str = ""
    domain_tertiary_pct: int = 0

    # Tags
    tags_weighted: list[dict] = field(default_factory=list)
    framework_keys: list[str] = field(default_factory=list)

    # Claims & links
    claim_ids: list[str] = field(default_factory=list)
    downstream_implications: list[str] = field(default_factory=list)
    topic_keys: list[str] = field(default_factory=list)

    # Scores
    score_total: int = 0
    score_ceiling: int = 100
    grade: str = ""
    score_class: str = ""
    coherence: float = 0.0

    # Evidence
    evd_support: int = 0
    evd_counter: int = 0
    evd_balance: int = 0
    evd_weakest_claim: str = ""

    # Key text fields (for similarity)
    governing_question: str = ""
    one_sentence_finding: str = ""
    build_next: str = ""
    content_type: str = ""
    canonical_rec: str = ""

    # Argument sections (extracted from markdown body)
    primary_argument: list[str] = field(default_factory=list)
    hidden_premises: list[str] = field(default_factory=list)
    argument_strengthening: list[str] = field(default_factory=list)
    classical_anchors: str = ""
    vulnerability_diagnosis: str = ""

    @property
    def tag_set(self) -> set[str]:
        return {t["tag"] for t in self.tags_weighted if isinstance(t, dict) and "tag" in t}

    @property
    def domain_set(self) -> set[str]:
        domains = set()
        for d in [self.domain_primary, self.domain_secondary, self.domain_tertiary]:
            if d:
                # Normalize: strip parentheticals, split on " / ", take each part
                clean = re.sub(r"\s*\(.*?\)\s*", "", d).strip()
                for part in clean.split("/"):
                    part = part.strip().lower()
                    if part:
                        domains.add(part)
        return domains

    @property
    def all_text(self) -> str:
        """All semantic text concatenated for similarity comparison."""
        parts = [
            self.governing_question,
            self.one_sentence_finding,
            self.build_next,
            self.evd_weakest_claim,
            self.classical_anchors,
            self.vulnerability_diagnosis,
        ]
        parts.extend(self.primary_argument)
        parts.extend(self.hidden_premises)
        return " ".join(p for p in parts if p)


# ──────────────────────────────────────────────────────────────────
# PARSER
# ──────────────────────────────────────────────────────────────────

def extract_yaml_block(text: str) -> str:
    """Pull the YAML from inside ```yaml ... ``` fences."""
    m = re.search(r"```yaml\s*\n---\s*\n(.*?)\n---\s*\n```", text, re.DOTALL)
    if m:
        return m.group(1)
    # Fallback: try bare --- fences
    m = re.search(r"^---\s*\n(.*?)\n---\s*$", text, re.DOTALL | re.MULTILINE)
    if m:
        return m.group(1)
    return ""


def parse_yaml_lightweight(yaml_text: str) -> dict[str, Any]:
    """Minimal YAML parser — enough for the companion frontmatter.

    Handles: scalars, simple lists, list-of-dicts (tags_weighted),
    inline lists (framework_keys: ["A", "B"]).
    Does NOT handle arbitrary nested YAML — but this format is fixed.
    """
    result: dict[str, Any] = {}
    current_key = ""
    current_list: list | None = None

    for line in yaml_text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # List-of-dict item:  - tag: "foo"
        if current_list is not None and stripped.startswith("- "):
            # Could be a dict item or a plain list item
            inner = stripped[2:].strip()
            if ":" in inner:
                # Dict item — accumulate
                k, v = inner.split(":", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                # Check if last item in list is a dict being built
                if current_list and isinstance(current_list[-1], dict) and k not in current_list[-1]:
                    current_list[-1][k] = _auto_type(v)
                else:
                    current_list.append({k: _auto_type(v)})
            else:
                current_list.append(_auto_type(inner.strip('"').strip("'")))
            continue

        # Continuation of dict item (indented under a list item)
        if current_list is not None and line.startswith("    ") and ":" in stripped:
            k, v = stripped.split(":", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if current_list and isinstance(current_list[-1], dict):
                current_list[-1][k] = _auto_type(v)
            continue

        # End of list context if we hit a new top-level key
        if current_list is not None and not line.startswith(" ") and ":" in stripped:
            result[current_key] = current_list
            current_list = None

        # Top-level key: value
        if ":" in stripped and not stripped.startswith("-"):
            k, v = stripped.split(":", 1)
            k = k.strip()
            v = v.strip()

            if not v:
                # Start of a list or block
                current_key = k
                current_list = []
                continue

            # Inline list: ["a", "b"]
            if v.startswith("["):
                items = re.findall(r'"([^"]*)"', v)
                if not items:
                    items = re.findall(r"'([^']*)'", v)
                if not items and v != "[]":
                    # Try bare items
                    inner = v.strip("[]")
                    items = [x.strip() for x in inner.split(",") if x.strip()]
                result[k] = items
                current_key = ""
                current_list = None
                continue

            # Inline dict: {key: val, ...}
            if v.startswith("{"):
                try:
                    # Quick JSON-ish parse
                    result[k] = json.loads(v.replace("null", "null"))
                except Exception:
                    result[k] = v
                current_key = ""
                current_list = None
                continue

            # Scalar
            result[k] = _auto_type(v.strip('"').strip("'"))
            current_key = ""
            current_list = None

    # Flush any trailing list
    if current_list is not None and current_key:
        result[current_key] = current_list

    return result


def _auto_type(v: str):
    """Convert string to int/float/bool/None where obvious."""
    if v in ("null", "~", ""):
        return None
    if v in ("true", "True"):
        return True
    if v in ("false", "False"):
        return False
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


def extract_argument_sections(text: str) -> dict[str, Any]:
    """Pull the key argument sections from the markdown body."""
    sections: dict[str, Any] = {}

    # Primary argument (numbered list)
    m = re.search(r"### Primary argument\s*\n(.*?)(?=\n###|\n---|\n## |\Z)", text, re.DOTALL)
    if m:
        lines = []
        for line in m.group(1).strip().split("\n"):
            line = line.strip()
            if re.match(r"\d+\.", line):
                lines.append(line)
        sections["primary_argument"] = lines

    # Hidden premises table
    m = re.search(r"### Hidden premises\s*\n(.*?)(?=\n###|\n---|\n## |\Z)", text, re.DOTALL)
    if m:
        premises = []
        for line in m.group(1).strip().split("\n"):
            if line.strip().startswith("|") and "Hidden premise" not in line and "---" not in line and line.count("|") >= 4:
                cells = [c.strip() for c in line.split("|")]
                cells = [c for c in cells if c]
                if len(cells) >= 2:
                    premises.append(cells[1])  # The premise text
        sections["hidden_premises"] = premises

    # Argument strengthening table
    m = re.search(r"### Argument strengthening\s*\n(.*?)(?=\n###|\n---|\n## |\Z)", text, re.DOTALL)
    if m:
        strengths = []
        for line in m.group(1).strip().split("\n"):
            if line.strip().startswith("|") and "Weak link" not in line and "---" not in line and line.count("|") >= 4:
                cells = [c.strip() for c in line.split("|")]
                cells = [c for c in cells if c]
                if len(cells) >= 2:
                    strengths.append(f"{cells[0]}: {cells[1]}")
        sections["argument_strengthening"] = strengths

    # Classical Prior Art
    m = re.search(r"### 🏛️ Classical Prior Art Anchors\s*\n(.*?)(?=\n###|\n---|\n## |\Z)", text, re.DOTALL)
    if m:
        sections["classical_anchors"] = m.group(1).strip()[:500]

    # Vulnerability diagnosis
    m = re.search(r"\*\*Vulnerability Diagnosis:\*\*\s*\n(.*?)(?=\n\*\*The 4 Dimensions|\n###|\n---|\n## |\Z)", text, re.DOTALL)
    if m:
        sections["vulnerability_diagnosis"] = m.group(1).strip()[:500]

    return sections


def parse_companion(filepath: str) -> CompanionRecord | None:
    """Parse a single companion .md file into a CompanionRecord."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception:
        return None

    yaml_text = extract_yaml_block(text)
    if not yaml_text:
        return None

    meta = parse_yaml_lightweight(yaml_text)

    # Must have at minimum a paper_id or clean_title
    if not meta.get("paper_id") and not meta.get("clean_title"):
        return None

    rec = CompanionRecord(
        filepath=filepath,
        filename=os.path.basename(filepath),
        paper_id=str(meta.get("paper_id", "")),
        clean_title=str(meta.get("clean_title", meta.get("original_title", ""))),
        source_file=str(meta.get("source_file", "")),
        domain_primary=str(meta.get("domain_primary", "")),
        domain_primary_pct=int(meta.get("domain_primary_pct", 0) or 0),
        domain_secondary=str(meta.get("domain_secondary", "")),
        domain_secondary_pct=int(meta.get("domain_secondary_pct", 0) or 0),
        domain_tertiary=str(meta.get("domain_tertiary", "")),
        domain_tertiary_pct=int(meta.get("domain_tertiary_pct", 0) or 0),
        tags_weighted=meta.get("tags_weighted", []) if isinstance(meta.get("tags_weighted"), list) else [],
        framework_keys=meta.get("framework_keys", []) if isinstance(meta.get("framework_keys"), list) else [],
        claim_ids=meta.get("claim_ids", []) if isinstance(meta.get("claim_ids"), list) else [],
        downstream_implications=meta.get("downstream_implications", []) if isinstance(meta.get("downstream_implications"), list) else [],
        topic_keys=meta.get("topic_keys", []) if isinstance(meta.get("topic_keys"), list) else [],
        score_total=int(meta.get("score_total", 0) or 0),
        score_ceiling=int(meta.get("score_ceiling", 100) or 100),
        grade=str(meta.get("grade", "")),
        score_class=str(meta.get("score_class", "")),
        coherence=float(meta.get("coherence", 0) or 0),
        evd_support=int(meta.get("evd_support", 0) or 0),
        evd_counter=int(meta.get("evd_counter", 0) or 0),
        evd_balance=int(meta.get("evd_balance", 0) or 0),
        evd_weakest_claim=str(meta.get("evd_weakest_claim", "")),
        governing_question=str(meta.get("governing_question", "")),
        one_sentence_finding=str(meta.get("one_sentence_finding", "")),
        build_next=str(meta.get("build_next", "")),
        content_type=str(meta.get("content_type", "")),
        canonical_rec=str(meta.get("canonical_rec", "")),
    )

    # Extract argument sections from body
    arg_sections = extract_argument_sections(text)
    rec.primary_argument = arg_sections.get("primary_argument", [])
    rec.hidden_premises = arg_sections.get("hidden_premises", [])
    rec.argument_strengthening = arg_sections.get("argument_strengthening", [])
    rec.classical_anchors = arg_sections.get("classical_anchors", "")
    rec.vulnerability_diagnosis = arg_sections.get("vulnerability_diagnosis", "")

    return rec


# ──────────────────────────────────────────────────────────────────
# SIMILARITY ENGINE
# ──────────────────────────────────────────────────────────────────

def tag_overlap(a: CompanionRecord, b: CompanionRecord) -> float:
    """Jaccard similarity of weighted tag sets."""
    sa, sb = a.tag_set, b.tag_set
    if not sa and not sb:
        return 0.0
    union = sa | sb
    inter = sa & sb
    return len(inter) / len(union) if union else 0.0


def domain_overlap(a: CompanionRecord, b: CompanionRecord) -> float:
    """Jaccard similarity of domain sets."""
    da, db = a.domain_set, b.domain_set
    if not da and not db:
        return 0.0
    union = da | db
    inter = da & db
    return len(inter) / len(union) if union else 0.0


def framework_key_overlap(a: CompanionRecord, b: CompanionRecord) -> float:
    """Jaccard similarity of framework keys."""
    fa = set(a.framework_keys)
    fb = set(b.framework_keys)
    if not fa and not fb:
        return 0.0
    union = fa | fb
    inter = fa & fb
    return len(inter) / len(union) if union else 0.0


def claim_link_score(a: CompanionRecord, b: CompanionRecord) -> float:
    """Do these papers explicitly reference each other via claim_ids or downstream?"""
    a_ids = set(a.claim_ids)
    b_ids = set(b.claim_ids)
    a_down = set(a.downstream_implications)
    b_down = set(b.downstream_implications)

    # Direct cross-reference
    if a_ids & b_down or b_ids & a_down:
        return 1.0

    # Shared claim prefixes (e.g. ME10L-C001 and ME10L-C003 share "ME10L")
    a_prefixes = {c.rsplit("-", 1)[0] for c in a_ids if "-" in c}
    b_prefixes = {c.rsplit("-", 1)[0] for c in b_ids if "-" in c}
    if a_prefixes & b_prefixes:
        return 0.5

    return 0.0


def text_similarity(a: CompanionRecord, b: CompanionRecord) -> float:
    """SequenceMatcher ratio on concatenated semantic text."""
    ta, tb = a.all_text, b.all_text
    if not ta or not tb:
        return 0.0
    # Truncate for performance
    ta, tb = ta[:2000], tb[:2000]
    return SequenceMatcher(None, ta.lower(), tb.lower()).ratio()


def build_next_similarity(a: CompanionRecord, b: CompanionRecord) -> float:
    """Papers that need the same thing built are merge candidates."""
    if not a.build_next or not b.build_next:
        return 0.0
    return SequenceMatcher(None, a.build_next.lower(), b.build_next.lower()).ratio()


def composite_similarity(a: CompanionRecord, b: CompanionRecord) -> float:
    """Weighted composite similarity score."""
    weights = {
        "tag":       0.20,
        "domain":    0.15,
        "fk":        0.10,
        "claim":     0.20,
        "text":      0.25,
        "build":     0.10,
    }
    scores = {
        "tag":    tag_overlap(a, b),
        "domain": domain_overlap(a, b),
        "fk":     framework_key_overlap(a, b),
        "claim":  claim_link_score(a, b),
        "text":   text_similarity(a, b),
        "build":  build_next_similarity(a, b),
    }
    total = sum(scores[k] * weights[k] for k in weights)
    return total


# ──────────────────────────────────────────────────────────────────
# CLUSTERING
# ──────────────────────────────────────────────────────────────────

@dataclass
class Cluster:
    """A group of related companion papers."""
    papers: list[CompanionRecord] = field(default_factory=list)
    avg_similarity: float = 0.0
    merge_rationale: str = ""
    shared_tags: set = field(default_factory=set)
    shared_domains: set = field(default_factory=set)
    shared_framework_keys: set = field(default_factory=set)
    combined_score: int = 0
    best_grade: str = ""
    common_build_next: str = ""


def cluster_papers(records: list[CompanionRecord], threshold: float = CLUSTER_THRESHOLD) -> list[Cluster]:
    """Single-linkage clustering with similarity threshold."""
    n = len(records)
    if n == 0:
        return []

    # Build similarity matrix
    sim = {}
    for i in range(n):
        for j in range(i + 1, n):
            s = composite_similarity(records[i], records[j])
            sim[(i, j)] = s

    # Union-Find for single-linkage
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for (i, j), s in sim.items():
        if s >= threshold:
            union(i, j)

    # Group by root
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)

    clusters = []
    for indices in groups.values():
        if len(indices) < 2:
            continue  # Skip singletons — no merge opportunity

        papers = [records[i] for i in indices]

        # Compute average pairwise similarity
        pair_sims = []
        for a_idx in range(len(indices)):
            for b_idx in range(a_idx + 1, len(indices)):
                i, j = indices[a_idx], indices[b_idx]
                key = (min(i, j), max(i, j))
                pair_sims.append(sim.get(key, 0.0))
        avg_sim = sum(pair_sims) / len(pair_sims) if pair_sims else 0.0

        # Shared attributes
        shared_tags = set.intersection(*[p.tag_set for p in papers]) if papers else set()
        shared_domains = set.intersection(*[p.domain_set for p in papers]) if papers else set()
        shared_fk = set.intersection(*[set(p.framework_keys) for p in papers]) if papers else set()

        # Combined score = sum of individual scores
        combined = sum(p.score_total for p in papers)

        # Best grade
        grade_order = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
        best_g = max(papers, key=lambda p: grade_order.get(p.grade, 0)).grade

        # Common build_next (find the most common theme)
        build_texts = [p.build_next for p in papers if p.build_next]
        common_build = build_texts[0] if build_texts else ""

        # Merge rationale
        rationale_parts = []
        if shared_tags:
            rationale_parts.append(f"shared tags: {', '.join(sorted(shared_tags))}")
        if shared_domains:
            rationale_parts.append(f"shared domains: {', '.join(sorted(shared_domains))}")
        if shared_fk:
            rationale_parts.append(f"shared framework keys: {', '.join(sorted(shared_fk))}")
        if avg_sim > 0.4:
            rationale_parts.append(f"high argument similarity ({avg_sim:.0%})")
        rationale = "; ".join(rationale_parts) if rationale_parts else "thematic overlap"

        clusters.append(Cluster(
            papers=papers,
            avg_similarity=avg_sim,
            merge_rationale=rationale,
            shared_tags=shared_tags,
            shared_domains=shared_domains,
            shared_framework_keys=shared_fk,
            combined_score=combined,
            best_grade=best_g,
            common_build_next=common_build,
        ))

    # Sort clusters: highest similarity first, then by paper count
    clusters.sort(key=lambda c: (-c.avg_similarity, -len(c.papers)))
    return clusters


# ──────────────────────────────────────────────────────────────────
# SCANNER
# ──────────────────────────────────────────────────────────────────

def scan_outbox(root: str) -> list[CompanionRecord]:
    """Walk the OUTBOX tree and parse all companion .md files."""
    records = []
    root_path = Path(root)

    if not root_path.exists():
        print(f"ERROR: OUTBOX_ROOT does not exist: {root}")
        print(f"  Update OUTBOX_ROOT at the top of this script.")
        sys.exit(1)

    for md_file in root_path.rglob("*.md"):
        rec = parse_companion(str(md_file))
        if rec:
            records.append(rec)

    return records


# ──────────────────────────────────────────────────────────────────
# DISPLAY
# ──────────────────────────────────────────────────────────────────

def display_clusters(clusters: list[Cluster], all_records: list[CompanionRecord]):
    """Pretty-print the cluster results."""
    total = len(all_records)
    clustered = sum(len(c.papers) for c in clusters)
    singletons = total - clustered

    print("=" * 72)
    print(f"  COMPANION PAPER CLUSTERING — POF 2828")
    print(f"  Scanned: {total} papers | Clustered: {clustered} | Singletons: {singletons}")
    print("=" * 72)

    if not clusters:
        print("\n  No clusters found above threshold.")
        print(f"  (threshold = {CLUSTER_THRESHOLD:.0%} — lower it in config to find weaker groupings)")
        return

    for i, cluster in enumerate(clusters, 1):
        print(f"\n{'─' * 72}")
        print(f"  CLUSTER {i}  │  {len(cluster.papers)} papers  │  similarity: {cluster.avg_similarity:.0%}  │  combined score: {cluster.combined_score}/{cluster.combined_score // len(cluster.papers) * len(cluster.papers)}")
        print(f"  Rationale: {cluster.merge_rationale}")
        if cluster.common_build_next:
            short_build = cluster.common_build_next[:120] + "..." if len(cluster.common_build_next) > 120 else cluster.common_build_next
            print(f"  Build next: {short_build}")
        print()

        for j, p in enumerate(cluster.papers, 1):
            rel_path = os.path.relpath(p.filepath, OUTBOX_ROOT) if OUTBOX_ROOT in p.filepath else p.filename
            print(f"    {j}. [{p.grade or '?'}] {p.clean_title}")
            print(f"       Score: {p.score_total}/{p.score_ceiling} | Coherence: {p.coherence} | Evidence balance: {p.evd_balance:+d}")
            print(f"       Domain: {p.domain_primary}")
            if p.tag_set:
                print(f"       Tags: {', '.join(sorted(p.tag_set)[:6])}")
            if p.primary_argument:
                print(f"       Argument steps: {len(p.primary_argument)}")
            if p.evd_weakest_claim:
                short_weak = p.evd_weakest_claim[:100] + "..." if len(p.evd_weakest_claim) > 100 else p.evd_weakest_claim
                print(f"       Weakest: {short_weak}")
            print(f"       File: {rel_path}")
            print()

    # Summary
    print(f"{'─' * 72}")
    print(f"  MERGE RECOMMENDATIONS (highest similarity first):")
    print()
    for i, cluster in enumerate(clusters[:10], 1):
        titles = " + ".join(p.clean_title[:40] for p in cluster.papers[:3])
        if len(cluster.papers) > 3:
            titles += f" + {len(cluster.papers) - 3} more"
        print(f"    {i}. ({cluster.avg_similarity:.0%}) {titles}")
    print()


def output_json(clusters: list[Cluster], all_records: list[CompanionRecord]):
    """Machine-readable JSON output."""
    data = {
        "total_papers": len(all_records),
        "cluster_count": len(clusters),
        "threshold": CLUSTER_THRESHOLD,
        "clusters": [],
    }
    for cluster in clusters:
        data["clusters"].append({
            "paper_count": len(cluster.papers),
            "avg_similarity": round(cluster.avg_similarity, 4),
            "merge_rationale": cluster.merge_rationale,
            "shared_tags": sorted(cluster.shared_tags),
            "shared_domains": sorted(cluster.shared_domains),
            "shared_framework_keys": sorted(cluster.shared_framework_keys),
            "combined_score": cluster.combined_score,
            "common_build_next": cluster.common_build_next,
            "papers": [
                {
                    "paper_id": p.paper_id,
                    "clean_title": p.clean_title,
                    "filename": p.filename,
                    "filepath": p.filepath,
                    "score": p.score_total,
                    "grade": p.grade,
                    "domain_primary": p.domain_primary,
                    "tags": sorted(p.tag_set),
                    "framework_keys": p.framework_keys,
                    "governing_question": p.governing_question,
                    "evd_weakest_claim": p.evd_weakest_claim,
                    "build_next": p.build_next,
                    "primary_argument_count": len(p.primary_argument),
                }
                for p in cluster.papers
            ],
        })
    print(json.dumps(data, indent=2, ensure_ascii=False))


# ──────────────────────────────────────────────────────────────────
# FILE OUTPUT — writes cluster reports to _output/ folder
# ──────────────────────────────────────────────────────────────────

def write_cluster_outputs(clusters: list[Cluster], all_records: list[CompanionRecord], output_dir: str):
    """Write cluster reports as markdown files into output_dir."""
    os.makedirs(output_dir, exist_ok=True)

    # 1. Write the index file
    index_path = os.path.join(output_dir, "00_CLUSTER_INDEX.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(f"# Companion Paper Cluster Index\n")
        f.write(f"**POF 2828 | Generated by companion_cluster.py**\n\n")
        f.write(f"Scanned: {len(all_records)} papers | Found: {len(clusters)} clusters\n")
        f.write(f"Threshold: {CLUSTER_THRESHOLD:.0%}\n\n")
        f.write(f"---\n\n")

        if not clusters:
            f.write("No clusters found above threshold.\n")
        else:
            f.write("| # | Similarity | Papers | Shared Tags | Rationale | File |\n")
            f.write("|---|-----------|--------|-------------|-----------|------|\n")
            for i, c in enumerate(clusters, 1):
                tags = ", ".join(sorted(c.shared_tags)[:3]) if c.shared_tags else "—"
                fname = f"CLUSTER_{i:02d}.md"
                titles = " + ".join(p.clean_title[:30] for p in c.papers[:2])
                if len(c.papers) > 2:
                    titles += f" +{len(c.papers)-2}"
                f.write(f"| {i} | {c.avg_similarity:.0%} | {len(c.papers)} | {tags} | {titles} | [{fname}]({fname}) |\n")

        # Singletons section
        clustered_files = {p.filepath for c in clusters for p in c.papers}
        singletons = [r for r in all_records if r.filepath not in clustered_files]
        if singletons:
            f.write(f"\n---\n\n## Singletons ({len(singletons)} papers — no merge partner found)\n\n")
            for r in sorted(singletons, key=lambda x: x.score_total):
                f.write(f"- [{r.grade or '?'}] **{r.clean_title}** — score {r.score_total}/100\n")

    print(f"  Wrote: {index_path}")

    # 2. Write individual cluster reports
    for i, cluster in enumerate(clusters, 1):
        cluster_path = os.path.join(output_dir, f"CLUSTER_{i:02d}.md")
        with open(cluster_path, "w", encoding="utf-8") as f:
            f.write(f"# Cluster {i} — Merge Candidate Report\n")
            f.write(f"**Similarity: {cluster.avg_similarity:.0%} | Papers: {len(cluster.papers)} | Combined score: {cluster.combined_score}**\n\n")
            f.write(f"## Merge Rationale\n\n")
            f.write(f"{cluster.merge_rationale}\n\n")

            if cluster.shared_tags:
                f.write(f"**Shared tags:** {', '.join(sorted(cluster.shared_tags))}\n\n")
            if cluster.shared_domains:
                f.write(f"**Shared domains:** {', '.join(sorted(cluster.shared_domains))}\n\n")
            if cluster.shared_framework_keys:
                f.write(f"**Shared framework keys:** {', '.join(sorted(cluster.shared_framework_keys))}\n\n")

            f.write(f"---\n\n")

            # Paper summaries
            f.write(f"## Papers in This Cluster\n\n")
            for j, p in enumerate(cluster.papers, 1):
                f.write(f"### {j}. {p.clean_title}\n\n")
                f.write(f"| Field | Value |\n")
                f.write(f"|-------|-------|\n")
                f.write(f"| Score | {p.score_total}/{p.score_ceiling} ({p.grade}) |\n")
                f.write(f"| Coherence | {p.coherence} |\n")
                f.write(f"| Evidence balance | {p.evd_balance:+d} (support {p.evd_support}, counter {p.evd_counter}) |\n")
                f.write(f"| Domain | {p.domain_primary} |\n")
                f.write(f"| Content type | {p.content_type} |\n")
                f.write(f"| Tags | {', '.join(sorted(p.tag_set))} |\n")
                f.write(f"| Framework keys | {', '.join(p.framework_keys)} |\n")
                f.write(f"| Source file | `{p.source_file}` |\n")
                f.write(f"| Companion file | `{p.filename}` |\n")
                f.write(f"\n")

                f.write(f"**Governing question:** {p.governing_question}\n\n")
                f.write(f"**Finding:** {p.one_sentence_finding}\n\n")
                f.write(f"**Weakest claim:** {p.evd_weakest_claim}\n\n")
                f.write(f"**Build next:** {p.build_next}\n\n")

                if p.primary_argument:
                    f.write(f"**Primary argument ({len(p.primary_argument)} steps):**\n\n")
                    for step in p.primary_argument:
                        f.write(f"{step}\n\n")

                if p.hidden_premises:
                    f.write(f"**Hidden premises:**\n\n")
                    for hp in p.hidden_premises:
                        f.write(f"- {hp}\n")
                    f.write(f"\n")

                if p.argument_strengthening:
                    f.write(f"**Argument strengthening needed:**\n\n")
                    for s in p.argument_strengthening:
                        f.write(f"- {s}\n")
                    f.write(f"\n")

                f.write(f"---\n\n")

            # Combined argument analysis
            f.write(f"## Combined Argument Analysis\n\n")

            # Merge all argument steps, dedup similar ones
            all_steps = []
            for p in cluster.papers:
                for step in p.primary_argument:
                    all_steps.append((step, p.clean_title[:30]))

            if all_steps:
                f.write(f"### All Argument Steps ({len(all_steps)} total)\n\n")
                for step, source in all_steps:
                    f.write(f"- {step} *— from {source}*\n\n")

            # Combined hidden premises
            all_premises = []
            for p in cluster.papers:
                for hp in p.hidden_premises:
                    all_premises.append((hp, p.clean_title[:30]))

            if all_premises:
                f.write(f"### Combined Hidden Premises ({len(all_premises)} total)\n\n")
                for hp, source in all_premises:
                    f.write(f"- {hp} *— from {source}*\n")
                f.write(f"\n")

            # Combined weaknesses
            f.write(f"### Combined Weaknesses\n\n")
            for p in cluster.papers:
                if p.evd_weakest_claim:
                    f.write(f"- **{p.clean_title[:40]}:** {p.evd_weakest_claim}\n")
            f.write(f"\n")

            # Combined build_next
            f.write(f"### Combined Build-Next Directives\n\n")
            for p in cluster.papers:
                if p.build_next:
                    f.write(f"- **{p.clean_title[:40]}:** {p.build_next}\n")
            f.write(f"\n")

            # Merge recommendation
            f.write(f"## Merge Recommendation\n\n")
            f.write(f"These {len(cluster.papers)} papers share enough structural overlap ")
            f.write(f"({cluster.avg_similarity:.0%} similarity) to be candidates for consolidation ")
            f.write(f"into a single, stronger companion paper.\n\n")
            f.write(f"**Estimated combined argument density:** {sum(len(p.primary_argument) for p in cluster.papers)} steps\n\n")
            f.write(f"**Combined evidence balance:** {sum(p.evd_balance for p in cluster.papers):+d}\n\n")

            # Source file list for easy access
            f.write(f"## Source Files\n\n")
            for p in cluster.papers:
                f.write(f"- `{p.filepath}`\n")

        print(f"  Wrote: {cluster_path}")

    # 3. Write JSON summary
    json_path = os.path.join(output_dir, "clusters.json")
    data = {
        "total_papers": len(all_records),
        "cluster_count": len(clusters),
        "threshold": CLUSTER_THRESHOLD,
        "clusters": [
            {
                "cluster_id": i + 1,
                "paper_count": len(c.papers),
                "avg_similarity": round(c.avg_similarity, 4),
                "merge_rationale": c.merge_rationale,
                "shared_tags": sorted(c.shared_tags),
                "combined_score": c.combined_score,
                "papers": [
                    {
                        "paper_id": p.paper_id,
                        "clean_title": p.clean_title,
                        "filename": p.filename,
                        "filepath": p.filepath,
                        "score": p.score_total,
                        "grade": p.grade,
                        "governing_question": p.governing_question,
                        "build_next": p.build_next,
                        "primary_argument_count": len(p.primary_argument),
                    }
                    for p in c.papers
                ],
            }
            for i, c in enumerate(clusters)
        ],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Wrote: {json_path}")

    print(f"\n  Total output files: {1 + len(clusters) + 1}")
    print(f"  Output folder: {output_dir}")


# ──────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────

# Output folder: _output/ next to this script by default
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "_output")


def main():
    global OUTBOX_ROOT

    json_mode = "--json" in sys.argv
    no_files = "--no-files" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    # Parse --output flag
    output_dir = DEFAULT_OUTPUT_DIR
    for i, arg in enumerate(sys.argv):
        if arg == "--output" and i + 1 < len(sys.argv):
            output_dir = sys.argv[i + 1]

    if args:
        OUTBOX_ROOT = args[0]

    print(f"Scanning: {OUTBOX_ROOT}")
    records = scan_outbox(OUTBOX_ROOT)
    print(f"Parsed {len(records)} companion papers.\n")

    if not records:
        print("No companion papers found. Check OUTBOX_ROOT path.")
        sys.exit(1)

    clusters = cluster_papers(records)

    # Always display to console
    display_clusters(clusters, records)

    # Write output files unless --no-files
    if not no_files and clusters:
        print(f"\nWriting cluster reports...")
        write_cluster_outputs(clusters, records, output_dir)
    elif not clusters:
        print(f"\nNo clusters to write (all papers are singletons at {CLUSTER_THRESHOLD:.0%} threshold).")

    if json_mode:
        output_json(clusters, records)


if __name__ == "__main__":
    main()
