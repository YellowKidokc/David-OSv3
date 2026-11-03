# Install — 02_INVENTORY + BATCH_ALL

## Copy these into David-OSv3

```
02_INVENTORY/           →  D:\GitHub\David-OSv3\02_INVENTORY\
  README.md
  inventory_core.py
  run.py
  INVENTORY.bat

BATCH_ALL.py            →  D:\GitHub\David-OSv3\BATCH_ALL.py
BATCH_ALL.bat           →  D:\GitHub\David-OSv3\BATCH_ALL.bat
```

## No dependencies

Pure stdlib Python. No pip install needed. Uses the same Python
that already runs 01_PROFILE and 03_CLASSIFY.

## Test single folder first

```
cd D:\GitHub\David-OSv3
python 02_INVENTORY\run.py "C:\Users\David\Documents\faiththruphysics.com\Arguments\01_GOD_IS"
```

Check `02_INVENTORY\OUTBOX\` for the inventory report.

## Run the full batch

```
cd D:\GitHub\David-OSv3
python BATCH_ALL.py
```

Default folders (edit in BATCH_ALL.py):
- O:\_Theophysics_v5
- C:\Users\David\Documents\faiththruphysics.com
- C:\theophysics
- D:\GitHub\David-OSv3\_FIS_ROOT_SIDECAR_ARCHIVE\EVIDENCE

Single folder:
```
python BATCH_ALL.py --folder "D:\some\path"
```

Custom list:
```
python BATCH_ALL.py --folders my_folders.json
```

## Pipeline order

```
01_PROFILE  →  04_ADAPT (if legacy)  →  02_INVENTORY  →  03_CLASSIFY (manual)
```

02_INVENTORY is read-only on source folders. All output goes to
`02_INVENTORY\OUTBOX\`. Nothing is renamed, moved, or deleted.

## What's still missing

1. **02_INVENTORY → 03_CLASSIFY bridge**: the inventory UID needs to flow
   into the sidecar card as a new field. This is a one-line addition to
   the sidecar writer when it gets built.

2. **Container code mapping**: `CONTAINER_CODES` in `inventory_core.py`
   needs to cover every `folder_class` value that 01_PROFILE assigns.
   Add entries as new folder classes appear.

3. **01_PROFILE run.py**: the batch runner calls `01_PROFILE/run.py` but
   that script may need a `--non-interactive` flag for batch mode (skip
   the 20-question wizard, use scan evidence only). Check if it exists.

4. **04_ADAPT run.py**: same — the batch runner calls it but it may
   expect interactive input. Needs a batch-mode flag.

5. **The watcher**: after the batch is done, a filesystem watcher
   (nerve or a small Python daemon) monitors working folders and runs
   the pipeline on new files. Build this AFTER the batch proves the
   pipeline works.

## Rust port notes

inventory_core.py is deliberately simple:
- No classes with inheritance
- No frameworks
- Pure functions: path in, data out
- All data is plain dicts/lists (JSON-shaped)
- SHA-256 is the only crypto (available in every Rust crate)
- The gate.py comment already mentions "future Rust port" (spec §8)

When the shape is locked, port inventory_core.py to Rust first — it's
the tightest module and the most performance-sensitive (hashing large
file sets). BATCH_ALL.py becomes the Rust orchestrator.
