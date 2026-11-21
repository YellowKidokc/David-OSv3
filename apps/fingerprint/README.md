# fingerprint

Content fingerprinting and near-duplicate detection. **Read-only**: never moves, renames or deletes.

- Run: double-click `START.bat`, or `python src/run.py FOLDER [--threshold 0.7] [--max-files 500]`
- Output: `data/fingerprint/fingerprint.v1.jsonl`, one record per file (`shared/contracts/fingerprint.v1.schema.json`)
- Engine: `src/fingerprint.py`, copied unchanged from FIS. The only edit is the path it uses to find the Rust build.
- Rust: `rust/` (MinHash, ~6x faster). Built automatically by START.bat when cargo exists; falls back to Python if it's missing, fails, or `FIS_DISABLE_RUST=1` is set.
- Tests: `python -m pytest tests` checks that results match the legacy `D:\GitHub\FIS\fingerprint.py`, that Rust and Python agree, and that output follows the contract.
