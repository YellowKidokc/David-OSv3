# APPROVAL OF STEP 0 + STEP 5 ADDITION
POF 2828 | Oct 25, 2026 | from David, for GPT

## Step 0: APPROVED
The proposed `fis/` layout and package boundary in FIS_STANDALONE_STEP0_READ_RECEIPT.md are approved. Proceed with Steps 1-4 as written, with these required fixes from your own safety findings built in from the start:
- A positive, plan-bound approval for every mutation. PREVIEW never mutates. Confidence is never approval.
- Durable pre-operation ledger records, unique run ids, idempotent undo, and recovery from partial failure.
- Undo detects conflicts: it refuses to restore over a file edited after apply, and reports it.
- Malformed configuration can never bypass a hard block, override token or not.
- No unlink anywhere in FIS. `wipe_existing_fisnotes` and `cleanup_stale_file_notes` are not reused; anything removed from a folder moves to quarantine.

## STEP 5 (after Steps 1-4 pass acceptance): background crawl, HTML sidecars, templates

### 5a. The crawler
- A background worker that walks configured roots folder by folder and runs scan -> tag -> classify -> sidecar on each folder. **Renames are never applied by the crawler**; it only queues rename proposals for David to approve in the GUI.
- Runs only while the computer is on; resumes where it stopped after a restart (folder-level checkpoint).
- **Speed dial** (GUI slider), from "trickle" to "full": controls files per minute, pause between folders, and CPU/disk priority. Presets: Trickle (barely noticeable), Background, Normal, Full. Optional rule: automatically speed up when the machine is idle and slow down when David is active (reuse idle detection from Rust_Idle_Runner's design, not its code).
- Skip list and protected roots honored exactly as the gate defines.

### 5b. HTML sidecars replace .fisnote
- In each processed folder, write one HTML sidecar (the folder's page) plus per-file entries, generated from the index.
- **Old .fisnote files are never deleted.** For each folder: read every .fisnote, carry its full content into the new HTML (nothing lost), then move the .fisnote into the run's archive (mirrored path under a central archive root), recorded in the ledger. Any folder can be rolled back to its exact prior state.
- Respect the existing path_write_policy (generated sidecar writes are currently disabled globally); add an explicit, reviewed policy that enables HTML sidecars only under approved roots.

### 5c. HTML templates, chosen by rule, taught by David
- A template registry: each template has an id, a description, and match rules (folder profile, dominant file types, tags, class, path patterns).
- The crawler picks a template per folder by rule, with a confidence. Low confidence -> queue the folder for David's choice instead of guessing.
- **Teaching:** when David overrides a template choice in the GUI, FIS records the override as a candidate rule ("folders like this get template X"), shows it, and applies it after David confirms. Rules are plain, readable config, never hidden weights.
- Start with the existing HTML in the repo (FIS_TEMPLATE_v2.1.0, the FIS PICS HTML set) as the first templates; list them in the read receipt for David to name and keep or drop.

### 5d. The GUI
One window, same plan/executor API as the CLI:
- Crawl status: current folder, folders done/remaining, files per minute, errors.
- The speed dial and pause/resume.
- Queues to review: rename proposals, low-confidence template choices, conflicts.
- Template chooser with "use this from now on for folders like this."
- Per-folder rollback.

### Acceptance for Step 5
- On a copy of a real folder tree with existing .fisnote files: crawl at Trickle, then at Full; every folder gets an HTML sidecar; every old .fisnote is in the archive with its content present in the HTML; a full rollback restores the tree byte-for-byte (verified by SHA-256).
- Killing the crawler mid-run and restarting resumes cleanly with no duplicated or lost work.
- A taught template rule changes the choice on the next matching folder.
