#!/usr/bin/env python3
"""Theophysics Convergence Tagger.

Read-only by default. Scans .md/.txt files, tags at document/paragraph/sentence
level, and writes CSV indexes. Copying into tag folders requires an explicit flag.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Theophysics_Tagger")
DEFAULT_REGISTRY = ROOT / "01_REGISTRY" / "combined_tag_registry.csv"
DEFAULT_OUTPUT = ROOT / "02_INDEX"
DEFAULT_TAGGED = ROOT / "03_TAGGED"

@dataclass
class Tag:
    tag: str
    slug: str
    category: str
    parent_path: str
    aliases: list[str]
    variable: str
    pattern: re.Pattern[str]


def slugify(value: str) -> str:
    value = re.sub(r"(?<!^)(?=[A-Z])", "-", value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "item"


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def load_registry(path: Path) -> list[Tag]:
    tags: list[Tag] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            terms = [row["tag"], *[x.strip() for x in row.get("aliases", "").split(";") if x.strip()]]
            escaped = [re.escape(term) for term in terms if term]
            if not escaped:
                continue
            pattern = re.compile(r"(?<![A-Za-z0-9_])(?:" + "|".join(escaped) + r")(?![A-Za-z0-9_])", re.IGNORECASE)
            tags.append(Tag(
                tag=row["tag"],
                slug=row.get("slug") or slugify(row["tag"]),
                category=row.get("category", "Uncategorized"),
                parent_path=row.get("parent_path", row["tag"]),
                aliases=[x.strip() for x in row.get("aliases", "").split(";") if x.strip()],
                variable=row.get("master_equation_variable", ""),
                pattern=pattern,
            ))
    return tags


def iter_files(sources: list[Path], exts: set[str], limit: int | None):
    count = 0
    for source in sources:
        if source.is_file() and source.suffix.lower() in exts:
            yield source
            count += 1
        elif source.is_dir():
            for path in source.rglob("*"):
                if path.is_file() and path.suffix.lower() in exts:
                    yield path
                    count += 1
                    if limit and count >= limit:
                        return
        if limit and count >= limit:
            return


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def find_hits(text: str, tags: list[Tag]) -> list[Tag]:
    return [tag for tag in tags if tag.pattern.search(text)]


def hash_path(path: Path) -> str:
    return hashlib.sha1(str(path).encode("utf-8", errors="ignore")).hexdigest()[:12]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append", help="File or folder to scan. Repeatable.")
    parser.add_argument("--source-list", help="UTF-8 text file containing one exact source path per line.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--tagged", default=str(DEFAULT_TAGGED))
    parser.add_argument("--extensions", default=".md,.txt")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--document-only", action="store_true", help="Skip paragraph and sentence indexes.")
    parser.add_argument("--copy-by-primary-tag", action="store_true", help="Copy files into 03_TAGGED/<category>/<tag>/ by primary hit.")
    args = parser.parse_args()

    tags = load_registry(Path(args.registry))
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    tagged_dir = Path(args.tagged)
    exts = {e.strip().lower() for e in args.extensions.split(",") if e.strip()}
    sources = [Path(s) for s in (args.source or [])]
    if args.source_list:
        sources.extend(Path(line.strip()) for line in Path(args.source_list).read_text(encoding="utf-8-sig").splitlines() if line.strip())
    if not sources:
        parser.error("provide --source or --source-list")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    doc_rows = []
    para_rows = []
    sent_rows = []
    folder_rows = []

    for file_path in iter_files(sources, exts, args.limit):
        try:
            text = read_text(file_path)
        except OSError as exc:
            folder_rows.append({"path": str(file_path), "status": f"read_error: {exc}", "primary_tag": "", "target_folder": ""})
            continue

        doc_hits = find_hits(text, tags)
        if not doc_hits:
            continue
        doc_id = hash_path(file_path)
        primary = doc_hits[0]
        doc_rows.append({
            "doc_id": doc_id,
            "path": str(file_path),
            "primary_tag": primary.tag,
            "primary_category": primary.category,
            "tags": ";".join(tag.tag for tag in doc_hits),
            "variables": ";".join(sorted({tag.variable for tag in doc_hits if tag.variable})),
            "hit_count": len(doc_hits),
        })

        if not args.document_only:
            for idx, para in enumerate(split_paragraphs(text), start=1):
                hits = find_hits(para, doc_hits)
                if hits:
                    para_rows.append({"doc_id": doc_id, "path": str(file_path), "paragraph": idx, "tags": ";".join(t.tag for t in hits), "text": para[:1000]})
                    for sidx, sent in enumerate(split_sentences(para), start=1):
                        shits = find_hits(sent, hits)
                        if shits:
                            sent_rows.append({"doc_id": doc_id, "path": str(file_path), "paragraph": idx, "sentence": sidx, "tags": ";".join(t.tag for t in shits), "text": sent[:1000]})

        target_folder = tagged_dir / slugify(primary.category) / primary.slug
        folder_rows.append({"path": str(file_path), "status": "suggested", "primary_tag": primary.tag, "target_folder": str(target_folder)})
        if args.copy_by_primary_tag:
            target_folder.mkdir(parents=True, exist_ok=True)
            target = target_folder / file_path.name
            if target.exists():
                target = target_folder / f"{file_path.stem}__{doc_id}{file_path.suffix}"
            shutil.copy2(file_path, target)

    def write_csv(name: str, rows: list[dict]):
        path = out_dir / f"{stamp}_{name}.csv"
        if not rows:
            path.write_text("", encoding="utf-8-sig")
            return path
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return path

    paths = {
        "documents": str(write_csv("document_tags", doc_rows)),
        "paragraphs": str(write_csv("paragraph_tags", para_rows)),
        "sentences": str(write_csv("sentence_tags", sent_rows)),
        "folders": str(write_csv("folder_suggestions", folder_rows)),
    }
    summary = {"scanned_sources": [str(s) for s in sources], "documents_tagged": len(doc_rows), "paragraph_hits": len(para_rows), "sentence_hits": len(sent_rows), "outputs": paths}
    (out_dir / f"{stamp}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8-sig")
    print(json.dumps(summary, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
