#!/usr/bin/env python3
"""Read-only cross-format publication-family inventory."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

TAG_BLOCK_RE = re.compile(r"<(script|style|nav|header|footer|aside)\b.*?</\1>", re.S | re.I)
TAG_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
TAG_ANY_RE = re.compile(r"<[^>]+>")
FRONTMATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.S)
WORD_RE = re.compile(r"[a-z0-9']+")
HASH_SUFFIX_RE = re.compile(r"[-_][0-9a-f]{8,12}$")
DATE_SUFFIX_RE = re.compile(r"[-_]\d{8}(?:[-_]\d{4,6})?$")
VARIANT_SUFFIXES = ("easy", "college", "academic", "phd", "high-school", "highschool",
                    "clean", "final", "old", "new", "v2", "v3", "draft", "backup",
                    "copy", "lossless", "summary", "index", "canonical")
SKIP_DIRS = {".git", "node_modules", ".wrangler", "assets", "audio", "img", "images",
             "fonts", "css", "js", "__pycache__"}
EXTS = {".html", ".htm", ".md", ".markdown"}


def extract_words(raw: str, ext: str) -> list[str]:
    if ext in {".html", ".htm"}:
        raw = TAG_BLOCK_RE.sub(" ", raw)
    elif ext in {".md", ".markdown"}:
        raw = FRONTMATTER_RE.sub("", raw)
    raw = TAG_COMMENT_RE.sub(" ", raw)
    raw = TAG_ANY_RE.sub(" ", raw)
    return WORD_RE.findall(html.unescape(raw).lower())


def family_stem(path: Path) -> str:
    stem = path.stem.lower()
    if stem == "index":
        stem = path.parent.name.lower()
    changed = True
    while changed:
        changed = False
        for pattern in (HASH_SUFFIX_RE, DATE_SUFFIX_RE):
            new = pattern.sub("", stem)
            if new != stem:
                stem, changed = new, True
        for suffix in VARIANT_SUFFIXES:
            for separator in ("-", "_", "."):
                token = separator + suffix
                if stem.endswith(token):
                    stem = stem[:-len(token)]
                    changed = True
    return stem.strip("-_.") or path.stem.lower()


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def verdict(score: float) -> str:
    if score >= 0.97:
        return "near-identical"
    if score >= 0.90:
        return "format/wrapper twin"
    if score >= 0.70:
        return "same article, edited"
    return "related name, different body"


def parse_buckets(values: list[str]) -> dict[str, Path]:
    buckets: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"Invalid --bucket {value!r}; expected LABEL=PATH")
        label, raw_path = value.split("=", 1)
        label, path = label.strip(), Path(raw_path.strip()).resolve()
        if not label or label in buckets:
            raise SystemExit(f"Bucket label must be non-empty and unique: {label!r}")
        if not path.is_dir():
            raise SystemExit(f"Bucket path is not a directory: {path}")
        buckets[label] = path
    return buckets


def walk_bucket(label: str, root: Path, max_bytes: int) -> list[dict]:
    rows: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS
                       and not d.lower().startswith(("_deploy", "_lineage"))]
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.suffix.lower() not in EXTS:
                continue
            size = 0
            try:
                size = path.stat().st_size
                if size > max_bytes:
                    continue
                words = extract_words(path.read_text(encoding="utf-8", errors="ignore"), path.suffix.lower())
            except OSError:
                words = []
            normalized = " ".join(words)
            rows.append({"bucket": label, "path": str(path),
                         "relative_path": str(path.relative_to(root)), "stem": family_stem(path),
                         "sha256_core": hashlib.sha256(normalized.encode()).hexdigest() if len(words) >= 40 else None,
                         "words": len(words), "bytes": size, "wordset": set(words)})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Markdown/HTML families without changing sources.")
    parser.add_argument("--bucket", action="append", required=True, metavar="LABEL=PATH")
    parser.add_argument("--out-dir", required=True, help="Separate directory for report.json and report.md")
    parser.add_argument("--max-bytes", type=int, default=8 * 1024 * 1024)
    args = parser.parse_args()
    buckets = parse_buckets(args.bucket)
    if len(buckets) < 2:
        raise SystemExit("At least two --bucket values are required.")
    out_dir = Path(args.out_dir).resolve()
    if any(out_dir == root or root in out_dir.parents for root in buckets.values()):
        raise SystemExit("--out-dir must be outside every source bucket.")

    rows: list[dict] = []
    for label, root in buckets.items():
        print(f"scanning {label}: {root}", flush=True)
        rows.extend(walk_bucket(label, root, args.max_bytes))
    by_stem: dict[str, list[dict]] = defaultdict(list)
    by_core: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_stem[row["stem"]].append(row)
        if row["sha256_core"]:
            by_core[row["sha256_core"]].append(row)

    expected, families, pairs = set(buckets), [], []
    for stem, members in sorted(by_stem.items()):
        present = {m["bucket"] for m in members}
        families.append({"stem": stem, "present_buckets": sorted(present),
                         "missing_buckets": sorted(expected - present),
                         "files": [{k: v for k, v in m.items() if k != "wordset"} for m in members]})
        for index, left in enumerate(members):
            for right in members[index + 1:]:
                score = jaccard(left["wordset"], right["wordset"])
                pairs.append({"stem": stem, "a": left["path"], "b": right["path"],
                              "jaccard": round(score, 4), "verdict": verdict(score)})
    exact_groups = [[{k: v for k, v in row.items() if k != "wordset"} for row in group]
                    for group in by_core.values() if len(group) > 1]
    payload = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "method": "shell-stripped normalized-text SHA-256 plus same-stem token Jaccard",
               "source_mutations": False, "buckets": {k: str(v) for k, v in buckets.items()},
               "summary": {"files": len(rows), "families": len(families),
                           "incomplete_families": sum(bool(f["missing_buckets"]) for f in families),
                           "exact_core_groups": len(exact_groups), "same_stem_pairs": len(pairs)},
               "families": families,
               "same_stem_pairs": sorted(pairs, key=lambda p: p["jaccard"], reverse=True),
               "exact_core_groups": exact_groups}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# Publication family format report", "", f"Generated: {payload['generated_utc']}", "",
             "Read-only source audit. No source files were changed.", "", f"- Files: **{len(rows)}**",
             f"- Families: **{len(families)}**",
             f"- Incomplete families: **{payload['summary']['incomplete_families']}**",
             f"- Exact normalized-text groups: **{len(exact_groups)}**", "", "## Family completeness", "",
             "| Family | Present | Missing | Files |", "|---|---|---|---:|"]
    for family in families:
        lines.append(f"| `{family['stem']}` | {', '.join(family['present_buckets'])} | "
                     f"{', '.join(family['missing_buckets']) or '-'} | {len(family['files'])} |")
    lines += ["", "## Same-stem comparisons", "", "| Family | Jaccard | Verdict | A | B |",
              "|---|---:|---|---|---|"]
    for pair in payload["same_stem_pairs"]:
        lines.append(f"| `{pair['stem']}` | {pair['jaccard']:.3f} | {pair['verdict']} | "
                     f"`{pair['a']}` | `{pair['b']}` |")
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    print(f"wrote {out_dir / 'report.json'}")
    print(f"wrote {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
