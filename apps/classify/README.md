# classify

Classifies files. **Read-only**: it never moves, renames or deletes anything. The Claude API fallback is **off** unless you pass `--allow-ai`.

- Run: `START.bat`, or `python src/run.py FOLDER [--engine fis|chi] [--max-files 500]`
- Output: `data/classify/classification.v1.jsonl` (`shared/contracts/classification.v1.schema.json`). A file whose lowest label confidence is below 0.45 gets `status: needs_review`.

## Engines (unchanged copies of the old code)
| Engine | From | Gives |
|---|---|---|
| `fis` (default) | `file-intelligence-system/fis_classifier.py` + `fis_namer.py` + `structural_evidence.py` | CHI factor, domain, law, content type, doc type, evidence |
| `chi` | `D:\GitHub\FIS\chi_classifier.py` | Master Equation CHI factor from text + filename. It runs with no keyword list; the old keyword extractor (`auto_sort.py`) hasn't moved yet |

Not moved yet: `agents/chi_pipeline.py` and `agents/chi_profiles.py` (they analyze claims and text, not files), and `03_CLASSIFY/02_CLASSIFICATION` (the card review window and prediction tools). Each needs its own decision.

Tests: `python -m pytest tests`. They check that both engines match the old code exactly, that output follows the contract, and that nothing calls the network without `--allow-ai`.
