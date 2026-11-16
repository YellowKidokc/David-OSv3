"""Controlled, read-only exact retrieval through ripgrep-all JSON events."""
from __future__ import annotations
import base64
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time
import hashlib
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]

def load_config():
    path = Path(os.environ.get("DAVIDOS_SEARCH_CONFIG", ROOT / "config/search.json"))
    cfg = json.loads(path.read_text(encoding="utf-8-sig"))
    cfg["roots"] = {alias: str((path.resolve().parent / value).resolve())
                    for alias, value in cfg.get("roots", {}).items()}
    extra = ROOT / '.data/search-locations.json'
    if extra.is_file() and not os.environ.get('DAVIDOS_SEARCH_CONFIG'):
        cfg['roots'].update(json.loads(extra.read_text(encoding='utf-8')))
    return cfg

_location_lock = threading.Lock()

def register_location(value):
    """Save an explicitly selected local folder, without touching its contents."""
    path = Path(value)
    if not path.is_absolute() or not path.is_dir():
        raise ValueError('Choose an existing absolute drive or folder path')
    resolved = str(path.resolve())
    alias = 'saved-' + hashlib.sha256(resolved.casefold().encode()).hexdigest()[:16]
    target = ROOT / '.data/search-locations.json'
    with _location_lock:
        entries = json.loads(target.read_text(encoding='utf-8')) if target.is_file() else {}
        entries[alias] = resolved
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(entries, indent=2), encoding='utf-8')
        temporary.replace(target)
    return {'alias': alias, 'path': resolved}

def tool_path(value, name):
    if value:
        p = Path(value)
        p = p if p.is_absolute() else ROOT / p
        if p.is_file():
            return str(p)
    return shutil.which(name)

def environment(cfg):
    env = os.environ.copy()
    paths = [str(ROOT / p) for p in cfg.get("tool_directories", [])]
    env["PATH"] = os.pathsep.join(paths + [env.get("PATH", "")])
    env.pop("RIPGREP_CONFIG_PATH", None)
    return env

def health():
    cfg = load_config()
    env = environment(cfg)
    return {"rga": tool_path(cfg.get("rga_path"), "rga"),
            "dependencies": {n: shutil.which(n, path=env["PATH"]) for n in ("rg", "pandoc", "pdftotext", "ffmpeg", "fd")},
            "roots": cfg["roots"], "semantic_search": "not implemented by this endpoint"}

def decode(value):
    return value.get("text") if "text" in value else base64.b64decode(value["bytes"]).decode("utf-8", "replace")

_VAULT_CACHE = {}
_VAULT_SKIP = {".git", "node_modules", ".obsidian", ".trash", ".stversions", "target", "$RECYCLE.BIN"}

def obsidian_vaults(root, max_depth=8, ttl=600):
    """Outermost folders under root that contain a .obsidian directory (cached)."""
    key = str(root).lower()
    hit = _VAULT_CACHE.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    vaults = []
    base = len(Path(root).parts)
    for current, dirs, _ in os.walk(root):
        if ".obsidian" in dirs:
            vaults.append(Path(current))
            dirs[:] = []
            continue
        if len(Path(current).parts) - base >= max_depth:
            dirs[:] = []
        else:
            dirs[:] = [d for d in dirs if d not in _VAULT_SKIP]
    _VAULT_CACHE[key] = (time.time(), vaults)
    return vaults

def search(query, roots=None, file_types=None, maximum_results=50, regex=False, case_sensitive=False, include_hidden=False, obsidian="any"):
    if not query or len(query) > 4096 or not 1 <= maximum_results <= 500:
        raise ValueError("Provide a nonempty query (up to 4096 characters) and 1-500 results")
    prepared = _prepare(query, roots, file_types, regex, case_sensitive, include_hidden, obsidian)
    if isinstance(prepared, dict):
        return prepared
    cfg, args, paths = prepared
    return _run_search(cfg, args, paths, query, maximum_results)

def _prepare(query, roots, file_types, regex, case_sensitive, include_hidden, obsidian, files_only=False):
    """Validate a request and build the rga command. Returns (cfg, args, paths) or an empty-result dict."""
    if not query or len(query) > 4096:
        raise ValueError("Provide a nonempty query (up to 4096 characters)")
    cfg = load_config()
    aliases = roots or cfg.get("default_roots", [])
    if not aliases or any(a not in cfg["roots"] for a in aliases):
        raise ValueError("Use configured root aliases only")
    paths = []
    for alias in aliases:
        p = Path(cfg["roots"][alias]).resolve()
        if not p.is_dir():
            raise ValueError(f"Search root unavailable: {alias}")
        paths.append(p)
    extensions = file_types or []
    if any(not re.fullmatch(r"[A-Za-z0-9]+", e) for e in extensions):
        raise ValueError("File types must be extensions such as md, lean, pdf")
    exe = tool_path(cfg.get("rga_path"), "rga")
    if not exe:
        raise RuntimeError("rga is missing; configure rga_path or install ripgrep-all")
    cache = ROOT / cfg.get("cache_path", "data/search-cache")
    cache.mkdir(parents=True, exist_ok=True)
    args = [exe, "--files-with-matches" if files_only else "--json", "--line-number", "--no-heading",
            "--color=never", "--no-config", "--rga-cache-path=" + str(cache), "--threads", "2"]
    if not regex:
        args.append("--fixed-strings")
    if not case_sensitive:
        args.append("--ignore-case")
    if include_hidden:
        args += ['--hidden', '--no-ignore']
    for ext in extensions:
        args += ["--glob", "*." + ext]
    if obsidian not in ("any", "only", "exclude"):
        raise ValueError("obsidian must be any, only or exclude")
    if obsidian == "only":
        root_paths = paths
        paths = []
        for p in root_paths:
            # A root inside a vault is already Obsidian-only.
            if any((a / ".obsidian").is_dir() for a in (p, *p.parents)):
                paths.append(p)
            else:
                paths += obsidian_vaults(p)
        if not paths:
            return {"results": [], "returned": 0, "complete": True, "incomplete_reason": None,
                    "diagnostic": "No Obsidian vaults (folders with .obsidian) in the selected locations."}
        args += ["--glob", "!**/.obsidian/**"]
    elif obsidian == "exclude":
        # Filtered as results arrive; rg globs cannot anchor to absolute search roots.
        cfg["_blocked_vaults"] = [v for p in paths for v in obsidian_vaults(p)]
        if any(any((a / ".obsidian").is_dir() for a in (p, *p.parents)) for p in paths):
            cfg["_blocked_vaults"] += [p for p in paths if any((a / ".obsidian").is_dir() for a in (p, *p.parents))]
    args += ["--", query, *map(str, paths)]
    return cfg, args, paths

def _run_search(cfg, args, paths, query, maximum_results):
    # Explicit root aliases only; no shell and no caller-provided executable/options.
    proc =subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment(cfg),
                            cwd=ROOT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    events = queue.Queue(maxsize=128)
    stop = threading.Event()
    errors = []
    def read_stdout():
        try:
            while not stop.is_set():
                line = proc.stdout.readline(1024 * 1024 + 1)
                if not line:
                    break
                while not stop.is_set():
                    try:
                        events.put(line, timeout=.1)
                        break
                    except queue.Full:
                        pass
        finally:
            while not stop.is_set():
                try:
                    events.put(None, timeout=.1)
                    break
                except queue.Full:
                    pass
    def read_stderr():
        while True:
            chunk = proc.stderr.read(4096)
            if not chunk:
                return
            if sum(map(len, errors)) < 16384:
                errors.append(chunk)
    readers = [threading.Thread(target=read_stdout, daemon=True), threading.Thread(target=read_stderr, daemon=True)]
    for reader in readers:
        reader.start()
    results = []
    reason = None
    deadline = time.monotonic() + min(float(cfg.get("timeout_seconds", 30)), 120)
    canonical = cfg.get("canonical_register", {})
    try:
        while True:
            if time.monotonic() >= deadline:
                reason = "timeout"
                break
            try:
                line = events.get(timeout=.1)
            except queue.Empty:
                continue
            if line is None:
                break
            if len(line) > 1024 * 1024:
                reason = "oversized_result"
                break
            event = json.loads(line)
            if event.get("type") != "match":
                continue
            data = event["data"]
            path = Path(decode(data["path"])).resolve()
            if not any(path.is_relative_to(root) for root in paths):
                continue
            if any(path.is_relative_to(v) for v in cfg.get("_blocked_vaults", ())):
                continue
            if len(results) == maximum_results:
                reason = "result_limit"
                break
            modified = None
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
            except OSError:
                pass
            results.append({"path": str(path), "line": data.get("line_number"),
                            "passage": decode(data["lines"]).rstrip("\r\n"),
                            "modified": modified, "canonical_status": canonical.get(str(path), "unknown"),
                            "locator_kind": "rga_extracted_line", "submatches": data.get("submatches", [])})
    finally:
        stop.set()
        if proc.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            else:
                proc.kill()
        proc.wait()
        for reader in readers:
            reader.join(timeout=2)
        proc.stdout.close()
        proc.stderr.close()
    diagnostic = b"".join(errors).decode("utf-8", "replace").strip()
    if (proc.returncode not in (0, 1) or diagnostic) and not reason:
        reason = "search_error"
    return {"query": query, "results": results, "returned": len(results),
            "complete": reason is None, "incomplete_reason": reason,
            "diagnostic": diagnostic, "backend": "rga", "ordering": "engine traversal; not relevance ranked"}


_GATHER_JOBS = {}

def start_gather(query, destination, roots=None, file_types=None, regex=False, case_sensitive=False,
                 include_hidden=False, obsidian="any", keep_structure=True):
    """Find every file matching the query (no result cap) and copy them into destination in the background."""
    dest = Path(destination)
    if not dest.is_absolute():
        raise ValueError("Destination must be an absolute folder path")
    prepared = _prepare(query, roots, file_types, regex, case_sensitive, include_hidden, obsidian, files_only=True)
    if isinstance(prepared, dict):
        raise ValueError(prepared.get("diagnostic") or "Nothing to search")
    cfg, args, paths = prepared
    job_id = hashlib.sha256(f"{time.time()}{query}".encode()).hexdigest()[:12]
    job = {"id": job_id, "query": query, "destination": str(dest), "state": "searching",
           "found": 0, "copied": 0, "skipped": 0, "failed": 0, "receipt": None, "error": None}
    _GATHER_JOBS[job_id] = job
    threading.Thread(target=_gather_worker, args=(job, cfg, args, paths, dest, keep_structure), daemon=True).start()
    return job

def gather_status(job_id):
    job = _GATHER_JOBS.get(job_id)
    if not job:
        raise ValueError("Unknown gather job")
    return job

def _gather_worker(job, cfg, args, paths, dest, keep_structure):
    import csv
    try:
        proc = subprocess.run(args, capture_output=True, env=environment(cfg), cwd=ROOT,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        files = []
        seen = set()
        dest_resolved = dest.resolve()
        for raw in proc.stdout.decode("utf-8", "replace").splitlines():
            if not raw.strip():
                continue
            src = Path(raw.strip()).resolve()
            root = next((r for r in paths if src.is_relative_to(r)), None)
            # Never re-gather files already sitting in the destination.
            if root is None or src.is_relative_to(dest_resolved) or str(src).lower() in seen \
                    or any(src.is_relative_to(v) for v in cfg.get("_blocked_vaults", ())):
                continue
            seen.add(str(src).lower())
            files.append((src, root))
        job["found"] = len(files)
        job["state"] = "copying"
        dest.mkdir(parents=True, exist_ok=True)
        rows = []
        for src, root in files:
            if keep_structure:
                target = dest / (root.name or "root") / src.relative_to(root)
            else:
                target = dest / src.name
            try:
                if target.exists():
                    if target.stat().st_size == src.stat().st_size and target.stat().st_mtime >= src.stat().st_mtime:
                        job["skipped"] += 1
                        rows.append([src, target, "already present"])
                        continue
                    stem, n = target.stem, 1
                    while target.exists():
                        target = target.with_name(f"{stem}-{n}{target.suffix}")
                        n += 1
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
                job["copied"] += 1
                rows.append([src, target, "copied"])
            except OSError as exc:
                job["failed"] += 1
                rows.append([src, "", str(exc)])
        receipt = dest / f"gather-receipt-{datetime.now():%Y%m%d-%H%M%S}.csv"
        with receipt.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["source", "copied_to", "status"])
            w.writerows(rows)
        job["receipt"] = str(receipt)
        job["state"] = "done"
    except Exception as exc:
        job["state"] = "failed"
        job["error"] = str(exc)
