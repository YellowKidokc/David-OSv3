# David-OS v3
## Personal Infrastructure System

One SQLite database. One FastAPI server. Port 10000.

### Quick Start

```bash
cd D:\GitHub\David-OSv3
pip install -e . --break-system-packages
dos-api --port 10000
```

### What It Does

- **File Intelligence** - watches folders, classifies files, suggests renames, review gate
- **Message Hub** - unified inbox for AI collaborators (Claude, GPT, Kimi, Gemini, Codex)
- **Memory Store** - vector-embedded searchable memory
- **Multi-Node** - desktop/NAS/laptop coordination with heartbeat

### Commands

| Command | What |
|---|---|
| `dos-api` | Start the hub API server |
| `dos-worker` | Start the job queue processor |
| `dos-watch` | Start native file watcher |
| `dos-poll` | Start polling file watcher |
| `dos-health` | Print node health JSON |
| `dos-top` | Top-of-Mind CLI (post messages, search memory) |

### Observe-only Master Equation intake

```bash
python scripts/master_equation_intake.py "C:\theophysics\OPUS\Master Equation" --output "D:\analysis\master-equation"
```

This command preserves every source location, groups exact duplicates by
SHA-256, maps corpus lanes and all ten variables, flags conservative filename
contamination indicators, and writes SQLite/CSV/JSON/Markdown receipts. It
never moves, renames, deletes, shortens, or rewrites source files.

The same analyzer is available as an independent standard-library GUI:

```text
gui\START_MASTER_EQUATION_INTAKE.bat
```

It does not require the API server, worker, watcher, or the other GUIs.

### Architecture

Stage 1 inventory/registry: `python -m engine.registry scan "PATH_TO_SOURCE"`.
The SQLite source of truth and generated master list live in `_data/`.
See [Stage 1 registry](docs/STAGE1_REGISTRY.md) for scope, Nabla proposals and checks.

The FIS Folder task lives at `D:\GitHub\pipeline-workflows\FIS_FOLDER` and
serves folder HTML, scoped checks and optional DeepSeek chat through the existing
Drive Brain master. Its backend is `folder_hub/`; its packet README documents
the pilot, local scopes and pending Mana handoff.

See `docs/ARCHITECTURE.md` for the full explainer.

The proposed intake boundary and incremental CocoIndex-to-Lean-4 tagging design
is documented in [docs/COCOINDEX_LEAN4_ADMISSION_AND_TAGGING.md](docs/COCOINDEX_LEAN4_ADMISSION_AND_TAGGING.md).
The implementation prompt for the missing admission contract is
[docs/DAVID_OSV3_STAGE2A_ADMISSION_MANIFEST.md](docs/DAVID_OSV3_STAGE2A_ADMISSION_MANIFEST.md).

### Stage 2B sidecars and approved renames

After Stage 2A has populated the registry `admission` table:

```powershell
python -m engine.sidecar_writer generate "PATH" --dry-run
python -m engine.sidecar_writer generate "PATH" --report
python -m engine.rename_applier preview "PATH"
python -m engine.rename_applier simulate "PATH" --out rename-simulation.json
python -m engine.rename_applier apply "PATH" --plan rename-simulation.json --confirm
python -m engine.rename_applier undo "CHANGESET_ID"
```

`sidecar_writer` records classification and rename proposals in `.fis.json`.
`rename_applier` refuses `HOLD`/`EXCLUDE` files and requires an exact saved
simulation plus an explicit `apply --plan ... --confirm` command. The optional `--me-enrich --me-intake-db PATH`
arguments add Master Equation intake metadata without changing the observe-only
intake analyzer.
