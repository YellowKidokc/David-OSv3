# DAVID-OS v3 — BUILD BRIEF: STAGE 1 (INVENTORY → REGISTRY)
**For: the standby dev on David-OSv3**
**From: David (POF 2828), drafted by Fable — 2026-11-01**
**Scope of THIS brief: Step 1 only (Inventory + Registry). Do not build Steps 2–3 yet.**

---

## 0. READ FIRST (don't skip — the plan already exists on disk)
- `03_CLASSIFY\README.md` — "Order of operations" (end of file) lists 5 steps
  with build status. We are building **Step 1 (Inventory)** and the **registry
  it writes into**. Steps 4 (Review) and 5 (checker) are already built; do not
  touch them.
- `03_CLASSIFY\00_SHARED\TAG_TAXONOMY_v0.4.md` — THE rulebook. Part A = closed
  tag vocabulary, Part B = sidecar schema (`mim.v1` + `canon_status`), Part C =
  naming. Stage 1 does NOT tag or rename; it only inventories. But it must emit
  fields the later steps will fill, named exactly as the taxonomy names them.
- `engine\inventory_scan.py` (11 KB, EXISTS) and `engine\fingerprint.py`
  (6.4 KB, EXISTS) — the near-complete pieces. Read both before writing anything.
  The job is largely to finish and wire these, not greenfield.

## 1. WHAT STAGE 1 MUST PRODUCE — the Registry (the master document)
A single, incremental registry that answers, for the whole corpus:
**what files exist, which are byte-identical, which are versions of one work,
and which work each belongs to** — WITHOUT moving, renaming, or deleting
anything. Inventory in place. (This is the "document registry before a document
sorter" principle: identity first, classification later.)

Three distinct record types — a FILE, a VERSION, and a WORK are not the same
thing (one paper may be 6 files = 2 versions = 1 work):

- **Files** — one row per physical file: full path, drive, size, mtime, sha256
  (byte hash), extracted-text sha256, extension, readable? (yes/no/failed),
  first-seen, last-seen.
- **Works** — one row per distinct intellectual work: permanent Work ID
  (`W000123`, never reused), series code (2–5 chars, e.g. `MIM`), paper number,
  display code (`MIM-019`), preferred title, preferred-version pointer.
- **Versions** — one row per revision of a work: version id, which files carry
  it, supersedes, reason-preferred (blank for now).
- **Review Queue** — one row per unresolved call (proposed duplicate group,
  proposed work grouping, extraction failure, **proposed Nabla vector**).
  Nothing auto-decided.
- **Nabla** — one row per distinct work/version: the six filing fields, all ten
  vector values (G M E S T K R Q F C, each 0 or 3), the computed signature, the
  per-variable confidence, the one-sentence decode, protocol version, and
  classifier/model + date. See §1b.

### 1b. NABLA CLASSIFICATION (proven portable 2026-11-01 — build it into Stage 1)
Each work gets a Nabla address — a compact, scannable profile so an AI can
decide what to open before opening it. The deterministic core already exists and
is placed: `03_CLASSIFY\00_SHARED\nabla\nabla_atlas.py` (read its README first).

How it wires into the registry:
- The tool is DETERMINISTIC for encode/decode/signature — call it, don't
  reimplement it. `python nabla_atlas.py address input.json` returns the full
  record (address, filename_safe, signature); `decode "<addr>"` reverses it.
- The ten-variable VECTOR (what the document IS) is the only judgment part. In
  Stage 1 it is PROPOSED with per-variable confidence and queued for review —
  never auto-approved, exactly like the duplicate/work groupings. An approved
  vector survives the next run untouched.
- Store the full Nabla record as columns on the per-work record (one source of
  truth), so the FIS/HTML display and the JSON are generated from the same row
  (spec §7). Do NOT keep a separate Nabla spreadsheet.
- Honesty firewall (carry verbatim): a valid signature proves the ENCODING is
  consistent, never that the classification is accurate or the claims true;
  `E` scores disorder OF THE ARTIFACT, not its subject (a clear paper about
  brokenness is E0); confidence is stored separately and never makes a document
  disordered; 0/3 stored scores and any 1–3 working ratings are different
  systems — never mixed, always provenance-tagged.
- KNOWN CODE GAP to fix first (LOCAL): `Filing.validate()` does not validate the
  `audience` field — add an `AUDIENCES` set and the `require(...)` line before
  relying on it.

OUTPUT FORMAT: write BOTH
  (a) a SQLite registry `_data\registry.sqlite` (tables: files, works, versions,
      series, nabla, review_queue, change_log) — the source of truth; and
  (b) exports: `registry_works.csv`, `registry_files.csv`, and an Obsidian
      markdown view `REGISTRY_MASTER.md` (the human inspection surface — the
      "one master list of all the papers" David asked for). The Works view
      shows each work's Nabla address inline.
The SQLite is canonical; CSV/MD are generated from it so competing programs
never edit separate spreadsheets.

## 2. EXACT STEPS (in order)
1. **Walk the roots.** Take a list of root paths (start with ONE test folder,
   see §4). For every file: record path, size, mtime, extension.
2. **Hash bytes.** sha256 of each file → the Files table. This is the ONLY
   mechanically-certain duplicate signal. Identical byte-hash = exact duplicate;
   group them, do not delete — propose the group in Review Queue.
3. **Extract text.** For .md/.txt read directly; for .pdf/.docx use the existing
   extractor if one is wired (check `engine\`); if extraction fails, record
   `readable=failed` and still list the file — NOTHING disappears silently.
4. **Hash text.** sha256 of normalized extracted text → text-equivalent copies
   (same content, different format/export). Propose as a version group, not a
   deletion.
5. **Propose works & versions.** Cluster files whose text-hash matches (same
   version) and whose titles/paths strongly overlap (same work, different
   version). These are PROPOSALS → Review Queue. A newer mtime alone never wins;
   record the evidence, let a human pick preferred-version later.
6. **Assign IDs.** Mint a Work ID for each proposed work; assign/scan a series
   code. Register series codes centrally so two series can't collide; keep old
   names as aliases.
7. **Propose Nabla address.** For each work (using its preferred version's
   extracted text): propose the six filing fields + the ten-variable 0/3 vector
   with per-variable confidence, call `nabla_atlas.py address` to get the
   signature and full record, store it in the `nabla` table, and queue the
   vector in Review Queue as a PROPOSAL. Deterministic parts (signature, decode)
   come from the tool; only the vector is a judgment. See §1b.
8. **Write the registry** (SQLite) and regenerate the CSV + MD exports.
9. **Change log.** Every run appends what it added/changed to a change_log
   table — never silent edits.

## 3. INCREMENTAL FROM DAY ONE (required)
Each run must answer per file: seen before? (path+size+mtime quick check) →
changed? (re-hash only if size/mtime moved) → already has approved metadata?
(leave it) → genuinely new/changed? (process). Repeat runs must be cheap;
only new/changed/ambiguous files get real work. An approved classification
from a later step must SURVIVE the next inventory run untouched.

## 4. FIRST MILESTONE — deliberately small
Do NOT point this at 10,000 files first. Run it on ONE representative folder:
`C:\Users\David\Documents\faiththruphysics.com\10_VAULTS\01_Working\Canonical Rebuild`
(9 governed books + index + corrections log — clean, small, known). Produce the
registry for that, let David inspect `REGISTRY_MASTER.md`, confirm the
work/version grouping looks right, THEN scale to more roots.

## 5. HARD RULES (non-negotiable)
- **Inventory in place.** No move, no rename, no delete. Ever, in this stage.
- **Only byte-hash duplicates are certain.** Everything fuzzier is a PROPOSAL.
- **List the unreadable.** Extraction failures appear in the registry, flagged —
  never dropped.
- **Published ≠ verified. Latest ≠ best.** Keep those as separate fields; don't
  collapse them.
- **SQLite is source of truth; Excel/MD are generated.** Never hand-edit the
  exports as if they were the DB.
- **Reproducible:** record the tool version + rulebook version on every row so a
  later run can tell what produced a classification.

## 6. WHAT STAGE 1 DOES NOT DO (explicitly out of scope)
- No tagging (that's Step 3, needs the taxonomy Part A + source papers).
- No renaming (Step 2 / `03_RENAMING` is already built and separate).
- Minimal LLM use — ONE narrow exception: proposing the Nabla vector (§1b),
  which is a model judgment, queued for review. Everything else in Stage 1 is
  pure file mechanics (hashing, extraction, grouping). Full tagging/DeepSeek
  triage stays at the TAG step, not here. If running the Nabla proposal via a
  model is not wired yet, leave the vector UNSET and queue it — the rest of the
  registry must not block on it.
- No CocoIndex, no canon, no Lean. Those consume the registry later.

## 7. DEFINITION OF DONE
- `_data\registry.sqlite` exists with all seven tables (files, works, versions,
  series, nabla, review_queue, change_log) populated for the test folder.
- `REGISTRY_MASTER.md`, `registry_works.csv`, `registry_files.csv` generated from it.
- Re-running on the unchanged folder does near-zero work and changes nothing.
- Every file in the test folder appears exactly once in Files; works/versions
  proposed; duplicates grouped; any failures flagged in Review Queue.
- Each work has a Nabla row (vector proposed + queued, or unset + queued if the
  model step isn't wired); the deterministic signature validates via the tool.
- David can open REGISTRY_MASTER.md and see the whole test corpus at a glance,
  each work showing its Nabla address inline.

*Questions route to David. Build mechanics are the dev's; the registry schema
and the hard rules above are fixed. — Fable*
