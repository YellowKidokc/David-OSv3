r"""flatten_dedupe.py - scan a folder tree, find exact + near duplicates, and (optionally) build ONE flat markdown folder.

  python flatten_dedupe.py SOURCE OUTDIR            # DRY RUN: writes OUTDIR\MANIFEST.csv + REPORT.md only. Touches nothing.
  python flatten_dedupe.py SOURCE OUTDIR --apply    # also COPIES the keepers into OUTDIR\FLAT\  (source is never modified)

Rules (each decision is written to the manifest with its reason):
  R1 never modify the source; output goes to OUTDIR only
  R2 text files only (.md .markdown .txt); everything else is listed as SKIPPED_TYPE
  R3 skip tool/system folders (.venv*, node_modules, __pycache__, .git, .obsidian, assets, Templates, Python)
  R4 exact duplicate = same text after whitespace normalisation -> keep one (KEEPER rule below), others DUP_EXACT
  R5 near duplicate = fingerprint.near_dup NEAR_DUPLICATE -> keep keeper, other NEAR_DUP_REVIEW (listed, not copied)
     RELATED_VERSION -> both kept, flagged RELATED
  R6 KEEPER rule: not in an archive folder > in a numbered folder (01_...) > shallower path > longer text > newer
  R7 flat name = origin folders joined by '__' + file name (so you always see where it came from)
  R8 folders whose names differ only by numbering/spacing/case are reported as NAME_GROUPS (a report, never an auto-merge)
"""
import csv, hashlib, os, re, sys, shutil
from collections import defaultdict
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fingerprint as fp

TEXT_EXT = {".md", ".markdown", ".txt"}
SKIP_DIRS = {"node_modules", "__pycache__", ".git", ".obsidian", "assets", "templates", "python"}
ARCHIVE_RX = re.compile(r"archive|_old|older|backup|zzz|migration", re.I)

def norm_folder(name):  # R8
    return " ".join(re.sub(r"^\d+[_\-\s.]*", "", name).lower().replace("_", " ").replace("-", " ").split())

def scan(src):
    files, skipped = [], []
    for root, dirs, names in os.walk(src):
        dirs[:] = [d for d in dirs if not d.lower().startswith(".venv") and d.lower() not in SKIP_DIRS]
        for n in names:
            p = os.path.join(root, n); rel = os.path.relpath(p, src); ext = os.path.splitext(n)[1].lower()
            if ext not in TEXT_EXT: skipped.append((rel, "SKIPPED_TYPE")); continue
            try: text = open(p, encoding="utf-8", errors="replace").read()
            except Exception as e: skipped.append((rel, f"UNREADABLE {e}")); continue
            parts = rel.split(os.sep)
            files.append({"rel": rel, "text": text, "norm": " ".join(text.split()),
                          "archive": any(ARCHIVE_RX.search(x) for x in parts[:-1]),
                          "numbered": any(re.match(r"^\d+_", x) for x in parts[:-1]),
                          "depth": len(parts), "mtime": os.path.getmtime(p)})
    return files, skipped

def keeper_key(f):  # R6 - smaller sorts first = better keeper
    return (f["archive"], not f["numbered"], f["depth"], -len(f["norm"]), -f["mtime"])

def flat_name(rel):  # R7
    s = re.sub(r'[<>:"/\\|?*]+', "_", rel.replace(os.sep, "__"))
    if len(s) > 150:
        root, ext = os.path.splitext(s); s = root[:130] + "_" + hashlib.sha1(rel.encode()).hexdigest()[:8] + ext
    return s

def run(src, out, apply=False):
    files, skipped = scan(src); rows = []
    # R4 exact
    by_hash = defaultdict(list)
    for f in files: by_hash[hashlib.sha256(f["norm"].encode()).hexdigest()].append(f)
    survivors = []
    for h, grp in by_hash.items():
        grp.sort(key=keeper_key); survivors.append(grp[0]); grp[0]["status"] = "KEEP"
        for g in grp[1:]: g["status"] = "DUP_EXACT"; g["of"] = grp[0]["rel"]
    # R5 near (candidates by simhash_v2, confirmed by near_dup)
    sh = [(f, fp.simhash_v2(f["text"])) for f in survivors]
    comparable = [(f, s) for f, s in sh if s is not None]
    survivors.sort(key=keeper_key); rank = {id(f): i for i, f in enumerate(survivors)}
    for i in range(len(comparable)):
        for j in range(i + 1, len(comparable)):
            (a, sa), (b, sb) = comparable[i], comparable[j]
            if a["status"] != "KEEP" or b["status"] != "KEEP": continue
            if fp.hamming_v2(sa, sb) > fp.CANDIDATE_HAMMING: continue
            v = fp.near_dup(a["text"], b["text"])
            if v["verdict"] == "NEAR_DUPLICATE":
                win, lose = (a, b) if rank[id(a)] < rank[id(b)] else (b, a)
                lose["status"] = "NEAR_DUP_REVIEW"; lose["of"] = win["rel"]; lose["jaccard"] = v["jaccard"]
            elif v["verdict"] == "RELATED_VERSION":
                for x, y in ((a, b), (b, a)): x.setdefault("related", []).append(f'{y["rel"]} ({v["jaccard"]})')
    for f in files:
        f.setdefault("status", "KEEP")
        if f["status"] == "KEEP" and fp.simhash_v2(f["text"]) is None: f["note"] = "TOO_SHORT_TO_COMPARE"
    # R8 name groups
    groups = defaultdict(set)
    for f in files:
        for part in f["rel"].split(os.sep)[:-1]: groups[norm_folder(part)].add(part)
    name_groups = {k: sorted(v) for k, v in groups.items() if len(v) > 1}
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "MANIFEST.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["status", "path", "flat_name", "same_as / keeper", "jaccard", "related", "archive", "words", "note"])
        for f in sorted(files, key=lambda x: (x["status"], x["rel"])):
            w.writerow([f["status"], f["rel"], flat_name(f["rel"]) if f["status"] == "KEEP" else "", f.get("of", ""),
                        f.get("jaccard", ""), " | ".join(f.get("related", [])), f["archive"], len(fp.content_words(f["text"])), f.get("note", "")])
        for rel, why in skipped: w.writerow([why, rel, "", "", "", "", "", "", ""])
    c = defaultdict(int)
    for f in files: c[f["status"]] += 1
    rep = [f"# Flatten + dedupe report  ({'APPLIED' if apply else 'DRY RUN - nothing copied'})", f"Source: {src}", f"Run: {datetime.now().isoformat(timespec='seconds')}", "",
           f"- text files scanned: {len(files)}", f"- kept: {c['KEEP']}", f"- exact duplicates dropped: {c['DUP_EXACT']}",
           f"- near-duplicates held for review: {c['NEAR_DUP_REVIEW']}", f"- related versions (both kept, flagged): {sum(1 for f in files if f.get('related'))//1}",
           f"- too short to compare (kept): {sum(1 for f in files if f.get('note'))}", f"- non-text / skipped: {len(skipped)}", "",
           "## Folder names that look like the same folder (R8 - report only, check by hand)"]
    rep += [f"- {k}: " + " | ".join(v) for k, v in sorted(name_groups.items())]
    rep += ["", "## Near-duplicates held for review (keeper  <-  held)"]
    rep += [f"- {f['of']}  <-  {f['rel']}  (overlap {f['jaccard']})" for f in files if f["status"] == "NEAR_DUP_REVIEW"]
    open(os.path.join(out, "REPORT.md"), "w", encoding="utf-8").write("\n".join(rep))
    if apply:
        flat = os.path.join(out, "FLAT"); os.makedirs(flat, exist_ok=True)
        for f in files:
            if f["status"] == "KEEP":
                shutil.copy2(os.path.join(src, f["rel"]), os.path.join(flat, flat_name(f["rel"])))
    print("\n".join(rep[:12]))

if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    run(a[0], a[1], "--apply" in sys.argv)
