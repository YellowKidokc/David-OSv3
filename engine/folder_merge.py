"""Bounded, copy-only folder merge pilot. Never moves or deletes a source.

Run a saved recipe with: python -m engine.folder_merge recipe.json
Only regular files and directories are supported. Reparse points and scan errors
block affected groups. This runner deliberately provides no cleanup action.
"""
from __future__ import annotations

import itertools
import json
import os
import re
import shutil
import stat
import sys
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path

from engine.fingerprint import sha256_file
from engine.path_write_policy import require_write_allowed


def inventory(root: Path, workers: int = 1) -> dict:
    if workers > 1:
        return _parallel_inventory(root, workers)
    root = root.resolve(strict=True)
    result = {"root": str(root), "files": {}, "directories": [], "errors": []}
    if not root.is_dir():
        result["errors"].append("Scope root is not a directory")
        return result
    def error(exc):
        result["errors"].append(str(exc))
    def linked(path):
        info = path.lstat()
        return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)
    if linked(root):
        result["errors"].append("Root is a link/reparse point")
        return result
    for base, dirs, names in os.walk(root, followlinks=False, onerror=error):
        for name in list(dirs):
            path = Path(base) / name
            try:
                if linked(path):
                    dirs.remove(name)
                    raise OSError(f"Unsupported link/reparse point: {path}")
                result["directories"].append(path.relative_to(root).as_posix())
            except OSError as exc:
                error(exc)
        for name in names:
            path = Path(base) / name
            try:
                before = path.stat()
                if linked(path) or not stat.S_ISREG(before.st_mode):
                    raise OSError(f"Unsupported object: {path}")
                digest = sha256_file(str(path))
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise OSError(f"Changed while hashing: {path}")
                result["files"][path.relative_to(root).as_posix()] = {
                    "sha256": digest, "bytes": after.st_size, "mtime_ns": after.st_mtime_ns,
                }
            except OSError as exc:
                error(exc)
    result["bytes"] = sum(x["bytes"] for x in result["files"].values())
    return result


def _parallel_inventory(root: Path, workers: int) -> dict:
    """Bounded I/O concurrency for large NAS inventories; same evidence contract."""
    root = root.resolve(strict=True)
    result = {"root": str(root), "files": {}, "directories": [], "errors": []}
    def linked(path):
        info = path.lstat()
        return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)
    if not root.is_dir() or linked(root):
        result['errors'].append('Unsupported root')
        return result
    paths=[]
    for base, dirs, names in os.walk(root, followlinks=False, onerror=lambda e: result['errors'].append(str(e))):
        for name in list(dirs):
            path=Path(base)/name
            try:
                if linked(path):
                    dirs.remove(name)
                    raise OSError(f'Unsupported link/reparse point: {path}')
                result['directories'].append(path.relative_to(root).as_posix())
            except OSError as exc:result['errors'].append(str(exc))
        paths.extend(Path(base)/name for name in names)
    def fingerprint(path):
        try:
            before=path.stat()
            if linked(path) or not stat.S_ISREG(before.st_mode):
                raise OSError(f'Unsupported object: {path}')
            digest=sha256_file(str(path))
            after=path.stat()
            if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
                raise OSError(f'Changed while hashing: {path}')
            return path.relative_to(root).as_posix(), {'sha256':digest,'bytes':after.st_size,'mtime_ns':after.st_mtime_ns}, None
        except OSError as exc:return None,None,str(exc)
    with ThreadPoolExecutor(max_workers=min(workers,8)) as pool:
        for relative, identity, error in pool.map(fingerprint, paths):
            if error:result['errors'].append(error)
            else:result['files'][relative]=identity
    result['bytes']=sum(v['bytes'] for v in result['files'].values())
    return result


def compare(a: dict, b: dict, minimum_shared: int = 3, minimum_overlap: float = .6) -> dict:
    # Empty files are not relationship evidence. Name similarity alone never merges.
    ah = {v["sha256"] for v in a["files"].values() if v["bytes"]}
    bh = {v["sha256"] for v in b["files"].values() if v["bytes"]}
    shared = len(ah & bh)
    overlap = shared / min(len(ah), len(bh)) if ah and bh else 0
    normalize = lambda s: re.sub(r"\s*\(\d+\)$", "", s.lower())
    name_score = SequenceMatcher(None, normalize(Path(a["root"]).name), normalize(Path(b["root"]).name)).ratio()
    common = a["files"].keys() & b["files"].keys()
    exact_replica = bool(ah) and (
        {p: v["sha256"] for p, v in a["files"].items()}
        == {p: v["sha256"] for p, v in b["files"].items()}
        and sorted(a["directories"]) == sorted(b["directories"])
    )
    return {"a": a["root"], "b": b["root"], "name_similarity": name_score,
            "shared_nonempty_hashes": shared, "hash_containment": overlap,
            "same_relative_paths": len(common),
            "exact_replica": exact_replica,
            "conflicting_paths": sum(a["files"][p]["sha256"] != b["files"][p]["sha256"] for p in common),
            "related": not a["errors"] and not b["errors"] and (exact_replica or (shared >= minimum_shared and overlap >= minimum_overlap))}


def discover(items: list[dict], minimum_shared=3, minimum_overlap=.6):
    pairs = [compare(a, b, minimum_shared, minimum_overlap) for a, b in itertools.combinations(items, 2)]
    # Require all pairs within a group to pass; avoid unsafe transitive chaining.
    passed = {frozenset((p["a"], p["b"])) for p in pairs if p["related"]}
    groups = []
    for item in sorted(items, key=lambda x: x["root"].casefold()):
        for group in groups:
            if all(frozenset((item["root"], peer["root"])) in passed for peer in group):
                group.append(item)
                break
        else:
            groups.append([item])
    return pairs, [g for g in groups if len(g) > 1]


def merge_group(items: list[dict], destination: Path, apply=False) -> dict:
    """Copy the largest folder first, then union others into an isolated staging root."""
    destination = destination.resolve()
    require_write_allowed(destination)
    for item in items:
        source = Path(item["root"]).resolve()
        if source == destination or source in destination.parents or destination in source.parents:
            raise ValueError("Source and destination must be disjoint")
        if item["errors"]:
            raise ValueError("Incomplete source inventory")
    ranked = sorted(items, key=lambda x: (-x["bytes"], x["root"].casefold()))
    receipt = {"selected_largest": ranked[0]["root"], "destination": str(destination),
               "mode": "copy_only_pilot", "cleanup_authorized": False, "operations": [], "errors": []}
    allocated = {}
    for item in ranked:
        for directory in item["directories"]:
            target = destination / directory
            if apply:
                try:
                    target.mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    receipt["errors"].append(str(exc))
        for relative, identity in sorted(item["files"].items()):
            source = Path(item["root"]) / relative
            target = destination / relative
            key = str(target).casefold()
            conflict = key in allocated and allocated[key] != identity["sha256"]
            if conflict:
                target = target.with_name(target.stem + "__conflict_" + identity["sha256"] + target.suffix)
                key = str(target).casefold()
            row = {"source": str(source), "target": str(target), "sha256": identity["sha256"],
                   "conflict": conflict, "status": "planned"}
            receipt["operations"].append(row)
            if key in allocated and allocated[key] != identity["sha256"]:
                row["status"] = "blocked"
                receipt["errors"].append(f"Conflict target collision: {target}")
                continue
            allocated[key] = identity["sha256"]
            if not apply:
                continue
            try:
                if sha256_file(str(source)) != identity["sha256"]:
                    raise OSError(f"Source changed after scan: {source}")
                if target.exists():
                    if not target.is_file() or sha256_file(str(target)) != identity["sha256"]:
                        raise OSError(f"Existing destination differs: {target}")
                    row["status"] = "skipped_identical"
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with source.open("rb") as inp, target.open("xb") as out:
                        shutil.copyfileobj(inp, out, 1024 * 1024)
                    shutil.copystat(source, target)
                    row["status"] = "copied"
                if sha256_file(str(target)) != identity["sha256"]:
                    raise OSError(f"Copy verification failed: {target}")
            except OSError as exc:
                row["status"] = "failed"
                receipt["errors"].append(str(exc))
    # Full re-inventory verifies the source has not gained/lost/changed objects.
    if apply:
        for original in items:
            live = inventory(Path(original["root"]))
            if live["errors"] or live["files"] != original["files"] or sorted(live["directories"]) != sorted(original["directories"]):
                receipt["errors"].append(f"Source changed or unreadable at final verification: {original['root']}")
        for row in receipt["operations"]:
            try:
                if sha256_file(row["target"]) != row["sha256"]:
                    raise OSError(f"Final target hash mismatch: {row['target']}")
            except OSError as exc:
                receipt["errors"].append(str(exc))
    receipt["verified"] = apply and not receipt["errors"]
    return receipt


def run(recipe: dict) -> dict:
    if recipe.get("mode") not in {"preview", "copy_only_pilot"}:
        raise ValueError("Only preview and copy_only_pilot modes are supported")
    if recipe.get("destination_policy", "largest_bytes") != "largest_bytes" or recipe.get("conflict_policy", "keep_both") != "keep_both":
        raise ValueError("Pilot supports largest_bytes and keep_both policies only")
    roots = [Path(p).resolve(strict=True) for p in recipe["roots"]]
    for a, b in itertools.combinations(roots, 2):
        if a == b or a in b.parents or b in a.parents:
            raise ValueError("Scope roots must be distinct and nonoverlapping")
    out = Path(recipe["output"]).resolve()
    for source in roots:
        if source == out or source in out.parents or out in source.parents:
            raise ValueError("Output must be disjoint from source roots")
    require_write_allowed(out)
    out.mkdir(parents=True, exist_ok=False)
    # Exclusive output creation also prevents two runs from sharing destinations.
    inventories = []
    for root in roots:
        print(f"Hashing {root.name}", flush=True)
        inventories.append(inventory(root))
    pairs, groups = discover(inventories, recipe.get("minimum_shared_hashes", 3), recipe.get("minimum_hash_containment", .6))
    report = {"recipe": recipe, "inventories": inventories, "comparisons": pairs,
              "groups": [], "cleanup_authorized": False,
              "limitations": "Pilot stages regular-file bytes and directories only; no live merge, source removal, OneDrive integration or cleanup authorization."}
    (out / "discovery.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for n, group in enumerate(groups, 1):
        print(f"Merging group {n}: {len(group)} folders", flush=True)
        receipt = merge_group(group, out / f"MERGED_{n:02d}", recipe["mode"] == "copy_only_pilot")
        report["groups"].append(receipt)
        (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"folders": len(roots), "pairs": len(pairs), "groups": len(groups),
                      "verified_groups": sum(g["verified"] for g in report["groups"]), "report": str(out / 'report.json')}), flush=True)
    return report


if __name__ == "__main__":
    run(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
