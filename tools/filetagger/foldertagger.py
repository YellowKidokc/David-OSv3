#!/usr/bin/env python3
"""foldertagger - leave a small memory marker inside every folder.

This is the folder-level companion to filetagger.py. It walks a root folder and
writes a sidecar-like manifest inside each scanned folder:

    .folder.fmeta

The manifest is meant to travel with the folder. On future scans, the existing
folder_id is preserved. If the folder moved, the marker records the previous
path and the current path.

Usage:
  python foldertagger.py "D:\\Some\\Folder"
  python foldertagger.py "D:\\Some\\Folder" --dry-run
  python foldertagger.py "D:\\Some\\Folder" --max-depth 3
  python foldertagger.py "D:\\Some\\Folder" --force
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import re
import uuid
from collections import Counter
from pathlib import Path


MARKER_NAME = ".folder.fmeta"
SAMPLE_BYTES = 2048
MAX_OUTLINE_ITEMS = 40
MAX_TAGS = 8

TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".rst", ".csv", ".tsv", ".log", ".json",
    ".yaml", ".yml", ".html", ".htm", ".xml", ".ini", ".cfg", ".py", ".js",
    ".ts", ".css", ".bat", ".ps1", ".sh", ".sql",
}

SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "node_modules", ".obsidian",
    ".next", "dist", "build",
}

SKIP_NAMES = {
    "thumbs.db", "desktop.ini", ".ds_store", MARKER_NAME.lower(),
}

STOP = set(
    "the a an and or of to in is it for on with as by at from this that be are "
    "was were will would can could should i you he she they we not no but if then "
    "else your our their his her its my me us them which who what when where how "
    "why all any some more most other into over under out up down off than too "
    "very just have has had do does did been being about also such only there here"
    .split()
)


def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def rel_depth(root: Path, path: Path) -> int:
    try:
        return len(path.relative_to(root).parts)
    except ValueError:
        return 0


def read_existing_marker(path: Path) -> dict[str, str]:
    marker = path / MARKER_NAME
    if not marker.exists():
        return {}
    out: dict[str, str] = {}
    try:
        for line in marker.read_text(encoding="utf-8", errors="ignore").splitlines():
            if ":" not in line or line.startswith("#"):
                continue
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    except OSError:
        return {}
    return out


def folder_fingerprint(path: Path) -> str:
    """A stable-ish fallback identity from visible immediate contents."""
    names: list[str] = []
    try:
        for child in sorted(path.iterdir(), key=lambda p: p.name.lower()):
            if child.name == MARKER_NAME:
                continue
            kind = "d" if child.is_dir() else "f"
            names.append(f"{kind}:{child.name.lower()}")
    except OSError:
        pass
    digest = hashlib.sha1("\n".join(names).encode("utf-8", errors="ignore")).hexdigest()
    return digest[:16]


def sample_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:SAMPLE_BYTES]
    except OSError:
        return ""


def extract_tags(path: Path, child_dirs: list[Path], child_files: list[Path]) -> list[str]:
    text_parts = [path.name.replace("-", " ").replace("_", " ")]
    text_parts.extend(p.name.replace("-", " ").replace("_", " ") for p in child_dirs[:20])
    text_parts.extend(p.stem.replace("-", " ").replace("_", " ") for p in child_files[:30])

    for file_path in child_files[:12]:
        if file_path.suffix.lower() in TEXT_EXTS:
            text_parts.append(sample_text(file_path))

    words = re.findall(r"[a-z][a-z0-9]{2,}", " ".join(text_parts).lower())
    counts: Counter[str] = Counter(w for w in words if w not in STOP)
    return [word for word, _ in counts.most_common(MAX_TAGS)] or ["untagged"]


def summarize_folder(path: Path) -> tuple[list[Path], list[Path], Counter[str], int]:
    child_dirs: list[Path] = []
    child_files: list[Path] = []
    ext_counts: Counter[str] = Counter()
    total_bytes = 0

    try:
        children = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError:
        return child_dirs, child_files, ext_counts, total_bytes

    for child in children:
        if child.name == MARKER_NAME:
            continue
        if child.is_dir():
            child_dirs.append(child)
            continue
        if child.name.lower() in SKIP_NAMES or child.name.endswith(".fmeta"):
            continue
        child_files.append(child)
        ext_counts[child.suffix.lower() or "[no extension]"] += 1
        try:
            total_bytes += child.stat().st_size
        except OSError:
            pass

    return child_dirs, child_files, ext_counts, total_bytes


def marker_body(path: Path, root: Path, force_new_id: bool = False) -> str:
    existing = read_existing_marker(path)
    previous_path = existing.get("current_path", "")
    folder_id = "" if force_new_id else existing.get("folder_id", "")
    if not folder_id:
        folder_id = str(uuid.uuid4())

    child_dirs, child_files, ext_counts, total_bytes = summarize_folder(path)
    tags = extract_tags(path, child_dirs, child_files)
    current_path = str(path.resolve())
    moved = bool(previous_path and previous_path.lower() != current_path.lower())

    outline: list[str] = []
    for child in child_dirs[:MAX_OUTLINE_ITEMS]:
        outline.append(f"- [dir] {child.name}")
    remaining = MAX_OUTLINE_ITEMS - len(outline)
    for child in child_files[:max(0, remaining)]:
        outline.append(f"- [file] {child.name}")
    if len(child_dirs) + len(child_files) > MAX_OUTLINE_ITEMS:
        outline.append(f"- ... {len(child_dirs) + len(child_files) - MAX_OUTLINE_ITEMS} more")

    ext_summary = ", ".join(f"{ext}={count}" for ext, count in ext_counts.most_common(12))
    if not ext_summary:
        ext_summary = "none"

    first_scanned = existing.get("first_scanned", now())
    previous_paths = existing.get("previous_paths", "")
    if moved:
        paths = [p.strip() for p in previous_paths.split(" | ") if p.strip()]
        if previous_path and previous_path not in paths:
            paths.append(previous_path)
        previous_paths = " | ".join(paths)

    body = [
        "# folder meta",
        f"folder_id: {folder_id}",
        f"name: {path.name}",
        f"current_path: {current_path}",
        f"root: {root.resolve()}",
        f"relative_path: {path.resolve().relative_to(root.resolve()) if path.resolve() != root.resolve() else '.'}",
        f"first_scanned: {first_scanned}",
        f"last_scanned: {now()}",
        f"moved_since_last_scan: {'yes' if moved else 'no'}",
        f"previous_paths: {previous_paths}",
        f"fingerprint: {folder_fingerprint(path)}",
        f"child_folder_count: {len(child_dirs)}",
        f"file_count: {len(child_files)}",
        f"total_file_bytes: {total_bytes}",
        f"extensions: {ext_summary}",
        f"tags: {', '.join(tags)}",
        "category: ",
        "notes: ",
        "",
        "## outline",
        *(outline or ["- [empty]"]),
        "",
    ]
    return "\n".join(body)


def iter_folders(root: Path, max_depth: int | None) -> list[Path]:
    folders: list[Path] = []
    for dirpath, dirnames, _ in os.walk(root):
        current = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if max_depth is not None and rel_depth(root, current) >= max_depth:
            dirnames[:] = []
        folders.append(current)
    return folders


def main() -> None:
    parser = argparse.ArgumentParser(description="Write .folder.fmeta markers into folders.")
    parser.add_argument("path", help="Root folder to tag")
    parser.add_argument("--max-depth", type=int, default=None, help="Optional folder depth limit")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be written")
    parser.add_argument("--force", action="store_true", help="Rewrite markers even if already present")
    parser.add_argument("--new-ids", action="store_true", help="Assign new folder IDs instead of preserving existing")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        parser.error(f"not a folder: {root}")

    folders = iter_folders(root, args.max_depth)
    written = skipped = errors = 0
    print(f"{len(folders)} folders found under {root}")

    for folder in folders:
        marker = folder / MARKER_NAME
        if marker.exists() and not args.force:
            skipped += 1
            continue
        try:
            body = marker_body(folder, root, force_new_id=args.new_ids)
            if args.dry_run:
                print(f"would write {marker}")
            else:
                marker.write_text(body, encoding="utf-8", newline="\n")
            written += 1
        except Exception as exc:
            errors += 1
            print(f"ERROR {folder}: {exc}")

    action = "would write" if args.dry_run else "wrote"
    print(f"done: {action} {written} markers | skipped {skipped} existing | errors {errors}")


if __name__ == "__main__":
    main()
