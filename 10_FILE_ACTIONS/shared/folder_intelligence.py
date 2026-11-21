r"""Read-only folder profiler and relationship scorer.

This module never copies, moves, renames, or deletes files.  It combines folder
evidence into profiles, then compares those profiles without using folder names
as a scoring signal.

Examples:
    python folder_intelligence.py profile D:\Papers D:\Archive --output profiles.json
    python folder_intelligence.py compare D:\Papers D:\Archive --hash-mode all
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


BLOCKED_NAMES = {
    "$recycle.bin",
    "#recycle",
    "system volume information",
    ".git",
    "node_modules",
    "__pycache__",
}


@dataclass
class FolderProfile:
    root: str
    generated_at: str
    available: bool = True
    errors: list[str] = field(default_factory=list)
    file_count: int = 0
    directory_count: int = 0
    total_bytes: int = 0
    extension_mix: dict[str, int] = field(default_factory=dict)
    size_buckets: dict[str, int] = field(default_factory=dict)
    modified_months: dict[str, int] = field(default_factory=dict)
    exact_hashes: dict[str, int] = field(default_factory=dict)


def _size_bucket(size: int) -> str:
    if size < 1_024:
        return "lt_1KiB"
    if size < 1_048_576:
        return "1KiB_1MiB"
    if size < 104_857_600:
        return "1MiB_100MiB"
    return "gte_100MiB"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _should_hash(path: Path, size: int, mode: str) -> bool:
    if mode == "all":
        return True
    if mode == "sample":
        # Deterministic, inexpensive sample; never hash very large files by default.
        marker = int(hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:8], 16)
        return size <= 100 * 1024 * 1024 and marker % 10 == 0
    return False


def profile_folder(root: Path, hash_mode: str = "none") -> FolderProfile:
    resolved = root.expanduser().resolve()
    profile = FolderProfile(
        root=str(resolved),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    if not resolved.exists() or not resolved.is_dir():
        profile.available = False
        profile.errors.append("root_unavailable")
        return profile

    extensions: Counter[str] = Counter()
    sizes: Counter[str] = Counter()
    months: Counter[str] = Counter()
    hashes: Counter[str] = Counter()

    def onerror(error: OSError) -> None:
        profile.errors.append(f"walk_error:{error.filename}:{error.strerror}")

    for current, dirs, files in os.walk(resolved, topdown=True, onerror=onerror, followlinks=False):
        dirs[:] = [d for d in dirs if d.casefold() not in BLOCKED_NAMES]
        profile.directory_count += len(dirs)
        base = Path(current)
        for name in files:
            path = base / name
            try:
                stat = path.stat(follow_symlinks=False)
                if path.is_symlink():
                    continue
                profile.file_count += 1
                profile.total_bytes += stat.st_size
                extensions[path.suffix.casefold() or "[no_extension]"] += 1
                sizes[_size_bucket(stat.st_size)] += 1
                months[datetime.fromtimestamp(stat.st_mtime, timezone.utc).strftime("%Y-%m")] += 1
                if _should_hash(path, stat.st_size, hash_mode):
                    hashes[_sha256(path)] += 1
            except (OSError, PermissionError) as exc:
                profile.errors.append(f"file_error:{path}:{exc.__class__.__name__}")

    profile.extension_mix = dict(sorted(extensions.items()))
    profile.size_buckets = dict(sorted(sizes.items()))
    profile.modified_months = dict(sorted(months.items()))
    profile.exact_hashes = dict(sorted(hashes.items()))
    return profile


def _cosine(left: dict[str, int], right: dict[str, int]) -> float:
    keys = set(left) | set(right)
    if not keys:
        return 1.0
    dot = sum(left.get(k, 0) * right.get(k, 0) for k in keys)
    lnorm = math.sqrt(sum(value * value for value in left.values()))
    rnorm = math.sqrt(sum(value * value for value in right.values()))
    return dot / (lnorm * rnorm) if lnorm and rnorm else 0.0


def _ratio_score(left: int, right: int) -> float:
    if left == right == 0:
        return 1.0
    if not left or not right:
        return 0.0
    return math.exp(-abs(math.log(left / right)))


def _hash_overlap(left: dict[str, int], right: dict[str, int]) -> tuple[float | None, int]:
    if not left or not right:
        return None, 0
    shared = set(left) & set(right)
    union = set(left) | set(right)
    return len(shared) / len(union), len(shared)


def compare_profiles(left: FolderProfile, right: FolderProfile) -> dict:
    if not left.available or not right.available:
        return {"left": left.root, "right": right.root, "allowed": False,
                "reason": "unavailable_root"}

    hash_score, shared_hashes = _hash_overlap(left.exact_hashes, right.exact_hashes)
    signals = {
        "extension_mix": _cosine(left.extension_mix, right.extension_mix),
        "size_mix": _cosine(left.size_buckets, right.size_buckets),
        "modified_time_mix": _cosine(left.modified_months, right.modified_months),
        "file_count": _ratio_score(left.file_count, right.file_count),
        "total_size": _ratio_score(left.total_bytes, right.total_bytes),
    }
    weights = {
        "extension_mix": 0.25,
        "size_mix": 0.15,
        "modified_time_mix": 0.15,
        "file_count": 0.10,
        "total_size": 0.10,
    }
    if hash_score is not None:
        signals["exact_hash_overlap"] = hash_score
        weights["exact_hash_overlap"] = 0.25
    total_weight = sum(weights.values())
    similarity = sum(signals[key] * weight for key, weight in weights.items()) / total_weight

    left_hashes, right_hashes = set(left.exact_hashes), set(right.exact_hashes)
    directional = "related"
    if left_hashes and right_hashes:
        if left_hashes == right_hashes:
            directional = "same_content_set"
        elif left_hashes < right_hashes:
            directional = "left_content_subset_of_right"
        elif right_hashes < left_hashes:
            directional = "right_content_subset_of_left"

    return {
        "left": left.root,
        "right": right.root,
        "allowed": True,
        "similarity": round(similarity, 6),
        "signals": {key: round(value, 6) for key, value in signals.items()},
        "shared_exact_hashes": shared_hashes,
        "directional_evidence": directional,
        "recommendation": "review_together" if similarity >= 0.75 else "keep_separate",
        "mutation_authorized": False,
    }


def all_relations(profiles: Iterable[FolderProfile]) -> list[dict]:
    items = list(profiles)
    return [compare_profiles(items[i], items[j])
            for i in range(len(items)) for j in range(i + 1, len(items))]


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only folder intelligence")
    parser.add_argument("command", choices=("profile", "compare"))
    parser.add_argument("folders", nargs="+", type=Path)
    parser.add_argument("--hash-mode", choices=("none", "sample", "all"), default="none")
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()

    profiles = [profile_folder(folder, args.hash_mode) for folder in args.folders]
    report = {
        "mode": "read_only",
        "profiles": [asdict(profile) for profile in profiles],
        "relations": all_relations(profiles) if args.command == "compare" else [],
    }
    encoded = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
