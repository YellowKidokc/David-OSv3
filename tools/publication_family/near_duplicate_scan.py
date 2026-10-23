"""
FIS NEAR-DUPLICATE + FAMILY SCANNER  v1.0
==========================================
POF 2828 / David-OS File Intelligence System
Built: 2026-07-09 (Fable) — replaces the degenerate cosine layer in
fis_cross_folder_scan.py.

Three layers, each catching what the others miss:

  L0  EXACT       SHA-256 on raw bytes. Identical copies.
  L1  NEAR-DUP    MinHash + LSH on *shell-stripped, normalized* content
                  shingles. Same article, edited/reformatted/converted
                  (html vs md, minor revisions).
  L2  FAMILY      Normalized-slug grouping. Reader-level variants
                  (easy / college / academic / clean / hash-suffixed)
                  of the same article, even when the text barely overlaps.

Outputs (to --out, default .\\fis_neardup_output):
  exact_dups.csv        hash, paths, canonical-owner recommendation
  near_dups.csv         cluster id, jaccard estimate, paths, owner rec
  families.csv          family stem, member paths, detected variants
  scan_errors.log       unreadable / vanished / too-long paths (never fatal)
  move_plan_DRAFT.ps1   move-and-tombstone script. NEVER auto-runs.
                        Review by hand. Tombstones, not deletions.

Usage:
  pip install datasketch
  python near_duplicate_scan.py --roots "D:\\GitHub\\siteA" "D:\\GitHub\\siteB"
  python near_duplicate_scan.py --roots "D:\\corpus" --threshold 0.7 --out D:\\scans\\run1

Canonical-owner rule (move-and-tombstone discipline):
  1. Repo priority order in REPO_PRIORITY (destination repo wins).
  2. Tie -> newest mtime.
  3. Everything else becomes a tombstone candidate in the draft plan.
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

try:
    from datasketch import MinHash, MinHashLSH
except ImportError:
    print("datasketch not installed.  Run:  pip install datasketch")
    sys.exit(1)

# ---------------------------------------------------------------- config

DEFAULT_ROOTS = []  # Explicit roots are required; never scan historical drives implicitly.

# Lower index = higher authority. The destination repo wins ownership ties.
REPO_PRIORITY = [
    "faiththruphysics-site",              # canonical destination repo
    "faiththruphysics-site-v2-lean-deploy",
    "faiththruphysics-site-v2",
    "faiththruphysics-site-v2-fresh",
    "faiththruphysics-site-data",
    "faiththruphysics-site_backup",
    "Faith-Thru-Physics-Lean-4-",
]

EXTS = {".md", ".html", ".htm", ".txt"}
MAX_FILE_SIZE = 8 * 1024 * 1024          # 8 MB cap per file
MIN_WORDS = 40                            # below this, content too thin to fingerprint
SHINGLE_WORDS = 5                         # 5-word shingles
NUM_PERM = 128                            # MinHash permutations
SKIP_DIR_PARTS = {".git", "node_modules", "__pycache__", ".obsidian",
                  "assets", "audio", "img", "images", "fonts", "css", "js"}

# Reader-level / generation suffixes stripped for family stems.
VARIANT_SUFFIXES = [
    "easy", "college", "academic", "phd", "high-school", "highschool",
    "clean", "final", "old", "new", "v2", "v3", "draft", "backup", "copy",
    "lossless", "summary", "index",
]
HASH_SUFFIX_RE = re.compile(r"[-_][0-9a-f]{8,12}$")           # -4ed68ac407
DATE_SUFFIX_RE = re.compile(r"[-_]\d{8}(?:[-_]\d{4,6})?$")    # -20260604_204547

# ---------------------------------------------------------- path handling

def longpath(p: str) -> str:
    """Windows long-path prefix. Fixes the >260-char crashes from the
    Evidence_Bundles nesting."""
    p = os.path.abspath(p)
    if os.name == "nt" and not p.startswith("\\\\?\\"):
        if p.startswith("\\\\"):                 # UNC
            return "\\\\?\\UNC" + p[1:]
        return "\\\\?\\" + p
    return p


def repo_of(path: str) -> str:
    for name in REPO_PRIORITY:
        if name.lower() in path.lower():
            return name
    return "unknown"


def repo_rank(path: str) -> int:
    r = repo_of(path)
    return REPO_PRIORITY.index(r) if r in REPO_PRIORITY else 99

# ------------------------------------------------------ content pipeline

TAG_SCRIPT_RE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
TAG_SHELL_RE = re.compile(
    r"<(nav|header|footer|aside)\b.*?</\1>", re.S | re.I)
TAG_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
TAG_ANY_RE = re.compile(r"<[^>]+>")
FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.S)
WS_RE = re.compile(r"\s+")
WORD_RE = re.compile(r"[a-z0-9']+")


def extract_text(raw: str, ext: str) -> str:
    """Strip the shell so pages compare on article text, not template.
    This is the fix for the 153M-pair blowup: shared topbar/nav/CSS made
    every page look like every other page."""
    if ext in (".html", ".htm"):
        raw = TAG_SCRIPT_RE.sub(" ", raw)
        raw = TAG_SHELL_RE.sub(" ", raw)
        raw = TAG_COMMENT_RE.sub(" ", raw)
        raw = TAG_ANY_RE.sub(" ", raw)
    elif ext == ".md":
        raw = FRONTMATTER_RE.sub("", raw)
        raw = TAG_COMMENT_RE.sub(" ", raw)
        raw = TAG_ANY_RE.sub(" ", raw)     # md files often embed html
    return WS_RE.sub(" ", raw).strip().lower()


def shingles(text: str):
    words = WORD_RE.findall(text)
    if len(words) < MIN_WORDS:
        return None
    n = SHINGLE_WORDS
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def minhash_of(shingle_set) -> MinHash:
    m = MinHash(num_perm=NUM_PERM)
    for s in shingle_set:
        m.update(s.encode("utf-8"))
    return m

# --------------------------------------------------------- family stems

def family_stem(path: str) -> str:
    """Normalize a filename into its article-family stem.
    drv-02-the-lock-easy.html, drv-02-the-lock-academic.md,
    drv-02-the-lock-4ed68ac407/  ->  'drv-02-the-lock'."""
    stem = Path(path).stem.lower()
    # also consider the parent dir name for index.html inside slug folders
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


def detect_variant(path: str) -> str:
    s = Path(path).stem.lower()
    for suf in VARIANT_SUFFIXES:
        if s.endswith(("-" + suf, "_" + suf, "." + suf)):
            return suf
    if HASH_SUFFIX_RE.search(s):
        return "hash-gen"
    return "base"


def normalized_core_fingerprint(raw: str, ext: str) -> str | None:
    """Stable hash of visible article text, excluding common page shell."""
    core = extract_text(raw, ext)
    if len(WORD_RE.findall(core)) < MIN_WORDS:
        return None
    return hashlib.sha256(core.encode("utf-8", "ignore")).hexdigest()


def presentation_features(raw: str, path: str, roots: list[str]) -> dict:
    """Score visible publication affordances, never content quality or truth."""
    lower = raw.lower()
    checks = {
        "topbar": ("topbar", "site-header", "<nav", "navbar", "main-nav"),
        "audio": ("<audio", ".mp3", "audio-dock", "audio-player", "data-audio"),
        "canonical_formatting": ("rel=\"canonical\"", "rel='canonical'", "canonical", "data-canonical", "canon-status"),
        "reading_layers": ("reading-layer", "reader-layer", "data-layer", "layer-toggle", "proof-layer"),
    }
    present = {name: any(marker in lower for marker in markers) for name, markers in checks.items()}
    root = next((item for item in roots if path.lower().startswith(os.path.abspath(item).lower())), "")
    relative = os.path.relpath(path, root) if root else path
    depth = max(0, len(Path(relative).parts) - 1)
    score = sum(2 for value in present.values() if value)
    return {
        **present,
        "richness_score": score,
        "root": root,
        "relative_path": relative,
        "nesting_depth": depth,
        "buried": depth >= 4,
    }

# ------------------------------------------------------------ union-find

class UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra

# ---------------------------------------------------------------- scan

def walk_files(roots, errlog):
    for root in roots:
        if not os.path.isdir(root):
            errlog.write(f"MISSING ROOT\t{root}\n")
            continue
        for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: errlog.write(f"WALK\t{e}\n")):
            dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIR_PARTS]
            for fn in filenames:
                if Path(fn).suffix.lower() in EXTS:
                    yield os.path.join(dirpath, fn)


def canonical_owner(paths):
    """Pick the file the group should keep: repo priority, then newest."""
    def key(p):
        try:
            mt = os.stat(longpath(p)).st_mtime
        except OSError:
            mt = 0
        return (repo_rank(p), -mt)
    return sorted(paths, key=key)[0]


def run(roots, threshold, outdir):
    os.makedirs(outdir, exist_ok=True)
    errlog = open(os.path.join(outdir, "scan_errors.log"), "w", encoding="utf-8")
    t0 = time.time()

    sha_groups = defaultdict(list)          # sha256 -> [paths]
    hashes = {}                             # path -> MinHash
    fams = defaultdict(list)                # stem -> [paths]
    file_meta = {}                           # path -> core hash + presentation facts
    scanned = fingerprinted = 0

    print("=" * 68)
    print("FIS NEAR-DUP + FAMILY SCAN   threshold=%.2f   perms=%d" % (threshold, NUM_PERM))
    print("=" * 68)

    lsh = MinHashLSH(threshold=threshold, num_perm=NUM_PERM)

    for path in walk_files(roots, errlog):
        scanned += 1
        lp = longpath(path)
        try:
            st = os.stat(lp)
            if st.st_size > MAX_FILE_SIZE or st.st_size == 0:
                continue
            raw = open(lp, "r", encoding="utf-8", errors="ignore").read()
        except OSError as e:
            errlog.write(f"READ\t{path}\t{e}\n")
            continue

        sha_groups[hashlib.sha256(raw.encode("utf-8", "ignore")).hexdigest()].append(path)
        fams[family_stem(path)].append(path)
        file_meta[path] = {
            "core_fingerprint": normalized_core_fingerprint(raw, Path(path).suffix.lower()),
            **presentation_features(raw, path, roots),
        }

        sh = shingles(extract_text(raw, Path(path).suffix.lower()))
        if sh:
            mh = minhash_of(sh)
            hashes[path] = mh
            lsh.insert(path, mh)
            fingerprinted += 1

        if scanned % 2000 == 0:
            print(f"  scanned {scanned:>7}   fingerprinted {fingerprinted:>7}   {time.time()-t0:6.0f}s")

    print(f"  scanned {scanned}   fingerprinted {fingerprinted}   ({time.time()-t0:.0f}s)")

    # ---- L0 exact
    exact = {h: ps for h, ps in sha_groups.items() if len(ps) > 1}

    # ---- L1 near-dup clustering via LSH + union-find
    uf = UF()
    for path, mh in hashes.items():
        for other in lsh.query(mh):
            if other != path:
                uf.union(path, other)
    clusters = defaultdict(list)
    for path in hashes:
        clusters[uf.find(path)].append(path)
    near = {k: v for k, v in clusters.items() if len(v) > 1}

    # drop near-dup clusters that are purely exact-dup groups (already in L0)
    exact_sets = {frozenset(ps) for ps in exact.values()}
    near = {k: v for k, v in near.items() if frozenset(v) not in exact_sets}

    # ---- L2 families (cross-file only, and only multi-member)
    families = {s: ps for s, ps in fams.items() if len(set(ps)) > 1 and s}

    # Content groups are the semantic-core layer used for review: the MinHash
    # connected components include near copies and normalized-core exact copies.
    content_groups = {key: paths for key, paths in clusters.items() if len(paths) > 1}

    # ------------------------------------------------------------ write
    with open(os.path.join(outdir, "exact_dups.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sha256_16", "count", "keep", "path", "repo"])
        for h, ps in sorted(exact.items(), key=lambda kv: -len(kv[1])):
            keep = canonical_owner(ps)
            for p in ps:
                w.writerow([h[:16], len(ps), "KEEP" if p == keep else "", p, repo_of(p)])

    with open(os.path.join(outdir, "near_dups.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cluster", "size", "est_jaccard_to_owner", "keep", "path", "repo"])
        for i, (root, ps) in enumerate(sorted(near.items(), key=lambda kv: -len(kv[1]))):
            keep = canonical_owner(ps)
            for p in ps:
                jac = hashes[p].jaccard(hashes[keep]) if p != keep else 1.0
                w.writerow([i, len(ps), f"{jac:.3f}", "KEEP" if p == keep else "", p, repo_of(p)])

    with open(os.path.join(outdir, "families.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["family_stem", "size", "variant", "path", "repo"])
        for stem, ps in sorted(families.items(), key=lambda kv: -len(kv[1])):
            for p in sorted(set(ps)):
                w.writerow([stem, len(set(ps)), detect_variant(p), p, repo_of(p)])

    # ---- content group + presentation richness review (report-only)
    richness_groups = []
    for number, (_, paths) in enumerate(sorted(content_groups.items(), key=lambda item: -len(item[1])), 1):
        members = []
        for path in sorted(paths, key=lambda item: (-file_meta[item]["richness_score"], file_meta[item]["nesting_depth"], item.lower())):
            meta = file_meta[path]
            members.append({
                "path": path,
                "core_fingerprint": meta["core_fingerprint"],
                "variant": detect_variant(path),
                "repo": repo_of(path),
                "presentation": {key: meta[key] for key in ("topbar", "audio", "canonical_formatting", "reading_layers")},
                "richness_score": meta["richness_score"],
                "relative_path": meta["relative_path"],
                "nesting_depth": meta["nesting_depth"],
                "buried": meta["buried"],
            })
        richest = members[0]
        richness_groups.append({
            "group_id": f"CORE-{number:04d}",
            "member_count": len(members),
            "recommended_review_candidate": richest["path"],
            "recommended_candidate_reason": "Highest observable presentation-richness score; ties use shallower path then name.",
            "buried_members": [member["path"] for member in members if member["buried"]],
            "members": members,
        })

    with open(os.path.join(outdir, "content_richness_groups.json"), "w", encoding="utf-8") as f:
        json.dump({"boundary": "Presentation ranking only; no source is moved or promoted.", "groups": richness_groups}, f, indent=2)
    with open(os.path.join(outdir, "content_richness_groups.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group_id", "member_count", "review_candidate", "richness_score", "topbar", "audio", "canonical_formatting", "reading_layers", "buried", "nesting_depth", "variant", "path"])
        for group in richness_groups:
            for member in group["members"]:
                present = member["presentation"]
                w.writerow([group["group_id"], group["member_count"], member["path"] == group["recommended_review_candidate"], member["richness_score"], present["topbar"], present["audio"], present["canonical_formatting"], present["reading_layers"], member["buried"], member["nesting_depth"], member["variant"], member["path"]])

    with open(os.path.join(outdir, "flattening_plan_PROPOSED.md"), "w", encoding="utf-8") as f:
        f.write("# Proposed Content Flattening Plan\n\n")
        f.write("This is a review plan, not a file operation. No originals were moved, renamed, or deleted.\n\n")
        f.write(f"- Content groups needing review: `{len(richness_groups)}`\n")
        f.write(f"- Groups with buried members: `{sum(bool(group['buried_members']) for group in richness_groups)}`\n\n")
        f.write("## Review Order\n\n")
        for group in richness_groups:
            candidate = group["recommended_review_candidate"]
            buried = len(group["buried_members"])
            f.write(f"- `{group['group_id']}` ({group['member_count']} members): review `{candidate}` as the presentation candidate; buried copies: `{buried}`.\n")
        f.write("\n## Human Approval Gate\n\n")
        f.write("For each group: verify source lineage and content differences; select one canonical presentation target; stage copies or redirects; approve any move separately.\n")

    # ---- move-and-tombstone DRAFT (exact dups only; never auto-run)
    with open(os.path.join(outdir, "move_plan_DRAFT.ps1"), "w", encoding="utf-8") as f:
        f.write("# FIS MOVE-AND-TOMBSTONE DRAFT — REVIEW BY HAND. NOTHING RUNS ITSELF.\n")
        f.write("# Policy: exact duplicates only. Non-canonical copy is REPLACED by a\n")
        f.write("# .tombstone.txt pointing at the canonical path. Content is never deleted\n")
        f.write("# here — the canonical copy holds it.\n\n")
        for h, ps in exact.items():
            keep = canonical_owner(ps)
            for p in ps:
                if p == keep:
                    continue
                f.write(f"# dup of: {keep}\n")
                f.write(f"# Remove-Item -LiteralPath '{p}'\n")
                f.write(f"# Set-Content -LiteralPath '{p}.tombstone.txt' "
                        f"-Value 'MOVED-CANONICAL: {keep}  ({time.strftime('%Y-%m-%d')})'\n\n")

    errlog.close()
    print("-" * 68)
    print(f"L0 exact-dup groups : {len(exact):>7}")
    print(f"L1 near-dup clusters: {len(near):>7}")
    print(f"L2 article families : {len(families):>7}")
    print(f"Core content groups : {len(content_groups):>7}")
    print(f"outputs -> {outdir}")
    print("move_plan_DRAFT.ps1 is fully commented out. Review, uncomment, run — in that order.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="FIS near-duplicate + family scanner")
    ap.add_argument("--roots", nargs="+", required=True,
                    help="One or more explicit corpus roots. Sources are read-only.")
    ap.add_argument("--threshold", type=float, default=0.7,
                    help="LSH Jaccard threshold for near-dup (0.7 = same article, edited)")
    ap.add_argument("--out", default=os.path.join(os.getcwd(), "fis_neardup_output"))
    a = ap.parse_args()
    run(a.roots, a.threshold, a.out)
