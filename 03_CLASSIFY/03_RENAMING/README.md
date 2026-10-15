# 03_RENAMING

What we call each paper. Rules: `../00_SHARED/TAG_TAXONOMY_v0.4.md`, **Part C**.
The core rule: **rename the card, not the file.** The human name lives in the sidecar; the source
filename is identity that scripts, hashes, JSON lineage and wikilinks depend on.

## Built here

**`RENAME.bat`** (in `03_CLASSIFY\`) opens the Renamer review window on `S:\PROCESSED`, or on any folder dragged onto it.

| Column | What it is |
|---|---|
| ✓ | Checked rows get renamed on **Apply**. Rows at ≥ 0.75 confidence start checked; duplicates and collisions never do |
| B · Original | The file's current name |
| C · Proposed | `DOMAIN__TYPE__words__YYYYMMDD__ST.ext` |
| D · Engine | How sure the engine is |
| E · Why | Which clue words decided it, and where they were found (name, title, folder, text) |
| F · Override | Your own name. Double-click a row to type one |

- **Rules:** `rename_rules.yaml` holds the context clue words for domain, type and status, the series prefixes that keep reading order (`gtq_05a`, `ch07b`, `p01`, `01_1`), the dropped words and the protected paths. Edit it, then press Scan again.
- **Safety:** you see a preview before anything renames. Every row is logged to `data/rename_ledger.csv`. **Undo a run…** puts everything back. Obsidian `[[links]]` inside the folder are updated to the new names, and each edited note is backed up and keeps its date. A file that changed since the scan is refused.
- **Engine score:** the top right shows how many of your decisions took the engine's name unchanged. Overrides and rejections count against it.
- **Export to Excel:** the same sheet as an `.xlsx`.
- **Engine only:** `python rename_engine.py "<folder>"` prints the proposals without changing anything.

Tested on a copy of `S:\PROCESSED` (279 files): 156 renamed, no links left pointing at old names, and the undo was byte- and date-identical.

## Filename scheme — decided 2026-10-14

**Hybrid: codes at the ends, real words in the middle.**
`DOMAIN__TYPE__words_in_lowercase__YYYYMMDD__ST.ext`, for example
`THE__ART__gtq_05a_trinity_mechanism__20260407__AC.md`. The 3-letter domain codes and 2-letter
status codes come from Kimi's live FIS engine (`file-intelligence-system\fis_namer.py`). Its
codes-only middle (`TR-DC`) is replaced by readable words. Part C.3 of the taxonomy says the same.
The older Part C.3 draft and the June FIS spec pattern are retired.

## Renaming tools that already exist elsewhere (pointed to, not moved)

| Tool | Where | What it does |
|---|---|---|
| Rename planner | `David-OSv3\engine\rename_planner.py` + `engine\config\naming_rules.yaml` | **Propose-only** name generator; thresholds 0.72 auto-approve / 0.45 queue, blended with the River preference engine |
| Fingerprint | `David-OSv3\engine\fingerprint.py` | Stable file identity — what lets a card find its source after a rename |
| FIS naming spec | `D:\DONT TOUCH BOOT UP\FIS\FIS_NAMING_SPEC.md` | Folder classes + symptom registry (S01–T04) + file pattern + rename safety rules |
| NABLA semantic naming v5.1 | `D:\DONT TOUCH BOOT UP\stratum pop up\06_engines\classification\prompts\01_NABLA_SEMANTIC_FILE_NAMING_SYSTEM_v5.1.md` | Prompt-based semantic naming system |
| Rename/organize station prompt | `Research-Acquisition\API_ALL\09_SOURCE_API_FOLDERS\Open-AI-CALL-OBS-Plugin-Final-Claude\consolidated\STATION_RENAME_ORGANIZE_PROMPT.md` | LLM station prompt for rename + organize |
| Rename worker | `Research-Acquisition\file-intelligence-hub\file_intelligence_hub\workers\rename_worker.py` | File Intelligence Hub rename job |
