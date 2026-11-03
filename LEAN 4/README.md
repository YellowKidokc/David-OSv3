# LEAN 4 — Theophysics Corpus Indexer

This folder holds the Python tooling built to index, classify, and verify the POF 2828 / Theophysics LEAN 4 corpus.

## Contents

- `theophysics_corpus_indexer/` — full P1-P2 pipeline
  - `run.py` — inventory + initial classification run
  - `reclassify.py` — content-based re-classification pass (fixes per-location aggregation, classifies non-`.lean` files)
  - `config.py` — source roots, schema config, classification rules
  - `db.py` — Postgres schema and metrics
  - `inventory.py` — read-only scanner / hasher
  - `lean_parser.py` — declaration / import / namespace / `sorry` parser
  - `classifier.py` — ordered keyword series classifier
  - `loaders.py` — manifest / registry / batch-run loaders
  - `receipts/` — run receipts with P1/P2 metrics
  - `spot_check.csv` — 50-file hand-checkable sample

## Quick use

```bash
cd "D:\GitHub\David-OSv3\LEAN 4\theophysics_corpus_indexer"
python run.py --reset
python reclassify.py
```

The Postgres target is `192.168.1.177:2665` database `theophysics_corpus`.

## Notes

- Source roots are READ-ONLY; the indexer copies nothing from them except hashes and metadata.
- `pgvector` is currently not installed on the Postgres server, so the `embeddings` table is deferred.
- Phase 3 (CocoIndex + semantic embeddings) and Phase 4 (CLI pull API) are future work.
