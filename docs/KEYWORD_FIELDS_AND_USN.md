# Locked code fields, filing preview, and journal prototype

Source rules: `C:\theophysics\tools\KEYWORD_CODES.yaml` and `FILING_RULES.yaml`.
They are read, not modified. R02 applies: source renames, flattening, moves and
deletions remain shown proposals for David. No source mutation command was added.

## Registry fields

Work rows now have `series`, `concepts` (JSON list), `opposition`, `status_level`,
`confidence`, `next_review_due`, and `blast_radius` (JSON list, nullable until
dependency coverage is available). `published` already existed as SQLite 0/1;
the validated API accepts yes/no or booleans. Unknown publication is left null,
independent of lifecycle, verification or legacy canon status.

`engine/code_fields.py` loads the locked vocabulary and hashes both rule files.
`update_codes` rejects unlisted series/concepts/opposition/lifecycle codes,
invalid confidence and dates. The explicit L1–L10 range comes from the YAML's
concepts.LW comment; no other codes are invented. The pipeline can set only
IN/WK/AP, cannot downgrade/overwrite a human CD/ES/RT level, and never sets CD/ES.
An explicit David ruling is a separate authority. No CD/ES promotion was made.

Existing record-type rulings and approved metadata survive inventory rescans.
New keyword values were not guessed into the live work records: the renamer CSV
carries keyword-based proposals for review. Code-field API writes are recorded
with authority, codebook hashes and a change-log receipt.

`downstream_dependents` reverses dependent → prerequisite `dependsOn` edges and
computes transitive downstream reachability, including cycle protection.
`propose_blast_radius` records graph-hash-linked review proposals for explicitly
mapped Work IDs. A work absent from the dependency graph is unknown, not zero.
The current pilot graph has no mapped Work-level dependsOn feed, so live
`blast_radius` values remain null rather than inventing dependents or links.

## Renamer: dry run only

```powershell
.venv\Scripts\python.exe -m engine.rename_preview --root "C:\Users\David\Documents\faiththruphysics.com\10_VAULTS\01_Working\Canonical Rebuild" --output _data\filing-review-20261101
```

Outputs: `rename_proposals.csv`, `folder_density.csv`, `REVIEW.md`, and receipts.
The 14 pilot file rows include 12 filename proposals; infrastructure/index sources
are held. Series/book ordinals are preserved where recorded; unnumbered one-offs
lead with a concept. At most two concepts and one opposition code appear. No
lifecycle suffix is added. Complete label phrases avoid interpreting a modal
"will" as Free Will. Keyword mentions, especially opposition, are explicitly
tentative and require semantic/human review. Collision holds remain visible.

The misspelling section found no `theopyhiscs` names within this pilot. R01 found
no zero/one-item folders. The pilot root has 12 real work items and is exempt as
a named series folder; the infrastructure marker and series index are excluded
from its real-item count. Tests separately exercise empty and one-item proposals
and preserve every fixture source byte. No full-drive spelling/density census
is claimed.

## C: USN journal: prototype, read-only

`engine/usn_reader.py` exposes only query/read control codes. It never creates,
deletes, resizes or alters a journal, and it has no source-file action executor.

```powershell
.venv\Scripts\python.exe -m engine.usn_reader --checkpoint _data\usn\C.checkpoint.json --output _data\usn\baseline-saved --initialize
.venv\Scripts\python.exe -m engine.usn_reader --checkpoint _data\usn\C.checkpoint.json --output _data\usn\since-checkpoint
```

A saved C: journal ID/NextUsn baseline was created. No older checkpoint was found
in the inspected task paths, so historical changes before that baseline are not
claimed. Journal ID/range mismatches and unsupported record versions hold the
checkpoint. V2 records yield creates/deletes/data changes and paired rename/move
events by FRN; rename pairing can span checkpoint boundaries. Reports retain
filename + parent FRN, not invented complete historical paths.

Live access result: querying journal metadata works through read-only `fsutil`.
Direct raw-volume open with data-read rights returned WinError 5; the zero-rights
handle's read control path returned WinError 1. A separate `fsutil usn readjournal`
probe also returned **Error 5: Access is denied**. No elevation, UAC helper or
journal modification was attempted. `_data/usn/since-checkpoint/REPORT.md` records
HOLD and the saved checkpoint is not advanced. This is a tested parser/reader
prototype, not a successful live change-feed deployment on this host.

`--advance` is optional and only persists an owned bookmark after a complete read
and written report; partial/gapped/failed reads never advance. Production full
path reconstruction, NTFS alternate streams, NAS watching and automatic hub
triggers are not enabled.

Microsoft references:
[fsutil usn](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/fsutil-usn),
[READ_USN_JOURNAL_DATA_V1](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ns-winioctl-read_usn_journal_data_v1).
