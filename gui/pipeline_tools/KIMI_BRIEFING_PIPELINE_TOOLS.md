# Pipeline Tools Briefing — For Kimi
**POF 2828 | September 2026**
**From: David's Claude (Cowork session)**

---

## What This Is

David has built a multi-stage research pipeline that takes source papers (theology, physics, mathematics, unification) and processes them through a series of API calls into structured companion documents. Those companions carry machine-readable YAML frontmatter, scored argument sections, evidence ratings, and cross-references. We've now built a Python toolset that works *on top of* those companion papers — clustering, statistical analysis, and (coming next) an interactive mind map.

This briefing explains what each piece does so you can work with the outputs David is sending you.

---

## The Pipeline Architecture (Big Picture)

```
SOURCE PAPERS (David's corpus, 1300+ papers)
        │
        ▼
EVIDENCE_CHAIN_INTAKE (3-4 API calls per paper)
   • Audit call — epistemic review
   • Claims/evidence call — structured extraction
   • Knowledge bank call — truth atoms
   • (Optional) Truth atom extraction
        │
        ▼
OUTBOX (7-lane flat structure)
   01_UNTOUCHED → 02_PROCESSED → 03_BY_DOMAIN → 04_BY_TYPE
   → 05_BY_READER → 06_CLAIMS → 07_TRUTH_LEDGER
        │
        ▼
COMPANION PAPERS (.md files, CKG_RECORD v2.0.1 format)
   • YAML frontmatter with scores, domains, tags, claims
   • Structured argument sections (primary argument, hidden premises, strengthening, defensibility)
   • Evidence sheet (support/counter/balance)
        │
        ▼
PIPELINE_TOOLS (what we just built — this folder)
   • companion_cluster.py — finds papers arguing the same thing
   • companion_stats.py — 20 statistical views of the corpus
   • companion_mindmap.py — interactive knowledge graph (HTML)
```

---

## The Companion Paper Format (CKG_RECORD v2.0.1)

Every processed paper produces a companion `.md` file. The format:

### YAML Frontmatter (inside ```yaml fences)
```yaml
paper_id: "unique identifier"
domain_primary: "Theology"
domain_primary_pct: 45
domain_secondary: "Physics"
domain_secondary_pct: 35
domain_tertiary: "Mathematics"
domain_tertiary_pct: 20
tags_weighted:
  - { tag: "consciousness", weight: 0.9 }
  - { tag: "measurement-problem", weight: 0.7 }
framework_keys: ["ME-VAR-CHI", "LAW-07"]
claim_ids: ["CLM-WATCHER-001"]
downstream_implications: ["Watcher model validates...", ...]
score_total: 34
s01_pos: 2    s01_neg: 0    s01_net: 2
s02_pos: 3    s02_neg: -1   s02_net: 2
# ... through s10
evd_support: 5
evd_counter: 2
evd_balance: 3
governing_question: "Can quantum measurement be formalized as..."
one_sentence_finding: "The Watcher model provides..."
build_next: "Derive the operator algebra for..."
coherence: 0.78
grade: "B-"
```

### Markdown Body Sections
- **Primary argument** — numbered logical steps
- **Hidden premises** — table of unstated assumptions
- **Argument strengthening** — table of improvements
- **Classical Prior Art Anchors** — historical witnesses
- **4-Dimensional Case & Defensibility Audit** — vulnerability diagnosis

---

## Tool 1: companion_cluster.py

**What it does:** Scans all companion papers, computes pairwise similarity across six dimensions, and clusters papers that share overlapping arguments/philosophy.

**The six similarity dimensions:**
| Dimension | Weight | Method |
|-----------|--------|--------|
| Tag overlap | 0.20 | Jaccard similarity on weighted tags |
| Domain overlap | 0.15 | Jaccard on normalized domain strings |
| Framework key overlap | 0.10 | Jaccard on ME variables/law references |
| Claim cross-references | 0.20 | Direct ID match or prefix overlap |
| Text similarity | 0.25 | SequenceMatcher on governing_question + one_sentence_finding |
| build_next similarity | 0.10 | SequenceMatcher on build_next strings |

**Clustering method:** Single-linkage at configurable threshold (default 25%).

**Outputs** (written to `_output/` subfolder):
- `00_CLUSTER_INDEX.md` — master list of all clusters with member papers
- `CLUSTER_NN.md` — per-cluster report combining arguments, hidden premises, weaknesses, build_next items
- `clusters.json` — machine-readable version of everything

**Why this matters:** David's corpus has papers that approach the same idea from different angles. Clustering identifies which papers are saying the same thing so the strongest arguments can be merged into one definitive version per topic.

---

## Tool 2: companion_stats.py

**What it does:** 20 different statistical views of the companion paper corpus.

**The 20 modes:**
1. **scoreboard** — Score distribution histogram + percentiles
2. **grade_curve** — A/B/C/D/F grade distribution
3. **domain_breakdown** — Papers per primary domain
4. **domain_cross** — Domain co-occurrence matrix
5. **tag_frequency** — Most common weighted tags
6. **tag_heatmap** — Tag × domain frequency table
7. **evidence_balance** — Support vs counter evidence distribution
8. **weakest_claims** — Papers ranked by lowest evidence balance
9. **strongest_claims** — Papers ranked by strongest evidence
10. **section_scores** — Average S01–S10 scores across corpus
11. **build_next_priority** — Upcoming work items ranked by frequency
12. **argument_density** — Papers ranked by argument step count
13. **framework_key_map** — Which ME variables/laws appear most
14. **coherence_ranking** — Papers ranked by coherence score
15. **content_type_dist** — Distribution of content types
16. **stale_candidates** — Papers that may need refresh
17. **bridge_audit** — Cross-domain bridge paper analysis
18. **formal_gaps** — Papers missing formal verification
19. **honesty_chain** — S05/S06/S08/S09 "honesty" section analysis
20. **progress_dashboard** — Overall corpus health summary

**Usage:**
```bash
python companion_stats.py --mode scoreboard
python companion_stats.py --mode grade_curve --mode domain_breakdown
python companion_stats.py                    # runs all 20
python companion_stats.py --json             # machine-readable
```

---

## Tool 3: companion_mindmap.py (Coming)

**What it does:** Reads all companion papers and generates an interactive HTML force-directed graph. Each paper is a node, connections are drawn from shared claims, tags, domains, and framework keys. You can click nodes, zoom, filter by domain, and see the connective tissue across the whole corpus.

**The key idea:** Every time a new paper comes through the pipeline, running the mind map script re-generates the graph with the new paper integrated. The graph grows as the corpus grows — it's the living picture of how everything connects.

---

## The ATOM System (Context)

Separate from the pipeline tools but feeding into them:

- **Claim atoms** — one primary claim extracted per paper (the paper's single overall finding)
- **Truth atoms** — 50-100 atomic true statements per paper, aggregated into a truth ledger
- **14-stage arc** — the extraction pipeline's full processing sequence
- **Repo:** `D:\GitHub\Faith-through-physics-atoms`

The atoms are the sentence-level complement to what the companion papers capture at the document level. The pipeline tools (clustering, stats, mind map) work on the companion documents; the atom system works on the claims within them.

---

## The Knowledge Bank

The knowledge bank is the cumulative output of the truth-atom extraction pass. Each paper yields atomic true statements tagged with:
- Epistemic mode (how we know it)
- Warrant class (what backs it up)
- Admission rule (DEFINITION/MATHEMATICAL/EMPIRICAL auto-admit; framework assertions only when canonized or Lean-receipted)

Dedup happens via embedding clustering. The bank grows with every paper processed.

---

## Folder Structure (pipeline_tools/)

```
pipeline_tools/
├── companion_cluster.py    — Clustering engine
├── companion_stats.py      — 20-mode stats engine
├── companion_mindmap.py    — Mind map generator (HTML output)
├── RUN_CLUSTER.bat         — Double-click launcher for clustering
├── RUN_STATS.bat           — Double-click launcher for stats
├── RUN_MINDMAP.bat         — Double-click launcher for mind map
└── _output/                — Generated output files land here
```

**Portability:** Change `OUTBOX_ROOT` on line ~18 of each `.py` file to point at whichever folder holds the companion papers. Copy the whole `pipeline_tools/` folder anywhere and it works.

---

## What David Needs From You

David will be dropping HTMLs and atom-related outputs into your context. Here's what's useful:

1. **Review companion paper quality** — the CKG_RECORD format is the contract; flag papers that don't fill it cleanly
2. **Work with clustering output** — when clusters are identified, help evaluate which papers carry the strongest version of each argument
3. **Build on the mind map** — the HTML graph shows the connective tissue; help identify gaps, orphan papers, and missing bridges
4. **Phase 2 (coming):** A merge/rewrite script that takes a selected cluster and combines the strongest arguments into one tightened companion paper. The rewrite targets the COMPANION paper, not the source paper.

---

*This briefing was generated from the active Cowork session building these tools. The companion format, pipeline architecture, and tool specifications are current as of this session.*
