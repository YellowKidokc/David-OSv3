#!/usr/bin/env python3
"""understand.py — FIS stage 0: scan folders, predict what they are, store it all.

Spec: docs/FIS_UNDERSTAND_PIPELINE.md.  Observe-only: nothing on disk is moved,
renamed, or deleted.  Observations and inferences are stored separately.

  python engine/understand.py scan  ROOT [ROOT ...] [--symptoms] [--blind] [--ollama MODEL] [--no-dupes]
  python engine/understand.py dupes  [--scan ID] [--skip-root ROOT ...]      stage 3 on an existing scan
  python engine/understand.py forge  [--scan ID] [--url URL] [--model M]      open questions -> Forge (names only)
  python engine/understand.py report [--scan ID]
  python engine/understand.py questions
  python engine/understand.py answer QID --kind documents --domain theophysics [--role ...] [--note ...]

DB: .data/fis_understand.sqlite     Ground truth: config/folder_registry.yaml
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB_PATH = REPO / ".data" / "fis_understand.sqlite"
REGISTRY = REPO / "config" / "folder_registry.yaml"

# Locked FIS exclusions + system / dependency / cache folders.
SKIP_DIRS = {
    ".lake", ".obsidian", ".smart-env", ".claudian", ".trash", ".git", "node_modules",
    "__pycache__", ".venv", "venv", "site-packages", ".cache", ".next", "dist-packages",
    "$recycle.bin", "#recycle", "#snapshot", "system volume information", "windows",
    "program files", "program files (x86)", "programdata", "appdata", "@eadir",
}
NEVER_WALK = {"dont touch boot up", "_fis_root_sidecar_archive"}

KIND_EXT = {
    "code": ".py .js .ts .tsx .jsx .mjs .cjs .java .c .cpp .h .cs .go .rs .rb .php .ps1 .bat .cmd .sh .ahk .lean .sql .vue .svelte .kt .swift .r .ipynb",
    "documents": ".md .txt .pdf .doc .docx .rtf .odt .epub .tex .html .htm .fisnote .chi",
    "pictures": ".png .jpg .jpeg .gif .webp .bmp .tif .tiff .svg .heic .ico .psd",
    "video": ".mp4 .mkv .mov .avi .webm .wmv .flv .m4v",
    "audio": ".mp3 .wav .flac .m4a .aac .ogg .opus .wma",
    "data": ".csv .xlsx .xls .json .jsonl .yaml .yml .xml .sqlite .sqlite3 .db .parquet .tsv",
    "archive": ".zip .7z .rar .tar .gz .tgz .bz2 .iso",
}
EXT_KIND = {e: k for k, exts in KIND_EXT.items() for e in exts.split()}

# Structural markers → observation name.  Presence is an observation, not a label.
MARKERS = {
    ".obsidian": "obsidian_vault", ".git": "git_repo", "package.json": "js_project",
    "pyproject.toml": "python_project", "requirements.txt": "python_project", "setup.py": "python_project",
    "cargo.toml": "rust_project", "go.mod": "go_project", "lakefile.lean": "lean_project",
    "lakefile.toml": "lean_project", "docker-compose.yml": "docker_stack", "docker-compose.yaml": "docker_stack",
    "index.html": "website", "vite.config.js": "js_project", "vite.config.ts": "js_project",
}
PROJECT_MARKERS = {"git_repo", "js_project", "python_project", "rust_project", "go_project", "lean_project", "docker_stack"}

DOMAIN_WORDS = {
    "theophysics": "axiom theophysics logos coherence chi master equation canon lean grace trinity faith physics paper derivation law gospel bible scripture resurrection",
    "trading": "trade trading candle candles ticker stock stocks options forex chart spy futures market daily-trading commodity broker pnl",
    "ai_chats": "chatgpt claude gemini kimi codex conversation conversations transcript export prompt chat chats deepseek gpt",
    "website": "site website html css public dist index assets wordpress page pages",
    "media_production": "video audio tts podcast youtube mp4 thumbnail render obs",
    "business": "invoice quote estimate fence fencing lowes customer receipt tax payroll contract",
}
DOMAIN_TOKENS = {d: set(w.split()) for d, w in DOMAIN_WORDS.items()}
SORTING_NAMES = re.compile(r"^(downloads?|desktop( \d+)?|inbox|new folder( \(\d+\))?|temp|tmp|misc|stuff|unsorted|_gather|00_inbox|staging|00_staging)$", re.I)

QUESTION_MIN_FILES = 15
QUESTION_MAX_CONF = 0.6
QUESTION_MAX_DEPTH = 3
HASH_MAX_BYTES = 512 * 1024 * 1024


# ── storage ────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (scan_id INTEGER PRIMARY KEY, started TEXT, finished TEXT, roots TEXT, options TEXT, stats TEXT);
CREATE TABLE IF NOT EXISTS files (scan_id INT, path TEXT, folder TEXT, name TEXT, ext TEXT, kind TEXT, size INT, mtime REAL, sha256 TEXT,
    PRIMARY KEY (scan_id, path));
CREATE INDEX IF NOT EXISTS ix_files_size ON files(scan_id, size);
CREATE INDEX IF NOT EXISTS ix_files_folder ON files(scan_id, folder);
CREATE TABLE IF NOT EXISTS skipped (scan_id INT, path TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS folders (scan_id INT, path TEXT, parent TEXT, depth INT, direct_files INT, total_files INT, total_bytes INT,
    kind_counts TEXT, ext_counts TEXT, collection_root TEXT, PRIMARY KEY (scan_id, path));
-- OBSERVATIONS: things seen.  Never interpretations.
CREATE TABLE IF NOT EXISTS observations (scan_id INT, folder TEXT, name TEXT, value TEXT, source TEXT);
-- INFERENCES: interpretations, each with evidence, confidence, and where it came from.
CREATE TABLE IF NOT EXISTS inferences (scan_id INT, folder TEXT, facet TEXT, value TEXT, confidence REAL, source TEXT, evidence TEXT,
    status TEXT DEFAULT 'shadow');
CREATE TABLE IF NOT EXISTS dup_groups (scan_id INT, sha256 TEXT, size INT, n INT, paths TEXT);
CREATE TABLE IF NOT EXISTS symptoms (scan_id INT, folder TEXT, symptom_id TEXT, name TEXT, severity TEXT, path TEXT, message TEXT, evidence TEXT);
CREATE TABLE IF NOT EXISTS questions (qid INTEGER PRIMARY KEY, scan_id INT, folder TEXT, question TEXT, prediction TEXT, evidence TEXT,
    choices TEXT, status TEXT DEFAULT 'open', answer TEXT, answered_at TEXT);
CREATE TABLE IF NOT EXISTS llm_requests (scan_id INT, folder TEXT, provider TEXT, packet TEXT, response TEXT, status TEXT, created TEXT);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    return con


# ── registry (ground truth) ────────────────────────────

def load_registry() -> list[dict]:
    try:
        import yaml
        data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    out = []
    for f in data.get("folders", []) or []:
        f = dict(f)
        f["_norm"] = norm(f["path"])
        out.append(f)
    for letter, d in (data.get("drives") or {}).items():
        d = dict(d or {})
        d["path"] = f"{letter}:\\"
        d["_norm"] = norm(d["path"])
        out.append(d)
    return out


def norm(p: str) -> str:
    return os.path.normcase(os.path.normpath(str(p))).rstrip("\\/")


def registry_for(folder: str, reg: list[dict]) -> tuple[dict | None, dict | None]:
    """(exact confirmed entry, nearest confirmed ancestor entry)."""
    nf = norm(folder)
    exact, anc, best = None, None, -1
    for e in reg:
        if not e.get("confirmed"):
            continue
        en = e["_norm"]
        if nf == en:
            exact = e
        elif nf.startswith(en + os.sep) and len(en) > best:
            anc, best = e, len(en)
    return exact, anc


# ── scan ───────────────────────────────────────────────

def sha256(path: str) -> str | None:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def tokens_of(name: str) -> set[str]:
    return set(re.findall(r"[a-z]+", name.lower()))


def scan(roots: list[str], con: sqlite3.Connection, run_symptoms=False, blind=False, ollama_model=None,
         max_files: int | None = None, log=print, dedupe: bool = True) -> int:
    reg = load_registry()
    cur = con.execute("INSERT INTO scans(started, roots, options) VALUES (?,?,?)",
                      (now(), json.dumps(roots), json.dumps({"symptoms": run_symptoms, "blind": blind, "ollama": ollama_model})))
    scan_id = cur.lastrowid
    folder_direct: dict[str, Counter] = defaultdict(Counter)
    folder_ext: dict[str, Counter] = defaultdict(Counter)
    folder_bytes: Counter = Counter()
    folder_names: dict[str, Counter] = defaultdict(Counter)
    markers: dict[str, set] = defaultdict(set)
    parents: dict[str, str] = {}
    n_files = 0
    t0 = time.time()

    for root in roots:
        root = os.path.normpath(root)
        if not os.path.isdir(root):
            con.execute("INSERT INTO skipped VALUES (?,?,?)", (scan_id, root, "root not a directory / unreachable"))
            continue
        parents.setdefault(root, "")

        def onerror(e, _root=root):
            con.execute("INSERT INTO skipped VALUES (?,?,?)", (scan_id, getattr(e, "filename", "") or _root, f"unreadable: {e.__class__.__name__}"))

        for dirpath, dirnames, filenames in os.walk(root, onerror=onerror, followlinks=False):
            lower = {d.lower(): d for d in dirnames}
            for low, real in lower.items():
                if low in (".obsidian", ".git"):
                    markers[dirpath].add(MARKERS[low])
            keep = []
            for d in dirnames:
                full = os.path.join(dirpath, d)
                if d.lower() in SKIP_DIRS or d.lower() in NEVER_WALK or d.startswith("$") or os.path.islink(full):
                    if d.lower() not in (".obsidian", ".git", "__pycache__", "node_modules", ".venv", "venv"):
                        con.execute("INSERT INTO skipped VALUES (?,?,?)", (scan_id, full, "excluded dir"))
                    continue
                keep.append(d)
                parents[full] = dirpath
            dirnames[:] = keep
            parents.setdefault(dirpath, os.path.dirname(dirpath) if dirpath != root else "")
            folder_direct[dirpath]  # materialize empty folders
            rows = []
            for fn in filenames:
                low = fn.lower()
                if low in MARKERS:
                    markers[dirpath].add(MARKERS[low])
                full = os.path.join(dirpath, fn)
                try:
                    st = os.stat(full)
                except OSError as e:
                    con.execute("INSERT INTO skipped VALUES (?,?,?)", (scan_id, full, f"unreadable: {e.__class__.__name__}"))
                    continue
                ext = os.path.splitext(low)[1]
                kind = EXT_KIND.get(ext, "other")
                folder_direct[dirpath][kind] += 1
                folder_ext[dirpath][ext or "(none)"] += 1
                folder_bytes[dirpath] += st.st_size
                for t in tokens_of(os.path.splitext(fn)[0]):
                    folder_names[dirpath][t] += 1
                rows.append((scan_id, full, dirpath, fn, ext, kind, st.st_size, st.st_mtime, None))
                n_files += 1
            con.executemany("INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?,?,?,?)", rows)
            if n_files and n_files % 5000 < len(rows):
                log(f"  {n_files:,} files · {dirpath}")
                con.commit()
            if max_files and n_files >= max_files:
                con.execute("INSERT INTO skipped VALUES (?,?,?)", (scan_id, dirpath, f"stopped: max_files={max_files}"))
                break

    # Observations: markers (things seen, not interpretations)
    for folder, ms in markers.items():
        for m in sorted(ms):
            con.execute("INSERT INTO observations VALUES (?,?,?,?,?)", (scan_id, folder, "marker", m, "filesystem"))

    # Roll up bottom-up.  A nested project is its own collection: its counts do not
    # decide the parent's kind (they are tracked separately as nested_projects).
    all_folders = sorted(set(folder_direct) | set(parents), key=lambda p: -p.count(os.sep))
    total = {f: Counter(folder_direct.get(f, {})) for f in all_folders}
    purpose_counts = {f: Counter(folder_direct.get(f, {})) for f in all_folders}
    total_ext = {f: Counter(folder_ext.get(f, {})) for f in all_folders}
    total_bytes = Counter(folder_bytes)
    names = {f: Counter(folder_names.get(f, {})) for f in all_folders}
    nested_projects: dict[str, list] = defaultdict(list)
    for f in all_folders:
        p = parents.get(f)
        if not p or p not in total:
            continue
        total[p].update(total[f])
        total_ext[p].update(total_ext[f])
        total_bytes[p] += total_bytes[f]
        names[p].update(names[f])
        if markers.get(f, set()) & PROJECT_MARKERS:
            nested_projects[p].append(f)
            nested_projects[p].extend(nested_projects[f])
        else:
            purpose_counts[p].update(purpose_counts[f])
            nested_projects[p].extend(nested_projects[f])

    root_norms = [os.path.normpath(r) for r in roots]
    for f in all_folders:
        depth = min((f.count(os.sep) - r.count(os.sep) for r in root_norms if norm(f).startswith(norm(r))), default=0)
        con.execute("INSERT OR REPLACE INTO folders VALUES (?,?,?,?,?,?,?,?,?,?)", (
            scan_id, f, parents.get(f, ""), depth, sum(folder_direct.get(f, {}).values()), sum(total[f].values()),
            total_bytes[f], json.dumps(total[f]), json.dumps(dict(total_ext[f].most_common(15))), None))
        predict_folder(con, scan_id, f, depth, purpose_counts[f], total[f], total_ext[f], names[f],
                       markers.get(f, set()), nested_projects.get(f, []), reg, blind)

    if dedupe:
        find_duplicates(con, scan_id, log)
    if run_symptoms:
        symptoms_for(con, scan_id, roots, log)
    if ollama_model:
        escalate_ollama(con, scan_id, ollama_model, log)

    stats = {"files": n_files, "folders": len(all_folders), "seconds": round(time.time() - t0, 1)}
    con.execute("UPDATE scans SET finished=?, stats=? WHERE scan_id=?", (now(), json.dumps(stats), scan_id))
    con.commit()
    return scan_id


def predict_folder(con, scan_id, folder, depth, purpose, total, ext, names, marks, nested, reg, blind):
    exact, anc = (None, None) if blind else registry_for(folder, reg)
    n = sum(purpose.values())
    evidence: list[str] = []

    # ── kind ──
    if exact and exact.get("kind"):
        kind, conf, src = exact["kind"], 1.0, "registry"
        evidence.append("confirmed in folder_registry.yaml")
    elif marks & PROJECT_MARKERS:
        kind, conf, src = "code", 0.95, "rules"
        evidence.append(f"project marker(s) here: {', '.join(sorted(marks & PROJECT_MARKERS))}")
    elif n == 0:
        kind, conf, src = ("code" if nested else "empty"), (0.7 if nested else 0.9), "rules"
        evidence.append(f"0 non-project files; {len(nested)} nested project(s)" if nested else "no files")
    else:
        top, top_n = purpose.most_common(1)[0]
        share = top_n / n
        n_ext = len([e for e, c in ext.items() if c])
        evidence.append(f"{top_n} of {n} files are {top} ({share:.0%})")
        folder_name = os.path.basename(folder.rstrip("\\/")) or folder
        if SORTING_NAMES.match(folder_name) or (share < 0.5 and n_ext >= 10 and n >= 30):
            kind, conf, src = "needs_sorting", 0.55 + (0.2 if SORTING_NAMES.match(folder_name) else 0), "rules"
            evidence.append(f"{n_ext} extensions; name '{folder_name}'")
        elif share >= 0.6 and top not in ("other", "archive"):
            kind, conf, src = top, round(min(0.95, 0.5 + share / 2), 2), "rules"
        elif top == "data" and share >= 0.6:
            kind, conf, src = "data", round(min(0.9, 0.5 + share / 2), 2), "rules"
        else:
            kind, conf, src = "mixed", round(0.4 + (1 - share) / 3, 2), "rules"
            second = [f"{k} {c}" for k, c in purpose.most_common(3)]
            evidence.append("mix: " + ", ".join(second))
    if nested:
        evidence.append(f"{len(nested)} nested project collection(s) excluded from purpose counts")
    if anc and not exact and (anc.get("protect") or anc.get("role")):
        evidence.append(f"inside confirmed '{anc['path']}' (role={anc.get('role')}, protect={anc.get('protect', False)})")
    add_inference(con, scan_id, folder, "kind", kind, conf, src, evidence)

    # ── domain(s): labels coexist ──
    if exact and exact.get("domain"):
        add_inference(con, scan_id, folder, "domain", exact["domain"], 1.0, "registry", ["confirmed in folder_registry.yaml"])
    else:
        if "obsidian_vault" in marks:
            add_inference(con, scan_id, folder, "domain", "obsidian_vault", 0.95, "rules", [".obsidian directory present"])
        tok_total = sum(names.values()) or 1
        scored = []
        for d, words in DOMAIN_TOKENS.items():
            hits = sum(c for t, c in names.items() if t in words)
            name_hit = bool(tokens_of(os.path.basename(folder)) & words)
            score = hits / tok_total + (0.25 if name_hit else 0)
            if hits >= 3 or name_hit:
                scored.append((score, d, hits, name_hit))
        for score, d, hits, name_hit in sorted(scored, reverse=True)[:2]:
            ev = [f"{hits} domain words in {tok_total} filename tokens"] + (["folder name matches"] if name_hit else [])
            add_inference(con, scan_id, folder, "domain", d, round(min(0.9, 0.3 + score * 2), 2), "rules", ev)
        if anc and anc.get("domain") and not scored:
            add_inference(con, scan_id, folder, "domain", anc["domain"], 0.6, "registry_inherited", [f"inherited from {anc['path']}"])

    # ── policy inherited from registry (protect) ──
    src_entry = exact or anc
    if src_entry and src_entry.get("protect"):
        add_inference(con, scan_id, folder, "protect", "true", 1.0, "registry",
                      [f"protect=true on {src_entry['path']}"])
    elif marks & PROJECT_MARKERS:
        add_inference(con, scan_id, folder, "protect", "true", 0.95, "rules", ["program root: never move/rename/flatten inside (GR-003)"])

    # ── ask David when unsure ──
    if (not exact and not (anc and anc.get("protect")) and conf < QUESTION_MAX_CONF and sum(total.values()) >= QUESTION_MIN_FILES
            and depth <= QUESTION_MAX_DEPTH):
        con.execute("INSERT INTO questions(scan_id, folder, question, prediction, evidence, choices) VALUES (?,?,?,?,?,?)", (
            scan_id, folder, f"What is this folder? ({sum(total.values())} files)",
            json.dumps({"kind": kind, "confidence": conf}), json.dumps(evidence),
            json.dumps({"kind": ["code", "documents", "pictures", "video", "audio", "data", "mixed", "needs_sorting"],
                        "importance": ["critical", "high", "normal", "low", "junk"], "protect": [True, False]})))


def add_inference(con, scan_id, folder, facet, value, conf, source, evidence):
    con.execute("INSERT INTO inferences(scan_id, folder, facet, value, confidence, source, evidence) VALUES (?,?,?,?,?,?,?)",
                (scan_id, folder, facet, str(value), conf, source, json.dumps(evidence)))


def find_duplicates(con, scan_id, log, skip_roots=()):
    """Stage 3: group by size, then SHA-256. Files under skip_roots are left out; a file that cannot be read
    while hashing is recorded in `skipped` with the reason (never silently dropped)."""
    skip = [norm(r) for r in skip_roots]
    con.execute("DELETE FROM dup_groups WHERE scan_id=?", (scan_id,))     # rerunnable on the same scan
    groups = con.execute("SELECT size FROM files WHERE scan_id=? AND size>0 GROUP BY size HAVING COUNT(*)>1", (scan_id,)).fetchall()
    log(f"  hashing {len(groups):,} same-size groups …")
    for (size,) in groups:
        if size > HASH_MAX_BYTES:
            continue
        paths = [p for (p,) in con.execute("SELECT path FROM files WHERE scan_id=? AND size=?", (scan_id, size))
                 if not any(norm(p) == r or norm(p).startswith(r + os.sep) for r in skip)]
        by_hash = defaultdict(list)
        for p in paths:
            h = sha256(p)
            if h:
                by_hash[h].append(p)
                con.execute("UPDATE files SET sha256=? WHERE scan_id=? AND path=?", (h, scan_id, p))
            else:
                con.execute("INSERT INTO skipped VALUES (?,?,?)", (scan_id, p, "unreadable while hashing"))
        for h, ps in by_hash.items():
            if len(ps) > 1:
                con.execute("INSERT INTO dup_groups VALUES (?,?,?,?,?)", (scan_id, h, size, len(ps), json.dumps(ps)))
    con.commit()


def symptoms_for(con, scan_id, roots, log):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from symptoms import run_all_symptoms
    except Exception as e:
        log(f"  symptoms unavailable: {e}")
        return
    for root in roots:
        n = con.execute("SELECT total_files FROM folders WHERE scan_id=? AND path=?", (scan_id, os.path.normpath(root))).fetchone()
        if not n or n[0] > 20000:
            log(f"  symptoms skipped for {root} ({n[0] if n else '?'} files > 20000)")
            continue
        rep = run_all_symptoms(root)
        for r in rep.results:
            d = r.to_dict()
            con.execute("INSERT INTO symptoms VALUES (?,?,?,?,?,?,?,?)", (scan_id, root, d["symptom_id"], d["name"], d["severity"],
                        d["path"], d["message"], json.dumps(d.get("evidence", {}), default=str)))
        log(f"  {len(rep.results)} symptoms in {root}")
    con.commit()


def escalate_ollama(con, scan_id, model, log, url="http://127.0.0.1:11434/api/generate"):
    """Local-only escalation for unanswered questions.  Sends names + extension mix, never file contents."""
    rows = con.execute("SELECT folder FROM questions WHERE scan_id=? AND status='open'", (scan_id,)).fetchall()
    for (folder,) in rows[:25]:
        sample = [n for (n,) in con.execute("SELECT name FROM files WHERE scan_id=? AND folder LIKE ? LIMIT 60", (scan_id, folder + "%"))]
        ext = con.execute("SELECT ext_counts FROM folders WHERE scan_id=? AND path=?", (scan_id, folder)).fetchone()
        packet = {"folder": folder, "ext_counts": json.loads(ext[0]) if ext else {}, "sample_file_names": sample}
        prompt = ("Classify this folder. Reply JSON only: {\"kind\": one of code|documents|pictures|video|audio|data|mixed|needs_sorting, "
                  "\"domain\": short label, \"purpose\": one sentence, \"confidence\": 0-1}.\n" + json.dumps(packet))
        try:
            req = urllib.request.Request(url, json.dumps({"model": model, "prompt": prompt, "stream": False, "format": "json"}).encode(),
                                         {"Content-Type": "application/json"})
            resp = json.loads(urllib.request.urlopen(req, timeout=120).read())["response"]
            ans = json.loads(resp)
            con.execute("INSERT INTO llm_requests VALUES (?,?,?,?,?,?,?)", (scan_id, folder, f"ollama:{model}", json.dumps(packet), resp, "ok", now()))
            if ans.get("kind"):
                add_inference(con, scan_id, folder, "kind", ans["kind"], float(ans.get("confidence", 0.5)), f"llm:ollama:{model}",
                              [ans.get("purpose", "")])
            if ans.get("domain"):
                add_inference(con, scan_id, folder, "domain", ans["domain"], float(ans.get("confidence", 0.5)), f"llm:ollama:{model}", [])
        except Exception as e:
            con.execute("INSERT INTO llm_requests VALUES (?,?,?,?,?,?,?)", (scan_id, folder, f"ollama:{model}", json.dumps(packet), str(e), "error", now()))
            log(f"  ollama failed for {folder}: {e}")
            break
    con.commit()


def escalate_forge(con, scan_id, log=print, url=None, model="default", limit=25, dry_run=False) -> list[dict]:
    """Same packet as escalate_ollama (folder name, file names, extension mix; never file contents), sent to Forge's
    OpenAI-compatible endpoint. Answers are stored as shadow inferences with source=llm:forge. Returns the packets."""
    url = (url or os.environ.get("FORGE_URL") or "http://127.0.0.1:8790").rstrip("/") + "/v1/chat/completions"
    rows = con.execute("SELECT folder FROM questions WHERE scan_id=? AND status='open'", (scan_id,)).fetchall()
    packets = []
    for (folder,) in rows[:limit]:
        sample = [n for (n,) in con.execute("SELECT name FROM files WHERE scan_id=? AND folder LIKE ? LIMIT 60", (scan_id, folder + "%"))]
        ext = con.execute("SELECT ext_counts FROM folders WHERE scan_id=? AND path=?", (scan_id, folder)).fetchone()
        packet = {"folder": folder, "ext_counts": json.loads(ext[0]) if ext else {}, "sample_file_names": sample}
        packets.append(packet)
        if dry_run:
            continue
        prompt = ("Classify this folder. Reply JSON only: {\"kind\": one of code|documents|pictures|video|audio|data|mixed|needs_sorting, "
                  "\"domain\": short label, \"purpose\": one sentence, \"confidence\": 0-1}.\n" + json.dumps(packet))
        body = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False}
        try:
            req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
            resp = json.loads(urllib.request.urlopen(req, timeout=180).read())["choices"][0]["message"]["content"]
            text = resp.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            ans = json.loads(text)
            con.execute("INSERT INTO llm_requests VALUES (?,?,?,?,?,?,?)", (scan_id, folder, f"forge:{model}", json.dumps(packet), resp, "ok", now()))
            if ans.get("kind"):
                add_inference(con, scan_id, folder, "kind", ans["kind"], float(ans.get("confidence", 0.5)), f"llm:forge:{model}",
                              [ans.get("purpose", "")])
            if ans.get("domain"):
                add_inference(con, scan_id, folder, "domain", ans["domain"], float(ans.get("confidence", 0.5)), f"llm:forge:{model}", [])
        except Exception as e:
            con.execute("INSERT INTO llm_requests VALUES (?,?,?,?,?,?,?)", (scan_id, folder, f"forge:{model}", json.dumps(packet), str(e), "error", now()))
            log(f"  forge failed for {folder}: {e}")
            break
    con.commit()
    return packets


# ── reporting / questions ──────────────────────────────

def latest_scan(con) -> int:
    r = con.execute("SELECT MAX(scan_id) FROM scans").fetchone()
    return r[0] if r and r[0] else 0


def report(con, scan_id=None):
    scan_id = scan_id or latest_scan(con)
    s = con.execute("SELECT roots, stats FROM scans WHERE scan_id=?", (scan_id,)).fetchone()
    print(f"scan {scan_id}  roots={s[0]}  {s[1]}")
    print(f"skipped/unreadable: {con.execute('SELECT COUNT(*) FROM skipped WHERE scan_id=?', (scan_id,)).fetchone()[0]}")
    d = con.execute("SELECT COUNT(*), COALESCE(SUM(n-1),0), COALESCE(SUM((n-1)*size),0) FROM dup_groups WHERE scan_id=?", (scan_id,)).fetchone()
    print(f"exact duplicate groups: {d[0]}  redundant copies: {d[1]}  reclaimable: {d[2] / 1e6:.1f} MB")
    print("\nfolders (depth ≤ 2):")
    q = """SELECT f.path, f.depth, f.total_files, i.value, i.confidence, i.source, i.evidence
           FROM folders f JOIN inferences i ON i.scan_id=f.scan_id AND i.folder=f.path AND i.facet='kind'
           WHERE f.scan_id=? AND f.depth<=2 AND f.total_files>0 ORDER BY f.path"""
    for path, depth, n, kind, conf, src, ev in con.execute(q, (scan_id,)):
        doms = [f"{v}({c:.2f})" for v, c in con.execute(
            "SELECT value, confidence FROM inferences WHERE scan_id=? AND folder=? AND facet='domain' ORDER BY confidence DESC", (scan_id, path))]
        print(f"{'  ' * depth}{os.path.basename(path) or path}  [{n} files]  kind={kind} {conf:.2f} ({src})  domain={', '.join(doms) or '-'}")
        print(f"{'  ' * depth}    ↳ {'; '.join(json.loads(ev))}")
    oq = con.execute("SELECT COUNT(*) FROM questions WHERE scan_id=? AND status='open'", (scan_id,)).fetchone()[0]
    print(f"\nopen questions: {oq}   (python engine/understand.py questions)")


def list_questions(con):
    for qid, folder, question, pred, ev in con.execute(
            "SELECT qid, folder, question, prediction, evidence FROM questions WHERE status='open' ORDER BY qid"):
        print(f"[{qid}] {folder}\n     {question}  prediction={pred}\n     evidence: {'; '.join(json.loads(ev))}")


def answer(con, qid, kind, domain=None, role=None, importance=None, protect=None, note=None):
    row = con.execute("SELECT folder FROM questions WHERE qid=?", (qid,)).fetchone()
    if not row:
        sys.exit(f"no question {qid}")
    folder = row[0]
    entry = {"path": folder, "kind": kind, "domain": domain, "role": role, "importance": importance,
             "protect": protect, "note": note, "confirmed": True}
    lines = [f"  - path: '{folder}'"] + [f"    {k}: {json.dumps(v) if isinstance(v, str) else str(v).lower()}"
                                         for k, v in entry.items() if k != "path" and v is not None]
    with open(REGISTRY, "a", encoding="utf-8") as f:
        f.write(f"\n  # answered via understand.py question {qid}, {now()}\n" + "\n".join(lines) + "\n")
    con.execute("UPDATE questions SET status='answered', answer=?, answered_at=? WHERE qid=?", (json.dumps(entry), now(), qid))
    con.commit()
    print(f"recorded → {REGISTRY}")


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("roots", nargs="+")
    s.add_argument("--symptoms", action="store_true", help="run the 41 symptom detectors on each root (≤20k files)")
    s.add_argument("--blind", action="store_true", help="ignore the registry — measures prediction accuracy")
    s.add_argument("--ollama", metavar="MODEL", help="ask a LOCAL Ollama model about folders it could not classify")
    s.add_argument("--max-files", type=int)
    s.add_argument("--no-dupes", action="store_true", help="stage 1 only: skip the size + SHA-256 pass (run `dupes` later)")
    s.add_argument("--db", default=str(DB_PATH))
    d = sub.add_parser("dupes")
    d.add_argument("--scan", type=int)
    d.add_argument("--skip-root", action="append", default=[], help="leave files under this root out (e.g. a build-artifact collection)")
    d.add_argument("--db", default=str(DB_PATH))
    fg = sub.add_parser("forge")
    fg.add_argument("--scan", type=int)
    fg.add_argument("--url", help="Forge base URL (default FORGE_URL or http://127.0.0.1:8790)")
    fg.add_argument("--model", default="default")
    fg.add_argument("--dry-run", action="store_true", help="show the packets, send nothing")
    fg.add_argument("--db", default=str(DB_PATH))
    r = sub.add_parser("report")
    r.add_argument("--scan", type=int)
    r.add_argument("--db", default=str(DB_PATH))
    q = sub.add_parser("questions")
    q.add_argument("--db", default=str(DB_PATH))
    a = sub.add_parser("answer")
    a.add_argument("qid", type=int)
    a.add_argument("--kind", required=True)
    for opt in ("domain", "role", "importance", "note"):
        a.add_argument(f"--{opt}")
    a.add_argument("--protect", choices=["true", "false"])
    a.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args(argv)
    con = connect(Path(args.db))
    if args.cmd == "scan":
        sid = scan(args.roots, con, args.symptoms, args.blind, args.ollama, args.max_files, dedupe=not args.no_dupes)
        report(con, sid)
    elif args.cmd == "dupes":
        find_duplicates(con, args.scan or latest_scan(con), print, args.skip_root)
        report(con, args.scan)
    elif args.cmd == "forge":
        for p in escalate_forge(con, args.scan or latest_scan(con), print, args.url, args.model, dry_run=args.dry_run):
            print(json.dumps(p)[:300])
    elif args.cmd == "report":
        report(con, args.scan)
    elif args.cmd == "questions":
        list_questions(con)
    elif args.cmd == "answer":
        answer(con, args.qid, args.kind, args.domain, args.role, args.importance,
               None if args.protect is None else args.protect == "true", args.note)


if __name__ == "__main__":
    main()
