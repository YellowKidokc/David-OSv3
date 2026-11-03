# Folder Understanding Pipeline — design

Date: 2026-10-25 · Repo: David-OSv3 · Builds on: `docs/FOLDER_UNDERSTANDING_AND_REPORT_METHOD.md`, `docs/specs/2026-10-15-folder-profile-doorway-design.md`

## Goal
Turn the "How We Understand a Folder Before We Touch It" methodology into a single, reproducible pipeline in David-OSv3. The pipeline must inspect a folder, interview the owner, classify contents along the three axes (Shape / Purpose / Position), detect anomalies, propose safe deduplication/reorganization actions, and produce a manifest + report — without modifying source files unless explicitly approved.

This design **extends existing modules** rather than replacing them. Most of the pieces already exist; the work is wiring them together and filling the gaps.

## What already exists

| Methodology step | Existing code | State |
|---|---|---|
| Step 0–1: list top level, get scope | `engine/understand.py` `scan()` | built — walks folders, counts, stores in `.data/fis_understand.sqlite` |
| Step 2: read names for signals | `engine/understand.py` `predict_folder()`, `engine/flatten_dedupe.py` `norm_folder()` | built — kind/domain inference, name normalization |
| Step 3: check existing code | `engine/fingerprint.py`, `engine/flatten_dedupe.py`, `engine/canon_sidecar.py`, `engine/gate.py`, `engine/aggregate_report.py` | built |
| Step 4: test existing code | `tests/test_fingerprint.py`, `tests/test_gate.py` | built |
| Step 5: fingerprint twice | `engine/fingerprint.py` `sha256_file()`, `text_record()`, `near_dup()` | built — exact + normalized + near-duplicate |
| Step 6: decide with written rules | `engine/flatten_dedupe.py` R1–R8 | built for flat markdown dedupe |
| Step 7: dry run first | `engine/flatten_dedupe.py` dry-run mode | built |
| Step 8: act through gate | `engine/gate.py`, `fis/gate.py` | built |
| Intake interview (Part 5) | `01_PROFILE/profile_core.py`, `profile_wizard.py`, `config/rules/onboarding_questions.v1.json` | built — 20 questions, profile writer |
| Three-axis classification | `engine/understand.py` (kind/domain/protect), `fis/classify.py` (extension class) | partial — Shape and Purpose exist, Position is implicit only |
| Anomaly detection (Part 2) | `engine/aggregate_report.py` `anomalies()`, `engine/symptoms/` | partial — overlaps with some anomalies |
| Reporting (Part 3) | `engine/aggregate_report.py`, `engine/flatten_dedupe.py` | partial — lacks facts-block + narrative split and change-since-last-run |

## The gate as the universal pre-flight matrix

The user's mental model is a **rule matrix** that every action must pass through before it touches disk. This design keeps that matrix in `engine/gate.py` and makes it the single authority for "is this action illegal/wrong?"

Key points:
- **Every mutating action is checked twice:** once when a plan/manifest is built, and again immediately before execution. The second check catches profile or file-system changes that happened after the plan was written.
- **Simple actions can call the gate directly.** You do not have to run the full folder-intake pipeline to ask "can I delete this file?" or "can I copy this here?". A lightweight CLI (`engine/folder_intake.py gate ...` or `engine/gate_cli.py`) gives a quick verdict.
- **The folder-intake pipeline generates proposals, but the gate owns approval.** No proposal is written to `MANIFEST.csv` without a gate verdict. `BLOCK` rows are surfaced immediately; `ASK` rows go into an approval queue; only `ALLOW`/`PREVIEW` rows become executable.
- **The gate reads both rule JSON and the folder profile.** Hard safety rules (system folders, secrets) live in JSON; personal boundaries (`off-limits`, `business/personal` separation, `fire-carry` files) come from the profile.

## Gaps to close

1. **Protected snapshot before any action.** The intake interview asks for "house on fire" files, but nothing zips them yet.
2. **Normalized-text fingerprinting in the scanner.** `engine/understand.py` only stores `sha256` for exact duplicates; it does not use `engine/fingerprint.near_dup()` for near-duplicate detection.
3. **Tiered check (snapshot → properties → read).** `engine/understand.py` reads 64 KB of every text file. The methodology wants Tier 1 cheap for all files, Tier 2 only for suspicious files, Tier 3 only when Tier 2 disagrees.
4. **Position axis.** Depth and parent exist in the DB, but there is no explicit inference for *where* a folder sits relative to a project root, its siblings, and its parent type.
5. **Anomaly coverage.** Several Part 2 anomalies are not detected: same title different content, copy newer than original, orphan type, version without parent.
6. **Manifest + report format.** `engine/flatten_dedupe.py` produces a CSV and a short markdown report, but not the methodology's ordered report (anomalies → biggest payoff → changes → near-duplicates → receipts) with a code-generated facts block and AI-written narrative.
7. **Gate integration with profile.** `engine/gate.py` evaluates actions against rule JSON; it does not yet load the `01_PROFILE` folder profile (`off-limits`, `business/personal` boundary, `fire-carry` files).
8. **Single orchestrator.** The user must run `profile_wizard.py`, `engine/understand.py`, `engine/flatten_dedupe.py`, and `engine/aggregate_report.py` separately. The methodology expects one flow.

## Proposed approach: one orchestrator that wires the pieces

Create `engine/folder_intake.py` as the single command-line orchestrator. It calls existing modules and adds only the missing glue.

```text
engine/folder_intake.py        # CLI + orchestration
engine/intake_position.py      # Position-axis inference (new, small)
engine/intake_anomalies.py     # Part 2 anomaly rules over the SQLite scan (new)
engine/intake_report.py        # facts block + narrative template (new)
01_PROFILE/profile_core.py     # extend: fire_carry snapshot
engine/understand.py           # extend: normalized fp, near_dup, tiered read, shape inference
engine/flatten_dedupe.py       # refactor: consume understand.py results, write full manifest
engine/gate.py                 # extend: read 01_PROFILE folder profile
engine/aggregate_report.py     # extend: change-since-last-run + biggest payoff + report template
```

### Why this approach
- It preserves the existing scanners, tests, and data formats.
- It keeps each module focused (`understand.py` observes, `flatten_dedupe.py` decides keepers, `gate.py` approves, `aggregate_report.py` reports).
- It avoids building a second FIS package; the methodology becomes a thin layer over the current engine.

### Alternatives considered
- **A. Build a parallel `fis/` subcommand.** Rejected: `fis` already has its own scan/gate/report and a separate CLI; duplicating the methodology there would fragment the codebase.
- **B. Rewrite `engine/understand.py` from scratch.** Rejected: it already captures most of the needed data; rewriting would discard existing tests and the SQLite schema.
- **C. Standalone script outside the repo.** Rejected: the methodology explicitly references `engine/fingerprint.py`, `engine/gate.py`, and `01_PROFILE/profile_core.py`, all of which live here.

## Data model additions

Extend the `.data/fis_understand.sqlite` schema in `engine/understand.py`:

```sql
-- Tier 2 properties (only for text files that look suspicious)
ALTER TABLE files ADD COLUMN norm_fp TEXT;          -- sha256 of whitespace-collapsed text
ALTER TABLE files ADD COLUMN content_words INT;     -- non-stopword count
ALTER TABLE files ADD COLUMN first_heading TEXT;    -- first # heading
ALTER TABLE files ADD COLUMN frontmatter TEXT;      -- JSON of title/version/date fields

-- Near-duplicate groups (separate from exact dup_groups)
CREATE TABLE near_dup_groups (
    scan_id INT, group_id TEXT, verdict TEXT,       -- NEAR_DUPLICATE | RELATED_VERSION
    jaccard REAL, hamming_v2 INT, paths TEXT        -- JSON list
);

-- Folder position inferences
CREATE TABLE position_inferences (
    scan_id INT, folder TEXT, parent_kind TEXT, sibling_kinds TEXT,
    nearest_project_root TEXT, depth_from_root INT,
    confidence REAL, evidence TEXT
);

-- Anomalies from Part 2
CREATE TABLE anomalies (
    scan_id INT, anomaly_id TEXT, severity TEXT, path TEXT,
    kind TEXT, why TEXT, evidence TEXT
);
```

## Algorithms

### Tiered check
1. **Tier 1 (every file):** path, size, mtime, extension, exact sha256.
2. **Tier 2 (only if):** file is text AND either (a) exact duplicate candidate, (b) name matches version/untitled/clipboard pattern, (c) size outlier, or (d) folder is flagged by shape classifier. Compute normalized fingerprint, word count, first heading, frontmatter.
3. **Tier 3 (only if):** two files have the same normalized fingerprint but different exact sha256, or near-dup candidate, or same title different content. Read full content, diff, and flag anomaly.

### Shape classification
Map `engine/understand.py` kind values onto the methodology's shape vocabulary:
- `code` + project markers → `project`
- `documents` dominant → `document`
- `pictures`/`video`/`audio` dominant → `media`
- `mixed` with many extensions and `needs_sorting` → `dump`
- `archive` or path contains archive hints → `archive`
- system/dependency folders (`SKIP_DIRS`) → `system`

### Position classification (`engine/intake_position.py`)
For each folder:
1. Find nearest ancestor with a project marker (`.git`, `package.json`, etc.) → `nearest_project_root`.
2. Record `parent_kind` from parent's shape inference.
3. Record sibling kind distribution from same-depth folders.
4. Use these to flag anomalies (e.g., `pictures` inside a `project` folder are assets, not a photo album).

### Near-duplicate detection
Reuse `engine/fingerprint.near_dup()` on Tier-2 text files. Group by verdict `NEAR_DUPLICATE` and `RELATED_VERSION`. Keeper selection uses the existing R6 rule from `engine/flatten_dedupe.py`:

```python
(not archive, numbered_folder, shallower_path, larger_text, newer_mtime)
```

### Anomaly detection (`engine/intake_anomalies.py`)
Translate Part 2 into SQL + Python rules over the scan tables:

| Anomaly | Detection |
|---|---|
| Wrong neighbourhood | file `kind` disagrees with folder `shape` (e.g., `.py` in `document` folder) |
| Copy newer than original | archive-path file mtime > non-archive file with same sha256 |
| Same title, different content | same `first_heading` or frontmatter title, different `sha256` |
| Same content, far apart | same `norm_fp` in folders with different normalized names |
| Empty/near-empty | `content_words` < 10 |
| Name says nothing | basename matches `Untitled*`, `Clipboard*`, `New folder*` |
| Content domain ≠ folder domain | file domain (from `domain_classifier`) disagrees with folder `domain` inference |
| Size outlier | file size > 10× folder median |
| Orphan type | only one file of its `kind` in a folder of a different dominant kind |
| Version without parent | `vN` filename exists but `v(N-1)` does not |

## Flows

### `engine/folder_intake.py interview <folder>`
1. Load `config/rules/onboarding_questions.v1.json`.
2. Run `profile_core.scan_evidence()` for suggestions.
3. Ask the 20 questions (CLI or GUI). Add one new question:
   - `fire_carry_files`: "If the house were on fire, which files would you carry out?"
4. Write `config/folder_profiles.json` and `.folder.fmeta` marker.
5. Immediately zip the named fire-carry files into `.data/protected_snapshots/<folder_name>_<timestamp>.zip`.
6. No scan or apply yet.

### `engine/folder_intake.py scan <folder>`
1. Load the folder profile; if missing, run with default preview-only policy.
2. Start `engine/understand.scan()` in a background thread (the methodology's interview/scan parallelism).
3. While scan runs, optionally prompt the user for any open questions from `engine/understand.questions`.
4. Wait for scan, then run `engine/intake_position.infer()`, `engine/intake_anomalies.detect()`, and near-duplicate grouping using `engine/fingerprint.near_dup()`.
5. Store everything in `.data/fis_understand.sqlite`.

### Direct gate check — any action, no scan needed
```bash
python -m engine.folder_intake gate move  C:\src.txt D:\dst.txt
python -m engine.folder_intake gate delete C:\temp\old.log
```
The gate loads the profile for the nearest known folder, evaluates the action, and prints `ALLOW`, `PREVIEW`, `ASK`, or `BLOCK` with the fired rules. No manifest is created and no disk state is read beyond the paths given.

### `engine/folder_intake.py dry-run <folder>`
1. Load the latest scan for the folder.
2. Generate proposed actions (dedupe keepers, near-dup holds, renames, moves, etc.).
3. **First gate pass:** for each proposal, call `engine/gate.evaluate()` with the folder profile.
4. Write:
   - `MANIFEST.csv` (one row per file, with action, rule, reason, **plan-time gate verdict**)
   - `ANOMALIES.csv`
   - `REPORT.md` with facts block + template narrative
5. Do not copy or move anything.

### `engine/folder_intake.py apply <folder> [--yes]`
1. Load `MANIFEST.csv`.
2. **Second gate pass:** re-run `engine/gate.evaluate()` for every row. If the verdict is worse than the plan-time verdict (e.g. a path became protected, a file appeared), stop that row.
3. `BLOCK` → skip and log.
4. `ASK` → unless `--yes` is given **and** the row still carries a clean `ALLOW` from the second pass, write to `ASK.csv` and stop.
5. `ALLOW` → execute copy/move through `engine/canon_sidecar.freeze()` so every keeper decision is recorded and non-keepers are archived, not deleted.
6. Update manifest with receipt paths.

### `engine/folder_intake.py report <folder>`
Regenerate `REPORT.md` from the latest scan/manifest, including a "what changed since last run" section by comparing to the previous scan's signature.

## Module-by-module changes

### `01_PROFILE/profile_core.py`
- Add `fire_carry_files` to the profile builder.
- Add `protected_snapshot(root, files, out_dir)` function (pure function + one disk write).
- Expose a headless `interview(root, answers_file=None)` entry point so `folder_intake.py` can run it without PySide6.

### `engine/understand.py`
- Add `norm_fp`, `content_words`, `first_heading`, `frontmatter` columns.
- Implement `tiered_read(path)` returning which tier was used and the extracted fields.
- After exact duplicate detection, run near-duplicate detection on same-size or candidate groups and write `near_dup_groups`.
- Add shape inference mapping kind → `project|document|media|data|dump|archive|system`.
- Call `engine/intake_position.infer()` and `engine/intake_anomalies.detect()` at the end of `scan()`.

### `engine/flatten_dedupe.py`
- Split into:
  - `build_manifest(scan_id, db_path, out_dir)` — reads SQLite, applies R1–R8, writes `MANIFEST.csv`.
  - `apply_manifest(manifest_path, out_dir, gate, profile)` — copies keepers, archives non-keepers via `canon_sidecar.freeze()`.
- Keep the existing standalone CLI for backward compatibility.

### `engine/gate.py`
- Add a `profile` loader that reads `config/folder_profiles.json` and the per-folder `.folder.fmeta`.
- Add rules:
  - off-limits path → `BLOCK`
  - business/personal boundary crossing → `ASK`
  - fire-carry file mutation → `BLOCK`
  - approval floor from profile (`report_only`, `suggest_only`, etc.) → `PREVIEW`/`ASK`
- Keep the function pure and fast so it can be called once per proposal at plan time and once per proposal at apply time.
- Add a thin CLI wrapper (`engine/folder_intake.py gate` or `engine/gate_cli.py`) so any tool or batch file can ask for a verdict without importing the full pipeline.

### `engine/aggregate_report.py`
- Add `changes_since_last_run(bundle, previous_bundle)` producing added/removed/changed counts.
- Add `biggest_payoff(bundle)` returning the single action that clears the most clutter.
- Add `render_markdown(bundle, out_path)` with the ordered sections from Part 3 and a visually simple bar chart (ASCII or HTML).
- Add the Part 2 anomaly kinds that are not already covered.

### `engine/intake_position.py` (new)
- `infer(scan_id, con)` → writes `position_inferences` table.

### `engine/intake_anomalies.py` (new)
- `detect(scan_id, con)` → writes `anomalies` table.

### `engine/intake_report.py` (new)
- `facts_block(bundle)` → dict of immutable counts.
- `narrative_template(bundle)` → markdown with placeholders for the AI narrative.
- `verify_numbers(narrative, facts)` → guard that flags mismatched counts.

### `engine/plan_simulator.py` (new)
- `simulate(manifest_path, profile)` — phantom-runs every action in order against an in-memory model of the file tree.
- Detects sequence-level problems the per-action gate cannot see: a later action deletes a folder that an earlier action just moved a file into, two actions write the same target path, a rename invalidates a later copy source, an action crosses a domain boundary only because an earlier action moved the source.
- Returns a `SIMULATION_REPORT.md` with passed/blocked/ask counts and a list of ordering problems.
- The simulator calls `engine/gate.evaluate()` at every step, so the same rule matrix is reused.

## CLI

```bash
python -m engine.folder_intake interview C:\Users\David\Cross-Domain
python -m engine.folder_intake scan C:\Users\David\Cross-Domain
python -m engine.folder_intake dry-run C:\Users\David\Cross-Domain --out D:\David-OS-Reports\cd
python -m engine.folder_intake simulate D:\David-OS-Reports\cd\MANIFEST.csv   # phantom-run all actions in order
python -m engine.folder_intake apply D:\David-OS-Reports\cd\MANIFEST.csv --yes
python -m engine.folder_intake report C:\Users\David\Cross-Domain --out D:\David-OS-Reports\cd
```

## Testing

- `tests/test_fingerprint.py` — already covers exact/near/short-text; keep passing.
- `tests/test_gate.py` — add cases for profile-derived `BLOCK`/`ASK` rules.
- New `tests/test_folder_intake.py` — end-to-end on a synthetic tree with:
  - exact duplicates in archive + live folders
  - near-duplicates (`Semantic_Entropy` vs `Somatic_Entropy`)
  - same title different content
  - orphan PDF in a markdown folder
  - version without parent
- New `tests/test_intake_anomalies.py` — one test per Part 2 anomaly.
- New `tests/test_intake_report.py` — facts block matches data; narrative guard catches a deliberately wrong number.

## Success criteria
- `python -m engine.folder_intake dry-run <folder>` produces `MANIFEST.csv`, `ANOMALIES.csv`, and `REPORT.md` without touching the source.
- Exact duplicates are collapsed to one keeper; near-duplicates are held for review.
- All Part 2 anomalies are detected and reported.
- The gate blocks off-limits files and asks before cross-domain moves.
- The interview writes a profile and a protected snapshot before any scan/apply.
- All existing tests still pass.

## Open questions
1. Should near-duplicate detection run on all text files, or only on same-size candidates? (`near_dup()` is more expensive than sha256.)
2. The methodology mentions `consolidate_scan.py` and `fis_dup_heuristic.py`; do these files exist under another name, or should their logic be folded into `folder_intake.py`?
3. Should the report narrative be generated by an LLM slot in this repo (e.g., DeepSeek via the API layer), or stay a template for v1?
