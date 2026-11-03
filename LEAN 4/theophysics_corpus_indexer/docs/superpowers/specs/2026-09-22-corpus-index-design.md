# Corpus Index — Design v1.0

**Date:** 2026-09-22  
**Goal:** Build a read-only indexer for the POF 2828 / Theophysics Lean corpus that hashes every file, deduplicates by SHA-256, classifies `.lean` files by content-derived declarations, loads existing receipts, and writes the P1/P2 acceptance report.

## Scope

This design covers Phases 1 and 2 only. Phase 3 (CocoIndex + pgvector embeddings) and Phase 4 (pull CLI) are out of scope for this build; they are noted as follow-up work.

## Architecture

A single Python pipeline runs on the Windows box and talks to the existing Postgres server at `192.168.1.177:2665`.

- **Read-only scanner** walks the six source roots, skips the blocked directories, and yields every file of the configured extensions.
- **Hasher** computes SHA-256 incrementally for each file. The manifest of 290 canonical files is used to avoid recomputing hashes that are already known.
- **Loader** ingests three existing record sources: `00_MANIFEST.csv`, `registry.json`, and `BATCH_RUNS/*`.
- **Lean parser** masks strings/comments and extracts top-level declarations (`theorem/lemma/def/axiom/...`) plus active `sorry` occurrences.
- **Classifier** applies the ordered keyword rules from the build spec to declaration names and import modules. It never uses folder names except for the explicit `Mathlib` path-segment library rule.
- **Database writer** upserts rows into `files`, `locations`, `declarations`, and `receipts`, then computes `verif_level` from receipts.
- **Reporter** emits the P1 gate metrics, the P2 success sentence, and a 50-file spot-check CSV.

## Data model

Same schema as the build spec, except the `embeddings` table is deferred until the `vector` Postgres extension is installed on the server:

```sql
CREATE EXTENSION IF NOT EXISTS vector;  -- deferred; not available today
```

Tables created now:

- `files` — primary record per unique SHA-256.
- `locations` — one row per discovered path.
- `declarations` — one row per `(sha256, name, kind)` for `.lean` files.
- `receipts` — `BUILD`, `PRINT_AXIOMS`, `AI_REVIEW` results.

## Verification levels

Computed from receipts and declaration analysis, exactly as the build spec defines:

1. `KERNEL` — BUILD pass + PRINT_AXIOMS clean of `native_decide`.
2. `KERNEL_NATIVE_DECIDE` — BUILD pass + `native_decide` present in axioms output.
3. `AI_REVIEW` — only AI review receipts exist and no build receipt passes.
4. `GAPS` — active `sorry` count > 0.
5. `UNVERIFIED` — everything else.

## Classification

For `.lean` files:

- Library detection first: `Mathlib` import/paths or known Mathlib declaration names.
- Then ordered keyword rules on declaration names.
- `series_conf` is `0.95` for a keyword match, `1.0` for `LIBRARY`, `0.0` for unclassified.

For non-`.lean` files:

- Same ordered rules applied to file content keywords.
- Library detection limited to path/content evidence.

## Source roots

```text
//192.168.2.50/h_hp/Desktop 2/LEAN 4
//192.168.2.50/h_hp/Desktop/___Pipeline_Done_New/One page paper API/LEAN4
//192.168.2.50/h_hp/Desktop/___Pipeline_Done_New/One page paper API/EVIDENCE/OUTBOX
//192.168.2.50/h_hp/Desktop/_____pipeline-workflows-main/LEAN_FLOOR
D:/TEMP_LEAN_ZIP
C:/Users/David/Documents/faiththruphysics.com/04_MASTER_EQUATION
```

## Blockers / follow-ups

- `pgvector` Postgres extension is not installed on `192.168.1.177:2665`; the `embeddings` table is deferred.
- P3 (CocoIndex) and P4 (CLI pull) are not implemented in this build.
