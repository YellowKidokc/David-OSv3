# FIS Canonization System — Architecture & Handoff Spec
## POF 2828 · 2026-08-04 · David Lowe

The system that lets David change canon ONCE (e.g. "the Master Equation is now X",
"Law 7 = Quantum", a grammar rule) and have it disperse through the whole file
system, get checked by the free local NLP stack, and come back as a human-review
list. **Nothing auto-edits content files.**

---

## The loop (how the pieces fit)

```
[1] CENTRAL REGISTRY (David edits this one file)
    D:\GitHub\David-OS\system\canon_rules.json
        each ruling = statement (WANTED) + regex patterns + nlp_keywords + severity
                |
                v
[2] DISPERSAL + SCAN     python fis_canon_scan.py <folder> --nlp
    D:\GitHub\David-OS\file-intelligence-system\fis_canon_scan.py
        - Layer 1: regex (free, deterministic, offline)
        - Layer 2: NLP — keyword-gated paragraphs sent to local :8700
          /nlp/contradiction (premise = paragraph, hypothesis = canon statement;
          flag if contradiction prob >= 0.60). Free — runs on David's own stack.
          Start server: D:\GitHub\BACKSIDE-NLP-NEW\nlp_api\RUN.bat
                |
                +--> writes CANONIZATION section into every folder's .fisnote,
                |    BELOW the divider line:
                |    <!-- FIS-CANON-DIVIDER : ... -->  then  ---  then # CANONIZATION
                |    (rulings in force + last scan result; inventory above the
                |    divider is untouched, and vice versa)
                |
                +--> writes review report (REPORT ONLY, changes nothing):
                     <folder>\09_TO_REVIEW\CANON_SCAN_<stamp>.md + .json
                     each alert = WANTED (canon statement) vs WRITTEN (the line)
                     + next step. David goes line by line: fix / mark historical /
                     exempt by ruling.

[3] FOLDER INVENTORY     python fisnote_scan.py <folder> [--depth N]
    D:\GitHub\David-OS\file-intelligence-system\fisnote_scan.py  (now v3)
        - every file gets a 1–2 sentence plain-language description
          (kind + size + modified + the file's own title/heading/docstring +
          keyword signals + NEW flag)
        - tracks moved / renamed / deleted since last scan
        - preserves the CANONIZATION section below the divider when regenerating
```

```
[4] SEARCH SPINE         python fis.py index <roots> | search <words> [--files] | stale | stats
    D:\GitHub\David-OS\file-intelligence-system\fis.py
        - ONE SQLite (D:\GitHub\David-OS\system\fis_index.sqlite, local disk on
          purpose - SQLite over SMB is unreliable) fed by every .fisnote
        - FTS5 over folder tags + per-file names/titles/descriptions/keywords
        - EVERY hit shows last-scanned age; >30d (configurable) prints
          [STALE - re-scan before trusting] so a hit on old intel is obvious
        - searching the computer = searching this DB
```

Existing related pieces (kept, not replaced):
- `canon.py` — file-level canonical LOCKS (sidecar .canon + D:\GitHub\David-OS\system\canon_registry.json). Locks say "this FILE is canon"; canon_rules.json says "this CONTENT RULE is canon". Complementary.
- `MASTER_EQUATION (1)\000_TOOLS\canon_gate_v3.py` — the ancestor of the regex layer; its 12 rules were lifted into canon_rules.json. Can be retired once the new loop is trusted.

## Status (what's DONE vs TODO)

DONE (2026-08-04, piloted on `\\192.168.2.50\h_hp\Desktop\Folders\MASTER_EQUATION (1)`):
- [x] canon_rules.json seeded with 6 rulings / 13 patterns (product form, Dict 7/8, Dict 4/9, variable dictionary, symmetry pairs, 58-count)
- [x] fis_canon_scan.py (regex + NLP layers, fisnote dispersal, wanted-vs-written reports)
- [x] fisnote_scan.py v3 (3x descriptions, move tracking, canon-section preservation)
- [x] 117 .fisnotes regenerated in the pilot folder

TODO — good tasks for a cheaper coder (Claude reviews the code after):
1. **Adjudication CLI/GUI**: read CANON_SCAN_*.json, step through alerts, record David's verdict per alert (fix / historical / exempt / false-positive) into `canon_verdicts.json`; exempted items are skipped on future scans. This is the "you've gone down the right road" learning loop.
2. **Scheduler**: nightly (or on-demand) run over a folder list (`canon_scan_targets.txt`); only re-scan folders whose .fisnote fingerprint changed.
3. **Approved-fix pass** (LATER, only after David trusts the verdicts): apply verdict="fix" edits with per-file diff preview + backup. Never automatic.
4. **DeepSeek mirror**: batch-box `api_call_22_CLASSIFY_AXIOMIZE_ORGANIZE` variant that takes the same registry and does cloud second-opinion scans when :8700 is down (~$0.006/doc).
5. Tune NLP_THRESHOLD (0.60) and keyword gates from false-positive rates in verdicts.

## Rules for any coder touching this
- Scans NEVER modify content files. Only .fisnote (below divider), 09_TO_REVIEW reports, and verdict/registry JSON.
- The registry is the single source of canon truth; scripts must not hardcode rules.
- Everything must run offline/free by default; cloud (DeepSeek) is opt-in fallback.
- Keep .fisnote parseable-but-readable: YAML frontmatter + markdown, divider contract intact.
