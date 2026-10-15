# 00_SHARED

Used by all three systems (01_SIDECARS, 02_CLASSIFICATION, 03_RENAMING).

| File | What |
|---|---|
| `TAG_TAXONOMY_v0.4.md` | **The rulebook — the only copy.** A tags · B sidecars · C naming · D prediction tie-in · classification order of operations |
| `taxonomy_validator.py` | The checker. `python taxonomy_validator.py "<folder>\sidecars"` (or `../VALIDATE.bat`) |
| `deepseek_triage.py` | DeepSeek caller for stuck cards: JSON answers, can ask you a question, `blind=True` hides the current value. Key: `DEEPSEEK_API_KEY` or `data/key.txt`. Retries like `API\000_QUICK_CALL` |
| `data/` | DeepSeek cache, review decision log, optional `key.txt` — all git-ignored |
