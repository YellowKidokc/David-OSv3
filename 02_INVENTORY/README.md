# 02_INVENTORY

This is the Stage 1 registry doorway between folder profiling and classification:

```text
01_PROFILE -> 02_INVENTORY -> 03_CLASSIFY -> 04_ADAPT -> 05_TOPIC_COLLECTION
```

The implementation remains in the shared engine modules:

- `engine/registry.py` — persistent works, versions, Nabla placeholders and review history
- `engine/inventory_scan.py` — structural inventory
- `engine/fingerprint.py` — SHA-256 identity

This folder contains wrappers, not copied implementations. The registry observes source files in place and writes its SQLite/CSV/Markdown outputs under `_data/`; it does not rename, move or delete source files.

## Run

```powershell
RUN_INVENTORY.bat "C:\path\to\source"
```

```bash
./RUN_INVENTORY.sh "/path/to/source"
```

Equivalent command:

```text
python -m engine.registry scan "PATH"
```

