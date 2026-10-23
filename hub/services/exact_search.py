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

def search(query, roots=None, file_types=None, maximum_results=50, regex=False, case_sensitive=False, include_hidden=False):
    if not query or len(query) > 4096 or not 1 <= maximum_results <= 500:
        raise ValueError("Provide a nonempty query (up to 4096 characters) and 1-500 results")
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
    args = [exe, "--json", "--line-number", "--no-heading", "--color=never", "--no-config",
            "--rga-cache-path=" + str(cache), "--threads", "2"]
    if not regex:
        args.append("--fixed-strings")
    if not case_sensitive:
        args.append("--ignore-case")
    if include_hidden:
        args += ['--hidden', '--no-ignore']
    for ext in extensions:
        args += ["--glob", "*." + ext]
    args += ["--", query, *map(str, paths)]
    # Explicit root aliases only; no shell and no caller-provided executable/options.
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment(cfg),
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

