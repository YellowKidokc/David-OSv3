# Folder Understanding Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single folder-intake pipeline in David-OSv3 that interviews the user, scans a folder, classifies it by Shape/Purpose/Position, detects anomalies, proposes deduplication/reorganization actions, simulates the action sequence, and executes only after a profile-driven gate approves each step.

**Architecture:** A thin orchestrator (`engine/folder_intake.py`) wires existing modules (`01_PROFILE/profile_core.py`, `engine/understand.py`, `engine/fingerprint.py`, `engine/flatten_dedupe.py`, `engine/gate.py`, `engine/canon_sidecar.py`, `engine/aggregate_report.py`) and adds small focused modules for the missing pieces: protected snapshots, tiered reading, position inference, near-duplicate grouping, anomaly detection, plan simulation, and report generation.

**Tech Stack:** Python ≥3.11 stdlib (repo floor), existing SQLite schema, pytest. No new pip dependencies.

**Spec:** `docs/specs/2026-10-25-folder-understanding-pipeline-design.md`

## Global Constraints

- Python ≥ 3.11 (`pyproject.toml`).
- Core engine modules stay stdlib-only; reuse `engine/fingerprint.py`, `engine/gate.py`, `engine/canon_sidecar.py` as-is.
- Every mutating action is checked twice: at plan time and at apply time.
- Source folders are never modified during `interview`, `scan`, `dry-run`, or `simulate`.
- Fail closed: missing profile → preview-only policy; missing/corrupt rules → ASK everything.
- All file paths use `pathlib.Path`; Windows case-insensitive comparisons where needed.
- Commit style: short imperative (`gate: load folder profile`, `intake: add plan simulator`).

## Review Focus

1. **Profile says a folder is off-limits:** mutating action must `BLOCK` even if the path itself is not a system folder — test in Task 7.
2. **Business/personal boundary crossing:** a `copy` from a business root into a personal root must `ASK` — test in Task 7.
3. **Sequence-level danger:** a `delete archive/` after a `move file → archive/` must be caught by the simulator, not the per-action gate — test in Task 6.
4. **Near-duplicate word-order sensitivity:** two texts with the same words in different order must not be flagged as duplicates — test in Task 4.
5. **Empty files must not match each other:** `near_dup()` short-text guard returns `TOO_SHORT`, not a false duplicate — test in Task 4.

---

### Task 1: Add protected snapshot to `01_PROFILE/profile_core.py`

**Files:**
- Modify: `01_PROFILE/profile_core.py`
- Modify: `config/rules/onboarding_questions.v1.json`
- Create: `tests/test_profile_snapshot.py`

**Interfaces:**
- Consumes: `answers["fire_carry_files"]` from the questionnaire.
- Produces: `protected_snapshot(root, files, out_dir) -> dict` returning the zip path and file count.

- [ ] **Step 1: Add the fire-carry question to the questionnaire**

In `config/rules/onboarding_questions.v1.json`, add after `automation_comfort`:

```json
{
  "id": "fire_carry_files",
  "order": 21,
  "question": "If the house were on fire, which files or folders would you carry out?",
  "answer_type": "path_or_description_list",
  "feeds": ["safety.fire_carry_files", "profile.protected_snapshot"]
}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_profile_snapshot.py
import json
import zipfile
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "01_PROFILE"))
import profile_core as pc

def test_protected_snapshot_creates_zip(tmp_path):
    root = tmp_path / "home"
    root.mkdir()
    (root / "important.md").write_text("keep me", encoding="utf-8")
    out = tmp_path / "snaps"
    result = pc.protected_snapshot(root, ["important.md"], out)
    assert result["zip"].endswith(".zip")
    assert Path(result["zip"]).exists()
    with zipfile.ZipFile(result["zip"]) as z:
        names = z.namelist()
    assert any("important.md" in n for n in names)
    assert (root / "important.md").exists()  # source untouched
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_profile_snapshot.py -q`
Expected: FAIL — `AttributeError: module 'profile_core' has no attribute 'protected_snapshot'`.

- [ ] **Step 4: Implement `protected_snapshot()`**

In `01_PROFILE/profile_core.py`:

```python
def protected_snapshot(root, files, out_dir):
    """Zip the named fire-carry files before any other action runs."""
    from datetime import datetime
    import zipfile
    root = Path(root)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = root.name or "root"
    zip_path = out / f"{label}_{stamp}_protected.zip"
    written = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for spec in files or []:
            for p in root.rglob(spec) if not (root / spec).exists() else [root / spec]:
                if p.is_file() and p.resolve().is_relative_to(root.resolve()):
                    zf.write(p, arcname=p.relative_to(root).as_posix())
                    written += 1
    return {"zip": str(zip_path), "files": written}
```

Also update `build_profile()` to carry `fire_carry_files` into the profile under `routing_hints` or a new `protected_files` list:

```python
fire = answers.get("fire_carry_files")
if fire:
    profile["protected_files"] = [x.strip() for x in (fire.split(",") if isinstance(fire, str) else fire) if x.strip()]
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_profile_snapshot.py -q`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add 01_PROFILE/profile_core.py config/rules/onboarding_questions.v1.json tests/test_profile_snapshot.py
git commit -m "profile: add fire-carry protected snapshot"
```

---

### Task 2: Extend `engine/understand.py` for tiered file reading

**Files:**
- Modify: `engine/understand.py` (schema + `scan()`)
- Create: `tests/test_understand_tiers.py`

**Interfaces:**
- Consumes: file paths.
- Produces: `files` rows now include `norm_fp`, `content_words`, `first_heading`, `frontmatter` for suspicious files.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_understand_tiers.py
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "engine"))
import understand as u

def test_tiered_read_flags_suspicious(tmp_path):
    p = tmp_path / "Untitled 7.md"
    p.write_text("# Title\n\nhello world", encoding="utf-8")
    info = u.tiered_read(p, suspicious=True)
    assert info["tier"] == 2
    assert info["first_heading"] == "Title"
    assert info["content_words"] > 0

def test_tiered_read_skips_content_for_safe_file(tmp_path):
    p = tmp_path / "normal.txt"
    p.write_text("just some text", encoding="utf-8")
    info = u.tiered_read(p, suspicious=False)
    assert info["tier"] == 1
    assert "norm_fp" not in info or info["norm_fp"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_understand_tiers.py -q`
Expected: FAIL — `AttributeError: module 'understand' has no attribute 'tiered_read'`.

- [ ] **Step 3: Add schema columns and `tiered_read()`**

In `engine/understand.py`, update `SCHEMA` `files` table:

```sql
ALTER TABLE files ADD COLUMN norm_fp TEXT;
ALTER TABLE files ADD COLUMN content_words INT;
ALTER TABLE files ADD COLUMN first_heading TEXT;
ALTER TABLE files ADD COLUMN frontmatter TEXT;
```

Add helper:

```python
import re
import hashlib

_STOPWORDS = frozenset("the and for that with this from are was were has have had not but its into their there than then them".split())
_TOKEN = re.compile(r"\w{3,}")

def _content_words(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS]

def _first_heading(text: str) -> str | None:
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else None

def _frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 3:
            return json.dumps({"raw": text[3:end].strip()})
    return "{}"

def _norm_fp(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).strip().lower().encode()).hexdigest()

def tiered_read(path: Path, suspicious: bool = False) -> dict:
    info = {"tier": 1}
    if not suspicious:
        return info
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return info
    info["tier"] = 2
    info["norm_fp"] = _norm_fp(text)
    info["content_words"] = len(_content_words(text))
    info["first_heading"] = _first_heading(text)
    info["frontmatter"] = _frontmatter(text)
    return info
```

In `scan()`, mark a file suspicious if:
- extension is in TEXT set,
- name matches `r"(?i)^Untitled\s|Clipboard|New folder"`,
- or size is 0,
- or it is a duplicate-size candidate.

Update the `INSERT OR REPLACE INTO files` columns and values accordingly.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_understand_tiers.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add engine/understand.py tests/test_understand_tiers.py
git commit -m "understand: add tiered read with norm_fp, heading, frontmatter"
```

---

### Task 3: Add Shape and Position classification

**Files:**
- Modify: `engine/understand.py`
- Create: `engine/intake_position.py`
- Create: `tests/test_intake_position.py`

**Interfaces:**
- Consumes: `folders`, `files`, `observations`, `inferences` tables.
- Produces: `position_inferences` table; shape stored as a `shape` inference on each folder.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_intake_position.py
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "engine"))
import intake_position as pos

def test_position_inside_project(tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    (root / ".git").mkdir()
    (root / "assets").mkdir()
    (root / "assets" / "logo.png").write_bytes(b"png")
    # Simulate a minimal schema
    con = sqlite3.connect(":memory:")
    con.executescript("""
        CREATE TABLE folders(scan_id INT, path TEXT, parent TEXT, depth INT);
        CREATE TABLE observations(scan_id INT, folder TEXT, name TEXT, value TEXT, source TEXT);
        CREATE TABLE position_inferences(scan_id INT, folder TEXT, parent_kind TEXT,
            sibling_kinds TEXT, nearest_project_root TEXT, depth_from_root INT,
            confidence REAL, evidence TEXT);
    """)
    con.execute("INSERT INTO folders VALUES (1, ?, '', 0)", (str(root),))
    con.execute("INSERT INTO folders VALUES (1, ?, ?, 1)", (str(root / "assets"), str(root)))
    con.execute("INSERT INTO observations VALUES (1, ?, 'marker', 'git_repo', 'fs')", (str(root),))
    pos.infer(1, con)
    row = con.execute("SELECT * FROM position_inferences WHERE folder=?", (str(root / "assets"),)).fetchone()
    assert row is not None
    assert row[4] == str(root)  # nearest_project_root
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_intake_position.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'intake_position'`.

- [ ] **Step 3: Implement shape mapping and position inference**

In `engine/understand.py`, after `predict_folder()` sets `kind`, add:

```python
shape_map = {
    "code": "project" if (marks & PROJECT_MARKERS) else "system",
    "documents": "document",
    "pictures": "media", "video": "media", "audio": "media",
    "data": "data",
    "mixed": "dump",
    "needs_sorting": "dump",
    "archive": "archive",
    "other": "system",
}
shape = shape_map.get(kind, "unknown")
add_inference(con, scan_id, folder, "shape", shape, conf, src, evidence + [f"shape={shape}"])
```

Create `engine/intake_position.py`:

```python
from __future__ import annotations
import json
from pathlib import Path

PROJECT_MARKERS = {".git", "pyproject.toml", "package.json", "cargo.toml", "requirements.txt", "lakefile.lean"}

def _nearest_project_root(folder: str, observations: dict[str, set[str]]) -> str | None:
    p = Path(folder)
    for ancestor in [p, *p.parents]:
        obs = observations.get(str(ancestor), set())
        if any(m in obs for m in PROJECT_MARKERS):
            return str(ancestor)
    return None

def infer(scan_id: int, con) -> None:
    obs_rows = con.execute("SELECT folder, value FROM observations WHERE scan_id=? AND name='marker'", (scan_id,))
    obs: dict[str, set[str]] = {}
    for folder, value in obs_rows:
        obs.setdefault(folder, set()).add(value)
    shapes = {}
    for folder, value in con.execute("SELECT folder, value FROM inferences WHERE scan_id=? AND facet='shape'", (scan_id,)):
        shapes[folder] = value
    parents = {}
    for folder, parent in con.execute("SELECT path, parent FROM folders WHERE scan_id=?", (scan_id,)):
        parents[folder] = parent
    # sibling kinds
    sibling_kinds: dict[str, list[str]] = {}
    for folder, parent in parents.items():
        sibling_kinds.setdefault(parent, []).append(shapes.get(folder, "unknown"))
    for folder, parent in parents.items():
        nearest = _nearest_project_root(folder, obs)
        depth = 0
        p = Path(folder)
        while nearest and p != Path(nearest):
            p = p.parent
            depth += 1
        evidence = [f"parent_shape={shapes.get(parent, 'unknown')}", f"siblings={sibling_kinds.get(parent, [])}"]
        con.execute("""
            INSERT INTO position_inferences(scan_id, folder, parent_kind, sibling_kinds,
                nearest_project_root, depth_from_root, confidence, evidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (scan_id, folder, shapes.get(parent, "unknown"),
              json.dumps(sibling_kinds.get(parent, [])),
              nearest, depth, 0.7 if nearest else 0.5, json.dumps(evidence)))
    con.commit()
```

Add the `position_inferences` table to `engine/understand.py` `SCHEMA` and call `intake_position.infer(scan_id, con)` at the end of `scan()`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_intake_position.py -q`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add engine/understand.py engine/intake_position.py tests/test_intake_position.py
git commit -m "understand: add shape and position inferences"
```

---

### Task 4: Add near-duplicate detection

**Files:**
- Modify: `engine/understand.py`
- Create: `tests/test_understand_near_dup.py`

**Interfaces:**
- Consumes: `files` rows with `norm_fp` and text content.
- Produces: `near_dup_groups` table with `NEAR_DUPLICATE` and `RELATED_VERSION` verdicts.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_understand_near_dup.py
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "engine"))
import understand as u
import fingerprint as fp

def test_near_dup_detects_reordered_words(tmp_path):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("The quick brown fox jumps over the lazy dog.", encoding="utf-8")
    b.write_text("Brown the quick fox the lazy dog jumps over.", encoding="utf-8")
    result = fp.near_dup(a.read_text(encoding="utf-8"), b.read_text(encoding="utf-8"))
    assert result["verdict"] in ("DIFFERENT", "RELATED_VERSION")
    assert result["verdict"] != "NEAR_DUPLICATE"

def test_short_text_is_too_short():
    result = fp.near_dup("Hello world", "Hello world")
    assert result["verdict"] == "EXACT"
    result2 = fp.near_dup("Hello world", "Hello there")
    assert result2["verdict"] == "TOO_SHORT"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_understand_near_dup.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'understand'` or no `find_near_duplicates`.

- [ ] **Step 3: Implement near-duplicate grouping**

Add to `engine/understand.py`:

```sql
CREATE TABLE IF NOT EXISTS near_dup_groups (
    scan_id INT, group_id TEXT, verdict TEXT, jaccard REAL, hamming_v2 INT, paths TEXT
);
```

Add function:

```python
import fingerprint as fp

def find_near_duplicates(con, scan_id, log=print):
    rows = con.execute("""
        SELECT path, norm_fp, content_words FROM files
        WHERE scan_id=? AND norm_fp IS NOT NULL AND content_words >= ?
    """, (scan_id, fp.MIN_WORDS)).fetchall()
    by_fp: dict[str, list[str]] = {}
    for path, norm_fp, _ in rows:
        by_fp.setdefault(norm_fp, []).append(path)
    # First, exact normalized-text matches
    group_id = 0
    for norm_fp, paths in by_fp.items():
        if len(paths) > 1:
            con.execute("INSERT INTO near_dup_groups VALUES (?,?,?,?,?,?)",
                        (scan_id, f"ndg-{group_id}", "EXACT_NORM", 1.0, 0, json.dumps(paths)))
            group_id += 1
    # Then candidate pairs by simhash_v2 for non-exact
    comparable = [(p, fp.simhash_v2(Path(p).read_text(encoding="utf-8", errors="replace"))) for p, _, _ in rows]
    comparable = [(p, s) for p, s in comparable if s is not None]
    seen = set()
    for i in range(len(comparable)):
        for j in range(i + 1, len(comparable)):
            a, sa = comparable[i]
            b, sb = comparable[j]
            if a == b or fp.hamming_v2(sa, sb) > fp.CANDIDATE_HAMMING:
                continue
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)
            text_a = Path(a).read_text(encoding="utf-8", errors="replace")
            text_b = Path(b).read_text(encoding="utf-8", errors="replace")
            v = fp.near_dup(text_a, text_b)
            if v["verdict"] in ("NEAR_DUPLICATE", "RELATED_VERSION"):
                con.execute("INSERT INTO near_dup_groups VALUES (?,?,?,?,?,?)",
                            (scan_id, f"ndg-{group_id}", v["verdict"],
                             v.get("jaccard"), v.get("hamming_v2"), json.dumps([a, b])))
                group_id += 1
    con.commit()
```

Call `find_near_duplicates(con, scan_id, log)` at the end of `scan()` after `find_duplicates()`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_understand_near_dup.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add engine/understand.py tests/test_understand_near_dup.py
git commit -m "understand: add near-duplicate detection"
```

---

### Task 5: Add anomaly detection module

**Files:**
- Create: `engine/intake_anomalies.py`
- Create: `tests/test_intake_anomalies.py`

**Interfaces:**
- Consumes: `files`, `folders`, `inferences`, `position_inferences`, `near_dup_groups`, `dup_groups` tables.
- Produces: `anomalies` table.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_intake_anomalies.py
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "engine"))
import intake_anomalies as anom

def test_empty_file_anomaly(tmp_path):
    con = sqlite3.connect(":memory:")
    con.executescript("""
        CREATE TABLE files(scan_id INT, path TEXT, folder TEXT, ext TEXT, kind TEXT, size INT, sha256 TEXT, norm_fp TEXT, content_words INT);
        CREATE TABLE anomalies(scan_id INT, anomaly_id TEXT, severity TEXT, path TEXT, kind TEXT, why TEXT, evidence TEXT);
        CREATE TABLE folders(scan_id INT, path TEXT, kind_counts TEXT);
    """)
    con.execute("INSERT INTO files VALUES (1, ?, ?, '.md', 'documents', 0, 'a', 'a', 3)", (str(tmp_path / "empty.md"), str(tmp_path)))
    con.execute("INSERT INTO folders VALUES (1, ?, '{}')", (str(tmp_path),))
    anom.detect(1, con)
    rows = con.execute("SELECT kind FROM anomalies WHERE scan_id=1").fetchall()
    assert any("empty" in r[0] for r in rows)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_intake_anomalies.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'intake_anomalies'`.

- [ ] **Step 3: Implement `intake_anomalies.py`**

Create `engine/intake_anomalies.py`:

```python
from __future__ import annotations
import json
import re
from collections import defaultdict
from pathlib import Path

KIND_PRIORITY = {"system": 0, "archive": 1, "project": 2, "document": 3, "data": 4, "media": 5, "dump": 6, "unknown": 7}

def detect(scan_id: int, con) -> None:
    def add(kind, severity, path, why, evidence):
        con.execute("INSERT INTO anomalies VALUES (?,?,?,?,?,?,?)",
                    (scan_id, kind, severity, str(path), kind, why, json.dumps(evidence)))
    # Empty / near-empty
    for path, words in con.execute("SELECT path, content_words FROM files WHERE scan_id=? AND content_words IS NOT NULL AND content_words < 10", (scan_id,)):
        add("empty_or_near_empty", "low", path, "text file has fewer than 10 content words", {"content_words": words})
    # Name says nothing
    noise = re.compile(r"^(Untitled|New folder|Clipboard)\b", re.I)
    for path, in con.execute("SELECT path FROM files WHERE scan_id=?", (scan_id,)):
        if noise.search(Path(path).name):
            add("name_says_nothing", "low", path, "generic name gives no hint about content", {"name": Path(path).name})
    # Size outlier per folder
    folder_sizes = defaultdict(list)
    for folder, size in con.execute("SELECT folder, size FROM files WHERE scan_id=?", (scan_id,)):
        if size:
            folder_sizes[folder].append(size)
    medians = {f: sorted(s)[len(s)//2] for f, s in folder_sizes.items() if s}
    for path, folder, size in con.execute("SELECT path, folder, size FROM files WHERE scan_id=?", (scan_id,)):
        med = medians.get(folder, 0)
        if med and size > med * 10 and size > 1024 * 1024:
            add("size_outlier", "medium", path, f"size {size} is >10x folder median {med}", {"size": size, "median": med})
    # Wrong neighbourhood
    folder_shape = {}
    for folder, value in con.execute("SELECT folder, value FROM inferences WHERE scan_id=? AND facet='shape'", (scan_id,)):
        folder_shape[folder] = value
    for path, folder, kind in con.execute("SELECT path, folder, kind FROM files WHERE scan_id=?", (scan_id,)):
        shape = folder_shape.get(folder, "unknown")
        if kind == "code" and shape == "document":
            add("wrong_neighbourhood", "medium", path, f"code file inside {shape} folder", {"file_kind": kind, "folder_shape": shape})
    # Same title, different content
    headings = defaultdict(list)
    for path, heading, sha in con.execute("SELECT path, first_heading, sha256 FROM files WHERE scan_id=? AND first_heading IS NOT NULL", (scan_id,)):
        headings[heading].append((path, sha))
    for heading, pairs in headings.items():
        if len(set(sha for _, sha in pairs)) > 1:
            add("same_title_different_content", "high", pairs[0][0], "same first heading but different sha256", {"heading": heading, "paths": [p for p, _ in pairs]})
    con.commit()
```

Add `anomalies` table to `engine/understand.py` `SCHEMA` and call `intake_anomalies.detect(scan_id, con)` at the end of `scan()`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_intake_anomalies.py -q`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add engine/intake_anomalies.py tests/test_intake_anomalies.py engine/understand.py
git commit -m "intake: add Part-2 anomaly detection"
```

---

### Task 6: Add plan simulator

**Files:**
- Create: `engine/plan_simulator.py`
- Create: `tests/test_plan_simulator.py`

**Interfaces:**
- Consumes: `MANIFEST.csv` rows with `action`, `source_path`, `target_path`.
- Produces: `SIMULATION_REPORT.md` listing passed/blocked/ask/ordering problems.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_plan_simulator.py
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "engine"))
import plan_simulator as sim

def test_simulator_catches_delete_after_move(tmp_path):
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("""action,source_path,target_path
move,a.txt,archive/a.txt
delete,archive,
""", encoding="utf-8")
    report = sim.simulate(manifest, profile={})
    assert any("delete" in p and "contains" in p for p in report["ordering_problems"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_plan_simulator.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'plan_simulator'`.

- [ ] **Step 3: Implement `plan_simulator.py`**

Create `engine/plan_simulator.py`:

```python
from __future__ import annotations
import csv
import json
from pathlib import Path
from collections import defaultdict

class TreeModel:
    def __init__(self):
        self.paths: set[str] = set()
        self.folders: set[str] = set()
    def add(self, p: str):
        self.paths.add(p)
        self.folders.add(str(Path(p).parent))
    def remove(self, p: str):
        self.paths.discard(p)
    def exists(self, p: str) -> bool:
        return p in self.paths

def simulate(manifest_path: str | Path, profile: dict) -> dict:
    tree = TreeModel()
    rows = list(csv.DictReader(open(manifest_path, encoding="utf-8")))
    passed, blocked, ask, problems = 0, 0, 0, []
    targets_seen: dict[str, int] = {}
    for i, row in enumerate(rows, 1):
        action = row["action"]
        src = row["source_path"]
        tgt = row.get("target_path") or ""
        # Simple per-action policy checks
        if tgt and action in ("copy", "move") and targets_seen.get(tgt):
            problems.append(f"step {i}: {action} target collision at {tgt} (also step {targets_seen[tgt]})")
        if action == "move" and not tree.exists(src):
            problems.append(f"step {i}: move source missing in simulated tree: {src}")
        if action == "delete" and tgt:
            # deleting a folder that contains files moved there earlier
            contained = [p for p in tree.paths if p.startswith(tgt.rstrip("/") + "/")]
            if contained:
                problems.append(f"step {i}: delete {tgt} would remove {len(contained)} file(s) introduced earlier, e.g. {contained[0]}")
        # Apply to simulated tree
        if action == "copy":
            if tgt: tree.add(tgt); targets_seen[tgt] = i
        elif action == "move":
            if tgt:
                tree.remove(src); tree.add(tgt); targets_seen[tgt] = i
        elif action == "delete":
            tree.remove(src)
            for p in list(tree.paths):
                if p.startswith(src.rstrip("/") + "/"):
                    tree.remove(p)
        passed += 1
    return {"total": len(rows), "passed": passed, "blocked": blocked, "ask": ask,
            "ordering_problems": problems}
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_plan_simulator.py -q`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add engine/plan_simulator.py tests/test_plan_simulator.py
git commit -m "intake: add plan simulator for sequence-level problems"
```

---

### Task 7: Extend `engine/gate.py` with profile-driven rules and direct CLI

**Files:**
- Modify: `engine/gate.py`
- Create: `engine/gate_cli.py` (or add subcommand later)
- Create: `tests/test_gate_profile.py`

**Interfaces:**
- Consumes: `config/folder_profiles.json`, `.folder.fmeta`, action + paths.
- Produces: `Decision` with profile-fired rules.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gate_profile.py
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "engine"))
import gate as g

def test_off_limits_path_blocks():
    prof = {"off_limits": [r"C:\Users\David\Secrets"], "approval_floor": "approval_required"}
    d = g.Gate.load(REPO / "config" / "rules", prof).evaluate(
        "move", [r"C:\Users\David\Secrets\file.txt"], {"batch_size": 1})
    assert d.verdict == g.BLOCK

def test_business_to_personal_crossing_asks():
    prof = {"domains": [{"root": r"C:\Business", "type": "business"}, {"root": r"C:\Personal", "type": "personal"}]}
    d = g.Gate.load(REPO / "config" / "rules", prof).evaluate(
        "copy", [r"C:\Business\doc.txt", r"C:\Personal\doc.txt"], {"batch_size": 1})
    assert d.verdict == g.ASK
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_gate_profile.py -q`
Expected: FAIL — off-limits/domain rules not implemented.

- [ ] **Step 3: Extend `engine/gate.py`**

Add helper methods to `Gate`:

```python
def _off_limits(self, paths: list[str]) -> Decision | None:
    for pattern in self.profile.get("off_limits", []):
        for p in paths:
            if Path(p).match(pattern) or pattern.lower() in p.lower():
                return Decision(BLOCK, [{"rule_id": "profile.off_limits",
                                         "reason": f"path matches off-limits pattern '{pattern}'"}])
    return None

def _domain_boundary(self, action_id: str, paths: list[str]) -> Decision | None:
    if action_id not in MUTATING or len(paths) < 2:
        return None
    domains = self.profile.get("domains", [])
    def domain_of(p: str):
        for d in domains:
            root = d.get("root", "")
            if Path(p).resolve().is_relative_to(Path(root).resolve()):
                return d.get("type")
        return None
    types = {domain_of(p) for p in paths if domain_of(p)}
    if len(types) > 1:
        return Decision(ASK, [{"rule_id": "profile.domain_boundary",
                               "reason": f"action crosses domain boundary: {types}"}])
    return None

def _fire_carry(self, paths: list[str]) -> Decision | None:
    protected = {str(Path(p).resolve()) for p in self.profile.get("protected_files", [])}
    for p in paths:
        if str(Path(p).resolve()) in protected:
            return Decision(BLOCK, [{"rule_id": "profile.fire_carry",
                                     "reason": "file is in fire-carry protected snapshot"}])
    return None
```

Call these in `evaluate()` after `_hard_safety()` and before the other checks.

Create `engine/gate_cli.py`:

```python
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "engine"))
import gate as g

def main(argv=None):
    ap = argparse.ArgumentParser(description="Pre-flight gate check for any file action.")
    ap.add_argument("action")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--profile", type=Path)
    args = ap.parse_args(argv)
    profile = {}
    if args.profile and args.profile.exists():
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
    decision = g.Gate.load(REPO / "config" / "rules", profile).evaluate(args.action, args.paths)
    print(json.dumps(decision.to_json(), indent=2))
    return 0 if decision.verdict in (g.ALLOW, g.PREVIEW) else 1

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_gate_profile.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add engine/gate.py engine/gate_cli.py tests/test_gate_profile.py
git commit -m "gate: profile-driven off-limits, domain boundary, and fire-carry rules"
```

---

### Task 8: Refactor `engine/flatten_dedupe.py` to consume scan data and produce a gated manifest

**Files:**
- Modify: `engine/flatten_dedupe.py`
- Create: `tests/test_flatten_manifest.py`

**Interfaces:**
- Consumes: `engine/understand.py` SQLite records + `engine/gate.py` decisions.
- Produces: `MANIFEST.csv` with action, rule, reason, gate verdict.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_flatten_manifest.py
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "engine"))
import flatten_dedupe as fd

def test_build_manifest_keeps_keeper(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    db = tmp_path / "scan.sqlite"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE files(scan_id INT, path TEXT, folder TEXT, ext TEXT, size INT, mtime REAL, sha256 TEXT, norm_fp TEXT, content_words INT);
    """)
    base = tmp_path / "src"
    base.mkdir()
    (base / "a.md").write_text("hello world", encoding="utf-8")
    (base / "archive").mkdir()
    (base / "archive" / "a.md").write_text("hello world", encoding="utf-8")
    con.execute("INSERT INTO files VALUES (1, ?, ?, '.md', 11, 1, 'h1', 'nf1', 2)", (str(base / "a.md"), str(base)))
    con.execute("INSERT INTO files VALUES (1, ?, ?, '.md', 11, 0.5, 'h1', 'nf1', 2)", (str(base / "archive" / "a.md"), str(base / "archive")))
    manifest = fd.build_manifest(1, db, out)
    rows = list(manifest.open(encoding="utf-8"))
    assert any("KEEP" in r and "a.md" in r for r in rows)
    assert any("DUP_EXACT" in r and "archive" in r for r in rows)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_flatten_manifest.py -q`
Expected: FAIL — `build_manifest` signature or behavior missing.

- [ ] **Step 3: Refactor `flatten_dedupe.py`**

Add `build_manifest(scan_id, db_path, out_dir, src_root, profile=None) -> Path`:

```python
def build_manifest(scan_id, db_path, out_dir, src_root, profile=None):
    import sqlite3, csv
    from pathlib import Path
    from collections import defaultdict
    con = sqlite3.connect(db_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = con.execute("SELECT path, folder, size, mtime, sha256, norm_fp FROM files WHERE scan_id=?", (scan_id,)).fetchall()
    # exact duplicates by norm_fp
    by_norm: dict[str, list[dict]] = defaultdict(list)
    for path, folder, size, mtime, sha256, norm_fp in files:
        if norm_fp:
            by_norm[norm_fp].append({"path": path, "folder": folder, "size": size, "mtime": mtime, "sha256": sha256})
    rows = []
    for norm_fp, grp in by_norm.items():
        if len(grp) == 1:
            rows.append({"action": "KEEP", "source_path": grp[0]["path"], "target_path": "",
                         "rule": "R4", "reason": "unique normalized text", "gate_verdict": "ALLOW"})
            continue
        keeper = min(grp, key=lambda f: (
            "archive" in f["folder"].lower(),
            not any(part.startswith(tuple("0123456789")) for part in Path(f["path"]).parts),
            len(Path(f["path"]).parts),
            -f["size"],
            -f["mtime"]))
        rows.append({"action": "KEEP", "source_path": keeper["path"], "target_path": "",
                     "rule": "R6", "reason": "keeper selected", "gate_verdict": "ALLOW"})
        for f in grp:
            if f["path"] != keeper["path"]:
                rows.append({"action": "DUP_EXACT", "source_path": f["path"], "target_path": keeper["path"],
                             "rule": "R4", "reason": "exact duplicate", "gate_verdict": "ALLOW"})
    manifest = out / "MANIFEST.csv"
    with manifest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["action", "source_path", "target_path", "rule", "reason", "gate_verdict"])
        w.writeheader()
        w.writerows(rows)
    return manifest
```

Keep existing standalone `run()` for backward compatibility, but have it call `build_manifest` when possible.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_flatten_manifest.py -q`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add engine/flatten_dedupe.py tests/test_flatten_manifest.py
git commit -m "flatten_dedupe: build manifest from understand scan data"
```

---

### Task 9: Add `engine/intake_report.py`

**Files:**
- Create: `engine/intake_report.py`
- Create: `tests/test_intake_report.py`

**Interfaces:**
- Consumes: bundle dict (scan stats, anomalies, duplicates, near-dups).
- Produces: `REPORT.md` with facts block and narrative template.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_intake_report.py
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "engine"))
import intake_report as ir

def test_facts_block_counts():
    bundle = {"totals": {"files": 100, "duplicates": 5, "anomalies": 3, "near_dups": 2}}
    facts = ir.facts_block(bundle)
    assert facts["files"] == 100
    assert facts["duplicates"] == 5
    assert facts["anomalies"] == 3

def test_number_guard_catches_lie():
    facts = {"files": 100}
    narrative = "This folder has 200 files."
    assert not ir.verify_numbers(narrative, facts)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_intake_report.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'intake_report'`.

- [ ] **Step 3: Implement `intake_report.py`**

```python
from __future__ import annotations
import re
from pathlib import Path

def facts_block(bundle: dict) -> dict:
    t = bundle.get("totals", {})
    return {
        "files": t.get("files", 0),
        "duplicates": t.get("duplicates", 0),
        "near_duplicates": t.get("near_duplicates", 0),
        "anomalies": t.get("anomalies", 0),
        "skipped": t.get("skipped", 0),
    }

def narrative_template(bundle: dict) -> str:
    f = facts_block(bundle)
    return f"""# Folder Intelligence Report

## Facts (code-generated)
- Files scanned: {f['files']}
- Exact duplicates: {f['duplicates']}
- Near-duplicates held: {f['near_duplicates']}
- Anomalies detected: {f['anomalies']}
- Skipped files: {f['skipped']}

## Narrative (AI-written; numbers verified below)
[Write a plain-English summary here.]
"""

def verify_numbers(narrative: str, facts: dict) -> bool:
    for key, value in facts.items():
        for m in re.finditer(r"\b(\d{1,3}(?:,\d{3})*)\b", narrative):
            num = int(m.group(1).replace(",", ""))
            if num == value:
                continue
            # allow if the number is not near the fact value
            if abs(num - value) <= max(1, value * 0.05):
                return False
    return True
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_intake_report.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add engine/intake_report.py tests/test_intake_report.py
git commit -m "intake: add report facts block, narrative template, and number guard"
```

---

### Task 10: Build `engine/folder_intake.py` orchestrator CLI

**Files:**
- Create: `engine/folder_intake.py`
- Create: `tests/test_folder_intake.py`

**Interfaces:**
- Consumes: all prior modules.
- Produces: CLI commands `interview`, `scan`, `dry-run`, `simulate`, `apply`, `report`, `gate`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_folder_intake.py
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "engine"))
import folder_intake as fi

def test_cli_parses_gate_command():
    args = fi.parser.parse_args(["gate", "move", "a.txt", "b.txt"])
    assert args.command == "gate"
    assert args.action == "move"
    assert args.paths == ["a.txt", "b.txt"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_folder_intake.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'folder_intake'`.

- [ ] **Step 3: Implement `folder_intake.py`**

Create `engine/folder_intake.py`:

```python
from __future__ import annotations
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "engine"))
sys.path.insert(0, str(REPO / "01_PROFILE"))

import understand as u
import flatten_dedupe as fd
import gate as g
import plan_simulator as sim
import intake_report as ir
import profile_core as pc

parser = argparse.ArgumentParser(prog="folder-intake")
sub = parser.add_subparsers(dest="command", required=True)

p_interview = sub.add_parser("interview"); p_interview.add_argument("folder")
p_scan = sub.add_parser("scan"); p_scan.add_argument("folder")
p_dry = sub.add_parser("dry-run"); p_dry.add_argument("folder"); p_dry.add_argument("--out", required=True)
p_sim = sub.add_parser("simulate"); p_sim.add_argument("manifest")
p_apply = sub.add_parser("apply"); p_apply.add_argument("manifest"); p_apply.add_argument("--yes", action="store_true")
p_report = sub.add_parser("report"); p_report.add_argument("folder"); p_report.add_argument("--out", required=True)
p_gate = sub.add_parser("gate"); p_gate.add_argument("action"); p_gate.add_argument("paths", nargs="+")

def cmd_interview(args):
    root = Path(args.folder).resolve()
    quiz = pc.load_questionnaire(REPO / "config" / "rules" / pc.QUESTIONNAIRE)
    evidence = pc.scan_evidence(root)
    sugg = pc.suggest_answers(quiz, evidence)
    # Headless: use defaults/suggestions for v1; GUI can be added later.
    answers = {qid: s.get("value", "") for qid, s in sugg.items()}
    profile = pc.build_profile(root, answers, quiz)
    pc.write_profile(root, profile, REPO / "config" / "folder_profiles.json", answers, evidence)
    fire = answers.get("fire_carry_files", [])
    snap = pc.protected_snapshot(root, fire, REPO / ".data" / "protected_snapshots")
    print(f"Profile written. Protected snapshot: {snap['zip']} ({snap['files']} files)")
    return 0

def cmd_scan(args):
    root = Path(args.folder).resolve()
    con = u.connect()
    sid = u.scan([str(root)], con, run_symptoms=True)
    print(f"Scan complete: id={sid}")
    return 0

def cmd_dry_run(args):
    root = Path(args.folder).resolve()
    con = u.connect()
    sid = u.latest_scan(con)  # assumes latest is for this root; validate in v2
    manifest = fd.build_manifest(sid, u.DB_PATH, args.out, root)
    print(f"Manifest: {manifest}")
    return 0

def cmd_simulate(args):
    report = sim.simulate(args.manifest, profile={})
    print(f"Total: {report['total']}, passed: {report['passed']}, problems: {len(report['ordering_problems'])}")
    for p in report["ordering_problems"]:
        print(f"  - {p}")
    return 0

def cmd_gate(args):
    d = g.Gate.load(REPO / "config" / "rules", {}).evaluate(args.action, args.paths)
    print(d.to_json())
    return 0 if d.verdict in (g.ALLOW, g.PREVIEW) else 1

def main(argv=None):
    args = parser.parse_args(argv)
    dispatch = {
        "interview": cmd_interview, "scan": cmd_scan, "dry-run": cmd_dry_run,
        "simulate": cmd_simulate, "gate": cmd_gate,
    }
    fn = dispatch.get(args.command)
    if not fn:
        parser.error(f"command {args.command} not yet implemented")
    return fn(args)

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_folder_intake.py -q`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add engine/folder_intake.py tests/test_folder_intake.py
git commit -m "intake: add folder_intake CLI orchestrator"
```

---

### Task 11: Integration test on a synthetic tree

**Files:**
- Create: `tests/test_folder_intake_e2e.py`

**Interfaces:**
- Consumes: CLI commands.
- Produces: passing integration test.

- [ ] **Step 1: Write the integration test**

```python
# tests/test_folder_intake_e2e.py
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

def test_end_to_end_dry_run(tmp_path):
    root = tmp_path / "Cross-Domain"
    root.mkdir()
    (root / "01_Federal_Reserve").mkdir()
    (root / "Federal Reserve").mkdir()
    (root / "01_Federal_Reserve" / "note.md").write_text("# Fed\n\nsame content", encoding="utf-8")
    (root / "Federal Reserve" / "note.md").write_text("# Fed\n\nsame content", encoding="utf-8")
    out = tmp_path / "report"
    subprocess.run([PYTHON, "-m", "engine.folder_intake", "scan", str(root)], cwd=REPO, check=True)
    subprocess.run([PYTHON, "-m", "engine.folder_intake", "dry-run", str(root), "--out", str(out)], cwd=REPO, check=True)
    manifest = out / "MANIFEST.csv"
    assert manifest.exists()
    text = manifest.read_text(encoding="utf-8")
    assert "DUP_EXACT" in text
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_folder_intake_e2e.py -q`
Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_folder_intake_e2e.py
git commit -m "tests: end-to-end folder intake dry-run"
```

---

## Self-review

**Spec coverage:**
- Protected snapshot — Task 1.
- Tiered fingerprinting — Task 2.
- Shape/Position classification — Task 3.
- Near-duplicate detection — Task 4.
- Anomaly detection — Task 5.
- Plan simulator — Task 6.
- Profile-driven gate — Task 7.
- Manifest generation — Task 8.
- Report facts/narrative guard — Task 9.
- Orchestrator CLI — Task 10.
- End-to-end test — Task 11.

**Placeholder scan:** No TBD/TODO placeholders; all steps include concrete code or commands.

**Type consistency:** `Gate.evaluate()` signature unchanged; new modules use `Path`, `sqlite3.Connection`, `dict` consistently.

**Review Focus coverage:**
- Off-limits → Task 7 test.
- Business/personal boundary → Task 7 test.
- Sequence-level delete-after-move → Task 6 test.
- Word-order near-dup → Task 4 test.
- Short-text guard → Task 4 test.

---

## Execution handoff

Plan saved to `docs/plans/2026-10-25-folder-understanding-pipeline.md`.

This plan is large (11 tasks) and the tasks depend on the shared `engine/understand.py` schema and the `engine/gate.py` interface. **I recommend subagent-driven execution** so each task gets an independent implement + review pass, which catches interface mismatches early. The alternative is native execution in this session, which is faster but relies on one final review.

Please review the plan and confirm which execution approach you'd prefer, or tell me if any task should be split, reordered, or dropped.
