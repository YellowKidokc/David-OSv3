# rename

Suggests new names for files. **It only makes suggestions**: it never renames, moves, deletes or edits anything.

- Run: `START.bat`, or `python src/run.py FOLDER [--no-recursive]` (uses David-OS `.venv`; needs PyYAML)
- Output: `data/rename/rename-proposal.v1.jsonl` (`shared/contracts/rename-proposal.v1.schema.json`). Every record has `review_state: "proposed"` plus `recovery` (the original path, name and SHA-256).
- Status: `ok` means confidence is at least 0.75 and nothing is flagged. Duplicates, name collisions, already-named and protected files, and anything under 0.75 get `needs_review`.

## Engine
`src/engine/rename_engine.py` + `rename_rules.yaml` are copied from `03_CLASSIFY/03_RENAMING` (the scheme decided 2026-10-14: `DOMAIN__TYPE__words__YYYYMMDD__ST.ext`; see `NAMING_DECISION.md`).
There's one edit: the `gate`/`ledger`/`hub` imports are optional, because only `apply()`/undo use them, and this app never calls either.

Applying names still goes through the existing Renamer review window (`03_CLASSIFY\RENAME.bat`), which has the preview, ledger, undo and link updates.

Not moved yet: FIS `naming_engine.py`, the template presets (`{domain}_{slug}_{seq}` …). It's an older scheme; it needs a decision on whether to keep it as a second engine.

Tests check that suggestions match the old engine exactly, that output follows the contract, and that the scanned folder is byte- and date-identical afterwards.
