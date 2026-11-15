# David-OSv3 cleanup report — 2026-11-15

## Final scope

Consolidation is implemented on `cleanup/v3-consolidation`, based on
`combine/fis-into-david-os` at `6b14728`. David-OS PR #3 and companion
Prediction_GUI PR #3 must be reviewed together. Neither has been merged.
The initial partial-report status is superseded by this final report.

The follow-up authorized work in Prediction_GUI. Existing uncommitted edits in
David-OS's original checkout were preserved by using a separate worktree. No
live data folders, H:, NAS, vault files, installed services or startup entries
were changed. All source mutation/rollback checks used disposable fixtures.

## What now has one owner

| Job | Owner | Compatibility treatment |
|---|---|---|
| FIS classification/naming/folder rendering | `fis/` | Legacy paths forward; duplicate app engine archived |
| Document/root UUID issuance and explicit IDs | `shared/identity/registry.py` | Other stores carry registry references; old IDs can be aliases |
| Master Equation namer / App 160 | `shared/meq_namer.py` | Same pure implementation used by FIS and GUI backend |
| Document tagging/catalog/watch | `Theophysics_Tagger/tools/tagger3.py` | Legacy catalog/GUI/watch entry points delegate to v3; unique extensions share its home |
| Prediction runner, engines and naming models | `prediction/` | David and GUI harnesses are import/state-path adapters |
| Human decision recording | Prediction_GUI | Exact plan/rows/actor/note receipt; no confidence-based auto approval |
| Guarded execution and recovery | `fis/transaction.py` | Validates receipt/identity/policy, consumes once, journals operations |
| Hub control-plane capabilities | `hub/` | Recovered duplicate gitlink/source archived after comparison |

Internal job keys, hashes, W/V rows and historical IDs remain preserved as local
keys or aliases; they are not newly issued document IDs. Existing low-level
execution tokens, root permissions and explicit legacy batch confirmation are
execution controls, distinct from prediction generation and GUI decision records.

## Final top-level folder map
- `.github/` — repository automation.
- `01_PROFILE/` — drive/folder profile wizard and policy inputs.
- `02_INVENTORY/` — inventory entry points and Stage 1 documentation.
- `03_CLASSIFY/` — MIM validation/review, taxonomies and compatibility imports for canonical prediction.
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
- `engine/` — inventory/file operations, registry-reference consumers and legacy state/CLI adapters.
- `file-intelligence-system/` — Python compatibility entry points only; existing database path retained.
- `files/` — retained inventory kit and outputs; untouched.
- `fis/` — canonical FIS implementation, including migrated classifier/namer/renderer/scorer.
- `folder_hub/` — folder relay/service, retaining existing store pending reference migration.
- `gui/` — existing desktop launchers/workbenches; legacy tagger retirement pending.
- `hub/` — application API, jobs, nodes and workers.
- `legacy-adapters/` — compatibility routes; FIS classifier now forwards without a hard-coded workstation path.
- `migration/` — existing migration specifications/evidence.
- `prediction/` — canonical inference runner/engines, naming learners, series matching and advice.
- `pipeline/` — downstream content helpers.
- `rule_brick/` — advisory work evidence and receipts.
- `schemas/` — existing data contracts.
- `scripts/` — operational entry points and migration helpers.
- `services/` — existing service support.
- `shared/` — identity authority, alias/assignment migration, App 160 and exact review contracts.
- `tests/` — regression checks, including namer and registry coverage.
- `tools/` — utilities and cold snapshots; filetagger entry points forward to Tagger v3-owned implementations.

The ignored `_data/registry.sqlite` is the development identity-state default;
configure one `DAVID_OS_REGISTRY` for installed applications. `work/` is local
scratch and is not part of the PR.

## Every move and archive

The full expanded ledger is `CLEANUP_MOVES_2026-11-15.csv`: repository, commit,
original path, destination and treatment. Each independent source/file move is
its own commit; whole-directory retirements are one logical move. Import adapters
occupy the old paths where required, so Git sometimes reports M+A rather than R.

- Legacy `file-intelligence-system` implementations moved into `fis/`, one
  module per commit. Its old folder-memory snapshot is archived.
- `apps/classify/src/engines/fis/` moved intact into
  `_archive/2026-11-15/apps/classify/src/engines/fis/`.
- Prediction_GUI harness/engines were salvaged into `prediction/`; unique
  David sidecar diagnostics and gate-event adapters were retained too.
  Duplicate harness/engine directories in both repositories are archived.
- GUI advisory and series inference moved into `prediction/advice.py` and
  `prediction/series_registry.py`; GUI modules now present their outputs.
- FIS base/features/frequency/Markov algorithms moved to `prediction/naming/`.
  Duplicate engine algorithms are archived; legacy state paths remain adapters.
- `engine/filetagger_core.py`, both legacy filetagger GUIs, and duplicate
  extension scripts are archived with forwarding entry points. The separate
  daemon is archived; its adapter uses an explicit existing configuration and
  v3's watch implementation. No watcher was launched or installed.
- Unique folder-marker compatibility moved into Tagger v3. Its forced
  `--new-ids` option now refuses the operation because it contradicts immutable
  registry identity; an explicit reviewed assignment/alias is the alternative.
- Recovered file-intelligence-hub gitlink moved to
  `_archive/2026-11-15/file-intelligence-hub`; its exact source tar and reason
  note are adjacent. `HUB_SALVAGE_2026-11-15.json` maps every Python module to
  the already-salvaged `hub/` counterpart. Canonical extensions/guarded
  replacements were kept; legacy destructive deletion was not restored.
- Root ZIPs and workstation shortcut are under `_archive/2026-11-15/` at their
  original relative names. The Stage 1 build brief moved into inventory docs.
- Shared test isolation moved from `tests/conftest.py` to root `conftest.py` so
  app/shared tests also use temporary identity state.

Archive reason notes are adjacent to each retired artifact or inside a retired
folder. Source data, generated corpora, catalogs and receipt folders were not
moved. The source tar is a recovered code snapshot, not a live data migration.

## Identity and storage

Observations receive UUIDv7 references from the configured registry. They have
no public document name until an explicit series/position/original-title
assignment is made. The public format is `SERIES.NN_Original-Title`.

Stage 1 and Folder Hub may retain scoped inventory caches, but their references
come from the same configured authority as FIS, filebrain, χ processing,
classifier exports and Tagger v3. A named registry assignment takes precedence
over descriptive rename proposals. Changing scores/counts are never added to
that identity. Envelopes no longer mint their own document roots.

Legacy sidecar UUIDs remain visible as historical aliases; new sidecars carry
the registry reference. Dotted legacy IDs still parse, and current IDs work
through sidecar/artifact validators. Static legacy ruling fixtures remain
compatibility imports, not a second UUID issuer.

Active locations and location history are separate: a reused former path does
not inherit the moved document's UUID. Planning/apply and rollback check identity
conflicts; journals preserve the reference for restart recovery between the
file move and registry commit.

`python -m shared.identity.migrate MAP.json --db STATE` is dry-run by default.
`--apply` atomically stores explicit assignments, scoped legacy aliases and
review provenance. Conflicts roll back the entire batch. **No live assignment
map was applied**, because the task forbids touching data folders and no reviewed
corpus-wide mapping was supplied. Unknown assignments remain honestly unassigned.

## Prediction and approval handoff

`shared/review.py` is the common plan/receipt contract. FIS browser/CLI decisions
are sent to Prediction_GUI's localhost API, which imports plans into its existing
inbox and records explicit choices before returning receipts. Receipts bind plan
hash, selected row IDs, actor and note. Held rows, tampered plans and edited names
cannot be approved against an old plan. Source edits require a new proposal.

David-OS validates and consumes the receipt before execution; it rejects replay.
The GUI never changes source files. The legacy namer's batch operation now queues
recommendations rather than approving its own predictions, and its human-decision
compatibility function records through the same GUI boundary.

The GUI API opens its ledger without instantiating the inference runner. Its
old ledger path is preserved. The companion dependency file pins the reviewed
David-OS backend; both applications import the same App 160 module.

## Audit corrections and retained uncertainties

- The original audit describes Windows checkout `4e36a9a`; this work starts
  from the later pushed `6b14728` snapshot. Its runtime file/size counts are
  not measurements of this isolated checkout.
- The audit recommends GUI-owned predictions. The explicit task supersedes
  that recommendation: inference belongs to David-OS, decisions to the GUI.
- The initial checkout had only a hub gitlink and no `.gitmodules` URL. The
  exact repository/commit was subsequently recovered and compared; all Python
  module paths already had canonical counterparts under `hub/`.
- Legacy identity validators used dotted IDs and UUID4/5 roots. The new issuer
  uses UUIDv7/current IDs, preserves legacy aliases, and updates validators
  rather than rewriting existing records.
- Tagger salvage had copied extensions without redirecting old callers. Core
  launchers and duplicate extension imports now forward to the v3 owner.
  Existing extension utilities are retained as utilities; no new GUI features
  or external-path exports were added or run.
- Root three-pane mockups reference an absent `shared.css`. Their intended
  stylesheet remains unknown; they stay in place. Simple FIS's sibling-served
  HTML path also stays intact.
- CSV-proposed duplicate SQLite/large-receipt moves would require data/WAL and
  external-consumer checks. They were not performed under the no-data rule.
- Existing registries/vocabularies are not presumed equivalent. The root
  keyword registry and cold snapshots remain where their consumers expect them.

## Validation

| Check | Before cleanup | Final local result |
|---|---|---|
| Root suite on untouched source | 268 passed, 17 failed | 326 passed, 3 skipped, no failures |
| Existing identity/classifier contracts | 12 passed, 4 skipped | 14 passed, 4 skipped |
| Prediction_GUI tests | 6 passed | 9 passed |
| Linux CI full suite with native GUI tests | — | 329 passed, no failures |
| Existing nine-engine GUI smoke | passed | passed with canonical backend |
| Real paired acceptance | — | passed |
| Original vs extracted App 160 outputs | baseline | identical |
| Root + standalone wheel builds | — | passed; isolated imports/resources checked |
| Diff whitespace | — | passed |

The local skips are the three native Tk tests because the shared display is not
usable. CI supplies Xvfb to run them. The separate contract skips are three Rust
binary checks (unbuilt executable) and parity against an unavailable external
legacy χ source. Missing dependencies are not reported as passes.

Baseline fixes include Windows path parsing on Linux, a portable interpreter in
command tests, an up-to-date package-discovery assertion, explicit synthetic
closed-vocabulary fixtures instead of private C: files, and declared test/native
search prerequisites. Production taxonomies were not fabricated or changed.
The clean CI runner exposed additional native Qt/search/PDF prerequisites; the
workflow now installs them explicitly.

The paired acceptance uses a real localhost GUI API and temporary databases:
Stage 1 inventory → registry assignment → Tagger v3 → FIS prediction → explicit
GUI receipt → restart → apply → replay rejection → byte-for-byte rollback.
Additional tests cover stale/edited/held proposals, alias conflicts and atomic
migration rollback, reused paths, registry conflicts before mutation, and a
process interruption between the file move and identity update.

App 160 comparison covers 40 full/short vector inputs, 80 scoring inputs,
four addresses and a folder aggregate. Tests retain scoring boundaries,
substring/repeated-keyword behavior, slot/pair order, UNSCORED and folder/date
fallbacks. No new inference model or source-changing feature was introduced.

Machine-readable results are in `CLEANUP_VALIDATION_2026-11-15.json`. The PR
contains Linux full/paired checks plus the existing Windows FIS safety checks;
Prediction_GUI has its own backend-pin/unit/smoke workflow. CI status is also
visible on the linked PRs; no merge was performed.

## Operational questions for David

1. **Which real documents receive which series/positions?** Recommendation:
   review an explicit assignment map, including scoped aliases for repeated W/V
   keys, and run the dry-run importer before any approved data migration.
   Code migration is implemented; live corpus conversion is intentionally not run.
2. **Which residents/shortcuts should be appointed after deployment?**
   Recommendation: use the preserved launch paths, point every process at one
   registry, install the paired backend pin, and review explicit watcher roots.
   No startup setting or live resident was inspected or changed here. The retired daemon's separate telemetry files are not rewritten; use v3's status/output when deploying.
3. **What is the intended stylesheet for the three-pane mockups?**
   Recommendation: identify it before moving the views together.
4. **When may old catalogs, duplicate SQLite snapshots and large receipts move?**
   Recommendation: a separate data migration with writers stopped, snapshot/WAL
   hashes, consumer mapping and reversible provenance. Keep them untouched now.

These are deployment/data or unresolved-reference decisions, not permission
requests for the completed code consolidation. PRs remain unmerged for review.
