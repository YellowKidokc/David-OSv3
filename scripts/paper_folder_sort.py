#!/usr/bin/env python3
"""paper_folder_sort.py — one-command sort for an API pipeline folder.

Created 2026-10-07 (Kimi, with David) from the ___Pipeline_Done_New sort.
Status: TESTED on "One page paper API" (196k files, produced 499 originals /
510 untouched / 21 canonization / 292 verified merged papers).

What it does, in order (source is never modified; every step writes receipts):

  1. MIRROR   robocopy the source to local scratch (network shares are too slow
              to hash directly). Skip with --no-mirror if a mirror exists.
  2. CENSUS   SHA-256 every text file; group duplicates; classify each file by
              role (originals / untouched / api sheets / canonization / merged).
  3. STAGE    one clean-named copy per unique original -> ORIGINALS/
              unique never-processed papers          -> UNTOUCHED/
              curated canonization set               -> CANONIZATION_GOD_IS/
  4. MERGE    if the folder carries the EVIDENCE merge machinery
              (api_original_merge.py + article_stack.py), run it across ALL
              shelves, then keep one copy per unique merged document -> MERGED/.
              Merged files are byte-verified: the bytes below the marker must
              hash to the value the marker records.
  5. PUSH     robocopy the staging tree to the destination (no /MIR — never
              deletes anything at the destination).
  6. REPORTS  census JSON + merge report CSV land in <dest>/_REPORTS/.

Usage:
  python paper_folder_sort.py --source "\\NAS\share\API folder" --dest "\\NAS\share\Out"
  python paper_folder_sort.py --source ... --dest ... --no-mirror --work D:\pipeline_sort_work
  python paper_folder_sort.py --source ... --dest ... --dry-run   # census + plan only

The role layout defaults match the EVIDENCE pipeline (PROCESSED_ORIGINALS,
OUTBOX/00_UNTOUCHED, OUTBOX/BY_* shelves, CANONIZATION). Override with the
--*-dirs options if another API folder names things differently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

TEXT_EXT = {".md", ".txt", ".html", ".htm"}
HASH_TAIL = re.compile(r"_[0-9a-f]{8}$")
MARKER_RE = re.compile(rb"<!-- ===== ORIGINAL ARTICLE BELOW - UNCHANGED sha256=([0-9a-f]{64}) ===== -->\r?\n")


def log(msg):
    print(f"[paper-sort] {msg}", flush=True)


def robocopy(src, dst, extra=()):
    """Run robocopy through a temp .bat so Git Bash / MSYS never mangles UNC paths."""
    bat = Path(tempfile.gettempdir()) / "paper_sort_robo.bat"
    log_file = Path(dst).parent / "_robocopy.log"
    bat.write_text(
        f'@echo off\r\nrobocopy "{src}" "{dst}" /S /XJ /R:2 /W:5 /NP '
        f'/LOG:"{log_file}" {" ".join(extra)}\r\nexit /b 0\r\n'
    )
    log(f"robocopy {src} -> {dst}")
    r = subprocess.run(["cmd", "/c", str(bat)], capture_output=True)
    if r.returncode not in (0, 1):  # robocopy: 0/1 = success
        raise RuntimeError(f"robocopy exited {r.returncode}; see {log_file}")
    return log_file


def canon_name(path: Path) -> str:
    stem = HASH_TAIL.sub("", path.stem)
    if stem.endswith("_"):
        stem = stem[:-1]
    return stem + path.suffix.lower()


def best_path(paths):
    return sorted(paths, key=lambda p: (bool(HASH_TAIL.search(Path(p).stem)), len(p)))[0]


class Sorter:
    def __init__(self, args):
        self.args = args
        self.root = Path(args.work) / "SRC"
        self.staging = Path(args.work) / "STAGING"
        self.by_hash = defaultdict(list)

    # -- step 1: mirror -----------------------------------------------------
    def mirror(self):
        if self.args.no_mirror:
            log(f"--no-mirror: using existing {self.root}")
            return
        robocopy(self.args.source, self.root)

    # -- step 2: census -----------------------------------------------------
    def role(self, rel: str) -> str:
        comps = set(Path(rel).parts)
        if "MERGED_WITH_ORIGINAL" in comps:
            return "merged_existing"  # derived output; never staged as source
        if comps & set(self.args.canon_dirs):
            return "canonization"
        if comps & set(self.args.original_dirs):
            return "original"
        if comps & set(self.args.untouched_dirs):
            return "untouched"
        if "OUTBOX" in comps:
            return "api_sheet"
        return "other"

    def census(self):
        n = 0
        excl = set(self.args.exclude_dirs)
        for p in self.root.rglob("*"):
            if not (p.is_file() and p.suffix.lower() in TEXT_EXT):
                continue
            if excl & set(p.relative_to(self.root).parts):
                continue
            n += 1
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            self.by_hash[h].append(str(p.relative_to(self.root)))
        dup = sum(len(v) for v in self.by_hash.values()) - len(self.by_hash)
        log(f"census: {n} text files, {len(self.by_hash)} unique documents, {dup} duplicate copies")
        out = Path(self.args.work) / "paper_census.json"
        out.write_text(json.dumps(self.by_hash, indent=1), encoding="utf-8")
        self.census_path = out

    # -- step 3: stage ------------------------------------------------------
    def claim_name(self, name: str, h: str) -> str:
        """Case-insensitive name claim: Windows filesystems collapse case, so
        'WHY_X.md' and 'Why_X.md' are the same slot even though Python sees two."""
        if name.lower() in self.used:
            stem, suffix = name.rsplit(".", 1)
            name = f"{stem}__{h[:8]}.{suffix}"
        self.used.add(name.lower())
        return name

    def stage_group(self, hashes, dest_name):
        dest = self.staging / dest_name
        dest.mkdir(parents=True, exist_ok=True)
        staged = 0
        for h in sorted(hashes):
            src = self.root / best_path(self.by_hash[h])
            name = self.claim_name(canon_name(src), h)
            shutil.copy2(src, dest / name)
            staged += 1
        return staged

    def stage(self):
        self.used = set()  # lowercased names — see claim_name
        orig, untouched, canon = set(), set(), set()
        for h, paths in self.by_hash.items():
            roles = {self.role(p) for p in paths}
            if "canonization" in roles:
                canon.add(h)
            if "original" in roles:
                orig.add(h)
            if "untouched" in roles:
                untouched.add(h)
        orig -= canon
        untouched -= orig | canon

        n_o = self.stage_group(orig, "ORIGINALS")
        n_u = self.stage_group(untouched, "UNTOUCHED")
        n_c = self.stage_group(canon, "CANONIZATION_GOD_IS") if canon else 0
        log(f"staged: {n_o} originals, {n_u} untouched, {n_c} canonization")

    # -- step 4: merge ------------------------------------------------------
    def merge(self):
        scripts = list(self.root.rglob("api_original_merge.py"))
        stack = list(self.root.rglob("article_stack.py"))
        if not scripts or not stack:
            log("no api_original_merge.py/article_stack.py in source — skipping merge step")
            return
        # prefer the deepest copy (real script over wrappers lives next to article_stack)
        sdir = next(s.parent for s in scripts if s.parent in {q.parent for q in stack})
        evidence_root = sdir.parent
        log(f"running folder's own merge machinery: {sdir}")
        r = subprocess.run([sys.executable, str(sdir / "api_original_merge.py")],
                           capture_output=True, text=True, cwd=sdir)
        log((r.stdout or r.stderr).strip().splitlines()[-1])

        merged_src = evidence_root / "OUTBOX" / "MERGED_WITH_ORIGINAL"
        groups = defaultdict(list)
        for p in merged_src.rglob("*.md"):
            groups[hashlib.sha256(p.read_bytes()).hexdigest()].append(p)
        dest = self.staging / "MERGED"
        dest.mkdir(parents=True, exist_ok=True)
        ok = bad = 0
        for h, ps in groups.items():
            best = sorted(ps, key=lambda p: (0 if "FOR_SUBSTACK" in p.parts else 1, len(str(p))))[0]
            name = self.claim_name(best.name, h)
            raw = best.read_bytes()
            m = MARKER_RE.search(raw)
            if m and hashlib.sha256(raw[m.end():]).hexdigest() == m.group(1).decode():
                ok += 1
            else:
                bad += 1
            shutil.copy2(best, dest / name)
        log(f"MERGED: {ok} unique documents byte-verified" + (f", {bad} FAILED verification" if bad else ""))
        reps = sorted(merged_src.glob("_MERGE_REPORT_*.csv"))
        if reps:
            (self.staging / "_REPORTS").mkdir(exist_ok=True)
            shutil.copy2(reps[-1], self.staging / "_REPORTS" / "_MERGE_REPORT.csv")

    # -- step 5: push -------------------------------------------------------
    def push(self):
        (self.staging / "_REPORTS").mkdir(exist_ok=True)
        shutil.copy2(self.census_path, self.staging / "_REPORTS" / "paper_census.json")
        if self.args.dry_run:
            log(f"--dry-run: staging left at {self.staging}, nothing pushed")
            return
        robocopy(self.staging, self.args.dest)
        log(f"delivered -> {self.args.dest}")

    def run(self):
        self.mirror()
        self.census()
        self.stage()
        self.merge()
        self.push()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="API pipeline folder to sort (UNC or local)")
    ap.add_argument("--dest", required=True, help="delivery folder (created if needed; never cleaned)")
    ap.add_argument("--work", default=r"D:\paper_sort_work", help="local scratch for mirror+staging")
    ap.add_argument("--no-mirror", action="store_true", help=r"reuse existing <work>\SRC")
    ap.add_argument("--dry-run", action="store_true", help="census + stage only, no push")
    ap.add_argument("--original-dirs", nargs="+", default=["PROCESSED_ORIGINALS", "00_ORIGINALS_PRESERVED", "INBOX"])
    ap.add_argument("--untouched-dirs", nargs="+", default=["00_UNTOUCHED"])
    ap.add_argument("--canon-dirs", nargs="+", default=["CANONIZATION"])
    ap.add_argument("--exclude-dirs", nargs="+",
                    default=["LEAN4", ".lake", ".git", "node_modules", "__pycache__", "SCRIPTS", "LOGS"],
                    help="directory-name components excluded from the census (build trees, code, logs)")
    args = ap.parse_args()
    Sorter(args).run()


if __name__ == "__main__":
    main()
