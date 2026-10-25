# FIS standalone

Offline folder intelligence, explainable rename proposals, and reversible HTML
folder memories. The package imports only Python's standard library. The hub,
Forge, Top-of-Mind, NAS and AI services are not required.

## Start here

From the repository, run:

```powershell
python -m fis --state .data/fis-live serve
```

Open **http://127.0.0.1:43107**. In **Scan & Pick**, enter a folder, preview its
permissions, and authorize that root. A scan leaves source files unchanged. Create
a plan, review the names, select the exact rows, then approve and apply. History
offers rollback with a conflict preview.

To install FIS independently, use `python -m pip install ./fis`. This installs the
`fis` command and packaged rules, templates shell, and preference learners without
installing David-OS dependencies. Installing from source needs setuptools available
locally or from the package registry; everyday FIS operation is offline.

## Always running on Windows

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/fis/INSTALL_BACKGROUND.ps1
```

This creates the current user's **FIS Background** sign-in shortcut and starts a
hidden supervisor. It provides a notification-area icon and restarts its child
Python server if the child exits. No administrator, stored password, or network
service is needed. It starts when you sign into Windows, not before sign-in, and
cannot work while the machine is off. You do not need to leave a browser open.

The tray menu opens FIS, opens rename review, pauses/resumes background work, or
exits until the next sign-in. A quiet balloon appears when the review queue changes,
at most once per 15 minutes; clicking opens review. Windows notification settings
can suppress balloons. The tray icon remains the persistent entry point.

The service checks selected roots every 15 minutes. No drives are selected by
default. Roots without HTML automation produce proposals only. Explicitly enabling
HTML automation permits the crawler to write folder pages and archive legacy notes
inside that root; it never approves source renames. Unchanged folders do not churn
pages or archives. Trickle, Background, Normal and Full pace scans; Windows thread
background mode reduces CPU and I/O priority. Idle boost uses Windows idle time.
Pause persists across restarts. Folder checkpoints survive process exit.

The state location defaults to `.data/fis-live` for the Windows launcher. Move the
repository or interpreter? Rerun the installer to refresh its paths. To disable
startup reversibly, move the `FIS Background.lnk` shortcut out of your Windows
Startup folder into an archive. An existing shortcut is backed up when reinstalling.
Logs and the installation receipt live in `<state>/logs/` and `startup.json`.

## The four daily commands

```powershell
fis --state D:\FIS_STATE scan D:\MyFolder
fis --state D:\FIS_STATE plan D:\MyFolder
fis --state D:\FIS_STATE apply PLAN_ID --approval APPROVAL_TOKEN
fis --state D:\FIS_STATE undo RUN_ID --preview
```

Authorize a root with `fis root <folder>`; optionally add `--enable-html` for
background HTML/legacy-note archival. CLI approvals use
`fis approve PLAN_ID --hash EXACT_PLAN_HASH` and return the single-use token for
`apply`. Omit `--preview` on `undo` to execute the checked rollback. Additional
commands: `report`, `search`, `history`, `export`, `preferences`, `crawl`, and
`background`. GUI and CLI call the same service and executor.

Keep state/archive outside source trees **on the same filesystem volume**. Moves
to a different volume are deliberately refused before mutation; FIS does not
implement cross-volume copy-and-delete. Use a separate state directory/service
instance and port when processing another volume.

## Rename review and learning

Review shows original name, proposed name, evidence, holds, and an advisory learned
preference score. Nothing starts pre-approved. Edit proposed names, choose
**Preview edited names**, then review the new immutable plan before applying.
Rejection is durable and teaches FIS without changing a file. Successfully applied
corrections teach both rejection of the old suggestion and acceptance of the new
one. Duplicate requests do not train twice. Automated HTML work does not train
rename preferences.

The existing dependency-free **frequency** and **Markov** learners were extracted
from `engine/preference/` and adapted to FIS-owned state. Predictions blend ready
engines after their original warm-up thresholds (4 and 10 examples). They never
grant filesystem approval. The learning history is stored in SQLite and can be
exported at `/api/preferences-export` in the older ensemble's decision format.
River/sklearn/VW/recommenders are not imported by this offline distribution; legacy
model files and old decision logs are preserved and not silently retrained or
imported. Template teaching is a separate readable rule/confirmation process.

## Preservation and receipts

Each source is byte-hashed with SHA-256; duplicate paths remain separate instances.
Plans are immutable and approvals bind their exact hash, row selection and policy.
Every mutation has a durable intent record before it starts. Recovery checks bytes,
refuses later edits and occupied restore paths, and is idempotent. Roll back newer
overlapping runs first. Generated HTML moves to quarantine on undo; old notes and
pre-existing HTML return from the archive. FIS contains no file deletion calls.

HTML pages embed complete original `.fisnote` bytes as base64 and escape their
display text. Their source notes move into the run archive with mirrored relative
paths. Template choices that lack a confident rule wait for a human choice. The
initial registry references the six preserved `FIS the onr` designs; its current
safe shared renderer uses their common sections with template-specific accents.

The Rust kernel under `tools/fis-intelligence/rust` is optional and preserved.
Its seven symptom rules now enrich the Python inventory without a second hash
pass. Kernel BLAKE3 hashes are never treated as SHA-256 identities. See
`docs/FIS_RUST_REUSE_RECEIPT.json` for the source comparison; historical test output
is not represented as a current scan.

Text extraction is currently bounded UTF-8 for listed formats; PDF/DOCX and other
binary formats receive metadata-only classification. Linked Markdown rename
proposals are held rather than rewriting links automatically. These limits remain
visible in the index/review and do not authorize guesswork. Full-screen browser
interaction and appearance verification remain separate from API acceptance.

## Verification

```powershell
python -m unittest discover -s tests -p test_fis_standalone.py -v
python -m unittest discover -s tests -p test_fis_background_preferences.py -v
cargo test --locked --offline --manifest-path tools/fis-intelligence/rust/Cargo.toml
```

Tests cover independence, denied networking, round-trip hashes, duplicate
instances, pre-existing HTML/notes, exact approval, later edits, actual process
exit during apply, checkpoints, template confirmation, preference learning,
pending names after crawler HTML apply, and incremental no-op passes. All mutation
tests run on copies or temporary fixtures. A small real-folder-copy receipt is in
`docs/FIS_FOUNDATION_ACCEPTANCE.json`; it is not a universal safety guarantee for
arbitrary drives.
