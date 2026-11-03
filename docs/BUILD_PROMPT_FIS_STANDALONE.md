# BUILD PROMPT: FIS, the standalone folder pipeline
POF 2828 | Oct 25, 2026 | for GPT / Codex (long coding session)

## Goal
Turn David-OSv3's scattered file-intelligence pieces into **one independent program, FIS**, that walks folders and runs four stages in order: **tag → classify → rename → sidecar.** FIS must stand on its own: no dependency on the hub, Forge, Top-of-Mind, the theophysics engine, the NAS, or the internet.

## Repo
D:\GitHub\David-OSv3, branch `wip/fis-snapshot-2026-10-23`. Create branch `fis-standalone` from it. Small commits per step.

## STEP 0: Read receipt, then STOP
Read and report what already exists, what each piece does, and where it overlaps:
- 03_CLASSIFY/ (00_SHARED incl. TAG_TAXONOMY_v0.4.md; 01_SIDECARS incl. docs/SIDECAR_CLASSIFICATIONS.md; 02_CLASSIFICATION; 03_RENAMING; ZZZ_DELETE; the .bat launchers)
- file-intelligence-system/ (fis_classifier.py, fis_namer.py, fis_folder_memory*.py, structural_evidence.py)
- engine/ pieces named in commit 46bf081: understand, symptoms, path_write_policy, flatten_dedupe, quality_score, term_closure
- the safety gate (commit 19cd17e: fail-closed registry, blocked floors, override token on ASK)
- gui/ (fis_control_surface, fis_scanner_gui, filetagger_gui, fis_search_workbench), tools/fis*, agents/filetagger.py, agents/foldertagger.py
- docs/: ARCHITECTURE.md, FIS_UNDERSTAND_PIPELINE.md, FOLDER_UNDERSTANDING_AND_REPORT_METHOD.md, INDEPENDENT_WORKBENCHES.md, SCHEMA.md, FIS_TEMPLATE_v2.1.0/
- the existing .fisnote sidecar format (sample several real ones)
Then propose the package layout and list every import that ties FIS to something outside it. **Stop for David's approval.**

## STEP 1: One package, cut loose
- New top-level package `fis/` with submodules `scan`, `tag`, `classify`, `rename`, `sidecar`, `gate`, `index`, `report`, `cli`.
- Move or wrap the existing working code into it. Don't rewrite what works; consolidate it.
- **Independence test:** `fis/` may import only the Python standard library and a short, listed set of third-party packages. A test fails the build if any module imports hub, engine (theophysics), services, Forge, or Top-of-Mind code.
- All theophysics-specific rules (canon namespaces, axiom inventory, master equation intake) become **optional rule packs** in config, loaded by name, never hard-wired.
- Optional AI help (e.g. classification suggestions) goes behind a provider interface that is **off by default**. FIS runs fully offline without it; a Forge adapter or Ollama adapter can be plugged in later.

## STEP 2: The four stages, in order
For each file in the chosen folders:
1. **Tag:** apply the tag taxonomy (v0.4), from content, structure, path, and existing sidecars. Record why each tag applied.
2. **Classify:** assign the file's class from the classification schema, with a confidence and the evidence used.
3. **Rename:** propose a new name from the naming rules (fis_namer). **Proposals only**; nothing is renamed until approved (step 3).
4. **Sidecar:** write the `.fisnote` sidecar beside the file, recording tags, class, evidence, old and new name, content hash, and the run id. The sidecar travels with the file; it is the file's memory.

## STEP 3: Safety (non-negotiable)
- **Dry run is the default.** Every run first produces a plan: a table of proposed tags, classes, renames, and sidecars.
- **Approval gate:** renames apply only after David approves the plan (all, per folder, or per file). Keep the existing fail-closed gate and blocked floors.
- **Nothing is ever deleted.** Anything flagged for removal moves to a quarantine folder (ZZZ_DELETE pattern).
- **Undo:** every applied run writes a ledger; `fis undo <run-id>` restores every name and removes that run's sidecars.
- **Hash identity:** each file is tracked by content hash, so a moved or renamed file is recognized as the same file.

## STEP 4: Interface
- CLI: `fis scan <folder>`, `fis plan <folder>`, `fis apply <plan-id>`, `fis undo <run-id>`, `fis report <folder>`, `fis search <query>`.
- One simple local GUI (reuse the best of the existing control surface) showing the plan table with approve/reject per row.
- SQLite index of everything FIS has seen (path, hash, tags, class, sidecar, history).

## Acceptance
- On a test copy of a real messy folder: scan, plan, approve, apply, then undo restores everything exactly (verified by hash).
- The independence test passes: no imports outside the allowed list.
- Runs fully offline with AI help disabled.
- Existing tests still pass; new tests cover each stage, the gate, quarantine, and undo.
- README explains install and the four commands a person needs.

## Rules
- Delete nothing in the repo; move superseded code to an `_archive/` folder with a note.
- If something can't be done, say exactly what and keep building the rest.
