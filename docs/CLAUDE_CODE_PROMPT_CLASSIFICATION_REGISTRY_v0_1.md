# CLAUDE CODE PROMPT: one classification registry in David OS (v0.1)
**Date:** 2026-10-23 | **Author:** Claude (Sonnet) with David | **Status:** ready for a builder, read receipt first

## Read receipt (first message back, before any edit)
Restate in your own words: (1) why nothing is moved, renamed or deleted (copy-first; originals stay),
(2) why three sheets all called `MASTER_TERM_REGISTRY` are treated as three different things until proven
the same, with conflicts reported and never merged silently, (3) why the data stays out of this PUBLIC repo,
(4) why you build against the schema summary and synthetic fixtures, not the real files. If any is wrong, stop.

## 1. David's ruling (2026-10-23)
All classification and tagging, wherever it lives (Excel, programs, loose files), is gathered into David OS:
the existing `03_CLASSIFY` layer. It already has `00_SHARED/TAG_TAXONOMY_v0.4.md`, `taxonomy_validator.py`,
and `02_CLASSIFICATION` (engines, harness, `classify_standing.db`: 10 engines, 51 events, 6,048 predictions).

## 2. What was gathered (copy-first, done 2026-10-23, on David's machine)
Real files are in `.data/classification/` (git-ignored; you cannot see them). Their shapes, hashes and row
counts are in `03_CLASSIFY/00_SHARED/CLASSIFICATION_SOURCES.json` (tracked). 86 files on disk collapsed to 10 families:
| Family | What it is |
|---|---|
| `LEXICON_MASTER_v2_UNIFIED.xlsx` and `..._JEV_SCORED.xlsx` (Sep 25) | `MASTER_TERM_REGISTRY` 1,797 rows x 20 cols, plus classification axes, Jev spec, shibboleth, six needs, belief ladder |
| `LEXICON_V2.xlsx` (Fruits, 4 identical copies) | 40 sheets: `MASTER_TERM_REGISTRY` 2,235 x 16, semantic buckets, `SI_*` schema sheets, `BFP_DG_*`, `NAMING_TAXONOMY`, `LAW_KEYWORDS`, `ME_VARS` |
| `lexicons_master_enhanced.xlsx` | 10 copies, **2 versions** (Jun 15 x9, Jun 22 x1); same sheets as the first half of `LEXICON_V2` |
| `theophysics_cross_domain_lexicon.xlsx` | coherence / discoherence master and flat lists, 4,839-row semantic buckets |
| `typed-canon-reclassification.json/.csv` | 191 canon items typed (new_type, logical_force, domain, depends_on, lean_kind, risk_level...); 29 and 27 identical copies |
| `03_AXIOMS_192_FULL_CLASSIFICATION_CATALOG.csv` | 192 axioms (id, label, mode, classification, status, root anchor, decision) |
| `02_ALL_CLASSIFICATIONS_AND_LOOKUP_TABLES.csv` | 365 rows: category, code, glyph, meaning, propagation rules |
| `master-equation.rules.json` | drift thresholds and protected markers |
Registered in place, not copied: `classify_standing.db`, the Tagger's `tagger.db` (live DB, open read-only only),
`keyword_registry.json`, `TAG_TAXONOMY_v0.4.md`, and the pipeline's draft `me_vocab.json` (ten laws + ME-CORE/NONE/UNSURE).

## 3. What to build
`engine/classification_registry.py` plus a CLI (`python -m engine.classification_registry build | report`).
- A loader per source. Read CSV/JSON as `utf-8-sig` (the JSON and CSVs start with a BOM). Read xlsx with
  openpyxl. Header rows are not always row 1 (`LEXICON_V2` has a stray typed note in cell A1 of
  `MASTER_TERM_REGISTRY` and `MASTER_README`); detect the header row and report what you detected.
- One SQLite at `.data/classification_registry.sqlite`, rebuilt from the sources each run: `source`
  (family, version hash, role), `term`, `axiom`, `typed_canon`, `law` (from `me_vocab.json`), `code`
  (from the lookup tables), and `conflict`. Every row carries `source_id`, sheet and row so any value can be traced.
- `report` writes `CONFLICTS.md` (same term or id, different class across sources) and `COVERAGE.md`
  (rows per source and per sheet). **Observations only. Nothing is merged, ranked or chosen.**
- Read-only on `.data/classification/` and on `tagger.db` (open with `mode=ro`; never copy or write it).
- `taxonomy_validator.py` gains an option to validate against the registry. Do not change its default behavior.

## 4. Open for David (do NOT decide these)
1. `lexicons_master_enhanced`: two versions exist. 2. Is `LEXICON_MASTER_v2_UNIFIED` the successor of
`LEXICON_V2` and the enhanced file, or a separate registry? Their `MASTER_TERM_REGISTRY` sheets differ
(1,797x20 vs 2,235x16). 3. The pipeline's `paths.json` has no `excel_lexicons` / `excel_fruits` value, so the
stations read the vendor copy of `LEXICON_V2.xlsx`. 4. 76 duplicate copies remain across `C:\theophysics`,
`D:\DONT TOUCH BOOT UP` and others; every path is recorded in the ignored `.data/classification/PROVENANCE.json`
for a later, exact cleanup. **Retiring any copy is out of scope and needs David's yes.**

## 5. Safety and tests
The repo is public: no lexicon rows, no tagger data and no absolute paths in anything tracked. Tests use tiny
synthetic fixtures with the same sheet and column names as the manifest. Acceptance is PENDING on David's
machine: run `build` then `report` against the real `.data/classification/` and show `CONFLICTS.md` counts.
Say "acceptance pending on target machine" in the PR description.

## 6. Branches
David-OSv3: branch from `wip/fis-snapshot-2026-10-23`, draft PR, never push to main or master.

## 7. Out of scope
Moving or deleting files, the Tagger program itself, GUIs, the pipeline stations, any canon decision.
