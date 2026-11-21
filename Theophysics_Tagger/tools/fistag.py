#!/usr/bin/env python3
"""fistag: the three-code sidecar beside each paper (Theophysics is a given, so it is not written).

    OV.MEQ · API · CC
    |  |     |     +-- 3 COCO     CC = indexed by CocoIndex (its sha256 is in Canonization's papers table), -- = not
    |  |     +-------- 2 STAGE    RUN first run -> RWK reworking -> API API-checked -> CAN canonical (highest that holds)
    |  +-------------- 1 SUBJECT  FIS domain from the tagger's own tags (MEQ, LAW, CON, GRC, INF, FRM, AXM, ETH, COS, PHY,
    |                             THE ...); 01_REGISTRY\\fistag_domains.json says which tags count for which domain
    +----------------- 1 CONTEXT  OV = inside an Obsidian vault (a folder above it has .obsidian), NO = not

  python fistag.py --source <folder or file> [...]            show the codes (writes nothing)
  python fistag.py --source <folder> --scan --write           tag with tagger2 first, then write <file>.fistag

The .fistag file is JSON next to the paper (FIS's fis_sidecar.py already reads .fistag). The paper itself is never
touched. A rerun keeps first_sha256 / first_tagged, so editing a paper moves it from RUN to RWK.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "02_INDEX" / "tagger.db"
REGISTRY = ROOT / "01_REGISTRY" / "combined_tag_registry.csv"
SPEC = json.loads((ROOT / "01_REGISTRY" / "fistag_domains.json").read_text(encoding="utf-8"))
OUTPUT_NAME = re.compile(r" · ([0-9]+_[A-Z0-9_]+|ANALYSIS|CKG|STORIES)\.md$")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tag_domains() -> dict[str, str]:
    """tag -> FIS domain, from each tag's name, category and parent_path."""
    import csv
    out = {}
    with REGISTRY.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            text = " ".join((row.get("tag") or "", row.get("category") or "", row.get("parent_path") or "")).lower()
            for code, words in SPEC["domains"].items():
                if any(w in text for w in words):
                    out[row["tag"]] = code
                    break
    return out


def coco_hashes() -> set[str]:
    db = Path(SPEC.get("coco_db", ""))
    if not db.is_file():
        return set()
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return {r[0].lower() for r in con.execute("SELECT source_sha256 FROM papers WHERE source_sha256 <> ''")}
    finally:
        con.close()


def in_vault(path: Path) -> bool:
    return any((p / ".obsidian").is_dir() for p in path.parents)


def subject(con: sqlite3.Connection, path: Path, domains: dict[str, str]) -> tuple[str, list[str]]:
    row = con.execute("SELECT content_hash FROM documents WHERE path = ?", (str(path),)).fetchone()
    if not row:
        return "TPH", []
    rows = con.execute("SELECT tag, title_hits, heading_hits, body_hits FROM tag_counts WHERE content_hash = ?", (row[0],)).fetchall()
    score: dict[str, float] = {}
    tags = sorted(((3 * t + 2 * h + b, tag) for tag, t, h, b in rows), reverse=True)
    for s, tag in tags:
        code = domains.get(tag)
        if code:
            score[code] = score.get(code, 0) + s * SPEC.get("weights", {}).get(code, 1)
    best = max(score, key=score.get) if score else "TPH"
    return best, [t for _, t in tags[:8]]


def stage(path: Path, text: str, current: str, old: dict) -> str:
    parts = {p.lower() for p in path.parts[:-1]}
    if parts & {c.lower() for c in SPEC["canon_folders"]} or any(p.lower().startswith("00_canonical") for p in parts):
        return "CAN"
    canon = Path(str(path) + ".canon.sidecar.json")
    if canon.is_file():
        try:
            if json.loads(canon.read_text(encoding="utf-8")).get("standing", {}).get("canon_ready"):
                return "CAN"
        except (OSError, ValueError, AttributeError):
            pass
    if "<!-- analysis:start -->" in text or any(OUTPUT_NAME.search(p.name) for p in path.parent.glob(f"{glob(path.stem)} · *.md")):
        return "API"
    if old.get("first_sha256") and old["first_sha256"] != current:
        return "RWK"
    return "RUN"


def glob(name: str) -> str:
    return re.sub(r"([\[\]*?])", r"[\1]", name)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source", action="append", required=True)
    p.add_argument("--scan", action="store_true", help="run tagger2 scan on the sources first (unchanged files are skipped)")
    p.add_argument("--write", action="store_true", help="write <file>.fistag beside each paper")
    a = p.parse_args()
    if a.scan:
        cmd = [sys.executable, str(ROOT / "tools" / "tagger2.py"), "scan"] + [x for s in a.source for x in ("--source", s)]
        if subprocess.call(cmd) != 0:
            print("tagger2 scan failed; codes use whatever is already in the database")
    files = []
    for s in map(Path, a.source):
        files += [s] if s.is_file() else sorted(f for f in s.rglob("*.md") if not OUTPUT_NAME.search(f.name)
                                                and not any(x.startswith(("_", ".")) for x in f.relative_to(s).parts[:-1]))
    domains, coco = tag_domains(), coco_hashes()
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    counts: dict[str, int] = {}
    for f in files:
        f = f.resolve()
        side = Path(str(f) + ".fistag")
        old = {}
        if side.is_file():
            try:
                old = json.loads(side.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                old = {}
        digest = sha256(f)
        text = f.read_text(encoding="utf-8", errors="replace")
        ctx = "OV" if in_vault(f) else "NO"
        dom, top = subject(con, f, domains)
        stg = stage(f, text, digest, old)
        cc = "CC" if digest in coco else "--"
        code = f"{ctx}.{dom} · {stg} · {cc}"
        counts[code] = counts.get(code, 0) + 1
        print(f"{code}   {f.name[:90]}")
        if a.write:
            now = datetime.now().isoformat(timespec="seconds")
            side.write_text(json.dumps({
                "fistag": code, "context": ctx, "domain": dom, "stage": stg, "stage_name": SPEC["stages"][stg], "coco": cc == "CC",
                "top_tags": top, "sha256": digest, "first_sha256": old.get("first_sha256") or digest,
                "first_tagged": old.get("first_tagged") or now, "updated": now, "by": "Theophysics_Tagger fistag.py v1",
            }, indent=2, ensure_ascii=False), encoding="utf-8")
    con.close()
    print(f"\n{len(files)} paper(s)" + (" · .fistag written beside each" if a.write else " · dry run (add --write)"))
    for code, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {n:4}  {code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
