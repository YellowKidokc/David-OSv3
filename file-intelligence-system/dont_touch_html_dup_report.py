"""Accuracy packet: HTML vs MD vs Canon duplicates. Inventory only. No moves."""
from __future__ import annotations

import hashlib
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent

TAG_SCRIPT_RE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
TAG_SHELL_RE = re.compile(r"<(nav|header|footer|aside)\b.*?</\1>", re.S | re.I)
TAG_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
TAG_ANY_RE = re.compile(r"<[^>]+>")
FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.S)
WS_RE = re.compile(r"\s+")
WORD_RE = re.compile(r"[a-z0-9']+")
HASH_SUFFIX_RE = re.compile(r"[-_][0-9a-f]{8,12}$")
DATE_SUFFIX_RE = re.compile(r"[-_]\d{8}(?:[-_]\d{4,6})?$")
VARIANT_SUFFIXES = [
    "easy", "college", "academic", "phd", "high-school", "highschool",
    "clean", "final", "old", "new", "v2", "v3", "draft", "backup", "copy",
    "lossless", "summary", "index", "canonical",
]


def extract_text(raw: str, ext: str) -> str:
    if ext in (".html", ".htm"):
        raw = TAG_SCRIPT_RE.sub(" ", raw)
        raw = TAG_SHELL_RE.sub(" ", raw)
        raw = TAG_COMMENT_RE.sub(" ", raw)
        raw = TAG_ANY_RE.sub(" ", raw)
    elif ext == ".md":
        raw = FRONTMATTER_RE.sub("", raw)
        raw = TAG_COMMENT_RE.sub(" ", raw)
        raw = TAG_ANY_RE.sub(" ", raw)
    return WS_RE.sub(" ", raw).strip().lower()


def family_stem(path: str) -> str:
    stem = Path(path).stem.lower()
    if stem == "index":
        stem = Path(path).parent.name.lower()
    changed = True
    while changed:
        changed = False
        new = HASH_SUFFIX_RE.sub("", stem)
        new = DATE_SUFFIX_RE.sub("", new)
        if new != stem:
            stem, changed = new, True
        for suf in VARIANT_SUFFIXES:
            for sep in ("-", "_", "."):
                if stem.endswith(sep + suf):
                    stem = stem[: -(len(suf) + 1)]
                    changed = True
    return stem.strip("-_.")


BASE = Path(r"D:\DONT TOUCH HTML")
ROOTS = {
    "HTML": BASE / "HTML",
    "MD": BASE / "MD",
    "Canon": BASE / "Canon",
}
OUT = BASE / "DUP_ACCURACY_PACKET.md"
OUT2 = HERE / "reports" / "DONT_TOUCH_HTML_DUP_ACCURACY.md"

SKIP_DIR = {
    ".git", "node_modules", ".wrangler", "assets", "audio", "img", "images",
    "fonts", "css", "js", "__pycache__",
}
EXTS = {".html", ".htm", ".md"}
MAX_BYTES = 8 * 1024 * 1024


def skip_dir(name: str) -> bool:
    low = name.lower()
    return low in SKIP_DIR or low.startswith("_deploy") or low.startswith("_lineage")


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def verdict(score: float) -> str:
    if score >= 0.97:
        return "near-identical"
    if score >= 0.90:
        return "format/wrapper twin"
    if score >= 0.70:
        return "same article, edited"
    return "related name, different body"


def walk_bucket(label: str, root: Path) -> list[dict]:
    rows = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not skip_dir(d)]
        for fn in filenames:
            path = Path(dirpath) / fn
            if path.suffix.lower() not in EXTS:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > MAX_BYTES:
                continue
            rel = str(path.relative_to(BASE))
            try:
                raw = path.read_text(encoding="utf-8", errors="ignore")
                core = extract_text(raw, path.suffix.lower())
                word_list = WORD_RE.findall(core)
                if len(word_list) < 40:
                    digest = "thin"
                else:
                    digest = hashlib.sha256(core.encode("utf-8", "ignore")).hexdigest()[:16]
            except OSError:
                digest, word_list, raw = "unreadable", [], ""
            rows.append({
                "bucket": label,
                "rel": rel,
                "stem": family_stem(str(path)),
                "core": digest,
                "words": len(word_list),
                "wordset": set(word_list),
                "bytes": size,
            })
    return rows


def main() -> int:
    all_rows: list[dict] = []
    for label, root in ROOTS.items():
        if not root.is_dir():
            print("missing", root)
            continue
        print(f"scanning {label}...", flush=True)
        chunk = walk_bucket(label, root)
        print(f"  {len(chunk)} files", flush=True)
        all_rows.extend(chunk)

    by_core: dict[str, list[dict]] = defaultdict(list)
    by_stem: dict[str, list[dict]] = defaultdict(list)
    for row in all_rows:
        if row["core"] not in {"thin", "unreadable"}:
            by_core[row["core"]].append(row)
        by_stem[row["stem"]].append(row)

    exact = {k: v for k, v in by_core.items() if len(v) > 1}
    cross_bucket_exact = []
    same_bucket_exact = []
    for core, rows in exact.items():
        buckets = {r["bucket"] for r in rows}
        (cross_bucket_exact if len(buckets) > 1 else same_bucket_exact).append((core, rows))

    pair_rows = []
    for stem, rows in by_stem.items():
        if len(rows) < 2:
            continue
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                score = jaccard(a["wordset"], b["wordset"])
                pair_rows.append((score, stem, a, b, verdict(score)))
    near_id = sum(1 for s, *_ in pair_rows if s >= 0.97)
    wrap = sum(1 for s, *_ in pair_rows if 0.90 <= s < 0.97)
    edited = sum(1 for s, *_ in pair_rows if 0.70 <= s < 0.90)
    different = sum(1 for s, *_ in pair_rows if s < 0.70)

    lines = [
        "# Duplicate accuracy packet — DONT TOUCH HTML series",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "Roots: `HTML/` · `MD/` · `Canon/`  (skipped `_deploy*`, `_lineage*`, `.wrangler`, assets)",
        "Method: strip nav/header/footer/script/style, then SHA of remaining text **and** Jaccard on unique words.",
        "Nothing was renamed or moved.",
        "",
        f"- Files scanned: **{len(all_rows)}**",
        f"- Exact core-text groups: **{len(exact)}** (byte-identical after shell strip)",
        f"- Cross-folder exact: **{len(cross_bucket_exact)}**",
        f"- Same-folder exact: **{len(same_bucket_exact)}**",
        f"- Same-stem pairs scored: **{len(pair_rows)}**",
        f"  - near-identical (≥0.97): **{near_id}**",
        f"  - format/wrapper twin (0.90–0.97): **{wrap}**",
        f"  - same article, edited (0.70–0.90): **{edited}**",
        f"  - related name, different body (<0.70): **{different}**",
        "",
        "## How to read this",
        "",
        "Exact SHA is strict: one extra topbar word fails it. Jaccard is the accuracy check.",
        "High Jaccard + different SHA = the duplicates you already know are there; the files are format twins, not unique essays.",
        "",
        "## Same-stem closeness",
        "",
        "| Stem | A | B | Jaccard | Words | Verdict |",
        "|---|---|---|---:|---|---|",
    ]
    for score, stem, a, b, label in sorted(pair_rows, key=lambda x: -x[0]):
        lines.append(
            f"| `{stem}` | `{a['rel']}` | `{b['rel']}` | {score:.3f} | {a['words']} / {b['words']} | {label} |"
        )

    lines += ["", "## Cross-folder exact SHA", ""]
    if not cross_bucket_exact:
        lines.append("_None besides what is listed._")
    for core, rows in sorted(cross_bucket_exact, key=lambda kv: -len(kv[1])):
        buckets = ",".join(sorted({r["bucket"] for r in rows}))
        lines.append(f"### `{core}`  ({len(rows)} files · {buckets})")
        for r in rows:
            lines.append(f"- `{r['rel']}` — {r['words']} words, {r['bytes']:,} bytes")
        lines.append("")

    lines += ["## Same-folder exact SHA", ""]
    if not same_bucket_exact:
        lines.append("_None._")
    for core, rows in same_bucket_exact:
        lines.append(f"- `{core}`")
        for r in rows:
            lines.append(f"  - `{r['rel']}`")

    lines += [
        "",
        "## Per-file index",
        "",
        "| Bucket | Stem | Core | Words | Path |",
        "|---|---|---|---:|---|",
    ]
    for r in sorted(all_rows, key=lambda x: (x["stem"], x["bucket"], x["rel"])):
        lines.append(f"| {r['bucket']} | `{r['stem']}` | `{r['core']}` | {r['words']} | `{r['rel']}` |")

    text = "\n".join(lines)
    OUT.write_text(text, encoding="utf-8")
    OUT2.parent.mkdir(parents=True, exist_ok=True)
    OUT2.write_text(text, encoding="utf-8")
    print("wrote", OUT)
    print("wrote", OUT2)
    print(f"files={len(all_rows)} pairs={len(pair_rows)} near={near_id} wrap={wrap} edited={edited} different={different}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
