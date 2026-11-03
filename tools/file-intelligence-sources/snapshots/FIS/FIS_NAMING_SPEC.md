# FIS Naming Specification

Two separate schemas. Folders and files are classified independently and named differently.

---

## FOLDER naming schema

Folders are classified by **symptoms** (structural / content / temporal) detected by the scanner,
not by CHI master equation scoring.

### Format
```
{class}_{topic-slug}
```

### Folder classes
| Class    | Meaning                                         | Example name             |
|----------|-------------------------------------------------|--------------------------|
| project  | Has dependency markers (.git, package.json, …)  | project_fis-engine       |
| document | Mostly PDFs, Word, markdown, notes              | document_theophysics-papers |
| media    | Mostly images, video, audio                     | media_vacation-2024      |
| data     | CSV, JSON, Excel, databases                     | data_trading-backtests   |
| dump     | Mixed, unclassified, or symptom-heavy           | dump_downloads-unsorted  |
| archive  | Old / cold storage, nothing active              | archive_2023-exports     |
| system   | OS/app dependency — NEVER rename or move        | (no rename applied)      |

### Symptom registry (from folder_symptom_registry.xlsx)

Symptoms drive the folder class assignment AND trigger naming proposals.

| ID  | Category   | Symptom             | Severity | Action                       |
|-----|------------|---------------------|----------|------------------------------|
| S01 | Structural | Extension swamp     | medium   | Split by content family      |
| S02 | Structural | Version sprawl      | medium   | Diff + keep latest + archive |
| S03 | Structural | Depth explosion     | low      | Flatten + preserve in .chi   |
| S04 | Structural | Flat overload       | medium   | Classify + split             |
| S05 | Structural | Orphan sidecar      | low      | Link or quarantine           |
| S06 | Structural | Naming collision    | high     | Hash compare + disambiguate  |
| S07 | Structural | Project scatter     | high     | Manifest + hub first         |
| S08 | Structural | Phantom reference   | medium   | Report broken refs           |
| C01 | Content    | Duplicate cluster   | medium   | Compare + review keeper      |
| C02 | Content    | Format redundancy   | low      | Pick canonical format        |
| C03 | Content    | Draft graveyard     | low      | Extract gold + archive raw   |
| C04 | Content    | Document chaos      | medium   | Sort by topic/project/date   |
| C05 | Content    | Media dump          | low      | Sort by type + date + EXIF   |
| C06 | Content    | Unknown blobs       | medium   | Quarantine + manual review   |
| C07 | Content    | Encoding chaos      | medium   | Normalize to UTF-8           |
| C08 | Content    | Incomplete extract  | low      | Verify extraction + remove   |
| T01 | Temporal   | Time bomb           | low      | Flag for archive review      |
| T02 | Temporal   | Burst dump          | medium   | Group by session + classify  |
| T03 | Temporal   | Stale pipeline      | medium   | ID final outputs + purge     |
| T04 | Temporal   | Abandoned workspace | low      | Snapshot + archive or revive |

### Approval threshold (folders)
- **0–49% confidence** → no rename proposed
- **50–84%** → proposed in approval queue (user decides)
- **85%+** → auto-rename allowed only if user has enabled it in settings

---

## FILE naming schema

Files are named using a structured slug built from 5 required tags.

### Format
```
DOMAIN__precise-name__tags__date__status.ext
```

All fields use lowercase-with-hyphens. Double underscore `__` separates fields.

### The 5 required tags (always applied, no master equation)

| # | Tag          | Source                          | Example value       |
|---|--------------|---------------------------------|---------------------|
| 1 | Domain       | Detected from content/keywords  | TP, DT, CD, EV, MS |
| 2 | Content type | Extension + keyword fallback    | document, code, data, note, image, video, audio |
| 3 | Status       | File age + modification pattern | draft, active, final, archive |
| 4 | Date         | File mtime or creation date     | 2026-06-27          |
| 5 | Topic slug   | Top keywords from filename/content | coherence-death-condition |

### Domain codes (2-letter)
| Code | Domain              |
|------|---------------------|
| TP   | Theophysics         |
| DT   | Data / Trading      |
| CD   | Code / Dev          |
| MS   | Media / Sound       |
| LG   | Legal / Law         |
| TH   | Theology            |
| PH   | Physics             |
| KG   | Knowledge Graph     |
| EV   | Evidence / Research |
| GN   | General             |

### Status values
| Status  | Meaning                                      |
|---------|----------------------------------------------|
| draft   | Work in progress, not finalized              |
| active  | Currently in use, being updated              |
| final   | Completed, do not edit                       |
| archive | Old / cold, kept for reference               |
| review  | Needs human review before next action        |

### Examples
```
TP__coherence-death-condition__law10-falsification__2026-06-23__draft.md
DT__premarket-checklist__risk-rules__2026-06-23__active.xlsx
CD__fis-classifier__symptom-scanner__2026-06-27__active.py
EV__consciousness-equations__statistical-audit__2026-05-25__final.xlsx
```

### Rename safety rules
- **project_root folders** → file rename allowed with warning; move policy = copy-or-link-first
- **system folders** → NEVER rename or move
- **Files with no readable content** → no rename proposed (tag as content_type: binary)
- **Sidecar files** (.chi, .fisnote) → renamed alongside parent, never independently

---

## Sidecar file extensions

Two custom extensions — one per schema type. Both are plain text (YAML frontmatter + markdown body)
so they open in any editor, render in markdown viewers, and can be grepped or scanned by extension.

### `.chi` — file sidecar

Written **next to** each classified file.
Filename: `original_filename.ext.chi`

```
report-2026-06-27.pdf  ←  actual file
report-2026-06-27.pdf.chi  ←  sidecar (same folder)
```

**Format:**
```yaml
---
fis_id: a3f8c2d1
path: D:\DONT TOUCH BOOT UP\FIS\report-2026-06-27.pdf
domain: EV
content_type: document
status: final
date: 2026-06-27
topic: consciousness-equations
tags: [evidence, statistical-audit]
confidence: 0.84
symptoms: [C03, T01]
proposed_name: EV__consciousness-equations__statistical-audit__2026-06-27__final.pdf
approved: null
classified_at: 2026-06-27T14:33:00Z
---

File intelligence sidecar. Edit `approved: true/false` to push decision to approval queue.
```

**Scan for all .chi files:**
```
Get-ChildItem D:\ -Recurse -Filter "*.chi"
```

---

### `.fisnote` — folder manifest

Written **inside** each classified folder.
Filename: `_FIS_FOLDER_INDEX.fisnote` (underscore prefix keeps it sorted to top)

```
D:\DONT TOUCH BOOT UP\FIS\
  _FIS_FOLDER_INDEX.fisnote  ←  folder manifest
  fis_classifier.py
  fis_daemon.py
  ...
```

**Format:**
```yaml
---
fis_id: b7d4e9a2
path: D:\DONT TOUCH BOOT UP\FIS
folder_class: project
confidence: 0.96
dependency_risk: high
symptoms: []
current_name: FIS
proposed_name: project_fis-engine
approved: null
file_count: 12
classified_at: 2026-06-27T14:33:00Z
---

## FIS — project_fis-engine

**Class:** project  
**Risk:** high — contains dependency markers (.git, Python scripts, config files)  
**Action policy:** rename with warning only; never auto-move or auto-delete  

### Detected symptoms
_none — folder is well-structured_

### Allowed actions
- Rename folder (with warning)
- Add files
- Read / scan

### Blocked actions
- Move (copy-or-link-first required)
- Delete
- Auto-rename without approval
```

**Scan for all .fisnote files:**
```
Get-ChildItem D:\ -Recurse -Filter "*.fisnote"
```

---

### Extension isolation table

| Extension | Attached to | Location         | Scanner target        | Opens as  |
|-----------|-------------|------------------|-----------------------|-----------|
| `.chi`    | File        | Same folder as file | `*.chi`            | Markdown  |
| `.fisnote`| Folder      | Inside the folder   | `*.fisnote`        | Markdown  |

Both are excluded from FIS's own crawl skip list so the daemon never re-classifies sidecars.
Both are written by the daemon automatically — never need to be created by hand.
Both can be edited by hand: set `approved: true` or `approved: false` in the frontmatter
to push a rename decision into the approval queue without opening any UI.

---

## Approval queue

Every naming proposal (folder or file) must pass through the approval queue before any action.

### approval_queue.csv columns (generated by FIS, filled in by user)
```
id | path | current_name | proposed_name | schema_type | symptoms | confidence | APPROVE | notes
```

- `schema_type` = "folder" or "file"
- `symptoms` = comma-separated symptom IDs that triggered the proposal (e.g. "S01,C05")
- `confidence` = 0.00–1.00
- `APPROVE` = empty → user fills in YES / NO
- `notes` = user can type reason (feeds preference engine)

### Preference engine integration

Every row where user fills in YES or NO is appended to the preference log:
```
D:\DONT TOUCH BOOT UP\AHK\command_center\data\preferences\fis_naming_preferences.jsonl
```

The preference engine reads this log to learn David's naming style over time.
Future proposals are weighted toward patterns the user consistently approves.
