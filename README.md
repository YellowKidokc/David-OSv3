# David-OS v3

## Clone → setup → run

Python 3.11+ and Git are required. The clone can live in any folder, including a
folder with spaces or a network share. The virtual environment lives separately
on local disk: `%LOCALAPPDATA%/david-os/venvs` on Windows, `~/.cache/david-os/venvs`
on Linux, or `~/Library/Caches/david-os/venvs` on macOS. Each clone gets its own
stable environment. Set `DAVID_OS_VENV` to override it with a local disk path;
setup rejects network mounts on Linux and non-fixed drives on Windows.

```sh
git clone --branch cleanup/v3-consolidation https://github.com/YellowKidokc/David-OSv3.git
cd David-OSv3
python setup_env.py
python run.py -m fis --help
```

No activation or sibling checkout is required. Windows users can use `py` in place
of `python`. Re-run setup after moving the clone or updating its dependency pin.
`python run.py` uses the same local environment from any working directory; give
its absolute path when calling from outside the clone.

Copy `config.example.yaml` to `config.yaml` if you need custom paths, and set
`DAVID_OS_CONFIG` to that file's absolute path. Paths inside the YAML resolve
relative to the YAML file. Environment variables override configured paths.
`DAVID_OS_STATE_DIR`, `DAVID_OS_REFERENCE_DB`, `DAVID_OS_LEXICON`,
`THEOPHYSICS_SERIES_FOLDER` and `DAVID_OS_CANON_RULES` override the matching paths.
`THEOPHYSICS_SERIES_REGISTRY` names an explicit series workbook; matching reports
a missing workbook until one is configured. `DAVID_OS_REGISTRY` selects the central
identity SQLite database. No personal corpus or remote disk is required for setup.

API keys and service tokens come from the process environment only. For hosted
DeepSeek use `DEEPSEEK_BACKEND=api` and `DEEPSEEK_API_KEY`; the default local Ollama
backend needs no key. Never put keys in YAML, source files, launchers or a token
JSON file. The optional YAML loader rejects credential fields. `config.yaml` and
`.env` files are ignored by Git; the application does not load `.env` files.

Install test dependencies with `python setup_env.py --test`. Run checks with
`python run.py -m pytest -q`. For the Tagger CLI use
`python run.py -m Theophysics_Tagger.tools.tagger3 --help`.
For the Tagger window install tkinter through your operating system,
then use `python run.py -m Theophysics_Tagger.tools.tagger3_gui`.

Historical generated tagger CSVs are losslessly compressed under
`_archive/tagger-index/`, with SHA-256 hashes and restoration instructions.
Machine-specific folder assignments, watch profiles and search roots are archived
under `_archive/2026-11-15/machine-config`; fresh clones start with no watched roots
and search the clone itself. Configure your own roots before enabling watchers.
Archived code, audit evidence and Windows-path test fixtures retain historical
paths; they are not portable runtime defaults.

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
| `rule-brick` | Register AI work intent, inspect shared heuristic questions, and close work with a receipt |

### Rule Brick: shared AI work contract

All AI and programmatic filesystem work should consult [`rule_brick/PRINCIPLES.md`](rule_brick/PRINCIPLES.md)
and open a Rule Brick session before analysis or proposed changes. During work,
engines record evidence-backed predictions against the shared question registry;
afterward, the worker closes the session with an outcome receipt. Rule Brick is
advisory and cannot authorize rename, move, deletion, or canonization.

```powershell
rule-brick before --agent codex --intent "inspect naming and placement" --root D:\Example
rule-brick questions
rule-brick after --session SESSION_ID --status complete --outcome "report written; no files changed"
```

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

## Contributor ownership map

See [ARCHITECTURE.md](ARCHITECTURE.md) for canonical owners and the remaining identity/prediction migration boundaries. Cleanup evidence and open questions are in [_AUDIT/CLEANUP_REPORT_2026-11-15.md](_AUDIT/CLEANUP_REPORT_2026-11-15.md).
