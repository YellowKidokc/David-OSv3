"""Read-only inventory and source reference index for the David-OSv3 audit."""
import ast
import csv
import json
import os
import re
import stat
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
AUDIT = ROOT / "_AUDIT"
SKIP = {".git", ".venv", "node_modules", "__pycache__", ".lake"}
CODE = {".py", ".pyw", ".ps1", ".psm1", ".bat", ".cmd", ".ahk", ".rs", ".js", ".ts",
        ".html", ".toml", ".ini", ".yaml", ".yml", ".json", ".md", ".sh", ".sql"}
MAX = 20 * 1024 * 1024
ABS = re.compile(r"(?<![\w])(?:[DHZ]:|C:(?=[\\/]+Users\b)|[\\/]{2,}192\.168(?:\.\d+){2})(?:[\\/]+[^\r\n\"'<>\x60|;,)}\]]{1,240})?", re.I)
SUSPICIOUS = re.compile(r"(?:while\s+True|Observer\(|PollingObserver|watchdog\.|watchfiles|FileSystemWatcher|"
                        r"schedule\.|Start-Job|Register-ScheduledTask|daemon=True|setInterval\(|uuid(?:4|7)\(|"
                        r"mint_(?:id|series|paper)|(?:allocate|issue)_(?:id|series|paper)|"
                        r"DeepSeek|MiniLM|\.fisnote|sqlite3\.connect)", re.I)
SPECIAL = re.compile(r"^(?:AGENTS|README|ARCHITECTURE|_ABOUT)(?:\.|_)", re.I)


def git(*args):
    return subprocess.check_output(["git", "--no-optional-locks", *args],
                                   cwd=ROOT).decode("utf-8", errors="replace")


def write_csv(name, headers, rows):
    with (AUDIT / name).open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file);writer.writerow(headers);writer.writerows(rows)


def scan_tree():
    rows, boundaries, errors = [], [], []
    stack = [(ROOT, "", False)]
    seen_dirs = set()
    while stack:
        path, prefix, excluded = stack.pop()
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    relative = f"{prefix}/{entry.name}" if prefix else entry.name
                    if not prefix and entry.name == "_AUDIT":
                        continue
                    try:
                        info = entry.stat(follow_symlinks=False)
                        if entry.is_symlink() or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                            boundaries.append((relative, "link/reparse point not followed"))
                            continue
                        if stat.S_ISDIR(info.st_mode):
                            if relative.count("/") >= 150:
                                boundaries.append((relative, "depth boundary"))
                                continue
                            if entry.name in SKIP and not excluded:
                                boundaries.append((relative, "metadata counted; contents excluded"))
                            identity = (info.st_dev, info.st_ino)
                            if info.st_ino and identity in seen_dirs:
                                boundaries.append((relative, "already visited directory identity"))
                                continue
                            seen_dirs.add(identity)
                            stack.append((Path(entry.path), relative, excluded or entry.name in SKIP))
                        elif stat.S_ISREG(info.st_mode):
                            rows.append((relative, info.st_size, info.st_mtime_ns, excluded))
                    except OSError as exc:
                        errors.append((relative, str(exc)))
        except OSError as exc:
            errors.append((prefix, str(exc)))
    return rows, boundaries, errors


def parse_source(rows, tracked):
    paths = set(path for path, *_ in rows)
    name_map = defaultdict(set)
    for path in paths:
        p = Path(path)
        if p.suffix == ".py":
            name_map[p.stem].add(path)
    refs, entries, signals, exclusions, launches = [], [], [], [], []
    for path, size, _, skip in rows:
        p = Path(path)
        suffix = p.suffix.casefold()
        if skip or suffix not in CODE:
            continue
        if size > MAX:
            exclusions.append((path, size, "above 20 MiB source-text limit"))
            continue
        try:
            data = (ROOT / p).read_bytes()
            if data.startswith((b"\xff\xfe", b"\xfe\xff")):
                text = data.decode("utf-16")
            else:
                text = data.decode("utf-8-sig", errors="replace")
        except (OSError, UnicodeError) as exc:
            exclusions.append((path, size, str(exc)))
            continue
        top = path.split("/")[0]
        if suffix in {".bat", ".cmd", ".ps1", ".sh"}:
            entries.append((top, path, "launcher/script", "tracked" if path in tracked else "working tree only"))
        elif suffix == ".py" and re.search(r"""if\s+__name__\s*==\s*['"]__main__['"]""", text):
            entries.append((top, path, "Python main", "tracked" if path in tracked else "working tree only"))
        for number, line in enumerate(text.splitlines(), 1):
            if suffix in {".bat", ".cmd", ".ps1", ".sh"} and re.search(r"\b(?:pythonw?|py|uvicorn|cargo|node|start-process|call|pushd|cd)\b|%~dp0|\$PSScriptRoot", line, re.I):
                launches.append((path, number, line.strip()[:450]))
            for match in ABS.finditer(line):
                literal = match.group().strip().rstrip(" .")
                refs.append((path, number, "absolute literal", literal, "", "VERIFIED literal; use not necessarily active"))
            if suffix not in {".md", ".html", ".json"}:
                for match in SUSPICIOUS.finditer(line):
                    signals.append((path, number, match.group(), line.strip()[:200]))
        if suffix == ".py":
            try:
                tree = ast.parse(text)
            except (SyntaxError, ValueError, RecursionError):
                continue
            for n in ast.walk(tree):
                if not isinstance(n, (ast.Import, ast.ImportFrom)):
                    continue
                imports = [x.name for x in n.names] if isinstance(n, ast.Import) else [("." * n.level) + (n.module or "")]
                for mod in imports:
                    if mod.startswith("."):
                        base = p.parent
                        dots = len(mod) - len(mod.lstrip("."))
                        for _ in range(dots-1):
                            base = base.parent
                        target_path = base.joinpath(*mod.lstrip(".").split("."))
                    else:
                        target_path = Path(*mod.split("."))
                    package = {target_path.with_suffix(".py").as_posix(), (target_path/"__init__.py").as_posix()}
                    if not mod.startswith("."):
                        package |= {(p.parent / q).as_posix() for q in package}
                    candidates = package & paths
                    if not candidates and not mod.startswith(".") and "." not in mod:
                        candidates = name_map.get(mod, set())
                    external = sorted(t for t in candidates if t.split("/")[0] != top)
                    if external:
                        refs.append((path, n.lineno, "cross-folder import", mod, " | ".join(external),
                                     "VERIFIED import; target " + ("candidate" if len(candidates)==1 else "ambiguous")))
    return refs, entries, signals, exclusions, launches


def main():
    tracked = set(git("ls-files", "-z").rstrip("\0").split("\0"))
    files, boundaries, errors = scan_tree()
    stats, details = {}, defaultdict(list)
    for p, size, mtime, excluded in files:
        if "/" not in p:
            continue
        top = p.split("/")[0]
        d = stats.setdefault(top, dict(folder=top, file_count=0, size_bytes=0, last_ns=0, excluded_content_files=0, tracked_files=0))
        d["file_count"] += 1;d["size_bytes"] += size;d["last_ns"] = max(d["last_ns"], mtime)
        d["excluded_content_files"] += int(excluded);d["tracked_files"] += int(p in tracked)
    for entry in ROOT.iterdir():
        if entry.is_dir() and entry.name != "_AUDIT":
            stats.setdefault(entry.name, dict(folder=entry.name,file_count=0,size_bytes=0,last_ns=0,excluded_content_files=0,tracked_files=0))
    refs, entries, signals, exclusions, launches = parse_source(files, tracked)
    for top, path, kind, state in entries:
        details[top].append(dict(path=path, kind=kind, git=state))
    for name, d in stats.items():
        ns = d.pop("last_ns")
        d["last_change"] = datetime.fromtimestamp(ns/1e9, timezone.utc).astimezone().isoformat(timespec="seconds") if ns else None
        d["entry_points"] = sorted(details[name], key=lambda x:x["path"])
    (AUDIT/"inventory_raw.json").write_text(json.dumps(list(stats.values()),indent=2),encoding="utf-8")
    write_csv("file_metadata.csv", ["path","bytes","mtime_ns","excluded_from_content"], files)
    write_csv("scan_boundaries.csv", ["path","reason"], boundaries + errors)
    write_csv("content_exclusions.csv", ["path","bytes","reason"], exclusions)
    write_csv("source_references.csv", ["source","line","kind","value","candidate_targets","confidence"], refs)
    write_csv("launchers.csv", ["source","line","command_excerpt"], launches)
    write_csv("principle_signals.csv", ["path","line","signal","excerpt"], signals)
    write_csv("tracked_over_5mb.csv", ["path","bytes"], sorted(
        [(p,s) for p,s,_,_ in files if p in tracked and s>5_000_000],key=lambda x:-x[1]))
    print(f"{len(files):,} files, {len(stats)} top-level folders, {len(refs):,} references, {len(entries):,} entries, "
          f"{len(boundaries)} boundaries, {len(errors)} read errors.",flush=True)


if __name__ == "__main__":
    main()
