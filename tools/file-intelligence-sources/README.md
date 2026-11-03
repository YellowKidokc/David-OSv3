# File intelligence consolidation

The two boot-folder applications have been collected here as byte-preserved
reference candidates. They are not installed, imported, enabled, or registered at
startup. `manifest.json` records source paths, SHA-256 hashes, copy verification,
Python syntax checks, imports, and files retained at their original locations.
All 47 eligible files were copied, including nested salvaged modules and samples.
None matched the maintained application files byte for byte. That does not mean
all their functionality is missing: similarity and behavior need separate review.
39 data/output files were retained in place; caches and disable receipts were skipped.
Database contents have not been migrated or validated.

Refresh/verify from the repository:

```powershell
python scripts/collect_file_intelligence_sources.py
```

Existing snapshots are never overwritten. A changed source causes verification
to stop so a new version can be preserved separately. Syntax success does not
establish dependency availability, correct behavior, or safe filesystem actions.

## Application boundaries

| Component | Existing home | Role in the combined app |
|---|---|---|
| FIS | `fis/` | Daily entry point, selected roots, background work, review, history and undo |
| Tagging/profiling | `engine/`, `agents/`, snapshots/filetagger | Explainable metadata and optional Theophysics profiles |
| Naming | `fis/naming_helpers.py`, `engine/rename_planner.py` | Candidate names with evidence; explicit review before application |
| Master Equation intake | `engine/master_equation_intake.py`, `gui/master_equation_intake_gui.py` | Independent observe-only corpus intake and receipts |
| Lossless tooling | `_LOSSLESS_SUMMARY/`, `docs/FIS_TEMPLATE_v2.1.0/` | Source-linked derivatives, splitting and vial preparation; needs adapter review |
| David-OS | repository root | Shared home for applications that can still run independently |

This is the proposed consolidation direction, not a claim that these components
already share a working pipeline. Keep FIS independently installable. Add optional
adapters around pure classification/proposal functions instead of importing old
daemons or coupling FIS to the hub, an API provider, or a NAS.

## Findings from selected source inspection

- Legacy `FIS/fis_namer.py` uses confidence-based auto-approval and teaches its
  preference engine from those approvals. Reuse naming vocabulary only after
  separating proposal generation from that behavior. Current FIS review remains
  the application boundary for approved mutations.
- `filetagger/filetagger_chi_v2.py` inserts the old FIS folder into `sys.path` and
  imports `chi_classifier`. A candidate module is preserved under
  `filetagger/salvaged/chi_classifier.py`; its API compatibility is unverified.
- `FIS/FIS_NAMING_SPEC.md` and `FIS/fis_namer.py` describe different naming
  conventions and domain mappings. Preserve both as historical sources; do not
  silently choose or migrate a schema.
- `_LOSSLESS_SUMMARY/lossless-tools/lossless-tools/lossless.py` calls DeepSeek,
  reads text with replacement decoding, and describes moving originals into
  `done/`. This requires a copy-only, hash-linked adapter before daily FIS use.
  Model-generated summaries need semantic review; the name "lossless" alone
  does not establish information preservation.
- The repository already has substantial uncommitted FIS and vocabulary work.
  This collection does not overwrite or promote those changes.

## Remaining implementation

1. Compare candidate functions and dependencies with current implementations;
   record which behavior is useful and which is already covered.
2. Extract selected pure tag/profile functions behind optional adapters, with
   source attribution and representative input/output checks.
3. Agree on naming fields and retain original names and rejected/corrected
   proposals. Profile scores describe this framework's classification, not an
   independent verification of theological or scientific truth.
4. Adapt lossless processing to preserve original bytes and source spans, write
   derivatives separately, and report unsupported/truncated content explicitly.
5. Join approved adapters into FIS review and test scan, proposal, apply, undo,
   background notifications, and independent application launches.

The sources are collected and verified. Unified tagging, naming and lossless
execution, database migration, and a new combined interface remain unfinished.
