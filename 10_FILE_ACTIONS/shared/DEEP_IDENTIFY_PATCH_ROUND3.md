# Deep Identify — patch for approval (round 3)

November 12, 2026. Fable, at David's direction. Lands steps 1 and 2 of the crew-approved sequence. Steps 3 (lexicon JSON + labeled batch) and 4 (Prediction_GUI) are NOT in this patch.

## What changed in deep_identify.py

1. **Report publishing.** Every run deletes the previous JSON/CSVs first and always writes all four files; CSVs are header-only when empty. New stats: `files_seen`, `coverage`, `extraction_status`, `weak_candidate_pairs`, `vocabulary_pairing`, `score_semantics`.
2. **Family discovery rebuilt** (`cluster_into_families`, v0 kept as `_cluster_into_families_v0`). Four signals can each nominate a pair: title root, numbering, resolved link, distinctive vocabulary (stopwords removed). A pair becomes a family edge only on an explicit link or two independent signals. Single-signal pairs are reported as weak candidates, never merged. Union-find builds families.
3. **Links resolve to real paths.** Wikilinks, markdown links, href, and distinctive bare stems (8+ chars). Self-links dropped. A name matching several files goes to `ambiguous_refs`, never guessed. Reverse index uses exact paths.
4. **Positions.** Unique slots counted; completeness can't exceed 1.0; two files claiming one slot are listed in `competing_versions`; gaps are within the observed range. Short series roots (Law, MS, ME, SP) count when the file carries a number.
5. **No marker evidence, no label.** A document type with zero marker hits is not a candidate; marker-free prose returns `unknown`.
6. **Protection per folder.** A project marker in a folder or any ancestor below the scan root protects its files; protected files are neither movable nor renameable.
7. **Binary formats.** PDF/DOC/DOCX/ODT/EPUB/RTF are flagged `unsupported_binary_format` instead of decoded as UTF-8.
8. **Stable output.** Sorted traversal; `family_id` is a hash of sorted member paths, identical across runs.

## Evidence

`test_deep_identify.py` — 8/8 pass on Windows (D:\GitHub\David-OSv3\10_FILE_ACTIONS\shared):
reciprocal links with different names → one family; same name, unrelated content → weak candidate only; repeated Paper_01 → completeness 1.0 + competing version; marker-free prose → unknown; nested .git → protected; empty rerun → no stale rows; PDF → flagged; family_id stable.

The first run failed one test (Law_01/Law_02 not grouped: 3-letter root rejected). Fixed in item 4 and re-run.

## Known limits (not fixed here)

- Scores are still heuristic (`score_semantics: heuristic_uncalibrated`). Evidence weights are guesses until step 3 measures them.
- `identity_confidence` formula unchanged from v0.
- All-pairs vocabulary is skipped above 1,500 documents (reported, not silent).
- No PDF/DOCX text extraction yet.
- `--max-files` bounds cards, not the first indexing walk.

## Ballot

For this patch: HOLD / BREAK / IMPROVE, with confidence and a cited line or test. Is it safe to run read-only against a real folder (C:\theophysics\faiththruphysics.com) for step 3's labeled batch? Name one test you'd add.


## Addendum — first real-folder check (later Nov 12)

Ran read-only on `faiththruphysics.com\O-09_Math_Is_Moral` (9 files). The synthetic tests had all passed; the real folder still exposed four faults, now fixed and covered by `test_real_folder_shapes_math_is_moral` (9/9 pass; Prediction_GUI 12/12 pass).

1. **Whole-vault scan did not finish in 4 minutes.** The link resolver looped every filename in the tree for every document. Now it extracts filename-shaped tokens from the text once and looks them up. A bare word ("introduction") no longer counts as a link to `introduction.md`; a bare mention must look like a filename (digit, `_`, `-`, or extension).
2. **Papers with YAML frontmatter were labeled identity_card** (6 of 9). Frontmatter is now treated as a header; the body is judged. Only a file that is nearly all frontmatter is an identity card.
3. **`FT-003_PAPER / _FACTS_CARD / _SCORED / _BIAXIOSUM` were reported as four competing versions.** Files sharing a leading document code are now one document's artifact set (`doc_code` signal, `artifact_set[...]` in evidence). Position 0 (readme/index) is not a series slot.
4. **Three stages of one paper (`DT-001_Math_Is_Moral.canonical`, `FP-002_MATH_IS_MORAL`, `Math_Is_Moral`) were not grouped.** Title roots now ignore the leading document code and dotted status suffix. Also fixed: the suffix stripper ate "new"/"old" inside words (newton -> ton).

Result on the real folder after fixes: 2 families, 0 orphans (FT-003: 5 files; FP-002 line: 4 files).

Still not verified: a full-vault run (root is an Obsidian vault with ~200 top-level folders; not re-attempted after the speed fix). Large hashes are skipped above 25 MB. Open question for David: what DT / FP / FT mean, and whether the two families above are one paper line.
