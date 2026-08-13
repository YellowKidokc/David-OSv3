# File Intelligence System (David-OS)

This is the single container for the file intelligence system.
**This README describes what is ACTUALLY on disk as of 2026-07-21.**
(The previous README described a `segments/` layout that was never built —
that layout is now the migration TARGET; see ARCHITECTURE-AND-GAPS.md.)

## File-action authority (unchanged, binding)

This system observes and proposes. Human approval is recorded in the Excel
`MovePlan` workbook, and `..\engine\excel_actions` is the separate executor.
The workbook and one-click preview/execute launchers live in
`..\tools\excel-file-mover`.

## What is actually here — use this table

| Folder / file | What it is | Status |
|---|---|---|
| `fis_cross_folder_scan.py` | Structural fingerprint scanner (SHA-256 + domain vector + cosine). Proven at 41k+ files. Used by the 2026-07-21 corpus gap scan. | **CANONICAL — working** |
| `fis_near_dup.py` | Near-duplicate + family scanner (fine-grained). Second stage after the coarse scan. | **CANONICAL — working** |
| `fis_intake_router.py` | Repeatable intake router. | **CANONICAL — working** |
| `file-intelligence-system-master/` | The full FIS product: NLP classify, rename, learn-from-corrections, Postgres-backed intelligence layer. The "big system". | CANONICAL — the future core |
| `continuous-scanner/` | Low-resource continuous scan monitor (CORTEX flow). Has the caching/watch loop the root scanners lack. | CANONICAL — not yet wired to the root scanners |
| `watchers/global-watcher/` | Global watcher: discovers files/folders, emits inspect jobs to `jobs/incoming`. | CANONICAL — working |
| `1files/` | Chi-dashboard prototype (CHI_BUILD_SPEC + server.py + index.html). | PROTOTYPE |
| `unified-system/` | Launch + wiring NOTES only (no code). Documents the legacy-fis vs fihub-source choice. | DOCS |
| `Local-File-Organizer-main/` | Third-party open-source project (vendored for reference). NOT David's code. | VENDORED — reference only |
| `organize/` | Third-party "organize" rule-based file automation tool (vendored). NOT David's code. | VENDORED — reference only |
| `cross-folder-scan-report.json` | Output of a prior 41,280-file scan. | ARTIFACT |
| `_fis_cache/` (created by gap scan wrapper) | mtime-keyed fingerprint cache. | ARTIFACT |

## The one dangerous fact

Live David-OS code imports FIS modules from OUTSIDE this folder:

- `engine\cluster_engine.py` -> `fis_near_dup` (here — fine)
- `engine\tagger.py` -> `fis_namer` (**lives in `..\_salvage_boot_up\FIS\`**)
- `tagger\filetagger_chi_v2.py` -> `fis_classifier` (**also `_salvage_boot_up`**)

Production code depends on a salvage folder. Fixing this is Phase 1 of the
migration plan — do not delete `_salvage_boot_up` until it's done.

## Quick start (today, as-is)

- Corpus gap analysis: the wrapper lives at
  `C:\Users\David\Desktop\FTP AI Work Packets 2026-07-21\00_CONTROL_BOARD\fis_corpus_gap_scan.py`
  (imports `fis_cross_folder_scan` from here; adds caching + progress +
  per-donor selection; Excel export via `gap_report_to_excel.py` beside it).
- Fine-grained duplicate families: `python fis_near_dup.py`
- Full product (classify/rename/learn): see `file-intelligence-system-master/README.md`

## Where this is going

Target structure, gap list, migration phases, and productization notes:
**ARCHITECTURE-AND-GAPS.md** (this folder).
