from __future__ import annotations

import csv
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import yaml

from organize import fileintel, ledger, settings as app_settings


APP_TITLE = "Organize Desktop"
DEFAULT_PREVIEW_LIMIT = 5000
SCAN_LIMIT = 200_000

# Built-in bundles of extensions so you can tick "Excel" instead of typing
# xlsx, xls, csv... every time. Custom extensions can be added on top.
EXTENSION_GROUPS: Dict[str, List[str]] = {
    "Excel": ["xlsx", "xls", "xlsm", "xlsb", "csv"],
    "Word": ["doc", "docx", "rtf", "odt"],
    "PowerPoint": ["ppt", "pptx"],
    "PDF": ["pdf"],
    "Pictures": ["jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp", "heic", "svg"],
    "Videos": ["mp4", "mov", "avi", "mkv", "wmv", "flv", "webm", "m4v"],
    "Audio": ["mp3", "wav", "flac", "aac", "ogg", "m4a", "wma"],
    "Archives": ["zip", "rar", "7z", "tar", "gz", "bz2"],
    "Code": ["py", "js", "ts", "java", "c", "cpp", "cs", "go", "rs", "rb", "php", "html", "css", "json"],
    "HTML": ["htm", "html"],
}

# Types that aren't extension-based (handled specially in search)
SPECIAL_SEARCH_TYPES = ["Folders", "Files"]

NO_EXTENSION_LABEL = "(no extension)"


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
@dataclass
class RuleRow:
    field: str
    operator: str
    value: str
    destination: str


def normalize_extensions(value: str) -> List[str]:
    parts = []
    for raw in value.replace(";", ",").split(","):
        part = raw.strip().lstrip(".").lower()
        if part:
            parts.append(part)
    return parts


def split_paths(value: str) -> List[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def path_for_yaml(path: str) -> str:
    return str(Path(path).expanduser())


def dump_yaml(config: Dict[str, Any]) -> str:
    return yaml.safe_dump(config, sort_keys=False, allow_unicode=True)


def home_folder(*parts: str) -> str:
    return str(Path.home().joinpath(*parts))


# --------------------------------------------------------------------------- #
# Quick Sort config builder (unchanged behaviour, kept tab-stable)
# --------------------------------------------------------------------------- #
# the organizer must never move/sort the history ledger or FIS sidecars
LEDGER_EXCLUDE_FILES = [f"*{ledger.LEDGER_EXT}", ledger.FIS_META]
LEDGER_EXCLUDE_DIRS = ["$Recycle.Bin", "System Volume Information"]


def common_location(path: str, recursive: bool) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "path": path_for_yaml(path),
        "exclude_files": list(LEDGER_EXCLUDE_FILES),
        "exclude_dirs": list(LEDGER_EXCLUDE_DIRS),
    }
    if recursive:
        data["max_depth"] = None
    return data


def build_rule_config(
    *,
    source_paths: List[str],
    destination: str,
    mode: str,
    recursive: bool,
    apply_rules: bool,
    rule_mode: str,
    custom_rules: List[RuleRow],
    date_basis: str,
    copy_instead: bool = False,
) -> Dict[str, Any]:
    if not source_paths:
        raise ValueError("Add at least one source folder.")
    if not destination:
        raise ValueError("Choose a destination folder.")

    destination = str(Path(destination).expanduser())
    locations = [common_location(path, recursive) for path in source_paths]
    action_name = "copy" if copy_instead else "move"
    rules: List[Dict[str, Any]] = []

    def action(dest: str) -> Dict[str, Any]:
        return {action_name: {"dest": dest, "on_conflict": "rename_new"}}

    if mode == "Extension":
        rules.append(
            {
                "name": "Sort files by extension",
                "locations": locations,
                "subfolders": recursive,
                "filters": ["extension"],
                "actions": [
                    action(
                        os.path.join(
                            destination,
                            "{extension.upper() if extension else 'NO_EXTENSION'}",
                            "",
                        )
                    )
                ],
            }
        )
    elif mode == "Alphabet":
        rules.append(
            {
                "name": "Sort files alphabetically",
                "locations": locations,
                "subfolders": recursive,
                "filters": ["name"],
                "actions": [
                    action(
                        os.path.join(
                            destination,
                            "{path.name[0].upper() if path.name else '_'}",
                            "",
                        )
                    )
                ],
            }
        )
    elif mode == "Date":
        filter_name = "created" if date_basis == "Created" else "lastmodified"
        rules.append(
            {
                "name": f"Sort files by {date_basis.lower()} date",
                "locations": locations,
                "subfolders": recursive,
                "filters": [filter_name],
                "actions": [
                    action(
                        os.path.join(
                            destination,
                            "{" + filter_name + ".strftime('%Y-%m-%d')}",
                            "",
                        )
                    )
                ],
            }
        )
    elif mode == "Size":
        size_rules = [
            ("Tiny files", "<100kb", "Tiny"),
            ("Small files", ">=100kb, <10mb", "Small"),
            ("Medium files", ">=10mb, <1gb", "Medium"),
            ("Huge files", ">=1gb", "Huge"),
        ]
        for name, condition, folder in size_rules:
            rules.append(
                {
                    "name": name,
                    "locations": locations,
                    "subfolders": recursive,
                    "filters": [{"size": condition}],
                    "actions": [action(os.path.join(destination, folder, ""))],
                }
            )
    elif mode == "Type":
        rules.append(
            {
                "name": "Sort files by type",
                "locations": locations,
                "subfolders": recursive,
                "filters": ["extension"],
                "actions": [
                    action(
                        os.path.join(
                            destination,
                            "Files",
                            "{extension.upper() if extension else 'NO_EXTENSION'}",
                            "",
                        )
                    )
                ],
            }
        )
        rules.append(
            {
                "name": "Sort folders",
                "targets": "dirs",
                "locations": locations,
                "subfolders": recursive,
                "filters": ["name"],
                "actions": [action(os.path.join(destination, "Folders", ""))],
            }
        )
    elif mode in {"Custom", "Rules"}:
        if apply_rules and custom_rules:
            rules.append(
                build_custom_rule(
                    locations=locations,
                    destination=destination,
                    recursive=recursive,
                    rule_mode=rule_mode,
                    custom_rules=custom_rules,
                    action=action,
                )
            )
        else:
            rules.append(
                {
                    "name": "Move everything",
                    "locations": locations,
                    "subfolders": recursive,
                    "actions": [action(os.path.join(destination, ""))],
                }
            )
    else:
        raise ValueError(f"Unknown mode: {mode}")

    return {"rules": rules}


def build_custom_rule(
    *,
    locations: List[Dict[str, Any]],
    destination: str,
    recursive: bool,
    rule_mode: str,
    custom_rules: List[RuleRow],
    action,
) -> Dict[str, Any]:
    filters: List[Any] = []
    dest = custom_rules[-1].destination.strip() if custom_rules else ""
    if not dest:
        dest = "Matched"

    for row in custom_rules:
        field_name = row.field
        operator = row.operator
        value = row.value.strip()
        if not value and field_name != "Size":
            continue

        if field_name == "Name":
            filters.append({"name": {operator.lower(): value, "case_sensitive": False}})
        elif field_name == "Extension":
            exts = normalize_extensions(value)
            filters.append({"extension": exts if len(exts) != 1 else exts[0]})
        elif field_name == "Size":
            filters.append({"size": value or ">0"})
        elif field_name == "Created Older Than Days":
            filters.append({"created": {"days": int(value), "mode": "older"}})
        elif field_name == "Modified Older Than Days":
            filters.append({"lastmodified": {"days": int(value), "mode": "older"}})

    if not filters:
        raise ValueError("Add at least one usable custom rule.")

    return {
        "name": "Custom GUI rule",
        "locations": locations,
        "subfolders": recursive,
        "filter_mode": "any" if rule_mode == "OR" else "all",
        "filters": filters,
        "actions": [action(os.path.join(destination, dest, ""))],
    }


def iter_items(paths: Iterable[str], recursive: bool, limit: int = DEFAULT_PREVIEW_LIMIT):
    _SKIP_DIRS = {'$recycle.bin', '$recycle', 'node_modules', '.git', '__pycache__', '.venv', 'system volume information'}
    seen = 0
    for source in paths:
        root = Path(source).expanduser()
        if not root.exists():
            continue
        iterator = root.rglob("*") if recursive else root.iterdir()
        for item in iterator:
            if seen >= limit:
                return
            if item.name.startswith("."):
                continue
            # Skip system/junk directories
            if any(part.lower() in _SKIP_DIRS for part in item.parts):
                continue
            seen += 1
            yield item


def preview_bucket(path: Path, mode: str, date_basis: str) -> str:
    if mode == "Extension":
        return path.suffix.lstrip(".").upper() or "NO_EXTENSION"
    if mode == "Alphabet":
        return path.name[:1].upper() or "_"
    if mode == "Date":
        stamp = path.stat().st_ctime if date_basis == "Created" else path.stat().st_mtime
        import datetime as _dt

        return _dt.datetime.fromtimestamp(stamp).strftime("%Y-%m-%d")
    if mode == "Size":
        size = path.stat().st_size if path.is_file() else 0
        if size < 100_000:
            return "Tiny"
        if size < 10_000_000:
            return "Small"
        if size < 1_000_000_000:
            return "Medium"
        return "Huge"
    if mode == "Type":
        if path.is_dir():
            return "Folders"
        return f"Files/{path.suffix.lstrip('.').upper() or 'NO_EXTENSION'}"
    return "Matched"


# --------------------------------------------------------------------------- #
# Workflow model (multi-stage, ignore folders, save/load)
# --------------------------------------------------------------------------- #
@dataclass
class Stage:
    name: str
    extensions: List[str] = field(default_factory=list)
    name_contains: str = ""
    destination: str = ""
    copy_instead: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "extensions": list(self.extensions),
            "name_contains": self.name_contains,
            "destination": self.destination,
            "copy_instead": self.copy_instead,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Stage":
        return cls(
            name=data.get("name", "Stage"),
            extensions=list(data.get("extensions", [])),
            name_contains=data.get("name_contains", ""),
            destination=data.get("destination", ""),
            copy_instead=bool(data.get("copy_instead", False)),
        )

    def label(self) -> str:
        if self.extensions:
            kinds = ", ".join(self.extensions)
        else:
            kinds = "all files"
        extra = f" name~'{self.name_contains}'" if self.name_contains else ""
        verb = "copy" if self.copy_instead else "move"
        return f"{self.name}: {verb} [{kinds}]{extra} -> {self.destination}"


@dataclass
class Workflow:
    name: str
    sources: List[str] = field(default_factory=list)
    ignore_dirs: List[str] = field(default_factory=list)
    recursive: bool = True
    stages: List[Stage] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "sources": list(self.sources),
            "ignore_dirs": list(self.ignore_dirs),
            "recursive": self.recursive,
            "stages": [stage.to_dict() for stage in self.stages],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Workflow":
        return cls(
            name=data.get("name", "Workflow"),
            sources=list(data.get("sources", [])),
            ignore_dirs=list(data.get("ignore_dirs", [])),
            recursive=bool(data.get("recursive", True)),
            stages=[Stage.from_dict(s) for s in data.get("stages", [])],
        )


def workflow_location(path: str, recursive: bool, ignore_dirs: List[str]) -> Dict[str, Any]:
    data: Dict[str, Any] = {"path": path_for_yaml(path), "exclude_files": list(LEDGER_EXCLUDE_FILES)}
    if recursive:
        data["max_depth"] = None
    if ignore_dirs:
        data["exclude_dirs"] = sorted({d.strip() for d in ignore_dirs if d.strip()})
    return data


def build_stage_rule(stage: Stage, locations: List[Dict[str, Any]], recursive: bool) -> Dict[str, Any]:
    filters: List[Any] = []
    exts = [e.strip().lstrip(".").lower() for e in stage.extensions if e.strip()]
    if exts:
        filters.append({"extension": exts})
    if stage.name_contains.strip():
        filters.append(
            {"name": {"contains": stage.name_contains.strip(), "case_sensitive": False}}
        )

    action_name = "copy" if stage.copy_instead else "move"
    dest = str(Path(stage.destination).expanduser())
    rule: Dict[str, Any] = {
        "name": stage.name or "Stage",
        "locations": locations,
        "subfolders": recursive,
    }
    if filters:
        rule["filters"] = filters
        if len(filters) > 1:
            rule["filter_mode"] = "all"
    rule["actions"] = [
        {action_name: {"dest": os.path.join(dest, ""), "on_conflict": "rename_new"}}
    ]
    return rule


def build_workflow_config(workflow: Workflow) -> Dict[str, Any]:
    if not workflow.sources:
        raise ValueError("Add at least one source folder.")
    if not workflow.stages:
        raise ValueError("Add at least one stage (for example: Excel -> Documents/Excel).")

    locations = [
        workflow_location(path, workflow.recursive, workflow.ignore_dirs)
        for path in workflow.sources
    ]
    rules: List[Dict[str, Any]] = []
    for stage in workflow.stages:
        if not stage.destination.strip():
            raise ValueError(f"Stage '{stage.name}' needs a destination folder.")
        rules.append(build_stage_rule(stage, locations, workflow.recursive))
    return {"rules": rules}


def _ignored(path: Path, ignore: set) -> bool:
    return any(part.lower() in ignore for part in path.parts)


def scan_extensions(
    sources: List[str], recursive: bool, ignore_dirs: List[str], limit: int = SCAN_LIMIT
) -> Dict[str, int]:
    ignore = {d.strip().lower() for d in ignore_dirs if d.strip()}
    counts: Dict[str, int] = {}
    seen = 0
    for source in sources:
        root = Path(source).expanduser()
        if not root.exists():
            continue
        iterator = root.rglob("*") if recursive else root.iterdir()
        for item in iterator:
            if seen >= limit:
                return counts
            try:
                if _ignored(item, ignore):
                    continue
                if not item.is_file():
                    continue
            except OSError:
                continue
            ext = item.suffix.lstrip(".").lower() or NO_EXTENSION_LABEL
            counts[ext] = counts.get(ext, 0) + 1
            seen += 1
    return counts


def count_stage_matches(
    stage: Stage, sources: List[str], recursive: bool, ignore_dirs: List[str]
) -> int:
    ignore = {d.strip().lower() for d in ignore_dirs if d.strip()}
    wanted = {e.strip().lstrip(".").lower() for e in stage.extensions if e.strip()}
    sub = stage.name_contains.strip().lower()
    total = 0
    seen = 0
    for source in sources:
        root = Path(source).expanduser()
        if not root.exists():
            continue
        iterator = root.rglob("*") if recursive else root.iterdir()
        for item in iterator:
            if seen >= SCAN_LIMIT:
                return total
            try:
                if _ignored(item, ignore):
                    continue
                if not item.is_file():
                    continue
            except OSError:
                continue
            seen += 1
            ext = item.suffix.lstrip(".").lower()
            if wanted and ext not in wanted:
                continue
            if sub and sub not in item.name.lower():
                continue
            total += 1
    return total


# --------------------------------------------------------------------------- #
# Cleanup helpers: empty folders, duplicate files, folder snapshot
# --------------------------------------------------------------------------- #
JUNK_FILES = {"desktop.ini", "thumbs.db", ".ds_store"}
SYNC_ARTIFACT_DIRS = {".stfolder", ".stversions", ".sync", "@eadir", ".syncthing"}
CLEANUP_SKIP_DIRS = {
    "$recycle.bin", "system volume information", ".git",
    "node_modules", "__pycache__", ".venv",
}

# trailing noise that makes "Report (3)", "report - Copy 2", "Report_v12"
# all collapse to "report". Bare trailing digits are left alone on purpose
# ("Track 2" is usually a real name, not a duplicate marker).
_DUP_NOISE = re.compile(
    r"(?ix)[\s_\-.]*(?:"
    r"\(\s*(?:copy|kopie|\d{1,4})\s*\)"                     # (1)  (copy)
    r"|(?<![a-z0-9])copy(?:\s*\d{1,3})?"                    # copy, Copy 2
    r"|(?<![a-z0-9])v(?:er(?:sion)?)?\s*\.?\s*\d{1,4}"      # v2, ver.3, version 12
    r")$"
)


def normalize_dup_name(filename: str) -> str:
    """'Report (3).pdf', 'report - Copy.pdf', 'Report_v2.pdf' -> 'report'."""
    stem = Path(filename).stem
    prev = None
    while prev != stem:
        prev = stem
        stem = _DUP_NOISE.sub("", stem).strip()
    cleaned = re.sub(r"[\s_\-]+", " ", stem).strip().lower()
    return cleaned or Path(filename).stem.strip().lower()


def _is_junk_file(name: str) -> bool:
    return (
        name.lower() in JUNK_FILES
        or name.endswith(ledger.LEDGER_EXT)
        or name == ledger.FIS_META
    )


def throttled(callback, interval: float = 0.15):
    """Wrap a progress callback so it fires at most every `interval` seconds.
    Scanners can then report every single path — you see where a scan is
    (or where it's stuck) without flooding the Tk event queue."""
    last = [0.0]

    def emit(message: str) -> None:
        now = time.monotonic()
        if now - last[0] >= interval:
            last[0] = now
            callback(message)

    return emit


def find_empty_dirs(sources: List[str], progress=None) -> List[str]:
    """Folders with no real files anywhere below them (junk like Thumbs.db
    and ledger sidecars don't count). Returned deepest-first so children can
    be deleted before their parents."""
    results: List[str] = []
    empties: set = set()
    seen_roots: set = set()
    for source in sources:
        root = str(Path(source).expanduser())
        root_key = os.path.normcase(os.path.normpath(root))
        if not Path(root).exists() or root_key in seen_roots:
            continue
        seen_roots.add(root_key)
        for dirpath, dirnames, filenames in os.walk(root, topdown=False):
            if any(part.lower() in CLEANUP_SKIP_DIRS for part in Path(dirpath).parts):
                continue
            if progress:
                progress(f"Checking: {dirpath}")
            key = os.path.normcase(os.path.normpath(dirpath))
            real_files = [f for f in filenames if not _is_junk_file(f)]
            subs_empty = all(
                os.path.normcase(os.path.normpath(os.path.join(dirpath, d))) in empties
                for d in dirnames
            )
            if not real_files and subs_empty and key != root_key:
                empties.add(key)
                results.append(dirpath)
    results.sort(key=lambda p: (-len(Path(p).parts), p.lower()))
    return results


def _file_md5(path: str, limit: int = 0) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as fh:
        if limit:
            digest.update(fh.read(limit))
        else:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
    return digest.hexdigest()


def scan_duplicates(
    sources: List[str],
    recursive: bool,
    mode: str,
    progress=None,
) -> List[List[Dict[str, Any]]]:
    """Find duplicate groups. mode: 'content' (MD5 only), 'name+content'
    (normalized name AND MD5), 'name' (normalized name only — no hashing,
    review before deleting). Only files that share size get hashed, with a
    quick 64KB pre-hash so big unique files are never fully read."""
    files: List[Dict[str, Any]] = []
    seen = 0
    for source in sources:
        root = Path(source).expanduser()
        if not root.exists():
            continue
        if recursive:
            walker = os.walk(str(root))
        else:
            try:
                names = [e.name for e in os.scandir(str(root)) if e.is_file()]
            except OSError:
                continue
            walker = [(str(root), [], names)]
        for dirpath, _dirs, filenames in walker:
            if any(part.lower() in CLEANUP_SKIP_DIRS for part in Path(dirpath).parts):
                continue
            if progress:
                progress(f"Listing ({seen:,} files): {dirpath}")
            for fn in filenames:
                if _is_junk_file(fn):
                    continue
                full = os.path.join(dirpath, fn)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                files.append(
                    {"path": full, "name": fn, "folder": dirpath,
                     "size": st.st_size, "mtime": st.st_mtime}
                )
                seen += 1
                if seen >= SCAN_LIMIT:
                    break

    def name_key(f: Dict[str, Any]):
        return (normalize_dup_name(f["name"]), Path(f["name"]).suffix.lower())

    groups: Dict[Any, List[Dict[str, Any]]] = {}
    if mode == "name":
        for f in files:
            groups.setdefault(name_key(f), []).append(f)
    else:
        buckets: Dict[Any, List[Dict[str, Any]]] = {}
        for f in files:
            pre = (name_key(f), f["size"]) if mode == "name+content" else f["size"]
            buckets.setdefault(pre, []).append(f)
        hashed = 0
        for bucket in buckets.values():
            if len(bucket) < 2:
                continue
            quick: Dict[str, List[Dict[str, Any]]] = {}
            for f in bucket:
                if progress:
                    progress(f"Pre-hashing: {f['path']}")
                try:
                    quick.setdefault(_file_md5(f["path"], limit=65536), []).append(f)
                except OSError:
                    continue
            for qgroup in quick.values():
                if len(qgroup) < 2:
                    continue
                for f in qgroup:
                    if progress:
                        progress(f"Hashing ({hashed:,} done): {f['path']}")
                    try:
                        f["md5"] = _file_md5(f["path"])
                    except OSError:
                        continue
                    hashed += 1
                for f in qgroup:
                    if "md5" not in f:
                        continue
                    key = (name_key(f), f["md5"]) if mode == "name+content" else f["md5"]
                    groups.setdefault(key, []).append(f)

    result = [sorted(g, key=lambda f: f["path"].lower()) for g in groups.values() if len(g) > 1]
    result.sort(key=lambda g: -sum(f["size"] for f in g[1:]))  # most reclaimable first
    return result


def pick_keeper(group: List[Dict[str, Any]], strategy: str) -> int:
    """Index of the file to KEEP in a duplicate group."""
    idx = range(len(group))
    if strategy == "First found":
        return 0
    if strategy == "Biggest":
        return max(idx, key=lambda i: group[i]["size"])
    if strategy == "Oldest modified":
        return min(idx, key=lambda i: group[i]["mtime"])
    if strategy == "Cleanest name":
        def score(i: int):
            stem = Path(group[i]["name"]).stem
            plain = re.sub(r"[\s_\-]+", " ", stem).strip().lower()
            has_noise = normalize_dup_name(group[i]["name"]) != plain
            return (has_noise, len(group[i]["name"]), group[i]["path"].lower())
        return min(idx, key=score)
    return max(idx, key=lambda i: group[i]["mtime"])  # Newest modified (default)


def folder_snapshot(root: str, progress=None) -> List[Dict[str, Any]]:
    """One row per immediate subfolder: recursive file count, total size,
    newest modified time, and a triage flag (EMPTY / sync artifacts only /
    conflict copy)."""
    rows: List[Dict[str, Any]] = []
    base = Path(root).expanduser()
    for entry in sorted(base.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_dir() or entry.name.lower() in CLEANUP_SKIP_DIRS:
            continue
        file_count = 0
        real_count = 0
        total = 0
        newest = 0.0
        for dirpath, _dirs, filenames in os.walk(str(entry)):
            if progress:
                progress(f"Measuring {entry.name}: {dirpath}")
            in_sync_dir = any(p.lower() in SYNC_ARTIFACT_DIRS for p in Path(dirpath).parts)
            for fn in filenames:
                try:
                    st = os.stat(os.path.join(dirpath, fn))
                except OSError:
                    continue
                file_count += 1
                total += st.st_size
                newest = max(newest, st.st_mtime)
                if not in_sync_dir and not _is_junk_file(fn):
                    real_count += 1
        if file_count == 0:
            flag = "EMPTY"
        elif real_count == 0:
            flag = "sync artifacts only"
        elif "conflict" in entry.name.lower():
            flag = "conflict copy"
        else:
            flag = ""
        rows.append(
            {"name": entry.name, "path": str(entry), "files": file_count,
             "size": total, "mtime": newest, "flag": flag}
        )
    return rows


def find_folders_by_type(
    root: str,
    extensions: set,
    threshold_pct: float,
    min_files: int = 5,
    progress=None,
) -> List[Dict[str, Any]]:
    """Find folders where >= threshold_pct of the files (counted recursively)
    have one of the given extensions. Only the TOPMOST qualifying folder of a
    tree is reported — children of a hit are not listed again. min_files keeps
    two-file folders from showing up as '100%'."""
    base = str(Path(root).expanduser())
    exts = {e.lower().lstrip(".") for e in extensions if e.strip()}
    counts: Dict[str, List[float]] = {}   # normcased dir -> [match, total, size, newest]
    display: Dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(base, topdown=False):
        if any(part.lower() in CLEANUP_SKIP_DIRS for part in Path(dirpath).parts):
            continue
        if progress:
            progress(f"Scanning: {dirpath}")
        match = total = 0
        size = 0
        newest = 0.0
        for fn in filenames:
            if _is_junk_file(fn):
                continue
            total += 1
            ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
            if ext in exts:
                match += 1
            try:
                st = os.stat(os.path.join(dirpath, fn))
                size += st.st_size
                newest = max(newest, st.st_mtime)
            except OSError:
                pass
        for d in dirnames:
            child = counts.get(os.path.normcase(os.path.join(dirpath, d)))
            if child:
                match += child[0]
                total += child[1]
                size += child[2]
                newest = max(newest, child[3])
        key = os.path.normcase(dirpath)
        counts[key] = [match, total, size, newest]
        display[key] = dirpath

    qualifying = {
        key for key, (m, t, _s, _n) in counts.items()
        if t >= min_files and (m / t) * 100.0 >= threshold_pct
    }
    results: List[Dict[str, Any]] = []
    for key in qualifying:
        parent = os.path.dirname(key)
        suppressed = False
        while parent and parent != key:
            if parent in qualifying:
                suppressed = True
                break
            nxt = os.path.dirname(parent)
            if nxt == parent:
                break
            parent = nxt
        if suppressed:
            continue
        m, t, size, newest = counts[key]
        results.append({
            "path": display[key],
            "rel": os.path.relpath(display[key], base),
            "match": int(m), "files": int(t),
            "pct": (m / t) * 100.0,
            "size": size, "mtime": newest,
        })
    results.sort(key=lambda r: (-r["pct"], -r["files"]))
    return results


def compare_trees(
    left: str,
    right: str,
    deep: bool = True,
    match_moved: bool = True,
    progress=None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Compare the tree being emptied (left) against the master copy (right).

    Buckets every left-side file:
      identical  — same relative path, same content (or size if deep=False)
      moved      — not at the same path, but identical content exists
                   somewhere in the master (match_moved)
      different  — same relative path but the content differs: review
      left_only  — nothing like it in the master: unique, migrate first
    Plus right_only for completeness."""
    emit = progress or (lambda _m: None)

    def index(root_str: str, label: str) -> Dict[str, Dict[str, Any]]:
        root = str(Path(root_str).expanduser())
        out: Dict[str, Dict[str, Any]] = {}
        for dirpath, _dirs, filenames in os.walk(root):
            if any(part.lower() in CLEANUP_SKIP_DIRS for part in Path(dirpath).parts):
                continue
            emit(f"Indexing {label}: {dirpath}")
            for fn in filenames:
                if _is_junk_file(fn):
                    continue
                full = os.path.join(dirpath, fn)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                rel = os.path.relpath(full, root)
                out[os.path.normcase(rel)] = {
                    "rel": rel, "path": full,
                    "size": st.st_size, "mtime": st.st_mtime,
                }
        return out

    lefts = index(left, "delete side")
    rights = index(right, "master")

    identical: List[Dict[str, Any]] = []
    different: List[Dict[str, Any]] = []
    left_only: List[Dict[str, Any]] = []
    moved: List[Dict[str, Any]] = []

    for key in sorted(lefts):
        lf = lefts[key]
        rf = rights.get(key)
        if rf is None:
            left_only.append(lf)
            continue
        if lf["size"] != rf["size"]:
            different.append({**lf, "note": "size differs"})
            continue
        if deep:
            emit(f"Verifying content: {lf['rel']}")
            try:
                if _file_md5(lf["path"]) != _file_md5(rf["path"]):
                    different.append({**lf, "note": "content differs"})
                    continue
            except OSError as exc:
                different.append({**lf, "note": f"read error: {exc}"})
                continue
        identical.append({**lf, "note": "matches master" if deep else "same size (not verified)"})

    right_only = [rights[k] for k in sorted(rights.keys() - lefts.keys())]

    if match_moved and left_only:
        by_size: Dict[int, List[Dict[str, Any]]] = {}
        for rf in rights.values():
            by_size.setdefault(rf["size"], []).append(rf)
        remaining: List[Dict[str, Any]] = []
        for lf in left_only:
            hit = None
            candidates = by_size.get(lf["size"], [])
            if candidates:
                emit(f"Looking for moved copy: {lf['rel']}")
                try:
                    lhash = _file_md5(lf["path"])
                except OSError:
                    lhash = None
                if lhash:
                    for rf in candidates:
                        if "md5" not in rf:
                            try:
                                rf["md5"] = _file_md5(rf["path"])
                            except OSError:
                                continue
                        if rf["md5"] == lhash:
                            hit = rf
                            break
            if hit:
                moved.append({**lf, "note": f"same content at: {hit['rel']}", "match": hit["rel"]})
            else:
                remaining.append(lf)
        left_only = remaining

    return {
        "identical": identical, "moved": moved, "different": different,
        "left_only": left_only, "right_only": right_only,
    }


def send_to_trash(path: str) -> str:
    """Recycle Bin when possible; permanent delete as fallback (UNC paths)."""
    try:
        from send2trash import send2trash as _trash
        _trash(os.fspath(path))
        return "recycled"
    except Exception:
        target = Path(path)
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return "deleted permanently"


def _fmt_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024 or unit == "TB":
            return f"{num:,.0f} {unit}" if unit == "B" else f"{num:,.1f} {unit}"
        num /= 1024
    return f"{num:,.1f} TB"


# --------------------------------------------------------------------------- #
# Workflow persistence (starters shipped in code, user copies on disk)
# --------------------------------------------------------------------------- #
def workflows_dir() -> Path:
    return Path.home() / ".organize_gui" / "workflows"


def list_saved_workflows() -> List[str]:
    directory = workflows_dir()
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.json"))


def load_saved_workflow(name: str) -> Workflow:
    path = workflows_dir() / f"{name}.json"
    return Workflow.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_workflow(workflow: Workflow) -> Path:
    directory = workflows_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{workflow.name}.json"
    path.write_text(json.dumps(workflow.to_dict(), indent=2), encoding="utf-8")
    return path


def delete_saved_workflow(name: str) -> None:
    path = workflows_dir() / f"{name}.json"
    if path.exists():
        path.unlink()


def starter_workflows() -> Dict[str, Workflow]:
    """A couple of ready-to-run examples so the first launch is useful."""
    return {
        "Excel: Desktop -> Documents": Workflow(
            name="Excel: Desktop -> Documents",
            sources=[home_folder("Desktop"), home_folder("Documents")],
            ignore_dirs=[],
            recursive=False,
            stages=[
                Stage(
                    name="Gather Excel files",
                    extensions=list(EXTENSION_GROUPS["Excel"]),
                    destination=home_folder("Documents", "Excel"),
                )
            ],
        ),
        "Pictures: Desktop -> Pictures": Workflow(
            name="Pictures: Desktop -> Pictures",
            sources=[home_folder("Desktop")],
            ignore_dirs=[],
            recursive=False,
            stages=[
                Stage(
                    name="Gather pictures",
                    extensions=list(EXTENSION_GROUPS["Pictures"]),
                    destination=home_folder("Pictures", "From Desktop"),
                )
            ],
        ),
        "Downloads cleanup": Workflow(
            name="Downloads cleanup",
            sources=[home_folder("Downloads")],
            ignore_dirs=[],
            recursive=False,
            stages=[
                Stage("Excel", list(EXTENSION_GROUPS["Excel"]), "", home_folder("Documents", "Excel")),
                Stage("PDFs", list(EXTENSION_GROUPS["PDF"]), "", home_folder("Documents", "PDF")),
                Stage("Pictures", list(EXTENSION_GROUPS["Pictures"]), "", home_folder("Pictures", "From Downloads")),
                Stage("Archives", list(EXTENSION_GROUPS["Archives"]), "", home_folder("Downloads", "Archives")),
            ],
        ),
    }


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #
class OrganizeGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1280x820")
        self.minsize(1040, 680)

        # Quick Sort state
        self.source_var = tk.StringVar()
        self.destination_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="Extension")
        self.recursive_var = tk.BooleanVar(value=True)
        self.copy_var = tk.BooleanVar(value=False)
        self.apply_rules_var = tk.BooleanVar(value=True)
        self.rule_mode_var = tk.StringVar(value="AND")
        self.date_basis_var = tk.StringVar(value="Modified")
        self.status_var = tk.StringVar(value="Ready.")
        self.rules: List[RuleRow] = []
        self._preview_excluded: set = set()  # extensions excluded via preview buttons
        self._last_sim_success: bool = False  # track if simulation ran OK

        # Workflow state
        self.workflow_stages: List[Stage] = []
        self.scanned_exts: List[Tuple[str, int]] = []
        self.wf_status_var = tk.StringVar(value="Build a workflow, scan, then add stages.")

        # persistent settings (NLP threshold, default process)
        self.settings = app_settings.load_settings()

        # File Intelligence state
        self.fi_url_var = tk.StringVar(value=fileintel.FIS_DEFAULT_URL)
        self.fi_folder_var = tk.StringVar()
        self.fi_status_var = tk.StringVar(value="Pick a folder + a renaming process, then Scan.")
        self.fi_process_var = tk.StringVar(value=self.settings["renaming_process"])
        self.fi_threshold_var = tk.StringVar(value=str(self.settings["nlp_threshold"]))
        self.fi_rows: List[Dict[str, Any]] = []
        self.fi_checked: set = set()
        self.fi_connected = False
        self.fi_queue: "queue.Queue[Tuple[str, Any]]" = queue.Queue()

        # Cleanup tab state (empty folders + duplicates)
        self.cl_status_var = tk.StringVar(value="Add folders, then find empty folders or duplicate files.")
        self.cl_recursive_var = tk.BooleanVar(value=True)
        self.cl_match_var = tk.StringVar(value="Exact content (MD5)")
        self.cl_keep_var = tk.StringVar(value="Newest modified")
        self.cl_queue: "queue.Queue[Tuple[str, Any]]" = queue.Queue()
        self.cl_busy = False
        self.cl_empty_dirs: List[str] = []
        self.cl_empty_checked: set = set()
        self.cl_dup_groups: List[List[Dict[str, Any]]] = []
        self.cl_dup_rows: List[Dict[str, Any]] = []
        self.cl_dup_checked: set = set()

        # Snapshot tab state (folder triage view)
        self.snap_root_var = tk.StringVar()
        self.snap_status_var = tk.StringVar(value="Choose a root folder, then take a snapshot.")
        self.snap_rows: List[Dict[str, Any]] = []
        self.snap_checked: set = set()

        # Compare tab state (empty one drive against its master copy)
        self.cmp_left_var = tk.StringVar()
        self.cmp_right_var = tk.StringVar()
        self.cmp_verify_var = tk.StringVar(value="Verify content (MD5) — safe")
        self.cmp_moved_var = tk.BooleanVar(value=True)
        self.cmp_status_var = tk.StringVar(
            value="Left = the drive you're emptying. Right = the master copy. Compare, then delete what matches."
        )
        self.cmp_result: Dict[str, List[Dict[str, Any]]] = {}
        self.cmp_entries: Dict[str, Dict[str, Any]] = {}
        self.cmp_checkable: set = set()
        self.cmp_checked: set = set()

        # History ledger state
        self.hist_interval_var = tk.StringVar(value=str(int(ledger.DEFAULT_INTERVAL)))
        self.hist_status_var = tk.StringVar(value="History watcher is stopped.")
        self.hist_watcher_thread: Optional[threading.Thread] = None
        self.hist_stop_event: Optional[threading.Event] = None

        # output is routed per-tab via (target, text) tuples
        self.output_queue: "queue.Queue[Tuple[str, str]]" = queue.Queue()
        self.yaml_widgets: Dict[str, tk.Text] = {}
        self.output_widgets: Dict[str, tk.Text] = {}

        self._build_ui()
        self._apply_dark_theme()
        self.after(150, self._drain_output_queue)
        self.after(150, self._fi_drain)
        self.after(150, self._cl_drain)
        self._refresh_yaml_and_preview()
        self._wf_populate_workflow_list()
        self._wf_refresh_yaml_and_preview()

    # ----- dark ("blacked out") theme -----
    def _apply_dark_theme(self) -> None:
        bg = "#121212"      # window
        panel = "#1e1e1e"   # frames / panels
        field = "#2a2a2a"   # entries, lists, tables
        fg = "#e6e6e6"      # main text
        sub = "#b8b8b8"     # secondary text
        sel = "#0a4d8c"     # selection / accent
        border = "#3c3c3c"
        disabled = "#6b6b6b"

        self.configure(bg=bg)
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=panel, foreground=fg, fieldbackground=field,
                        bordercolor=border, lightcolor=panel, darkcolor=panel,
                        troughcolor=field, insertcolor=fg, arrowcolor=fg)
        style.configure("TFrame", background=panel)
        style.configure("TLabel", background=panel, foreground=fg)
        style.configure("TLabelframe", background=panel, foreground=fg, bordercolor=border)
        style.configure("TLabelframe.Label", background=panel, foreground=sub)
        style.configure("TButton", background=field, foreground=fg, bordercolor=border, focuscolor=sel)
        style.map("TButton",
                  background=[("pressed", sel), ("active", "#37373d"), ("disabled", panel)],
                  foreground=[("disabled", disabled)])
        style.configure("TCheckbutton", background=panel, foreground=fg)
        style.map("TCheckbutton", background=[("active", panel)], foreground=[("disabled", disabled)])
        style.configure("TRadiobutton", background=panel, foreground=fg)
        style.map("TRadiobutton", background=[("active", panel)])
        style.configure("TEntry", fieldbackground=field, foreground=fg, insertcolor=fg, bordercolor=border)
        style.map("TEntry", fieldbackground=[("disabled", panel)], foreground=[("disabled", disabled)])
        style.configure("TSpinbox", fieldbackground=field, foreground=fg, insertcolor=fg,
                        arrowcolor=fg, bordercolor=border)
        style.configure("TCombobox", fieldbackground=field, foreground=fg, background=field,
                        arrowcolor=fg, bordercolor=border)
        style.map("TCombobox",
                  fieldbackground=[("readonly", field), ("disabled", panel)],
                  foreground=[("readonly", fg), ("disabled", disabled)])
        style.configure("TNotebook", background=bg, bordercolor=border)
        style.configure("TNotebook.Tab", background=panel, foreground=sub, padding=(12, 6))
        style.map("TNotebook.Tab", background=[("selected", field)], foreground=[("selected", fg)])
        style.configure("Treeview", background=field, fieldbackground=field, foreground=fg,
                        bordercolor=border, rowheight=22)
        style.configure("Treeview.Heading", background=panel, foreground=sub, bordercolor=border)
        style.map("Treeview.Heading", background=[("active", "#37373d")])
        style.map("Treeview", background=[("selected", sel)], foreground=[("selected", "#ffffff")])
        style.configure("Vertical.TScrollbar", background=panel, troughcolor=bg,
                        bordercolor=border, arrowcolor=fg)
        style.configure("Horizontal.TScrollbar", background=panel, troughcolor=bg,
                        bordercolor=border, arrowcolor=fg)

        # combobox drop-down list (a tk Listbox under the hood)
        self.option_add("*TCombobox*Listbox.background", field)
        self.option_add("*TCombobox*Listbox.foreground", fg)
        self.option_add("*TCombobox*Listbox.selectBackground", sel)
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

        # restyle plain tk widgets (Text, Listbox) that ttk styles don't reach
        self._restyle_tk_widgets(self, field, fg, sel, border)

        # blacken the native Windows title bar too
        self._dark_title_bar()
        self.after(40, self._dark_title_bar)

    def _dark_title_bar(self) -> None:
        if not sys.platform.startswith("win"):
            return
        try:
            import ctypes

            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            value = ctypes.c_int(1)
            for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE: 20 (Win10 1903+), 19 older
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
                )
        except Exception:
            pass  # cosmetic only; never fail launch over the title bar

    def _restyle_tk_widgets(self, widget, field, fg, sel, border) -> None:
        for child in widget.winfo_children():
            cls = child.winfo_class()
            if cls in ("Text", "Listbox"):
                opts = dict(
                    background=field, foreground=fg,
                    selectbackground=sel, selectforeground="#ffffff",
                    highlightbackground=border, highlightcolor=sel,
                    relief="flat", borderwidth=1,
                )
                if cls == "Text":
                    opts["insertbackground"] = fg  # Listbox has no insert cursor
                try:
                    child.configure(**opts)
                except tk.TclError:
                    pass
            self._restyle_tk_widgets(child, field, fg, sel, border)

    # ----- top-level layout: notebook with two tabs -----
    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        quick_tab = ttk.Frame(notebook)
        workflow_tab = ttk.Frame(notebook)
        fileintel_tab = ttk.Frame(notebook)
        cleanup_tab = ttk.Frame(notebook)
        snapshot_tab = ttk.Frame(notebook)
        compare_tab = ttk.Frame(notebook)
        history_tab = ttk.Frame(notebook)
        settings_tab = ttk.Frame(notebook)
        notebook.add(quick_tab, text="Quick Sort")
        notebook.add(workflow_tab, text="Workflow Builder")
        notebook.add(fileintel_tab, text="File Intelligence")
        notebook.add(cleanup_tab, text="Cleanup")
        notebook.add(snapshot_tab, text="Snapshot")
        notebook.add(compare_tab, text="Compare")
        notebook.add(history_tab, text="History")
        notebook.add(settings_tab, text="Settings")

        self._build_quick_tab(quick_tab)
        self._build_workflow_tab(workflow_tab)
        self._build_fileintel_tab(fileintel_tab)
        self._build_cleanup_tab(cleanup_tab)
        self._build_snapshot_tab(snapshot_tab)
        self._build_compare_tab(compare_tab)
        self._build_history_tab(history_tab)
        self._build_settings_tab(settings_tab)

        bottom = ttk.Frame(self, padding=(12, 0, 12, 8))
        bottom.pack(fill="x", side="bottom")
        ttk.Label(bottom, textvariable=self.status_var).pack(side="left")

    # ----------------------------------------------------------------- #
    # Quick Sort tab (preserved behaviour)
    # ----------------------------------------------------------------- #
    def _build_quick_tab(self, root: ttk.Frame) -> None:
        root.columnconfigure(0, weight=0)
        root.columnconfigure(1, weight=1)
        root.columnconfigure(2, weight=1)
        root.rowconfigure(1, weight=1)

        top = ttk.Frame(root, padding=(12, 10))
        top.grid(row=0, column=0, columnspan=3, sticky="ew")
        top.columnconfigure(1, weight=1)
        top.columnconfigure(4, weight=1)

        # --- Source folders (multi-folder listbox) ---
        src_frame = ttk.LabelFrame(top, text="Source folders", padding=4)
        src_frame.grid(row=0, column=0, columnspan=3, sticky="ew")
        src_frame.columnconfigure(0, weight=1)

        self.source_listbox = tk.Listbox(src_frame, height=3, selectmode="extended")
        self.source_listbox.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        src_btns = ttk.Frame(src_frame)
        src_btns.grid(row=0, column=1, sticky="ns")
        ttk.Button(src_btns, text="Add", width=7, command=self._choose_source).pack(pady=(0, 2))
        ttk.Button(src_btns, text="Remove", width=7, command=self._remove_source).pack(pady=(0, 2))
        ttk.Button(src_btns, text="MDA", width=7, command=self._load_mda_sources).pack(pady=(0, 2))

        # --- Destination ---
        ttk.Label(top, text="Destination").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(top, textvariable=self.destination_var).grid(row=1, column=1, sticky="ew", padx=6, pady=(6, 0))
        ttk.Button(top, text="Choose", command=self._choose_destination).grid(row=1, column=2, padx=3, pady=(6, 0))

        # --- Presets ---
        preset_frame = ttk.Frame(top)
        preset_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        ttk.Label(preset_frame, text="Preset:").pack(side="left")
        self.preset_name_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(preset_frame, textvariable=self.preset_name_var, width=25)
        self.preset_combo.pack(side="left", padx=6)
        ttk.Button(preset_frame, text="Save", width=6, command=self._save_preset).pack(side="left", padx=2)
        ttk.Button(preset_frame, text="Load", width=6, command=self._load_preset).pack(side="left", padx=2)
        ttk.Button(preset_frame, text="Delete", width=6, command=self._delete_preset).pack(side="left", padx=2)
        self._refresh_preset_list()

        # --- Search (left) + Action buttons (right) ---
        bar = ttk.Frame(top)
        bar.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        bar.columnconfigure(0, weight=1)

        search = ttk.LabelFrame(bar, text="Find files everywhere  ·  searches your Source folders", padding=6)
        search.grid(row=0, column=0, sticky="ew")
        ttk.Label(search, text="Type").grid(row=0, column=0, sticky="w")
        self.search_type_var = tk.StringVar(value="Any")
        ttk.Combobox(
            search, textvariable=self.search_type_var, width=9,
            values=["Any"] + list(EXTENSION_GROUPS) + SPECIAL_SEARCH_TYPES,
        ).grid(row=0, column=1, padx=(4, 12))
        ttk.Label(search, text="Name contains").grid(row=0, column=2, sticky="w")
        self.search_name_var = tk.StringVar()
        name_entry = ttk.Entry(search, textvariable=self.search_name_var, width=30)
        name_entry.grid(row=0, column=3, padx=4)
        name_entry.bind("<Return>", lambda _e: self._run_file_search())
        ttk.Label(search, text="(comma or | to search multiple terms)").grid(row=1, column=2, columnspan=2, sticky="w", pady=(1, 0))
        self.search_filename_only_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(search, text="Filename only (uncheck to match full path)",
                        variable=self.search_filename_only_var).grid(row=2, column=2, columnspan=3, sticky="w", pady=(2, 0))
        self.search_strict_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(search, text="Strict title match  (term must be a whole word — not buried inside another word)",
                        variable=self.search_strict_var).grid(row=3, column=2, columnspan=3, sticky="w", pady=(1, 0))
        ttk.Button(search, text="Search", command=self._run_file_search).grid(row=0, column=4, padx=4)
        ttk.Button(search, text="Clear", width=6, command=self._clear_file_search).grid(row=0, column=5)

        # Progress bar (hidden until search runs)
        self.search_progress = ttk.Progressbar(search, mode="indeterminate", length=200)
        self.search_progress.grid(row=4, column=0, columnspan=6, sticky="ew", pady=(4, 0))
        self.search_progress.grid_remove()  # hidden by default

        actions = ttk.Frame(bar)
        actions.grid(row=0, column=1, sticky="e", padx=(12, 0))
        ttk.Button(actions, text="Simulate",
                   command=lambda: self._run_quick(simulate=True)).pack(side="left", padx=(0, 4))
        ttk.Button(actions, text="Organize for real",
                   command=lambda: self._run_quick(simulate=False)).pack(side="left")

        left = ttk.Frame(root, padding=12)
        left.grid(row=1, column=0, sticky="nsew")
        left.columnconfigure(0, weight=1)

        ttk.Label(left, text="Organizer").grid(row=0, column=0, sticky="w")
        mode = ttk.Combobox(
            left,
            textvariable=self.mode_var,
            values=["Type", "Extension", "Date", "Alphabet", "Size", "Custom", "Rules"],
            state="readonly",
        )
        mode.grid(row=1, column=0, sticky="ew", pady=(3, 12))
        mode.bind("<<ComboboxSelected>>", lambda _e: self._refresh_yaml_and_preview())

        # --- Quick-pick extension filter ---
        ext_frame = ttk.LabelFrame(left, text="Filter by type", padding=6)
        ext_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        self._ext_filter_vars: Dict[str, tk.BooleanVar] = {}
        btn_frame = ttk.Frame(ext_frame)
        btn_frame.pack(fill="x")
        col = 0
        row_num = 0
        for group_name in EXTENSION_GROUPS:
            var = tk.BooleanVar(value=False)
            self._ext_filter_vars[group_name] = var
            cb = ttk.Checkbutton(
                btn_frame,
                text=group_name,
                variable=var,
                command=self._refresh_yaml_and_preview,
            )
            cb.grid(row=row_num, column=col, sticky="w", padx=2, pady=1)
            col += 1
            if col >= 3:
                col = 0
                row_num += 1

        filter_btns = ttk.Frame(ext_frame)
        filter_btns.pack(fill="x", pady=(4, 0))
        ttk.Button(filter_btns, text="All", width=6,
                   command=lambda: self._set_ext_filters(True)).pack(side="left", padx=2)
        ttk.Button(filter_btns, text="None", width=6,
                   command=lambda: self._set_ext_filters(False)).pack(side="left", padx=2)

        ttk.Checkbutton(
            left,
            text="Include subfolders",
            variable=self.recursive_var,
            command=self._refresh_yaml_and_preview,
        ).grid(row=3, column=0, sticky="w")
        ttk.Checkbutton(
            left,
            text="Copy instead of move",
            variable=self.copy_var,
            command=self._refresh_yaml_and_preview,
        ).grid(row=4, column=0, sticky="w")

        date_frame = ttk.LabelFrame(left, text="Date mode", padding=8)
        date_frame.grid(row=5, column=0, sticky="ew", pady=10)
        ttk.Radiobutton(
            date_frame,
            text="Modified",
            variable=self.date_basis_var,
            value="Modified",
            command=self._refresh_yaml_and_preview,
        ).pack(anchor="w")
        ttk.Radiobutton(
            date_frame,
            text="Created",
            variable=self.date_basis_var,
            value="Created",
            command=self._refresh_yaml_and_preview,
        ).pack(anchor="w")

        rules_frame = ttk.LabelFrame(left, text="Rules", padding=8)
        rules_frame.grid(row=6, column=0, sticky="ew", pady=10)
        rules_frame.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            rules_frame,
            text="Apply custom rules",
            variable=self.apply_rules_var,
            command=self._refresh_yaml_and_preview,
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(rules_frame, text="Process as").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(
            rules_frame,
            textvariable=self.rule_mode_var,
            values=["AND", "OR"],
            state="readonly",
            width=8,
        ).grid(row=1, column=1, sticky="w", pady=(6, 0))

        self.rule_field = tk.StringVar(value="Name")
        self.rule_operator = tk.StringVar(value="contains")
        self.rule_value = tk.StringVar()
        self.rule_dest = tk.StringVar(value="Matched")

        ttk.Combobox(
            rules_frame,
            textvariable=self.rule_field,
            values=[
                "Name",
                "Extension",
                "Size",
                "Created Older Than Days",
                "Modified Older Than Days",
            ],
            state="readonly",
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 2))
        ttk.Combobox(
            rules_frame,
            textvariable=self.rule_operator,
            values=["contains", "startswith", "endswith"],
            state="readonly",
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=2)
        ttk.Entry(rules_frame, textvariable=self.rule_value).grid(row=4, column=0, columnspan=2, sticky="ew", pady=2)
        ttk.Entry(rules_frame, textvariable=self.rule_dest).grid(row=5, column=0, columnspan=2, sticky="ew", pady=2)
        ttk.Button(rules_frame, text="Add Rule", command=self._add_rule).grid(row=6, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(rules_frame, text="Clear", command=self._clear_rules).grid(row=6, column=1, sticky="ew", pady=(8, 0), padx=(4, 0))

        self.rules_list = tk.Listbox(left, height=7)
        self.rules_list.grid(row=7, column=0, sticky="ew", pady=(2, 10))

        center = ttk.Frame(root, padding=12)
        center.grid(row=1, column=1, sticky="nsew")
        center.rowconfigure(1, weight=1)
        center.columnconfigure(0, weight=1)

        ttk.Label(center, text="Preview").grid(row=0, column=0, sticky="w")
        self.preview = ttk.Treeview(center, columns=("count",), show="tree headings", selectmode="extended")
        self.preview.heading("#0", text="Folder")
        self.preview.heading("count", text="Items")
        self.preview.column("count", width=80, anchor="e")
        self.preview.grid(row=1, column=0, sticky="nsew", pady=(6, 10))

        # Filter buttons for preview results
        filter_row = ttk.Frame(center)
        filter_row.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        filter_row.columnconfigure(0, weight=1)
        filter_row.columnconfigure(1, weight=1)
        ttk.Button(filter_row, text="Keep selected",
                   command=self._preview_keep_selected).grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ttk.Button(filter_row, text="Remove selected",
                   command=self._preview_remove_selected).grid(row=0, column=1, sticky="ew", padx=(3, 0))

        buttons = ttk.Frame(center)
        buttons.grid(row=3, column=0, sticky="ew")
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        ttk.Button(buttons, text="Refresh Preview", command=self._refresh_yaml_and_preview).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="Save YAML", command=self._save_yaml).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        right = ttk.Frame(root, padding=12)
        right.grid(row=1, column=2, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.rowconfigure(3, weight=1)
        right.columnconfigure(0, weight=1)

        ttk.Label(right, text="Generated config").grid(row=0, column=0, sticky="w")
        quick_yaml = tk.Text(right, height=16, wrap="none")
        quick_yaml.grid(row=1, column=0, sticky="nsew", pady=(6, 12))
        self.yaml_widgets["quick"] = quick_yaml

        ttk.Label(right, text="Run output").grid(row=2, column=0, sticky="w")
        quick_output = tk.Text(right, height=14, wrap="word")
        quick_output.grid(row=3, column=0, sticky="nsew", pady=(6, 0))
        self.output_widgets["quick"] = quick_output

    # ----------------------------------------------------------------- #
    # Workflow Builder tab
    # ----------------------------------------------------------------- #
    def _build_workflow_tab(self, root: ttk.Frame) -> None:
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(1, weight=1)

        # --- saved workflows bar ---
        bar = ttk.Frame(root, padding=(12, 10))
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        bar.columnconfigure(1, weight=1)
        ttk.Label(bar, text="Workflow").grid(row=0, column=0, sticky="w")
        self.wf_name_var = tk.StringVar(value="My workflow")
        ttk.Entry(bar, textvariable=self.wf_name_var).grid(row=0, column=1, sticky="ew", padx=6)
        self.wf_saved_var = tk.StringVar()
        self.wf_saved_combo = ttk.Combobox(bar, textvariable=self.wf_saved_var, state="readonly", width=34)
        self.wf_saved_combo.grid(row=0, column=2, padx=6)
        ttk.Button(bar, text="Load", command=self._wf_load_selected).grid(row=0, column=3, padx=2)
        ttk.Button(bar, text="Save", command=self._wf_save).grid(row=0, column=4, padx=2)
        ttk.Button(bar, text="Delete", command=self._wf_delete).grid(row=0, column=5, padx=2)

        # --- left column: sources, ignore, scan, stage builder ---
        left = ttk.Frame(root, padding=12)
        left.grid(row=1, column=0, sticky="nsew")
        left.columnconfigure(0, weight=1)
        left.rowconfigure(7, weight=1)

        # sources
        src = ttk.LabelFrame(left, text="Source folders (clean these out)", padding=8)
        src.grid(row=0, column=0, sticky="ew")
        src.columnconfigure(0, weight=1)
        self.wf_source_list = tk.Listbox(src, height=3)
        self.wf_source_list.grid(row=0, column=0, sticky="ew")
        src_btns = ttk.Frame(src)
        src_btns.grid(row=0, column=1, sticky="ns", padx=(6, 0))
        ttk.Button(src_btns, text="Add", width=8, command=self._wf_add_source).pack(fill="x")
        ttk.Button(src_btns, text="Remove", width=8, command=self._wf_remove_source).pack(fill="x", pady=(4, 0))

        # ignore
        ign = ttk.LabelFrame(left, text="Ignore folders (skip these)", padding=8)
        ign.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ign.columnconfigure(0, weight=1)
        self.wf_ignore_list = tk.Listbox(ign, height=3)
        self.wf_ignore_list.grid(row=0, column=0, sticky="ew")
        ign_btns = ttk.Frame(ign)
        ign_btns.grid(row=0, column=1, sticky="ns", padx=(6, 0))
        ttk.Button(ign_btns, text="Add folder", width=10, command=self._wf_add_ignore_folder).pack(fill="x")
        ttk.Button(ign_btns, text="Add name", width=10, command=self._wf_add_ignore_pattern).pack(fill="x", pady=(4, 0))
        ttk.Button(ign_btns, text="Remove", width=10, command=self._wf_remove_ignore).pack(fill="x", pady=(4, 0))

        ttk.Checkbutton(
            left,
            text="Include subfolders",
            variable=self.recursive_var,
            command=self._wf_refresh_yaml_and_preview,
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))

        # scan + extension picker
        scan = ttk.LabelFrame(left, text="Pre-scan: pick the file types to move", padding=8)
        scan.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        scan.columnconfigure(0, weight=1)
        ttk.Button(scan, text="Scan source folders", command=self._wf_scan).grid(row=0, column=0, sticky="ew")

        groups = ttk.Frame(scan)
        groups.grid(row=1, column=0, sticky="ew", pady=(8, 4))
        ttk.Label(groups, text="Quick pick:").pack(side="left")
        for name in EXTENSION_GROUPS:
            ttk.Button(groups, text=name, width=9, command=lambda n=name: self._wf_select_group(n)).pack(side="left", padx=2)

        self.wf_ext_list = tk.Listbox(scan, height=8, selectmode="extended", exportselection=False)
        self.wf_ext_list.grid(row=2, column=0, sticky="ew", pady=(4, 0))

        custom = ttk.Frame(scan)
        custom.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        custom.columnconfigure(0, weight=1)
        self.wf_custom_ext_var = tk.StringVar()
        ttk.Entry(custom, textvariable=self.wf_custom_ext_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(custom, text="Add custom extension", command=self._wf_add_custom_ext).grid(row=0, column=1, padx=(6, 0))

        # stage builder
        stage = ttk.LabelFrame(left, text="Turn the selection into a stage", padding=8)
        stage.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        stage.columnconfigure(1, weight=1)
        ttk.Label(stage, text="Stage name").grid(row=0, column=0, sticky="w")
        self.wf_stage_name_var = tk.StringVar(value="Move Excel")
        ttk.Entry(stage, textvariable=self.wf_stage_name_var).grid(row=0, column=1, sticky="ew", padx=6, pady=2)
        ttk.Label(stage, text="Name contains").grid(row=1, column=0, sticky="w")
        self.wf_stage_contains_var = tk.StringVar()
        ttk.Entry(stage, textvariable=self.wf_stage_contains_var).grid(row=1, column=1, sticky="ew", padx=6, pady=2)
        ttk.Label(stage, text="Send to").grid(row=2, column=0, sticky="w")
        self.wf_stage_dest_var = tk.StringVar(value=home_folder("Documents", "Excel"))
        ttk.Entry(stage, textvariable=self.wf_stage_dest_var).grid(row=2, column=1, sticky="ew", padx=6, pady=2)
        ttk.Button(stage, text="...", width=3, command=self._wf_choose_stage_dest).grid(row=2, column=2, pady=2)
        self.wf_stage_copy_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(stage, text="Copy instead of move", variable=self.wf_stage_copy_var).grid(row=3, column=0, columnspan=2, sticky="w")
        ttk.Button(stage, text="Add stage from selection", command=self._wf_add_stage).grid(row=4, column=0, columnspan=3, sticky="ew", pady=(6, 0))

        # --- right column: stages, preview, yaml, output, run ---
        right = ttk.Frame(root, padding=12)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        right.rowconfigure(4, weight=1)
        right.rowconfigure(6, weight=1)

        ttk.Label(right, text="Stages (run top to bottom)").grid(row=0, column=0, sticky="w")
        self.wf_stages_list = tk.Listbox(right, height=6)
        self.wf_stages_list.grid(row=1, column=0, sticky="nsew", pady=(4, 4))
        stage_btns = ttk.Frame(right)
        stage_btns.grid(row=2, column=0, sticky="ew")
        ttk.Button(stage_btns, text="Up", width=6, command=lambda: self._wf_move_stage(-1)).pack(side="left")
        ttk.Button(stage_btns, text="Down", width=6, command=lambda: self._wf_move_stage(1)).pack(side="left", padx=(4, 0))
        ttk.Button(stage_btns, text="Remove stage", command=self._wf_remove_stage).pack(side="left", padx=(4, 0))
        ttk.Button(stage_btns, text="Clear all", command=self._wf_clear_stages).pack(side="left", padx=(4, 0))

        ttk.Label(right, text="What each stage will move (preview)").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.wf_preview = ttk.Treeview(right, columns=("count",), show="tree headings", height=5)
        self.wf_preview.heading("#0", text="Stage -> destination")
        self.wf_preview.heading("count", text="Files")
        self.wf_preview.column("count", width=70, anchor="e")
        self.wf_preview.grid(row=4, column=0, sticky="nsew", pady=(4, 4))

        run_btns = ttk.Frame(right)
        run_btns.grid(row=5, column=0, sticky="ew", pady=(4, 4))
        run_btns.columnconfigure(0, weight=1)
        run_btns.columnconfigure(1, weight=1)
        run_btns.columnconfigure(2, weight=1)
        ttk.Button(run_btns, text="Refresh preview", command=self._wf_refresh_yaml_and_preview).grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ttk.Button(run_btns, text="Simulate", command=lambda: self._wf_run(simulate=True)).grid(row=0, column=1, sticky="ew", padx=3)
        ttk.Button(run_btns, text="Organize for real", command=lambda: self._wf_run(simulate=False)).grid(row=0, column=2, sticky="ew", padx=(3, 0))

        ttk.Label(right, text="Generated config / run output").grid(row=6, column=0, sticky="w", pady=(6, 0))
        wf_yaml = tk.Text(right, height=8, wrap="none")
        wf_yaml.grid(row=7, column=0, sticky="nsew", pady=(4, 4))
        self.yaml_widgets["workflow"] = wf_yaml
        wf_output = tk.Text(right, height=8, wrap="word")
        wf_output.grid(row=8, column=0, sticky="nsew")
        self.output_widgets["workflow"] = wf_output

        ttk.Label(right, textvariable=self.wf_status_var).grid(row=9, column=0, sticky="w", pady=(4, 0))

    # ----------------------------------------------------------------- #
    # Quick Sort callbacks
    # ----------------------------------------------------------------- #
    def _choose_source(self) -> None:
        selected = filedialog.askdirectory(title="Choose source folder")
        if not selected:
            return
        # Check for duplicates
        existing = list(self.source_listbox.get(0, "end"))
        if selected not in existing:
            self.source_listbox.insert("end", selected)
        # Sync to source_var for backward compat
        self.source_var.set("\n".join(self.source_listbox.get(0, "end")))
        if not self.destination_var.get().strip():
            self.destination_var.set(str(Path(selected) / "_organized"))
        self._refresh_yaml_and_preview()

    def _remove_source(self) -> None:
        """Remove selected folders from the source list."""
        selected = list(self.source_listbox.curselection())
        for idx in reversed(selected):
            self.source_listbox.delete(idx)
        self.source_var.set("\n".join(self.source_listbox.get(0, "end")))
        self._refresh_yaml_and_preview()

    def _load_mda_sources(self) -> None:
        """One-click: load all known MDA source folders and set the MDA destination."""
        mda_sources = [
            r"\\dlowenas\HPWorkstation\Desktop\Master HTMl\____ MDA WORKFLOW",
            r"\\dlowenas\HPWorkstation\Desktop\Master HTMl\faiththruPhysics",
            r"\\dlowenas\HPWorkstation\Desktop\Master HTMl\MDA-BUILD",
            r"\\dlowenas\HPWorkstation\Desktop\Master HTMl\K-Production-Ready",
        ]
        existing = list(self.source_listbox.get(0, "end"))
        for path in mda_sources:
            if path not in existing:
                self.source_listbox.insert("end", path)
        self.source_var.set("\n".join(self.source_listbox.get(0, "end")))
        # Pre-fill destination and search term
        self.destination_var.set(r"\\dlowenas\HPWorkstation\Desktop\_MDA")
        self.search_name_var.set("MDA, moral decline")
        self.search_type_var.set("HTML")
        self._refresh_yaml_and_preview()

    def _choose_destination(self) -> None:
        selected = filedialog.askdirectory(title="Choose destination folder")
        if selected:
            self.destination_var.set(selected)
            self._refresh_yaml_and_preview()

    def _add_rule(self) -> None:
        row = RuleRow(
            field=self.rule_field.get(),
            operator=self.rule_operator.get(),
            value=self.rule_value.get(),
            destination=self.rule_dest.get() or "Matched",
        )
        self.rules.append(row)
        self.rules_list.insert("end", f"{row.field} {row.operator} {row.value} -> {row.destination}")
        self._refresh_yaml_and_preview()

    def _clear_rules(self) -> None:
        self.rules.clear()
        self.rules_list.delete(0, "end")
        self._refresh_yaml_and_preview()

    def _set_ext_filters(self, state: bool) -> None:
        """Set all extension filter checkboxes to the given state."""
        for var in self._ext_filter_vars.values():
            var.set(state)
        self._preview_excluded.clear()  # Reset preview exclusions
        self._refresh_yaml_and_preview()

    def _get_active_extensions(self) -> List[str]:
        """Get list of extensions from checked quick-pick groups."""
        exts = []
        for group_name, var in self._ext_filter_vars.items():
            if var.get():
                exts.extend(EXTENSION_GROUPS[group_name])
        return exts

    def _preview_keep_selected(self) -> None:
        """Keep only the selected preview items — exclude everything else."""
        selected = self.preview.selection()
        if not selected:
            return
        keep_exts = set()
        for item_id in selected:
            text = self.preview.item(item_id, "text").strip().lower()
            if text and text != "no_extension" and text != "scanning...":
                keep_exts.add(text)
        if not keep_exts:
            return
        # Remove everything NOT selected from the treeview
        for item_id in list(self.preview.get_children()):
            text = self.preview.item(item_id, "text").strip().lower()
            if text not in keep_exts:
                self._preview_excluded.add(text)
                self.preview.delete(item_id)
        # Update YAML only (no rescan)
        try:
            config = self._current_config()
            self._set_text(self.yaml_widgets["quick"], dump_yaml(config))
            total = sum(int(self.preview.item(i, "values")[0] or 0) for i in self.preview.get_children())
            self.status_var.set(f"Ready. {total} files remaining.")
        except Exception as exc:
            self.status_var.set(str(exc))

    def _preview_remove_selected(self) -> None:
        """Remove the selected preview items — instant, no rescan."""
        selected = self.preview.selection()
        if not selected:
            return
        for item_id in selected:
            text = self.preview.item(item_id, "text").strip().lower()
            if text and text != "scanning...":
                self._preview_excluded.add(text)
            self.preview.delete(item_id)
        # Update YAML only (no rescan)
        try:
            config = self._current_config()
            self._set_text(self.yaml_widgets["quick"], dump_yaml(config))
            total = sum(int(self.preview.item(i, "values")[0] or 0) for i in self.preview.get_children())
            self.status_var.set(f"Ready. {total} files remaining.")
        except Exception as exc:
            self.status_var.set(str(exc))

    # --- Preset save/load ---
    _PRESETS_FILE = Path(os.getenv("LOCALAPPDATA", ".")) / "organize-gui" / "quick_presets.json"

    def _load_presets_data(self) -> Dict[str, Any]:
        if self._PRESETS_FILE.exists():
            try:
                return json.loads(self._PRESETS_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_presets_data(self, data: Dict[str, Any]) -> None:
        self._PRESETS_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._PRESETS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _refresh_preset_list(self) -> None:
        data = self._load_presets_data()
        names = sorted(data.keys())
        self.preset_combo["values"] = names

    def _save_preset(self) -> None:
        name = self.preset_name_var.get().strip()
        if not name:
            messagebox.showwarning(APP_TITLE, "Enter a preset name first.")
            return
        data = self._load_presets_data()
        sources = list(self.source_listbox.get(0, "end"))
        # Collect which extension filters are checked
        ext_filters = [g for g, v in self._ext_filter_vars.items() if v.get()]
        data[name] = {
            "sources": sources,
            "destination": self.destination_var.get(),
            "mode": self.mode_var.get(),
            "recursive": self.recursive_var.get(),
            "copy": self.copy_var.get(),
            "ext_filters": ext_filters,
        }
        self._save_presets_data(data)
        self._refresh_preset_list()
        self.status_var.set(f"Preset '{name}' saved.")

    def _load_preset(self) -> None:
        name = self.preset_name_var.get().strip()
        data = self._load_presets_data()
        if name not in data:
            messagebox.showwarning(APP_TITLE, f"Preset '{name}' not found.")
            return
        preset = data[name]
        # Restore sources
        self.source_listbox.delete(0, "end")
        for src in preset.get("sources", []):
            self.source_listbox.insert("end", src)
        self.source_var.set("\n".join(preset.get("sources", [])))
        # Restore destination
        self.destination_var.set(preset.get("destination", ""))
        # Restore mode
        self.mode_var.set(preset.get("mode", "Extension"))
        # Restore checkboxes
        self.recursive_var.set(preset.get("recursive", False))
        self.copy_var.set(preset.get("copy", False))
        # Restore extension filters
        for g, var in self._ext_filter_vars.items():
            var.set(g in preset.get("ext_filters", []))
        # Clear preview exclusions
        self._preview_excluded.clear()
        self._refresh_yaml_and_preview()
        self.status_var.set(f"Preset '{name}' loaded.")

    def _delete_preset(self) -> None:
        name = self.preset_name_var.get().strip()
        data = self._load_presets_data()
        if name in data:
            del data[name]
            self._save_presets_data(data)
            self._refresh_preset_list()
            self.preset_name_var.set("")
            self.status_var.set(f"Preset '{name}' deleted.")

    def _current_config(self) -> Dict[str, Any]:
        config = build_rule_config(
            source_paths=split_paths(self.source_var.get()),
            destination=self.destination_var.get().strip(),
            mode=self.mode_var.get(),
            recursive=self.recursive_var.get(),
            apply_rules=self.apply_rules_var.get(),
            rule_mode=self.rule_mode_var.get(),
            custom_rules=self.rules,
            date_basis=self.date_basis_var.get(),
            copy_instead=self.copy_var.get(),
        )
        # Inject extension filter from quick-pick buttons + preview exclusions
        active_exts = self._get_active_extensions()
        excluded = self._preview_excluded
        if active_exts or excluded:
            # Build final extension list: start with active, remove excluded
            if active_exts:
                final_exts = [e for e in active_exts if e not in excluded]
            else:
                # No quick-pick active, but we have exclusions from preview
                # We need to know what's available to exclude from
                # Use a broad list minus excluded
                final_exts = None  # Will handle via exclude_files pattern

            for rule in config.get("rules", []):
                existing_filters = rule.get("filters", [])
                existing_filters = [f for f in existing_filters
                                   if not (isinstance(f, dict) and "extension" in f)
                                   and f != "extension"]
                if final_exts is not None:
                    existing_filters.insert(0, {"extension": final_exts})
                elif excluded:
                    # No quick-pick but have exclusions — use NOT extension filter
                    existing_filters.insert(0, {"not": {"extension": sorted(excluded)}})
                rule["filters"] = existing_filters
        return config

    def _refresh_yaml_and_preview(self) -> None:
        try:
            config = self._current_config()
            self._set_text(self.yaml_widgets["quick"], dump_yaml(config))
            self._build_preview()
            self.status_var.set("Ready.")
        except Exception as exc:
            self._set_text(self.yaml_widgets["quick"], f"# {exc}\n")
            self.status_var.set(str(exc))

    def _build_preview(self) -> None:
        """Build preview in a background thread so the GUI doesn't freeze."""
        self.preview.delete(*self.preview.get_children())
        sources = split_paths(self.source_var.get())
        if not sources or not self.destination_var.get().strip():
            return

        self.status_var.set("Scanning...")
        self.preview.insert("", "end", text="Scanning...", values=("",))

        def _scan():
            counts: Dict[str, int] = {}
            mode = self.mode_var.get()
            active_exts = self._get_active_extensions()
            scanned = 0
            excluded = self._preview_excluded
            for item in iter_items(sources, self.recursive_var.get()):
                if item.is_file():
                    ext = item.suffix.lstrip(".").lower()
                    # Skip if extension is in the excluded set
                    if ext in excluded or (not ext and "no_extension" in excluded):
                        continue
                    # Skip if quick-pick filter is active and ext isn't in it
                    if active_exts and ext not in active_exts:
                        continue
                try:
                    bucket = preview_bucket(item, mode, self.date_basis_var.get())
                except OSError:
                    continue
                counts[bucket] = counts.get(bucket, 0) + 1
                scanned += 1
                # Update status every 500 files so user sees progress
                if scanned % 500 == 0:
                    self.after(0, lambda s=scanned: self.status_var.set(f"Scanning... {s} files"))

            # Update UI from main thread
            def _update():
                self.preview.delete(*self.preview.get_children())
                for bucket, count in sorted(counts.items()):
                    self.preview.insert("", "end", text=bucket, values=(count,))
                total = sum(counts.values())
                self.status_var.set(f"Ready. {total} files in {len(counts)} groups.")

            self.after(0, _update)

        threading.Thread(target=_scan, daemon=True).start()

    def _search_ext_set(self):
        """Extensions to match, or None for any. Returns (exts_set_or_None, mode).

        mode is 'files' (default), 'folders', or 'any'.
        """
        t = self.search_type_var.get().strip().lower()
        if not t or t == "any":
            return None, "files"
        if t == "folders":
            return None, "folders"
        if t == "files":
            return None, "files"
        for group, exts in EXTENSION_GROUPS.items():
            if group.lower() == t:
                return {e.lower() for e in exts}, "files"
        return {t.lstrip(".")}, "files"

    def _parse_search_terms(self, raw: str):
        """Split 'MDA | moral decline of america' or 'MDA, moral decline' into a list of terms."""
        sep = "|" if "|" in raw else ","
        parts = [p.strip().lower() for p in raw.split(sep) if p.strip()]
        return parts

    def _clear_file_search(self) -> None:
        self.search_name_var.set("")
        self.search_type_var.set("Any")
        self.search_progress.stop()
        self.search_progress.grid_remove()
        self.preview.delete(*self.preview.get_children())
        self.status_var.set("Search cleared.")

    def _run_file_search(self) -> None:
        """Find files/folders by type + name across ALL Source folders, in a background thread.

        Results group by the folder that holds them. Supports multiple search terms
        separated by comma or pipe (OR logic): 'MDA, moral decline of america' finds
        anything matching either term. Type dropdown includes HTML, Folders, Files.
        """
        # Always read directly from listbox — source_var can lag behind
        sources = list(self.source_listbox.get(0, "end"))
        if not sources:
            messagebox.showinfo("Search", "Add at least one Source folder to search in.")
            return
        raw_term = self.search_name_var.get().strip()
        exts, search_mode = self._search_ext_set()
        if not raw_term and exts is None and search_mode not in ("folders",):
            messagebox.showinfo("Search", "Type a name to search for (e.g. MDA) and/or pick a type.")
            return

        def norm(s: str) -> str:
            return s.lower().replace("-", " ").replace("_", " ")

        terms = self._parse_search_terms(raw_term) if raw_term else []
        filename_only = self.search_filename_only_var.get()
        strict = self.search_strict_var.get()

        if strict:
            import re
            patterns = [re.compile(r'\b' + re.escape(t) + r'\b') for t in terms]
            def matches_terms(name: str) -> bool:
                if not patterns:
                    return True
                normed = norm(name)
                return any(p.search(normed) for p in patterns)
        else:
            def matches_terms(name: str) -> bool:
                if not terms:
                    return True
                normed = norm(name)
                return any(t in normed for t in terms)

        self.preview.delete(*self.preview.get_children())
        self.preview.insert("", "end", text="Searching...", values=("",))
        self.status_var.set("Searching...")
        self.search_progress.grid()
        self.search_progress.start(12)

        def worker():
            by_folder: Dict[str, List[str]] = {}
            total = 0
            hit_limit = False

            for root in sources:
                for dirpath, dirs, files in os.walk(root):
                    if hit_limit:
                        break

                    if search_mode == "folders":
                        for d in dirs:
                            if not matches_terms(d):
                                continue
                            by_folder.setdefault(dirpath, []).append(f"[DIR] {d}")
                            total += 1
                            if total >= DEFAULT_PREVIEW_LIMIT:
                                hit_limit = True
                                break
                    else:
                        for fn in files:
                            ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
                            if exts is not None and ext not in exts:
                                continue
                            # Match against filename only OR full path depending on checkbox
                            match_target = fn if filename_only else os.path.join(dirpath, fn)
                            if not matches_terms(match_target):
                                continue
                            by_folder.setdefault(dirpath, []).append(fn)
                            total += 1
                            if total >= DEFAULT_PREVIEW_LIMIT:
                                hit_limit = True
                                break

                if hit_limit:
                    break

            def _update():
                self.search_progress.stop()
                self.search_progress.grid_remove()
                self.preview.delete(*self.preview.get_children())
                for folder in sorted(by_folder):
                    names = sorted(by_folder[folder])
                    parent = self.preview.insert("", "end", text=folder, values=(len(names),), open=False)
                    for nm in names:
                        self.preview.insert(parent, "end", text=nm, values=("",))
                if total:
                    term_display = " | ".join(terms) if terms else "(any name)"
                    msg = f"Found {total} {'folder' if search_mode == 'folders' else 'file'}(s) in {len(by_folder)} folder(s). Terms: {term_display}"
                    if hit_limit:
                        msg += f" Stopped at {DEFAULT_PREVIEW_LIMIT} -- narrow the term."
                else:
                    msg = "No matches. Try a broader name or add more Source folders."
                self.status_var.set(msg)

            self.after(0, _update)

        threading.Thread(target=worker, daemon=True).start()

    def _save_yaml(self) -> None:
        try:
            config = self._current_config()
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        path = filedialog.asksaveasfilename(
            title="Save organize config",
            defaultextension=".yaml",
            filetypes=[("YAML", "*.yaml"), ("YAML", "*.yml"), ("All files", "*.*")],
        )
        if not path:
            return
        Path(path).write_text(dump_yaml(config), encoding="utf-8")
        self.status_var.set(f"Saved {path}")

    def _run_quick(self, simulate: bool) -> None:
        try:
            config = self._current_config()
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        self._start_run(config, simulate, target="quick", status=self.status_var)

    # ----------------------------------------------------------------- #
    # Workflow callbacks
    # ----------------------------------------------------------------- #
    def _wf_add_source(self) -> None:
        selected = filedialog.askdirectory(title="Choose a source folder to clean")
        if selected and selected not in self.wf_source_list.get(0, "end"):
            self.wf_source_list.insert("end", selected)
            self._wf_refresh_yaml_and_preview()

    def _wf_remove_source(self) -> None:
        for index in reversed(self.wf_source_list.curselection()):
            self.wf_source_list.delete(index)
        self._wf_refresh_yaml_and_preview()

    def _wf_add_ignore_folder(self) -> None:
        selected = filedialog.askdirectory(title="Choose a folder to ignore")
        if not selected:
            return
        name = Path(selected).name
        if name and name not in self.wf_ignore_list.get(0, "end"):
            self.wf_ignore_list.insert("end", name)
            self._wf_refresh_yaml_and_preview()

    def _wf_add_ignore_pattern(self) -> None:
        value = self.wf_custom_ext_var.get().strip()
        # reuse the small entry for a quick typed name if it holds text,
        # otherwise prompt via a tiny dialog
        if not value:
            value = _ask_string(self, "Ignore folder name", "Folder name to ignore (e.g. _archive or *backup*):")
        if value and value not in self.wf_ignore_list.get(0, "end"):
            self.wf_ignore_list.insert("end", value)
            self.wf_custom_ext_var.set("")
            self._wf_refresh_yaml_and_preview()

    def _wf_remove_ignore(self) -> None:
        for index in reversed(self.wf_ignore_list.curselection()):
            self.wf_ignore_list.delete(index)
        self._wf_refresh_yaml_and_preview()

    def _wf_scan(self) -> None:
        sources = list(self.wf_source_list.get(0, "end"))
        if not sources:
            messagebox.showinfo(APP_TITLE, "Add at least one source folder first.")
            return
        self.wf_status_var.set("Scanning...")
        self.update_idletasks()
        counts = scan_extensions(sources, self.recursive_var.get(), list(self.wf_ignore_list.get(0, "end")))
        self.scanned_exts = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        self.wf_ext_list.delete(0, "end")
        for ext, count in self.scanned_exts:
            self.wf_ext_list.insert("end", f"{ext}  —  {count} files")
        total = sum(counts.values())
        self.wf_status_var.set(f"Found {len(counts)} file types, {total} files. Tick the ones to move.")

    def _ext_at(self, index: int) -> str:
        return self.scanned_exts[index][0]

    def _wf_select_group(self, group: str) -> None:
        wanted = {e.lower() for e in EXTENSION_GROUPS.get(group, [])}
        if not self.scanned_exts:
            # no scan yet: drop the group straight into a stage selection by
            # showing them in the list so the user can add a stage
            self.scanned_exts = [(e, 0) for e in EXTENSION_GROUPS.get(group, [])]
            self.wf_ext_list.delete(0, "end")
            for ext, _ in self.scanned_exts:
                self.wf_ext_list.insert("end", f"{ext}  —  (not scanned)")
        for index in range(self.wf_ext_list.size()):
            if self._ext_at(index) in wanted:
                self.wf_ext_list.selection_set(index)
        self.wf_stage_name_var.set(f"Move {group}")
        self.wf_status_var.set(f"Selected {group} types. Set a destination and add the stage.")

    def _wf_add_custom_ext(self) -> None:
        for ext in normalize_extensions(self.wf_custom_ext_var.get()):
            if ext == NO_EXTENSION_LABEL:
                continue
            if ext not in [e for e, _ in self.scanned_exts]:
                self.scanned_exts.append((ext, 0))
                self.wf_ext_list.insert("end", f"{ext}  —  (custom)")
            # select it
            for index in range(self.wf_ext_list.size()):
                if self._ext_at(index) == ext:
                    self.wf_ext_list.selection_set(index)
        self.wf_custom_ext_var.set("")

    def _wf_selected_extensions(self) -> List[str]:
        exts: List[str] = []
        for index in self.wf_ext_list.curselection():
            ext = self._ext_at(index)
            if ext != NO_EXTENSION_LABEL:
                exts.append(ext)
        return exts

    def _wf_choose_stage_dest(self) -> None:
        selected = filedialog.askdirectory(title="Choose destination for this stage")
        if selected:
            self.wf_stage_dest_var.set(selected)

    def _wf_add_stage(self) -> None:
        dest = self.wf_stage_dest_var.get().strip()
        if not dest:
            messagebox.showinfo(APP_TITLE, "Set a destination folder for this stage.")
            return
        exts = self._wf_selected_extensions()
        contains = self.wf_stage_contains_var.get().strip()
        if not exts and not contains:
            if not messagebox.askyesno(
                APP_TITLE,
                "No file types or name filter selected. This stage will move EVERY file. Continue?",
            ):
                return
        stage = Stage(
            name=self.wf_stage_name_var.get().strip() or f"Stage {len(self.workflow_stages) + 1}",
            extensions=exts,
            name_contains=contains,
            destination=dest,
            copy_instead=self.wf_stage_copy_var.get(),
        )
        self.workflow_stages.append(stage)
        self._wf_redraw_stages()
        self.wf_stage_contains_var.set("")
        self._wf_refresh_yaml_and_preview()

    def _wf_redraw_stages(self) -> None:
        self.wf_stages_list.delete(0, "end")
        for stage in self.workflow_stages:
            self.wf_stages_list.insert("end", stage.label())

    def _wf_remove_stage(self) -> None:
        selection = list(self.wf_stages_list.curselection())
        for index in reversed(selection):
            del self.workflow_stages[index]
        self._wf_redraw_stages()
        self._wf_refresh_yaml_and_preview()

    def _wf_move_stage(self, delta: int) -> None:
        selection = self.wf_stages_list.curselection()
        if not selection:
            return
        index = selection[0]
        new_index = index + delta
        if 0 <= new_index < len(self.workflow_stages):
            self.workflow_stages[index], self.workflow_stages[new_index] = (
                self.workflow_stages[new_index],
                self.workflow_stages[index],
            )
            self._wf_redraw_stages()
            self.wf_stages_list.selection_set(new_index)
            self._wf_refresh_yaml_and_preview()

    def _wf_clear_stages(self) -> None:
        self.workflow_stages.clear()
        self._wf_redraw_stages()
        self._wf_refresh_yaml_and_preview()

    def _wf_current_workflow(self) -> Workflow:
        return Workflow(
            name=self.wf_name_var.get().strip() or "My workflow",
            sources=list(self.wf_source_list.get(0, "end")),
            ignore_dirs=list(self.wf_ignore_list.get(0, "end")),
            recursive=self.recursive_var.get(),
            stages=list(self.workflow_stages),
        )

    def _wf_refresh_yaml_and_preview(self) -> None:
        workflow = self._wf_current_workflow()
        self.wf_preview.delete(*self.wf_preview.get_children())
        try:
            config = build_workflow_config(workflow)
            self._set_text(self.yaml_widgets["workflow"], dump_yaml(config))
        except Exception as exc:
            self._set_text(self.yaml_widgets["workflow"], f"# {exc}\n")
        # per-stage preview counts (best effort)
        if workflow.sources and workflow.stages:
            for stage in workflow.stages:
                try:
                    count = count_stage_matches(stage, workflow.sources, workflow.recursive, workflow.ignore_dirs)
                except OSError:
                    count = 0
                self.wf_preview.insert("", "end", text=f"{stage.name} -> {stage.destination}", values=(count,))

    def _wf_run(self, simulate: bool) -> None:
        workflow = self._wf_current_workflow()
        try:
            config = build_workflow_config(workflow)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        self._start_run(config, simulate, target="workflow", status=self.wf_status_var)

    # ----- saved workflow management -----
    def _wf_populate_workflow_list(self) -> None:
        starters = [f"★ {name}" for name in starter_workflows()]
        saved = list_saved_workflows()
        self.wf_saved_combo["values"] = starters + saved
        if starters and not self.wf_saved_var.get():
            self.wf_saved_var.set(starters[0])

    def _wf_load_selected(self) -> None:
        choice = self.wf_saved_var.get().strip()
        if not choice:
            return
        try:
            if choice.startswith("★ "):
                workflow = starter_workflows()[choice[2:]]
            else:
                workflow = load_saved_workflow(choice)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not load workflow: {exc}")
            return
        self._wf_apply_workflow(workflow)
        self.wf_status_var.set(f"Loaded '{workflow.name}'. Review, scan, then simulate.")

    def _wf_apply_workflow(self, workflow: Workflow) -> None:
        self.wf_name_var.set(workflow.name)
        self.recursive_var.set(workflow.recursive)
        self.wf_source_list.delete(0, "end")
        for source in workflow.sources:
            self.wf_source_list.insert("end", source)
        self.wf_ignore_list.delete(0, "end")
        for ignore in workflow.ignore_dirs:
            self.wf_ignore_list.insert("end", ignore)
        self.workflow_stages = [Stage.from_dict(s.to_dict()) for s in workflow.stages]
        self._wf_redraw_stages()
        self._wf_refresh_yaml_and_preview()

    def _wf_save(self) -> None:
        workflow = self._wf_current_workflow()
        if not workflow.stages:
            messagebox.showinfo(APP_TITLE, "Add at least one stage before saving.")
            return
        try:
            path = save_workflow(workflow)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not save: {exc}")
            return
        self._wf_populate_workflow_list()
        self.wf_saved_var.set(workflow.name)
        self.wf_status_var.set(f"Saved workflow to {path}")

    def _wf_delete(self) -> None:
        choice = self.wf_saved_var.get().strip()
        if not choice or choice.startswith("★ "):
            messagebox.showinfo(APP_TITLE, "Pick one of your saved workflows to delete (starters can't be deleted).")
            return
        if not messagebox.askyesno(APP_TITLE, f"Delete saved workflow '{choice}'?"):
            return
        delete_saved_workflow(choice)
        self._wf_populate_workflow_list()
        self.wf_saved_var.set("")
        self.wf_status_var.set(f"Deleted '{choice}'.")

    # ----------------------------------------------------------------- #
    # File Intelligence tab
    # ----------------------------------------------------------------- #
    def _build_fileintel_tab(self, root: ttk.Frame) -> None:
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        bar = ttk.Frame(root, padding=(12, 10))
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(1, weight=1)
        bar.columnconfigure(4, weight=1)

        ttk.Label(bar, text="Folder").grid(row=0, column=0, sticky="w")
        ttk.Entry(bar, textvariable=self.fi_folder_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(bar, text="Choose", command=self._fi_choose_folder).grid(row=0, column=2, padx=3)
        ttk.Label(bar, text="FIS service").grid(row=0, column=3, sticky="e", padx=(16, 0))
        ttk.Entry(bar, textvariable=self.fi_url_var, width=24).grid(row=0, column=4, sticky="ew", padx=6)
        ttk.Button(bar, text="Check", command=self._fi_check_health).grid(row=0, column=5, padx=3)
        ttk.Button(bar, text="Scan files", command=self._fi_scan).grid(row=0, column=6, padx=3)

        proc = ttk.Frame(bar)
        proc.grid(row=1, column=0, columnspan=7, sticky="w", pady=(8, 0))
        ttk.Label(proc, text="Renaming process").pack(side="left")
        ttk.Combobox(
            proc,
            textvariable=self.fi_process_var,
            values=app_settings.RENAMING_PROCESSES,
            state="readonly",
            width=18,
        ).pack(side="left", padx=(4, 16))
        ttk.Label(proc, text="Auto-name at/above").pack(side="left")
        ttk.Spinbox(
            proc,
            from_=0,
            to=100,
            increment=5,
            width=4,
            textvariable=self.fi_threshold_var,
            command=self._fi_threshold_changed,
        ).pack(side="left", padx=(4, 2))
        ttk.Label(proc, text="% certainty — below that, a file goes to NLP / review.").pack(side="left")
        self.fi_process_var.trace_add("write", lambda *_: self._fi_process_changed())
        self.fi_threshold_var.trace_add("write", lambda *_: self._fi_threshold_changed())

        controls = ttk.Frame(root, padding=(12, 0))
        controls.grid(row=1, column=0, sticky="ew")
        ttk.Button(controls, text="Select all", command=lambda: self._fi_select("all")).pack(side="left")
        ttk.Button(controls, text="Select none", command=lambda: self._fi_select("none")).pack(side="left", padx=(4, 0))
        ttk.Button(controls, text="Select confident only", command=lambda: self._fi_select("confident")).pack(side="left", padx=(4, 0))
        ttk.Button(controls, text="Apply selected renames", command=self._fi_apply).pack(side="left", padx=(16, 0))
        ttk.Label(controls, text="(tick the box column to choose rows)").pack(side="left", padx=(8, 0))

        table = ttk.Frame(root, padding=(12, 8))
        table.grid(row=2, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)

        columns = ("check", "name", "location", "proposed", "confidence", "status", "source")
        self.fi_tree = ttk.Treeview(table, columns=columns, show="headings", selectmode="none")
        self.fi_tree.heading("check", text="✓")
        self.fi_tree.heading("name", text="Current name")
        self.fi_tree.heading("location", text="Location")
        self.fi_tree.heading("proposed", text="Wants to rename to")
        self.fi_tree.heading("confidence", text="Certainty")
        self.fi_tree.heading("status", text="Status")
        self.fi_tree.heading("source", text="By")
        self.fi_tree.column("check", width=34, anchor="center", stretch=False)
        self.fi_tree.column("name", width=220)
        self.fi_tree.column("location", width=220)
        self.fi_tree.column("proposed", width=260)
        self.fi_tree.column("confidence", width=70, anchor="e", stretch=False)
        self.fi_tree.column("status", width=80, anchor="center", stretch=False)
        self.fi_tree.column("source", width=60, anchor="center", stretch=False)

        vsb = ttk.Scrollbar(table, orient="vertical", command=self.fi_tree.yview)
        self.fi_tree.configure(yscrollcommand=vsb.set)
        self.fi_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        # colour rows by certainty band, like the station would route them
        self.fi_tree.tag_configure("auto", background="#14361f", foreground="#cdeccd")     # high certainty
        self.fi_tree.tag_configure("pending", background="#3a3000", foreground="#f0e6b0")  # medium
        self.fi_tree.tag_configure("low", background="#3a1414", foreground="#f0bcbc")      # low / needs NLP
        self.fi_tree.tag_configure("offline", background="#2a2a2a", foreground="#cccccc")  # offline cleanup
        self.fi_tree.tag_configure("review", background="#4d3300", foreground="#ffd699")   # below threshold -> NLP
        self.fi_tree.bind("<Button-1>", self._fi_on_click)

        out = ttk.Frame(root, padding=(12, 0, 12, 8))
        out.grid(row=3, column=0, sticky="ew")
        out.columnconfigure(0, weight=1)
        ttk.Label(out, textvariable=self.fi_status_var).grid(row=0, column=0, sticky="w")
        fi_output = tk.Text(out, height=5, wrap="word")
        fi_output.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.output_widgets["fileintel"] = fi_output

    def _fi_choose_folder(self) -> None:
        selected = filedialog.askdirectory(title="Choose folder for File Intelligence")
        if selected:
            self.fi_folder_var.set(selected)

    def _fi_client(self) -> "fileintel.FISClient":
        return fileintel.FISClient(self.fi_url_var.get().strip() or fileintel.FIS_DEFAULT_URL)

    def _fi_check_health(self) -> None:
        self.fi_status_var.set("Checking File Intelligence service...")
        self.update_idletasks()

        def worker() -> None:
            connected = self._fi_client().health()
            self.fi_queue.put(("health", connected))

        threading.Thread(target=worker, daemon=True).start()

    def _fi_scan(self) -> None:
        folder = self.fi_folder_var.get().strip()
        if not folder or not Path(folder).expanduser().exists():
            messagebox.showinfo(APP_TITLE, "Choose a folder that exists first.")
            return
        self.fi_tree.delete(*self.fi_tree.get_children())
        self.fi_rows.clear()
        self.fi_checked.clear()
        self.fi_status_var.set("Scanning... (File Intelligence reads each file; this can take a moment)")
        self._set_text(self.output_widgets["fileintel"], "")

        url = self.fi_url_var.get().strip() or fileintel.FIS_DEFAULT_URL
        process = self.fi_process_var.get()
        force_offline = process == "Offline cleanup"

        def worker() -> None:
            client = fileintel.FISClient(url)
            connected = False if force_offline else client.health()
            self.fi_queue.put(("health", connected))
            files = [
                p
                for p in sorted(Path(folder).expanduser().iterdir())
                if p.is_file()
                and not p.name.startswith(".")
                and not p.name.endswith(ledger.LEDGER_EXT)
                and p.name != ledger.FIS_META
            ]
            collected: List[Dict[str, Any]] = []
            for index, path in enumerate(files, 1):
                try:
                    if connected:
                        result = client.classify(str(path))
                        row = fileintel.row_from_fis(result, str(path))
                    else:
                        row = fileintel.offline_proposal(str(path))
                except Exception as exc:  # never let one file kill the scan
                    row = fileintel.offline_proposal(str(path))
                    row["error"] = str(exc)
                collected.append(row)
                self.fi_queue.put(("row", row))
                self.fi_queue.put(("progress", f"{index}/{len(files)} {path.name}"))

            # When real NLP ran, stamp the folder's UUID + NLP fingerprint on the paper.
            if connected:
                proposals = [r["proposed_name"] for r in collected if r["source"] == "fis" and r["proposed_name"]]
                fingerprint = ledger.nlp_fingerprint(proposals)
                try:
                    ledger.record_folder_fingerprint(folder, fingerprint, len(proposals), process)
                except Exception:
                    pass
                self.fi_queue.put(("fingerprint", {"uuid": ledger.folder_uuid(folder), "fp": fingerprint, "n": len(proposals)}))
            self.fi_queue.put(("scan_done", len(files)))

        threading.Thread(target=worker, daemon=True).start()

    def _fi_threshold(self) -> int:
        try:
            return max(0, min(100, int(float(self.fi_threshold_var.get()))))
        except (TypeError, ValueError):
            return self.settings.get("nlp_threshold", 50)

    def _fi_band(self, row: Dict[str, Any], threshold: int) -> str:
        """Below the user's threshold a real FIS proposal is flagged for NLP/review."""
        if row["source"] == "fis" and row["proposed_name"] and row["confidence"] < threshold:
            return "review"
        return fileintel.confidence_band(row["status"], row["confidence"])

    def _fi_status_label(self, row: Dict[str, Any], threshold: int) -> str:
        if row["source"] == "fis" and row["proposed_name"] and row["confidence"] < threshold:
            return "-> NLP"
        return row["status"]

    def _fi_insert_row(self, row: Dict[str, Any]) -> None:
        threshold = self._fi_threshold()
        band = self._fi_band(row, threshold)
        conf = "—" if row["source"] == "offline" else f"{row['confidence']:.0f}"
        iid = self.fi_tree.insert(
            "",
            "end",
            values=(
                "☐",
                row["original_name"],
                str(Path(row["file_path"]).parent),
                row["proposed_name"],
                conf,
                self._fi_status_label(row, threshold),
                row["source"].upper(),
            ),
            tags=(band,),
        )
        row["_iid"] = iid
        self.fi_rows.append(row)

    def _fi_recolor(self) -> None:
        threshold = self._fi_threshold()
        for row in self.fi_rows:
            iid = row.get("_iid")
            if not iid:
                continue
            self.fi_tree.item(iid, tags=(self._fi_band(row, threshold),))
            self.fi_tree.set(iid, "status", self._fi_status_label(row, threshold))

    def _fi_threshold_changed(self) -> None:
        self.settings = app_settings.save_settings({"nlp_threshold": self._fi_threshold()})
        if hasattr(self, "set_threshold_var"):
            self.set_threshold_var.set(str(self.settings["nlp_threshold"]))
        self._fi_recolor()

    def _fi_process_changed(self) -> None:
        self.settings = app_settings.save_settings({"renaming_process": self.fi_process_var.get()})

    def _fi_on_click(self, event: tk.Event) -> None:
        if self.fi_tree.identify_region(event.x, event.y) != "cell":
            return
        if self.fi_tree.identify_column(event.x) != "#1":  # only the check column
            return
        iid = self.fi_tree.identify_row(event.y)
        if not iid:
            return
        self._fi_toggle(iid)

    def _fi_toggle(self, iid: str, force: Optional[bool] = None) -> None:
        checked = iid in self.fi_checked if force is None else not force
        if checked:
            self.fi_checked.discard(iid)
            self.fi_tree.set(iid, "check", "☐")
        else:
            self.fi_checked.add(iid)
            self.fi_tree.set(iid, "check", "☑")

    def _fi_select(self, mode: str) -> None:
        for row in self.fi_rows:
            iid = row["_iid"]
            if mode == "all":
                want = True
            elif mode == "none":
                want = False
            else:  # confident: real FIS proposals at/above your threshold
                want = (
                    row["source"] == "fis"
                    and bool(row["proposed_name"])
                    and row["confidence"] >= self._fi_threshold()
                )
            if want:
                self.fi_checked.add(iid)
                self.fi_tree.set(iid, "check", "☑")
            else:
                self.fi_checked.discard(iid)
                self.fi_tree.set(iid, "check", "☐")

    # TODO(undo): add an "Undo last apply" button. ~20-30 min of work.
    #   Why: Apply renames real files; an undo makes that button safe to press.
    #   How: when this method renames a file, write a ledger event recording the
    #        exact old path -> new path (a "batch_id" = the apply timestamp) via
    #        ledger.LedgerWriter, instead of relying on the background watcher
    #        being on. Then "Undo last apply" reads the most recent batch_id from
    #        the master ledger and reverses each move (new path -> old path),
    #        skipping any whose source no longer exists. The ledger already
    #        stores both ends of every move, so the data model is ready.
    #   Same pattern can give Quick Sort / Workflow runs an undo later.
    def _fi_apply(self) -> None:
        selected = [r for r in self.fi_rows if r["_iid"] in self.fi_checked]
        if not selected:
            messagebox.showinfo(APP_TITLE, "Tick at least one row's box first.")
            return
        offline = any(r["source"] == "offline" for r in selected)
        note = (
            "\n\nNote: some rows are OFFLINE cleanups (File Intelligence was not "
            "reachable). Those rename on disk only — no learning, no database."
            if offline
            else ""
        )
        if not messagebox.askyesno(
            APP_TITLE,
            f"Rename {len(selected)} file(s) to the proposed names?{note}",
        ):
            return
        self.fi_status_var.set("Applying renames...")
        url = self.fi_url_var.get().strip() or fileintel.FIS_DEFAULT_URL

        def worker() -> None:
            client = fileintel.FISClient(url)
            connected = client.health()
            done = 0
            for row in selected:
                name = row["original_name"]
                try:
                    if connected and row["source"] == "fis" and row.get("file_id") is not None:
                        resp = client.approve(row["file_id"])
                        new_name = resp.get("new_name", row["proposed_name"])
                        self.fi_queue.put(("applied", f"FIS renamed: {name} -> {new_name}"))
                    else:
                        new_name = fileintel.apply_local_rename(row["file_path"], row["proposed_name"])
                        if new_name:
                            self.fi_queue.put(("applied", f"Offline renamed: {name} -> {new_name}"))
                        else:
                            self.fi_queue.put(("applied", f"Skipped (missing/empty): {name}"))
                    done += 1
                except Exception as exc:
                    self.fi_queue.put(("applied", f"FAILED {name}: {exc}"))
            self.fi_queue.put(("apply_done", done))

        threading.Thread(target=worker, daemon=True).start()

    def _fi_drain(self) -> None:
        try:
            while True:
                kind, payload = self.fi_queue.get_nowait()
                if kind == "health":
                    self.fi_connected = bool(payload)
                    if self.fi_connected:
                        self.fi_status_var.set(f"Connected to File Intelligence at {self.fi_url_var.get().strip()}.")
                    else:
                        self.fi_status_var.set(
                            "File Intelligence not reachable — using offline name cleanup. "
                            "Start it with: python -m fis api  (in the file-intelligence station)."
                        )
                elif kind == "row":
                    self._fi_insert_row(payload)
                elif kind == "progress":
                    self.fi_status_var.set(f"Scanning... {payload}")
                elif kind == "fingerprint":
                    self._append_text(
                        self.output_widgets["fileintel"],
                        f"Folder UUID: {payload['uuid']}\n"
                        f"NLP fingerprint ({payload['n']} files): {payload['fp']}\n"
                        f"(stamped on this folder's .orgledger paper)\n",
                    )
                elif kind == "scan_done":
                    src = "File Intelligence" if self.fi_connected else "offline cleanup"
                    self.fi_status_var.set(f"Scanned {payload} file(s) via {src}. Tick rows, then Apply.")
                elif kind == "applied":
                    self._append_text(self.output_widgets["fileintel"], payload + "\n")
                elif kind == "apply_done":
                    self.fi_status_var.set(f"Applied {payload} rename(s). Re-scan to refresh the list.")
        except queue.Empty:
            pass
        self.after(150, self._fi_drain)

    # ----------------------------------------------------------------- #
    # Cleanup tab (empty folders + duplicate files)
    # ----------------------------------------------------------------- #
    def _build_cleanup_tab(self, root: ttk.Frame) -> None:
        root.columnconfigure(0, weight=2)
        root.columnconfigure(1, weight=3)
        root.rowconfigure(1, weight=1)

        top = ttk.Frame(root, padding=(12, 10))
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        top.columnconfigure(0, weight=1)

        src = ttk.LabelFrame(top, text="Folders to clean", padding=4)
        src.grid(row=0, column=0, sticky="ew")
        src.columnconfigure(0, weight=1)
        self.cl_source_list = tk.Listbox(src, height=3, selectmode="extended")
        self.cl_source_list.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        src_btns = ttk.Frame(src)
        src_btns.grid(row=0, column=1, sticky="ns")
        ttk.Button(src_btns, text="Add", width=8, command=self._cl_add_source).pack(pady=(0, 2))
        ttk.Button(src_btns, text="Remove", width=8, command=self._cl_remove_source).pack(pady=(0, 2))
        ttk.Button(src_btns, text="Use Quick Sort", width=14,
                   command=self._cl_copy_quick_sources).pack(pady=(0, 2))

        ttk.Checkbutton(
            top, text="Search subfolders for duplicates", variable=self.cl_recursive_var
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        # --- left: empty folders ---
        left = ttk.LabelFrame(root, text="Empty folders", padding=8)
        left.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(0, 4))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        ebtns = ttk.Frame(left)
        ebtns.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(ebtns, text="Find empty folders", command=self._cl_find_empty).pack(side="left")
        ttk.Button(ebtns, text="Check all", width=9,
                   command=lambda: self._cl_empty_set_all(True)).pack(side="left", padx=(6, 0))
        ttk.Button(ebtns, text="Uncheck all", width=10,
                   command=lambda: self._cl_empty_set_all(False)).pack(side="left", padx=(4, 0))
        ttk.Button(ebtns, text="Delete checked", command=self._cl_delete_empty).pack(side="left", padx=(10, 0))

        self.cl_empty_tree = ttk.Treeview(left, columns=("check",), show="tree headings", selectmode="none")
        self.cl_empty_tree.heading("#0", text="Empty folder (nothing real inside, all the way down)")
        self.cl_empty_tree.heading("check", text="✓")
        self.cl_empty_tree.column("check", width=34, anchor="center", stretch=False)
        self.cl_empty_tree.grid(row=1, column=0, sticky="nsew")
        self.cl_empty_tree.bind("<Button-1>", self._cl_empty_click)

        # --- right: duplicates ---
        right = ttk.LabelFrame(root, text="Duplicate files", padding=8)
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(0, 4))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        opts = ttk.Frame(right)
        opts.grid(row=0, column=0, sticky="ew")
        ttk.Label(opts, text="Match").pack(side="left")
        ttk.Combobox(
            opts, textvariable=self.cl_match_var, state="readonly", width=26,
            values=["Exact content (MD5)", "Same name + content (MD5)",
                    "Similar name only — review!"],
        ).pack(side="left", padx=(4, 14))
        ttk.Label(opts, text="Keep").pack(side="left")
        ttk.Combobox(
            opts, textvariable=self.cl_keep_var, state="readonly", width=16,
            values=["Newest modified", "Oldest modified", "Biggest",
                    "First found", "Cleanest name"],
        ).pack(side="left", padx=(4, 0))

        dbtns = ttk.Frame(right)
        dbtns.grid(row=1, column=0, sticky="ew", pady=6)
        ttk.Button(dbtns, text="Find duplicates", command=self._cl_find_dups).pack(side="left")
        ttk.Button(dbtns, text="Select all but keeper", command=self._cl_select_keepers).pack(side="left", padx=(6, 0))
        ttk.Button(dbtns, text="Delete checked", command=self._cl_delete_dups).pack(side="left", padx=(10, 0))

        cols = ("check", "size", "modified", "folder")
        self.cl_dup_tree = ttk.Treeview(right, columns=cols, show="tree headings", selectmode="none")
        self.cl_dup_tree.heading("#0", text="File")
        self.cl_dup_tree.heading("check", text="✓")
        self.cl_dup_tree.heading("size", text="Size")
        self.cl_dup_tree.heading("modified", text="Modified")
        self.cl_dup_tree.heading("folder", text="Folder")
        self.cl_dup_tree.column("check", width=34, anchor="center", stretch=False)
        self.cl_dup_tree.column("size", width=80, anchor="e", stretch=False)
        self.cl_dup_tree.column("modified", width=120, stretch=False)
        self.cl_dup_tree.column("folder", width=320)
        dvsb = ttk.Scrollbar(right, orient="vertical", command=self.cl_dup_tree.yview)
        self.cl_dup_tree.configure(yscrollcommand=dvsb.set)
        self.cl_dup_tree.grid(row=2, column=0, sticky="nsew")
        dvsb.grid(row=2, column=1, sticky="ns")
        self.cl_dup_tree.bind("<Button-1>", self._cl_dup_click)
        self.cl_dup_tree.tag_configure("keeper", foreground="#9fdc9f")

        # --- shared bottom: progress, status, log ---
        bottom = ttk.Frame(root, padding=(12, 0, 12, 8))
        bottom.grid(row=2, column=0, columnspan=2, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        self.cl_progress = ttk.Progressbar(bottom, mode="indeterminate", length=240)
        self.cl_progress.grid(row=0, column=0, sticky="ew")
        self.cl_progress.grid_remove()
        ttk.Label(bottom, textvariable=self.cl_status_var).grid(row=1, column=0, sticky="w")
        cl_output = tk.Text(bottom, height=5, wrap="none")
        cl_output.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        self.output_widgets["cleanup"] = cl_output

    # ----- shared check-column helpers -----
    def _tree_check(self, tree: ttk.Treeview, checked: set, iid: str, state: bool) -> None:
        if state:
            checked.add(iid)
            tree.set(iid, "check", "☑")
        else:
            checked.discard(iid)
            tree.set(iid, "check", "☐")

    def _cl_busy_start(self, message: str, bar: "ttk.Progressbar | None" = None,
                       status: "tk.StringVar | None" = None) -> bool:
        if self.cl_busy:
            return False
        self.cl_busy = True
        (status or self.cl_status_var).set(message)
        bar = bar or self.cl_progress
        bar.grid()
        bar.start(12)
        return True

    def _cl_busy_stop(self) -> None:
        self.cl_busy = False
        for name in ("cl_progress", "snap_progress", "cmp_progress"):
            bar = getattr(self, name, None)
            if bar is not None:
                bar.stop()
                bar.grid_remove()

    def _cl_progress_cb(self, kind: str = "status"):
        """Throttled live-path reporter for worker threads: you can watch the
        scan walk the tree and spot where it's stuck."""
        return throttled(lambda msg: self.cl_queue.put((kind, msg)))

    # ----- cleanup sources -----
    def _cl_sources(self) -> List[str]:
        return list(self.cl_source_list.get(0, "end"))

    def _cl_add_source(self) -> None:
        selected = filedialog.askdirectory(title="Choose a folder to clean")
        if selected and selected not in self._cl_sources():
            self.cl_source_list.insert("end", selected)

    def _cl_remove_source(self) -> None:
        for index in reversed(self.cl_source_list.curselection()):
            self.cl_source_list.delete(index)

    def _cl_copy_quick_sources(self) -> None:
        existing = self._cl_sources()
        for path in self.source_listbox.get(0, "end"):
            if path not in existing:
                self.cl_source_list.insert("end", path)

    # ----- empty folders -----
    def _cl_find_empty(self) -> None:
        sources = self._cl_sources()
        if not sources:
            messagebox.showinfo(APP_TITLE, "Add at least one folder to clean first.")
            return
        if not self._cl_busy_start("Looking for empty folders..."):
            return
        emit = self._cl_progress_cb()

        def worker() -> None:
            try:
                found = find_empty_dirs(sources, progress=emit)
            except Exception as exc:
                found = []
                self.cl_queue.put(("log", f"Empty-folder scan failed: {exc}"))
            self.cl_queue.put(("empty_result", found))

        threading.Thread(target=worker, daemon=True).start()

    def _cl_show_empty(self, dirs: List[str]) -> None:
        self._cl_busy_stop()
        self.cl_empty_tree.delete(*self.cl_empty_tree.get_children())
        self.cl_empty_checked.clear()
        self.cl_empty_dirs = dirs
        for path in dirs:
            iid = self.cl_empty_tree.insert("", "end", text=path, values=("☑",))
            self.cl_empty_checked.add(iid)
        self.cl_status_var.set(
            f"{len(dirs)} empty folder(s) found — all checked. Uncheck any to keep, then Delete checked."
            if dirs else "No empty folders found."
        )

    def _cl_empty_click(self, event: tk.Event) -> None:
        tree = self.cl_empty_tree
        if tree.identify_region(event.x, event.y) != "cell":
            return
        if tree.identify_column(event.x) != "#1":
            return
        iid = tree.identify_row(event.y)
        if iid:
            self._tree_check(tree, self.cl_empty_checked, iid, iid not in self.cl_empty_checked)

    def _cl_empty_set_all(self, state: bool) -> None:
        for iid in self.cl_empty_tree.get_children():
            self._tree_check(self.cl_empty_tree, self.cl_empty_checked, iid, state)

    def _cl_delete_empty(self) -> None:
        tree = self.cl_empty_tree
        paths = [tree.item(iid, "text") for iid in tree.get_children() if iid in self.cl_empty_checked]
        if not paths:
            messagebox.showinfo(APP_TITLE, "Find empty folders first, then leave the ones to delete checked.")
            return
        if not messagebox.askyesno(
            APP_TITLE,
            f"Send {len(paths)} empty folder(s) to the Recycle Bin?\n\n"
            "(Network folders that can't be recycled are deleted permanently.)",
        ):
            return
        if not self._cl_busy_start("Deleting empty folders..."):
            return

        def worker() -> None:
            deleted = skipped = 0
            for path in paths:  # already deepest-first
                try:
                    entries = list(os.scandir(path))
                except OSError:
                    skipped += 1
                    continue
                # a folder only goes if nothing real is left inside right now
                real = [e.name for e in entries if e.is_dir() or not _is_junk_file(e.name)]
                if real:
                    self.cl_queue.put(("log", f"Skipped (no longer empty): {path}"))
                    skipped += 1
                    continue
                try:
                    how = send_to_trash(path)
                    deleted += 1
                    self.cl_queue.put(("log", f"{how}: {path}"))
                except Exception as exc:
                    skipped += 1
                    self.cl_queue.put(("log", f"FAILED {path}: {exc}"))
            self.cl_queue.put(("empty_deleted", (deleted, skipped)))

        threading.Thread(target=worker, daemon=True).start()

    # ----- duplicates -----
    def _cl_match_mode(self) -> str:
        value = self.cl_match_var.get()
        if value.startswith("Same name"):
            return "name+content"
        if value.startswith("Similar name"):
            return "name"
        return "content"

    def _cl_find_dups(self) -> None:
        sources = self._cl_sources()
        if not sources:
            messagebox.showinfo(APP_TITLE, "Add at least one folder to clean first.")
            return
        if not self._cl_busy_start("Scanning for duplicates..."):
            return
        mode = self._cl_match_mode()
        recursive = self.cl_recursive_var.get()
        emit = self._cl_progress_cb()

        def worker() -> None:
            try:
                groups = scan_duplicates(sources, recursive, mode, progress=emit)
            except Exception as exc:
                groups = []
                self.cl_queue.put(("log", f"Duplicate scan failed: {exc}"))
            self.cl_queue.put(("dup_result", groups))

        threading.Thread(target=worker, daemon=True).start()

    def _cl_show_dups(self, groups: List[List[Dict[str, Any]]]) -> None:
        self._cl_busy_stop()
        import datetime as _dt

        tree = self.cl_dup_tree
        tree.delete(*tree.get_children())
        self.cl_dup_checked.clear()
        self.cl_dup_groups = groups
        self.cl_dup_rows = []
        wasted = 0
        for gi, group in enumerate(groups):
            display = normalize_dup_name(group[0]["name"]) or group[0]["name"]
            wasted += sum(f["size"] for f in group[1:])
            parent = tree.insert(
                "", "end", text=f"{display}  —  {len(group)} files",
                values=("", "", "", ""), open=(gi < 20),
            )
            for f in group:
                stamp = _dt.datetime.fromtimestamp(f["mtime"]).strftime("%Y-%m-%d %H:%M")
                iid = tree.insert(
                    parent, "end", text=f["name"],
                    values=("☐", _fmt_size(f["size"]), stamp, f["folder"]),
                )
                f["_iid"] = iid
                f["_group"] = gi
                self.cl_dup_rows.append(f)
        mode_note = "  (name match only — REVIEW before deleting!)" if self._cl_match_mode() == "name" else ""
        self.cl_status_var.set(
            f"{len(groups)} duplicate group(s), {_fmt_size(wasted)} reclaimable{mode_note}. "
            "Pick a Keep rule, then 'Select all but keeper'."
            if groups else "No duplicates found."
        )

    def _cl_dup_click(self, event: tk.Event) -> None:
        tree = self.cl_dup_tree
        if tree.identify_region(event.x, event.y) != "cell":
            return
        if tree.identify_column(event.x) != "#1":
            return
        iid = tree.identify_row(event.y)
        if not iid:
            return
        children = tree.get_children(iid)
        if children:  # group header: toggle the whole group
            any_unchecked = any(c not in self.cl_dup_checked for c in children)
            for c in children:
                self._tree_check(tree, self.cl_dup_checked, c, any_unchecked)
        else:
            self._tree_check(tree, self.cl_dup_checked, iid, iid not in self.cl_dup_checked)

    def _cl_select_keepers(self) -> None:
        if not self.cl_dup_groups:
            messagebox.showinfo(APP_TITLE, "Run 'Find duplicates' first.")
            return
        strategy = self.cl_keep_var.get()
        for group in self.cl_dup_groups:
            rows = [f for f in group if "_iid" in f]
            if not rows:
                continue
            keep = pick_keeper(rows, strategy)
            for i, f in enumerate(rows):
                self._tree_check(self.cl_dup_tree, self.cl_dup_checked, f["_iid"], i != keep)
                self.cl_dup_tree.item(f["_iid"], tags=("keeper",) if i == keep else ())
        checked = len(self.cl_dup_checked)
        size = sum(f["size"] for f in self.cl_dup_rows if f["_iid"] in self.cl_dup_checked)
        self.cl_status_var.set(
            f"Keeping the {strategy.lower()} copy of each group — {checked} file(s) "
            f"({_fmt_size(size)}) selected for deletion. Review, then Delete checked."
        )

    def _cl_delete_dups(self) -> None:
        if not any(f["_iid"] in self.cl_dup_checked for f in self.cl_dup_rows):
            messagebox.showinfo(APP_TITLE, "Nothing is checked. Use 'Select all but keeper' or tick files manually.")
            return
        # never let an entire group disappear — always keep one copy
        targets: List[Dict[str, Any]] = []
        protected = 0
        by_group: Dict[int, List[Dict[str, Any]]] = {}
        for f in self.cl_dup_rows:
            by_group.setdefault(f["_group"], []).append(f)
        for rows in by_group.values():
            checked = [f for f in rows if f["_iid"] in self.cl_dup_checked]
            if checked and len(checked) == len(rows):
                keeper = rows[pick_keeper(rows, self.cl_keep_var.get())]
                checked = [f for f in checked if f is not keeper]
                protected += 1
            targets.extend(checked)
        if not targets:
            messagebox.showinfo(APP_TITLE, "Only whole groups were checked — one copy of each is always kept.")
            return
        note = f"\n({protected} group(s) had every copy checked — one copy is kept anyway.)" if protected else ""
        size = _fmt_size(sum(f["size"] for f in targets))
        if not messagebox.askyesno(
            APP_TITLE,
            f"Send {len(targets)} duplicate file(s) ({size}) to the Recycle Bin?{note}\n\n"
            "(Network files that can't be recycled are deleted permanently.)",
        ):
            return
        if not self._cl_busy_start("Deleting duplicates..."):
            return

        def worker() -> None:
            gone: List[str] = []
            for f in targets:
                try:
                    how = send_to_trash(f["path"])
                    gone.append(f["_iid"])
                    self.cl_queue.put(("log", f"{how}: {f['path']}"))
                except Exception as exc:
                    self.cl_queue.put(("log", f"FAILED {f['path']}: {exc}"))
            self.cl_queue.put(("dups_deleted", gone))

        threading.Thread(target=worker, daemon=True).start()

    def _cl_dups_deleted(self, gone: List[str]) -> None:
        self._cl_busy_stop()
        gone_set = set(gone)
        tree = self.cl_dup_tree
        for iid in gone:
            self.cl_dup_checked.discard(iid)
            if tree.exists(iid):
                tree.delete(iid)
        self.cl_dup_rows = [f for f in self.cl_dup_rows if f["_iid"] not in gone_set]
        # drop group headers that have one (or zero) files left
        for parent in list(tree.get_children()):
            if len(tree.get_children(parent)) <= 1:
                tree.delete(parent)
        self.cl_dup_rows = [f for f in self.cl_dup_rows if tree.exists(f["_iid"])]
        self.cl_status_var.set(f"Deleted {len(gone)} duplicate file(s). Re-run Find duplicates to verify.")

    def _cl_drain(self) -> None:
        try:
            while True:
                kind, payload = self.cl_queue.get_nowait()
                if kind == "status":
                    self.cl_status_var.set(payload)
                elif kind == "log":
                    self._append_text(self.output_widgets["cleanup"], payload + "\n")
                elif kind == "empty_result":
                    self._cl_show_empty(payload)
                elif kind == "empty_deleted":
                    deleted, skipped = payload
                    self._cl_busy_stop()
                    msg = f"Recycled {deleted} empty folder(s)."
                    if skipped:
                        msg += f" Skipped {skipped} (see log)."
                    self.cl_status_var.set(msg)
                    self._cl_find_empty()  # parents may have become empty
                elif kind == "dup_result":
                    self._cl_show_dups(payload)
                elif kind == "dups_deleted":
                    self._cl_dups_deleted(payload)
                elif kind == "snap_status":
                    self.snap_status_var.set(payload)
                elif kind == "cmp_status":
                    self.cmp_status_var.set(payload)
                elif kind == "cmp_result":
                    self._cmp_show(payload)
                elif kind == "cmp_deleted":
                    self._cmp_deleted(payload)
                elif kind == "snap_result":
                    self._snap_show(payload)
                elif kind == "snap_typed":
                    self._snap_show_typed(*payload)
                elif kind == "snap_deleted":
                    deleted, failed = payload
                    self._cl_busy_stop()
                    msg = f"Recycled {deleted} folder(s)."
                    if failed:
                        msg += f" {failed} failed (see Cleanup log)."
                    self.snap_status_var.set(msg)
                    self._snap_take()
        except queue.Empty:
            pass
        self.after(150, self._cl_drain)

    # ----------------------------------------------------------------- #
    # Snapshot tab (folder triage: counts, sizes, EMPTY/conflict flags)
    # ----------------------------------------------------------------- #
    def _build_snapshot_tab(self, root: ttk.Frame) -> None:
        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=1)

        bar = ttk.Frame(root, padding=(12, 10))
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(1, weight=1)
        ttk.Label(bar, text="Root folder").grid(row=0, column=0, sticky="w")
        ttk.Entry(bar, textvariable=self.snap_root_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(bar, text="Choose", command=self._snap_choose).grid(row=0, column=2, padx=3)
        ttk.Button(bar, text="Take snapshot", command=self._snap_take).grid(row=0, column=3, padx=3)

        # find folders dominated by one file type (e.g. >=70% HTML), any depth
        typed = ttk.LabelFrame(root, text="Find folders by content type (searches all subfolders)", padding=(8, 4))
        typed.grid(row=1, column=0, sticky="ew", padx=12)
        ttk.Label(typed, text="Type").pack(side="left")
        self.snap_type_var = tk.StringVar(value="HTML")
        ttk.Combobox(typed, textvariable=self.snap_type_var, width=12,
                     values=list(EXTENSION_GROUPS)).pack(side="left", padx=(4, 12))
        ttk.Label(typed, text="at least").pack(side="left")
        self.snap_pct_var = tk.StringVar(value="70")
        ttk.Spinbox(typed, from_=1, to=100, increment=5, width=4,
                    textvariable=self.snap_pct_var).pack(side="left", padx=(4, 2))
        ttk.Label(typed, text="% of files,").pack(side="left")
        ttk.Label(typed, text="min").pack(side="left", padx=(8, 0))
        self.snap_min_var = tk.StringVar(value="5")
        ttk.Spinbox(typed, from_=1, to=1000, increment=1, width=5,
                    textvariable=self.snap_min_var).pack(side="left", padx=(4, 2))
        ttk.Label(typed, text="files in the folder").pack(side="left")
        ttk.Button(typed, text="Find folders", command=self._snap_find_by_type).pack(side="left", padx=(14, 0))
        ttk.Label(typed, text="(type a custom extension in the box, e.g. py)").pack(side="left", padx=(10, 0))

        controls = ttk.Frame(root, padding=(12, 6))
        controls.grid(row=2, column=0, sticky="ew")
        ttk.Button(controls, text="Check empty + sync-only", command=self._snap_check_empties).pack(side="left")
        ttk.Button(controls, text="Uncheck all", command=lambda: self._snap_set_all(False)).pack(side="left", padx=(4, 0))
        ttk.Button(controls, text="Delete checked", command=self._snap_delete).pack(side="left", padx=(12, 0))
        ttk.Button(controls, text="Open in Explorer", command=self._snap_open).pack(side="left", padx=(12, 0))

        table = ttk.Frame(root, padding=(12, 8))
        table.grid(row=3, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        cols = ("check", "files", "size", "modified", "flag")
        self.snap_tree = ttk.Treeview(table, columns=cols, show="tree headings", selectmode="browse")
        self.snap_tree.heading("#0", text="Folder")
        self.snap_tree.heading("check", text="✓")
        self.snap_tree.heading("files", text="Files")
        self.snap_tree.heading("size", text="Size")
        self.snap_tree.heading("modified", text="Newest file")
        self.snap_tree.heading("flag", text="Flag")
        self.snap_tree.column("check", width=34, anchor="center", stretch=False)
        self.snap_tree.column("files", width=80, anchor="e", stretch=False)
        self.snap_tree.column("size", width=100, anchor="e", stretch=False)
        self.snap_tree.column("modified", width=130, stretch=False)
        self.snap_tree.column("flag", width=160, stretch=False)
        svsb = ttk.Scrollbar(table, orient="vertical", command=self.snap_tree.yview)
        self.snap_tree.configure(yscrollcommand=svsb.set)
        self.snap_tree.grid(row=0, column=0, sticky="nsew")
        svsb.grid(row=0, column=1, sticky="ns")
        self.snap_tree.bind("<Button-1>", self._snap_click)
        self.snap_tree.tag_configure("empty", background="#3a1414", foreground="#f0bcbc")
        self.snap_tree.tag_configure("synconly", background="#3a3000", foreground="#f0e6b0")
        self.snap_tree.tag_configure("conflict", background="#4d3300", foreground="#ffd699")
        self.snap_tree.tag_configure("typematch", background="#14283c", foreground="#bcd6f0")

        self.snap_progress = ttk.Progressbar(root, mode="indeterminate", length=240)
        self.snap_progress.grid(row=4, column=0, sticky="ew", padx=12)
        self.snap_progress.grid_remove()
        ttk.Label(root, textvariable=self.snap_status_var, padding=(12, 0, 12, 8)).grid(row=5, column=0, sticky="w")

    def _snap_choose(self) -> None:
        selected = filedialog.askdirectory(title="Choose the root folder to snapshot")
        if selected:
            self.snap_root_var.set(selected)
            self._snap_take()

    def _snap_take(self) -> None:
        root = self.snap_root_var.get().strip()
        if not root or not Path(root).expanduser().exists():
            messagebox.showinfo(APP_TITLE, "Choose a root folder that exists first.")
            return
        if not self._cl_busy_start(
            "Snapshotting (sizes need a full walk — big trees take a moment)...",
            bar=self.snap_progress, status=self.snap_status_var,
        ):
            return
        emit = self._cl_progress_cb("snap_status")

        def worker() -> None:
            try:
                rows = folder_snapshot(root, progress=emit)
            except Exception as exc:
                rows = []
                self.cl_queue.put(("log", f"Snapshot failed: {exc}"))
            self.cl_queue.put(("snap_result", rows))

        threading.Thread(target=worker, daemon=True).start()

    def _snap_show(self, rows: List[Dict[str, Any]]) -> None:
        self._cl_busy_stop()
        import datetime as _dt

        tree = self.snap_tree
        tree.delete(*tree.get_children())
        self.snap_checked.clear()
        self.snap_rows = rows
        flagged = 0
        for row in rows:
            tags = ()
            if row["flag"] == "EMPTY":
                tags = ("empty",)
            elif row["flag"] == "sync artifacts only":
                tags = ("synconly",)
            elif row["flag"] == "conflict copy":
                tags = ("conflict",)
            if row["flag"]:
                flagged += 1
            stamp = (
                _dt.datetime.fromtimestamp(row["mtime"]).strftime("%Y-%m-%d")
                if row["mtime"] else "—"
            )
            iid = tree.insert(
                "", "end", text=row["name"],
                values=("☐", f"{row['files']:,}", _fmt_size(row["size"]), stamp, row["flag"]),
                tags=tags,
            )
            row["_iid"] = iid
        self.snap_status_var.set(
            f"{len(rows)} folder(s), {flagged} flagged. Red = empty, yellow = sync artifacts only, "
            "orange = conflict copy. Check what should go, then Delete checked."
        )

    def _snap_type_exts(self) -> Tuple[set, str]:
        """Resolve the Type box: a group name (HTML, Code...) or raw
        extensions typed in ('py' or 'py, ipynb')."""
        raw = self.snap_type_var.get().strip()
        for group, exts in EXTENSION_GROUPS.items():
            if group.lower() == raw.lower():
                return set(exts), group
        return set(normalize_extensions(raw)), raw

    def _snap_find_by_type(self) -> None:
        root = self.snap_root_var.get().strip()
        if not root or not Path(root).expanduser().exists():
            messagebox.showinfo(APP_TITLE, "Choose a root folder that exists first.")
            return
        exts, label = self._snap_type_exts()
        if not exts:
            messagebox.showinfo(APP_TITLE, "Pick a type group or enter an extension (e.g. py).")
            return
        try:
            pct = max(1.0, min(100.0, float(self.snap_pct_var.get())))
            min_files = max(1, int(float(self.snap_min_var.get())))
        except (TypeError, ValueError):
            messagebox.showinfo(APP_TITLE, "Percent and min files must be numbers.")
            return
        if not self._cl_busy_start(f"Finding folders that are >= {pct:.0f}% {label}...",
                                   bar=self.snap_progress, status=self.snap_status_var):
            return
        emit = self._cl_progress_cb("snap_status")

        def worker() -> None:
            try:
                results = find_folders_by_type(root, exts, pct, min_files, progress=emit)
            except Exception as exc:
                results = []
                self.cl_queue.put(("log", f"Type search failed: {exc}"))
            self.cl_queue.put(("snap_typed", (results, label, pct)))

        threading.Thread(target=worker, daemon=True).start()

    def _snap_show_typed(self, results: List[Dict[str, Any]], label: str, pct: float) -> None:
        self._cl_busy_stop()
        import datetime as _dt

        tree = self.snap_tree
        tree.delete(*tree.get_children())
        self.snap_checked.clear()
        self.snap_rows = []
        total_size = 0
        for row in results:
            stamp = (_dt.datetime.fromtimestamp(row["mtime"]).strftime("%Y-%m-%d")
                     if row["mtime"] else "—")
            flag = f"{row['pct']:.0f}% {label} ({row['match']}/{row['files']})"
            iid = tree.insert(
                "", "end", text=row["rel"],
                values=("☐", f"{row['files']:,}", _fmt_size(row["size"]), stamp, flag),
                tags=("typematch",),
            )
            entry = {"name": row["rel"], "path": row["path"], "files": row["files"],
                     "size": row["size"], "mtime": row["mtime"], "flag": flag, "_iid": iid}
            self.snap_rows.append(entry)
            total_size += row["size"]
        self.snap_status_var.set(
            f"{len(results)} folder tree(s) are >= {pct:.0f}% {label} ({_fmt_size(total_size)} total). "
            "Topmost qualifying folders only — children aren't listed twice. "
            "Check rows to delete, or select one and Open in Explorer."
            if results else
            f"No folders >= {pct:.0f}% {label} under that root. Lower the percent or the min-files bar."
        )

    def _snap_click(self, event: tk.Event) -> None:
        tree = self.snap_tree
        if tree.identify_region(event.x, event.y) != "cell":
            return
        if tree.identify_column(event.x) != "#1":
            return
        iid = tree.identify_row(event.y)
        if iid:
            self._tree_check(tree, self.snap_checked, iid, iid not in self.snap_checked)

    def _snap_set_all(self, state: bool) -> None:
        for iid in self.snap_tree.get_children():
            self._tree_check(self.snap_tree, self.snap_checked, iid, state)

    def _snap_check_empties(self) -> None:
        for row in self.snap_rows:
            if row["flag"] in ("EMPTY", "sync artifacts only"):
                self._tree_check(self.snap_tree, self.snap_checked, row["_iid"], True)
        self.snap_status_var.set(f"{len(self.snap_checked)} folder(s) checked. Review, then Delete checked.")

    def _snap_open(self) -> None:
        focus = self.snap_tree.focus()
        for row in self.snap_rows:
            if row.get("_iid") == focus:
                try:
                    os.startfile(row["path"])  # noqa: S606 — user-initiated
                except OSError as exc:
                    messagebox.showerror(APP_TITLE, str(exc))
                return

    def _snap_delete(self) -> None:
        targets = [r for r in self.snap_rows if r.get("_iid") in self.snap_checked]
        if not targets:
            messagebox.showinfo(APP_TITLE, "Check at least one folder first.")
            return
        listing = "\n".join(f"  • {r['name']}  ({r['files']:,} files, {_fmt_size(r['size'])})" for r in targets[:12])
        if len(targets) > 12:
            listing += f"\n  ... and {len(targets) - 12} more"
        if not messagebox.askyesno(
            APP_TITLE,
            f"Send {len(targets)} folder(s) AND EVERYTHING IN THEM to the Recycle Bin?\n\n{listing}\n\n"
            "(Network folders that can't be recycled are deleted permanently.)",
        ):
            return
        if not self._cl_busy_start("Deleting folders...", bar=self.snap_progress,
                                   status=self.snap_status_var):
            return

        def worker() -> None:
            deleted = failed = 0
            for row in targets:
                try:
                    how = send_to_trash(row["path"])
                    deleted += 1
                    self.cl_queue.put(("log", f"{how}: {row['path']}"))
                except Exception as exc:
                    failed += 1
                    self.cl_queue.put(("log", f"FAILED {row['path']}: {exc}"))
            self.cl_queue.put(("snap_deleted", (deleted, failed)))

        threading.Thread(target=worker, daemon=True).start()

    # ----------------------------------------------------------------- #
    # Compare tab (empty one drive against its master copy)
    # ----------------------------------------------------------------- #
    _CMP_CATEGORIES = [
        ("identical", "Identical — same place, same content. Safe to delete from the delete side."),
        ("moved", "Moved in master — same content lives elsewhere in the master. Safe to delete."),
        ("different", "Different content — same place but NOT the same file. Review before touching."),
        ("left_only", "Only on delete side — unique. Migrate to the master before deleting."),
        ("right_only", "Only in master — nothing to do."),
    ]

    def _build_compare_tab(self, root: ttk.Frame) -> None:
        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=1)

        bar = ttk.Frame(root, padding=(12, 10))
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(1, weight=1)
        ttk.Label(bar, text="Delete from (the drive you're emptying)").grid(row=0, column=0, sticky="w")
        ttk.Entry(bar, textvariable=self.cmp_left_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(bar, text="Choose", command=lambda: self._cmp_choose(self.cmp_left_var)).grid(row=0, column=2, padx=3)
        ttk.Label(bar, text="Master copy (the one you keep)").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(bar, textvariable=self.cmp_right_var).grid(row=1, column=1, sticky="ew", padx=6, pady=(4, 0))
        ttk.Button(bar, text="Choose", command=lambda: self._cmp_choose(self.cmp_right_var)).grid(row=1, column=2, padx=3, pady=(4, 0))

        opts = ttk.Frame(root, padding=(12, 0))
        opts.grid(row=1, column=0, sticky="ew")
        ttk.Combobox(
            opts, textvariable=self.cmp_verify_var, state="readonly", width=30,
            values=["Verify content (MD5) — safe", "Size only — fast, less safe"],
        ).pack(side="left")
        ttk.Checkbutton(
            opts, text="Find moved files by content", variable=self.cmp_moved_var
        ).pack(side="left", padx=(10, 0))
        ttk.Button(opts, text="Compare", command=self._cmp_run).pack(side="left", padx=(16, 0))

        controls = ttk.Frame(root, padding=(12, 6))
        controls.grid(row=2, column=0, sticky="ew")
        ttk.Button(controls, text="Check all safe (identical + moved)",
                   command=self._cmp_check_safe).pack(side="left")
        ttk.Button(controls, text="Uncheck all", command=self._cmp_uncheck_all).pack(side="left", padx=(4, 0))
        ttk.Button(controls, text="Delete checked from delete side",
                   command=self._cmp_delete).pack(side="left", padx=(12, 0))
        ttk.Button(controls, text="Export CSV", command=self._cmp_export).pack(side="left", padx=(12, 0))

        table = ttk.Frame(root, padding=(12, 0))
        table.grid(row=3, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        cols = ("check", "size", "modified", "note")
        self.cmp_tree = ttk.Treeview(table, columns=cols, show="tree headings", selectmode="none")
        self.cmp_tree.heading("#0", text="File (relative path)")
        self.cmp_tree.heading("check", text="✓")
        self.cmp_tree.heading("size", text="Size")
        self.cmp_tree.heading("modified", text="Modified")
        self.cmp_tree.heading("note", text="Detail")
        self.cmp_tree.column("check", width=34, anchor="center", stretch=False)
        self.cmp_tree.column("size", width=80, anchor="e", stretch=False)
        self.cmp_tree.column("modified", width=120, stretch=False)
        self.cmp_tree.column("note", width=320)
        cvsb = ttk.Scrollbar(table, orient="vertical", command=self.cmp_tree.yview)
        self.cmp_tree.configure(yscrollcommand=cvsb.set)
        self.cmp_tree.grid(row=0, column=0, sticky="nsew")
        cvsb.grid(row=0, column=1, sticky="ns")
        self.cmp_tree.bind("<Button-1>", self._cmp_click)
        self.cmp_tree.tag_configure("safe", foreground="#9fdc9f")
        self.cmp_tree.tag_configure("review", background="#3a3000", foreground="#f0e6b0")
        self.cmp_tree.tag_configure("unique", background="#14283c", foreground="#bcd6f0")

        self.cmp_progress = ttk.Progressbar(root, mode="indeterminate", length=240)
        self.cmp_progress.grid(row=4, column=0, sticky="ew", padx=12)
        self.cmp_progress.grid_remove()
        ttk.Label(root, textvariable=self.cmp_status_var, padding=(12, 0, 12, 8)).grid(row=5, column=0, sticky="w")

    def _cmp_choose(self, var: tk.StringVar) -> None:
        selected = filedialog.askdirectory(title="Choose folder")
        if selected:
            var.set(selected)

    def _cmp_run(self) -> None:
        left = self.cmp_left_var.get().strip()
        right = self.cmp_right_var.get().strip()
        if not left or not Path(left).expanduser().exists():
            messagebox.showinfo(APP_TITLE, "Choose the folder you're emptying (delete side) first.")
            return
        if not right or not Path(right).expanduser().exists():
            messagebox.showinfo(APP_TITLE, "Choose the master copy folder.")
            return
        if os.path.normcase(os.path.normpath(left)) == os.path.normcase(os.path.normpath(right)):
            messagebox.showinfo(APP_TITLE, "Those are the same folder.")
            return
        if not self._cl_busy_start("Comparing trees...", bar=self.cmp_progress,
                                   status=self.cmp_status_var):
            return
        deep = self.cmp_verify_var.get().startswith("Verify")
        match_moved = self.cmp_moved_var.get()
        emit = self._cl_progress_cb("cmp_status")

        def worker() -> None:
            try:
                result = compare_trees(left, right, deep=deep,
                                       match_moved=match_moved, progress=emit)
            except Exception as exc:
                result = {}
                self.cl_queue.put(("log", f"Compare failed: {exc}"))
            self.cl_queue.put(("cmp_result", result))

        threading.Thread(target=worker, daemon=True).start()

    def _cmp_show(self, result: Dict[str, List[Dict[str, Any]]]) -> None:
        self._cl_busy_stop()
        import datetime as _dt

        tree = self.cmp_tree
        tree.delete(*tree.get_children())
        self.cmp_result = result
        self.cmp_entries.clear()
        self.cmp_checkable.clear()
        self.cmp_checked.clear()
        if not result:
            self.cmp_status_var.set("Compare failed — see the Cleanup tab log.")
            return
        tags_for = {"identical": ("safe",), "moved": ("safe",),
                    "different": ("review",), "left_only": ("unique",)}
        for key, label in self._CMP_CATEGORIES:
            items = result.get(key, [])
            size = _fmt_size(sum(f["size"] for f in items))
            parent = tree.insert(
                "", "end", text=f"{label}  ({len(items)} files, {size})",
                values=("", "", "", ""), open=key not in ("right_only",) and bool(items),
            )
            checkable = key in ("identical", "moved")
            for f in items:
                stamp = _dt.datetime.fromtimestamp(f["mtime"]).strftime("%Y-%m-%d %H:%M")
                iid = tree.insert(
                    parent, "end", text=f["rel"],
                    values=("☐" if checkable else "", _fmt_size(f["size"]), stamp, f.get("note", "")),
                    tags=tags_for.get(key, ()),
                )
                self.cmp_entries[iid] = f
                if checkable:
                    self.cmp_checkable.add(iid)
        safe = len(result.get("identical", [])) + len(result.get("moved", []))
        safe_size = _fmt_size(sum(f["size"] for f in result.get("identical", []) + result.get("moved", [])))
        self.cmp_status_var.set(
            f"{safe} file(s) ({safe_size}) already in the master — safe to delete. "
            f"{len(result.get('different', []))} different, {len(result.get('left_only', []))} unique to the delete side."
        )

    def _cmp_click(self, event: tk.Event) -> None:
        tree = self.cmp_tree
        if tree.identify_region(event.x, event.y) != "cell":
            return
        if tree.identify_column(event.x) != "#1":
            return
        iid = tree.identify_row(event.y)
        if not iid:
            return
        children = tree.get_children(iid)
        if children:  # category header: toggle its checkable children
            kids = [c for c in children if c in self.cmp_checkable]
            any_unchecked = any(c not in self.cmp_checked for c in kids)
            for c in kids:
                self._tree_check(tree, self.cmp_checked, c, any_unchecked)
        elif iid in self.cmp_checkable:
            self._tree_check(tree, self.cmp_checked, iid, iid not in self.cmp_checked)

    def _cmp_check_safe(self) -> None:
        for iid in self.cmp_checkable:
            self._tree_check(self.cmp_tree, self.cmp_checked, iid, True)
        size = _fmt_size(sum(self.cmp_entries[i]["size"] for i in self.cmp_checked))
        self.cmp_status_var.set(
            f"{len(self.cmp_checked)} file(s) ({size}) checked — every one verified present in the master. "
            "Review, then Delete checked."
        )

    def _cmp_uncheck_all(self) -> None:
        for iid in list(self.cmp_checked):
            self._tree_check(self.cmp_tree, self.cmp_checked, iid, False)

    def _cmp_delete(self) -> None:
        targets = [(iid, self.cmp_entries[iid]) for iid in self.cmp_checked]
        if not targets:
            messagebox.showinfo(APP_TITLE, "Check files first — 'Check all safe' grabs everything the master already has.")
            return
        size = _fmt_size(sum(f["size"] for _i, f in targets))
        if not messagebox.askyesno(
            APP_TITLE,
            f"Send {len(targets)} file(s) ({size}) from the DELETE side to the Recycle Bin?\n\n"
            "Every one of them was found in the master copy.\n"
            "(Network files that can't be recycled are deleted permanently.)",
        ):
            return
        if not self._cl_busy_start("Deleting matched files...", bar=self.cmp_progress,
                                   status=self.cmp_status_var):
            return

        def worker() -> None:
            gone: List[str] = []
            for iid, f in targets:
                try:
                    how = send_to_trash(f["path"])
                    gone.append(iid)
                    self.cl_queue.put(("log", f"{how}: {f['path']}"))
                except Exception as exc:
                    self.cl_queue.put(("log", f"FAILED {f['path']}: {exc}"))
            self.cl_queue.put(("cmp_deleted", gone))

        threading.Thread(target=worker, daemon=True).start()

    def _cmp_deleted(self, gone: List[str]) -> None:
        self._cl_busy_stop()
        for iid in gone:
            self.cmp_checked.discard(iid)
            self.cmp_checkable.discard(iid)
            self.cmp_entries.pop(iid, None)
            if self.cmp_tree.exists(iid):
                self.cmp_tree.delete(iid)
        self.cmp_status_var.set(
            f"Deleted {len(gone)} file(s) from the delete side. "
            "Run the Cleanup tab's empty-folder pass on it next."
        )

    def _cmp_export(self) -> None:
        if not self.cmp_result:
            messagebox.showinfo(APP_TITLE, "Run a compare first.")
            return
        path = filedialog.asksaveasfilename(
            title="Save compare report",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            writer.writerow(["category", "relative_path", "full_path", "size_bytes", "note"])
            for key, _label in self._CMP_CATEGORIES:
                for f in self.cmp_result.get(key, []):
                    writer.writerow([key, f["rel"], f["path"], f["size"], f.get("note", "")])
        self.cmp_status_var.set(f"Report saved: {path}")

    # ----------------------------------------------------------------- #
    # History (ledger) tab
    # ----------------------------------------------------------------- #
    def _build_history_tab(self, root: ttk.Frame) -> None:
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        intro = ttk.Label(
            root,
            padding=(12, 10),
            text=(
                "Records every new file, rename, move, and delete in the folders below to a "
                "plain-text .orgledger logbook (open it in Notepad++). One master timeline "
                "aggregates them all. The organizer never moves .orgledger files."
            ),
            wraplength=1180,
            justify="left",
        )
        intro.grid(row=0, column=0, sticky="ew")

        top = ttk.Frame(root, padding=(12, 0))
        top.grid(row=1, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)

        roots_frame = ttk.LabelFrame(top, text="Folders to watch", padding=8)
        roots_frame.grid(row=0, column=0, sticky="ew")
        roots_frame.columnconfigure(0, weight=1)
        self.hist_roots_list = tk.Listbox(roots_frame, height=3)
        self.hist_roots_list.grid(row=0, column=0, sticky="ew")
        for r in ledger.default_roots():
            self.hist_roots_list.insert("end", r)
        rbtns = ttk.Frame(roots_frame)
        rbtns.grid(row=0, column=1, sticky="ns", padx=(6, 0))
        ttk.Button(rbtns, text="Add", width=8, command=self._hist_add_root).pack(fill="x")
        ttk.Button(rbtns, text="Remove", width=8, command=self._hist_remove_root).pack(fill="x", pady=(4, 0))

        ctrl = ttk.Frame(top, padding=(0, 8))
        ctrl.grid(row=1, column=0, sticky="ew")
        ttk.Label(ctrl, text="Check every (sec)").pack(side="left")
        ttk.Entry(ctrl, textvariable=self.hist_interval_var, width=5).pack(side="left", padx=(4, 12))
        self.hist_start_btn = ttk.Button(ctrl, text="Start watching", command=self._hist_start)
        self.hist_start_btn.pack(side="left")
        self.hist_stop_btn = ttk.Button(ctrl, text="Stop", command=self._hist_stop, state="disabled")
        self.hist_stop_btn.pack(side="left", padx=(4, 12))
        ttk.Button(ctrl, text="Run at login", command=self._hist_install_startup).pack(side="left")
        ttk.Button(ctrl, text="Remove from login", command=self._hist_uninstall_startup).pack(side="left", padx=(4, 12))
        ttk.Button(ctrl, text="Open ledger", command=self._hist_open_ledger).pack(side="left")
        ttk.Button(ctrl, text="Refresh", command=self._hist_refresh).pack(side="left", padx=(4, 0))

        table = ttk.Frame(root, padding=(12, 0, 12, 4))
        table.grid(row=2, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        columns = ("ts", "event", "file", "from", "to", "certain")
        self.hist_tree = ttk.Treeview(table, columns=columns, show="headings")
        for col, text, width, anchor in (
            ("ts", "When (UTC)", 150, "w"),
            ("event", "Event", 70, "center"),
            ("file", "File", 220, "w"),
            ("from", "From", 240, "w"),
            ("to", "To", 240, "w"),
            ("certain", "Sure?", 60, "center"),
        ):
            self.hist_tree.heading(col, text=text)
            self.hist_tree.column(col, width=width, anchor=anchor)
        vsb = ttk.Scrollbar(table, orient="vertical", command=self.hist_tree.yview)
        self.hist_tree.configure(yscrollcommand=vsb.set)
        self.hist_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.hist_tree.tag_configure("inferred", background="#3a3000", foreground="#f0e6b0")
        self.hist_tree.tag_configure("delete", background="#3a1414", foreground="#f0bcbc")

        ttk.Label(root, textvariable=self.hist_status_var, padding=(12, 0, 12, 8)).grid(row=3, column=0, sticky="w")

        self._hist_refresh()
        self.after(2500, self._hist_auto_refresh)

    def _hist_roots(self) -> List[str]:
        return list(self.hist_roots_list.get(0, "end"))

    def _hist_add_root(self) -> None:
        selected = filedialog.askdirectory(title="Choose a folder to watch")
        if selected and selected not in self._hist_roots():
            self.hist_roots_list.insert("end", selected)

    def _hist_remove_root(self) -> None:
        for index in reversed(self.hist_roots_list.curselection()):
            self.hist_roots_list.delete(index)

    def _hist_interval(self) -> float:
        try:
            return max(1.0, float(self.hist_interval_var.get()))
        except ValueError:
            return ledger.DEFAULT_INTERVAL

    def _hist_start(self) -> None:
        roots = self._hist_roots()
        if not roots:
            messagebox.showinfo(APP_TITLE, "Add at least one folder to watch.")
            return
        if self.hist_watcher_thread and self.hist_watcher_thread.is_alive():
            return
        self.hist_stop_event = threading.Event()
        watcher = ledger.LedgerWatcher(roots, interval=self._hist_interval())

        def run() -> None:
            watcher.run_forever(stop_event=self.hist_stop_event)

        self.hist_watcher_thread = threading.Thread(target=run, daemon=True)
        self.hist_watcher_thread.start()
        self.hist_start_btn.configure(state="disabled")
        self.hist_stop_btn.configure(state="normal")
        self.hist_status_var.set(
            f"Watching {len(roots)} folder(s) while this window is open. "
            "Use 'Run at login' for always-on."
        )

    def _hist_stop(self) -> None:
        if self.hist_stop_event:
            self.hist_stop_event.set()
        self.hist_start_btn.configure(state="normal")
        self.hist_stop_btn.configure(state="disabled")
        self.hist_status_var.set("History watcher stopped (in-app). Login watcher, if installed, still runs.")

    def _hist_install_startup(self) -> None:
        roots = self._hist_roots()
        if not roots:
            messagebox.showinfo(APP_TITLE, "Add at least one folder to watch.")
            return
        try:
            bat = ledger.install_startup(roots, self._hist_interval(), python_exe=sys.executable)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not install startup watcher: {exc}")
            return
        self.hist_status_var.set(f"Always-on watcher installed at login: {bat}")
        messagebox.showinfo(APP_TITLE, f"It will start watching automatically each time you log in.\n\n{bat}")

    def _hist_uninstall_startup(self) -> None:
        removed = ledger.uninstall_startup()
        self.hist_status_var.set("Removed from login startup." if removed else "No login watcher was installed.")

    def _hist_open_ledger(self) -> None:
        ledger.open_in_editor(ledger.master_ledger_path())

    def _hist_refresh(self) -> None:
        events = ledger.read_events(ledger.master_ledger_path(), limit=500)
        self.hist_tree.delete(*self.hist_tree.get_children())
        for ev in reversed(events):  # newest first
            tags = ()
            if ev.get("event") == "delete":
                tags = ("delete",)
            elif not ev.get("certain", True):
                tags = ("inferred",)
            self.hist_tree.insert(
                "",
                "end",
                values=(
                    ev.get("ts", ""),
                    ev.get("event", ""),
                    ev.get("new_name") or ev.get("file", ""),
                    ev.get("from") or "",
                    ev.get("to") or "",
                    "yes" if ev.get("certain", True) else "guess",
                ),
                tags=tags,
            )

    def _hist_auto_refresh(self) -> None:
        if self.hist_watcher_thread and self.hist_watcher_thread.is_alive():
            self._hist_refresh()
        self.after(2500, self._hist_auto_refresh)

    # ----------------------------------------------------------------- #
    # Settings tab
    # ----------------------------------------------------------------- #
    def _build_settings_tab(self, root: ttk.Frame) -> None:
        self.set_threshold_var = tk.StringVar(value=str(self.settings["nlp_threshold"]))
        self.set_autoapply_var = tk.StringVar(value=str(self.settings["auto_apply_threshold"]))
        self.set_process_var = tk.StringVar(value=self.settings["renaming_process"])
        self.set_status_var = tk.StringVar(value=f"Settings file: {app_settings.settings_path()}")

        frame = ttk.Frame(root, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Renaming settings", font=("", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            frame,
            wraplength=760,
            justify="left",
            text=(
                "These control how the File Intelligence tab names files. The NLP threshold is the "
                "saving grace: anything the engine is less sure about than this gets flagged to go to "
                "NLP / review instead of being auto-named. Lower it (e.g. to 30) if too much is being "
                "held back; raise it if you want only very confident names applied."
            ),
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 14))

        ttk.Label(frame, text="NLP / review threshold (%)").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Spinbox(frame, from_=0, to=100, increment=5, width=6, textvariable=self.set_threshold_var).grid(row=2, column=1, sticky="w", pady=4)
        ttk.Label(frame, text="Below this certainty -> goes to NLP / review.").grid(row=2, column=2, sticky="w", padx=(8, 0))

        ttk.Label(frame, text="Auto-apply threshold (%)").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Spinbox(frame, from_=0, to=100, increment=5, width=6, textvariable=self.set_autoapply_var).grid(row=3, column=1, sticky="w", pady=4)
        ttk.Label(frame, text="At/above this, a name is considered safe to apply.").grid(row=3, column=2, sticky="w", padx=(8, 0))

        ttk.Label(frame, text="Default renaming process").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Combobox(frame, textvariable=self.set_process_var, values=app_settings.RENAMING_PROCESSES, state="readonly", width=18).grid(row=4, column=1, columnspan=2, sticky="w", pady=4)

        ttk.Button(frame, text="Save settings", command=self._settings_save).grid(row=5, column=0, sticky="w", pady=(14, 6))
        ttk.Label(frame, textvariable=self.set_status_var).grid(row=6, column=0, columnspan=3, sticky="w")

    def _settings_save(self) -> None:
        try:
            updates = {
                "nlp_threshold": int(float(self.set_threshold_var.get())),
                "auto_apply_threshold": int(float(self.set_autoapply_var.get())),
                "renaming_process": self.set_process_var.get(),
            }
        except (TypeError, ValueError):
            messagebox.showerror(APP_TITLE, "Thresholds must be numbers between 0 and 100.")
            return
        self.settings = app_settings.save_settings(updates)
        # reflect saved values back into both tabs
        self.set_threshold_var.set(str(self.settings["nlp_threshold"]))
        self.set_autoapply_var.set(str(self.settings["auto_apply_threshold"]))
        self.fi_threshold_var.set(str(self.settings["nlp_threshold"]))
        self.fi_process_var.set(self.settings["renaming_process"])
        self._fi_recolor()
        self.set_status_var.set(f"Saved. Settings file: {app_settings.settings_path()}")

    # ----------------------------------------------------------------- #
    # Shared run machinery
    # ----------------------------------------------------------------- #
    def _start_run(self, config: Dict[str, Any], simulate: bool, target: str, status: tk.StringVar) -> None:
        if not simulate and not self._last_sim_success:
            ok = messagebox.askyesno(
                APP_TITLE,
                "You haven't simulated yet. Run anyway?",
            )
            if not ok:
                return
        yaml_text = dump_yaml(config)
        self._set_text(self.yaml_widgets[target], yaml_text)
        self._set_text(self.output_widgets[target], "")
        status.set("Running simulation..." if simulate else "Organizing for real...")
        thread = threading.Thread(target=self._run_worker, args=(yaml_text, simulate, target), daemon=True)
        thread.start()

    def _run_worker(self, yaml_text: str, simulate: bool, target: str) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as tmp:
            tmp.write(yaml_text)
            config_path = tmp.name
        command = [
            sys.executable,
            "-m",
            "organize",
            "sim" if simulate else "run",
            "-F",
            "jsonl",
            config_path,
        ]
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            proc = subprocess.run(
                command,
                cwd=str(Path(__file__).resolve().parents[1]),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            output = proc.stdout
            if proc.stderr:
                output += "\n[stderr]\n" + proc.stderr
            output += f"\n[exit code {proc.returncode}]\n"
            self.output_queue.put((target, output))
        except Exception as exc:
            self.output_queue.put((target, f"{exc}\n"))
        finally:
            try:
                Path(config_path).unlink()
            except OSError:
                pass

    def _drain_output_queue(self) -> None:
        try:
            while True:
                target, output = self.output_queue.get_nowait()
                widget = self.output_widgets.get(target)
                if widget is not None:
                    self._append_text(widget, output)

                # Parse JSONL output for result summary
                success = 0
                errors = 0
                was_sim = False
                for line in output.splitlines():
                    try:
                        data = json.loads(line)
                        if data.get("type") == "START":
                            was_sim = data.get("simulate", False)
                        elif data.get("type") == "REPORT":
                            success = data.get("success_count", 0)
                            errors = data.get("error_count", 0)
                    except (json.JSONDecodeError, TypeError):
                        continue

                if was_sim:
                    self._last_sim_success = errors == 0 and success > 0

                # Build clear status message
                action = "Simulation" if was_sim else "Organize"
                msg = f"{action} done: {success} files processed"
                if errors:
                    msg += f", {errors} errors"
                if was_sim and success > 0:
                    msg += " — click 'Organize for real' to apply."
                elif not was_sim and success > 0:
                    msg += " — files moved!"

                if target == "quick":
                    self.status_var.set(msg)
                    if not was_sim:
                        self._build_preview()
                else:
                    self.wf_status_var.set(msg)
                    if not was_sim:
                        self._wf_refresh_yaml_and_preview()
        except queue.Empty:
            pass
        self.after(150, self._drain_output_queue)

    @staticmethod
    def _set_text(widget: tk.Text, value: str) -> None:
        widget.delete("1.0", "end")
        widget.insert("1.0", value)

    @staticmethod
    def _append_text(widget: tk.Text, value: str) -> None:
        widget.insert("end", value)
        widget.see("end")


def _ask_string(parent: tk.Misc, title: str, prompt: str) -> str:
    """Tiny modal text prompt (avoids importing simpledialog at module load)."""
    from tkinter import simpledialog

    return simpledialog.askstring(title, prompt, parent=parent) or ""


def _self_test() -> None:
    # Quick Sort modes still build
    for mode in ["Type", "Extension", "Date", "Alphabet", "Size", "Custom", "Rules"]:
        config = build_rule_config(
            source_paths=[str(Path.cwd())],
            destination=str(Path.cwd() / "_organized"),
            mode=mode,
            recursive=False,
            apply_rules=True,
            rule_mode="AND",
            custom_rules=[RuleRow("Extension", "contains", "xlsx", "Excel")] if mode in {"Custom", "Rules"} else [],
            date_basis="Modified",
        )
        print(f"OK quick {mode}: {len(config['rules'])} rule(s)")

    # Workflow with ignore folders, multi-stage, custom extensions
    workflow = Workflow(
        name="self-test",
        sources=[str(Path.cwd())],
        ignore_dirs=["node_modules", "_archive"],
        recursive=True,
        stages=[
            Stage("Excel", list(EXTENSION_GROUPS["Excel"]), "", str(Path.cwd() / "out" / "Excel")),
            Stage("Reports", ["pdf"], "report", str(Path.cwd() / "out" / "Reports")),
        ],
    )
    config = build_workflow_config(workflow)
    text = dump_yaml(config)
    assert "exclude_dirs" in text, "ignore folders missing from config"
    assert "node_modules" in text
    assert config["rules"][0]["filters"][0]["extension"] == EXTENSION_GROUPS["Excel"]
    print(f"OK workflow: {len(config['rules'])} stage rule(s), ignore-dirs wired")

    # Starters round-trip through to_dict/from_dict
    for name, wf in starter_workflows().items():
        restored = Workflow.from_dict(wf.to_dict())
        build_workflow_config(restored)
        print(f"OK starter '{name}': {len(restored.stages)} stage(s)")

    # File Intelligence helpers
    off = fileintel.offline_proposal(str(Path.cwd() / "My Big Report (final).PDF"))
    assert off["proposed_name"] == "my_big_report_final.pdf", off["proposed_name"]
    assert off["source"] == "offline" and off["confidence"] == 0.0
    fis_row = fileintel.row_from_fis(
        {"original_name": "x.pdf", "proposed_name": "tax_FIN.AUDIT_42.pdf", "confidence": 91.0, "status": "auto", "file_id": 7},
        str(Path.cwd() / "x.pdf"),
    )
    assert fis_row["file_id"] == 7 and fileintel.confidence_band(fis_row["status"], fis_row["confidence"]) == "auto"
    assert fileintel.confidence_band("pending", 60) == "pending"
    assert fileintel.confidence_band("kickout", 20) == "low"
    assert fileintel.FISClient("http://localhost:8420/").base == "http://localhost:8420"
    print("OK fileintel: offline cleanup, FIS row mapping, certainty bands")

    # Cleanup: duplicate-name normalizer + keeper strategies
    assert normalize_dup_name("Report (3).pdf") == "report"
    assert normalize_dup_name("report - Copy (2).PDF") == "report"
    assert normalize_dup_name("Report_v12.pdf") == "report"
    assert normalize_dup_name("My Report version 3.docx") == "my report"
    assert normalize_dup_name("Photocopy.pdf") == "photocopy"  # 'copy' inside a word survives
    assert normalize_dup_name("Track 2.mp3") == "track 2"      # bare numbers survive
    assert normalize_dup_name("v2.pdf") == "v2"                # never normalize to nothing
    group = [
        {"name": "a (1).txt", "path": "x/a (1).txt", "size": 5, "mtime": 200.0},
        {"name": "a.txt", "path": "x/a.txt", "size": 9, "mtime": 100.0},
    ]
    assert pick_keeper(group, "First found") == 0
    assert pick_keeper(group, "Biggest") == 1
    assert pick_keeper(group, "Newest modified") == 0
    assert pick_keeper(group, "Oldest modified") == 1
    assert pick_keeper(group, "Cleanest name") == 1

    # Cleanup: empty-folder finder + MD5 duplicate scan on a scratch tree
    with tempfile.TemporaryDirectory() as td:
        deep = Path(td) / "a" / "b"
        deep.mkdir(parents=True)
        (deep / "Thumbs.db").write_text("junk")          # junk doesn't block emptiness
        full = Path(td) / "full"
        full.mkdir()
        (full / "doc.txt").write_text("hello world")
        (full / "doc (1).txt").write_text("hello world")  # exact dupe
        (full / "other.txt").write_text("different")
        found = {Path(p).name for p in find_empty_dirs([td])}
        assert found == {"a", "b"}, found
        dupes = scan_duplicates([td], recursive=True, mode="content")
        assert len(dupes) == 1 and len(dupes[0]) == 2, dupes
        assert {Path(f["path"]).name for f in dupes[0]} == {"doc.txt", "doc (1).txt"}
        dupes_nc = scan_duplicates([td], recursive=True, mode="name+content")
        assert len(dupes_nc) == 1 and len(dupes_nc[0]) == 2
    print("OK cleanup: name normalize, keeper pick, empty dirs, MD5 dupes")

    # Snapshot: flags for empty / sync-only / conflict folders
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "Empty One").mkdir()
        sync = Path(td) / "Old Vault Conflict Copy" / ".stfolder"
        sync.mkdir(parents=True)
        (sync / "marker").write_text("")
        real = Path(td) / "Active"
        real.mkdir()
        (real / "notes.md").write_text("content")
        flags = {r["name"]: r["flag"] for r in folder_snapshot(td)}
        assert flags["Empty One"] == "EMPTY"
        assert flags["Old Vault Conflict Copy"] == "sync artifacts only"
        assert flags["Active"] == ""
    print("OK snapshot: empty/sync/conflict flags")

    # Compare: identical / different / moved / only-left buckets
    with tempfile.TemporaryDirectory() as td:
        left = Path(td) / "left"
        right = Path(td) / "right"
        (left / "sub").mkdir(parents=True)
        (right / "sub").mkdir(parents=True)
        (left / "same.txt").write_text("alpha")
        (right / "same.txt").write_text("alpha")
        (left / "diff.txt").write_text("left version")
        (right / "diff.txt").write_text("right version!")
        (left / "only_left.txt").write_text("unique")
        (right / "only_right.txt").write_text("master only")
        (left / "moved.txt").write_text("payload")
        (right / "sub" / "relocated.txt").write_text("payload")
        result = compare_trees(str(left), str(right), deep=True, match_moved=True)
        assert [f["rel"] for f in result["identical"]] == ["same.txt"]
        assert [f["rel"] for f in result["different"]] == ["diff.txt"]
        assert [f["rel"] for f in result["left_only"]] == ["only_left.txt"]
        assert {f["rel"] for f in result["right_only"]} == {"only_right.txt", os.path.join("sub", "relocated.txt")}
        assert [f["rel"] for f in result["moved"]] == ["moved.txt"]
        assert result["moved"][0]["match"] == os.path.join("sub", "relocated.txt")
        # size-only mode never hashes
        fast = compare_trees(str(left), str(right), deep=False, match_moved=False)
        assert [f["rel"] for f in fast["identical"]] == ["same.txt"]
        assert {f["rel"] for f in fast["left_only"]} == {"only_left.txt", "moved.txt"}
    print("OK compare: identical/different/moved/only-left buckets")

    # Folders-by-type: threshold, min-files guard, topmost-only suppression
    with tempfile.TemporaryDirectory() as td:
        heavy = Path(td) / "html_dump"          # 80% html, should hit
        sub = heavy / "more_html"               # also >=70% but inside a hit -> suppressed
        sub.mkdir(parents=True)
        for i in range(6):
            (heavy / f"page{i}.html").write_text("<html>")
        (heavy / "notes.txt").write_text("x")
        for i in range(4):
            (sub / f"deep{i}.html").write_text("<html>")
        (sub / "readme.md").write_text("x")
        mixed = Path(td) / "code"               # 10% html, should not hit
        mixed.mkdir()
        (mixed / "one.html").write_text("<html>")
        for i in range(9):
            (mixed / f"s{i}.py").write_text("pass")
        tiny = Path(td) / "tiny"                # 100% html but 1 file < min_files
        tiny.mkdir()
        (tiny / "solo.html").write_text("<html>")
        hits = find_folders_by_type(td, {"html", "htm"}, 70.0, min_files=5)
        names = [Path(h["path"]).name for h in hits]
        assert names == ["html_dump"], names    # topmost only, mixed/tiny excluded
        assert hits[0]["match"] == 10 and hits[0]["files"] == 12
        assert abs(hits[0]["pct"] - 83.3) < 1
    print("OK folders-by-type: threshold, min-files, topmost suppression")

    # Settings: clamp + normalize the user-controlled NLP threshold
    assert app_settings._normalize({"nlp_threshold": 250})["nlp_threshold"] == 100
    assert app_settings._normalize({"nlp_threshold": "30"})["nlp_threshold"] == 30
    assert app_settings._normalize({"renaming_process": "bogus"})["renaming_process"] == "File Intelligence"
    # below-threshold FIS rows route to NLP/review; at/above pass through
    low = fileintel.row_from_fis({"proposed_name": "x_FIN_3.pdf", "confidence": 22.0, "status": "kickout", "file_id": 3}, "x.pdf")
    assert low["confidence"] < 30 and fileintel.confidence_band(low["status"], low["confidence"]) == "low"
    print("OK settings: threshold clamp + NLP-review routing")


def main() -> None:
    if "--self-test" in sys.argv:
        _self_test()
        return
    app = OrganizeGui()
    app.mainloop()


if __name__ == "__main__":
    main()
