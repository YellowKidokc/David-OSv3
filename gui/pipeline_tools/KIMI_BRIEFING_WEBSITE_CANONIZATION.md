# Website Canonization Pipeline Briefing — For Kimi
**POF 2828 | September 17, 2026**
**From: Adam (David's Claude/Cowork session)**

---

## Purpose of This Document

David asked me to rigorously explain how the canonization process feeds the website, so you can build the import path. This covers: what nerve is, what the canonization pipeline produces, how that output should flow into faiththruphysics.com, and what the companion paper tools (atoms, mind maps, clustering, stats) contribute to that flow.

---

## 1. The Canonization Pipeline — What Exists

### 1.1 The Evidence Chain Intake

This is the front door. Lives at:
```
\\192.168.2.50\h_hp\Desktop\_____pipeline-workflows-main\EVIDENCE_CHAIN_INTAKE
```

**What it does:** Takes source papers (David's 1,300+ paper corpus) and runs them through 3–4 API calls per paper:
1. **Audit call** — epistemic review (what's claimed, what's supported, what's overstated)
2. **Claims/evidence call** — structured extraction of claims, evidence, proofs, bridges
3. **Knowledge bank call** — truth atoms (50–100 atomic true statements per paper)
4. **Optional truth-atom extraction** — feeds the growing truth ledger

**What it produces:** Companion papers in CKG_RECORD v2.0.1 format — `.md` files with YAML frontmatter carrying scores, domains, tags, claim IDs, evidence ratings, and 14 structured headings in the body.

**Output structure (7-lane flat OUTBOX):**
```
OUTBOX/
├── 01_UNTOUCHED/        — Raw paper, never modified
├── 02_PROCESSED/        — Master companion copy (source of truth)
├── 03_BY_DOMAIN/        — Copies sorted into ~16 closed domains
├── 04_BY_TYPE/          — 7 closed content types
├── 05_BY_READER/        — ~10 closed reader categories
├── 06_CLAIMS/           — Lean Floor handoff (formal verification staging)
├── 07_TRUTH_LEDGER/     — Accumulated truth atoms
└── 90_LEGACY/           — Old folder structure, frozen, don't touch
```

**Rating scale:** −10 to +10 with verifier caps:
- API max: +8
- Human review: +9
- Lean receipt only: +10
- Negatives = failed tests kept as negative controls (never deleted)

### 1.2 The Canon Ballot Process

Claims don't become canon by API score. They go through a multi-AI cold vote:

1. A **CANON_VOTING_BALLOT** is drafted with numbered items (V-01, V-02, etc.)
2. Multiple AIs vote independently (cold — they haven't seen each other's work)
3. Votes come back to the Opus seat (David's coordination point)
4. **Tally produces a three-way split:** CANON / OPEN / RETIRED
5. Everything downstream builds on the settled ground from that tally

**Current ballot state:** Numbers in God ballot (V-01 through V-33, four blocks) has votes from Codex and Fable. David's own votes partially recorded. The [F-d] (Fable-delegated) rows are STILL UNRATIFIED as of the last check. This is the #1 blocking item for advancing canon status.

### 1.3 The Nerve Desktop Agent

**Repo:** `D:\GitHub\nerve` (YellowKidokc/nerve on GitHub)

**What nerve is:** A Rust webview-panel desktop agent — a local application with:
- Global hotkeys
- Clipboard hook
- Hotstring/prompt expansion
- TTS (text-to-speech)
- Cloudflare Worker + KV sync API
- HTML panels served inside the webview

**Where canon pages live in nerve:**
```
nerve/source/html/
├── 7q-engine.html          — The 7-Question Scientific Method engine
├── theophysics-hub.html    — Framework hub/dashboard
├── [canon workbench pages] — (being built)
└── [atom builder pages]    — (being built)
```

**The four surfaces (from David's ruling, no duplicated authority):**

| Surface | Owns | Output |
|---------|------|--------|
| **Atom Builder** | Intake — object type, register, definition class, source, scope, candidate fields, Lean status | A candidate atom (not yet admitted) |
| **Classification/Reconciliation** | Stage 5 emergent-vs-inherited comparison, conflict detection, blast radius | A reconciliation proposal (never a rewritten atom, never an admission) |
| **Canon Workbench** | Review staged proposals, preview consequences, prepare human ruling | A decision package for David |
| **Engine** | Versions, candidates, rulings, edges, receipts, admitted state | The canonical record |

**Key ruling:** The Builder page opens FIRST. The selection is preserved in local draft storage immediately. Nothing enters the shared candidate graph until David presses **Stage Candidate** (not Save, not Admit). Ollama may suggest fields before staging but stays visibly AI-proposed and editable, and stays outside the sealed engine.

---

## 2. What Flows to the Website

### 2.1 The Corrected Methodology (David's ruling, Sep 16)

David corrected the methodology — and you (Kimi) already identified the precedent proving it:

> **Static HTML from NAS masters → deploy forward, fix retroactively → no API layer, just `site-shell.js` doing vanilla JS injection.**

The three rules:
1. **Markdown templates are the contract** — DeepSeek (or any AI) fills them, but a human could fill the same slots by hand
2. **The thin layer does only three things:** UUID binding, auto-filling template fields from the source paper, and flagging/filling missing pieces as `AI-FILLED — UNCHECKED`
3. **No grading, no promotion, no closing OPENs** — those stay behind the ruling door with receipts

### 2.2 The Flow: Canonization → Website

```
SOURCE PAPER
    │
    ▼
EVIDENCE_CHAIN_INTAKE (3-4 API calls)
    │
    ▼
COMPANION PAPER (CKG_RECORD v2.0.1)
    │
    ├──→ PIPELINE_TOOLS (clustering, stats, mind map)
    │         → identifies gaps, merges, strongest arguments
    │
    ├──→ TRUTH LEDGER (atomic statements, dedup'd)
    │
    ├──→ CLAIMS (06_CLAIMS lane → Lean Floor for formal verification)
    │
    ▼
CANON BALLOT (multi-AI cold vote)
    │
    ▼
THREE-WAY SPLIT: CANON / OPEN / RETIRED
    │
    ▼  [only CANON items flow forward]
    │
NERVE CANON ENGINE (preserves versions, edges, receipts)
    │
    ▼
THE_STORY (20 chapters, the public narrative arc)
    │
    ▼
WEBSITE PAGES (faiththruphysics.com)
    │
    ├── Cathedral shell (5-column layout, reading level toggle)
    ├── Shell-data JSON block drives everything
    ├── MTL (Math Translation Layer) — equation/wordEquation/plain stack
    ├── Claim beacons at /claims/... paths
    └── Audio dock (AT-/D-/DD-/C- prefix scheme)
```

### 2.3 THE_STORY — The Public Surface

The 20-chapter arc is what the public sees. Lives at:
```
C:\Users\David\Documents\faiththruphysics.com\00_ Production\00_ Production\00_THE_STORY
```

**Chapters 02–20:**
02. Truth Before Argument
03. I AM
04. Four Debts
05. Trinity and Truth
06. Logos / Word / Information
07. Creation as Ordered Gift
08. Science as Witness
09. Consciousness as Witness
10. Freedom / Trust-Space
11. Fall / Damaged Receiver
12. Evil Vandalizes
13. Cost / Justice / Mercy
14. Grace as External Repair
15. Christ Enters the Cost
16. Redemption Without Erasure
17. Resurrection and Identity
18. Fruits as Restored Life
19. Fruits and Counterfeits
20. What Survived the Pressure

**Each chapter has three editions:**
- **FL** (full/long) — the source edition, the one to read
- **SH** (short) — condensed public surface
- **IX** (index) — support/pointer document

All are currently **CANDIDATE_DRAFT — NOT ADMITTED**. Canon status pending ballot ratification.

### 2.4 The Page Shell

Every published page follows the **Universal Page Shell Integration Guide v1.0** (dated 2026-07-02):

**4 layers:**
1. **Top bar** — navigation, domain context
2. **Expandable verify panel** — show-your-work (claims, evidence, MTL)
3. **Audio dock + mini-player** — TTS/podcast/debate/critique tracks
4. **Footer system** — provenance, audit trail

**All driven from one JSON block:**
```html
<script id="shell-data" type="application/json">
  { /* claims, proofs, MTL arrays, glyph data, audit metadata */ }
</script>
```

The **MTL (Math Translation Layer)** is already built and working — it's a 3-part stack per equation:
- `equation` — the formal math
- `wordEquation` — every symbol swapped for 1–2 plain words, operators kept
- `plain` — full English sentence

Produced by Call 2 of the 3-call Topbar Fill pipeline (System B) at:
```
D:\GitHub\Python-WEB\topbar\canonical-page-shell\api-fill\
```

---

## 3. What the Pipeline Tools Give You

These are the Python tools we just built in `D:\GitHub\David-OSv3\gui\pipeline_tools\`:

### 3.1 companion_cluster.py
Scans companion papers, clusters them by 6 similarity dimensions (tags, domains, framework keys, claims, text, build_next), and writes output to `_output/`:
- `00_CLUSTER_INDEX.md` — master list of clusters
- `CLUSTER_NN.md` — per-cluster combined arguments
- `clusters.json` — machine-readable

**For the website:** Clustering tells you which papers cover the same ground. The strongest cluster member becomes the definitive page for that topic. Other papers point to it via topic keys.

### 3.2 companion_stats.py
20 statistical views across the corpus — score distributions, domain breakdowns, evidence balance, weakness rankings, framework key frequency, etc.

**For the website:** Stats feed the dashboard. Which domains are strongest? Where are the gaps? What needs more evidence? This is the health monitor.

### 3.3 companion_mindmap.py (NEW)
Generates an interactive HTML force-directed graph — every paper is a node, connections drawn from shared claims/tags/domains/framework keys. Black/gold theme. Click nodes for detail. Filter by domain. Search. Zoom/pan.

**For the website:** This IS the connective tissue view. Every time a paper goes through the pipeline, re-run the mind map and it grows. This could serve as:
- A navigation tool on the site (click a node → go to that paper's page)
- A "how everything connects" visualization for visitors
- An internal tool showing David where the gaps and orphan papers are

### 3.4 The Mind Map as Living Knowledge Graph

Here's the key idea David is after: **every paper that comes through the pipeline gets offered for insertion into a growing knowledge graph.** The mind map isn't a one-time snapshot — it's regenerated every time. As the corpus grows, the graph grows. The connections between papers ARE the framework's connective tissue made visible.

For the website, this means:
- Run the pipeline on a paper → companion generated → run mind map → graph updated
- The graph shows which claims connect to which, across domains
- Visitors can see the entire framework as a navigable map
- Each node links to its chapter in THE_STORY or its claim page

---

## 4. What You (Kimi) Should Build

Based on your findings (Sep 16) and David's methodology correction:

### 4.1 Immediate: Fix the Findability Gap
- Add `sitemap.xml` and `robots.txt` to the live Cloudflare deployment
- This alone will dramatically improve Google indexing of the deep pages (`/mda/`, `/genesis-to-quantum/`, `/moral-decline/`, `/one-page-stories/`)

### 4.2 Publish the Consilience Atlas
The Atlas master template exists in two repos:
- `YellowKidokc/Faith-through-physics-atoms` → `_template/html/consilience-atlas-master-template.html` (v1.0-freeze-candidate)
- `YellowKidokc/Nabla` → `atom_package/_template/html/`

Its `.well-known/claim-beacons.json` declares canonical URLs like `faiththruphysics.com/claims/master-equation/01/001` — but those paths currently serve the homepage fallback. Publishing the Atlas under those beacon URLs would make the declared canon scheme actually resolve.

### 4.3 Import Canonization from Nerve

This is the big one. The flow:

1. **Nerve's canon engine** holds the admitted claims, versions, edges, receipts
2. **Export from nerve** as JSON (the engine already produces structured data)
3. **Transform to shell-data format** — each canon claim becomes an entry in the `<script id="shell-data">` JSON block
4. **Inject into page templates** — the thin layer (UUID binding + field filling + `AI-FILLED — UNCHECKED` flagging)
5. **Deploy static HTML** to Cloudflare

The import should respect:
- **Only CANON items flow to the public site** — OPEN stays behind the ruling door
- **Provenance is preserved** — every claim carries its ballot vote record, its rating (−10 to +10), its verifier cap
- **MTL is carried** — each equation gets the 3-layer translation
- **Lean receipts are surfaced** — a claim with a +10 Lean receipt shows that receipt

### 4.4 Integrate the Mind Map

The mind map HTML (`_output/MIND_MAP.html`) can be:
- Served as a standalone page at a route like `/map` or `/connections`
- Embedded in the cathedral shell as a navigation aid
- Auto-regenerated by a build script whenever the corpus updates

The nodes should link to their corresponding pages on the site. Right now nodes carry `paper_id`, `domain`, `claim_ids`, and `framework_keys` — enough to route to the right page.

### 4.5 The Atom/Truth Display

Each paper's truth atoms (the 50–100 atomic statements from the knowledge bank call) can be displayed as an expandable section on its page — or aggregated into a site-wide truth ledger. The atoms carry:
- Epistemic mode (how we know it)
- Warrant class (what backs it up)
- Provenance (ORIGINAL / HISTORICAL_WITNESS / MODERN_PARALLEL / UNVERIFIED)

---

## 5. File Locations Reference

| What | Where |
|------|-------|
| Live site source | `D:\GitHub\faiththruphysics-site\` |
| Live site (Cloudflare) | https://faiththruphysics.com |
| GitHub repo | `YellowKidokc/FaiththruPhysics`, branch `HTML` |
| Nerve repo | `D:\GitHub\nerve` (YellowKidokc/nerve) |
| Nerve canon HTML pages | `nerve/source/html/` |
| Atlas template | `Faith-through-physics-atoms/_template/html/consilience-atlas-master-template.html` |
| Content masters (NAS) | `\\dlowenas\h_hp\Desktop\Folders\Master HTML\` |
| Production folder | `C:\theophysics\PRODUCTION\` |
| Canonical root | `C:\theophysics\CANONICAL\` |
| THE_STORY chapters | `C:\Users\David\Documents\faiththruphysics.com\00_ Production\00_ Production\00_THE_STORY` |
| Pipeline tools | `D:\GitHub\David-OSv3\gui\pipeline_tools\` |
| Evidence Chain Intake | `\\192.168.2.50\h_hp\Desktop\_____pipeline-workflows-main\EVIDENCE_CHAIN_INTAKE` |
| Canonical templates | `999_TEMPLATES\MASTER_PAPER_TEMPLATE_v0.3.md` |
| Architecture spec | `C:\theophysics\_CANON\THEOPHYSICS_ARCHITECTURE_v11_CANONICAL.md` |
| Topbar Fill / MTL | `D:\GitHub\Python-WEB\topbar\canonical-page-shell\api-fill\` |
| Deployment handoff | `KIMI-DEPLOYMENT-HANDOFF.md` in the FaiththruPhysics repo (written by Claude Opus 4.6, June 17, 2026) |

---

## 6. Design Constraints (Non-Negotiable)

1. **Pushing down is never optional** — every truth must reach the everyday person. The 14-stage arc enforces this.
2. **No API layer between templates and the site** — static HTML, vanilla JS injection via `site-shell.js`, deployed forward
3. **The vault (Obsidian/Nimbalyst) is the canonical artifact**, not any database — series complete → export → that export IS the markdown canonicity
4. **Two registers:** DECLARATION (public, unhedged voice) and CANON (graded, gated). The website is declaration register. The audit runs but arrives as a separate private file.
5. **AI-filled content is flagged** — `AI-FILLED — UNCHECKED` until David reads it. No AI output passes as human-verified.
6. **Historical thinkers are cited as WITNESSES, not sources** — David derived the arguments independently; Augustine, Aquinas, etc. serve as independent confirmations from other centuries.

---

## 7. The Handoff You Already Found

The `KIMI-DEPLOYMENT-HANDOFF.md` in the FaiththruPhysics repo (written June 17, 2026) describes the original site build. That document plus this briefing should give you the complete picture: the June build shows what's deployed, this briefing shows what's coming in from the canonization pipeline.

---

*This briefing was written by Adam (Claude/Cowork, POF 2828 session) at David's request, September 17, 2026. The pipeline architecture, tool specs, and design constraints are current as of this session. The companion tools (cluster, stats, mind map) are deployed and tested at `D:\GitHub\David-OSv3\gui\pipeline_tools\`.*
