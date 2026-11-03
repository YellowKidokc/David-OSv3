# 03_CLASSIFY

## Document Classifier

**Document Classifier** is the overall tool name. **Nabla** stays underneath it
as the address/vector component; it is not a replacement name for the whole
classifier. The existing `nabla` module, protocol and registry fields retain
their names.

The classifier brings together source-based classification, prediction
suggestions, reviewed navigation cards, and Nabla addresses. The prediction
engines and their scoring harness already live in `02_CLASSIFICATION/`; they
do not need importing again. The navigation-card writer and the complete
classification-to-Nabla workflow remain implementation work. Stage 1 currently
supports supplied Nabla proposals and explicitly queues unset vectors.

The χ/Master Equation scorer is a separate feed with its own definitions and
provenance. Its scores must not be copied into Nabla coordinates. The renamer,
sidecar tools and future Notification Hub retain their separate responsibilities.

Step 03 of the David-OS sequence: **every paper gets classified before anything runs through the
pipeline** — what it's called, what it is, how settled it is, and the sidecar that points to it.
Step 01 is `../01_PROFILE` (the doorway wizard — profile the folder first). Step 02 is not
defined yet.

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

## Prediction harness (vendored 2026-10-15)

The engines live in `02_CLASSIFICATION\harness` + `02_CLASSIFICATION\engines` — moved out of the
old standalone `D:\GitHub\Prediction_GUI` repo, which no longer exists on disk (history is on
GitHub and in `ZZZ_DELETE\Prediction_GUI_repo.bundle`). Classification ledgers
(`classify_standing.db`, …) live in `02_CLASSIFICATION\data\`, separate from the YouTube one.
The `PREDICTION_GUI` environment variable still overrides the harness location if ever needed.

Extra launchers: `PREDICT.bat` (engine scoreboard GUI), `INTAKE.bat` (register a dropped engine),
`HARVEST_CHROME_YOUTUBE.bat` / `HARVEST_CLIPBOARD_DITTO.bat` / `WATCH_CLIPBOARD.bat` (event adapters).

## Order of operations (rulebook, end of Part C)

1. **Inventory** — list, hash, flag duplicates and misfiles — *not built* (`engine\inventory_scan.py`, `fingerprint.py` are close)
2. **Name** — short human card names — *not built* (hand-made so far)
3. **Tag** — read the paper, set standing / domain / ct- / ep- / topics — *not built; needs the source papers*
4. **Review** — `REVIEW.bat` — **built**
5. **Write + check** — cards, JSON, index — **checker built** (`VALIDATE.bat`, `REPORT.bat`); writer not

## Setup on a new machine

Run `SETUP_PREDICTION.bat` once — it creates `03_CLASSIFY\.venv` with `river`, `cpt`,
`scikit-learn` and `mabwiser` (see `requirements-prediction.txt`) and runs the smoke test.
DeepSeek needs `DEEPSEEK_API_KEY` (or `00_SHARED\data\key.txt`).
