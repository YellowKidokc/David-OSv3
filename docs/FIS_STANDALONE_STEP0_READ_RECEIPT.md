# FIS standalone: Step 0 read receipt and proposed boundary

Date: 2026-10-25. Review only; implementation awaits David's approval as required by `docs/BUILD_PROMPT_FIS_STANDALONE.md`, STEP 0: "Stop for David's approval."

Created `fis-standalone` from the checked-out `wip/fis-snapshot-2026-10-23`. Existing untracked files were preserved. No scans, APIs, rename/apply/undo commands, source moves, or deletions were run. This receipt and its inventory are the only new review artifacts. No acceptance or runtime test pass is claimed.

## What exists and overlaps

| Area | Existing responsibility | Reuse decision |
|---|---|---|
| `03_CLASSIFY/00_SHARED` | v0.4 closed tag vocabulary, card validation, source lookup, DeepSeek triage and notification helpers | Retain validator and explicit taxonomy version; extract the theological vocabulary into an optional pack. Provider and notification code stay outside core. |
| `03_CLASSIFY/01_SIDECARS` | Generates the human classification report from navigation cards | Reuse reporting concepts and standing validation. Generated report records 51 cards with no Part A tags; that is a historical report, not a current corpus census. |
| `03_CLASSIFY/02_CLASSIFICATION` | Vendored prediction harness, independent event/score ledgers, engines, review UI, clipboard/Chrome/card adapters | Keep deterministic suggestions optional. This is not a completed v0.4 content tagger. Browser and clipboard harvesters are separate intake integrations. |
| `03_CLASSIFY/03_RENAMING` | Hybrid readable filename proposals, confidence/reasons, duplicate/collision detection, GUI approval, CSV ledger, link backups and undo | Best existing mutation foundation, after gate and undo repairs. Prefer configured current hybrid naming over older codes-only fallback. |
| `03_CLASSIFY/ZZZ_DELETE` | Older taxonomy, validator/review backups, cards and Prediction_GUI git bundle | Preserve as historical material; do not execute or delete. Old README permission to delete is superseded by the build prompt. |
| `03_CLASSIFY/*.bat` | Review/report/validate/rename/prediction/setup and harvest launchers | Replace entry points only after standalone commands work. Remove drive/NAS defaults and reliance on sibling-stage Python paths. Setup installs ML extras; not required for offline core. |
| `file-intelligence-system/fis_classifier.py` | Folder shape, document type, domain, chi/law/fruit signals, structure, safe-action suggestions, optional Claude fallback | Reuse generic structural features. Move theological signals to pack; provider output cannot authorize filesystem work. |
| `fis_namer.py` | Filename codes, taxonomy integration, preferences and enrichment, approval score thresholds | Reuse pure naming functions; optional imports and score-based approval must not become mutation authority. |
| `fis_folder_memory.py` and `.v2.1.0.py` | Folder/file SQLite records, SHA-256, keywords, naming proposals, folder HTML/file dossiers, sidecar rendering and AI enrichment | Reuse selected renderer/index routines, not the monolithic scan entry point. Current and versioned copies overlap; preserve both pending parity checks. |
| `structural_evidence.py` | Evidence/structure signals consumed by classification and search | Candidate shared deterministic evidence module. |
| `engine/inventory_scan.py`, tagger, classifier, naming, DB, reports | Another scan-to-proposal pipeline with bare sibling imports and preferences | Extract reusable functions; do not wrap `engine` and call the result independent. |
| `engine/understand.py` | Inventory/SQLite observations and inferences, registry-aware folder understanding, symptoms, optional Ollama escalation | Reuse observation/inference separation and inventory models. Folder registry and provider state must become injected configuration. |
| `engine/symptoms/` | Structural, content, temporal, naming, infrastructure and research diagnostics with evidence/severity | Reuse detectors selectively; infrastructure subprocess probes are optional diagnostics. |
| `engine/path_write_policy.py` | Process-local protected roots; global generated-fisnote disable; drive/repository exclusions | Preserve protections as explicit portable policy. Current policy conflicts with requested sidecar output and cannot simply be bypassed. |
| `engine/flatten_dedupe.py` | Normalized-text exact grouping, near-duplicate review, keeper rules, reports and optional output copies | Analysis extra only. Its normalized hash is not byte identity. Never turn keeper ranking into deletion. |
| `engine/quality_score.py` | Explainable text/markup structure score | Optional deterministic report signal; no truth/authority ruling. |
| `engine/term_closure.py` | Selected-root topic candidates, SHA-256 grouping and keeper proposals | Optional report/planner; imports fingerprint and extractor from engine. |
| `engine/gate.py` plus profile registry and rule JSON | Ranked rule stack, hard blocks, approval floors, ASK, PREVIEW and ALLOW | Extract gate together with portable profile parsing and all required rule data. Preserve fail-closed behavior from 19cd17e. |
| `gui/fis_control_surface.py` | Small stdlib scope/preview model; only available non-source-mutating actions cross its apply filter | Best reusable scope model; it is not a rename approval executor. Remove NAS default. |
| `gui/fis_scanner_gui.py` | PySide6 scanner, SQLite and engine helpers, operations-panel integration | Reuse progress/results concepts; avoid requiring Qt for core. Hash-keyed records collapse duplicate locations per workbench documentation. |
| `gui/filetagger_gui.py` | Tk wrapper launching `engine/filetagger_core.py` in subprocess | Reuse simple local GUI approach, change entry point to package CLI/API. |
| `gui/fis_search_workbench.py` | Registry/FTS search plus hub-memory/cache/folder writes | Reuse local search independently; hub writes become a separately enabled integration. |
| `agents/filetagger.py`, `agents/foldertagger.py` | File extraction/keyword/catalog work; folder metadata marker generation | Reconcile MD5/quick fingerprints with SHA-256; preserve imported markers and their provenance. |
| `tools/fis` and `tools/fis-intelligence` | Copied HTML indexing/search/MCP and Rust read-only kernel | Prefer consolidated `tools/fis-intelligence` lineage; preserve copy receipts/originals. Rust BLAKE3 is a different algorithm from Python SHA-256. MCP/Cargo are optional integrations. |
| `docs/FIS_TEMPLATE_v2.1.0` | Versioned renderer/reference HTML and lossless splitter | Reference and compatibility fixtures; not another runtime pipeline. |

## Documents and formats

Read the requested architectural/method documents. `ARCHITECTURE.md` describes the broader historical hub including Top-of-Mind, workers and services; it is not the independent FIS boundary. `SCHEMA.md` is an LLM wiki exploration schema with a separate vault/SQLite system, not a FIS file-index schema. Do not inherit its research runner protocol.

The v0.4 taxonomy separates content tags, epistemic roles, subjects, standing and file lifecycle. Its current physical naming rule delegates precedence to `03_RENAMING/rename_rules.yaml`; card titles and source filenames have distinct roles. Existing taggers still contain older tag/code vocabularies. Mapping and UNKNOWN handling are required, not silently equating the schemes.

Sampled actual `.fisnote` files in `file-intelligence-system`, `engine`, `gui`, and the HTML tool: these use YAML frontmatter `folder-index.v1` plus Markdown, carrying folder id, class, confidence, allowed actions and suggested name. They do not prove file-level history support. Separately, renderer code defines `<source filename>.fisnote`, `file-memory.v2`, an HTML metadata comment with source path/fingerprint and a Markdown field table. It does not yet supply the full requested per-stage evidence/run/undo contract. Other existing layers are `mim.v1` navigation cards, `canon_status` JSON, `.fmeta/.chi` and evidence `.sidecar`; keep these distinct and import with provenance. Actual per-file `file-memory.v2` samples were not established in this review.

`FIS_UNDERSTAND_PIPELINE.md` requires observations, inferences, judgments and authorization to remain distinct. `INDEPENDENT_WORKBENCHES.md` requires both content objects and path-specific instances: a shared hash must not erase duplicate locations. The folder reporting method requires bounded scope, visible exclusions and written reasons.

## External ties and independence plan

The appended import inventory lists every non-stdlib import found by AST in the reviewed Python scope, including function-local and try/except imports. Some are internal siblings to move into `fis`; others are third-party extras. The operational appendix adds path injection, absolute roots, URLs, subprocesses and deletion call sites. This is static evidence, not a claim that arbitrary dynamic/plugin execution has been exhaustively resolved. Inventory hashes record exact reviewed bytes.

Direct boundary crossings include:

- Renamer: `gate`, `ledger` from injected engine path and `hub.config.folder_profiles.FolderProfileRegistry`; repository-level rules/profile files and ledger storage.
- Namer: optional `theophysics_taxonomy`, `fis_preference_engine`, `fis_enricher`, whose availability changes behavior.
- Folder renderer: absolute David-OS engine path then `smart_tagger`; Ollama endpoint and master-equation-specific identities.
- Scanner GUI: engine `tagger`, `text_extractor`, `fingerprint`, `gui.fis_control_surface`, and `gui.operations_panel`; filetagger GUI starts an engine script.
- Search workbench: `hub.storage.db`, `memory_repo`, `desktop_file_cache_repo`, `folder_repo`, `FIHUB_DB_PATH` and hub database schema.
- Engine pipeline: bare `config`/tagger/classifier/preference imports, shared system directories created at import, external reference catalog/lexicon workbook and optional recommenders checkout. Term closure imports `engine.fingerprint` and `engine.text_extractor`.
- Classification stage: shared/harness sys.path modifications, optional `PREDICTION_GUI` override, source-paper/NAS references, provider credentials/cache, Chrome and Ditto adapters.
- Network/provider ties: automatic low-confidence Claude fallback when a key is present, DeepSeek triage, explicit Ollama enrichment, NLTK corpus download paths. Explicit provider enablement must replace ambient-key activation.
- Tool extras: BeautifulSoup, MCP server, Cargo/Rust crates and historical AnythingLLM/Chat2DB connection instructions. No direct Forge Python import was found in this scope; absence of a direct import does not establish independence from all runtime integrations.

Proposed core dependency allowlist: Python standard library plus PyYAML (existing rename configuration). Optional extraction extras: pypdf and python-docx; optional HTML parsing: beautifulsoup4. ML, MCP, Qt, workbook exports and AI providers are separate extras; none imported by default. Offline means no sockets, model downloads, pip/Cargo execution or service startup during core operations.

## Safety findings before extraction

1. `fis_folder_memory.py` contains `cleanup_stale_file_notes` and `wipe_existing_fisnotes` calling unlink; existing HTML-only paths must not be reused as no-delete standalone behavior. Preserve/move artifacts to run quarantine instead.
2. Renamer `apply` blocks BLOCK/DROP and requires override for ASK, but PREVIEW falls through to rename. The new executor must enforce a positive approval bound to the exact plan and refuse preview-only mutations. Never interpret confidence as David's approval.
3. Renamer checks SHA-256 before apply, but `undo_run` restores link backups and renames without checking current bytes against expected post-apply state. It can overwrite post-apply edits through backup restore. Require conflict detection before any restore.
4. Renamer logs after mutations and link rewrites; interruption can leave changes ahead of ledger. Require durable pre-operation records and recovery states, unique run ids, idempotent undo and partial-failure recovery.
5. Gate load errors currently yield ASK before hard-safety checks. The standalone adapter must not permit malformed configuration plus an override to bypass an independently established hard block.
6. Generated `.fisnote` writes are currently globally disabled by path policy. The requested new sidecar writer needs an explicit reviewed policy and safe out-of-source dry runs, preserving protected roots.
7. Undo must preserve pre-existing sidecar bytes and metadata, not merely remove every matching sidecar. Newly generated sidecars can move to run quarantine on undo to satisfy both visible restoration and no deletion.
8. Byte hashes, normalized text fingerprints, MD5/quick hashes and BLAKE3 are distinct. SHA-256 content objects plus separate instance ids preserve all duplicate paths. Do not infer an ambiguous moved duplicate from hash alone.
9. Source/card links, old sidecars, collision/case-only names, moved files, junction escape and edited-after-plan files require explicit handling. The historical 279-file undo claim in the renamer README was not rerun here.

## Proposed package

```text
fis/
  __init__.py, __main__.py
  scan.py             # bounded inventory, extraction and byte fingerprints
  tag.py              # v0.4 vocabulary mapping and per-tag evidence
  classify.py         # structural class, confidence, evidence, UNKNOWN
  rename.py           # pure proposals, current configured filename grammar
  sidecar.py          # versioned read/write adapters and legacy preservation
  gate.py             # gate/profile parsing with packaged rule data
  index.py            # content objects, path instances, plans, run history
  report.py           # explainable tables, HTML and local search
  cli.py              # scan, plan, apply, undo, report, search
  transaction.py      # preflight, durable ledger, quarantine, conflict-safe undo
  ui.py               # simple Tk approval table using same plan/executor API
  providers/          # disabled default provider interface
config/fis/
  defaults.json
  rules/              # packaged safety requirements
  rulepacks/          # opt-in theophysics/axiom/master-equation vocabulary
```

Consolidate pure functions rather than wrap forbidden engine or hub imports. Retain current entry points until compatibility is verified; archive superseded code only in a later approved step. Approval must identify plan hash, selected rows/scope and source hashes. Every stage records rule ids, evidence origin/span, confidence and rulepack version.

## Acceptance to implement after approval

Use an explicitly selected copy of a real messy folder. Capture relative paths, bytes/SHA-256, relevant timestamps and all pre-existing sidecar bytes before scan. Confirm default scan/plan leaves this snapshot unchanged. Approve the immutable plan; apply; verify ledger and post-state; undo; compare full path membership and byte hashes, restore pre-existing sidecars and ensure no unexpected source-tree artifacts remain. Keep run evidence/quarantine outside the source tree. Test duplicate instances, collisions, existing sidecars, partial apply, crash recovery and edits made after apply. A passing round trip is required evidence for this workflow, not a universal guarantee for arbitrary drives.

Independence test must resolve imports against the allowlist, reject hub/engine/services/Forge/Top-of-Mind and bare local aliases, inspect relative and dynamic imports/path injection, and exercise package import/CLI from an isolated installation with the repo unavailable. An offline test should deny sockets and verify core commands still work with no credentials/models/services.

STOP: approve this boundary and layout before Step 1. No standalone implementation has begun.

## Complete non-stdlib Python import inventory

| Source | Imported module |
|---|---|
| `03_CLASSIFY/00_SHARED/blind_test_papers.py:20` | `deepseek_triage` |
| `03_CLASSIFY/00_SHARED/blind_test_papers.py:21` | `source_papers` |
| `03_CLASSIFY/01_SIDECARS/sidecar_report.py:23` | `taxonomy_validator` |
| `03_CLASSIFY/01_SIDECARS/sidecar_report.py:24` | `harness.adapters.sidecars` |
| `03_CLASSIFY/02_CLASSIFICATION/engines/_TEMPLATE/engine.py:15` | `harness.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/engines/bandit_mabwiser/engine.py:19` | `harness.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/engines/bandit_mabwiser/engine.py:22` | `mabwiser.mab` |
| `03_CLASSIFY/02_CLASSIFICATION/engines/channel_streak/engine.py:14` | `harness.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/engines/cpt_sequence/engine.py:16` | `harness.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/engines/cpt_sequence/engine.py:19` | `cpt.cpt` |
| `03_CLASSIFY/02_CLASSIFICATION/engines/ensemble_weighted/engine.py:18` | `harness.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/engines/frequency_baseline/engine.py:12` | `harness.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/engines/name_words/engine.py:15` | `harness.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/engines/recency_baseline/engine.py:13` | `harness.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/engines/river_online/engine.py:13` | `harness.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/engines/river_online/engine.py:16` | `river` |
| `03_CLASSIFY/02_CLASSIFICATION/engines/sklearn_context/engine.py:12` | `harness.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/engines/sklearn_context/engine.py:15` | `sklearn.feature_extraction` |
| `03_CLASSIFY/02_CLASSIFICATION/engines/sklearn_context/engine.py:16` | `sklearn.linear_model` |
| `03_CLASSIFY/02_CLASSIFICATION/gui/app.py:22` | `harness.runner` |
| `03_CLASSIFY/02_CLASSIFICATION/gui/app.py:23` | `harness.adapters` |
| `03_CLASSIFY/02_CLASSIFICATION/gui/app.py:26` | `harness.adapters` |
| `03_CLASSIFY/02_CLASSIFICATION/gui/review.py:47` | `deepseek_triage` |
| `03_CLASSIFY/02_CLASSIFICATION/gui/review.py:48` | `notify` |
| `03_CLASSIFY/02_CLASSIFICATION/gui/review.py:49` | `source_papers` |
| `03_CLASSIFY/02_CLASSIFICATION/gui/review.py:50` | `harness.adapters` |
| `03_CLASSIFY/02_CLASSIFICATION/gui/review.py:51` | `harness.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/gui/review.py:52` | `harness.registry` |
| `03_CLASSIFY/02_CLASSIFICATION/gui/review.py:53` | `harness.runner` |
| `03_CLASSIFY/02_CLASSIFICATION/gui/review.py:697` | `sidecar_report` |
| `03_CLASSIFY/02_CLASSIFICATION/harness/adapters/chrome_history.py:24` | `harness.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/harness/adapters/chrome_history.py:68` | `harness.runner` |
| `03_CLASSIFY/02_CLASSIFICATION/harness/adapters/clipboard.py:34` | `harness.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/harness/adapters/clipboard.py:147` | `harness.runner` |
| `03_CLASSIFY/02_CLASSIFICATION/harness/adapters/csv_events.py:14` | `harness.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/harness/adapters/csv_events.py:35` | `harness.runner` |
| `03_CLASSIFY/02_CLASSIFICATION/harness/adapters/gate_events.py:15` | `harness.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/harness/adapters/gate_events.py:55` | `harness.runner` |
| `03_CLASSIFY/02_CLASSIFICATION/harness/adapters/sidecars.py:27` | `harness.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/harness/adapters/sidecars.py:118` | `harness.runner` |
| `03_CLASSIFY/02_CLASSIFICATION/harness/ledger.py:13` | `.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/harness/registry.py:18` | `.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/harness/registry.py:19` | `.ledger` |
| `03_CLASSIFY/02_CLASSIFICATION/harness/runner.py:12` | `.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/harness/runner.py:13` | `.ledger` |
| `03_CLASSIFY/02_CLASSIFICATION/harness/runner.py:14` | `.registry` |
| `03_CLASSIFY/02_CLASSIFICATION/intake/intake.py:24` | `harness.ledger` |
| `03_CLASSIFY/02_CLASSIFICATION/intake/intake.py:25` | `harness.runner` |
| `03_CLASSIFY/02_CLASSIFICATION/tests/smoke.py:6` | `harness.contract` |
| `03_CLASSIFY/02_CLASSIFICATION/tests/smoke.py:7` | `harness.runner` |
| `03_CLASSIFY/02_CLASSIFICATION/tests/smoke.py:8` | `harness.registry` |
| `03_CLASSIFY/02_CLASSIFICATION/tests/smoke.py:52` | `harness.adapters` |
| `03_CLASSIFY/03_RENAMING/rename_engine.py:26` | `yaml` |
| `03_CLASSIFY/03_RENAMING/rename_engine.py:40` | `gate` |
| `03_CLASSIFY/03_RENAMING/rename_engine.py:41` | `ledger` |
| `03_CLASSIFY/03_RENAMING/rename_engine.py:42` | `hub.config.folder_profiles` |
| `03_CLASSIFY/03_RENAMING/rename_engine.py:371` | `openpyxl` |
| `03_CLASSIFY/03_RENAMING/rename_engine.py:372` | `openpyxl.styles` |
| `03_CLASSIFY/03_RENAMING/renamer_gui.py:21` | `rename_engine` |
| `03_CLASSIFY/03_RENAMING/renamer_gui.py:22` | `notify` |
| `03_CLASSIFY/ZZZ_DELETE/review_py_before_deepseek/review.py:35` | `harness.adapters` |
| `03_CLASSIFY/ZZZ_DELETE/review_py_before_deepseek/review.py:36` | `harness.registry` |
| `03_CLASSIFY/ZZZ_DELETE/review_py_before_deepseek/review.py:37` | `harness.runner` |
| `agents/filetagger.py:91` | `pypdf` |
| `agents/filetagger.py:98` | `docx` |
| `agents/filetagger.py:113` | `yake` |
| `docs/FIS_TEMPLATE_v2.1.0/fis_folder_memory.v2.1.0.py:26` | `fis_namer` |
| `docs/FIS_TEMPLATE_v2.1.0/fis_folder_memory.v2.1.0.py:30` | `fis_classifier` |
| `engine/aggregate_report.py:22` | `.` |
| `engine/aggregate_report.py:23` | `.symptoms` |
| `engine/canon_scan.py:27` | `engine.path_write_policy` |
| `engine/canon_scan.py:30` | `engine.path_write_policy` |
| `engine/category_markov.py:18` | `config` |
| `engine/chi.py:14` | `config` |
| `engine/chi.py:17` | `chi_engine` |
| `engine/chi_engine.py:267` | `openpyxl` |
| `engine/claim_jurisdiction.py:26` | `nltk` |
| `engine/claim_jurisdiction.py:27` | `nltk` |
| `engine/cli.py:26` | `config` |
| `engine/cli.py:27` | `inventory_scan` |
| `engine/cli.py:28` | `report_builder` |
| `engine/cli.py:29` | `metadata_db` |
| `engine/cli.py:77` | `preference_engine` |
| `engine/cli.py:87` | `preference.ensemble` |
| `engine/cli.py:107` | `preference_engine` |
| `engine/cli.py:108` | `ledger` |
| `engine/cluster_engine.py:29` | `config` |
| `engine/cluster_engine.py:30` | `domain_classifier` |
| `engine/cluster_engine.py:31` | `fingerprint` |
| `engine/cluster_engine.py:32` | `tagger` |
| `engine/cluster_engine.py:33` | `text_extractor` |
| `engine/cluster_engine.py:36` | `fis_near_dup` |
| `engine/config.py:56` | `yaml` |
| `engine/domain_classifier.py:16` | `config` |
| `engine/domain_classifier.py:17` | `chi` |
| `engine/enricher.py:30` | `config` |
| `engine/enricher.py:31` | `tagger` |
| `engine/enricher.py:32` | `wordnet_expander` |
| `engine/enricher.py:35` | `sklearn.feature_extraction.text` |
| `engine/enricher.py:36` | `sklearn.metrics.pairwise` |
| `engine/enricher.py:37` | `numpy` |
| `engine/filetagger_core.py:91` | `pypdf` |
| `engine/filetagger_core.py:98` | `docx` |
| `engine/filetagger_core.py:113` | `yake` |
| `engine/flatten_dedupe.py:21` | `fingerprint` |
| `engine/inventory_scan.py:17` | `config` |
| `engine/inventory_scan.py:18` | `fingerprint` |
| `engine/inventory_scan.py:19` | `text_extractor` |
| `engine/inventory_scan.py:20` | `domain_classifier` |
| `engine/inventory_scan.py:21` | `rename_planner` |
| `engine/inventory_scan.py:22` | `metadata_db` |
| `engine/inventory_scan.py:23` | `ledger` |
| `engine/inventory_scan.py:24` | `enricher` |
| `engine/inventory_scan.py:25` | `capability` |
| `engine/inventory_scan.py:26` | `category_markov` |
| `engine/ledger.py:15` | `config` |
| `engine/master_equation_intake.py:19` | `engine.fingerprint` |
| `engine/master_equation_intake.py:20` | `engine.text_extractor` |
| `engine/metadata_db.py:16` | `config` |
| `engine/preference/__init__.py:13` | `.ensemble` |
| `engine/preference/__init__.py:14` | `.base` |
| `engine/preference/ensemble.py:21` | `config` |
| `engine/preference/ensemble.py:22` | `.base` |
| `engine/preference/ensemble.py:23` | `.frequency` |
| `engine/preference/ensemble.py:24` | `.river_engine` |
| `engine/preference/ensemble.py:25` | `.sklearn_gbdt` |
| `engine/preference/ensemble.py:26` | `.vw_engine` |
| `engine/preference/ensemble.py:27` | `.markov_engine` |
| `engine/preference/ensemble.py:28` | `.recommenders_adapter` |
| `engine/preference/features.py:15` | `config` |
| `engine/preference/features.py:24` | `tagger` |
| `engine/preference/frequency.py:13` | `config` |
| `engine/preference/frequency.py:14` | `.base` |
| `engine/preference/frequency.py:15` | `.` |
| `engine/preference/markov_engine.py:19` | `config` |
| `engine/preference/markov_engine.py:20` | `.base` |
| `engine/preference/recommenders_adapter.py:21` | `config` |
| `engine/preference/recommenders_adapter.py:22` | `.base` |
| `engine/preference/recommenders_adapter.py:23` | `.` |
| `engine/preference/recommenders_adapter.py:30` | `lightgbm` |
| `engine/preference/recommenders_adapter.py:37` | `recommenders` |
| `engine/preference/recommenders_adapter.py:70` | `sklearn.feature_extraction` |
| `engine/preference/river_engine.py:11` | `config` |
| `engine/preference/river_engine.py:12` | `.base` |
| `engine/preference/river_engine.py:13` | `.` |
| `engine/preference/river_engine.py:16` | `river` |
| `engine/preference/sklearn_gbdt.py:12` | `config` |
| `engine/preference/sklearn_gbdt.py:13` | `.base` |
| `engine/preference/sklearn_gbdt.py:14` | `.` |
| `engine/preference/sklearn_gbdt.py:17` | `sklearn.ensemble` |
| `engine/preference/sklearn_gbdt.py:18` | `sklearn.feature_extraction` |
| `engine/preference/vw_engine.py:10` | `config` |
| `engine/preference/vw_engine.py:11` | `.base` |
| `engine/preference/vw_engine.py:12` | `.` |
| `engine/preference/vw_engine.py:15` | `vowpalwabbit` |
| `engine/preference/vw_engine.py:19` | `vowpalwabbit` |
| `engine/preference_engine.py:11` | `preference.ensemble` |
| `engine/priority_roots.py:21` | `.` |
| `engine/rename_planner.py:14` | `config` |
| `engine/rename_planner.py:15` | `tagger` |
| `engine/rename_planner.py:16` | `preference_engine` |
| `engine/report_builder.py:19` | `config` |
| `engine/report_builder.py:20` | `metadata_db` |
| `engine/symptoms/__init__.py:3` | `.models` |
| `engine/symptoms/__init__.py:4` | `.structural` |
| `engine/symptoms/__init__.py:5` | `.content` |
| `engine/symptoms/__init__.py:6` | `.temporal` |
| `engine/symptoms/__init__.py:7` | `.infrastructure` |
| `engine/symptoms/__init__.py:8` | `.naming` |
| `engine/symptoms/__init__.py:9` | `.research` |
| `engine/symptoms/_common.py:11` | `.models` |
| `engine/symptoms/content.py:5` | `._common` |
| `engine/symptoms/content.py:6` | `.models` |
| `engine/symptoms/infrastructure.py:4` | `._common` |
| `engine/symptoms/infrastructure.py:5` | `.models` |
| `engine/symptoms/naming.py:3` | `._common` |
| `engine/symptoms/naming.py:4` | `.models` |
| `engine/symptoms/research.py:5` | `._common` |
| `engine/symptoms/research.py:6` | `.models` |
| `engine/symptoms/structural.py:6` | `._common` |
| `engine/symptoms/structural.py:7` | `.models` |
| `engine/symptoms/temporal.py:5` | `._common` |
| `engine/symptoms/temporal.py:6` | `.models` |
| `engine/tagger.py:13` | `config` |
| `engine/term_closure.py:17` | `engine.fingerprint` |
| `engine/term_closure.py:18` | `engine.text_extractor` |
| `engine/text_extractor.py:57` | `pypdf` |
| `engine/text_extractor.py:77` | `docx` |
| `engine/text_extractor.py:60` | `PyPDF2` |
| `engine/understand.py:116` | `yaml` |
| `engine/understand.py:392` | `symptoms` |
| `engine/wordnet_expander.py:17` | `nltk.corpus` |
| `engine/wordnet_expander.py:38` | `nltk` |
| `engine/wordnet_expander_full.py:19` | `nltk.corpus` |
| `engine/wordnet_expander_full.py:180` | `chi_profiles` |
| `file-intelligence-system/fis_classifier.py:93` | `structural_evidence` |
| `file-intelligence-system/fis_classifier.py:906` | `fis_namer` |
| `file-intelligence-system/fis_classifier.py:964` | `pypdf` |
| `file-intelligence-system/fis_classifier.py:971` | `docx` |
| `file-intelligence-system/fis_folder_memory.py:26` | `fis_namer` |
| `file-intelligence-system/fis_folder_memory.py:30` | `fis_classifier` |
| `file-intelligence-system/fis_folder_memory.py:281` | `smart_tagger` |
| `file-intelligence-system/fis_folder_memory.v2.1.0.py:26` | `fis_namer` |
| `file-intelligence-system/fis_folder_memory.v2.1.0.py:30` | `fis_classifier` |
| `file-intelligence-system/fis_namer.py:26` | `theophysics_taxonomy` |
| `file-intelligence-system/fis_namer.py:33` | `fis_preference_engine` |
| `file-intelligence-system/fis_namer.py:40` | `fis_enricher` |
| `gui/fis_scanner_gui.py:32` | `PySide6.QtCore` |
| `gui/fis_scanner_gui.py:33` | `PySide6.QtWidgets` |
| `gui/fis_scanner_gui.py:40` | `PySide6.QtGui` |
| `gui/fis_scanner_gui.py:100` | `gui.fis_control_surface` |
| `gui/fis_scanner_gui.py:43` | `PySide6.QtWebEngineWidgets` |
| `gui/fis_scanner_gui.py:44` | `PySide6.QtWebEngineCore` |
| `gui/fis_scanner_gui.py:72` | `tagger` |
| `gui/fis_scanner_gui.py:79` | `text_extractor` |
| `gui/fis_scanner_gui.py:84` | `fingerprint` |
| `gui/fis_scanner_gui.py:628` | `gui.operations_panel` |
| `gui/fis_search_workbench.py:660` | `hub.storage.db` |
| `gui/fis_search_workbench.py:492` | `fis_classifier` |
| `gui/fis_search_workbench.py:499` | `structural_evidence` |
| `gui/fis_search_workbench.py:510` | `fis_namer` |
| `gui/fis_search_workbench.py:686` | `hub.storage.memory_repo` |
| `gui/fis_search_workbench.py:670` | `hub.storage.memory_repo` |
| `gui/fis_search_workbench.py:674` | `hub.storage.desktop_file_cache_repo` |
| `gui/fis_search_workbench.py:677` | `hub.storage.folder_repo` |
| `tools/fis/FIS-HTML-Intelligence/src/cli.py:7` | `fis_html_index` |
| `tools/fis/FIS-HTML-Intelligence/src/fis_html_index.py:15` | `bs4` |
| `tools/fis/FIS-HTML-Intelligence/src/fis_mcp_server.py:8` | `mcp.server.fastmcp` |
| `tools/fis/FIS-HTML-Intelligence/src/fis_mcp_server.py:10` | `fis_html_index` |
| `tools/fis/FIS-HTML-Intelligence/src/fis_mcp_server.py:11` | `fis_html_index` |
| `tools/fis/FIS-HTML-Intelligence/tests/test_index.py:6` | `fis_html_index` |
| `tools/fis-intelligence/src/cli.py:7` | `fis_html_index` |
| `tools/fis-intelligence/src/fis_html_index.py:15` | `bs4` |
| `tools/fis-intelligence/src/fis_mcp_server.py:8` | `mcp.server.fastmcp` |
| `tools/fis-intelligence/src/fis_mcp_server.py:10` | `fis_html_index` |
| `tools/fis-intelligence/src/fis_mcp_server.py:11` | `fis_html_index` |
| `tools/fis-intelligence/tests/test_index.py:6` | `fis_html_index` |

## Operational boundary call sites

- `03_CLASSIFY/00_SHARED/blind_test_papers.py:19`: `sys.path.insert(0, str(HERE))`
- `03_CLASSIFY/00_SHARED/deepseek_triage.py:22`: `URL = "https://api.deepseek.com/chat/completions"`
- `03_CLASSIFY/00_SHARED/notify.py:39`: `subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS],`
- `03_CLASSIFY/00_SHARED/TAG_TAXONOMY_v0.4.md:2`: `**POF 2828 | 2026-10-13 | supersedes v0.3 (2026-09-14) | the only copy: 'D:\GitHub\David-OSv3\03_CLASSIFY\00_SHARED\TAG_TAXONOMY_v0.4.md'**`
- `03_CLASSIFY/01_SIDECARS/README.md:29`: `| Convergence Tagger v3 | 'C:\Theophysics_Tagger\tools\tagger3.py --write-sidecars --write-folder-markers' | '.fmeta' beside each document, '.folder.fmeta' per folder |`
- `03_CLASSIFY/01_SIDECARS/sidecar_report.py:20`: `sys.path.insert(0, str(HERE.parent / "00_SHARED"))   # taxonomy_validator`
- `03_CLASSIFY/01_SIDECARS/sidecar_report.py:21`: `sys.path.insert(0, os.environ.get("PREDICTION_GUI", str(HERE.parent / "02_CLASSIFICATION")))  # harness`
- `03_CLASSIFY/02_CLASSIFICATION/gui/app.py:20`: `sys.path.insert(0, str(ROOT))`
- `03_CLASSIFY/02_CLASSIFICATION/gui/review.py:20`: `old Prediction_GUI repo (PREDICTION_GUI env var still overrides, default: local).`
- `03_CLASSIFY/02_CLASSIFICATION/gui/review.py:41`: `PGUI = Path(os.environ.get("PREDICTION_GUI", str(ROOT / "02_CLASSIFICATION")))`
- `03_CLASSIFY/02_CLASSIFICATION/gui/review.py:44`: `sys.path.insert(0, str(PGUI))`
- `03_CLASSIFY/02_CLASSIFICATION/gui/review.py:45`: `sys.path.insert(0, str(SHARED))`
- `03_CLASSIFY/02_CLASSIFICATION/gui/review.py:696`: `sys.path.insert(0, str(ROOT / "01_SIDECARS"))`
- `03_CLASSIFY/02_CLASSIFICATION/harness/adapters/chrome_history.py:10`: `python -m harness.adapters.chrome_history "C:\\...\\Profile 2\\History"`
- `03_CLASSIFY/02_CLASSIFICATION/harness/adapters/chrome_history.py:67`: `sys.path.insert(0, str(Path(__file__).resolve().parents[2]))`
- `03_CLASSIFY/02_CLASSIFICATION/harness/adapters/clipboard.py:14`: `python -m harness.adapters.clipboard ditto "D:\\Ditto\\Ditto.db"`
- `03_CLASSIFY/02_CLASSIFICATION/harness/adapters/clipboard.py:66`: `def ollama_topic(text: str, model: str, host: str = "http://localhost:11434") -> str:`
- `03_CLASSIFY/02_CLASSIFICATION/harness/adapters/clipboard.py:146`: `sys.path.insert(0, str(Path(__file__).resolve().parents[2]))`
- `03_CLASSIFY/02_CLASSIFICATION/harness/adapters/csv_events.py:34`: `sys.path.insert(0, str(Path(__file__).resolve().parents[2]))`
- `03_CLASSIFY/02_CLASSIFICATION/harness/adapters/gate_events.py:14`: `sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 02_CLASSIFICATION`
- `03_CLASSIFY/02_CLASSIFICATION/harness/adapters/sidecars.py:117`: `sys.path.insert(0, str(Path(__file__).resolve().parents[2]))`
- `03_CLASSIFY/02_CLASSIFICATION/harness/registry.py:26`: `spec = importlib.util.spec_from_file_location(f"pgui_engine_{py_file.parent.name}", py_file)`
- `03_CLASSIFY/02_CLASSIFICATION/intake/intake.py:22`: `sys.path.insert(0, str(ROOT))`
- `03_CLASSIFY/02_CLASSIFICATION/README.md:33`: `| Convergence Tagger v3 | 'C:\Theophysics_Tagger\' ('START_TAGGER.bat') | Tags documents against the registry; Browse / Tags tabs |`
- `03_CLASSIFY/02_CLASSIFICATION/tests/smoke.py:4`: `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`
- `03_CLASSIFY/02_CLASSIFICATION/tests/smoke.py:53`: `assert [cb.kind_of(t) for t in ("https://x.com/a", "C:\\Users\\d", "a@b.co", "42.5", "def f():\n    return 1", "hello")] == \`
- `03_CLASSIFY/02_CLASSIFICATION/tests/smoke.py:58`: `[(1760000000, "https://a.com", 0, 1760000100), (1760000200, "grp", 1, 0), (1760000300, "", 0, 0)])`
- `03_CLASSIFY/03_RENAMING/README.md:9`: `**'RENAME.bat'** (in '03_CLASSIFY\') opens the Renamer review window on 'S:\PROCESSED', or on any folder dragged onto it.`
- `03_CLASSIFY/03_RENAMING/README.md:26`: `Tested on a copy of 'S:\PROCESSED' (279 files): 156 renamed, no links left pointing at old names, and the undo was byte- and date-identical.`
- `03_CLASSIFY/03_RENAMING/README.md:43`: `| FIS naming spec | 'D:\DONT TOUCH BOOT UP\FIS\FIS_NAMING_SPEC.md' | Folder classes + symptom registry (S01–T04) + file pattern + rename safety rules |`
- `03_CLASSIFY/03_RENAMING/README.md:44`: `| NABLA semantic naming v5.1 | 'D:\DONT TOUCH BOOT UP\stratum pop up\06_engines\classification\prompts\01_NABLA_SEMANTIC_FILE_NAMING_SYSTEM_v5.1.md' | Prompt-based semantic naming system |`
- `03_CLASSIFY/03_RENAMING/rename_engine.py:11`: `python rename_engine.py "S:\\PROCESSED"            print proposals (dry run)`
- `03_CLASSIFY/03_RENAMING/rename_engine.py:38`: `if str(_p) not in sys.path:`
- `03_CLASSIFY/03_RENAMING/rename_engine.py:39`: `sys.path.insert(0, str(_p))`
- `03_CLASSIFY/03_RENAMING/rename_engine.py:395`: `root = Path(sys.argv[1] if len(sys.argv) > 1 else r"S:\PROCESSED")`
- `03_CLASSIFY/03_RENAMING/renamer_gui.py:7`: `python renamer_gui.py ["S:\\PROCESSED"]`
- `03_CLASSIFY/03_RENAMING/renamer_gui.py:19`: `sys.path.insert(0, str(HERE))`
- `03_CLASSIFY/03_RENAMING/renamer_gui.py:20`: `sys.path.insert(0, str(HERE.parent / "00_SHARED"))`
- `03_CLASSIFY/03_RENAMING/renamer_gui.py:32`: `def __init__(self, folder: str = r"S:\PROCESSED"):`
- `03_CLASSIFY/03_RENAMING/renamer_gui.py:306`: `Renamer(sys.argv[1] if len(sys.argv) > 1 else r"S:\PROCESSED").mainloop()`
- `03_CLASSIFY/README.md:29`: `'David-OSv3\engine\', 'C:\Theophysics_Tagger\', Research-Acquisition, the NAS). They're live code`
- `03_CLASSIFY/README.md:35`: `old standalone 'D:\GitHub\Prediction_GUI' repo, which no longer exists on disk (history is on`
- `03_CLASSIFY/README.md:38`: `The 'PREDICTION_GUI' environment variable still overrides the harness location if ever needed.`
- `03_CLASSIFY/RENAME.bat:2`: `rem 03_CLASSIFY - open the Renamer review window (03_RENAMING). Drag a folder onto this file, or it opens S:\PROCESSED.`
- `03_CLASSIFY/RENAME.bat:6`: `python 03_RENAMING\renamer_gui.py "S:\PROCESSED"`
- `03_CLASSIFY/ZZZ_DELETE/review_py_before_deepseek/review.py:33`: `sys.path.insert(0, str(ROOT))`
- `agents/filetagger.py:16`: `python filetagger.py "X:\\folder"`
- `agents/filetagger.py:17`: `python filetagger.py "X:\\folder" --db catalog.db --workers 6`
- `agents/filetagger.py:18`: `python filetagger.py "X:\\folder" --sidecar     # also write .fmeta files`
- `agents/filetagger.py:19`: `python filetagger.py "X:\\folder" --quickhash   # faster id hash, huge files`
- `agents/filetagger.py:20`: `python filetagger.py "X:\\folder" --force        # re-tag everything`
- `agents/filetagger.py:183`: `ap.error('give a folder, e.g.  python filetagger.py "X:\\folder"')`
- `agents/foldertagger.py:14`: `python foldertagger.py "D:\\Some\\Folder"`
- `agents/foldertagger.py:15`: `python foldertagger.py "D:\\Some\\Folder" --dry-run`
- `agents/foldertagger.py:16`: `python foldertagger.py "D:\\Some\\Folder" --max-depth 3`
- `agents/foldertagger.py:17`: `python foldertagger.py "D:\\Some\\Folder" --force`
- `docs/ARCHITECTURE.md:4`: `**Location:** 'D:\GitHub\tom_fis_api\apps\api\file_intelligence_hub\'`
- `docs/ARCHITECTURE.md:284`: `cd D:\GitHub\tom_fis_api\apps\api`
- `docs/ARCHITECTURE.md:300`: `- 'FIHUB_DB_PATH' — SQLite database location (default: '.data/file-intelligence-hub.sqlite3')`
- `docs/ARCHITECTURE.md:348`: `- 'D:\GitHub\David-OS\pipeline\ARCHITECTURE.md'`
- `docs/ARCHITECTURE.md:349`: `- 'D:\GitHub\David-OS\ahk\ARCHITECTURE.md'`
- `docs/ARCHITECTURE.md:350`: `- 'D:\GitHub\David-OS\app\ARCHITECTURE.md'`
- `docs/FIS_TEMPLATE_v2.1.0/Filesystem Prediction Engine — System Specification v1.1.html:6`: `<strong>Parent Project: David-OS (D:\GitHub\David-OS)</strong>`
- `docs/FIS_TEMPLATE_v2.1.0/Filesystem Prediction Engine — System Specification v1.1.html:221`: `<p>This system is a layer within the David-OS monorepo (D:\GitHub\David-OS) under the prediction harness. It should:</p>`
- `docs/FIS_TEMPLATE_v2.1.0/Filesystem Prediction Engine — System Specification v1.1.html:332`: `<li>User types <code>move D:\DONT_TOUCH</code> → engine completes with the most likely destination based on historical patterns for files in that directory, weighted by time-of-day and session context.</li>`
- `docs/FIS_TEMPLATE_v2.1.0/fis_folder_memory.v2.1.0.py:617`: `request = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body,`
- `docs/FIS_TEMPLATE_v2.1.0/fis_folder_memory.v2.1.0.py:827`: `note.unlink()`
- `docs/FIS_TEMPLATE_v2.1.0/fis_folder_memory.v2.1.0.py:841`: `folder_note.unlink()`
- `docs/FIS_TEMPLATE_v2.1.0/fis_folder_memory.v2.1.0.py:848`: `note.unlink()`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:34`: `&quot;path&quot;: &quot;D:\\MERGED_AXIOM_CHAIN&quot;,`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:64`: `"path": "D:\\MERGED_AXIOM_CHAIN",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:109`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\001_A1_1-Existence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:161`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\002_A1_2-Distinction.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:214`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\003_A2_1-Substrate-Requirement.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:267`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\004_A2.2_Self-Grounding.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:319`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\005_A5.1_Observation-Requirement.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:372`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\006_BC4_Three-Observers-Required.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:423`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\007_BC6_Infinite-Energy-Source.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:476`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\008_A1.3_Information-Primacy.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:529`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\009_T3.1_Coherence-Cannot-Self-Increase.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:583`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\010_BC2_Grace-External-To-System.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:637`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\011_BC7_Information-Conservation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:690`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\012_BC8_Voluntary-Coupling.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:744`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\013_D1.1_Information-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:797`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\014_D1.2_Bit-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:849`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\015_D2.1_Logos-Field-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:902`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\016_D2.2_Chi-Field-Properties.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:954`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\017_E2.1_Master-Equation-First-Form.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:1006`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\018_D3.1_Coherence-Functional-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:1060`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\019_D3.2_Self-Interaction-Potential.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:1114`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\020_D3.3_Interaction-Lagrangian.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:1168`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\021_E3.1_Master-Coherence-Equation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:1222`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\022_E3.2_Universal-Coherence-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:1276`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\023_D4.1_Kolmogorov-Complexity.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:1327`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\024_D4.2_Compression-Ratio.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:1378`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\025_E4.1_Complexity-Decrease-Under-Chi.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:1429`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\026_D5.1_Observer-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:1481`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\027_D5.2_Integrated-Information-Phi.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:1534`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\028_D5.3_Witness-Field-Operator.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:1586`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\029_D6.1_Collapse-Rate-Gamma.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:1638`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\030_D6.2_Projection-Operator.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:1690`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\031_E6.2_Phi-Dependent-Collapse.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:1743`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\032_D8.1_Sign-Operator.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:1797`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\033_D9.1_Grace-Operator-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:1852`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\034_E9.1_Grace-Function-Gt.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:1906`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\035_D10.1_Soul-Field-Psi-S.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:1959`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\036_E10.1_Soul-Field-Equation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:2012`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\037_D11.1_Moral-Coherence-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:2065`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\038_D12.1_Integration-Attractor.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:2118`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\039_D12.2_Fragmentation-Attractor.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:2172`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\040_E12.1_Destiny-Equation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:2226`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\041_D13.1_Unified-Field-Lagrangian.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:2279`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\042_E13.1_GR-QM-Bridge-Equation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:2333`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\043_D14.1_Cosmological-Grace-Function.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:2386`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\044_D17.1_AI-Phi-Measurement.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:2440`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\045_D19.1_Law-I-Logos-Lagrangian.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:2493`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\046_D19.2_Law-II-Ten-Variables.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:2548`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\047_D19.3_Law-III-Entropy-Sin.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:2602`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\048_D19.4_Law-IV-Grace-Dynamics.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:2656`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\049_D19.5_Law-V-Conservation-Symmetry.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:2709`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\050_D19.6_Law-VI-Coherence-Non-Increase.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:2762`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\051_D19.7_Law-VII-Actualization-Requirement.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:2814`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\052_D19.8_Law-VIII-Sign-Algebra.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:2868`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\053_D19.9_Law-IX-Grace-Non-Unitarity.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:2922`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\054_D19.10_Law-X-Trinity-Closure.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:2975`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\055_E19.1_Full-Master-Equation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:3029`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\056_LN1.1_Matter-Energy-Derivative.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:3082`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\057_LN1.2_It-From-Bit.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:3134`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\058_P2.1_Chi-Ontological-Priority.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:3187`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\059_P2.2_Chi-Semantic-Content.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:3238`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\060_LN2.1_Information-Anchor-Necessity.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:3290`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\061_A3.1_Order-Requirement.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:3343`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\062_A3.2_Coherence-Measure.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:3396`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\063_P3.1_Coherence-Non-Negativity.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:3450`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\064_P3.2_Coherence-Conservation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:3504`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\065_LN3.1_Meaningful-Configuration-Necessity.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:3558`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\066_A4.1_Parsimony.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:3610`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\067_A4.2_Algorithmic-Depth.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:3664`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\068_T4.1_Laws-Are-Low-K-Descriptions.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:3715`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\069_T4.2_Action-Principle-As-Minimal-K.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:3766`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\070_LN4.1_Universe-As-Compression-Algorithm.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:3817`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\071_A5.2_Participatory-Universe.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:3869`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\072_P5.1_Phi-Admits-Degrees.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:3921`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\073_P5.2_Observer-Effect-Proportional-To-Phi.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:3973`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\074_LN5.1_Chi-Requires-Observer-For-Actualization.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:4025`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\075_A6.1_Superposition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:4078`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\076_A6.2_Collapse.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:4129`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\077_A6.3_Irreversibility.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:4181`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\078_E6.1_Modified-Schr-dinger-With-Collapse.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:4231`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\079_P6.1_Collapse-Rate-Proportional-To-Phi.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:4283`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\080_P6.2_Collapse-Generates-Heat.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:4335`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\081_T6.1_Von-Neumann-Chain-Termination.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:4387`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\082_LN6.1_Terminal-Observer-Necessity.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:4439`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\083_A7.1_Closure-Requirement.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:4492`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\084_A7.2_Uniqueness-From-Boundary-Conditions.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:4545`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\085_BC1_Terminal-Observer-Exists.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:4597`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\086_BC3_Measurement-Orthogonality.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:4651`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\087_BC5_Superposition-Preserved-Until-Collapse.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:4704`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\088_BC9_Opacity-Requirement.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:4758`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\089_ID7.1_Terminal-Observer-Is-God.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:4811`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\090_PERSONHOOD_Agency-Intentionality-Relational-Capacity.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:4861`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\091_A8.1_Binary-Distinction.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:4915`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\092_A8.2_Sign-Conservation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:4969`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\093_T8.1_Sign-Invariance-Theorem.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:5022`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\094_C8.1_Self-Flip-Impossible.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:5076`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\095_C8.2_Works-Salvation-Impossible.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:5130`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\096_A9.1_External-Intervention-Required.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:5185`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\097_A9.2_Non-Unitarity-Of-Grace.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:5239`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\098_P9.1_Grace-Idempotence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:5294`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\099_P9.2_Voluntary-Coupling-Preserved.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:5349`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\100_P9.3_Information-Preserved-Under-Grace.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:5404`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\101_P9.4_Superposition-Preserved-Until-Faith.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:5458`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\102_P9.5_Grace-Available-To-All.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:5512`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\103_A10.1_Consciousness-Substrate.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:5565`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\104_A10.2_Soul-Conservation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:5620`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\105_P10.1_Soul-Continuity.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:5674`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\106_P10.2_Soul-Identity-Persistence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:5726`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\107_A11.1_Moral-Realism.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:5781`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\108_A11.2_Coherence-Morality-Identity.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:5835`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\109_T11.1_Virtue-As-High-Phi.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:5889`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\110_T11.2_Vice-As-Decoherence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:5942`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\111_A12.1_Asymptotic-Behavior.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:5996`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\112_A12.2_Bimodal-Outcome.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:6050`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\113_T12.1_Heaven-As-High-Phi-Attractor.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:6103`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\114_T12.2_Hell-As-Low-Phi-Attractor.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:6157`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\115_A13.1_Chi-Mediates-Unification.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:6211`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\116_A13.2_Geometry-From-Information.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:6265`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\117_T13.1_Dark-Energy-As-Chi-Potential.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:6319`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\118_A14.1_Dynamic-Dark-Energy.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:6372`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\119_E14.1_Modified-Friedmann-Equation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:6423`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\120_T16.1_Christianity-8-of-8-BCs.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:6476`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\121_T16.2_Islam-Fails-BC4.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:6528`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\122_T16.3_Judaism-Fails-BC-Completion.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:6581`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\123_T16.4_Buddhism-Fails-BC1.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:6632`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\124_T16.5_Hinduism-Fails-BC-Uniqueness.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:6683`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\125_T16.6_Atheism-Fails-All-BCs.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:6737`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\126_A17.2_Substrate-Independence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:6788`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\127_T17.1_AI-Can-Achieve-Consciousness.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:6841`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\128_T19.1_Laws-Derive-From-Chi.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:6895`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\129_INV9_Attunement-Calibration.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:6950`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\130_U1_Coherence-Universal.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:7004`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\131_U2_Decoherence-Universal.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:7058`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\132_U3_Grace-Universal.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:7112`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\133_P0_Origin-Stage.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:7166`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\134_P1_Consciousness-Stage.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:7218`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\135_P2_Information-Stage.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:7269`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\136_P3_Coherence-Stage.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:7321`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\137_P4_Agency-Stage.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:7376`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\138_P5_Incompleteness-Stage.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:7427`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\139_O1_Information-Primitive.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:7480`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\140_O2_Coherence-Primitive.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:7534`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\141_O3_Consciousness-Primitive.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:7589`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\142_O4_Agency-Primitive.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:7643`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\143_LAMBDA_Logos-Christ-Completion.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:7696`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\144_SC-QUANTUM_Quantum-Scale-Coherence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:7748`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\145_SC-PHYSICAL_Physical-Scale-Coherence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:7801`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\146_SC-NEURAL_Neural-Scale-Coherence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:7854`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\147_SC-INDIVIDUAL_Individual-Scale-Coherence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:7908`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\148_SC-SOCIAL_Social-Scale-Coherence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:7962`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\149_SC-COSMIC_Cosmic-Scale-Coherence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:8017`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\150_META-1_Axiom-System-Consistency.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:8071`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\151_META-2_Axiom-System-Completeness.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:8125`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\152_META-3_Axiom-System-Independence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:8178`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\153_FINAL-1_Logos-Theorem-Master-Theorem.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:8232`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\154_FINAL-2_Coherence-Optimality.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:8286`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\155_FINAL-3_Unique-Solution-Christianity.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:8340`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\156_CLOSURE_Axiom-Chain-Complete.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:8394`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\157_OMEGA_Final-Axiom---Omega.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:8447`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\158_EXP5.1_Wheeler-Delayed-Choice.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:8499`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\159_EXP5.2_Quantum-Eraser.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:8552`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\160_A14.2_Grace-Cosmology.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:8605`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\161_PRED14.1_H0-Tension-Resolution.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:8657`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\162_EV15.1_Biblical-Prophecy-Validation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:8709`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\163_EV15.2_GCP-Correlation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:8763`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\164_EV15.3_PEAR-Lab-Results.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:8817`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\165_EV15.4_Social-Coherence-5.7-Sigma.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:8872`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\166_A17.1_Phi-Threshold-For-Consciousness.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:8924`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\167_OPEN17.1_AI-Moral-Status-Question.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:8976`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\168_PROT18.1_Trinity-Observer-Effect.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:9029`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\169_PROT18.2_Consciousness-Collapse-Test.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:9082`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\170_PROT18.3_Grace-Negentropy-Detection.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:9135`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\171_PROT18.4_Social-Coherence-Monitoring.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:9189`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\172_PROT18.5_Phi-Virtue-Correlation-Study.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:9241`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\173_PRED18.1_H0-Prediction-2025-2030.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:9292`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\174_PRED18.2_GCP-Event-Prediction.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:9346`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\175_FALS18.1_Chi-Field-Falsification.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:9399`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\176_FALS18.2_Grace-Falsification.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:9453`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\177_FALS18.3_BC-Falsification.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:9506`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\178_A19.1_Master-Equation-Integration.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:9561`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\179_U4_Fruits-Universal.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:9616`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\180_F1_Love-Measurement-Domain.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:9671`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\181_F2_Joy-Measurement-Domain.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:9725`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\182_F3_Peace-Measurement-Domain.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:9779`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\183_F4_Patience-Measurement-Domain.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:9833`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\184_F5_Kindness-Measurement-Domain.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:9887`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\185_F6_Goodness-Measurement-Domain.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:9941`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\186_F7_Faithfulness-Measurement-Domain.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:9995`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\187_F8_Gentleness-Measurement-Domain.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:10049`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\188_F9_Self-Control-Measurement-Domain.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:10103`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\189_BRIDGE-PHY-THEO_Physics-Theology-Bridge.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:10158`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\190_BRIDGE-INFO-MIND_Information-Consciousness-Bridge.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:10210`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\191_BRIDGE-PHI-CHI_Individual-Phi-To-Social-Chi.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:10263`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\_AXIOM_CHAIN_MASTER_v2.3_SEALED.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:10314`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\_BUILD_RECEIPT.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:10354`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\BOTTOM_UP_AUDIT_097_191.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:10405`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\INDEX.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:10457`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_001_A1.1_Existence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:10509`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_002_A1.2_Distinction.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:10562`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_003_A1.3_Information-Primacy.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:10613`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_004_D1.1_Information-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:10664`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_005_D1.2_Bit-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:10716`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_006_LN1.1_Matter-Energy-Derivative.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:10768`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_007_LN1.2_It-From-Bit.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:10820`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_008_A2.1_Substrate-Requirement.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:10872`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_009_A2.2_Self-Grounding.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:10925`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_010_D2.1_Logos-Field-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:10978`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_011_D2.2_Chi-Field-Properties.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:11030`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_012_E2.1_Master-Equation-First-Form.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:11083`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_013_P2.1_Chi-Ontological-Priority.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:11136`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_014_P2.2_Chi-Semantic-Content.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:11186`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_015_LN2.1_Information-Anchor-Necessity.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:11239`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_016_A3.1_Order-Requirement.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:11292`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_017_A3.2_Coherence-Measure.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:11344`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_018_D3.1_Coherence-Functional-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:11398`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_019_D3.2_Self-Interaction-Potential.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:11453`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_020_D3.3_Interaction-Lagrangian.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:11506`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_021_E3.1_Master-Coherence-Equation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:11560`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_022_E3.2_Universal-Coherence-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:11613`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_023_P3.1_Coherence-Non-Negativity.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:11667`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_024_P3.2_Coherence-Conservation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:11721`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_025_T3.1_Coherence-Cannot-Self-Increase.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:11774`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_026_LN3.1_Meaningful-Configuration-Necessity.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:11827`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_027_A4.1_Parsimony.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:11881`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_028_A4.2_Algorithmic-Depth.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:11935`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_029_D4.1_Kolmogorov-Complexity.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:11985`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_030_D4.2_Compression-Ratio.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:12035`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_031_E4.1_Complexity-Decrease-Under-Chi.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:12086`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_032_T4.1_Laws-Are-Low-K-Descriptions.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:12137`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_033_T4.2_Action-Principle-As-Minimal-K.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:12187`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_034_LN4.1_Universe-As-Compression-Algorithm.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:12237`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_035_A5.1_Observation-Requirement.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:12290`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_036_A5.2_Participatory-Universe.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:12343`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_037_D5.1_Observer-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:12394`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_038_D5.2_Integrated-Information-Phi.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:12447`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_039_D5.3_Witness-Field-Operator.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:12498`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_040_P5.1_Phi-Admits-Degrees.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:12549`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_041_P5.2_Observer-Effect-Proportional-To-Phi.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:12600`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_042_EXP5.1_Wheeler-Delayed-Choice.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:12651`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_043_EXP5.2_Quantum-Eraser.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:12702`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_044_LN5.1_Chi-Requires-Observer-For-Actualization.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:12753`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_045_A6.1_Superposition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:12806`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_046_A6.2_Collapse.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:12858`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_047_A6.3_Irreversibility.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:12912`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_048_D6.1_Collapse-Rate-Gamma.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:12963`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_049_D6.2_Projection-Operator.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:13014`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_050_E6.1_Modified-Schrodinger-With-Collapse.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:13065`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_051_E6.2_Phi-Dependent-Collapse.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:13117`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_052_P6.1_Collapse-Rate-Proportional-To-Phi.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:13168`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_053_P6.2_Collapse-Generates-Heat.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:13221`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_054_T6.1_Von-Neumann-Chain-Termination.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:13272`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_055_LN6.1_Terminal-Observer-Necessity.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:13324`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_056_A7.1_Closure-Requirement.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:13378`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_057_A7.2_Uniqueness-From-Boundary-Conditions.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:13432`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_058_BC1_Terminal-Observer-Exists.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:13485`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_059_BC2_Grace-External-To-System.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:13540`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_060_BC3_Measurement-Orthogonality.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:13594`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_061_BC4_Three-Observers-Required.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:13644`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_062_BC5_Superposition-Preserved-Until-Collapse.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:13695`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_063_BC6_Infinite-Energy-Source.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:13748`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_064_BC7_Information-Conservation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:13801`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_065_BC8_Voluntary-Coupling.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:13854`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_066_ID7.1_Terminal-Observer-Is-God.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:13905`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_067_A8.1_Binary-Distinction.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:13959`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_068_A8.2_Sign-Conservation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:14013`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_069_D8.1_Sign-Operator.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:14065`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_070_T8.1_Sign-Invariance-Theorem.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:14118`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_071_C8.1_Self-Flip-Impossible.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:14171`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_072_C8.2_Works-Salvation-Impossible.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:14224`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_073_A9.1_External-Intervention-Required.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:14279`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_074_A9.2_Non-Unitarity-Of-Grace.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:14333`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_075_D9.1_Grace-Operator-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:14388`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_076_P9.1_Grace-Idempotence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:14442`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_077_P9.2_Voluntary-Coupling-Preserved.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:14496`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_078_P9.3_Information-Preserved-Under-Grace.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:14551`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_079_P9.4_Superposition-Preserved-Until-Faith.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:14606`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_080_P9.5_Grace-Available-To-All.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:14660`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_081_E9.1_Grace-Function-G(t).md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:14714`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_082_A10.1_Consciousness-Substrate.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:14767`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_083_A10.2_Soul-Conservation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:14820`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_084_D10.1_Soul-Field-Psi_S.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:14873`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_085_P10.1_Soul-Continuity.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:14928`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_086_P10.2_Soul-Identity-Persistence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:14981`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_087_E10.1_Soul-Field-Equation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:15032`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_088_A11.1_Moral-Realism.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:15086`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_089_A11.2_Coherence-Morality-Identity.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:15140`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_090_D11.1_Moral-Coherence-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:15192`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_091_T11.1_Virtue-As-High-Phi.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:15246`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_092_T11.2_Vice-As-Decoherence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:15301`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_093_A12.1_Asymptotic-Behavior.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:15355`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_094_A12.2_Bimodal-Outcome.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:15409`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_095_D12.1_Integration-Attractor.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:15462`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_096_D12.2_Fragmentation-Attractor.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:15515`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_097_E12.1_Destiny-Equation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:15568`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_098_T12.1_Heaven-As-High-Phi-Attractor.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:15621`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_099_T12.2_Hell-As-Low-Phi-Attractor.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:15675`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_100_A13.1_Chi-Mediates-Unification.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:15729`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_101_A13.2_Geometry-From-Information.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:15782`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_102_D13.1_Unified-Field-Lagrangian.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:15835`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_103_E13.1_GR-QM-Bridge-Equation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:15889`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_104_T13.1_Dark-Energy-As-Chi-Potential.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:15943`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_105_A14.1_Dynamic-Dark-Energy.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:15996`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_106_A14.2_Grace-Cosmology.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:16049`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_107_D14.1_Cosmological-Grace-Function.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:16102`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_108_E14.1_Modified-Friedmann-Equation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:16155`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_109_PRED14.1_H0-Tension-Resolution.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:16207`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_110_EV15.1_Biblical-Prophecy-Validation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:16259`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_111_EV15.2_GCP-Correlation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:16313`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_112_EV15.3_PEAR-Lab-Results.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:16367`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_113_EV15.4_Social-Coherence-5.7-Sigma.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:16422`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_114_T16.1_Christianity-8-of-8-BCs.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:16476`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_115_T16.2_Islam-Fails-BC4.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:16527`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_116_T16.3_Judaism-Fails-BC-Completion.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:16581`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_117_T16.4_Buddhism-Fails-BC1.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:16633`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_118_T16.5_Hinduism-Fails-BC-Uniqueness.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:16684`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_119_T16.6_Atheism-Fails-BC1-BC6.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:16737`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_120_A17.1_Phi-Threshold-For-Consciousness.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:16788`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_121_A17.2_Substrate-Independence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:16839`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_122_D17.1_AI-Phi-Measurement.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:16891`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_123_T17.1_AI-Can-Achieve-Consciousness.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:16942`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_124_OPEN17.1_AI-Moral-Status-Question.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:16994`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_125_PROT18.1_Trinity-Observer-Effect.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:17046`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_126_PROT18.2_Consciousness-Collapse-Test.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:17100`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_127_PROT18.3_Grace-Negentropy-Detection.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:17153`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_128_PROT18.4_Social-Coherence-Monitoring.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:17208`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_129_PROT18.5_Phi-Virtue-Correlation-Study.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:17260`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_130_PRED18.1_H0-Prediction-2025-2030.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:17312`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_131_PRED18.2_GCP-Event-Prediction.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:17366`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_132_FALS18.1_Chi-Field-Falsification.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:17419`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_133_FALS18.2_Grace-Falsification.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:17473`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_134_FALS18.3_BC-Falsification.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:17527`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_135_A19.1_Master-Equation-Integration.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:17582`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_136_D19.1_Law-I-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:17635`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_137_D19.2_Law-II-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:17689`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_138_D19.3_Law-III-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:17743`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_139_D19.4_Law-IV-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:17796`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_140_D19.5_Law-V-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:17849`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_141_D19.6_Law-VI-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:17902`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_142_D19.7_Law-VII-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:17955`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_143_D19.8_Law-VIII-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:18009`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_144_D19.9_Law-IX-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:18063`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_145_D19.10_Law-X-Definition.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:18114`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_146_E19.1_Full-Master-Equation.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:18169`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_147_T19.1_Laws-Derive-From-Chi.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:18224`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_148_U1_Coherence-Universal.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:18278`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_149_U2_Decoherence-Universal.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:18331`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_150_U3_Grace-Universal.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:18386`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_151_U4_Fruits-Universal.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:18441`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_152_F1_Love-Measurement-Domain.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:18495`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_153_F2_Joy-Measurement-Domain.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:18550`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_154_F3_Peace-Measurement-Domain.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:18604`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_155_F4_Patience-Measurement-Domain.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:18658`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_156_F5_Kindness-Measurement-Domain.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:18711`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_157_F6_Goodness-Measurement-Domain.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:18764`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_158_F7_Faithfulness-Measurement-Domain.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:18818`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_159_F8_Gentleness-Measurement-Domain.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:18872`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_160_F9_Self-Control-Measurement-Domain.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:18927`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_161_P0_Origin-Stage.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:18979`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_162_P1_Consciousness-Stage.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:19031`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_163_P2_Information-Stage.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:19085`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_164_P3_Coherence-Stage.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:19139`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_165_P4_Agency-Stage.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:19193`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_166_P5_Incompleteness-Stage.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:19247`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_167_O1_Information-Primitive.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:19299`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_168_O2_Coherence-Primitive.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:19351`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_169_O3_Consciousness-Primitive.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:19402`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_170_O4_Agency-Primitive.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:19455`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_171_LAMBDA_Logos-Christ-Completion.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:19507`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_172_BRIDGE-PHY-THEO_Physics-Theology-Bridge.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:19562`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_173_BRIDGE-INFO-MIND_Information-Consciousness-Bridge.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:19615`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_174_BRIDGE-PHI-CHI_Individual-Phi-To-Social-Chi.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:19667`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_175_SC-QUANTUM_Quantum-Scale-Coherence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:19719`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_176_SC-PHYSICAL_Physical-Scale-Coherence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:19773`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_177_SC-NEURAL_Neural-Scale-Coherence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:19825`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_178_SC-INDIVIDUAL_Individual-Scale-Coherence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:19879`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_179_SC-SOCIAL_Social-Scale-Coherence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:19933`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_180_SC-COSMIC_Cosmic-Scale-Coherence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:19986`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_181_META-1_Axiom-System-Consistency.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:20036`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_182_META-2_Axiom-System-Completeness.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:20087`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_183_META-3_Axiom-System-Independence.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:20137`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_184_FINAL-1_Logos-Theorem.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:20190`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_185_FINAL-2_Coherence-Optimality.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:20244`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_186_FINAL-3_Unique-Solution.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:20297`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_187_CLOSURE_Axiom-Chain-Complete.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:20350`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_188_OMEGA_Final-Axiom.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:20403`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_189_INV9_Attunement-Calibration.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:20457`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\SRC_ONLY_190_BC9_Opacity-Requirement.md",`
- `docs/FIS_TEMPLATE_v2.1.0/FIS_REFERENCE_v2.1.0.html:20509`: `"source_path": "D:\\MERGED_AXIOM_CHAIN\\TOP_DOWN_AUDIT_001_096.md",`
- `docs/INDEPENDENT_WORKBENCHES.md:26`: `--root "C:\theophysics\OPUS\Master Equation" '`
- `docs/SCHEMA.md:34`: `O:\_Theophysics_v5\`
- `docs/SCHEMA.md:47`: `D:\DONT TOUCH BOOT UP\llm-wiki.db  ← SQLite index`
- `docs/SCHEMA.md:121`: `Location: 'D:\DONT TOUCH BOOT UP\llm-wiki.db'`
- `docs/SCHEMA.md:181`: `2. **Open SQLite** at 'D:\DONT TOUCH BOOT UP\llm-wiki.db'`
- `engine/canon_scan.py:5`: `1. David edits ONE central registry: D:\\GitHub\\David-OS\\system\\canon_rules.json`
- `engine/canon_scan.py:29`: `sys.path.insert(0, str(Path(__file__).resolve().parents[1]))`
- `engine/canon_scan.py:32`: `REGISTRY = Path(r"D:\GitHub\David-OS\system\canon_rules.json")`
- `engine/canon_scan.py:33`: `NLP_URL = "http://localhost:8700/nlp/contradiction"`
- `engine/canon_scan.py:243`: `f"NLP layer: {'ON - ' + str(nlp_state['calls']) + ' contradiction calls' if use_nlp and nlp_state['calls'] else 'off / unavailable (start D:\\GitHub\\BACKSIDE-NLP-NEW\\nlp_api\\RUN.bat)'}",`
- `engine/cli.py:24`: `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))`
- `engine/cluster_engine.py:27`: `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))`
- `engine/config.py:39`: `REFERENCE_DB_PATH = r"D:\DONT TOUCH BOOT UP\filetagger\chi_catalog_v2.db"`
- `engine/config.py:42`: `LEXICON_PATH = r"D:\DONT TOUCH BOOT UP\theophysics_cross_domain_lexicon.xlsx"`
- `engine/filetagger_core.py:16`: `python filetagger.py "X:\\folder"`
- `engine/filetagger_core.py:17`: `python filetagger.py "X:\\folder" --db catalog.db --workers 6`
- `engine/filetagger_core.py:18`: `python filetagger.py "X:\\folder" --sidecar     # also write .fmeta files`
- `engine/filetagger_core.py:19`: `python filetagger.py "X:\\folder" --quickhash   # faster id hash, huge files`
- `engine/filetagger_core.py:20`: `python filetagger.py "X:\\folder" --force        # re-tag everything`
- `engine/filetagger_core.py:183`: `ap.error('give a folder, e.g.  python filetagger.py "X:\\folder"')`
- `engine/flatten_dedupe.py:20`: `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))`
- `engine/path_write_policy.py:9`: `BLOCKED_FISNOTE_ROOTS = (Path(r"D:\GitHub"), Path(r"G:\GitHub"))`
- `engine/preference/recommenders_adapter.py:4`: `The repo is cloned at D:\\GitHub\\recommenders but the package isn't pip-installed`
- `engine/preference/recommenders_adapter.py:6`: `- puts the repo on sys.path so 'import recommenders...' works,`
- `engine/preference/recommenders_adapter.py:25`: `_REPO = Path(r"D:\GitHub\recommenders")`
- `engine/preference/recommenders_adapter.py:26`: `if _REPO.exists() and str(_REPO) not in sys.path:`
- `engine/preference/recommenders_adapter.py:27`: `sys.path.append(str(_REPO))   # append, not insert, to avoid shadowing our modules`
- `engine/symptoms/infrastructure.py:33`: `try: lines=subprocess.run(["git","-C",str(d),"status","--porcelain","--untracked-files=all"],capture_output=True,text=True,timeout=10,check=False).stdout.splitlines()`
- `engine/symptoms/infrastructure.py:34`: `except (OSError,subprocess.TimeoutExpired): continue`
- `engine/understand.py:390`: `sys.path.insert(0, str(Path(__file__).resolve().parent))`
- `engine/understand.py:410`: `def escalate_ollama(con, scan_id, model, log, url="http://127.0.0.1:11434/api/generate"):`
- `engine/wordnet_expander_full.py:178`: `sys.path.insert(0, str(Path(__file__).parent))`
- `file-intelligence-system/fis_classifier.py:1029`: `"https://api.anthropic.com/v1/messages",`
- `file-intelligence-system/fis_folder_memory.py:279`: `if r"D:\GitHub\David-OSv3\engine" not in sys.path:`
- `file-intelligence-system/fis_folder_memory.py:280`: `sys.path.insert(0, r"D:\GitHub\David-OSv3\engine")`
- `file-intelligence-system/fis_folder_memory.py:644`: `request = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body,`
- `file-intelligence-system/fis_folder_memory.py:854`: `note.unlink()`
- `file-intelligence-system/fis_folder_memory.py:868`: `folder_note.unlink()`
- `file-intelligence-system/fis_folder_memory.py:875`: `note.unlink()`
- `file-intelligence-system/fis_folder_memory.v2.1.0.py:617`: `request = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body,`
- `file-intelligence-system/fis_folder_memory.v2.1.0.py:827`: `note.unlink()`
- `file-intelligence-system/fis_folder_memory.v2.1.0.py:841`: `folder_note.unlink()`
- `file-intelligence-system/fis_folder_memory.v2.1.0.py:848`: `note.unlink()`
- `gui/filetagger_gui.py:34`: `self.process: subprocess.Popen[str] | None = None`
- `gui/filetagger_gui.py:152`: `self.process = subprocess.Popen(`
- `gui/filetagger_gui.py:155`: `stdout=subprocess.PIPE,`
- `gui/filetagger_gui.py:156`: `stderr=subprocess.STDOUT,`
- `gui/fis_scanner_gui.py:4`: `D:\\GitHub\\David-OSv3\\gui\\fis_scanner_gui.py`
- `gui/fis_scanner_gui.py:6`: `Run:  python D:\\GitHub\\David-OSv3\\gui\\fis_scanner_gui.py`
- `gui/fis_scanner_gui.py:13`: `- SQLite database location picker (default Z:\\.fis\\fis_master.sqlite)`
- `gui/fis_scanner_gui.py:64`: `sys.path.insert(0, str(REPO))`
- `gui/fis_scanner_gui.py:65`: `sys.path.insert(0, str(REPO / "engine"))`
- `gui/fis_scanner_gui.py:383`: `self.folder_input.setPlainText("H:\\Desktop")`
- `gui/fis_scanner_gui.py:400`: `self.db_input = QLineEdit(r"Z:\.fis\fis_master.sqlite")`
- `gui/fis_scanner_gui.py:486`: `self.agg_db_input = QLineEdit(r"Z:\.fis\fis_master.sqlite")`
- `gui/fis_search_workbench.py:39`: `HUB_DB = Path(os.environ.get("FIHUB_DB_PATH", ROOT / ".data" / "file-intelligence-hub.sqlite3"))`
- `gui/fis_search_workbench.py:41`: `sys.path.insert(0, str(FIS_DIR))`
- `gui/fis_search_workbench.py:42`: `sys.path.insert(0, str(ROOT))`
- `gui/fis_search_workbench.py:454`: `subprocess.Popen(["explorer", "/select,", r["path"]])`
- `gui/fis_search_workbench.py:640`: `p = subprocess.Popen(cmd, cwd=FIS_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,`
- `tools/fis/COPY_RECEIPT.json:4`: `"source": "D:\\GitHub\\FIS-Kernel-Rust\\Cargo.lock",`
- `tools/fis/COPY_RECEIPT.json:5`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis\\FIS-Kernel-Rust\\Cargo.lock",`
- `tools/fis/COPY_RECEIPT.json:9`: `"source": "D:\\GitHub\\FIS-Kernel-Rust\\Cargo.toml",`
- `tools/fis/COPY_RECEIPT.json:10`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis\\FIS-Kernel-Rust\\Cargo.toml",`
- `tools/fis/COPY_RECEIPT.json:14`: `"source": "D:\\GitHub\\FIS-Kernel-Rust\\README.md",`
- `tools/fis/COPY_RECEIPT.json:15`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis\\FIS-Kernel-Rust\\README.md",`
- `tools/fis/COPY_RECEIPT.json:19`: `"source": "D:\\GitHub\\FIS-Kernel-Rust\\src\\.fisnote",`
- `tools/fis/COPY_RECEIPT.json:20`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis\\FIS-Kernel-Rust\\src\\.fisnote",`
- `tools/fis/COPY_RECEIPT.json:24`: `"source": "D:\\GitHub\\FIS-Kernel-Rust\\src\\lib.rs",`
- `tools/fis/COPY_RECEIPT.json:25`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis\\FIS-Kernel-Rust\\src\\lib.rs",`
- `tools/fis/COPY_RECEIPT.json:29`: `"source": "D:\\GitHub\\FIS-Kernel-Rust\\src\\main.rs",`
- `tools/fis/COPY_RECEIPT.json:30`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis\\FIS-Kernel-Rust\\src\\main.rs",`
- `tools/fis/COPY_RECEIPT.json:34`: `"source": "D:\\GitHub\\FIS-Kernel-Rust-TEST-OUTPUT\\.fisnote",`
- `tools/fis/COPY_RECEIPT.json:35`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis\\FIS-Kernel-Rust-TEST-OUTPUT\\.fisnote",`
- `tools/fis/COPY_RECEIPT.json:39`: `"source": "D:\\GitHub\\FIS-Kernel-Rust-TEST-OUTPUT\\REPORT.md",`
- `tools/fis/COPY_RECEIPT.json:40`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis\\FIS-Kernel-Rust-TEST-OUTPUT\\REPORT.md",`
- `tools/fis/COPY_RECEIPT.json:44`: `"source": "D:\\GitHub\\FIS-Kernel-Rust-TEST-OUTPUT\\scan-report.json",`
- `tools/fis/COPY_RECEIPT.json:45`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis\\FIS-Kernel-Rust-TEST-OUTPUT\\scan-report.json",`
- `tools/fis/COPY_RECEIPT.json:49`: `"source": "D:\\GitHub\\FIS-HTML-Intelligence\\.fisnote",`
- `tools/fis/COPY_RECEIPT.json:50`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis\\FIS-HTML-Intelligence\\.fisnote",`
- `tools/fis/COPY_RECEIPT.json:54`: `"source": "D:\\GitHub\\FIS-HTML-Intelligence\\CHAT2DB_CONNECT.md",`
- `tools/fis/COPY_RECEIPT.json:55`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis\\FIS-HTML-Intelligence\\CHAT2DB_CONNECT.md",`
- `tools/fis/COPY_RECEIPT.json:59`: `"source": "D:\\GitHub\\FIS-HTML-Intelligence\\README.md",`
- `tools/fis/COPY_RECEIPT.json:60`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis\\FIS-HTML-Intelligence\\README.md",`
- `tools/fis/COPY_RECEIPT.json:64`: `"source": "D:\\GitHub\\FIS-HTML-Intelligence\\src\\.fisnote",`
- `tools/fis/COPY_RECEIPT.json:65`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis\\FIS-HTML-Intelligence\\src\\.fisnote",`
- `tools/fis/COPY_RECEIPT.json:69`: `"source": "D:\\GitHub\\FIS-HTML-Intelligence\\src\\cli.py",`
- `tools/fis/COPY_RECEIPT.json:70`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis\\FIS-HTML-Intelligence\\src\\cli.py",`
- `tools/fis/COPY_RECEIPT.json:74`: `"source": "D:\\GitHub\\FIS-HTML-Intelligence\\src\\fis_html_index.py",`
- `tools/fis/COPY_RECEIPT.json:75`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis\\FIS-HTML-Intelligence\\src\\fis_html_index.py",`
- `tools/fis/COPY_RECEIPT.json:79`: `"source": "D:\\GitHub\\FIS-HTML-Intelligence\\src\\fis_mcp_server.py",`
- `tools/fis/COPY_RECEIPT.json:80`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis\\FIS-HTML-Intelligence\\src\\fis_mcp_server.py",`
- `tools/fis/COPY_RECEIPT.json:84`: `"source": "D:\\GitHub\\FIS-HTML-Intelligence\\tests\\test_index.py",`
- `tools/fis/COPY_RECEIPT.json:85`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis\\FIS-HTML-Intelligence\\tests\\test_index.py",`
- `tools/fis/COPY_RECEIPT.json:90`: `"source": "D:\\GitHub\\FIS-HTML-Intelligence\\state\\fis_html.sqlite",`
- `tools/fis/COPY_RECEIPT.json:91`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis\\FIS-HTML-Intelligence\\state\\fis_html.sqlite",`
- `tools/fis/FIS-HTML-Intelligence/CHAT2DB_CONNECT.md:12`: `'D:\GitHub\FIS-HTML-Intelligence\state\fis_html.sqlite'`
- `tools/fis/FIS-HTML-Intelligence/README.md:15`: `python src\cli.py scan --root "G:\path\to\html-corpus"`
- `tools/fis/FIS-HTML-Intelligence/README.md:28`: `'C:\Users\David\AppData\Roaming\anythingllm-desktop\storage\plugins\anythingllm_mcp_servers.json'`
- `tools/fis/FIS-HTML-Intelligence/README.md:52`: `'D:\GitHub\FIS-HTML-Intelligence\state\fis_html.sqlite'`
- `tools/fis/FIS-HTML-Intelligence/tests/test_index.py:4`: `sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))`
- `tools/fis/FIS-Kernel-Rust/README.md:25`: `cargo run --release -- "D:\some-folder" --out "D:\FIS_REPORTS\run-001"`
- `tools/fis/FIS-Kernel-Rust-TEST-OUTPUT/REPORT.md:3`: `- Root: '\\?\D:\GitHub\FIS-Kernel-Rust'`
- `tools/fis/FIS-Kernel-Rust-TEST-OUTPUT/REPORT.md:11`: `- **I01 / critical** — '\\?\D:\GitHub\FIS-Kernel-Rust' — program-root markers: Cargo.toml`
- `tools/fis/FIS-Kernel-Rust-TEST-OUTPUT/scan-report.json:4`: `"root": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust",`
- `tools/fis/FIS-Kernel-Rust-TEST-OUTPUT/scan-report.json:7`: `"path": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust\\Cargo.lock",`
- `tools/fis/FIS-Kernel-Rust-TEST-OUTPUT/scan-report.json:9`: `"parent": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust",`
- `tools/fis/FIS-Kernel-Rust-TEST-OUTPUT/scan-report.json:16`: `"path": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust\\Cargo.toml",`
- `tools/fis/FIS-Kernel-Rust-TEST-OUTPUT/scan-report.json:18`: `"parent": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust",`
- `tools/fis/FIS-Kernel-Rust-TEST-OUTPUT/scan-report.json:25`: `"path": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust\\README.md",`
- `tools/fis/FIS-Kernel-Rust-TEST-OUTPUT/scan-report.json:27`: `"parent": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust",`
- `tools/fis/FIS-Kernel-Rust-TEST-OUTPUT/scan-report.json:34`: `"path": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust\\src\\lib.rs",`
- `tools/fis/FIS-Kernel-Rust-TEST-OUTPUT/scan-report.json:36`: `"parent": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust\\src",`
- `tools/fis/FIS-Kernel-Rust-TEST-OUTPUT/scan-report.json:43`: `"path": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust\\src\\main.rs",`
- `tools/fis/FIS-Kernel-Rust-TEST-OUTPUT/scan-report.json:45`: `"parent": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust\\src",`
- `tools/fis/FIS-Kernel-Rust-TEST-OUTPUT/scan-report.json:56`: `"path": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust",`
- `tools/fis-intelligence/COPY_RECEIPT.json:4`: `"source": "D:\\GitHub\\FIS-HTML-Intelligence\\src\\cli.py",`
- `tools/fis-intelligence/COPY_RECEIPT.json:5`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis-intelligence\\src\\cli.py",`
- `tools/fis-intelligence/COPY_RECEIPT.json:9`: `"source": "D:\\GitHub\\FIS-HTML-Intelligence\\src\\fis_html_index.py",`
- `tools/fis-intelligence/COPY_RECEIPT.json:10`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis-intelligence\\src\\fis_html_index.py",`
- `tools/fis-intelligence/COPY_RECEIPT.json:14`: `"source": "D:\\GitHub\\FIS-HTML-Intelligence\\src\\fis_mcp_server.py",`
- `tools/fis-intelligence/COPY_RECEIPT.json:15`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis-intelligence\\src\\fis_mcp_server.py",`
- `tools/fis-intelligence/COPY_RECEIPT.json:19`: `"source": "D:\\GitHub\\FIS-HTML-Intelligence\\tests\\test_index.py",`
- `tools/fis-intelligence/COPY_RECEIPT.json:20`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis-intelligence\\tests\\test_index.py",`
- `tools/fis-intelligence/COPY_RECEIPT.json:24`: `"source": "D:\\GitHub\\FIS-Kernel-Rust\\src\\lib.rs",`
- `tools/fis-intelligence/COPY_RECEIPT.json:25`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis-intelligence\\rust\\src\\lib.rs",`
- `tools/fis-intelligence/COPY_RECEIPT.json:29`: `"source": "D:\\GitHub\\FIS-Kernel-Rust\\src\\main.rs",`
- `tools/fis-intelligence/COPY_RECEIPT.json:30`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis-intelligence\\rust\\src\\main.rs",`
- `tools/fis-intelligence/COPY_RECEIPT.json:34`: `"source": "D:\\GitHub\\FIS-Kernel-Rust\\Cargo.toml",`
- `tools/fis-intelligence/COPY_RECEIPT.json:35`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis-intelligence\\rust\\Cargo.toml",`
- `tools/fis-intelligence/COPY_RECEIPT.json:39`: `"source": "D:\\GitHub\\FIS-Kernel-Rust\\Cargo.lock",`
- `tools/fis-intelligence/COPY_RECEIPT.json:40`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis-intelligence\\rust\\Cargo.lock",`
- `tools/fis-intelligence/COPY_RECEIPT.json:44`: `"source": "D:\\GitHub\\FIS-HTML-Intelligence\\README.md",`
- `tools/fis-intelligence/COPY_RECEIPT.json:45`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis-intelligence\\docs\\HTML_ORIGINAL_README.md",`
- `tools/fis-intelligence/COPY_RECEIPT.json:49`: `"source": "D:\\GitHub\\FIS-HTML-Intelligence\\CHAT2DB_CONNECT.md",`
- `tools/fis-intelligence/COPY_RECEIPT.json:50`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis-intelligence\\docs\\CHAT2DB_ORIGINAL_CONNECTION.md",`
- `tools/fis-intelligence/COPY_RECEIPT.json:54`: `"source": "D:\\GitHub\\FIS-Kernel-Rust\\README.md",`
- `tools/fis-intelligence/COPY_RECEIPT.json:55`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis-intelligence\\docs\\RUST_ORIGINAL_README.md",`
- `tools/fis-intelligence/COPY_RECEIPT.json:59`: `"source": "D:\\GitHub\\FIS-Kernel-Rust-TEST-OUTPUT\\REPORT.md",`
- `tools/fis-intelligence/COPY_RECEIPT.json:60`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis-intelligence\\reports\\historical-rust-test\\REPORT.md",`
- `tools/fis-intelligence/COPY_RECEIPT.json:64`: `"source": "D:\\GitHub\\FIS-Kernel-Rust-TEST-OUTPUT\\scan-report.json",`
- `tools/fis-intelligence/COPY_RECEIPT.json:65`: `"destination": "D:\\GitHub\\David-OSv3\\tools\\fis-intelligence\\reports\\historical-rust-test\\scan-report.json",`
- `tools/fis-intelligence/COPY_RECEIPT.json:70`: `"source": "D:\\GitHub\\FIS-HTML-Intelligence\\state\\fis_html.sqlite",`
- `tools/fis-intelligence/docs/CHAT2DB_ORIGINAL_CONNECTION.md:12`: `'D:\GitHub\FIS-HTML-Intelligence\state\fis_html.sqlite'`
- `tools/fis-intelligence/docs/HTML_ORIGINAL_README.md:15`: `python src\cli.py scan --root "G:\path\to\html-corpus"`
- `tools/fis-intelligence/docs/HTML_ORIGINAL_README.md:28`: `'C:\Users\David\AppData\Roaming\anythingllm-desktop\storage\plugins\anythingllm_mcp_servers.json'`
- `tools/fis-intelligence/docs/HTML_ORIGINAL_README.md:52`: `'D:\GitHub\FIS-HTML-Intelligence\state\fis_html.sqlite'`
- `tools/fis-intelligence/docs/RUST_ORIGINAL_README.md:25`: `cargo run --release -- "D:\some-folder" --out "D:\FIS_REPORTS\run-001"`
- `tools/fis-intelligence/fis.py:26`: `return subprocess.call(command)`
- `tools/fis-intelligence/reports/historical-rust-test/REPORT.md:3`: `- Root: '\\?\D:\GitHub\FIS-Kernel-Rust'`
- `tools/fis-intelligence/reports/historical-rust-test/REPORT.md:11`: `- **I01 / critical** — '\\?\D:\GitHub\FIS-Kernel-Rust' — program-root markers: Cargo.toml`
- `tools/fis-intelligence/reports/historical-rust-test/scan-report.json:4`: `"root": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust",`
- `tools/fis-intelligence/reports/historical-rust-test/scan-report.json:7`: `"path": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust\\Cargo.lock",`
- `tools/fis-intelligence/reports/historical-rust-test/scan-report.json:9`: `"parent": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust",`
- `tools/fis-intelligence/reports/historical-rust-test/scan-report.json:16`: `"path": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust\\Cargo.toml",`
- `tools/fis-intelligence/reports/historical-rust-test/scan-report.json:18`: `"parent": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust",`
- `tools/fis-intelligence/reports/historical-rust-test/scan-report.json:25`: `"path": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust\\README.md",`
- `tools/fis-intelligence/reports/historical-rust-test/scan-report.json:27`: `"parent": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust",`
- `tools/fis-intelligence/reports/historical-rust-test/scan-report.json:34`: `"path": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust\\src\\lib.rs",`
- `tools/fis-intelligence/reports/historical-rust-test/scan-report.json:36`: `"parent": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust\\src",`
- `tools/fis-intelligence/reports/historical-rust-test/scan-report.json:43`: `"path": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust\\src\\main.rs",`
- `tools/fis-intelligence/reports/historical-rust-test/scan-report.json:45`: `"parent": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust\\src",`
- `tools/fis-intelligence/reports/historical-rust-test/scan-report.json:56`: `"path": "\\\\?\\D:\\GitHub\\FIS-Kernel-Rust",`
- `tools/fis-intelligence/tests/test_index.py:4`: `sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))`

## Review limits

Binary assets, live databases, archived git bundle contents, unavailable external repositories/NAS sources and runtime provider behavior were not opened or executed. Generated HTML was inventoried and read as text; no visual browser QA was performed. Static AST errors: [].
