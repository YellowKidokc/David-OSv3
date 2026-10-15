# 03_CLASSIFY

Step 03 of the David-OS sequence: **every paper gets classified before anything runs through the
pipeline** — what it's called, what it is, how settled it is, and the sidecar that points to it.
Steps 01 and 02 (before this) are not defined yet.

## Double-click

| File | Does |
|---|---|
| `REVIEW.bat` | The review window — every card, engine + DeepSeek suggestions, accept / reject / edit one or all |
| `REPORT.bat` | Rebuilds and opens **the classifications doc** (`01_SIDECARS\docs\SIDECAR_CLASSIFICATIONS.md`) |
| `VALIDATE.bat` | Checks a sidecars folder against the rules (drag a folder onto it; default = AXIOM canon sidecars) |

Also on the David-OS launcher (`David-OSv3\gui\START_HERE.bat`) and as `gui\START_03_CLASSIFY_*.bat`.

## Folders

| Folder | System | Rulebook part | Has |
|---|---|---|---|
| `00_SHARED\` | used by all three | — | **`TAG_TAXONOMY_v0.4.md` (the rulebook)**, validator, DeepSeek caller, data |
| `01_SIDECARS\` | Sidecars | Part B | Report script + **the classifications doc** · map of every sidecar tool we have |
| `02_CLASSIFICATION\` | Tagging / standing | Parts A + D | **The review window** · map of every tagger we have |
| `03_RENAMING\` | Naming | Part C | ⚠ a decision for you (3 filename schemes disagree) · map of every renamer we have |
| `ZZZ_DELETE\` | — | — | Old versions and backups. Safe to delete once you're happy |

Each folder's README lists the tools that **already exist elsewhere** for that system (in
`David-OSv3\engine\`, `C:\Theophysics_Tagger\`, Research-Acquisition, the NAS). They're live code
other things run, so they're pointed to, not moved.

## Ties into Prediction_GUI (not copied)

The engines live in `D:\GitHub\Prediction_GUI` (override with the `PREDICTION_GUI` environment
variable). 03 imports from it and runs on its `.venv`. Added there, because they're engine-side:
`engines/name_words/` and `harness/adapters/sidecars.py`. Classification ledgers
(`classify_standing.db`, …) live in `Prediction_GUI\data\`, separate from the YouTube one.

## Order of operations (rulebook, end of Part C)

1. **Inventory** — list, hash, flag duplicates and misfiles — *not built* (`engine\inventory_scan.py`, `fingerprint.py` are close)
2. **Name** — short human card names — *not built* (hand-made so far)
3. **Tag** — read the paper, set standing / domain / ct- / ep- / topics — *not built; needs the source papers*
4. **Review** — `REVIEW.bat` — **built**
5. **Write + check** — cards, JSON, index — **checker built** (`VALIDATE.bat`, `REPORT.bat`); writer not

## Setup on a new machine

Clone Prediction_GUI to `D:\GitHub\Prediction_GUI` (or set `PREDICTION_GUI`) and give it a `.venv`
with `river` and `cpt`. DeepSeek needs `DEEPSEEK_API_KEY` (or `00_SHARED\data\key.txt`).
