# BRAIN STATION MAP
## X:\graphify\ — Infrastructure & Pipeline Stations
### Created: 2026-05-22
### Status: ACTIVE BUILD

---

## STATION 1: INGEST (BUILT ✅)
**Location:** X:\graphify\ingest\
**Script:** X:\graphify\auto_ingest.py
**Target DB:** 192.168.1.177:2665 / treaties / ingest_documents
**What it does:** Drop any file -> auto-parsed, SHA256 deduped, auto-tagged, full text stored in Postgres
**Auto-tags:** law, axiom, proof, theorem, grace, entropy, trinity, master-equation, strong-force, shannon, coherence, fruits, justice, mercy, sower, yukawa, lagrangian, isomorphism, gtq, mda, convergence, derivation
**Run:** `X:\graphify\venv\Scripts\python.exe X:\graphify\auto_ingest.py` (watch mode)
**Needs:** More keyword tags, YAML injection (see Station 3)

---

## STATION 2: CLASSIFICATION (DESIGNED, NOT WIRED)
**Location:** X:\file-intelligence-system-master\
**What it does:** NLP classification pipeline — YAKE + spaCy + KeyBERT + faster-whisper
**Domain codes:** TP, DT, EV, AP, MD, DC, OB, CB, SY
**Subject codes:** MQ, LG, JS, IS, SV, RS, GR, CS, EN, AX, WV, etc.
**Confidence tiers:** >85% auto-rename, 50-85% propose, <50% kickout
**Status:** Designed, requirements.txt exists, needs install + config + Postgres wiring
**Depends on:** Station 1 (ingest feeds classification)

---

## STATION 3: YAML INJECTION (NOT BUILT)
**What it does:** After classification, writes Obsidian-compatible YAML frontmatter into files
**Fields needed:**
  - tags (from auto-tagger + classifier)
  - domain (from FIS)
  - subject (from FIS)
  - law_mappings (which of 10 Laws this touches)
  - confidence_score
  - date_ingested
  - source_path
  - series (GTQ, MDA, Convergence, etc.)
  - status (draft, review, canonical, published)
**Depends on:** Station 2

---

## STATION 4: GRAPHIFY KNOWLEDGE GRAPH (INSTALLED, NOT RUN)
**Location:** X:\graphify\
**Venv:** X:\graphify\venv\ (Python 3.13, graphifyy 0.8.14, openai installed)
**What it does:** Builds knowledge graph from corpus — nodes, edges, communities, god-nodes
**Output:** graphify-out/graph.json, graph.html, GRAPH_REPORT.md
**Two modes:**
  - `update` = AST-only, FREE, no API calls
  - `extract` = AST + semantic LLM, costs Gemini API tokens
**API key:** GEMINI_API_KEY set at User level
**Target corpus:** O:\Production Vault (16K files) or O:\Vault (250K files — expensive)
**Status:** Installed, needs first run
**Depends on:** Nothing (independent)

---

## STATION 5: POSTGRES SYNC (SCOUT BRIDGE BUILT)
**What it does:** Bridges Graphify graph.json -> Postgres without mixing it into legacy paper-grader graph tables
**Direction:** Graphify output INTO Postgres first; metadata back into graph later
**Current DB state:** 
  - treaties DB: 78 nodes, 53 edges, 6 axioms, 5 papers (paper grader output)
  - crawlab_data DB: 52K link graph, 4.5K apologetics links, 3.9K YouTube entries
  - theophysics DB: DOES NOT EXIST (was dropped/rebuilt)
**Bridge:** `graphify_pg_bridge.py`
**Safety:** Dry-run by default; writes only with `--apply`; credentials come from `GRAPHIFY_PGPASSWORD` / `PGPASSWORD`; Graphify data goes into separate `graphify_runs`, `graphify_nodes`, and `graphify_edges` tables instead of the legacy paper-grader graph tables.
**Dry-run verified:** 2026-05-24, against `runs\lane3-small-update-20260524\corpus\graphify-out\graph.json` (41 nodes / 37 edges / 0 missing endpoints) and `runs\ai-chats-theophysics\graphify-out\graph.json` (188 nodes / 174 edges / 0 missing endpoints).
**Depends on:** Station 4 (graph output) + Postgres credential env var

---

## STATION 6: WEEKLY DIGEST / n8n (NOT BUILT)
**What it does:** Automated weekly workflow
  - Triggers Graphify update on vault
  - Dumps new graph.json to X: drive
  - Pushes updated nodes to Postgres
  - Posts summary to comms hub
  - Optionally posts to Obsidian daily note
**Platform:** n8n on NAS (192.168.1.177)
**Depends on:** Stations 4 + 5

---

## STATION 7: RAG QUERY LAYER (NOT BUILT)
**What it does:** Makes the knowledge graph queryable by any AI partner
**Options:**
  - pgvector extension on existing Postgres (embeddings in same DB)
  - Graphify query/path/explain commands against graph.json
  - MCP server wrapping Graphify (serve.py exists in package)
**Depends on:** Stations 4 + 5

---

## CONTENT REVIEW QUEUES (SEPARATE FROM PIPELINE)

### MDA — Moral Decline of America
**Location:** D:\MDA-BUILD\articles\HTML\ (26 articles)
**Index:** index.html (dark theme, red #dc2626 accent)
**Status:** Out of order. Needs LLM-assisted CLI review pass.
**Known issues:** Omniscience papers jumbled, inter-article claims inconsistent
**Stories:** D:\MDA-BUILD\stories\ (7 HTML + audio)
**Action:** Cowork/Codex session — read through, reorder, fix cross-refs

### GTQ — Genesis to Quantum
**Location:** Desktop\Codex\GTQ_CANONICAL\ (canonical MDs), Z:\GTQ_Series (HTML)
**Status:** 26 HTML articles built. Needs same review pass as MDA.
**Action:** Same approach — LLM CLI pass with human decisions

### Convergence Series
**Status:** Not inventoried yet
**Action:** Inventory first, then review

---

## POSTGRES DUMP BACKUP
**Location:** X:\graphify\postgres_dump\
**Date:** 2026-05-22
**Contains:** All treaties + crawlab_data tables as JSON
**Manifest:** MANIFEST.json

---

## KEY CREDENTIALS (rotate after use)
**NAS Postgres:** root@192.168.1.177:2665 / pw: [see session]
**Gemini API:** GEMINI_API_KEY set as User env var
**Laptop Postgres:** offline / password was changed March 2026

---

## BUILD ORDER (recommended)
1. ✅ Station 1 — Ingest (done)
2. Station 4 — Run Graphify free pass on Production Vault
3. Station 5 — Bridge graph.json to Postgres
4. Station 2 — Wire up FIS classification
5. Station 3 — YAML injection
6. Station 7 — RAG query layer
7. Station 6 — n8n weekly automation

---

## STATION 8: DIFF DETECTOR / DRIFT MONITOR (NOT BUILT)
**What it does:** Hashes all tracked files weekly, compares to previous scan, surfaces changes
**Catches:**
  - Canonical docs that got edited without logging
  - Database tables that disappeared (would have caught theophysics DB wipe)
  - Files that moved between folders
  - Content drift in published articles
**Output:** Weekly diff report — "47 files changed, 3 canonical, here's what moved"
**Key insight:** This is insurance. Everything else builds forward. This catches silent breaks.
**Depends on:** Nothing (independent, runs against any folder)

---

## STATION 9: CONFLICT RESOLVER (NOT BUILT)
**What it does:** Finds near-duplicate content across locations, surfaces for reconciliation
**Problem it solves:** MDA in 3+ folders on D:, vault content scattered across O: root
**Method:** SHA256 exact dupes (in ingest already), fuzzy match (rapidfuzz/SBERT) for near-dupes
**Output:** Conflict queue — "these 2 files are 90% similar, different names, which is canonical?"
**Depends on:** Station 1 (needs file inventory)

---

## STATION 10: PUBLICATION GATE (NOT BUILT)
**What it does:** Automated pre-flight before anything goes live on faiththruphysics.com
**Checks:** STT artifact scanner, series consistency checker, voice check, broken links
**Output:** Scored report per article + punch list of fixes
**Human makes final call — gate just catches what kills reader trust**
**Depends on:** Content exists in reviewed state

---

## STATION 11: COMMS BRIDGE (NOT BUILT)
**What it does:** Connects pipeline to comms hub automatically
**Events that trigger posts:**
  - Graphify finds new god-node or surprising connection -> broadcast
  - FIS classifies low confidence -> triage channel
  - Diff detector finds canonical doc changed -> alert

---

## STATION 12: CLAIM COVERAGE LAYER (SPEC'D, NOT BUILT)
**Spec:** `\\dlowenas\brain\graphify\CLAIM_COVERAGE_LAYER_SPEC.md`
**What it does:** Turns every extracted claim into a visible coverage object with span, definition, dependency, local support, series support, source support, method support, science audit, process-mapping, overclaim, contradiction, reader-burden, and next-action status.
**Key output:** Claim matrix / graph snapshot where each claim shows coverage dots: green=satisfied, yellow=partial, red=missing/blocker, blue=inherited from series, purple=supported by proof lab, gray=not applicable.
**Why it matters:** Prevents series arguments from being falsely graded as isolated pages. A claim can be weak locally but strong in series context, or strong rhetorically but red on source/provenance.
**Depends on:** span_trace, claim ledger, series context ledger, evidence/source mapper, science/process-isomorphism audit, contradiction/overclaim scan.
**First targets:** MDA-037 through MDA-041 statistical/coherence spine; GTQ bridge/process-isomorphism pages.
**Status:** Spec created 2026-05-25. Needs report-only prototype that exports JSON/CSV/HTML matrix before any production integration.

---

## STATION 13: NABLA SEMANTIC ADDRESSING / LOSSLESS SNAPSHOT (SPEC'D, NOT BUILT)
**Protocol:** `\\dlowenas\brain\graphify\NABLA_SEMANTIC_ADDRESSING_PROTOCOL.md`
**Prompt:** `\\dlowenas\brain\graphify\NABLA_CLASSIFIER_PROMPT.md`
**Calibration:** `\\dlowenas\brain\graphify\NABLA_CALIBRATION_TEST.md`
**What it does:** Assigns each artifact a deterministic semantic address in the form `D/N/V/A/U/R :: VECTOR :: HASH`, then produces a reconstructable audit snapshot: claim archaeology, evidence chain, kill architecture, equation semantics, domain boundary, reviewer seeds, four-score dashboard, eight gaps, score events, and repair queue.
**Key rules:** Score the artifact, not the topic; binary vector only (`0` or `3`); confidence is continuous but does not alter the address; fixed tie-break order `E -> C -> G -> K -> M -> T -> R -> F -> S -> Q`; C is explicit synthesis only; E is artifact disorder only.
**Agreement metric:** Hamming distance across the ten binary vector variables. 0=exact, 1=strong with review flag, 2=adjudicate, 3+=unstable classification.
**Why it matters:** Gives every paper/page/file a universal, AI-readable semantic address and snapshot so future models can reconstruct what it is, what it does, how risky it is, and how to repair it without relying on folder vibes.
**Depends on:** ingest/document text, optional span trace and claim extraction. Later feeds claim coverage layer, proof packets, Obsidian metadata, and Postgres audit memory.
**Status:** Protocol/prompt/calibration created 2026-05-25. Needs report-only prototype and multi-model calibration run.
  - Weekly digest completes -> summary to all channels
**Pipeline shouldn't be silent — it should talk to the team**
**Depends on:** Stations 4, 6, 8

---

## STATION 12: CLOUDFLARE PERSONAL DASHBOARD / NLP COMMAND CENTER (NOT BUILT)
**What it does:** The convergence point. One URL. Queryable intelligence layer.
**Stack:**
  - Frontend: Cloudflare Pages — dashboard UI
  - Backend: Cloudflare Worker — routes queries to NLP/RAG
  - NLP/RAG: Worker calling Gemini/Claude API with context, or NAS service behind tunnel
**Data sources it queries:**
  - Recent activity buffer (last 48 hours across all AI partners)
  - Postgres (structured — papers, axioms, scores, ingest)
  - graph.json (relational — knowledge graph, communities, god-nodes)
  - Comms hub (what each AI partner has been working on)
**Example queries:**
  - "What happened while I was asleep?"
  - "Current state of Law 4 derivation?"
  - "Show me everything tagged 'sower' across all sources"
  - "What did Jim post this week?"
  - "Which MDA articles are out of order?"
**This is the command center. Everything else feeds into it.**
**Depends on:** Stations 1, 4, 5, 7, 11

---

## BUILD ORDER (recommended)
1. ✅ Station 1 — Ingest (done)
2. Station 4 — Run Graphify free pass on Production Vault
3. Station 8 — Diff detector (insurance — catches silent breaks)
4. Station 5 — Bridge graph.json to Postgres
5. Station 2 — Wire up FIS classification
6. Station 3 — YAML injection
7. Station 9 — Conflict resolver (needs file inventory from 1+2)
8. Station 7 — RAG query layer
9. Station 11 — Comms bridge
10. Station 10 — Publication gate
11. Station 6 — n8n weekly automation (ties it all together)
12. Station 12 — Cloudflare dashboard (the crown — needs everything underneath)
