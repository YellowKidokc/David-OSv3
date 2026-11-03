# FIS naming: operating principles
POF 2828 | Oct 25, 2026 | records how renaming works today and the agreed next design

The formal schema (core and learned tiers, how new classifications are created) is in `docs/FIS_NAMING_SCHEMA.md`; where the two documents differ, the schema document wins.

Status key: **[built]** exists and was exercised on 2026-10-25. **[proposed]** agreed in conversation, not yet built.

## 1. The name format [built]
`DOMAIN__TYPE__title-words__YYYYMMDD__STATUS.ext`

Example: `untitled 1.md` ("Quantum notes") becomes `PHY__NOT__quantum__20261025__AC.md`.

| Part | Meaning | Fallback |
|---|---|---|
| DOMAIN (3 letters) | Topic, e.g. PHY, CON, COS, FRM, INF, SOC, FAM, SCI | `GEN` |
| TYPE (3 letters) | Kind, e.g. NOT, RES, PAP, DRV, DAT, TST, ART | `ART` |
| title words | Up to 7 words from filename/title; filler words dropped | none |
| YYYYMMDD | Date (see open issue 1) | none |
| STATUS (2 letters) | DR draft, FN final, AR archive, RV review | `AC` active |

A name already in this format is left alone. Series numbers stay short: `gtq_12`, `ch3a`, `p4`.

## 2. Codes and keywords are data, not code [built]
- Defaults: `fis/data/naming.json`. Opt-in Theophysics pack: `fis/data/theophysics.json` (MEQ, AXM, GRC, ETH, THE, TPH). The pack applies only when `theophysics` is in the root's rule packs; it is off by default.
- Adding a keyword = append to a domain's `words`. Partial words match (`sentien` matches "sentient").
- Adding a domain = add `{"code": "BIO", "words": [...]}`. Codes are three capital letters, because the already-named check expects `AAA__AAA__...__YYYYMMDD__AA`.
- Only the pack name `theophysics` is accepted (`fis/rename.py`). A second pack needs a code change.

## 3. How matching decides [built]
1. Filename, then title (first `# ` heading), then folder, then the first 4000 characters of the body.
2. In filename/title, the first rule in list order wins. List order is priority, and pack domains go ahead of defaults.
3. In the body, the domain with the most keyword hits wins, with at least 3 hits.
4. No hit means the fallback code, and the row records "No clue; configured fallback".
5. Every proposal carries its evidence. Nothing renames without approval.

## 4. Principles
1. **Evidence or fallback.** A code is assigned only with a quoted reason. Otherwise use the fallback and say so.
2. **Proposals only.** Naming never changes a file. Approval is bound to the exact plan hash. Every apply can be rolled back.
3. **Rules are readable data.** A person can open, edit and diff the vocabulary. No hidden model decides a name.
4. **Low confidence is visible.** Confidence is 0.3 plus the domain weight plus the type weight, so a row with no clues scores 0.30. Show it as low and do not pre-select it.
5. **Learned preference is advisory.** It never grants approval.
6. **New vocabulary is earned, then confirmed.** See section 5.

## 5. Suggestion counter [proposed]
Goal: let the system notice new vocabulary and promote it to a code once the evidence is strong enough, so the vocabulary grows without hand editing.

Design:
- **Candidates ledger** (SQLite in the FIS state directory). Each row holds a candidate keyword or phrase, the domain it is suggested for, a count, the distinct files and folders it appeared in, first and last seen, and a source.
- **Sources of a suggestion:**
  - a repeated unmatched term in files that fell back to `GEN`;
  - a term the user typed when correcting a proposed name (a successful correction counts for more than a passive sighting);
  - optionally an AI provider suggestion (section 6).
- **Counting rule:** count distinct files, not repeats within one file, so one long document cannot trip the threshold.
- **Two thresholds, both configurable:**
  - *Keyword threshold* (starting value 5 distinct files): the term is added to an existing domain's `words`.
  - *Domain threshold* (starting value 15 distinct files across at least 3 folders): propose a new 3-letter code. The code is suggested from the term (BIO for biophysics) and checked against existing codes.
- **Promotion is a proposal, not a silent edit.** Crossing a threshold queues a "new vocabulary" row in the review screen showing the term, its count, and example files. Approving it writes to a user vocabulary file (see below). Rejecting it records a block so it is not suggested again.
- **Where promoted terms are written:** a separate `vocabulary.user.json` in the state directory, layered over `naming.json` at load time. Shipped defaults stay untouched and an undo is a file revert. This also lifts the one-pack limit, because user vocabulary is not a named pack.
- **Axiom awareness:** axioms and other canon-bearing terms get their own counter, because they recur across many documents by design. Their threshold and promotion target are separate, and a promotion into canon is never automatic.

Open design questions for the owner: the starting thresholds, whether a corrected name counts as one sighting or the full threshold, and whether code suggestions should be shown with a short list of alternatives.

## 6. Optional AI classification [proposed]
- `fis/providers.py` already defines the hook: `SuggestionProvider.suggest(evidence) -> dict`. The default `OfflineProvider` returns no suggestions and makes no network call. Provider mode is `off` by default.
- A hosted model (for example DeepSeek, which exposes an OpenAI-compatible API) could be added as a provider. It would receive bounded evidence (filename, heading, an excerpt) and return suggested domain, type and keywords, each with a reason.
- Constraints:
  - Off unless the user enables it per root. The key stays in a local setting and is never written into a plan, a page, or the ledger.
  - Excerpts leave the machine, so the root setting must say so, and protected or blocked folders are never sent.
  - Output is treated as one more suggestion source feeding section 5. It can raise a candidate's count but cannot change a name or vocabulary by itself.
  - Responses are cached by file hash so the same file is never sent twice.
  - A bad or empty response falls back to the offline result.

## 6b. Drop folders and spreadsheet reading [proposed]
- **Drop folder = instruction.** An inbox folder carries a small settings file giving a default domain, type and keywords (for example `_IN/axioms/` implies AXM + NOT). The folder choice is a strong naming clue, weighted above the body text but below an explicit filename match. It is data the rules can read, not free text.
- **Learning.** Terms recurring across files dropped in one folder are fed to the section 5 counter. Crossing a threshold queues a confirmable keyword or code.
- **No AI required.** The folder hint plus the counter handle the common case. A provider (section 6) is only for files that still match nothing.
- **Safety.** The existing profile system (`profiles` in the root policy, `fis/gate.py`) sets approval floors only. The drop-folder hint is a separate, additive setting and must not loosen a floor.
- **Spreadsheets.** `.xlsx` is zipped XML and can be read with the standard library. Useful signals: sheet names, header row, first rows. Currently `.xlsx`, PDF and DOCX get metadata-only classification.
- **Build order:** counter and user vocabulary, then drop-folder hints, then the `.xlsx` reader, then the optional provider.

## 7. Open issues found on 2026-10-25
1. **Date field uses today's date.** In the test every file received `20261025`, which was the day of the run, so check whether it is meant to be the file's own modified time. The code passes `mtime`, and the fixture files were created that day, so this may be correct. Confirm with an older file before calling it a bug.
2. **Generic filenames get empty names.** `IMG_001.txt` became `GEN__ART__img_001__...` at confidence 0.30. Fixes: more keywords, reading content, the section 5 counter.
3. **Low-confidence rows can be applied by a whole-plan approval.** Check whether the GUI preselects them.
4. **Only the `theophysics` pack name is accepted.**
5. **Stale copy** at `fis/build/lib/fis/data/`. Do not edit it.
