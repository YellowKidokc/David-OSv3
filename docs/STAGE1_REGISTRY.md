# Stage 1 inventory and registry

Stage 1 inventories sources in place. It writes only its SQLite registry and
generated exports, outside the source roots. It does not invoke the older
inventory pipeline's tagging, rename proposals, preference learning or canon work.
It reuses `engine.fingerprint.sha256_file` and `engine.text_extractor`; complete
extraction is requested explicitly instead of hashing a content preview.

```powershell
python -m engine.registry scan "C:\Users\David\Documents\faiththruphysics.com\10_VAULTS\01_Working\Canonical Rebuild"
```

Defaults: `_data/registry.sqlite`, `_data/REGISTRY_MASTER.md`,
`_data/registry_works.csv`, `_data/registry_files.csv`.
For an isolated registry, place options before the command:

```powershell
python -m engine.registry --db D:\RegistryState\registry.sqlite scan D:\Corpus
python -m engine.registry --db D:\RegistryState\registry.sqlite export
```

The seven application tables are `files`, `works`, `versions`, `series`, `nabla`,
`review_queue`, and `change_log`. SQLite also owns its AUTOINCREMENT sequence.
Work IDs are permanent `W000001` identifiers; display codes are separate proposed
series/ordinal labels. A root-derived series code is provisional and centrally
unique. Titles and aliases retain observed naming; no title is promoted to canon.
Later taxonomy fields use `standing`, `domain`, `tags_json`, and `canon_status`;
they, `published`, `verified`, preferred version and supersession remain unset.

## Reviewed record types

Registry entities have `record_type`: `work`, `infrastructure`, or `index`.
New observations default to proposed works; only an explicit human ruling changes
the type. The `works` table remains the historical entity store so permanent IDs,
version links and foreign keys survive retyping. Non-work entities appear in their
own master-list section and are excluded from the work count. Both CSVs expose
`record_type`; `registry_works.csv` retains all entity rows for lineage.

```powershell
python -m engine.registry set-type W000001 infrastructure --by David --reason "System marker; pilot grouping review"
python -m engine.registry set-type W000002 index --by David --reason "Series index; pilot grouping review"
```

Rulings are logged with authority, reason, date and prior type. Existing pending
work/version/Nabla items for non-work entities are retained as
`resolved_by_record_type`; unset Nabla placeholders become `not_applicable`.
Supplied or approved Nabla data is preserved. Returning an entity to `work`
reopens those historical review items and restores unset placeholders. Rescans
preserve the human type ruling. No source path, title, canon status or ID is changed.

Byte-identical and whitespace-normalized text groups retain every physical path.
Shared version membership is explicitly proposed. Same-folder title matches
after explicit revision-marker removal create review items, never automatic work
merges. This deliberately conservative first milestone leaves other fuzzy work
relationships for review. New source bytes create a retained historical version;
approved work and Nabla metadata are not overwritten. Missing files are marked,
not removed. Directory traversal failures are queued and suppress missing-file
inference for that root. Linked roots are refused, linked files are recorded as
failed and linked directories are queued rather than followed.

Unchanged successful observations do not rehash or extract. The six domain tables
and exports remain unchanged; every invocation appends a scan receipt to
`change_log`. `last_seen` is the last substantive file observation, not a heartbeat;
the scan receipt timestamps subsequent unchanged observations. Failed observations
are retried. Unsupported formats remain visible as `readable=no`; supported
extraction failures remain visible as `readable=failed` with review items. The
existing optional PDF/DOCX extractors may return no text without a detailed cause;
the registry explicitly records that ambiguity. Image-only PDFs are not OCRed.
NFC and whitespace normalization preserve case, punctuation and word order;
text equality does not establish byte identity or authority.

## Nabla

The existing Atlas core validates and encodes proposals. Supported audiences are
the four explicitly documented values: `SELF`, `TEAM`, `PUBLIC`, `AI_RESEARCH`.
The registry does not call a model or infer a vector from filenames. Every version
starts with a null vector/address/signature and an unset review item. Unset is not
an all-zero vector. This is the build brief's permitted unset-and-queued route.

A supplied proposal may be imported without approving it:

```powershell
python -m engine.registry nabla-propose V_VERSION_ID proposal.json
```

The JSON supplies Atlas's `filing`, `vector`, `confidence` and optional
`review_flags`, plus `classifier`, `protocol_version: "nabla-atlas/0-3-v1"`
and the exact version's `source_sha256`. All six filing fields must be supplied;
no preferred version is guessed. The tool calls Atlas encode and decode, checks
the signature, stores columns and complete record JSON on the same Nabla row,
and queues the proposal with source binding and provenance. Approved rows refuse
replacement. The Stage 1 command provides no metadata-approval or canon command.
Outstanding review history remains retained even after a later proposal arrives.

Honesty firewall (from the build brief): a valid signature proves the ENCODING is
consistent, never that the classification is accurate or the claims true; `E`
scores disorder OF THE ARTIFACT, not its subject (a clear paper about brokenness
is E0); confidence is stored separately and never makes a document disordered;
0/3 stored scores and any 1–3 working ratings are different systems — never mixed,
always provenance-tagged.

## Checks

```powershell
python -m pytest tests/test_stage1_registry.py tests/test_fingerprint.py -q
```

The live pilot acceptance receipt is `_data/stage1_acceptance.json`. Review
`_data/REGISTRY_MASTER.md` before widening roots. No existing review GUI or
taxonomy checker is modified by Stage 1.
