# FIS AI_NLP

This is the one root for File Intelligence System enrichment rails. It is a
control surface, not another catalog and not a source-content folder.

## Order of work

1. `fis_folder_memory.py` inventories every eligible file and produces
   deterministic local classifications and retrieval keywords.
2. The post-scan local-Ollama queue enriches changed text files with proposed
   keywords, topic phrases, and a source-bound one-sentence summary.
3. Results are stored in the FIS SQLite registry and surfaced in generated file
   dossiers. Source files are never rewritten.

## Boundaries

- Local AI may propose retrieval metadata only.
- It cannot rename, move, delete, archive, promote canon, or render truth and
  quality decisions.
- Every local-AI result stores its model, scan time, and source fingerprint.
- `runs/` is for receipts and batch reports only; it is never a replacement for
  the source tree.

## Existing rails retained in place

- `..\fis_classifier.py`: deterministic FIS classification.
- `..\fis_folder_memory.py`: registry and clickable HTML dossiers.
- `..\nlp_light\`: existing lightweight NLP material.
- `..\_nlp_runs\`: historic/generated run output.
- `..\..\fis-atlas\run_tagger.py`: corpus association discovery.

The current local model endpoint is Ollama at `http://127.0.0.1:11434`. The
default FIS enrichment model is `qwen3:4b-instruct`.
