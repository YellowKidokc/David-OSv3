#!/usr/bin/env python3
"""Create one recursive FIS root note for a drive or territory.

This is the D-drive policy variant: scattered folder-level `.fisnote` files are
preserved into an archive, and one root `FIS_FOLDER_INDEX.fisnote` becomes the
recursive human-readable map.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

SKIP_DIR_NAMES = {
    "$RECYCLE.BIN",
    "System Volume Information",
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".pnpm-store",
}

SIDECAR_SWEEP_SKIP_DIR_NAMES = {
    "$RECYCLE.BIN",
    "System Volume Information",
    ".git",
    ".hg",
    ".svn",
    "node_modules",
}

SIDECAR_NAMES = {".fisnote", "FIS_FOLDER_INDEX.fisnote"}

ME_KEYWORDS = {
    "ME_G_CONVERGENCE": {
        "gather", "collect", "archive", "vault", "canon", "canonical", "root",
        "master", "source", "intake", "inbox", "aggregate", "merge",
    },
    "ME_M_BINDING": {
        "bind", "link", "bridge", "hub", "graph", "relationship", "network",
        "sync", "workflow", "system", "engine", "pipeline",
    },
    "ME_E_SIGNAL": {
        "signal", "message", "api", "bridge", "communication", "clipboard",
        "email", "prompt", "chat", "voice", "transcript",
    },
    "ME_F_TRANSFORMATION": {
        "convert", "extract", "ocr", "transcribe", "parse", "render", "build",
        "generate", "rename", "move", "transform",
    },
    "ME_T_ENTROPY": {
        "temp", "tmp", "delete", "trash", "old", "backup", "copy", "final",
        "draft", "cache", "log", "broken", "orphan",
    },
    "ME_K_INFORMATION": {
        "data", "db", "sqlite", "json", "csv", "xlsx", "index", "manifest",
        "metadata", "knowledge", "memory", "vector",
    },
    "ME_R_FRAME": {
        "view", "dashboard", "report", "review", "compare", "perspective",
        "model", "frame", "ui", "screen",
    },
    "ME_Q_POTENTIAL": {
        "candidate", "staging", "test", "prototype", "experiment", "sandbox",
        "research", "hypothesis", "draft",
    },
    "ME_C_INTEGRATION": {
        "integrate", "unified", "complete", "production", "release", "site",
        "publish", "deployment", "canonical",
    },
    "ME_L_LOGOS_ORDER": {
        "logos", "theophysics", "faith", "physics", "axiom", "law", "truth",
        "nabla", "chi",
    },
}

TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".rst", ".json", ".jsonl", ".yaml", ".yml",
    ".csv", ".tsv", ".html", ".htm", ".py", ".ps1", ".bat", ".js", ".ts",
    ".jsx", ".tsx", ".css", ".xml", ".ini", ".cfg", ".toml",
}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def safe_rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def quick_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def long_path(path: Path) -> str:
    resolved = str(path.resolve())
    if resolved.startswith("\\\\?\\"):
        return resolved
    if resolved.startswith("\\\\"):
        return "\\\\?\\UNC\\" + resolved[2:]
    return "\\\\?\\" + resolved


def classify_me_tags(path: Path, is_dir: bool) -> list[str]:
    words = set()
    for part in path.parts:
        cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in part)
        words.update(w for w in cleaned.split() if len(w) >= 3)
    scores: list[tuple[int, str]] = []
    for tag, vocab in ME_KEYWORDS.items():
        score = len(words & vocab)
        if score:
            scores.append((score, tag))
    scores.sort(reverse=True)
    tags = [tag for _, tag in scores[:3]]
    if not tags:
        tags = ["ME_UNCLASSIFIED_NEEDS_NLP"]
    if is_dir:
        tags.append("FOLDER")
    return tags


def symptom_tags(path: Path, stat: os.stat_result | None, is_dir: bool) -> list[str]:
    name = path.name.lower()
    tags: list[str] = []
    if any(token in name for token in ("copy", "final", "old", "backup", "(1)", "(2)")):
        tags.append("SYM_VERSION_SPRAWL")
    if any(token in name for token in ("tmp", "temp", "cache", "log")):
        tags.append("SYM_TEMP_OR_CACHE")
    if any(token in name for token in ("delete", "trash", "recycle")):
        tags.append("SYM_DELETE_LANE")
    if len(str(path)) >= 220:
        tags.append("SYM_LONG_PATH")
    if stat and not is_dir and stat.st_size == 0:
        tags.append("SYM_EMPTY_FILE")
    if is_dir and name in {"node_modules", ".git", "__pycache__", ".pytest_cache"}:
        tags.append("SYM_TOOLCHAIN_RESIDUE")
    return tags


def should_skip_dir(path: Path, archive_root: Path, root_note: Path) -> bool:
    if path.name in SKIP_DIR_NAMES:
        return True
    try:
        path.resolve().relative_to(archive_root.resolve())
        return True
    except ValueError:
        pass
    return path == root_note.parent / "_FIS_ROOT_INDEX"


def iter_tree(root: Path, archive_root: Path, root_note: Path) -> Iterable[tuple[Path, bool, bool]]:
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                dirs = []
                for entry in entries:
                    p = Path(entry.path)
                    try:
                        is_dir = entry.is_dir(follow_symlinks=False)
                    except OSError:
                        yield p, False, False
                        continue
                    skipped = is_dir and should_skip_dir(p, archive_root, root_note)
                    yield p, is_dir, skipped
                    if is_dir and not skipped:
                        dirs.append(p)
                stack.extend(reversed(sorted(dirs, key=lambda x: x.name.lower())))
        except (PermissionError, FileNotFoundError, OSError):
            yield current, True, True


def iter_child_sidecars(root: Path, archive_root: Path, root_note: Path) -> Iterable[Path]:
    archive_resolved = archive_root.resolve()
    for current, dirs, files in os.walk(root, topdown=True):
        current_path = Path(current)
        try:
            current_path.resolve().relative_to(archive_resolved)
            dirs[:] = []
            continue
        except ValueError:
            pass
        dirs[:] = [d for d in dirs if d not in SIDECAR_SWEEP_SKIP_DIR_NAMES]
        for name in files:
            if name not in SIDECAR_NAMES:
                continue
            path = current_path / name
            if path == root_note:
                continue
            yield path


def archive_sidecar(path: Path, root: Path, archive_root: Path, moved: list[dict[str, str]], dry_run: bool) -> None:
    rel = safe_rel(path, root)
    dest = archive_root / "sidecars" / rel
    if len(str(dest)) > 230:
        digest = quick_id(rel)
        dest = archive_root / "sidecars_long" / f"{digest}__{path.name}"
    if dest.exists():
        dest = dest.with_name(f"{dest.name}.{dt.datetime.now():%Y%m%d_%H%M%S}.archived")
    moved.append({"source": str(path), "archive": str(dest)})
    if dry_run:
        return
    os.makedirs(long_path(dest.parent), exist_ok=True)
    shutil.move(long_path(path), long_path(dest))


def write_note(
    root: Path,
    note_path: Path,
    scan_id: str,
    archive_root: Path,
    folders: list[dict[str, object]],
    files: list[dict[str, object]],
    skipped: list[dict[str, object]],
    archived_sidecars: list[dict[str, str]],
    max_inventory_rows: int,
    truncated: bool,
) -> None:
    folder_count = len(folders)
    file_count = len(files)
    total_bytes = sum(int(f["size"]) for f in files)
    ext_counts = Counter(str(f["extension"]) for f in files)
    me_counts = Counter(tag for item in [*folders, *files] for tag in item["me_tags"])
    symptom_counts = Counter(tag for item in [*folders, *files] for tag in item["symptoms"])

    lines: list[str] = []
    lines.extend([
        "---",
        "fis_schema: d_drive_single_root_index.v1",
        f"scan_id: {scan_id}",
        f"root: {root}",
        f"generated_at: {now_iso()}",
        "policy: one_recursive_root_note_for_d_drive",
        f"archive_root: {archive_root}",
        f"folder_count: {folder_count}",
        f"file_count: {file_count}",
        f"total_bytes: {total_bytes}",
        f"inventory_truncated: {str(truncated).lower()}",
        "---",
        "",
        "# FIS Root Index: D Drive",
        "",
        "This is the single recursive FIS note for D:. Child `.fisnote` files are",
        "archived out of working folders so Git repositories do not keep syncing",
        "many generated sidecars.",
        "",
        "## Scan Summary",
        "",
        f"- Scan ID: `{scan_id}`",
        f"- Root: `{root}`",
        f"- Folders recorded: {folder_count:,}",
        f"- Files recorded: {file_count:,}",
        f"- Total file bytes: {total_bytes:,}",
        f"- Skipped protected/dependency folders: {len(skipped):,}",
        f"- Archived sidecar notes: {len(archived_sidecars):,}",
        f"- Archive root: `{archive_root}`",
        f"- Inventory row display limit: {max_inventory_rows:,}",
        f"- Entry scan was truncated: {str(truncated).lower()}",
        "",
        "## Top-Level Folders",
        "",
        "| Path | Direct/recursive hint tags | Symptoms |",
        "|---|---|---|",
    ])
    for folder in folders:
        rel = str(folder["path"])
        if "\\" in rel and rel.count("\\") > 0:
            continue
        lines.append(f"| `{rel}` | {', '.join(folder['me_tags'])} | {', '.join(folder['symptoms']) or '-'} |")

    lines.extend(["", "## Master Equation Tag Counts", "", "| Tag | Count |", "|---|---:|"])
    for tag, count in me_counts.most_common():
        lines.append(f"| {tag} | {count:,} |")

    lines.extend(["", "## Symptom Counts", "", "| Symptom | Count |", "|---|---:|"])
    if symptom_counts:
        for tag, count in symptom_counts.most_common():
            lines.append(f"| {tag} | {count:,} |")
    else:
        lines.append("| none_detected | 0 |")

    lines.extend(["", "## Extension Counts", "", "| Extension | Count |", "|---|---:|"])
    for ext, count in ext_counts.most_common(80):
        lines.append(f"| `{ext or '[none]'}` | {count:,} |")

    lines.extend(["", "## Archived Child FIS Notes", "", "| Source | Archive |", "|---|---|"])
    for item in archived_sidecars[:500]:
        lines.append(f"| `{item['source']}` | `{item['archive']}` |")
    if len(archived_sidecars) > 500:
        lines.append(f"| ... | {len(archived_sidecars) - 500:,} more archived sidecars omitted from display |")

    lines.extend(["", "## Skipped Folders", "", "| Path | Reason |", "|---|---|"])
    for item in skipped[:500]:
        lines.append(f"| `{item['path']}` | {item['reason']} |")
    if len(skipped) > 500:
        lines.append(f"| ... | {len(skipped) - 500:,} more skipped folders omitted from display |")

    lines.extend([
        "",
        "## Recursive Folder Inventory",
        "",
        "| Path | Tags | Symptoms |",
        "|---|---|---|",
    ])
    for folder in folders[:max_inventory_rows]:
        lines.append(
            f"| `{folder['path']}` | {', '.join(folder['me_tags'])} | {', '.join(folder['symptoms']) or '-'} |"
        )
    if len(folders) > max_inventory_rows:
        lines.append(f"| ... | {len(folders) - max_inventory_rows:,} more folders omitted from display | |")

    lines.extend([
        "",
        "## Recursive File Inventory",
        "",
        "| Path | Ext | Size | Modified | Tags | Symptoms | NLP |",
        "|---|---:|---:|---|---|---|---|",
    ])
    for f in files[:max_inventory_rows]:
        lines.append(
            f"| `{f['path']}` | `{f['extension']}` | {int(f['size']):,} | {f['modified']} | "
            f"{', '.join(f['me_tags'])} | {', '.join(f['symptoms']) or '-'} | {f['nlp_status']} |"
        )
    if len(files) > max_inventory_rows:
        lines.append(f"| ... |  |  |  |  |  | {len(files) - max_inventory_rows:,} more files omitted from display |")

    lines.append("")
    lines.append("<!-- d_drive_single_root_index.v1: safe to regenerate. -->")
    note_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a single recursive FIS note for a drive.")
    parser.add_argument("--root", default="D:\\", help="Root to scan")
    parser.add_argument("--note", default=None, help="Root note path")
    parser.add_argument("--archive-root", default=None, help="Archive root for child notes")
    parser.add_argument("--max-entries", type=int, default=200000, help="Stop after this many filesystem entries; 0 means no cap")
    parser.add_argument("--inventory-limit", type=int, default=2000, help="Max folders/files displayed in the markdown inventory")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Root does not exist or is not a directory: {root}")
    note_path = Path(args.note).resolve() if args.note else root / "FIS_FOLDER_INDEX.fisnote"
    scan_id = f"DROOT-{dt.datetime.now():%Y%m%d-%H%M%S}-{quick_id(str(root))}"
    archive_root = Path(args.archive_root).resolve() if args.archive_root else root / "_FIS_ROOT_SIDECAR_ARCHIVE" / scan_id

    folders: list[dict[str, object]] = []
    files: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    archived_sidecars: list[dict[str, str]] = []

    print(f"Scanning {root} -> {note_path}")
    print(f"Archive root: {archive_root}")
    print("Sweeping child FIS sidecars before inventory...")
    for path in iter_child_sidecars(root, archive_root, note_path):
        archive_sidecar(path, root, archive_root, archived_sidecars, args.dry_run)
    print(f"  child sidecars found: {len(archived_sidecars):,}")
    swept_sidecars = {item["source"] for item in archived_sidecars}
    truncated = False
    for i, (path, is_dir, is_skipped) in enumerate(iter_tree(root, archive_root, note_path), start=1):
        if args.max_entries and i > args.max_entries:
            truncated = True
            print(f"  max entries reached: {args.max_entries:,}")
            break
        if i % 10000 == 0:
            print(f"  scanned entries: {i:,} | files={len(files):,} folders={len(folders):,} archived_notes={len(archived_sidecars):,}")
        if path == note_path:
            continue
        if str(path) in swept_sidecars:
            continue
        if path.name in SIDECAR_NAMES and path != note_path:
            archive_sidecar(path, root, archive_root, archived_sidecars, args.dry_run)
            continue
        try:
            stat = path.stat()
        except OSError:
            stat = None
        rel = safe_rel(path, root)
        symptoms = symptom_tags(path, stat, is_dir)
        tags = classify_me_tags(path, is_dir)
        if is_dir:
            folders.append({
                "path": rel,
                "me_tags": tags,
                "symptoms": symptoms,
                "skipped": is_skipped,
            })
            if is_skipped:
                skipped.append({"path": rel, "reason": "protected/dependency/system folder"})
        else:
            ext = path.suffix.lower()
            files.append({
                "path": rel,
                "extension": ext,
                "size": stat.st_size if stat else 0,
                "modified": dt.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds") if stat else "UNKNOWN",
                "me_tags": tags,
                "symptoms": symptoms,
                "nlp_status": "candidate" if ext in TEXT_EXTS and tags == ["ME_UNCLASSIFIED_NEEDS_NLP"] else "not_needed",
            })

    if args.dry_run:
        print("Dry run: no note written and no sidecars moved.")
    else:
        archive_root.mkdir(parents=True, exist_ok=True)
        write_note(root, note_path, scan_id, archive_root, folders, files, skipped, archived_sidecars, max(0, args.inventory_limit), truncated)
        manifest = {
            "scan_id": scan_id,
            "root": str(root),
            "note_path": str(note_path),
            "archive_root": str(archive_root),
            "generated_at": now_iso(),
            "folder_count": len(folders),
            "file_count": len(files),
            "archived_sidecar_count": len(archived_sidecars),
            "skipped_count": len(skipped),
            "truncated": truncated,
            "max_entries": args.max_entries,
            "inventory_limit": args.inventory_limit,
            "archived_sidecars": archived_sidecars,
        }
        (archive_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Done. folders={len(folders):,} files={len(files):,} archived_notes={len(archived_sidecars):,} skipped={len(skipped):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
