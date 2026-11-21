# DEEP IDENTIFY — CREW REVIEW PROMPT
## David-OSv3 / 10_FILE_ACTIONS / deep_identify.py

**Date:** November 12, 2026
**Author:** Fable (Claude) + David
**Location:** D:\GitHub\David-OSv3\10_FILE_ACTIONS\shared\deep_identify.py
**Status:** First draft — needs crew vote before integration

---

## What This Is

`deep_identify.py` is a new deep file-action for David-OS. You point it at a folder. It reads every qualifying file, classifies each one by document type, discovers series/family relationships even when naming is inconsistent, and scores everything with confidence percentages.

**It is read-only. It never moves, renames, or deletes anything.**

It sits in `10_FILE_ACTIONS/shared/` alongside `series_finder.py`, `metastasize.py`, and `folder_intelligence.py`. Those do structural work (filenames, hashes, folder shapes). This one opens files and reads content.

---

## The Classification Cascade (5 Levels)

Each file passes through five levels. Each level narrows the classification. Each produces a confidence score.

### Level 0 — Container Type (Is this even mine to touch?)
Detects what kind of folder this is: Obsidian vault, git repo, Python project, research/writing folder, media folder, code folder, mixed, empty. Sets protection flags: `can_move`, `can_rename`, `is_protected`.

**Principle:** If breaking the folder breaks a program, don't touch the folder.

### Level 1 — File Kind (What family of thing is this?)
Extension-based: code, document, picture, video, audio, data, config, sidecar, archive.

### Level 2 — Domain (What world does this belong to?)
Content-token scoring against domain vocabularies: theophysics, website, business, ai_chats, media. Returns domain + confidence with margin-aware scoring (how much better is the winner than second place).

**REVIEW NEEDED:** The domain vocabulary is hardcoded. It should load from the lexicon spreadsheet (LAW_KEYWORDS, SEMANTIC_BUCKETS, etc.) so the vocabulary is canonical and shared across all tools. How should we wire this?

### Level 3 — Document Type (What is this document?)
Classifies as: paper, note, guide, template, identity_card, data_artifact, code, config, sidecar, media. Scores based on content markers, document length, and section structure (markdown headers, HTML headings).

**REVIEW NEEDED:** The DOC_TYPE_PATTERNS sheet in the lexicon already has the canonical marker lists (paper = abstract/introduction/methodology/conclusion/references/theorem/proof/lemma; article = subscribe/read more/published/blog/series). The code should load these instead of using its own hardcoded list.

### Level 4 — Series/Family Discovery (Does this belong to a group?)
Three independent signals, following the Three Connector Rule (STR-013 / DER rules):
1. **Title root grouping** — strip numbers, suffixes, extensions; group by shared root
2. **Cross-reference detection** — wikilinks `[[something]]` and filename mentions in content
3. **Vocabulary similarity** — cosine of top-50 content tokens between documents

Sequential numbering detected via: named prefixes (Paper_01, Law_03, MS_02), bare position numbers, and Roman numerals (I, II, III).

Family confidence starts at 0.60 (title root alone) and gets boosted by:
- Cross-references between members: +0.15
- Vocabulary similarity > 0.30: +0.15
- Sequential numbering detected: +0.10

Series completeness and gaps are reported (e.g., "positions 1,2,4,5 found — gap at 3").

---

## Output

Four files in the output directory:
- `deep_identify.json` — full structured report (every card, every family, all stats)
- `file_cards.csv` — one row per file with all scores
- `families.csv` — discovered families with confidence, evidence, gaps
- `orphans.csv` — documents that don't belong to any family

Stats include: domain distribution, doc_type distribution, kind distribution, average identity confidence, family count, orphan count.

---

## What I Want From You

### 1. Architecture Review
- Is the 5-level cascade the right order? Should anything move?
- Are there classification levels missing?
- Is the scoring math reasonable? Too generous? Too stingy?

### 2. Lexicon Integration
The lexicon spreadsheet (`lexicons_master_enhanced_v2_classification_2026-11-06.xlsx`) has canonical vocabulary for:
- **DOC_TYPE_PATTERNS** — marker words for paper, article, note, config, readme, changelog, license
- **LAW_KEYWORDS** — L1 through L10 keyword lists
- **SEMANTIC_BUCKETS** — claim strength (weak/moderate/strong), polarity, weight, danger_level
- **CLAIM_TERMS, EVIDENCE_TERMS, FALSIFY_TERMS, HEDGE_TERMS, BRIDGE_TERMS**
- **FRUITS / ANTI_FRUITS** — the full Galatians 5 lexicon with retrieval classes

How should deep_identify load and use this? Options:
a) Read the xlsx at scan time
b) Export canonical JSON from the xlsx once, load that
c) Load from the SQLite that Jev/TypeSafe already uses

### 3. Prediction GUI Integration
When deep_identify finds something — a new family, an orphan that might belong somewhere, a gap in a series — it should notify through the Prediction_GUI system. What's the notification format? What confidence threshold triggers a notification vs. silent logging?

### 4. Scoring Calibration
Every classification needs a confidence score. Every family needs a confidence score. These need to be:
- Comparable across runs (same file should score the same)
- Useful for the preference engine (the prediction harness learns from feedback)
- Honest (low confidence means low confidence, not "I don't know so I'll say 50%")

Does the current scoring approach achieve this?

### 5. What I Missed
What's the dumbest failure mode you can see? What will break first when this hits real data?

---

## Files to Read

1. `D:\GitHub\David-OSv3\10_FILE_ACTIONS\shared\deep_identify.py` (761 lines — the code)
2. `D:\GitHub\David-OSv3\rule_brick\questions.json` (the 32 rule-brick questions this implements)
3. `D:\GitHub\David-OSv3\10_FILE_ACTIONS\shared\series_finder.py` (existing series finder — hardcoded patterns)
4. `D:\GitHub\David-OSv3\10_FILE_ACTIONS\shared\metastasize.py` (existing connection walker)
5. `D:\GitHub\David-OSv3\10_FILE_ACTIONS\shared\folder_intelligence.py` (existing folder profiler)
6. The lexicon spreadsheet (for vocabulary review)

---

## Vote Format

For each of the 5 sections above, give:
- **HOLD** — the design is sound, build on it
- **BREAK** — here's a specific failure mode or wrong assumption (name it)
- **IMPROVE** — the design is right but here's how to make it better (specific change)

Then give an overall confidence: what percentage chance does this approach correctly identify series relationships when pointed at `C:\theophysics\faiththruphysics.com`?

---

*Built by Fable + David, November 12, 2026. Read-only. No mutations. Every score is auditable.*
