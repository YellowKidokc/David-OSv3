# David-OSv3 cleanup report — 2026-11-15

## Status and scope

**Partial consolidation, draft review; not ready to merge.** Branch:
`cleanup/v3-consolidation`, based on freshly fetched
`combine/fis-into-david-os` at `6b14728`. No merge performed.

Read the Nov 14 HTML audit and move CSV, then verified the selected changes
against code. The original checkout had unrelated uncommitted edits; work was
isolated in a separate worktree. No source data folders, H:, NAS, vaults,
services, startup jobs or external repository files were modified. Tests used
scratch copies and temporary databases. `work/` is untracked local scratch.

Completed: shared App 160 extraction; one implementation for each migrated FIS
module under `fis/`; duplicate app engine and older renderer snapshot archived;
tested new registry issuance boundary; compatibility entry points; packaging;
selected root cleanup and contributor documentation.

Not completed: conversion of all identity producers, Prediction_GUI integration
and removal of duplicate approval/prediction paths, hub salvage, or retirement
of all legacy tagger launchers. These are explicit stop items below; the new
registry module is not yet the sole live identity source. FIS still contains
its existing approval executor and review endpoints.

## Final top-level folder map

One line per versioned top-level folder (including the unpopulated gitlink):

- `.github/` — repository automation.
- `01_PROFILE/` — drive/folder profile wizard and policy inputs.
- `02_INVENTORY/` — inventory entry points and Stage 1 documentation.
- `03_CLASSIFY/` — MIM validation/review, taxonomies and existing prediction harness; retirement pending.
- `04_ADAPT/` — contract adaptation into MIM cards.
- `05_TOPIC_COLLECTION/` — topic search, selection and reviewed collection.
- `06_FIS_HTML/` — registry scan views and gates; remains a projection consumer pending identity integration.
- `10_FILE_ACTIONS/` — reviewed file-action tools, deep-identify and series analysis.
- `FIS PICS HTML/` — legacy HTML/reference views; sibling GUI's path contract preserved.
- `LEAN 4/` — formal/corpus tools; no authority over identity issuance.
- `LossLess/` — retained older lossless sources; distinct namer not assumed equivalent.
- `Theophysics_Tagger/` — designated Tagger v3 and already salvaged extensions/data.
- `_AUDIT/` — original evidence plus cleanup report and validation summary.
- `_LOSSLESS_SUMMARY/` — current lossless framework launchers and references.
- `_archive/` — dated retired code/artifacts, preserving original paths and reason notes.
- `agents/` — existing agent support code.
- `apps/` — task launchers and shared-contract adapters; classify imports canonical FIS.
- `archive/` — pre-existing archive; retained to preserve provenance.
- `canon_guard/` — downstream canon review and ratification.
- `config/` — application configuration.
- `data/` — existing versioned inputs/outputs; untouched.
- `deploy/` — deployment definitions; nothing deployed.
- `docs/` — operational and design documentation.
- `engine/` — existing registry/inventory, file operations and legacy prediction/tagging consumers; migration pending.
- `file-intelligence-hub` — gitlink at `14f6708`; source unavailable in this snapshot, salvage pending.
- `file-intelligence-system/` — Python compatibility entry points only; existing database path retained.
- `files/` — retained inventory kit and outputs; untouched.
- `fis/` — canonical FIS implementation, including migrated classifier/namer/renderer/scorer.
- `folder_hub/` — folder relay/service, retaining existing store pending reference migration.
- `gui/` — existing desktop launchers/workbenches; legacy tagger retirement pending.
- `hub/` — application API, jobs, nodes and workers.
- `legacy-adapters/` — compatibility routes; FIS classifier now forwards without a hard-coded workstation path.
- `migration/` — existing migration specifications/evidence.
- `pipeline/` — downstream content helpers.
- `rule_brick/` — advisory work evidence and receipts.
- `schemas/` — existing data contracts.
- `scripts/` — operational entry points and migration helpers.
- `services/` — existing service support.
- `shared/` — dependency-light contracts, App 160 namer and tested new ID issuer.
- `tests/` — regression checks, including namer and registry coverage.
- `tools/` — retained utilities/snapshots; old taggers still present pending parity review.

Root `ARCHITECTURE.md` is the short ownership map; `LAUNCH.bat` stays in place.

## Every move

Each row is its own move commit. Other commits extract shared code, wire imports,
add tests or document results; they do not combine independent moves.

| Commit | Original | Destination / treatment |
|---|---|---|
| `0c2f4ba` | `file-intelligence-system/structural_evidence.py` implementation | `fis/structural_evidence.py`; original path becomes a forwarding entry point |
| `626b5b7` | `file-intelligence-system/fis_namer.py` implementation | `fis/fis_namer.py`; original path forwards |
| `154c94c` | `file-intelligence-system/fis_classifier.py` implementation | `fis/fis_classifier.py`; original path forwards |
| `0e2cfed` | `file-intelligence-system/fis_folder_memory.py` implementation | `fis/fis_folder_memory.py`; original path forwards; old DB default retained |
| `9e33cc4` | `apps/classify/src/engines/fis/` | `_archive/2026-11-15/apps/classify/src/engines/fis/`; app imports canonical package |
| `5188c01` | `file-intelligence-system/fis_folder_memory.v2.1.0.py` | `_archive/2026-11-15/file-intelligence-system/fis_folder_memory.v2.1.0.py` |
| `bfcabd0` | `files.zip` | `_archive/2026-11-15/files.zip` |
| `1b35f15` | `scripts.zip` | `_archive/2026-11-15/scripts.zip` |
| `a023957` | `theophysics-read - Shortcut.lnk` | `_archive/2026-11-15/theophysics-read - Shortcut.lnk` |
| `662aa18` | `_BUILD_BRIEF_STAGE1_INVENTORY_REGISTRY.md` | `02_INVENTORY/docs/_BUILD_BRIEF_STAGE1_INVENTORY_REGISTRY.md` |

Every archive has a one-line adjacent `ARCHIVE_NOTE.txt` or
`<filename>.ARCHIVE_NOTE.txt`. No retired source was deleted.

`e97346e` extracts χ signals/scoring, full/short names, coupling pairs, folder
aggregation and lossless addressing into `shared/meq_namer.py`. The two
classifier/namer copies were identical before extraction. The archived app
copies include the extraction imports; the immutable base commit retains the
pre-extraction source for comparison.

The standalone package now ships the shared module, and the root package ships
FIS. Legacy optional integrations remain optional and scoped. Removed dynamic
`__import__` calls and a hard-coded D: path injection. Legacy note-cleanup calls
now preserve retired notes as timestamped `.fisnote.legacy.*.bak` siblings;
the no-delete safety test remains enforced. No cleanup was run on live folders.

## Where the audit differs from this checkout or the task

- Audit was based on `4e36a9a`; pushed snapshot is `6b14728` and contains newer
  FIS/engine work. Runtime counts from the author's Windows checkout are not
  counts for this isolated source checkout.
- Audit recommends Prediction_GUI own predictions and approvals. The explicit
  task supersedes that recommendation: David-OS produces, GUI displays/records.
- Audit describes hub source as available. Git records only an unpopulated
  mode-160000 gitlink, with no `.gitmodules` URL. Its implementation cannot be
  assessed from this checkout; no salvage was invented.
- Existing identity standard/parser uses `SERIES.POSITION.SLUG`; layers also
  derive UUID5, while Stage 1 has W/V records. These are not the requested
  `SERIES.NN_Original-Title` plus UUIDv7. New issuer preserves rather than
  reinterprets these records.
- Previous commit already copied filetagger extensions into Tagger v3. Its
  README explicitly says they are not wired into the core/GUI yet. Copying
  source is not proof that legacy callers can be retired without regression.
- The three-pane root mockups reference `./shared.css`, absent at repo root.
  The CSV treats their move as local; their existing stylesheet dependency
  needs resolution first, so they stay put.
- Audit's duplicate SQLite and multi-GB receipt moves are data moves and
  require WAL/consumer verification. This task forbids touching data folders;
  those items stay put, including the live Simple FIS wrapper.
- Root archives use `_archive/<date>/<original-path>` as explicitly requested,
  rather than the CSV's older `archive/root-packages` proposal.

## Test results

The default Python lacked pytest. The existing environment then stopped on
missing rapidfuzz. Installed declared test/runtime dependencies into local
scratch; used the existing GUI-capable environment with those dependencies.
The actual full baseline ran on an untouched `git archive 6b14728` copy before
comparing to the changed tree.

| Check | Before | After |
|---|---|---|
| Root pytest suite, same interpreter/environment | 268 passed, 17 failed | 297 passed, 17 failed |
| `apps/classify/tests shared/identity`, scratch venv | 12 passed, 4 skipped | 12 passed, 4 skipped |
| Focused namer/registry/FIS/app suite | — | 56 passed, 4 skipped |
| Original vs extracted namer outputs | baseline | identical |
| Standalone wheel build and imports outside repo | — | passed |
| `git diff --check` | — | passed |

No new failures remain. The 17 pre-existing failures cover missing taxonomy
files, Windows launcher/path assumptions, missing rga, missing display, SQLite
FTS configuration, and an outdated exact package-list assertion. They are not
reported as passes. Exact failed test names and comparison counts are in
`CLEANUP_VALIDATION_2026-11-15.json`. Rust binary/old external χ parity tests
skip because their prerequisites are unavailable.

Full-suite command (from each tree):

```sh
QT_QPA_PLATFORM=offscreen \
PYTHONPATH=/workspace/work/david-osv3-consolidation/work/venv/lib/python3.12/site-packages \
/workspace/David-OSv3/.venv/bin/python -m pytest -q
```

Namer regression comparison includes 40 full/short vector inputs, 80 scoring
inputs, four addresses and one folder aggregate. Tests lock substring matching,
repeated-keyword counting, thresholds 0/1/2/3, slot/pair order, sparse vectors,
UNSCORED display fallback, local-time date behavior and folder metadata fallback.
Registry tests cover UUID version/variant, restart stability, concurrent issuance,
immutable original title, bad assignments and preservation of legacy tables.

The import safety test now recognizes relative package imports, the exact shared
namer module and file-scoped optional legacy integrations. Its prohibitions on
deletes, dynamic code/module loading and path injection remain intact.

## Open questions and recommendations — stopped items

1. **How should existing W/V, dotted document, UUID5 and path-hash identities map
   to explicit series/position assignments?** Recommendation: keep the existing
   Stage 1 SQLite as authority; build a reviewed alias/assignment migration and
   switch producers atomically. The tested new issuer is ready as a boundary,
   but adding it does not retire existing issuers. Do not auto-assign a generic
   series or derive document identity from a hash. This item remains unfinished.
2. **May the coordinated change include the external Prediction_GUI repository?**
   Recommendation: a companion PR there should consume David-OS plans and the
   installed shared namer, and submit explicit decisions bound to plan hash/row
   IDs. Then retire its inference runner and redirect David-OS approval views
   to that contract. The current rule forbids edits outside this repository;
   removing working approval paths here alone would break them. No shared GUI
   interface has been claimed as implemented.
3. **Where is file-intelligence-hub's source at gitlink `14f6708`?** Recommendation:
   supply its repository URL or source snapshot, inspect unique capabilities,
   salvage into `fis/`, and archive the remainder in a dedicated commit. Keep
   the gitlink until that review is possible.
4. **Which legacy tagger capabilities/callers must remain supported?**
   Recommendation: verify Tagger v3's salvaged extensions against the existing
   filetagger GUI, `engine/filetagger_core.py`, and `tools/filetagger` before
   redirecting launchers and archiving code. Their CLI/schema differences mean
   a launcher replacement alone is not behavior-preserving. Keep current callers
   in place; no new tagging feature was introduced to bridge an unverified gap.
5. **Which stylesheet is the intended three-pane reference?** Recommendation:
   identify it first, then move all three views together in a dedicated commit.
   Keep Simple FIS at its current sibling-served path until GUI coordination.
6. **When can duplicate databases/large receipts be retired?** Recommendation:
   a separate approved data migration with readers mapped, writers stopped,
   snapshot/WAL verification, and reversible alias/receipt handling. Leave the
   keyword registry where it is until authority/consumers are resolved too.

These stop items are why the PR is a draft. The requested single identity source,
full tagger retirement, hub salvage and completed prediction split must not be
represented as done by this initial consolidation.
