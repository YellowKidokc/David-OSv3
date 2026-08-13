# FIS Federated Architecture — databases, search, external classification

Design captured from the multi-model synthesis + rulings. Preserved so it isn't
lost again (the case-builder already got lost once — see §5).

## 1. Not one giant DB — federated territory databases + a central catalog

```
FIS Central
├── catalog.sqlite            (territories · object_locator · project_membership
│                              · global_aliases · sync_state · schema_versions)
├── T001 Desktop  → territory.sqlite
├── T002 Documents→ territory.sqlite
├── T003 H:       → territory.sqlite
└── T004 Z:       → territory.sqlite
```
Each **territory.sqlite** holds full local records (objects, paths, names, tags,
classifications, relationships, operations, tombstones, content_terms,
external_entities). The **catalog** holds only the locator: which territory owns
an object and its current path/sequence. Initial scan populates a territory;
filesystem events + FIS operations update it incrementally.

**What fis-atlas already has for this:** `lineage.py` IS the object registry
(stable `F-######` ids + current location + relationship graph + `trace`);
`store.py` is a per-scan SQLite. The federation layer = a central catalog +
coordinator over N territory DBs.

## 2. One coordinator, one AI-facing operation

The AI never picks `query_h_database` vs `query_d_database`. It calls one thing —
`search_all_territories` — and a deterministic coordinator resolves which
territories are registered/available, runs the SAME versioned query against each,
and merges. Results keep their origin: `T003:F-008142` (never bare ids/paths, so
locals can't collide).

Determinism requires: shared schema version · controlled tag dictionary · stable
ids · normalized timestamps · defined ranking/tie-break · recorded sequence
numbers · fixed merge order. Every report states the snapshot it searched:
```yaml
query_run: QR-0041
territories: {T001: seq_884, T003: seq_184227, T004: unavailable}
complete: false        # never claim it searched everything when Z: was offline
```

**SQLite reality (honest):** `ATTACH DATABASE` works for local drives on one
host; WAL does NOT work across a network filesystem between hosts, and
multi-database transactions aren't atomic across attached DBs. So: local drives →
direct SQLite; NAS/other machine → that host owns its DB and exposes a small
read API; central search → federated read-only; cross-territory changes →
coordinated jobs with individual receipts, never a pretend-global transaction.
DuckDB can attach+query many SQLites for analytics/reports — not the live ledger.

## 3. Rough language → structured intent → deterministic search

The missing bridge (and the only genuinely new part to build):
```
"find that exel stuff about moral decline it might be mda"
   → small local LLM →
{ intent: find_files, file_types: [xlsx,csv], concepts: [MDA, "Moral Decline of America"],
  territories: all_available, include: [current_paths, previous_paths, project_members,
  copies, derivatives], operation_mode: read_only }
```
The model interprets language into a typed request; it does **not** invent SQL or
decide which drives exist. The deterministic coordinator resolves project records,
queries every registered territory, follows moves/renames/copies, verifies current
paths, does a narrow disk scan only for gaps. If interpretation is uncertain, the
GUI asks ("Excel files *about* MDA?  /  names containing 'MDA'?  /  all MDA-project files?").

## 4. External classification = imported evidence, never authority

For "classifications of God": Wikidata (entity ids, labels/aliases, instance-of/
subclass-of, SPARQL) is the backbone; Wikipedia categories are noisy supplemental;
ConceptNet gives loose relations. **Resolve the meaning first** (God = monotheistic
concept? deity? a title/book?) — the GUI presents the entity choice. Then store
with provenance and separate lanes:
```yaml
classification: {value: deity, source: Wikidata, status: external}
classification: {value: foundational_ground, source: POF_2828_ontology, status: canonical_internal}
```
External never overwrites internal. **Cache the reviewed entity package centrally**
(aliases, broader/narrower/related, internal meaning, excluded meanings) so every
territory uses the same entity id + dictionary — that's what makes a simultaneous
D/H/Z/Documents search deterministic instead of four keyword guesses.

## 5. The case-builder (found; do not lose again)

`…\Startup\AHK\stratum\chi_jm_diagnostic_engine_v4_gold.py` — the **χ Justice–Mercy
Diagnostic Engine**: takes a document, builds the case for/against it, reports
coherence/discoherence, justice/mercy balance, fruit/anti-fruit, **evidence
pressure**, claim maturity, and **failure modes**, and orchestrates the
paper-intelligence-suite scorers (X:/04_STATIONS/paper-intelligence-suite.station:
academic_scorer, 7Q, novelty_classification). This is the "make it indefensible"
loop. It maps onto the Consilience-Atlas defensibility model (claim → evidence →
audit → verdict-against-self) and the NABLA-χ defensibility snapshot.

## 6. Foundation ruling

- **FilePilot AI** (MIT) is the strongest GUI/ops/MCP base — PySide6 GUI, SQLite,
  indexing, Office extraction, preview-plan/apply/undo, JSONL audit, MCP with
  scoped `--allow D:\ --allow H:\ --read-only`, and GUI/CLI/MCP all call the same
  services. **But it's near-zero adoption — clone, run, and test before trusting.**
- **File Brain** is the stronger typo-tolerant semantic search reference (but
  read-only + Docker-heavy).
- **FreePeak DB-MCP** is the multi-database *pattern* to borrow — expose ONE
  `search_all_territories`, not a tool per DB.

**Build order:** test FilePilot → add `territories` + stable global ids → add one
federated `search_all_territories` → add the NL→intent translator → lineage +
tombstones after. Don't rebuild the GUI/indexer/extractor/MCP from scratch.

## 7. Housekeeping (deferred, physical, risky)

Scattered D: roots (`00_CANON_REFERENCE`, `00_Canonical_PRODUCTION_v1.0`,
`CHI PARTS`, `evidence`, `Routing`, `AI-RESEARCH-AGENTS`, `article-builder`,
`brain`, `Evidence_HQ`, `TKE_Production_Vault_Starter_v1`, `Vault-Rater-TSR100`)
should live under David-OS. This is a Phase move with a ledger + shims — never a
silent bulk move (they may have live importers). Register each as a **territory**
rather than physically relocating first.
```
