# Topic Collection validation — 2026-10-25

- Seven tests pass: archive/trash tiers and exclusions; bounded-scan/seed reporting; verified flat copies and source-byte preservation; changed-source and selection-version rejection; filename collisions retaining separate drafts; safe HTML embedding; PDF and DOCX body extraction.
- Review UI checked in headless Edge against the real pilot: all 50 rows render, nothing selected initially, select-all/clear/filter and version-bound selection download work, no JavaScript page errors.
- Final targeted pilot: 66 eligible files inspected, 50 candidates, 47 active and 3 archive-tier matches. No scan cap reached. All five requested seed families have path-matched candidates; this does not establish canonical status or content identity of every seed.
- The pilot includes GRACE-001, Law1 Lean sources, Response/Rebellion archive, July28 corrected derivation, a Lindblad derivation, a Terminus Sui record and the justification-reset bridge. Latest source material may differ from earlier readings.
- Trash recovery is tested with a temporary .trash fixture. The live pilot did not discover a trash-tier file; no claim of restoring a deleted document is made.
- No real source collection was exported yet. Copy/export tests used temporary fixtures. No source folder deletion, rename or move, no model API calls, no canonization and no definitive paper generated.
- Anatomy spec09 and canon_guard governing implementation remain unlocated/unwired. Family analysis and FIS classification are documented follow-on stages, not asserted complete.
- Launcher interpreter check found .venv lacks PySide6. The launcher was corrected to use PATH Python, matching the existing Harvester launcher; station --help succeeds there. No dependency installation was performed.

## Native GUI (2026-10-25)

Added BACKSIDE/topic_gui.py and OPEN GUI.bat. Twelve combined engine/GUI tests pass, including a 15-level nested source rendered as a flat row with hierarchy retained, format-specific background search, preview invalidation, cancellation, flat/per-type export and source preservation. Native window launched with the saved 50-file pilot and visually observed through computer-use. Later edits add a scrollable criteria sidebar, screen-bounded sizing and a top Stop button; these will appear on the next app launch, not in the currently running process.

David then entered D: and H: and started a search himself. The process remained responsive; no completed interactive plan was present at the last check. Screenshot showed Markdown/HTML/Lean checked, Text/PDF/Word unchecked, 5000-file cap, and the prior 50-file pilot still displayed while searching. Do not treat those 50 rows as the new drive search. No input was sent to interrupt, restart or change his active search. No real source export was triggered.
