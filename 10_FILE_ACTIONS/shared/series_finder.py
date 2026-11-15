r"""Series Finder — scan locations for files matching known series by name patterns.

Reads the canonical series from Z:\SERIES\ to learn what exists,
then searches target directories for matches and generates a movement plan.

Usage:
    python series_finder.py                    # dry-run report
    python series_finder.py --plan plan.csv    # write CSV movement plan
"""

import argparse
import csv
import hashlib
import json
import os
import re
from pathlib import Path
from datetime import datetime
from itertools import combinations

SERIES_ROOT = Path(r"Z:\SERIES")

SERIES_PATTERNS = {
    "01_MORAL_SUBSTRATE": {
        "prefix": re.compile(r"MS[_-]?\d{2}", re.IGNORECASE),
        "keywords": re.compile(r"moral.?substrate|cupcake.?proof|parasitic.?order|self.?defeating|domain.?audit", re.IGNORECASE),
    },
    "02_TEN_LAWS": {
        "prefix": re.compile(r"(?:LAW|Law)[_\s-]?\d{2}", re.IGNORECASE),
        "keywords": re.compile(r"ten.?laws|newton.?grace|maxwell.?truth|yukawa.?agape|clausius.?judgment|shannon.?logos|heisenberg.?faith|fermi.?conservation|einstein.?frame|coherence.?christ", re.IGNORECASE),
    },
    "03_MASTER_EQUATION": {
        "prefix": re.compile(r"ME[_-]?\d", re.IGNORECASE),
        "keywords": re.compile(r"master.?equation|logos.?theoretic.?lagrangian|CDR.?schema", re.IGNORECASE),
    },
    "04_GOD_IS_LOVE": {
        "prefix": re.compile(r"GOD[_-](?:IS[_-])?LOVE", re.IGNORECASE),
        "keywords": re.compile(r"god.?is.?love|character.?of.?god|if.?god.?is.?love", re.IGNORECASE),
    },
}

SEARCH_LOCATIONS = [
    Path(r"C:\Users\David\Documents\faiththruphysics.com"),
    Path(r"Z:\#recycle"),
    Path(r"Z:\___MASTER_EQ"),
    Path(r"Z:\SERIES"),
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return "UNREADABLE"


def scan_series_root():
    r"""Read Z:\SERIES to know what's already consolidated."""
    existing = {}
    if not SERIES_ROOT.is_dir():
        return existing
    for series_dir in SERIES_ROOT.iterdir():
        if series_dir.is_dir() and series_dir.name in SERIES_PATTERNS:
            files = list(series_dir.rglob("*"))
            existing[series_dir.name] = {
                "count": sum(1 for f in files if f.is_file()),
                "files": [f.name for f in files if f.is_file()],
            }
    return existing


def match_file(filepath: Path) -> list:
    """Return list of series names this file might belong to."""
    name = filepath.stem
    matches = []
    for series, patterns in SERIES_PATTERNS.items():
        if patterns["prefix"].search(name) or patterns["keywords"].search(name):
            matches.append(series)
    return matches


def scan_location(loc: Path) -> list:
    """Walk a location and return all files with series matches."""
    results = []
    if not loc.exists():
        return results
    for root, dirs, files in os.walk(loc):
        for fname in files:
            fp = Path(root) / fname
            matches = match_file(fp)
            if matches:
                try:
                    stat = fp.stat()
                    results.append({
                        "path": str(fp),
                        "name": fname,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "series_matches": matches,
                    })
                except (OSError, PermissionError):
                    pass
    return results


def corroborate_candidates(candidates: list[dict]) -> dict:
    """Retain exact-copy paths and folder evidence without deciding membership."""
    groups = {}
    unreadable = []
    for row in candidates:
        path = Path(row["path"]).resolve()
        digest = sha256_file(path)
        if digest == "UNREADABLE":
            unreadable.append(str(path))
            continue
        instances = groups.setdefault(digest, {})
        instances.setdefault(str(path), set()).update(row["series_matches"])

    evidence = []
    for digest, instances in sorted(groups.items()):
        folders = {}
        for path, series_names in instances.items():
            for series in series_names:
                folders.setdefault(series, set()).add(str(Path(path).parent))
        evidence.append({
            "sha256": digest,
            "instances": sorted(instances),
            "series_folders": {series: sorted(paths) for series, paths in sorted(folders.items())},
            "conflicting_series": len(folders) > 1,
        })
    return {"groups": evidence, "folder_overlap": folder_overlap(groups),
            "unreadable": sorted(set(unreadable))}


def folder_overlap(groups: dict) -> list[dict]:
    # Denominators cover the hashed candidates in this report.
    folder_hashes = {}
    shared_by_pair = {}
    for digest, instances in groups.items():
        folders = sorted({str(Path(path).parent) for path in instances})
        for folder in folders:
            folder_hashes.setdefault(folder, set()).add(digest)
        for pair in combinations(folders, 2):
            shared_by_pair.setdefault(pair, []).append(digest)

    overlaps = []
    for (left, right), shared in shared_by_pair.items():
        left_hashes = folder_hashes[left]
        right_hashes = folder_hashes[right]
        shared_set = set(shared)
        overlaps.append({
            "left_folder": left,
            "right_folder": right,
            "shared_sha256": sorted(shared_set),
            "left_only_sha256": sorted(left_hashes - shared_set),
            "right_only_sha256": sorted(right_hashes - shared_set),
            "left_candidate_coverage": len(shared_set) / len(left_hashes),
            "right_candidate_coverage": len(shared_set) / len(right_hashes),
        })
    return sorted(overlaps, key=lambda row: (
        -len(row["shared_sha256"]), row["left_folder"], row["right_folder"]
    ))


def main():
    parser = argparse.ArgumentParser(description="Series Finder")
    parser.add_argument("--plan", type=str, help="Write CSV movement plan to this path")
    parser.add_argument("--evidence", type=Path, help="Write exact-copy and series folder evidence to JSON")
    parser.add_argument("--locations", nargs="*", help="Override search locations")
    args = parser.parse_args()

    locations = [Path(p) for p in args.locations] if args.locations else SEARCH_LOCATIONS

    print("=== Series Finder ===")
    print(f"Series root: {SERIES_ROOT}")
    print()

    existing = scan_series_root()
    print("--- Already consolidated ---")
    for series, info in sorted(existing.items()):
        print(f"  {series}: {info['count']} files")
    print()

    all_found = []
    for loc in locations:
        print(f"Scanning: {loc} ...", end=" ", flush=True)
        found = scan_location(loc)
        print(f"{len(found)} matches")
        all_found.extend(found)

    print(f"\nTotal matches: {len(all_found)}")
    print()

    if args.evidence:
        with args.evidence.open("x", encoding="utf-8") as output:
            json.dump(corroborate_candidates(all_found), output, indent=2, ensure_ascii=False)
            output.write("\n")

    by_series = {}
    for item in all_found:
        for s in item["series_matches"]:
            by_series.setdefault(s, []).append(item)

    print("--- Matches by series ---")
    for series in sorted(by_series):
        items = by_series[series]
        already = set(existing.get(series, {}).get("files", []))
        new = [i for i in items if i["name"] not in already]
        print(f"  {series}: {len(items)} total, {len(new)} not yet in SERIES")

    if args.plan:
        rows = []
        for item in all_found:
            for s in item["series_matches"]:
                already = set(existing.get(s, {}).get("files", []))
                rows.append({
                    "source_path": item["path"],
                    "filename": item["name"],
                    "size": item["size"],
                    "modified": item["modified"],
                    "target_series": s,
                    "already_in_series": item["name"] in already,
                    "action": "SKIP" if item["name"] in already else "COPY",
                })
        with open(args.plan, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)
        print(f"\nMovement plan written to: {args.plan}")


if __name__ == "__main__":
    main()
