# Folder merge pilot

**2026-10-30 broad-scope acceptance: automatic grouping failed.** Shared paper
subsets grouped Browser OS with Skills (1); shared fonts/scripts/styles grouped
Export Html with a different article collection. Discovery found real shared
material, but that is insufficient evidence for whole-folder merge eligibility.
Do not use the automatic pilot runner as an unattended Desktop/OneDrive workflow.
The fourteen explicitly reviewed isolated merges passed preservation checks;
the broader hash pass was stopped, with `STOP_RECEIPT.json` retaining the cases.
The required next design step is a general separation between relationship
discovery and merge eligibility, not per-folder threshold adjustments.

The saved recipe is `config/workflows/folder_merge_desktop_pilot.json`.
Run it with `python -m engine.folder_merge <recipe.json>` from the repository root.
Choose a fresh output directory for each run; an existing output is refused.

This is a scoped pilot runner, not the general Routine Builder implementation.
It reuses `engine.fingerprint.sha256_file` and the existing path write policy.

## Sequence

1. Inventory the explicit, nonoverlapping source roots and hash every regular file.
2. Compare every pair in this small scope, regardless of folder names. Names are
   reported as evidence but do not decide membership.
3. Accept complete exact replicas with at least one nonempty file, or require
   at least three shared nonempty hashes and 60% containment of the
   smaller distinct-hash set. These are provisional pilot thresholds, not
   calibrated probabilities. Every pair within a group must pass; there is no
   transitive chaining. Shared templates can still produce false candidates;
   automated live consolidation requires a reviewed group-selection stage.
4. Rank each discovered group by total logical bytes, using lexical path order
   to resolve ties in this staging-only experiment. The largest supplies the
   initial layout. The actual destination is a separate `MERGED_nn` directory.
5. Copy the union of relative paths using exclusive file creation. Identical
   files at the same path are skipped; different versions use a SHA-256 suffix.
   Existing differing targets and file/directory collisions are blocked.
6. Re-inventory sources and verify destination hashes. Save per-object source
   mappings, conflicts, errors, pair evidence and verification in `report.json`.

`preview` writes the discovery/plan reports without creating merged directories.
`copy_only_pilot` creates isolated merged directories. Neither mode changes or
removes source folders. The merge primitive can rerun against its own output;
the workflow runner uses a fresh run folder for an unambiguous receipt.

## Limits

Only `largest_bytes` and `keep_both` are implemented. Other policy names are
rejected. Links/reparse points and scan failures block affected groups. Metadata
is copied with `copystat`, but streams, ACLs, reference repairs and OneDrive
hydration/sync state are not verified. `verified` means regular-file content
and inventoried directories passed this pilot's checks; it never authorizes
source cleanup. Partial failed copies require a fresh run/review. A process
crash can leave staged copies without a completed receipt. There is no watcher,
scheduler, cleanup action, atomic-copy recovery or production resume contract.

Tests: `python -m pytest tests/test_folder_merge.py -q`.

## Supervised Desktop expansion

`engine.desktop_merge_survey` inventories explicit roots with metadata-only
checkpoints. Name variants and discriminative relative-path/size matches produce
candidate pairs; they do not establish identity. Its dependency/system directory
exclusions are recorded per root, and any root with exclusions or unsupported
objects is held out of whole-folder merging. Loose files directly on Desktop are
outside this folder-level survey.

The 2026-10-30 run lives in `runs/desktop_merge_supervised_20261030`. Its recipe,
metadata checkpoints and `survey.json` retain scope and candidate evidence. The
run-specific `assess.py` hashes supported candidates; an impossible-byte-match
prefilter avoids reading large unrelated same-name folders. Up to eight I/O
workers accelerate small-file hashing; serial and parallel inventory equivalence
has a test. Complete hashes are checkpointed per root for this supervised run;
they are historical evidence, not a trusted unattended cache.

The run-specific `stage.py` accepts explicitly reviewed groups and stages each
in a fresh isolated output, with a 10 GB free-space reserve. Per-group receipts
retain review reasons, copy mappings and final checks. Database WAL families,
backup/transfer copies, pipeline stages and reused asset bundles require separate
role review even when their bytes match. None of these receipts permits cleanup.
