#!/usr/bin/env python3
"""fis_canon_scan.py - Canonization dispersal + scan. POF 2828 | August 2026

The canon loop:
  1. David edits ONE central registry: D:\\GitHub\\David-OS\\system\\canon_rules.json
     ("the master equation should be X", "Law 7 = Quantum", grammar rulings...)
  2. This script disperses those rulings into every scanned folder's .fisnote,
     in a CANONIZATION section below a divider line (so the folder itself
     tells any human or AI what canon is in force).
  3. It scans the folder's text files against the rulings, two layers:
       - regex layer (free, deterministic, always on)
       - NLP layer (--nlp): sends suspect paragraphs to the local :8700
         claim-stack server (/nlp/contradiction) with the canonical statement
         as hypothesis; flags semantic contradictions regex can't see.
  4. It writes a WANTED-vs-WRITTEN review report (md + json) to
     <target>/09_TO_REVIEW/. REPORT ONLY - this script NEVER edits content
     files. Humans (or a later approved pass) make the changes.

Usage:
  python fis_canon_scan.py <folder> [--nlp] [--depth N] [--no-fisnote]
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, re, sys
from pathlib import Path

try:
    from engine.path_write_policy import fisnote_write_allowed
except ModuleNotFoundError:  # direct `python engine/canon_scan.py ...` launch
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from engine.path_write_policy import fisnote_write_allowed

REGISTRY = Path(r"D:\GitHub\David-OS\system\canon_rules.json")
NLP_URL = "http://localhost:8700/nlp/contradiction"
NLP_MODEL = "contradiction_fast"   # fast DeBERTa; use contradiction_primary for final passes
NLP_THRESHOLD = 0.60          # contradiction prob -> CONTRADICTION alert
NLP_GRAY_LOW = 0.40           # 0.40-0.60 -> NEEDS_CANON_DECISION (registry underspecified,
                              # not clearly wrong; David has to rule, not the scanner)
NLP_MAX_CHARS = 1200          # premise truncation
NLP_PROSE_EXTS = {".md", ".txt", ".html", ".htm"}   # NLP layer: prose only (regex still covers code)
NLP_MIN_WORDS = 25            # skip trivial paragraphs
NLP_MAX_CALLS_PER_FILE = 15   # cap per file, longest keyword-hits first
_NLP_CACHE = {}               # (md5(para), rule_id) -> prob; corpus is duplicate-heavy
MARKER = ".fisnote"
DIVIDER = "<!-- FIS-CANON-DIVIDER : everything below is written by fis_canon_scan.py -->"

SCAN_EXTS = {".md", ".html", ".txt", ".py", ".js", ".json", ".tex"}
SKIP_DIRS = {"99_ARCHIVE", "_EXCESS_ARCHIVE", "__pycache__", ".git", "node_modules",
             ".claude", ".obsidian", "09_TO_REVIEW", ".lake", "$recycle.bin"}
EXEMPT_FRAGMENTS = ("canon_gate", "canon_ruling", "canon_scan", "migration_status",
                    "where_the_fruits_live", "fisnote", "canon_rules",
                    "july_29_master_equation_canon_packet",
                    "master_equation_unified_2026-07-29")


def now_iso(): return dt.datetime.now().isoformat(timespec="seconds")


DEFINITIONS = REGISTRY.parent / "definitions_registry.json"

def load_registry():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rulings = [r for r in data.get("rulings", []) if r.get("status", "binding") != "retired"]
    # merge the definitions database: each definition scans exactly like a ruling
    if DEFINITIONS.exists():
        defs = json.loads(DEFINITIONS.read_text(encoding="utf-8")).get("definitions", [])
        have = {r["id"] for r in rulings}
        for de in defs:
            if de.get("status", "binding") == "retired" or de["id"] in have:
                continue
            rulings.append({"id": de["id"], "title": de.get("term", de["id"]),
                "version": de.get("version", "?"), "status": de.get("status", "binding"),
                "statement": de.get("canonical_statement", ""),
                "source_ruling": de.get("source_ruling", ""),
                "severity": de.get("severity", "review"),
                "patterns": de.get("patterns", []),
                "nlp_keywords": de.get("nlp_keywords", [])})
    for r in rulings:
        r["_compiled"] = [(re.compile(p["regex"], re.IGNORECASE), p) for p in r.get("patterns", [])]
        r["_kw"] = [k.lower() for k in r.get("nlp_keywords", [])]
    return data, rulings


def iter_files(root: Path, depth):
    for dirpath, dirnames, filenames in os.walk(root):
        cur = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        if depth is not None and len(cur.relative_to(root).parts) >= depth:
            dirnames[:] = []
        for fn in filenames:
            if Path(fn).suffix.lower() not in SCAN_EXTS:
                continue
            base = fn.lower()
            if any(f in base for f in EXEMPT_FRAGMENTS):
                continue
            yield cur / fn


def nlp_contradiction(premise: str, hypothesis: str):
    """Returns contradiction probability via :8700, or None if server unreachable."""
    import urllib.request
    body = json.dumps({"premise": premise[:NLP_MAX_CHARS], "hypothesis": hypothesis, "model": NLP_MODEL}).encode()
    req = urllib.request.Request(NLP_URL, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            out = json.loads(resp.read())
        scores = {k.lower(): v for k, v in out.get("scores", {}).items()}
        return scores.get("contradiction")
    except Exception:
        return None


def paragraphs(text: str):
    """Yield (start_line, paragraph) blocks."""
    lines = text.splitlines()
    buf, start = [], 1
    for i, ln in enumerate(lines, 1):
        if ln.strip():
            if not buf: start = i
            buf.append(ln)
        elif buf:
            yield start, "\n".join(buf); buf = []
    if buf: yield start, "\n".join(buf)


def scan_file(path: Path, rulings, use_nlp, nlp_state):
    hits = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return hits
    # Layer 1: regex, line by line
    for ln_no, line in enumerate(text.splitlines(), 1):
        for r in rulings:
            for regex, pat in r["_compiled"]:
                if regex.search(line):
                    hits.append({"file": str(path), "line": ln_no, "rule": r["id"],
                        "rule_version": r.get("version", "?"), "verdict": "CONTRADICTION",
                        "layer": "regex", "severity": r.get("severity", "blocker"),
                        "wanted": r["statement"], "written": line.strip()[:240],
                        "message": pat["message"], "next_step": pat["next_step"]})
    # Layer 2: NLP contradiction on keyword-matched paragraphs (prose only, capped, cached)
    if use_nlp and nlp_state["alive"] and path.suffix.lower() in NLP_PROSE_EXTS:
        import hashlib as _hl
        flagged = {(h["line"], h["rule"]) for h in hits}
        cands = []
        for start, para in paragraphs(text):
            if len(para.split()) < NLP_MIN_WORDS: continue
            low = para.lower()
            for r in rulings:
                if not r["_kw"] or not any(k in low for k in r["_kw"]):
                    continue
                if (start, r["id"]) in flagged: continue
                cands.append((sum(low.count(k) for k in r["_kw"]), start, para, r))
        cands.sort(key=lambda x: -x[0])
        for _score, start, para, r in cands[:NLP_MAX_CALLS_PER_FILE]:
            key = (_hl.md5(para.encode()).hexdigest(), r["id"])
            if key in _NLP_CACHE:
                prob = _NLP_CACHE[key]
            else:
                prob = nlp_contradiction(para, r["statement"])
                if prob is None:
                    nlp_state["alive"] = False
                    print("  NLP server stopped answering; continuing regex-only.")
                    break
                _NLP_CACHE[key] = prob
                nlp_state["calls"] += 1
            if True:
                if prob >= NLP_THRESHOLD:
                    hits.append({"file": str(path), "line": start, "rule": r["id"],
                        "rule_version": r.get("version", "?"), "verdict": "CONTRADICTION",
                        "layer": "nlp", "severity": "review", "nlp_contradiction": round(prob, 3),
                        "wanted": r["statement"], "written": para.strip()[:240],
                        "message": f"NLP contradiction {prob:.0%} vs canon statement.",
                        "next_step": "Human review: paragraph semantically conflicts with the ruling."})
                elif prob >= NLP_GRAY_LOW:
                    hits.append({"file": str(path), "line": start, "rule": r["id"],
                        "rule_version": r.get("version", "?"), "verdict": "NEEDS_CANON_DECISION",
                        "layer": "nlp", "severity": "decision", "nlp_contradiction": round(prob, 3),
                        "wanted": r["statement"], "written": para.strip()[:240],
                        "message": f"Gray zone ({prob:.0%}): text is not clearly wrong; the registry may be underspecified here.",
                        "next_step": "David rules: extend/clarify the registry entry, or mark this passage in-canon."})
            if not nlp_state["alive"]:
                break
    return hits


# ---------------- fisnote propagation ----------------

def canon_section(data, rulings, folder: Path, folder_hits, stamp, nlp_used):
    lines = ["", DIVIDER, "", "---", "", "# CANONIZATION",
             "",
             f"> Rulings dispersed from central registry: `{REGISTRY}` "
             f"(registry updated {data.get('updated','?')}; this scan {stamp}; "
             f"layers: regex{' + NLP:8700' if nlp_used else ' only'})",
             "",
             "These rulings are IN FORCE for every file in this folder. A scan flag does",
             "NOT change any file - it only marks WANTED vs WRITTEN for human review.",
             ""]
    for r in rulings:
        lines.append(f"## [{r['id']} v{r.get('version','?')}] {r['title']}  ({r.get('status','binding')}/{r.get('severity','blocker')})")
        lines.append(f"- **Canon:** {r['statement']}")
        lines.append(f"- **Source ruling:** {r.get('source_ruling','')}")
        lines.append("")
    lines.append("## Last Scan Result")
    if not folder_hits:
        lines.append(f"- CLEAN - no canon conflicts in this folder's direct files ({stamp}).")
    else:
        by_file = {}
        for h in folder_hits: by_file.setdefault(Path(h["file"]).name, []).append(h)
        lines.append(f"- **{len(folder_hits)} alert(s)** in {len(by_file)} file(s) - see 09_TO_REVIEW report:")
        for name, hs in sorted(by_file.items()):
            rules = ", ".join(sorted({h['rule'] for h in hs}))
            lines.append(f"  - {name}: {len(hs)} ({rules})")
    lines.append("")
    return "\n".join(lines)


def update_fisnote(folder: Path, section: str):
    marker = folder / MARKER
    inventory = ""
    if marker.exists():
        try: inventory = marker.read_text(encoding="utf-8", errors="ignore")
        except OSError: inventory = ""
        inventory = inventory.split(DIVIDER)[0].rstrip("\n")
    if not inventory:
        inventory = (f"# FIS Inventory: {folder.name}\n\n"
                     "(inventory not yet generated - run fisnote_scan.py)")
    marker.write_text(inventory + "\n" + section, encoding="utf-8", newline="\n")


# ---------------- reports ----------------

def write_reports(target: Path, hits, files_scanned, stamp, nlp_state, use_nlp, data):
    review = target / "09_TO_REVIEW"
    review.mkdir(exist_ok=True)
    md = review / f"CANON_SCAN_{stamp}.md"
    js = review / f"CANON_SCAN_{stamp}.json"
    by_file = {}
    for h in hits: by_file.setdefault(h["file"], []).append(h)
    out = [f"# CANON SCAN - WANTED vs WRITTEN - {stamp}", "",
           f"Registry: `{REGISTRY}` (updated {data.get('updated','?')})",
           f"Files scanned: {files_scanned} | files flagged: {len(by_file)} | alerts: {len(hits)}",
           f"NLP layer: {'ON - ' + str(nlp_state['calls']) + ' contradiction calls' if use_nlp and nlp_state['calls'] else 'off / unavailable (start D:\\GitHub\\BACKSIDE-NLP-NEW\\nlp_api\\RUN.bat)'}",
           "", "**This report changes nothing.** Go line by line; for each item decide:",
           "fix the file, mark it historical/superseded, or exempt it by ruling.", ""]
    if not hits:
        out.append("CANON STATUS: CLEAN")
    for fp in sorted(by_file):
        out.append(f"## {fp}")
        for h in sorted(by_file[fp], key=lambda x: x["line"]):
            tag = f"NLP {h['nlp_contradiction']:.0%}" if h["layer"] == "nlp" else "REGEX"
            verdict = h.get("verdict", "CONTRADICTION")
            out += [f"- L{h['line']} [{h['rule']} v{h.get('rule_version','?')}] {verdict} / {h['severity'].upper()} ({tag}): {h['message']}",
                    f"  - WANTED: {h['wanted']}",
                    f"  - WRITTEN: `{h['written']}`",
                    f"  - Next step: {h['next_step']}"]
        out.append("")
    md.write_text("\n".join(out), encoding="utf-8", newline="\n")
    js.write_text(json.dumps({"stamp": stamp, "registry_updated": data.get("updated"),
        "files_scanned": files_scanned, "alerts": hits}, indent=2, ensure_ascii=False),
        encoding="utf-8", newline="\n")
    return md, js


def main():
    ap = argparse.ArgumentParser(description="Disperse canon rulings into .fisnotes and scan WANTED vs WRITTEN.")
    ap.add_argument("path")
    ap.add_argument("--nlp", action="store_true", help="Use :8700 contradiction model on suspect paragraphs")
    ap.add_argument("--depth", type=int, default=None)
    ap.add_argument("--no-fisnote", action="store_true", help="Report only; don't touch .fisnote files")
    args = ap.parse_args()

    target = Path(args.path).resolve()
    if not target.is_dir(): ap.error(f"Not a folder: {target}")
    data, rulings = load_registry()
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    nlp_state = {"alive": args.nlp, "calls": 0}

    import time as _t
    all_files = list(iter_files(target, args.depth))
    t0 = _t.time()
    hits, files_scanned = [], 0
    for f in all_files:
        files_scanned += 1
        hits.extend(scan_file(f, rulings, args.nlp, nlp_state))
        if files_scanned % 10 == 0 or files_scanned == len(all_files):
            el = _t.time() - t0
            eta = el / files_scanned * (len(all_files) - files_scanned)
            print(f"  [{files_scanned}/{len(all_files)}] {el/60:.1f}m elapsed | ~{eta/60:.0f}m left | "
                  f"{len(hits)} alerts | {nlp_state['calls']} NLP calls", flush=True)

    md, js = write_reports(target, hits, files_scanned, stamp, nlp_state, args.nlp, data)

    allow_fisnotes = fisnote_write_allowed(target)
    if not allow_fisnotes and not args.no_fisnote:
        print("Policy: generated .fisnote writes are disabled globally; canon reports remain enabled.")

    if not args.no_fisnote and allow_fisnotes:
        # propagate canon section into the fisnote of every scanned folder level
        folders = {target}
        for dirpath, dirnames, _ in os.walk(target):
            cur = Path(dirpath)
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            if args.depth is not None and len(cur.relative_to(target).parts) >= args.depth:
                dirnames[:] = []
            folders.add(cur)
        for folder in sorted(folders):
            fh = [h for h in hits if Path(h["file"]).parent == folder]
            update_fisnote(folder, canon_section(data, rulings, folder, fh, stamp, nlp_state["calls"] > 0))

    print(f"Scanned {files_scanned} files | {len(hits)} alerts "
          f"({sum(1 for h in hits if h['layer']=='nlp')} from NLP, {nlp_state['calls']} NLP calls)")
    print(f"Report: {md}")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
