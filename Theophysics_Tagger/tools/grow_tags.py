#!/usr/bin/env python3
"""Grow the tag registry: Theophysics at the top, the vault's folders as its categories, and new tags found in the
documents themselves, always as CANDIDATES first. Nothing reaches the registry until you mark it keep=yes.

  python grow_tags.py folders [--root <vault folder>] [--depth 2]
        Theophysics -> each folder under --root -> its subfolders, as category tags (parent_path Theophysics/...).
        Default root: ...\\_Theophysics_v5\\04_THEOPYHISCS. Archive, ZZZ, _ and Untitled folders are skipped.
  python grow_tags.py mine --source <folder> [--source ...] [--min-docs 3] [--api]
        New tag candidates from the documents: [[wikilinks]], YAML tags / #tags, **bold** terms, and repeated
        capitalised phrases, kept when they appear in at least --min-docs documents and are not tags or aliases yet.
        Each gets the category of the folder it is most common in. --api: DeepSeek (DEEPSEEK_API_KEY) merges
        duplicates, picks the category and writes a one-line description, in batches.
  python grow_tags.py accept
        Every row of 06_REVIEW\\candidate_tags.csv with keep=yes goes into 01_REGISTRY\\grown_tags.csv (old copy kept
        in 01_REGISTRY\\_older), then the combined registry is rebuilt, so the next scan uses them.

Candidates collect in 06_REVIEW\\candidate_tags.csv: reruns add new ones and keep your keep / category edits.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "01_REGISTRY"
SEED, GROWN, COMBINED = REG / "tag_registry.csv", REG / "grown_tags.csv", REG / "combined_tag_registry.csv"
CANDIDATES = ROOT / "06_REVIEW" / "candidate_tags.csv"
DEFAULT_ROOT = Path(os.environ.get("USERPROFILE", r"C:\Users\David")) / r"Documents\faiththruphysics.com\10_VAULTS\_Theophysics_v5\04_THEOPYHISCS"
FIELDS = ["tag", "slug", "category", "parent_path", "aliases", "master_equation_variable", "route_enabled", "scope",
          "description", "secondary_categories"]
CAND_FIELDS = ["keep", "tag", "category", "parent_path", "aliases", "description", "source", "doc_count", "example", "found_at"]
SKIP = re.compile(r"(archive|^zzz|^_|^\.|untitled|backup|duplicate|auto_extracted|analytics|^a3_|python|^new folder)", re.I)
TOP = "Theophysics"
STOP = set("""the a an and or of to in on for with by from at as is are was were be this that these those it its
his her their our your my we you they he she i not no yes all any each every one two three new old more most
chapter part section paper note notes figure table appendix introduction conclusion summary abstract draft
read first next last see also how what why when where who which""".split())


def clean(name: str) -> str:
    name = re.sub(r"^[\d!\-_.\s]+", "", name)                  # 03_, !! , 1-
    name = re.sub(r"^(DP|DT|FT)-\d+[-_ ]", "", name)            # DP-01- ...
    name = re.sub(r"\[[\d.]+\]", "", name)                     # [5.5], [69.1]
    name = re.sub(r"^(FP|S)\s?\d+[\s_-]+", "", name.replace("_", " "))   # FP_001_, S02_
    name = name.replace("_", " ").replace("-", " ").strip()
    return re.sub(r"\s+", " ", name)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def known_names() -> set[str]:
    names = set()
    for row in read_csv(COMBINED if COMBINED.exists() else SEED) + read_csv(GROWN):
        names.add((row.get("tag") or "").casefold())
        names.add((row.get("slug") or "").casefold())
        names |= {a.strip().casefold() for a in (row.get("aliases") or "").split(";") if a.strip()}
    names.discard("")
    return names


def merge_candidates(new: list[dict]) -> tuple[int, int]:
    """Add new candidates; keep every row already there (and the owner's edits to it)."""
    rows = read_csv(CANDIDATES)
    have = {r["tag"].casefold() for r in rows}
    added = 0
    for r in new:
        if r["tag"].casefold() in have:
            old = next(x for x in rows if x["tag"].casefold() == r["tag"].casefold())
            old["doc_count"] = r.get("doc_count", old.get("doc_count", ""))
            continue
        rows.append({**{k: "" for k in CAND_FIELDS}, **r, "found_at": datetime.now().strftime("%Y-%m-%d")})
        have.add(r["tag"].casefold())
        added += 1
    rows.sort(key=lambda r: (r.get("keep") != "yes", r.get("parent_path", ""), -int(r.get("doc_count") or 0)))
    write_csv(CANDIDATES, rows, CAND_FIELDS)
    return added, len(rows)


# ---------- folders ----------
def folders(root: Path, depth: int, min_notes: int = 3) -> int:
    if not root.is_dir():
        raise SystemExit(f"Not a folder: {root}")
    known = known_names()
    new = [{"tag": TOP, "category": TOP, "parent_path": TOP, "source": "top", "doc_count": "",
            "description": "The framework itself: the root of every Theophysics category."}] if TOP.casefold() not in known else []

    def visit(folder: Path, path: list[str], level: int):
        for sub in sorted(p for p in folder.iterdir() if p.is_dir()):
            if SKIP.search(sub.name):
                continue
            name = clean(sub.name)
            docs = sum(1 for _ in sub.rglob("*.md"))
            if not name or docs < min_notes:              # a one-note folder is a paper, not a category
                continue
            here = path + [name]
            if name.casefold() not in known:
                new.append({"tag": name, "category": f"{TOP} - {here[0]}", "parent_path": "/".join([TOP, *here]),
                            "source": f"folder: {sub.relative_to(root.parent)}", "doc_count": str(docs),
                            "description": f"Vault folder {sub.name} ({docs} notes)."})
            if level < depth:
                visit(sub, here, level + 1)
    visit(root, [], 1)
    added, total = merge_candidates(new)
    print(f"folders: {len(new)} category tags from {root} (depth {depth}); {added} new candidate(s), {total} in {CANDIDATES}")
    return 0


# ---------- mine ----------
WIKI = re.compile(r"\[\[([^\]|#]{3,60})(?:[#|][^\]]*)?\]\]")
HASHTAG = re.compile(r"(?<![\w/#])#([A-Za-z][\w/-]{2,40})")
BOLD = re.compile(r"\*\*([^*\n]{3,50})\*\*")
CAPS = re.compile(r"\b([A-Z][a-z]+(?:[ -](?:of |the |and )?[A-Z][a-z]+){1,3})\b")
YAML_TAGS = re.compile(r"^tags:\s*(.*?)(?=^\w[\w-]*:|\Z)", re.S | re.M)


def terms(text: str) -> set[str]:
    found = set()
    fm = re.match(r"^---\n(.*?)\n---", text, re.S)
    if fm:
        for block in YAML_TAGS.findall(fm.group(1)):
            found |= {t.strip(" -'\"[]#") for t in re.split(r"[,\n]", block) if t.strip(" -'\"[]#")}
    found |= {m.strip() for m in WIKI.findall(text)}
    found |= {m.split("/")[-1] for m in HASHTAG.findall(text)}
    found |= {m.strip() for m in BOLD.findall(text) if len(m.split()) <= 5}
    found |= set(CAPS.findall(text))
    out = set()
    for t in found:
        t = re.sub(r"\s+", " ", t.replace("_", " ")).strip(" .,:;")
        t = re.sub(r"^(the|a|an)\s+", "", t, flags=re.I)          # "The Trinity" is the Trinity tag
        words = t.lower().split()
        if (not t or len(t) < 3 or len(words) > 5 or all(w in STOP for w in words) or re.search(r"\d{3,}|https?|\.md$", t)
                or NOISE.match(t)):
            continue
        out.add(t)
    return out


# Page furniture, not concepts: "Part Four", "If God ...", "Do not say".
NOISE = re.compile(r"^(part|chapter|section|step|layer|level|phase|tier|figure|table|appendix)\s+\w+$"
                   r"|^(if|when|why|how|what|do|does|did|this|that|here|there|then|but|and|so|yet|not|no)\b", re.I)
# Station outputs beside a paper ("<note> · 41_STORY.md", "· ANALYSIS.md") and the analysis blocks on it are ours,
# not the author's: they are left out of mining.
OUTPUT_NAME = re.compile(r" · ([0-9]+_[A-Z0-9_]+|ANALYSIS|CKG|STORIES)\.md$")
OUR_BLOCKS = re.compile(r"<!-- (analysis|analysis-detail|scorecard):start -->.*?<!-- \1:end -->", re.S)


def mine(sources: list[Path], min_docs: int, use_api: bool) -> int:
    known = known_names()
    count: collections.Counter = collections.Counter()
    where: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    example: dict[str, str] = {}
    shown: dict[str, str] = {}
    docs = 0
    for src in sources:
        files = [src] if src.is_file() else [p for p in src.rglob("*.md") if not any(SKIP.search(x) for x in p.relative_to(src).parts[:-1])]
        for f in files:
            if OUTPUT_NAME.search(f.name):
                continue
            try:
                text = OUR_BLOCKS.sub(" ", f.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            docs += 1
            top = clean(f.relative_to(src).parts[0]) if src.is_dir() and len(f.relative_to(src).parts) > 1 else ""
            for t in terms(text):
                key = t.casefold()
                if key in known:
                    continue
                count[key] += 1
                shown.setdefault(key, t)
                example.setdefault(key, str(f))
                if top:
                    where[key][top] += 1
    picked = [(k, n) for k, n in count.most_common() if n >= min_docs]
    print(f"mine: {docs:,} documents, {len(count):,} unknown terms, {len(picked):,} in >= {min_docs} documents")
    new = []
    for key, n in picked[:600]:
        home = where[key].most_common(1)[0][0] if where[key] else ""
        new.append({"tag": shown[key], "category": f"{TOP} - {home}" if home else TOP,
                    "parent_path": "/".join(x for x in (TOP, home, shown[key]) if x), "source": "documents",
                    "doc_count": str(n), "example": example[key]})
    if use_api and new:
        new = refine_with_api(new)
    added, total = merge_candidates(new)
    print(f"mine: {added} new candidate(s); {total} in {CANDIDATES}. Mark keep=yes, then: grow_tags.py accept")
    return 0


def refine_with_api(rows: list[dict]) -> list[dict]:
    """DeepSeek tidies candidates in batches: drops noise, merges duplicates, picks a category, describes."""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        print("mine --api: DEEPSEEK_API_KEY is not set; candidates kept as found")
        return rows
    tree = sorted({r["parent_path"].rsplit("/", 1)[0] for r in read_csv(CANDIDATES) + rows if "/" in r.get("parent_path", "")})
    out = []
    for i in range(0, len(rows), 80):
        batch = rows[i:i + 80]
        prompt = ("You curate a theology-and-physics tag registry rooted at 'Theophysics'. For each candidate term, decide "
                  "keep (a real concept worth tagging) or drop (noise, a person's name used once, formatting). For kept "
                  "terms give the best parent_path from the TREE (or a new 'Theophysics/<Category>'), aliases that mean the "
                  "same thing (from the list too), and one plain sentence of description.\n"
                  f"TREE: {json.dumps(tree[:200])}\nCANDIDATES: {json.dumps([{'tag': r['tag'], 'docs': r['doc_count'], 'path': r['parent_path']} for r in batch])}\n"
                  'Return JSON: {"tags": [{"tag": "", "keep": true, "parent_path": "", "aliases": [], "description": ""}]}')
        body = json.dumps({"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
                           "response_format": {"type": "json_object"}, "temperature": 0.2, "max_tokens": 8000}).encode()
        req = urllib.request.Request("https://api.deepseek.com/chat/completions", data=body,
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                reply = json.loads(json.loads(r.read())["choices"][0]["message"]["content"])
        except Exception as e:  # one bad batch keeps its candidates as found
            print(f"  api batch {i // 80 + 1}: {e}; kept as found")
            out += batch
            continue
        by = {t.get("tag", "").casefold(): t for t in reply.get("tags", [])}
        for r in batch:
            t = by.get(r["tag"].casefold())
            if t is None:
                out.append(r)
            elif t.get("keep"):
                path = t.get("parent_path") or r["parent_path"]
                out.append({**r, "parent_path": path if path.endswith(r["tag"]) else f"{path}/{r['tag']}",
                            "category": f"{TOP} - {path.split('/')[1]}" if path.count("/") >= 1 else TOP,
                            "aliases": "; ".join(t.get("aliases") or []), "description": t.get("description", ""),
                            "source": "documents + DeepSeek"})
        print(f"  api batch {i // 80 + 1}: {len(batch)} in, {sum(1 for t in by.values() if t.get('keep'))} kept")
    return out


# ---------- accept ----------
def accept() -> int:
    rows = read_csv(CANDIDATES)
    chosen = [r for r in rows if (r.get("keep") or "").strip().lower() in ("yes", "y", "1", "true")]
    if not chosen:
        print(f"accept: nothing marked keep=yes in {CANDIDATES}")
        return 0
    grown = read_csv(GROWN)
    have = {r["slug"] for r in grown} | {r["slug"] for r in read_csv(SEED)}
    added = 0
    for r in chosen:
        s = slug(r["tag"])
        if s in have:
            continue
        grown.append({"tag": r["tag"], "slug": s, "category": r.get("category") or TOP,
                      "parent_path": r.get("parent_path") or f"{TOP}/{r['tag']}", "aliases": r.get("aliases", ""),
                      "route_enabled": "yes", "scope": "document;paragraph;sentence", "description": r.get("description", "")})
        have.add(s)
        added += 1
    if GROWN.exists():
        keep = REG / "_older" / datetime.now().strftime("%Y-%m-%d_%H%M%S")
        keep.mkdir(parents=True, exist_ok=True)
        shutil.copy2(GROWN, keep / GROWN.name)
    write_csv(GROWN, grown, FIELDS)
    left = [r for r in rows if r not in chosen or slug(r["tag"]) not in {g["slug"] for g in grown}]
    write_csv(CANDIDATES, left, CAND_FIELDS)
    print(f"accept: {added} tag(s) added to {GROWN} ({len(grown)} grown in all); rebuilding the combined registry")
    return subprocess.call([sys.executable, str(ROOT / "tools" / "rebuild_combined_registry.py")])


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("folders")
    f.add_argument("--root", default=str(DEFAULT_ROOT))
    f.add_argument("--depth", type=int, default=2)
    f.add_argument("--min-notes", type=int, default=3, help="a folder needs this many notes to be a category")
    m = sub.add_parser("mine")
    m.add_argument("--source", action="append", required=True)
    m.add_argument("--min-docs", type=int, default=3)
    m.add_argument("--api", action="store_true")
    sub.add_parser("accept")
    a = p.parse_args()
    if a.cmd == "folders":
        return folders(Path(a.root), a.depth, a.min_notes)
    if a.cmd == "mine":
        return mine([Path(s) for s in a.source], a.min_docs, a.api)
    return accept()


if __name__ == "__main__":
    raise SystemExit(main())
