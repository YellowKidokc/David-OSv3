# 05 · Topic Collection

Builds a topic-focused review plan, then copies an explicitly selected set into a flat working collection. Reuses `gui/drive_harvester.py` matching, export collision handling, SHA-256 verification, sidecars and manifests; PDF/DOCX extraction delegates to `engine/text_extractor.py`. No model calls, source moves, source deletions or canonical winner selection.

## Doorway

Double-click `OPEN GUI.bat` for the native app. Choose source roots, formats and match fields, then search. The paper list is flat; the Original folder structure tab retains the matched source hierarchy. Sorting includes best match, name, file type, nesting, recovery tier and original folder. Select results, preview the destination layout, then copy. Flat and per-file-type layouts are available; source nesting is not reproduced in flat mode.

Search and export run in background threads with Stop controls. The GUI can load a saved plan or the Grace pilot. Loading a plan starts no scan and copies nothing. A new search captures the chosen criteria; existing results remain visible until completion and are labeled as previous-plan results. Changing the destination/layout or selection invalidates the copy preview. Review original paths, tiers and checksums in Preview/activity before export.

Copy `BACKSIDE/request.example.json` into INBOX, replace its root placeholder with the folders/drives to search, then run `1 RUN HERE.bat`. Results go into a new OUTBOX run folder. `REVIEW.html` shows candidate files and lets you select a subset and download `selection.json`. Nothing is collected merely by reviewing the page.

The launcher uses the same PATH Python as the existing Drive Harvester launcher. It needs PySide6 because it reuses that module; PDF/DOCX extraction needs pypdf and python-docx. These are present in the tested system Python. The repository's current .venv lacks PySide6, so it is deliberately not selected by this launcher. No new environment was installed or changed.

Use the same Python interpreter from the repository root to collect your selection:

```
python 05_TOPIC_COLLECTION/BACKSIDE/run.py --collect PATH_TO_PLAN_JSON --selection PATH_TO_SELECTION_JSON --out NEW_COLLECTION_DIRECTORY
```

The collection contains flat `FILES`, source sidecars, the original metadata text when present, a timestamped CSV export manifest, `PROVENANCE.json` and the review page. Original paths/roots and recovery tiers remain in provenance. The selected sources are rehashed before export, and copied bytes are verified by the existing exporter. Filename collisions receive suffixes. Partial exports are recorded, never passed off as complete. Failed or interrupted copies remain identified for review.

## Recovery and coverage

Archive directories are searched. Obsidian `.trash` is searched by default as a separate `recovered_from_trash` tier; set include_trash false to exclude it. Windows recycle bins, OS/dependency/cache directories and symlinks/junctions remain excluded. This does not restore deleted files from Windows recycle storage or inspect ZIP contents.

PDF and DOCX are included by default. Image-only PDF text needs OCR, and legacy .doc is not supported here. Missing/empty extraction is marked rather than treated as proof of no topic content. Drive Harvester keeps its existing 400,000-character content limit and 25MB file-size ceiling. The plan records exclusions, errors, limits and partial scope. Search terms are discovery cues, not claims of conceptual equivalence. Match scores are heuristics, not probabilities.

Seeds are filename/path smoke tests; a candidate_found result does not verify the manuscript's content or canonical status. A missing seed only means not found within the chosen scope and limit. Start with selected roots and widen deliberately; do not label a bounded pilot a complete Grace corpus.

## Remaining stages

Exact duplicate groups use byte SHA-256; no drafts or reading-level variants are dropped. Existing publication-family scanners can subsequently review the flat FILES folder. Full FIS naming/YAML, the anatomy pass (spec 09), canon_guard integration and drafting the definitive article are not claimed implemented by this station. Their source specifications and governing rulings must be located first. Relative links/images are not rewritten during flat export, so a publishing package needs a later asset/link pass.

Runtime INBOX/OUTBOX are ignored by Git. The numbered station itself is portable and source-preserving. The original Drive Harvester GUI remains available.
