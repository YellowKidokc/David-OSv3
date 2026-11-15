# David-OSv3: who owns what

- **FIS — `fis/`:** scan, classify, generate proposals, folder views, guarded
  execution and rollback. `apps/classify` exports contracts from this owner.
  `file-intelligence-system/` contains forwarding entry points.
- **Identity — `shared/identity/registry.py`:** the only document/root UUID
  issuer. Configure **one `DAVID_OS_REGISTRY`** for every application. The
  development default is `_data/registry.sqlite`; installed deployments should
  set an explicit owned state path. Other SQLite stores are inventories,
  caches, projections or execution/review journals, not identity authorities.
- **App 160 — `shared/meq_namer.py`:** pure χ scoring, full/short names, ten
  slots/pairs, MEQ__/LOSS__ addressing and folder aggregation. FIS and the
  installed Prediction_GUI backend import this same module.
- **Tagger — `Theophysics_Tagger/tools/tagger3.py`:** the supported document
  tagger/catalog and watcher. Unique extensions live under `ext_filetagger/`;
  older catalog/GUI/extension launch paths forward here. `tagger2.py` remains
  v3's implementation dependency. FIS facets and descriptive name tags are
  evidence adapters, not another catalog authority.
- **Prediction — `prediction/`:** David-OS owns event inference, engines,
  scoring, rename-preference algorithms, series matching and advice. Older
  harness/preference imports are adapters. Prediction_GUI owns presentation
  and the durable record of explicit human choices.
- **Control plane — `hub/`:** jobs, nodes, memory and related APIs. The old
  file-intelligence-hub source already had counterparts here; its exact source
  and gitlink are archived, with a comparison receipt.

## Identity flow

An observation receives a registry-issued UUIDv7. It stays **unassigned** until
an explicit series, two-digit position and original title are supplied. The
issued public name is `SERIES.NN_Original-Title`; neither classifiers nor GUI
clients invent one. An assigned ID overrides descriptive rename suggestions.
Scores and relation counts remain computed metadata.

Inventory, FIS, filebrain, classification exports and Tagger v3 store registry
references. Existing W/V keys, content hashes and historical sidecar IDs remain
local record keys or legacy aliases; they are not replacement permanent IDs.
Envelopes require a supplied root instead of minting one.

Active locations and location history are separate. A verified rename transfers
the location while retaining its history; a new file at the old path gets a new
reference. The executor journals the registry reference so restart/rollback can
recover even between the file move and registry update.

`python -m shared.identity.migrate assignments.json --db PATH` validates an
explicit map without writing. `--apply` applies assignments/aliases atomically
and records provenance. Conflicting aliases fail instead of merging identities.
**No live corpus assignments or database migration were run during cleanup.**

## Proposal → approval → execution

FIS produces an immutable plan. `shared/review.py` binds a decision to the exact
plan hash, selected row IDs, actor and note. Prediction_GUI renders that plan in
its existing inbox and records the choice before returning a receipt. Edited
names need a new David-OS plan; held rows cannot be approved.

The FIS browser/CLI send decisions to `PREDICTION_GUI_URL` (default localhost
port 2831). David-OS validates the receipt, records its consumption, then calls
its guarded executor. A receipt cannot be replayed. Prediction_GUI never moves
source files and never turns confidence into automatic approval. The legacy
namer batch now queues recommendations too. Executor tokens, root policies and
HTML-only crawler permissions are execution controls, not competing predictors.

Install the paired Prediction_GUI dependency pin before using the new handoff.
The supported roots/launch paths and pre-existing data locations are retained;
no resident was started or installed. Retirement uses
`_archive/2026-11-15/<original-path>` with a reason note. See the cleanup report
and move CSV under `_AUDIT/` for evidence and remaining operational decisions.
