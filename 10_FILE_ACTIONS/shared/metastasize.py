"""Walk outward from a seed folder through master-classification relationships.

Read-only. A walk creates a connection report; it never moves or edits sources.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


def values(text: str) -> set[str]:
    return {v.strip().casefold() for v in re.split(r"[;,]", text or "") if v.strip()}


def load_rows(index: Path, perimeter: str = "") -> list[dict]:
    with index.open("r", encoding="utf-8-sig", errors="replace", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    if perimeter:
        key = perimeter.replace("\\", "/").casefold().strip("/")
        rows = [r for r in rows if key in (r.get("file_path") or "").replace("\\", "/").casefold()]
    return rows


def folder_of(raw: str) -> str:
    return str(PurePosixPath((raw or "").replace("\\", "/")).parent)


def build_walk(seeds: list[Path], rows: list[dict], max_hops: int, branches: int) -> dict:
    seed_names = {
        p.name.casefold() for seed in seeds for p in seed.rglob("*") if p.is_file()
    }
    matched = [r for r in rows if Path(r.get("file_path") or "").name.casefold() in seed_names]
    series = Counter((r.get("series") or "").strip() for r in matched if (r.get("series") or "").strip())
    subjects: set[str] = set()
    laws: set[str] = set()
    for row in matched:
        subjects |= values(row.get("subjects") or "")
        laws |= values(row.get("laws") or "")

    folders: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        folders[folder_of(row.get("file_path") or "")].append(row)
    visited: set[str] = set()
    jumps: list[dict] = []
    for hop in range(1, max_hops + 1):
        candidates = []
        for folder, members in folders.items():
            if folder in visited:
                continue
            f_series = Counter((r.get("series") or "").strip() for r in members if (r.get("series") or "").strip())
            f_subjects = set().union(*(values(r.get("subjects") or "") for r in members))
            f_laws = set().union(*(values(r.get("laws") or "") for r in members))
            shared_series = sorted(set(series) & set(f_series))
            shared_subjects = sorted(subjects & f_subjects)
            shared_laws = sorted(laws & f_laws)
            structural = any(
                folder.startswith(parent + "/") or parent.startswith(folder + "/")
                for parent in visited
            )
            score = 100 * len(shared_series) + 4 * len(shared_laws) + 2 * len(shared_subjects) + (25 if structural else 0)
            if score:
                candidates.append((score, folder, members, shared_series, shared_subjects, shared_laws, structural, f_series, f_subjects, f_laws))
        candidates.sort(key=lambda item: (-item[0], item[1].casefold()))
        chosen = candidates[:branches]
        if not chosen:
            break
        for score, folder, members, ss, st, sl, structural, fs, fst, fl in chosen:
            visited.add(folder)
            jumps.append({
                "hop": hop, "folder": folder, "score": score,
                "record_count": len(members),
                "unique_filename_count": len({Path(r.get('file_path') or '').name.casefold() for r in members}),
                "shared_series": ss, "shared_subjects": st[:20], "shared_laws": sl,
                "structural_link": structural,
                "reason": f"series={','.join(ss) or '-'}; laws={','.join(sl) or '-'}; subjects={','.join(st[:8]) or '-'}; structural_parent={str(structural).lower()}",
            })
            series.update(fs)
            subjects |= fst
            laws |= fl
    return {
        "schema": "david-os.metastasize-walk.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seeds": [str(seed.resolve()) for seed in seeds],
        "source_mutations": False,
        "seed_file_count": len(seed_names),
        "seed_index_matches": len(matched),
        "seed_series": dict(series.most_common()),
        "jumps": jumps,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, action="append", help="Repeat for multiple starting folders")
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--perimeter", default="", help="Optional logical path fragment inside the master index")
    parser.add_argument("--max-hops", type=int, default=5)
    parser.add_argument("--branches", type=int, default=5)
    args = parser.parse_args()
    seeds = args.seed or [Path.cwd()]
    report = build_walk(seeds, load_rows(args.index, args.perimeter), args.max_hops, args.branches)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "metastasize.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (args.output / "metastasize.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["hop", "folder", "score", "record_count", "unique_filename_count", "shared_series", "shared_subjects", "shared_laws", "structural_link", "reason"])
        writer.writeheader()
        for row in report["jumps"]:
            writer.writerow({**row, "shared_series": ";".join(row["shared_series"]), "shared_subjects": ";".join(row["shared_subjects"]), "shared_laws": ";".join(row["shared_laws"])})
    print(json.dumps({"seed_matches": report["seed_index_matches"], "jumps": len(report["jumps"]), "mutations": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
