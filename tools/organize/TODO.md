# Organize GUI — TODO

Notes for next session. Nothing here is urgent.

## 1. Undo last apply  (~20-30 min)  ← do this one
Make the File Intelligence **Apply** (and later Quick Sort / Workflow runs) safe to press.
- When Apply renames/moves a file, write a ledger event recording the exact
  `old path -> new path` with a `batch_id` (= the apply timestamp), using
  `ledger.LedgerWriter` directly — do NOT depend on the background watcher being on.
- Add an **"Undo last apply"** button that reads the latest `batch_id` from the
  master ledger and reverses each move (new -> old), skipping any whose source is gone.
- The ledger already stores both ends of every move, so the data is ready.
- Code anchor: `TODO(undo)` comment above `OrganizeGui._fi_apply` in `organize/gui.py`.

## 2. Commit the work to git
Everything (gui.py, fileintel.py, ledger.py, settings.py, LAUNCH_GUI.bat,
WATCH_HISTORY.bat) is currently uncommitted. One commit makes it safe.

## 3. Bring up FIS on localhost:8420
Turns the File Intelligence grid from offline cleanup into real names + certainty
+ the NLP fingerprint number. The GUI auto-detects it once it's running.

## 4. Longevity
- Fold the `--self-test` checks (`organize/gui.py`, `organize/ledger.py`) into the
  repo's real `tests/` so future edits can't silently break the GUI.
- Add a soft file-count cap / warning to the History watcher so pointing it at a
  huge folder (e.g. all of Documents) doesn't chug.
