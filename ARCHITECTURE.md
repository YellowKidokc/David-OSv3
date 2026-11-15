# David-OSv3 ownership

`fis/` owns file intelligence. Start with `python -m fis --help`; `fis/service.py`
is the existing scan/proposal boundary, and `fis/transaction.py` is its guarded
executor. `apps/classify` is a classification contract adapter, importing
`fis.fis_classifier`; it no longer carries a second FIS engine. The legacy
folder renderer and compressed-name proposer also live in `fis/`.
`file-intelligence-system/*.py` and `legacy-adapters/fis_classifier.py` are
compatibility entry points, not separate implementations. Existing database
paths remain unchanged; no live data migration has been performed.

`shared/meq_namer.py` owns App 160: ten χ slots, coupling pairs, keyword scoring,
full/short labels, lossless MEQ__/LOSS__ addresses and folder aggregation.
It has no filesystem writes, approval decisions or ID issuance. FIS imports
it directly. Prediction_GUI can import the same module from an installed
David-OS/FIS distribution; its external checkout has not been changed here.
These computed labels are descriptive metadata, not permanent document IDs.

`Theophysics_Tagger/tools/tagger3.py` and `tagger3_gui.py` are the designated
Tagger v3. `ext_filetagger/` already contains salvaged extensions, but their
integration and remaining legacy launchers need verification before retirement.
The smaller FIS facet matcher (`fis/tag.py`) describes scan evidence; it is not
a replacement catalog or a new Tagger v3 service.

## Identity migration boundary

`shared/identity/registry.py:IdentityRegistry` is the issuance boundary for new
`SERIES.NN_Original-Title` IDs plus UUIDv7. It requires an explicit assignment,
keeps titles immutable, and uses the existing Stage 1 `_data/registry.sqlite`
by default (`DAVID_OS_REGISTRY` can select a configured registry). Other
components should store that issued reference. Scores and relation counts are
computed metadata and never part of the permanent ID.

**Migration remains open:** Stage 1 W/V records, legacy document IDs, UUID5
identity envelopes, filebrain/catalog and standalone path hashes still exist.
The new issuer is tested but is not yet wired into those producers. No claim
is made that there is already one identity source. Keep old records and map
aliases explicitly before switching producers; do not infer a series/position
from a hash or rewrite existing names during cleanup.

## Prediction and approval boundary

The required ownership is David-OS produces suggestions; Prediction_GUI renders
them and records explicit approvals. Existing `fis/service.make_plan` provides
plan IDs, hashes, row IDs and advisory preference scores; an approval must bind
to that exact proposal before the guarded executor can apply it.

**Split remains open:** current FIS approval/review endpoints and the external
Prediction_GUI runner/ledger have not been removed. Its checkout is outside
this repository, and removing either side before a coordinated adapter would
break working approval paths. Do not treat a naming-confidence decision as a
human approval or a next-event predictor as a rename-preference learner.

See `_AUDIT/CLEANUP_REPORT_2026-11-15.md` for moves, validation, the submodule
salvage blocker, and the remaining decisions. Retired source lives in
`_archive/2026-11-15/<original-path>` with a reason; data folders stay in place.
