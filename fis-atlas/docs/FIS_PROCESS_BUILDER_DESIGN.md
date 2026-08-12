# FIS Process Builder — GUI Design & Its Evolution

This is the surface design for FIS, and (deliberately) the record of how it got
here — including the ideas we tried and corrected. The corrections are load-bearing
knowledge; a later reader learns as much from the wrong turns as the final shape.

---

## The governing rule

The simplest scalable GUI is **not one button per operation**. It is one
consistent sentence every operation fills in:

> **SELECT → ACT → STAGE → PREVIEW → APPROVE**

The surface only ever asks four things; everything else is an implementation
detail behind it:

```
What do you have?   What do you want to do?   Where does the result go?   Does the preview look right?
```

Search, cut, copy, convert, group, dedupe, archive, rename, classify — all use
that same grammar, so the screen never crowds.

---

## Three layers (the clean distinction)

```
OPERATIONS   individual verbs        Find · Compare · Group · Rename · Copy · Move · Convert · Archive
PROCESS      verbs in a sequence     Find → Compare → Group → Rename → Move
RECIPE       a locked, named process NotebookLM Slide Recovery
RUN          one recorded execution  Run 0042 · 2026-08-12
SAFETY       wraps every run         Preflight → Snapshot → Preview → Execute → Verify → Commit/Rollback
```

**Operations are words; a process is a sentence; a recipe is a saved sentence; a
run is one historical execution; the safety envelope protects every run.**

---

## Layout

```
┌ FIS Process Builder ──────────── Recipes · History · ⚙ ─────────────────────┐
│ FILE OPERATIONS │ PROCESS (the sentence)        │ STEP DETAILS / RESULTS     │
│ Find · Select   │  INPUT                        │ what the selected step      │
│ Compare · Group │   ▼ [1 Find matches]          │ means in THIS process:      │
│ Rename · Copy   │   ▼ [2 Group by identity]     │ input · action · output ·   │
│ Move · Convert  │   ▼ [3 Rename members]        │ label · options             │
│ Archive · More› │   ▼ [4 Move to Matched/]      │                             │
│                 │      [+ Add step]             │                             │
├─────────────────┴───────────────────────────────┴─────────────────────────────┤
│ ✓ Preflight  ✓ Snapshot  Preview only  Verify after  Rollback ready   [Preview]│
└──────────────────────────────────────────────────────────────────────────────┘
```

- **Left = operation vocabulary** (plain verbs; the 9-stage pipeline collapses under "More").
- **Middle = the process sentence** (drag verbs into a sequence; also the working area).
- **Right = step details / results basket** (what the selected step produces; staged groups).
- **Bottom = a permanent safety rail** — always present, almost no interaction needed.

### Six operation families (not 40 loose commands)

| Family | Purpose | Underneath |
|---|---|---|
| **Find** | locate things | search, filter, scan, OCR, metadata/content search |
| **Compare** | determine relationships | exact-dup, visual match, near-dup, versions, folder compare |
| **Organize** | change placement/structure | move, copy, cut, paste, group, flatten, split, merge |
| **Transform** | change representation | rename, convert, compress, extract, rasterize, resize |
| **Protect** | risk & lifecycle | archive, quarantine, encrypt, lock, restore, delete |
| **Describe** | machine understanding | classify, tag, summarize, identify, relate, assign purpose |

The rail shows the most-used verb per family; expanding a family reveals the shelf.

---

## Every step is a contract (Input · Action · Output · Label)

Each operation card answers four things — and the fourth is the one people miss:

```yaml
step: 3
operation: group
input:  visually_matched_candidates
action: group_by_visual_identity
output: identity_groups
label:  matched_slide_group        # <-- what the result now MEANS
```

**Label** is the categorizing layer: a step doesn't just move files, it *declares
what its result represents*, so the next step can consume it by name
(`input: $output_of("Find visual matches")`) without knowing how it was produced.

### Operations are typed empty slots; binding happens per-template

An operation starts **unbound** — no drives, no folders baked in:

```yaml
operation: {verb: move, input: {status: unbound}, destination: {status: unbound}}
```

You build the *logic* first (`FIND → COMPARE → GROUP → RENAME → MOVE`), then
attach files, a previous step's output, or a folder structure to specific slots.
Dragging `H:\Recovered Slides` onto a card's Destination binds it **only to that
card** — other operations and templates stay independent. A proposed folder tree
(`Matched / Review / Unmatched`) is **template-local and virtual** until the run
is approved; it becomes real bytes only at `act`.

### The three-row card grammar

```
OPERATION
─────────────────────────
OBJECTS   [files · folders · groups · a previous step's output]
ACTION    [move]
LOCATION  [destination]
─────────────────────────
PRODUCES  [moved objects]        # result.location = chosen destination
```

Collapsed → `MOVE · 23 files → Matched/`. Expanded → conflict policy, structure
rule, safety toggles. Depth is hidden until requested.

### The middle has three switchable views (not three screens)

**Files** (folder listing) · **Groups** (match sets / projects) · **Plan** (proposed
final arrangement). Double-click a group to compare; drag it right to stage.

---

## The safety envelope (automatic, not user-assembled)

Every saved process is wrapped without the user adding safety steps:

```
Preflight → Snapshot → Named process → Verify → Commit+ledger  (or Stop/Rollback)
```

- **Before:** sources still exist? protected/locked files? destination space?
  name collisions? permissions? record paths+hashes; save the process definition;
  create a **recovery manifest**; show the full preview.
- **During:** record each step individually — `Step 3/5 failed` — never pretend a
  partial run fully succeeded.
- **After:** verify expected files exist, copy hashes match sources, moved sources
  are gone/preserved as planned, counts & group membership correct, nothing else
  changed. Only then is the run "complete."

**"Snapshot" has two meanings, and the difference is honest:**
1. **Recovery manifest** — always available; records every original path,
   destination, operation, hash, result. Reverses ordinary moves/renames.
2. **Real filesystem snapshot** — only when the drive supports it (VSS, NAS, ZFS/
   Btrfs). Required to reverse **overwrites or deletions**.

> The system must **never promise rollback after permanent deletion** unless the
> bytes were actually preserved (quarantine/backup/snapshot). No delete button
> appears in the ordinary workspace; deletion routes to quarantine.

---

## Naming schema (final form + why)

Visual identity and document identity are **separate** (a PDF is a multi-slide
container, so one deck can belong to many visual groups):

```
G0011-P.pdf   G0011-N.png   G0011-W.webp     # single-page: P/N/W = pdf/png/webp
```
For a multi-page deck, the PDF keeps its **document** identity and the group holds
a **pointer**, never a renamed copy:
```
D004.pdf                     # the deck = document identity
G0011-N.png                  # image members get the group id
G0011-W.webp
G0011-P03.ref  →  {source_document: D004, source_page: 3}
```
The shared prefix identifies the underlying slide; the last code identifies the
representation. **Identity lives in the group manifest (registry); the filename is
a projection of it** — so a hand-rename can't lose the identity, the label just
re-derives. (Your `11A/22A` instinct, made explicit and scalable.)

---

## What learns from you (and what it must never do)

- **Preference selector (primary):** learns weights over evidence — visual
  similarity, OCR agreement, aspect ratio, NotebookLM metadata, filename hints,
  prior decisions — updated on every accept/reject/add/remove/split/merge. It
  ranks candidates into lanes: **Auto-selected · Review · Unmatched**.
- **Markov (secondary):** predicts the *next operation* (group → assign identity
  → rename → stage), not which files match.
- **Hard rule:** learning predicts **selection**, it never grants **permission**.
  Acceptance history widens/narrows what's *proposed*; it never authorizes a move.

---

## Evolution & corrections (the wrong turns, kept on purpose)

1. **"One button per operation" → one operation grammar.** A 40-command palette
   crowds the screen; `SELECT → ACT → STAGE → PREVIEW → APPROVE` scales.
2. **The 9-stage op-shelf as a header → collapsed reference.** Look/Identity/…/
   Automate are *architecture*, not everyday controls. Verbs on the surface.
3. **"It's a File Explorer" → it's a process builder.** The middle isn't for
   browsing; it's for assembling a *sentence* of operations.
4. **"Needs an NLP to look at images" → mostly a deterministic vision pipeline.**
   Perceptual hashing (30-year-old, local, reproducible) does the bulk; a **vision
   model** (not NLP — NLP reads words) only adjudicates the ambiguous band, as
   `inferred`, never auto-acted.
5. **Rename the whole PDF as `G011-A.pdf` → document ≠ visual identity.** A deck
   is `D004`; a slide is `G011`; the pdf member is a page *pointer*, not a copy.
6. **Filename as the database → filename as a projection of the registry.** The
   registry/manifest owns identity; the label re-derives.
7. **"Compare them all" felt like the hard part → it wasn't.** pHash makes an
   image a 64-bit number; comparison is milliseconds. The hard part was always
   *trusting the system enough to let it act* — which is what the capsule chain,
   decision codes, and observe-first default were built to earn.

The picture job (W9) is the proof case: run it observe-only, review proposed
families, rule once on naming, let `act` fire. If the ledger reads clean, the
architecture earned its next drive.
