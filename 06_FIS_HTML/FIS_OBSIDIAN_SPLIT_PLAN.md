# FIS / Obsidian split — build order and naming ladder

David, 2026-11-11. This adds to `HANDOFF_REGISTRY_INTEGRATION.md`. Where they disagree, this one wins.

## 1. Two lanes, one generator

| Lane | Where it applies | Page it writes | What it covers |
|---|---|---|---|
| **Obsidian** | Any folder inside the Obsidian vault (has a `.obsidian` ancestor) | `OBSIDIAN_REGISTRY.html` | Notes: identity, progress boxes, relations, links between notes |
| **FIS** | Every other folder | `FIS.html` (unchanged) | Files: names, keywords, address, proposed rename |

- Both pages come from **one generator** (the FIS engine, `fis_folder_memory.py`). It picks the lane per folder.
  A folder gets one page, never both. That settles objection 5.
- `registry_scan.py` + `registry_template.html` become the Obsidian lane's renderer, not a second tool.
- Dot folder name: **`.data`**. Math Is Moral already uses it and the scanner already reads receipts there.
- Generated pages (`OBSIDIAN_REGISTRY.html`, `FIS.html`) stay in the folder. They never move to `.data`.

## 2. Build order: gates 1–5 before any indexing

Nothing indexes the whole campus until all five are done and tested on one small and one large folder.

1. **Disk-space gate.** Check free space before every write and stop cleanly if it's short. C: had 0 GB free.
2. **Built-set exclusion.** Linked HTML sets (Kimi axiom series, `50_PRODUCTION_AND_PUBLICATION`, site builds)
   are skipped, or moved only as a whole set. Frontmatter paths (`card:`, `receipt:`) are rewritten or checked so they still resolve.
3. **Obsidian files are off-limits.** `.obsidian/`, `*.base` and `*.canvas` are never moved or rewritten.
4. **Simulate → receipt → move → undo.** A dry run writes a receipt (source, destination, SHA-256).
   David approves it. The move then writes an undo file. Nothing is deleted.
5. **One page per folder.** Lane detection is in place, and an old second page found in a folder is reported (not deleted).

6. *Only then:* full index. Cap listings in big folders (MIM.06 has 22,240 transcripts). Hash or classify only new or changed files, tracked by mtime and size.
7. *Then:* linking. Obsidian lane shows note-to-note relations and "Also shown in". FIS lane links files to the notes that cite them.

## 3. Naming ladder (who gets to name a file)

Each rung only runs if the rung above it couldn't decide.

1. **Excel lexicon.** Look the file's terms up in `.data/classification/LEXICON_MASTER_v2_UNIFIED.xlsx`
   (the one source; the other workbooks merge into it or are retired). A clear match names the file.
2. **Local inference.** Rules plus the learned vocabulary (folder context, sibling names, frontmatter). Free, offline.
3. **DeepSeek.** A cheap model suggests the name, with a confidence score.
4. **Council.** For low confidence or files that matter most (canon, published, cited papers), send it to all
   the models (Claude, DeepSeek, Kimi, GPT…). A name is accepted if they agree.
5. **David.** Anything still unsettled goes to a review queue. His ruling is final, and new terms go
   back into the Excel so rung 1 catches them next time.

**Sidecar.** Every naming decision writes `.data/<file>.fis.json` with: the name, the rung that decided it,
the confidence, each model's vote, and the time. You can always see why a file has its name, and undo it.

## 4. Ruled by David (2026-11-11)

- Page name `OBSIDIAN_REGISTRY.html` is accepted.
- "Matters most" (goes straight to the council): **canon, new work, published, cited by others**.
- Rungs 3–4 go through David's API job handoff (`hub/api`). Each naming question is a small job, and they add
  up to the big rename. Wiring this is a later step, after gates 1–5.

## 5. Still open

- The twelve progress steps are still a proposal, not a ruling.
