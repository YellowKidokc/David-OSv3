from __future__ import annotations

import argparse
import csv
import hashlib
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_EXCLUDE_DIRS = {
    "$RECYCLE.BIN",
    "$Recycle.Bin",
    "#recycle",
    "System Volume Information",
    ".git",
    "__pycache__",
    "node_modules",
}


@dataclass(frozen=True)
class RouteDecision:
    action: str
    source: Path
    destination: Path | None
    size: int
    reason: str


@dataclass
class RouteStats:
    seen: int = 0
    delete_duplicate: int = 0
    move_new: int = 0
    move_conflict: int = 0
    skip: int = 0
    delete_bytes: int = 0
    move_bytes: int = 0


def sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(1, 100_000):
        candidate = path.with_name(f"{stem}__CONFLICT_{index:05d}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"No unique destination available for {path}")


def walk_files(source: Path, exclude_dirs: set[str]) -> Iterable[Path]:
    for root, dirs, files in os.walk(source, topdown=True, followlinks=False):
        dirs[:] = [
            name
            for name in dirs
            if name not in exclude_dirs and not os.path.islink(os.path.join(root, name))
        ]
        for name in files:
            path = Path(root) / name
            try:
                if path.is_symlink() or not path.is_file():
                    continue
            except OSError:
                continue
            yield path


def decide(source_file: Path, source_root: Path, target_root: Path, import_root: Path) -> RouteDecision:
    try:
        size = source_file.stat().st_size
    except OSError as exc:
        return RouteDecision("skip", source_file, None, 0, f"stat failed: {exc}")

    if not is_within(source_file, source_root):
        return RouteDecision("skip", source_file, None, size, "source escaped source root")

    relpath = source_file.relative_to(source_root)
    canonical = target_root / relpath

    if canonical.exists() and canonical.is_file():
        try:
            if canonical.stat().st_size == size and sha256(source_file) == sha256(canonical):
                return RouteDecision(
                    "delete_duplicate",
                    source_file,
                    canonical,
                    size,
                    "same relative path, same size, same sha256",
                )
        except OSError as exc:
            return RouteDecision("skip", source_file, canonical, size, f"hash probe failed: {exc}")

        return RouteDecision(
            "move_conflict",
            source_file,
            import_root / relpath,
            size,
            "same relative path exists but content differs",
        )

    return RouteDecision("move_new", source_file, canonical, size, "no canonical relative path exists")


def apply_decision(decision: RouteDecision, execute: bool) -> RouteDecision:
    if not execute:
        return decision

    if decision.action == "delete_duplicate":
        decision.source.unlink()
        return decision

    if decision.action in {"move_new", "move_conflict"}:
        if decision.destination is None:
            return decision
        destination = unique_path(decision.destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(decision.source), str(destination))
        return RouteDecision(decision.action, decision.source, destination, decision.size, decision.reason)

    return decision


def update_stats(stats: RouteStats, decision: RouteDecision) -> None:
    stats.seen += 1
    if decision.action == "delete_duplicate":
        stats.delete_duplicate += 1
        stats.delete_bytes += decision.size
    elif decision.action == "move_new":
        stats.move_new += 1
        stats.move_bytes += decision.size
    elif decision.action == "move_conflict":
        stats.move_conflict += 1
        stats.move_bytes += decision.size
    else:
        stats.skip += 1


def route(
    source_root: Path,
    target_root: Path,
    import_root: Path,
    log_path: Path,
    execute: bool,
    exclude_dirs: set[str] | None = None,
) -> RouteStats:
    source_root = source_root.resolve()
    target_root = target_root.resolve()
    import_root = import_root.resolve()
    exclude_dirs = exclude_dirs or set(DEFAULT_EXCLUDE_DIRS)

    if not source_root.exists():
        raise FileNotFoundError(source_root)
    if not target_root.exists():
        raise FileNotFoundError(target_root)
    if source_root == target_root:
        raise ValueError("source and target resolve to the same path")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    stats = RouteStats()

    with log_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["mode", "action", "bytes", "source", "destination", "reason"])
        for source_file in walk_files(source_root, exclude_dirs):
            decision = decide(source_file, source_root, target_root, import_root)
            applied = apply_decision(decision, execute)
            update_stats(stats, applied)
            writer.writerow(
                [
                    "execute" if execute else "dry_run",
                    applied.action,
                    applied.size,
                    str(applied.source),
                    str(applied.destination or ""),
                    applied.reason,
                ]
            )
    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Proof-gated file router: delete only hash-proven duplicates, move everything else safely."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--execute", action="store_true", help="Perform deletes and moves. Default is dry-run.")
    parser.add_argument("--import-root", type=Path, help="Conflict import root. Defaults to target/_IMPORT_<timestamp>.")
    parser.add_argument("--log", type=Path, help="CSV action log path.")
    parser.add_argument("--exclude-dir", action="append", default=[], help="Additional directory name to skip.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    import_root = args.import_root or (args.target / f"_IMPORT_{stamp}")
    log_path = args.log or Path.cwd() / f"proof_router_{stamp}.csv"
    exclude_dirs = set(DEFAULT_EXCLUDE_DIRS) | set(args.exclude_dir)
    stats = route(args.source, args.target, import_root, log_path, args.execute, exclude_dirs)
    print(f"mode={'execute' if args.execute else 'dry_run'}")
    print(f"log={log_path}")
    print(f"seen={stats.seen}")
    print(f"delete_duplicate={stats.delete_duplicate} ({stats.delete_bytes / 1024**3:.2f} GB)")
    print(f"move_new={stats.move_new}")
    print(f"move_conflict={stats.move_conflict}")
    print(f"move_bytes={stats.move_bytes / 1024**3:.2f} GB")
    print(f"skip={stats.skip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
