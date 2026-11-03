#!/usr/bin/env python3
"""filetagger_chi - filetagger + Master Equation classification.

Merges filetagger's fast scanning with chi_classifier's framework vocabulary.
Every file gets classified against G·M·E·S·T·K·R·Q·F·C.

Usage:
  python filetagger_chi.py "O:\\_Theophysics_v4"
  python filetagger_chi.py "D:\\GitHub\\faiththruphysics-site" --sidecar
  python filetagger_chi.py "X:\\folder" --db chi_catalog.db --workers 6
"""
import os, sys, re, hashlib, sqlite3, argparse, datetime
from multiprocessing import Pool, cpu_count
from pathlib import Path

# Add FIS to path for chi_classifier
FIS_DIR = r"D:\DONT TOUCH BOOT UP\FIS"
if FIS_DIR not in sys.path:
    sys.path.insert(0, FIS_DIR)

from chi_classifier import (
    classify_chi_factor, build_chi_vector,
    generate_frontmatter, CHI_FACTORS
)

# ---- config ---------------------------------------------------------------
SIDECAR_EXT  = ".chi"    # custom Theophysics extension — markdown-compatible, unique to this project
SAMPLE_BYTES = 4096
PDF_PAGES    = 2

TEXT_EXTS = {".txt",".md",".markdown",".rst",".csv",".tsv",".log",".json",
             ".yaml",".yml",".html",".htm",".xml",".ini",".cfg",".py",".js",
             ".ts",".css",".bat",".ps1",".sh",".c",".cpp",".h",".java",".sql",
             ".lean",".tex",".bib",".r",".m"}
DOC_EXTS  = {".pdf",".docx"}
SKIP_DIRS = {".git","__pycache__",".venv","node_modules",".obsidian",
             ".next","dist","build","_archive","graveyard"}
SKIP_NAMES= {"thumbs.db","desktop.ini",".ds_store"}

STOP = set("the a an and or of to in is it for on with as by at from this that be are "
    "was were will would can could should i you he she they we not no but if then else "
    "your our their his her its my me us them which who what when where how why all any "
    "some more most other into over under out up down off than too very just have has had "
    "do does did been being about also such only there here".split())
# ---------------------------------------------------------------------------

def human(n):
    n = float(n)
    for u in ("B","KB","MB","GB","TB"):
        if n < 1024 or u == "TB":
            return f"{int(n)} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024

def quick_md5(path, size):
    h = hashlib.md5(str(size).encode())
    with open(path, "rb") as fh:
        h.update(fh.read(65536))
        if size > 131072:
            fh.seek(-65536, os.SEEK_END)
            h.update(fh.read(65536))
    return h.hexdigest()

def tier(ext):
    if ext in TEXT_EXTS: return "text"
    if ext in DOC_EXTS:  return "doc"
    return "blob"

def read_sample(path, ext):
    if ext in TEXT_EXTS:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read(SAMPLE_BYTES)
        except Exception:
            return ""
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            pages = PdfReader(path).pages[:PDF_PAGES]
            return "\n".join((p.extract_text() or "") for p in pages)[:SAMPLE_BYTES]
        except Exception:
            return ""
    if ext == ".docx":
        try:
            import docx
            out, n = [], 0
            for p in docx.Document(path).paragraphs:
                out.append(p.text); n += len(p.text)
                if n >= SAMPLE_BYTES: break
            return "\n".join(out)[:SAMPLE_BYTES]
        except Exception:
            return ""
    return ""

def extract_keywords(text, name):
    """Pull keyword list from text for chi_classifier input."""
    text = (text or "").strip()
    if text:
        words = re.findall(r"[a-z]{3,}", text.lower())
    else:
        words = re.findall(r"[a-z]{3,}", name.lower())
    freq = {}
    for w in words:
        if w in STOP: continue
        freq[w] = freq.get(w, 0) + 1
    return sorted(freq, key=lambda w: (-freq[w], w))[:20]

def when(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

def process_one(job):
    """Scan one file: metadata + chi classification."""
    path, force, sidecar = job
    try:
        st = os.stat(path)
        ext = os.path.splitext(path)[1].lower()
        size = st.st_size
        t = tier(ext)
        sample = read_sample(path, ext) if t != "blob" else ""
        keywords = extract_keywords(sample, os.path.basename(path))
        digest = quick_md5(path, size)

        # ── Chi Classification ──
        chi = classify_chi_factor(keywords, sample, os.path.basename(path))
        primary = chi.get('primary_factor') or 'UC'
        secondary = ','.join(chi.get('secondary_factors', []))
        vector = chi.get('vector', 'G0M0E0S0T0K0R0Q0F0C0')
        confidence = chi.get('confidence', 0)
        chi_role = chi.get('chi_role', '')
        chi_law = chi.get('primary_law', '')

        rec = {
            "path": os.path.abspath(path),
            "name": os.path.basename(path),
            "ext": ext, "size": size, "md5": digest,
            "created": when(st.st_ctime),
            "modified": when(st.st_mtime),
            "accessed": when(st.st_atime),
            "keywords": ", ".join(keywords[:8]),
            "tier": t,
            "mtime": st.st_mtime,
            "scanned": when(datetime.datetime.now().timestamp()),
            # Chi fields
            "chi_primary": primary,
            "chi_secondary": secondary,
            "chi_vector": vector,
            "chi_confidence": confidence,
            "chi_role": chi_role,
            "chi_law": chi_law,
        }

        if sidecar:
            body = f"""# file meta (chi-classified)
name: {rec['name']}
path: {rec['path']}
ext: {ext}
size: {human(size)} ({size} bytes)
md5: {digest}
created: {rec['created']}
modified: {rec['modified']}
chi_primary: {primary} ({chi.get('primary_name', '')})
chi_secondary: [{secondary}]
chi_vector: {vector}
chi_confidence: {confidence}%
chi_law: {chi_law}
chi_role: {chi_role}
keywords: {rec['keywords']}
tier: {t}
scanned: {rec['scanned']}
"""
            with open(path + SIDECAR_EXT, "w", encoding="utf-8") as fh:
                fh.write(body)

        return ("done", rec)
    except Exception as e:
        return ("error", f"{path} :: {e}")

# ── Schema ──
SCHEMA = """CREATE TABLE IF NOT EXISTS files(
  path TEXT PRIMARY KEY, name TEXT, ext TEXT, size INTEGER, md5 TEXT,
  created TEXT, modified TEXT, accessed TEXT, keywords TEXT, tier TEXT,
  mtime REAL, scanned TEXT,
  chi_primary TEXT, chi_secondary TEXT, chi_vector TEXT,
  chi_confidence REAL, chi_role TEXT, chi_law TEXT)"""

COLS = ("path","name","ext","size","md5","created","modified","accessed",
        "keywords","tier","mtime","scanned",
        "chi_primary","chi_secondary","chi_vector",
        "chi_confidence","chi_role","chi_law")

# ── Indexes for fast chi queries ──
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_chi_primary ON files(chi_primary)",
    "CREATE INDEX IF NOT EXISTS idx_chi_vector ON files(chi_vector)",
    "CREATE INDEX IF NOT EXISTS idx_chi_confidence ON files(chi_confidence)",
    "CREATE INDEX IF NOT EXISTS idx_ext ON files(ext)",
    "CREATE INDEX IF NOT EXISTS idx_tier ON files(tier)",
]

def print_chi_summary(db_path):
    """Print Master Equation distribution from the catalog."""
    db = sqlite3.connect(db_path)
    print(f"\n{'='*60}")
    print(f"  CHI FACTOR DISTRIBUTION -- {db_path}")
    print(f"  chi = G * M * E * S * T * K * R * Q * F * C")
    print(f"{'='*60}")
    for row in db.execute(
        "SELECT chi_primary, COUNT(*), ROUND(AVG(chi_confidence),1) "
        "FROM files WHERE chi_primary IS NOT NULL "
        "GROUP BY chi_primary ORDER BY COUNT(*) DESC"
    ):
        factor, count, avg_conf = row
        name = CHI_FACTORS.get(factor, {}).get('name', '?')
        print(f"  [{factor:3s}] {name:<28s}  {count:5d} files  avg {avg_conf}%")
    total = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    unclass = db.execute(
        "SELECT COUNT(*) FROM files WHERE chi_primary IS NULL OR chi_primary = 'UC'"
    ).fetchone()[0]
    print(f"\n  Total: {total} | Classified: {total-unclass} | Unclassified: {unclass}")
    print(f"{'='*60}\n")
    db.close()

def main():
    ap = argparse.ArgumentParser(
        description="Catalog files with Master Equation chi classification.")
    ap.add_argument("path", nargs="?")
    ap.add_argument("--path", dest="path_opt")
    ap.add_argument("--db", default="chi_catalog.db")
    ap.add_argument("--workers", type=int,
                    default=max(1, cpu_count() - 1))
    ap.add_argument("--sidecar", action="store_true",
                    help="Write .fmeta sidecars with chi classification")
    ap.add_argument("--force", action="store_true",
                    help="Re-scan everything, ignore incremental cache")
    ap.add_argument("--summary", action="store_true",
                    help="Print chi distribution from existing DB and exit")
    a = ap.parse_args()

    if a.summary:
        print_chi_summary(a.db)
        return

    root = a.path_opt or a.path
    if not root or not os.path.isdir(root):
        ap.error('give a folder, e.g.  python filetagger_chi.py "O:\\_Theophysics_v4"')

    db = sqlite3.connect(a.db)
    db.execute(SCHEMA)
    for idx in INDEXES:
        db.execute(idx)
    db.commit()
    db_name = os.path.basename(a.db)

    seen = {}
    if not a.force:
        seen = {r[0]: r[1] for r in db.execute("SELECT path, mtime FROM files")}

    jobs, unchanged = [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if (f.endswith(SIDECAR_EXT) or f.endswith('.fmeta')
                    or f.lower() in SKIP_NAMES or f == db_name):
                continue
            p = os.path.join(dirpath, f)
            try:
                mt = os.path.getmtime(p)
            except OSError:
                continue
            if (not a.force
                    and abs(seen.get(os.path.abspath(p), -1) - mt) < 1e-6):
                unchanged += 1
                continue
            jobs.append((p, a.force, a.sidecar))

    total = len(jobs)
    print(f"{total} files to chi-classify | {unchanged} unchanged | "
          f"{a.workers} workers")
    if total == 0:
        print("Nothing new to scan.")
        print_chi_summary(a.db)
        return

    done = err = 0
    batch = []
    ins = f"INSERT OR REPLACE INTO files VALUES ({','.join('?' * len(COLS))})"

    with Pool(a.workers) as pool:
        for i, (status, rec) in enumerate(
                pool.imap_unordered(process_one, jobs, chunksize=8), 1):
            if status == "error":
                err += 1
                print("  ERROR:", rec)
                continue
            done += 1
            batch.append(tuple(rec[c] for c in COLS))
            if len(batch) >= 500:
                db.executemany(ins, batch)
                db.commit()
                batch.clear()
            if i % 500 == 0 or i == total:
                print(f"  {i}/{total}  (classified {done}, errors {err})")

    if batch:
        db.executemany(ins, batch)
        db.commit()
    db.close()

    print(f"\ndone: {done} chi-classified | {unchanged} unchanged | "
          f"{err} errors -> {os.path.abspath(a.db)}")
    print_chi_summary(a.db)


if __name__ == "__main__":
    main()
