# 02_INVENTORY — hash, dedupe, UID

Step 02 of the David-OS sequence: **every file gets a fingerprint and a UID before
classification touches it.** Step 01 is `../01_PROFILE` (the doorway wizard).
Step 03 is `../03_CLASSIFY` (tagging, sidecars, naming).

## What it does

1. **Walks the folder** — every `.md`, `.html`, `.txt`, `.pdf`, `.docx` at root
   and one level deep (configurable).
2. **Hashes each file** — SHA-256, full content. This is identity.
3. **Detects duplicates** — byte-identical files grouped by hash.
4. **Flags problems** — empty files, zero-byte, corrupt names, files that
   shouldn't be here (`.lnk`, `desktop.ini`, `thumbs.db`).
5. **Assigns UIDs** — `TP-{container}-{sequence}` based on folder profile
   and file position. UID is deterministic from path + hash; re-running
   produces the same UID for the same file.
6. **Writes the inventory** — `02_INVENTORY/OUTBOX/{folder_slug}/inventory.json`
   with every file's path, hash, size, UID, duplicate group, and flags.

## Run it

```
INVENTORY.bat "D:\path\to\folder"
```

or drag a folder onto `INVENTORY.bat`, or run it bare and pick a folder.

Reads the folder profile from `config/folder_profiles.json` (written by
01_PROFILE). If no profile exists, it still runs but UIDs use `TP-UNK` as
the container code and a warning is logged.

## What it feeds

- `03_CLASSIFY` reads the inventory to know what files exist, skip dupes,
  and carry UIDs into sidecar cards.
- The duplicate report feeds human decisions: which copy is canon?
- The UID registry feeds the eventual junction table connecting papers to
  Bible verse UUIDs.

## No mutations

This step is **read-only on the source folder**. It writes only to its own
OUTBOX. No renames, no moves, no deletes. The gate (`engine/gate.py`) is
not consulted because nothing mutates.

## Output shape

```
OUTBOX/{folder_slug}/
  inventory.json        — the full manifest
  duplicates.json       — grouped by hash (only groups with 2+)
  problems.json         — flagged files
  inventory_report.md   — human-readable summary
```
