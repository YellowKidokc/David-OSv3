# How We Understand a Folder Before We Touch It — and How We Report It
*David Lowe · POF 2828 · Oct 17, 2026 · David-OSv3 · written from the Cross-Domain Coherence Project session*

This is the method, written down so a script (or any AI) can follow it the same way every time.
Part 1 is the steps. Part 2 is what an anomaly is. Part 3 is the report.

---

## PART 1 — The steps, in order

### Step 0. Look before touching anything.
List the top level first. No copying, no creating, no deleting until you have seen what is there.
(The one time this was skipped on Oct 17, a duplicate set of 112 folders got built next to a better existing one.)

### Step 1. Get the scope.
How many files, how big, what types. Cross-Domain turned out to be 3,101 text files and 123 MB, not the 300 expected —
that one number changed the whole plan (NotebookLM bundling became required).

### Step 2. Read the names for five kinds of signal.
1. **Same folder, different spelling** — `01_Federal_Reserve` vs `Federal Reserve`, `11_Master_Equation` vs `MASTER EQ`.
   Strip the number prefix, lowercase, turn `_` and `-` into spaces, then compare.
2. **Look-alikes that are NOT the same** — `Somatic_Entropy` vs `Semantic_Entropy`. One letter apart, different meaning.
   Names can suggest a match; only content can confirm one.
3. **Not papers at all** — `.venv`, `Python`, `assets`, `Templates`, `.git`, `node_modules`, scripts, HTML templates.
4. **Archives** — `Archive`, `A3_ARCHIVE`, `_DESKTOP_MIGRATION_ARCHIVE`. Probably older copies; a guess until opened.
5. **Unknowns** — `Untitled 1..15`, `CDC_*`, `Clipboard Text`. A name that says nothing means the file must be read.

### Step 3. Check what code already exists before writing new code.
Search the repos for the job (fingerprint, dedupe, near-dup, simhash, normalize). On Oct 17 this found:
`engine/fingerprint.py`, `fis_dup_heuristic.py`, `consolidate_scan.py` (written for this very folder, with a sandbox),
`engine/canon_sidecar.py` (records the keeper decision, deletes nothing), `engine/gate.py` (every file action needs approval).

### Step 4. Test the existing code before trusting it.
Read every line, then run it on known cases. `fingerprint.py` exact hashing was solid. Its near-duplicate check was not:
blind to word order, every empty file "matched" every other, ~18% false matches on shared vocabulary.
Fixed with a two-step check (`near_dup`: cheap candidate, then exact overlap confirm), short-text guard, tests saved in
`tests/test_fingerprint.py`. Rule: a description of what code does is not evidence it does it.

### Step 5. Fingerprint every file twice.
Exact bytes (sha256) and normalised text (whitespace collapsed). Same normalised text = same paper.

### Step 6. Decide with written rules, and write every decision down. (`engine/flatten_dedupe.py`)
- R1 never modify the source; output goes somewhere else
- R2 text files only; everything else listed as skipped
- R3 skip tool/system folders
- R4 exact duplicates -> keep one
- R5 near duplicates -> keep one, HOLD the other for review (never silently drop a version)
- R6 keeper = not archive > numbered folder > shallower > longer > newer
- R7 flat name carries the origin folders (`06_History_AW__Founders__Jefferson.md`)
- R8 same-name folders are REPORTED, never auto-merged
Every file gets a row in `MANIFEST.csv` saying what happened to it and why.

### Step 7. Dry run first.
The first run only writes the manifest and the report. A human (or a second AI) checks a sample of the decisions —
especially the edge cases — before `--apply` copies anything.

### Step 8. Only then act, and only through the gate.
Every action (copy, move, rename, dedupe) goes through `gate.py`'s rule stack. Anything short of a hard stop comes back ASK.

### Still to build (the three axes of "what is this folder")
| Axis | Question | Status |
|---|---|---|
| Shape | What is physically in here? | built — `fis_classifier.py` (system / media / document / project / dump / archive) |
| Purpose | Code, business, work, personal, pictures, research? | missing — sample files, classify by NABLA domain, majority vote |
| Position | Where does it sit relative to everything else? | missing — depth, parent type, sibling types, nearest project root above it |

Position matters most for safety: images inside a code project are project assets, not a photo album.

---

## PART 2 — What counts as an anomaly (the things that shouldn't be there, but are)

An anomaly is anything where **what a file is** disagrees with **where it is** or **what it's called** or **what it's with**.

| Anomaly | Example | Why it matters |
|---|---|---|
| Wrong neighbourhood | a Python script inside a paper folder; a paper inside `assets` | something was dropped in the wrong place |
| Copy newer than the original | the archive copy was edited after the main copy | the "old" one may be the real latest version |
| Same title, different content | two `Trinity.md` files that disagree | two papers sharing a name, or a fork nobody noticed |
| Same content, far apart | one paper in `03_Education` and `Somatic_Entropy` | a misfile, or a paper doing double duty |
| Empty or near-empty | `Untitled 7.md` with 4 words | clutter, or a lost draft |
| Name says nothing | `Untitled`, `Clipboard Text`, `New folder` | must be read to be classified |
| Content domain ≠ folder domain | a Federal Reserve paper inside `Trinity` | misfile, or a real cross-domain bridge worth flagging |
| Size outlier | one 4 MB markdown among 20 KB papers | a merged dump, pasted logs, or a full book |
| Orphan type | one PDF in a folder of markdown | a source that belongs to some paper |
| Version without a parent | `v3` exists, `v1`/`v2` don't | history lost somewhere |

Some anomalies are mistakes; some are discoveries (a real bridge between two domains). The report flags; it does not judge.

---

## PART 3 — The report

**Split the work: code gathers the facts, one AI call writes the words.**

Order, most useful first:
1. **Anomalies** — the things that shouldn't be there (Part 2), most surprising first.
2. **Biggest payoff** — the one action that clears the most clutter or fixes the most for the least work
   (e.g. "approve these 40 exact duplicates — one click removes 1,100 copies").
3. **What changed since last run** — the AI is given the previous report and leads with what is new; if nothing changed, one line.
4. **Everything else worth knowing** — near-duplicates held for review, folder-name groups, unknowns.
5. **Receipts** — where the manifest and data files are, so anyone can check.

**Statistics run through the whole report, and visually** — counts as bars, folder sizes as a map, duplicates as a
before/after. Early versions do not need to be beautiful.

**Keep it from going stale:** the facts never change between runs; the LENS rotates (lead with risks one run, wins the
next, oddities the next). Never vary the numbers — vary the emphasis.

**Guard:** numbers are inserted by code in a fixed facts block; the AI writes the narrative around them. A check confirms
any number the AI repeats matches the data, and flags the report if one doesn't.

**Always leave data behind.** Every scan writes its manifest and per-folder data whether anyone reads the report or not.
Nothing is ever lost to a report nobody opened.


---

## PART 4 — Look fast, then dig where it matters (the tiered check)

Nobody can inspect 3,000 files deeply. So every file gets a **snapshot** first, and only suspicious ones get the deep look.

**Tier 1 — snapshot (every file, cheap):** name, folder, size, dates, extension, exact fingerprint.
**Tier 2 — properties (only when Tier 1 says "looks like a duplicate"):** normalised-text fingerprint, word count,
first heading, frontmatter (title, version, date fields), near-duplicate overlap.
**Tier 3 — read it (only when Tier 2 disagrees with itself):** the content is compared directly, the differences are listed,
and the file goes to the anomaly section.

The rule that makes this honest: **a dramatic difference in the NAME never ends the check.** If two files are 99% the same
inside, they are the same paper no matter what they are called. Some of the best findings will be exactly those.

### How the report tells it (the version everyone reads)
> 15 folders look like near-copies of each other (e.g. `01_Federal_Reserve` / `Federal Reserve`).
> Together they hold 412 files. 13 of the 15 pairs are exact duplicates after checking content, size and fingerprints —
> those are merged into one copy each (receipts in MANIFEST.csv).
> 2 pairs were different, and they are the interesting ones:
> - `Semantic_Entropy` / `Somatic_Entropy` — the names are one letter apart, but the contents share nothing. Kept separate.
> - `Trinity_v2.md` / `Coherence_Of_Three.md` — completely different names, 96% the same text. Same paper.
>   **Likely reason for the rename** (inferred, not known): the later copy adds a new title heading and is dated 3 weeks later.

**The system can see THAT a name changed and WHEN. It can only guess WHY.** So the "reason" line is always labelled
*likely* / *inferred*, never stated as fact — unless the file itself says so (a changelog line, a frontmatter note).

---

## PART 5 — The intake interview (the most fundamental step)

Before the system organises anything for a person, it asks about 20 short questions. **While they answer, the scan is
already running in the background** — FIS pages written into each folder, the SQLite map filling, fingerprints cached — so
by the time the interview ends, most of the heavy work is done and actions feel instant.

### What the questions are for
- **Boundaries:** Do you mix business and personal here? Which folders are off-limits? Anything shared with other people?
- **What matters most:** *"If the house were on fire, which files would you carry out?"* — the moment those are named,
  they are **zipped into a protected snapshot immediately**. The person keeps their files; we keep a record that can never
  be damaged by anything we do afterward.
- **What they're looking for:** find things faster? stop duplicates? prepare for a project? hand off to someone?
- **How far they want to go:** this is the big one —
  1. **Light touch** — rename and tidy what exists, change nothing about how they work.
  2. **Reorganise** — a new folder structure, existing files moved into it (with receipts).
  3. **Start from zero** — commit to a whole new system, rebuilt from the ground up.
- **Then we offer 2–3 baseline organisations** (naming scheme + folder layout) to pick from. Everyone gets a sensible
  baseline even if they don't know what they want — somebody has to propose one.

### Where this already exists
The idea was built once before: the **vault generator** (bat + Python interview, revival of the Nov 2025 Adaptive
Research Framework) and `01_PROFILE\profile_core.py` in this repo (the registry writer). The 20 questions should be
recovered from there before writing new ones.

### Rules
- The answers become the person's **profile**, and every later action is checked against it by `gate.py`
  ("off-limits folder" -> BLOCK; "business and personal mixed" -> ASK before moving anything across).
- The protected snapshot is taken **before** any action of any kind, every time.
- Nothing in the interview is required; a skipped answer means the gentlest option.
