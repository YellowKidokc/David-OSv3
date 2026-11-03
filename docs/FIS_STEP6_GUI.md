# STEP 6: THE FIS GUI (well thought out, built to grow into David-OS)
POF 2828 | Oct 25, 2026 | from David, for GPT | builds on FIS_STEP0_APPROVAL_AND_STEP5.md

## Decision: a local web GUI, not Tk
Step 0 proposed a Tk approval table (`ui.py`). Replace it with a **local web interface** served by FIS on localhost (standard library HTTP server, or one small listed dependency), using the same plan/executor API as the CLI. Reasons:
- David's existing GUI designs are all HTML (below); build from them, don't redraw them.
- This GUI will later move into the larger David-OS / Top-of-Mind system, which is web-based (Tauri + Svelte fork). A web GUI moves over almost unchanged.
The GUI must stay independent: it talks only to FIS's own API.

## Read the existing designs first
Folder: `D:\GitHub\David-OSv3\FIS PICS HTML\` (the `FIS (1)` subfolder is a duplicate). In the Step 6 read receipt, list each file, what it shows, and keep / merge / drop:
- **River flow:** river-fis-1-scan-pick.html, river-fis-2-intelligence-mode.html, river-fis-3-advanced-mode.html, simple.html
- **Staged simple mode:** fis_simple_v2.html, fis_flow_prototype_20260617_025037_simple.html (includes Dedupe & Conflict Map and Anomaly review buckets)
- **Approval:** post-scan-executive-report.html (plain outcome, evidence map, predicted actions, review gates)
- **Design thinking:** prediction_engine_product_design.html, one-skinny-master-workflow.html, fis-walkthrough.html, files-workbench.html, pof_hub_integration_plan.html
- **Folder pages = the HTML sidecar templates:** `FIS the onr\` (1FIS, 5FIS, 6FIS, FIS.html [FABLE], fis_vault_intelligence_v3.html), with sections Semantic Capsule, Health, Files Here, Child Folders, Semantic Network / Folder Signals, Recovery Contract. These become the first entries in the Step 5c template registry.

## Design principles (apply to every screen)
1. **Plain language first, detail on demand.** Every screen opens with one sentence a non-technical person understands; evidence and tables expand below.
2. **Every decision shows its why.** Tags, classes, names, and template choices each carry their evidence, one click away.
3. **Nothing changes without visible approval.** Every screen that could change files shows "what will change" before the button, and the button names the exact action.
4. **Always reversible, always visible.** Every applied action appears in History with a rollback button.
5. **Two depths:** Simple mode (guided, River flow) and Advanced mode (full workbench). Same data, same API.
6. **Keyboard-first** (approve, reject, next, search), light and dark themes, one consistent look across screens.

## The shell (designed to grow)
- Left **icon rail** with modules. Now: **FIS**. Reserved slots for later David-OS modules (Hub/rooms, Canon, Search, Jobs), rendered as disabled placeholders so the shell's shape is set from day one.
- Top bar: current root, crawl status light, speed dial (compact), search box.
- Right drawer: the evidence/"why" panel for whatever is selected.

## FIS screens
1. **Home / Dashboard:** crawl status (current folder, done/remaining, files per minute, errors), the **speed dial** (Trickle / Background / Normal / Full + idle boost), health across roots, and counts of everything waiting for David (renames, template choices, conflicts).
2. **Scan & Pick** (River 1): choose roots and folders, see protected/blocked floors, start a scan or a crawl.
3. **Intelligence** (River 2 / staged simple mode): scan complete → file intelligence → plan ready, with the Dedupe & Conflict Map and Anomaly buckets.
4. **Plan & Review gates** (Executive Report): plain outcome, evidence map, predicted actions, review gates; approve all, per folder, or per file; the approval is bound to the exact plan hash.
5. **Advanced Workbench** (River 3 / files-workbench): full table with filters, the dry-run simulation report, per-file evidence, bulk actions.
6. **Folder Page preview:** the HTML sidecar exactly as it will be written, rendered with its chosen template; switch template; "use this from now on for folders like this" (teaching, per 5c).
7. **Templates & Rules:** the template registry and every taught rule, in plain words, editable, each showing which folders it matched.
8. **History & Rollback:** timeline of runs from the ledger; per-run and per-folder rollback with conflict detection shown before it runs.
9. **Settings:** roots, protected roots, rule packs (theophysics etc., opt-in), providers (off by default), crawler schedule and idle behavior.

## What else belongs in it (add these)
- **Notifications:** quiet tray/browser notice when a queue needs David or the crawler hits errors.
- **Search across the index** (files, tags, classes, sidecars), with results that jump to the folder page.
- **Health score per folder** over time, so David can see the drive getting cleaner.
- **A "what happened while I was away" summary** on Home after a long crawl.
- **Export:** any report or plan as HTML/CSV.

## Acceptance for Step 6
- Every screen works against the real FIS API on a test tree; no screen has a mutating button without a "what will change" preview.
- Simple mode can take a new user from picking a folder to an approved, applied plan without opening Advanced mode.
- Rollback from History restores a folder byte-for-byte (SHA-256 verified).
- The shell runs standalone, and its module slots make it obvious where David-OS modules will plug in.
