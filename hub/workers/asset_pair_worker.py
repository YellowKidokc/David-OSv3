"""Deterministic paired-asset detection promoted into hub style."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

SIDE_CAR_EXTENSIONS = {".xmp", ".json", ".srt", ".txt", ".md"}


def detect_asset_pairs(paths: list[str]) -> dict[str, list[str]]:
    by_stem: dict[str, list[Path]] = defaultdict(list)
    for path in paths:
        file_path = Path(path)
        by_stem[str(file_path.with_suffix(""))].append(file_path)
    pairs: dict[str, list[str]] = {}
    for stem, grouped in by_stem.items():
        if len(grouped) < 2:
            continue
        sidecars = [str(path) for path in grouped if path.suffix.lower() in SIDE_CAR_EXTENSIONS]
        primaries = [str(path) for path in grouped if path.suffix.lower() not in SIDE_CAR_EXTENSIONS]
        if primaries and sidecars:
            pairs[primaries[0]] = sidecars
    return pairs
