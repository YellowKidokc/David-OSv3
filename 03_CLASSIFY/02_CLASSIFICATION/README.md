# 02_CLASSIFICATION

Deciding what each paper **is**: its standing (how settled), domain, content type (`ct-`),
epistemic role (`ep-`) and topic tags. Rules: `../00_SHARED/TAG_TAXONOMY_v0.4.md`, **Part A** (tags)
and **Part D** (prediction tie-in).

## Built here

| File | Does |
|---|---|
| `gui/review.py` | **The review window** (`../REVIEW.bat`). Every card in one list (tested with 1,053) · filters · "Select ALL n" across the whole filter · accept / reject / set value for one or many · details pane showing where each card stopped · DeepSeek for stuck cards (blind mode, answer its question and re-ask) · nothing written until "Write accepted to cards", backups first · every decision scores the engines |

Uses from `../00_SHARED`: `deepseek_triage.py`, `taxonomy_validator.py`.
Uses from **Prediction_GUI** (`D:\GitHub\Prediction_GUI`, tied in, not copied): the harness, all engines
(including `engines/name_words`, which predicts from the paper's name), and `harness/adapters/sidecars.py`.

## What we learned (2026-10-13)

- Blind, DeepSeek matched the cards' standing on only 8 of 51 from the one-line summaries — it
  mostly (correctly) refused to guess. Real tagging needs the **source papers**, whose location
  is unknown right now.
- No card carries Part A tags yet (`ct-`, `ep-`, topics). That's the next real job.

## Classification tools that already exist elsewhere (pointed to, not moved)

| Tool | Where | What it does |
|---|---|---|
| Domain classifier | `David-OSv3\engine\domain_classifier.py` | Assigns the 5 FIS tags to a file |
| Smart tagger | `David-OSv3\engine\smart_tagger.py` | 4-tag disambiguating tagger (FIS / filetagger) |
| Tagger | `David-OSv3\engine\tagger.py` | Topic slug + compressed tag codes |
| Keyword registry | `David-OSv3\keyword_registry.json`, `engine\config\domains.yaml` | Keyword → domain tables those taggers use |
| Convergence Tagger v3 | `C:\Theophysics_Tagger\` (`START_TAGGER.bat`) | Tags documents against the registry; Browse / Tags tabs |
| Pipeline validators | `taxonomy_validator.py` in `Research-Acquisition\...\backside_SCRIPTS\` and NAS `EVIDENCE_CHAIN_INTAKE\SCRIPTS\` | Same file as `00_SHARED\taxonomy_validator.py`; the evidence pipelines run those copies |
| Obsidian tag registry | `Documents\faiththruphysics.com\10_VAULTS\_Theophysics_v5\.obsidian\plugins\obsidian-semantic-ai\reference\` | `CANONICAL_TAG_TAXONOMY.md`, `THEOPHYSICS_MACHINE_TAG_REGISTRY_v1.0.tsv`, `THEOPHYSICS_MASTER_YAML_SCHEMA_v1.0.md` (March, older than v0.3) |

These taggers use the older FIS 5-tag scheme, not the Part A closed vocabulary. Bringing them onto
Part A is open work.
