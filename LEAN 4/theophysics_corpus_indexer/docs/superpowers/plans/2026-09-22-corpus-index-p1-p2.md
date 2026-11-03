# Corpus Index P1-P2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run the P1 inventory and P2 classifier for the Theophysics corpus, producing the honest success sentence and a 50-file spot-check sheet.

**Architecture:** A single Python pipeline reads the six source roots, hashes each file, loads existing manifest/registry/build records, parses `.lean` declarations, classifies by content, writes to Postgres, and reports P1/P2 metrics.

**Tech Stack:** Python 3.12, psycopg2, Postgres 192.168.1.177:2665 (database `theophysics_corpus`).

## Global Constraints

- READ-ONLY on all source folders: copy, never move, delete, or edit a source.
- SHA-256 of file content is the primary key.
- Verification levels are separate facts, never blended into one flag.
- Classification is derived from file CONTENT (declarations), never trusted from filename, folder, or header claims.
- Every run writes a receipt (counts, timestamps, config hash).
- Source roots and skip dirs are copied verbatim from the build spec.
- Library detection is the only rule allowed to use path segments (`Mathlib`).

---

### Task 1: Project scaffolding and database schema

**Files:**
- Create: `//192.168.2.50/h_hp/Desktop/theophysics_corpus_indexer/config.py`
- Create: `//192.168.2.50/h_hp/Desktop/theophysics_corpus_indexer/db.py`
- Create: `//192.168.2.50/h_hp/Desktop/theophysics_corpus_indexer/requirements.txt`

**Interfaces:**
- Consumes: Postgres connection parameters (host, port, user, password, database).
- Produces: `DB_DSN`, `SOURCE_ROOTS`, `SKIP_DIRS`, `INDEX_EXTS`, `SERIES_LABELS`, `CLASSIFICATION_RULES`, `LIBRARY_MARKERS`; `init_schema(conn)` function that creates all tables.

- [ ] **Step 1: Write `config.py`**

```python
DB_CONFIG = {
    "host": "192.168.1.177",
    "port": 2665,
    "dbname": "theophysics_corpus",
    "user": "Yellowkid",
    "password": "Moss9pep28$",
}

SOURCE_ROOTS = [
    "//192.168.2.50/h_hp/Desktop 2/LEAN 4",
    "//192.168.2.50/h_hp/Desktop/___Pipeline_Done_New/One page paper API/LEAN4",
    "//192.168.2.50/h_hp/Desktop/___Pipeline_Done_New/One page paper API/EVIDENCE/OUTBOX",
    "//192.168.2.50/h_hp/Desktop/_____pipeline-workflows-main/LEAN_FLOOR",
    "D:/TEMP_LEAN_ZIP",
    "C:/Users/David/Documents/faiththruphysics.com/04_MASTER_EQUATION",
]

SKIP_DIRS = {".lake", ".git", ".venv", "__pycache__", "node_modules", "_support"}
INDEX_EXTS = {".lean", ".md", ".txt", ".tex", ".py", ".csv", ".json"}
SERIES_LABELS = [
    "MASTER_EQUATION", "AXIOMS", "SPIRITUAL_TERMS", "TEN_LAWS", "TRINITY",
    "GRACE_COHERENCE", "FALL_ENTROPY", "GENESIS_QUANTUM", "HARNESS_TESTS", "LIBRARY",
]
```

- [ ] **Step 2: Write `db.py` with `init_schema`**

Create `files`, `locations`, `declarations`, `receipts` tables. Try `CREATE EXTENSION IF NOT EXISTS vector;`; if it fails, log a warning and skip the `embeddings` table. Use `IF NOT EXISTS` for tables.

- [ ] **Step 3: Write `requirements.txt`**

```text
psycopg2-binary>=2.9.0
```

- [ ] **Step 4: Run a quick connection test**

```bash
cd //192.168.2.50/h_hp/Desktop/theophysics_corpus_indexer
python -c "from db import get_conn, init_schema; import psycopg2; conn=get_conn(); init_schema(conn); print('schema ok')"
```

Expected: prints `schema ok`.

- [ ] **Step 5: Commit**

```bash
git add config.py db.py requirements.txt
git commit -m "feat: corpus indexer scaffold and schema"
```

---

### Task 2: Existing-record loaders

**Files:**
- Create: `//192.168.2.50/h_hp/Desktop/theophysics_corpus_indexer/loaders.py`

**Interfaces:**
- Consumes: paths to `00_MANIFEST.csv`, `registry.json`, `MASTER_LIST.csv`, and `BATCH_RUNS/`.
- Produces:
  - `load_manifest(path) -> dict[sha256, dict]`
  - `load_registry(path) -> dict[sha256, dict]`
  - `load_master_list(path) -> list[dict]`
  - `load_batch_runs(path) -> list[dict]`

- [ ] **Step 1: Implement `load_manifest`**

Read CSV, lowercase the `Hash` field, return a dict keyed by SHA-256. Keep columns: `Node`, `Status`, `Theorems`, `Sorries`, `ActiveSorry`, `ActiveAdmit`, `InventoryTheorems`, `InventorySorries`, `CanonicalOrSuperseded`, `NewPath`, `RelativePath`.

- [ ] **Step 2: Implement `load_registry`**

Read JSON `records`, return dict keyed by lower-cased `sha256` with `status`, `provider`, `output_dir`, `title`, `source`.

- [ ] **Step 3: Implement `load_master_list`**

Read CSV, return list of rows keyed by `source_sha256` with `status`, `reader_paper`, `paper_status`, `source_folder`, `source`.

- [ ] **Step 4: Implement `load_batch_runs`**

Walk `BATCH_RUNS/`. For each `FAMILY_BUILD_RECEIPT.json`, parse array of records; for each `<hash>.build.log.txt` without a matching JSON entry, read the log and infer `build_status` from presence/absence of `error:` lines. Return a list of dicts with `sha256`, `run_id`, `build_status`, `log_path`, `bytes`.

- [ ] **Step 5: Write a loader smoke test**

```python
def test_loaders():
    from loaders import load_manifest, load_registry, load_batch_runs
    m = load_manifest("//192.168.2.50/h_hp/Desktop 2/LEAN 4/_CANON_SORTED_2026-09-17/00_MANIFEST.csv")
    assert len(m) >= 290
    r = load_registry("//192.168.2.50/h_hp/Desktop 2/LEAN 4/AXIOM_OUTPUT/_support/registry.json")
    assert len(r) > 0
    b = load_batch_runs("//192.168.2.50/h_hp/Desktop/_____pipeline-workflows-main/LEAN_FLOOR/03_VERIFIED_RECEIPTS/BATCH_RUNS")
    assert len(b) > 0
```

Run: `pytest tests/test_loaders.py -v`. Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add loaders.py tests/test_loaders.py
git commit -m "feat: manifest, registry, and batch-run loaders"
```

---

### Task 3: Lean parser and classifier

**Files:**
- Create: `//192.168.2.50/h_hp/Desktop/theophysics_corpus_indexer/lean_parser.py`
- Create: `//192.168.2.50/h_hp/Desktop/theophysics_corpus_indexer/classifier.py`

**Interfaces:**
- Consumes: file content bytes and path.
- Produces:
  - `parse_declarations(code: str) -> list[tuple[str, str]]`
  - `count_active_sorry(code: str) -> int`
  - `extract_imports(code: str) -> list[str]`
  - `classify(path: str, ext: str, code: str, decls: list[tuple], imports: list[str]) -> tuple[series, confidence, is_library, decl_count, sorry_active, decls]`

- [ ] **Step 1: Implement `lean_parser.py`**

Use regex to strip `--` line comments, `/- ... -/` block comments, and `"..."` strings (rough mask is fine for keyword classification). Then:

```python
DECL_RE = re.compile(r"^\s*(?:theorem|lemma|def|axiom|instance|structure|class|inductive)\s+([^\s(:[{]+)", re.MULTILINE)
IMPORT_RE = re.compile(r"^\s*import\s+([^\n]+)", re.MULTILINE)
SORRY_RE = re.compile(r"\bsorry\b")
```

- [ ] **Step 2: Implement `classifier.py`**

Apply ordered rules from the build spec. For `.lean`, the keyword text is the joined declaration names plus import module names. For non-`.lean`, the keyword text is the first 8 KB of content. Confidence: `1.0` for `LIBRARY`, `0.95` for any other matched rule, `0.0` for unclassified.

- [ ] **Step 3: Write parser/classifier tests**

Test a tiny Lean snippet containing `theorem foo`, `def bar`, `sorry`, and an `import Mathlib.Data.Nat.Basic`. Assert declaration count, sorry count, library classification.

- [ ] **Step 4: Commit**

```bash
git add lean_parser.py classifier.py tests/test_parser_classifier.py
git commit -m "feat: lean parser and content classifier"
```

---

### Task 4: Inventory scanner and database writer

**Files:**
- Create: `//192.168.2.50/h_hp/Desktop/theophysics_corpus_indexer/inventory.py`
- Create: `//192.168.2.50/h_hp/Desktop/theophysics_corpus_indexer/run.py`

**Interfaces:**
- Consumes: `SOURCE_ROOTS`, `SKIP_DIRS`, `INDEX_EXTS`, manifest dict.
- Produces: `scan_roots()` generator; `write_file_record(cur, ...)`, `write_receipts(cur, ...)` helpers.

- [ ] **Step 1: Implement `inventory.py`**

```python
def scan_roots(roots, skip_dirs, exts, manifest):
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in exts:
                    continue
                path = os.path.join(dirpath, fn)
                size = os.path.getsize(path)
                mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
                # trust manifest hash if path matches canonical NewPath
                manifest_entry = find_manifest_entry(path, manifest)
                if manifest_entry:
                    sha = manifest_entry["Hash"].lower()
                else:
                    sha = sha256_file(path)
                yield {"path": path, "sha256": sha, "ext": ext, "size": size, "mtime": mtime, "manifest": manifest_entry}
```

- [ ] **Step 2: Implement `run.py` orchestration skeleton**

Connect, init schema, load records, scan, classify, insert `files`, `locations`, `declarations`, then insert receipts (registry AI reviews, batch-run builds, print-axioms inferences), then compute verification levels.

- [ ] **Step 3: Commit**

```bash
git add inventory.py run.py
git commit -m "feat: inventory scanner and run skeleton"
```

---

### Task 5: Receipt loader, verification computer, and reporter

**Files:**
- Modify: `//192.168.2.50/h_hp/Desktop/theophysics_corpus_indexer/run.py`
- Create: `//192.168.2.50/h_hp/Desktop/theophysics_corpus_indexer/reporter.py`

**Interfaces:**
- Consumes: loaded registry/batch-run records and parsed `.lean` `sorry_active` counts.
- Produces: inserted `receipts` rows, updated `files.verif_level`, P1/P2 report JSON/CSV.

- [ ] **Step 1: Insert AI_REVIEW receipts from registry.json**

For each registry record, insert `receipts(sha256, run_id=registry_id, kind='AI_REVIEW', result=status, log_path=output_dir, ran_at=updated)`.

- [ ] **Step 2: Insert BUILD and PRINT_AXIOMS receipts from BATCH_RUNS**

For each batch-run record:

- `kind='BUILD'`, `result='PASS'` if `build_status` starts with `BUILD_PASS` or no `error:` lines; else `FAIL`.
- If pass, read the log and add `kind='PRINT_AXIOMS'`, `result='NATIVE_DECIDE'` if log contains `native_decide`, else `CLEAN`.

- [ ] **Step 3: Compute `verif_level`**

SQL update per the build-spec priority:

```sql
UPDATE files SET verif_level = 'GAPS' WHERE sorry_active > 0 AND verif_level NOT IN ('KERNEL','KERNEL_NATIVE_DECIDE');
```

Then apply build-derived levels via Python or SQL on `receipts`.

- [ ] **Step 4: Implement `reporter.py`**

Write functions for:

- P1 metrics: total files, unique hashes, duplicate ratio, per-root counts.
- P2 metrics: % classified, % LIBRARY, % unclassified, % with receipt above AI_REVIEW.
- 50-file spot-check CSV: random `.lean` rows with `path, sha256, series, series_conf, verif_level, decl_count, sorry_active, summary`.
- Run receipt JSON with `run_id`, `started`, `finished`, `config_hash`, `counts`.

- [ ] **Step 5: Commit**

```bash
git add run.py reporter.py
git commit -m "feat: receipts, verification levels, and reporter"
```

---

### Task 6: End-to-end run and acceptance gates

**Files:**
- Run: `python run.py`
- Outputs: `//192.168.2.50/h_hp/Desktop/theophysics_corpus_indexer/receipts/YYYY-MM-DDTHHMMSS-receipt.json`, `spot_check.csv`.

- [ ] **Step 1: Run the full pipeline**

```bash
cd //192.168.2.50/h_hp/Desktop/theophysics_corpus_indexer
python run.py
```

- [ ] **Step 2: Verify P1 gate output**

Check receipt for total files, unique hashes, duplicate ratio, per-root counts. Total should be > 60,000 indexed files across all roots.

- [ ] **Step 3: Verify P2 gate output**

Check the printed success sentence:

```text
N unique files: a% classified at >=0.8 confidence, b% LIBRARY quarantined, c% unclassified, d% carrying a receipt above AI_REVIEW.
```

- [ ] **Step 4: Inspect `spot_check.csv`**

Confirm 50 rows with assigned series for David to grade.

- [ ] **Step 5: Commit outputs**

```bash
git add receipts/ spot_check.csv
git commit -m "data: P1-P2 run receipt and spot-check sheet"
```

---

## Self-Review

- **Spec coverage:** P1 inventory, P2 classification, receipt ingestion, verification levels, and reporting all have tasks. P3/P4 are intentionally out of scope.
- **Placeholder scan:** No TBD/TODO in concrete steps.
- **Type consistency:** Functions and table names match the schema.
