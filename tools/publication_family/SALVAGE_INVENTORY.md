# David-OS publication-tool salvage inventory

Reviewed source:

`\\192.168.2.50\g_github\D_DRIVE_FULL\GitHub\David-OS\file-intelligence-system`

Review date: 2026-08-25.

## Promoted now

| Earlier tool | v3 location | Distinct retained capability | Validation |
|---|---|---|---|
| `fis_near_dup.py` | `near_duplicate_scan.py` | SHA-256 duplicates, shell-stripped MinHash/LSH similarity, inferred article families, presentation-richness comparison | Compile/help and local smoke passed |
| `dont_touch_html_dup_report.py` | `format_family_report.py` | Named Markdown/HTML/Canon bucket comparison, normalized body hashes, same-stem Jaccard, missing-format slots | Compile and 11-file local smoke passed; unsafe nested output rejected |

Both tools require explicit source roots and write reports outside the source
corpus. Neither tool authorizes a move, rename, archive, deletion, or canonical
selection.

## Preserve as reference; adapt only behind a separate task

| Earlier tool | Useful material | Reason not promoted wholesale |
|---|---|---|
| `lossless_packer.py`, `lossless_reader.py`, `lossless_nse.py` | Exact-byte packets, SHA-256 verification, reconstruction, compact derived index | Multi-file subsystem with write/reconstruct modes; needs an isolated recovery-contract audit and tests |
| `fis_visualizer.py`, `fis_vector_space.py` | Offline Plotly cluster map and corpus-vector visualization | Depends on the older database/schema and theological scoring model; visualization is not evidence or canon authority |
| `fis_search.py` | Simple read-only search UI over folder-memory database | v3 already has search/API surfaces; old Flask dependency is absent |
| `fis_dup_heuristic.py` | Exact/near duplicate capsule and near-canon review hints | Coupled to old sidecars and status ladder; core duplicate logic is already retained more safely |
| `fis_meq_graph.py` | Master Equation relationship graph ideas | Must preserve nine-coordinate canon and keep `C_W` as wrapper; old graph assumptions require a separate semantic audit |
| `theophysics_taxonomy.py` | Historical classification vocabulary | Useful as migration/reference data, not automatically authoritative current taxonomy |

## Do not reactivate directly

| Earlier tool | Reason |
|---|---|
| `fis_daemon.py`, `fis_folder_daemon.py` | Auto-discovers roots and writes status/config/sidecars; overlaps v3 watchers and violates explicit-target staging |
| `fis_sidecar.py`, `fis_enricher.py` | Writes older sidecar formats and can conflict with current HTML/SQLite and review-gate policies |
| Old `FIS_WORKBENCH.bat` rename stations | Broad multi-root rename behavior; must remain unavailable until universal preflight, preview, approval, receipt, and postflight checks exist |

## Still-useful design fragments

- Keep exact hashes and normalized-content similarity separate.
- Treat format richness as a review signal, never a keeper decision.
- Retain conflicting versions and near-duplicates for human adjudication.
- Make recovery verification a first-class future station before any archive or
  cleanup action.
