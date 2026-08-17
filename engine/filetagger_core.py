#!/usr/bin/env python3
"""filetagger - fast, free, fully-local file cataloger.

For every file under a folder it records: name, path, ext, size, MD5,
created / modified / accessed times, and 3 content tags -- into a SQLite
catalog (and optionally a per-file .fmeta sidecar).

Speed model:
  * sampled reads - reads only a small slice of each file to tag it, never
                    the whole document (first ~4 KB of text / first PDF pages)
  * read tiers    - media / binaries are cataloged but not read at all
  * incremental   - files unchanged since the last run are skipped
  * multi-core    - a worker pool does the CPU work; ONE writer owns SQLite

Usage:
  python filetagger.py "X:\\folder"
  python filetagger.py "X:\\folder" --db catalog.db --workers 6
  python filetagger.py "X:\\folder" --sidecar     # also write .fmeta files
  python filetagger.py "X:\\folder" --quickhash   # faster id hash, huge files
  python filetagger.py "X:\\folder" --force        # re-tag everything
"""
import os, re, hashlib, sqlite3, argparse, datetime
from multiprocessing import Pool, cpu_count

# ---- config (edit freely) -------------------------------------------------
SIDECAR_EXT  = ".fmeta"     # not md / not json / not common; markdown-safe body
NUM_TAGS     = 3
SAMPLE_BYTES = 4096         # text read per file for tagging (never the whole doc)
PDF_PAGES    = 2            # PDF pages to sample
CATEGORIES   = []           # your ~20 categories go here later

TEXT_EXTS = {".txt",".md",".markdown",".rst",".csv",".tsv",".log",".json",
             ".yaml",".yml",".html",".htm",".xml",".ini",".cfg",".py",".js",
             ".ts",".css",".bat",".ps1",".sh",".c",".cpp",".h",".java",".sql"}
DOC_EXTS  = {".pdf",".docx"}
SKIP_DIRS = {".git","__pycache__",".venv","node_modules",".obsidian"}
SKIP_NAMES= {"thumbs.db","desktop.ini",".ds_store"}
# everything else (images, video, audio, zips, exe, ...) = cataloged, not read
# ---------------------------------------------------------------------------

STOP = set("the a an and or of to in is it for on with as by at from this that be are "
    "was were will would can could should i you he she they we not no but if then else "
    "your our their his her its my me us them which who what when where how why all any "
    "some more most other into over under out up down off than too very just have has had "
    "do does did been being about also such only there here".split())


def human(n):
    n = float(n)
    for u in ("B","KB","MB","GB","TB","PB"):
        if n < 1024 or u == "PB":
            return f"{int(n)} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024


def full_md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def quick_md5(path, size):
    # size + first/last 64 KB -> fast, stable identity for big files
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
    return "blob"        # cataloged, not read


def read_sample(path, ext):
    """Small text sample for tagging. Never reads the whole file."""
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
    return ""   # blob tier: not read


def extract_tags(text, name):
    text = (text or "").strip()
    if text:
        try:
            import yake
            kw = yake.KeywordExtractor(n=1, top=NUM_TAGS)
            t = [k.lower() for k, _ in kw.extract_keywords(text)]
            if t: return t[:NUM_TAGS]
        except Exception:
            pass
        words = re.findall(r"[a-z]{3,}", text.lower())
    else:
        words = re.findall(r"[a-z]{3,}", name.lower())
    freq = {}
    for w in words:
        if w in STOP: continue
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq, key=lambda w: (-freq[w], w))
    return ranked[:NUM_TAGS] or ["untagged"]


def when(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def process_one(job):
    path, force, quick, sidecar = job
    try:
        st = os.stat(path)
        ext = os.path.splitext(path)[1].lower()
        size = st.st_size
        t = tier(ext)
        tags = extract_tags(read_sample(path, ext) if t != "blob" else "",
                            os.path.basename(path))
        digest = quick_md5(path, size) if quick else full_md5(path)
        rec = {"path": os.path.abspath(path), "name": os.path.basename(path),
               "ext": ext, "size": size, "md5": digest,
               "created": when(st.st_ctime), "modified": when(st.st_mtime),
               "accessed": when(st.st_atime), "tags": ", ".join(tags),
               "category": "", "tier": t, "mtime": st.st_mtime,
               "scanned": when(datetime.datetime.now().timestamp())}
        if sidecar:
            disp = dict(rec); disp["size"] = f"{human(size)} ({size} bytes)"
            body = "# file meta\n" + "".join(
                f"{k}: {disp[k]}\n" for k in
                ("name","path","ext","size","md5","created","modified",
                 "accessed","tags","category","tier"))
            with open(path + SIDECAR_EXT, "w", encoding="utf-8") as fh:
                fh.write(body)
        return ("done", rec)
    except Exception as e:
        return ("error", f"{path} :: {e}")


SCHEMA = """CREATE TABLE IF NOT EXISTS files(
  path TEXT PRIMARY KEY, name TEXT, ext TEXT, size INTEGER, md5 TEXT,
  created TEXT, modified TEXT, accessed TEXT, tags TEXT, category TEXT,
  tier TEXT, mtime REAL, scanned TEXT)"""
COLS = ("path","name","ext","size","md5","created","modified","accessed",
        "tags","category","tier","mtime","scanned")


def main():
    ap = argparse.ArgumentParser(description="Catalog files (metadata + MD5 + 3 tags) into SQLite.")
    ap.add_argument("path", nargs="?")
    ap.add_argument("--path", dest="path_opt")
    ap.add_argument("--db", default="filecatalog.db")
    ap.add_argument("--workers", type=int, default=max(1, cpu_count() - 1))
    ap.add_argument("--quickhash", action="store_true")
    ap.add_argument("--sidecar", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    root = a.path_opt or a.path
    if not root or not os.path.isdir(root):
        ap.error('give a folder, e.g.  python filetagger.py "X:\\folder"')

    db = sqlite3.connect(a.db)
    db.execute(SCHEMA); db.commit()
    db_name = os.path.basename(a.db)
    seen = {} if a.force else {r[0]: r[1] for r in db.execute("SELECT path, mtime FROM files")}

    jobs, unchanged = [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if f.endswith(SIDECAR_EXT) or f.lower() in SKIP_NAMES or f == db_name:
                continue
            p = os.path.join(dirpath, f)
            try: mt = os.path.getmtime(p)
            except OSError: continue
            if (not a.force) and abs(seen.get(os.path.abspath(p), -1) - mt) < 1e-6:
                unchanged += 1; continue
            jobs.append((p, a.force, a.quickhash, a.sidecar))

    total = len(jobs)
    print(f"{total} files to tag | {unchanged} unchanged (skipped) | {a.workers} workers")
    done = err = 0; batch = []
    ins = f"INSERT OR REPLACE INTO files VALUES ({','.join('?'*len(COLS))})"
    with Pool(a.workers) as pool:
        for i, (status, rec) in enumerate(pool.imap_unordered(process_one, jobs, chunksize=8), 1):
            if status == "error":
                err += 1; print("  ERROR:", rec); continue
            done += 1
            batch.append(tuple(rec[c] for c in COLS))
            if len(batch) >= 500:
                db.executemany(ins, batch); db.commit(); batch.clear()
            if i % 500 == 0 or i == total:
                print(f"  {i}/{total}  (tagged {done}, errors {err})")
    if batch:
        db.executemany(ins, batch); db.commit()
    db.close()
    print(f"done: {done} tagged | {unchanged} unchanged | {err} errors -> {os.path.abspath(a.db)}")


if __name__ == "__main__":
    main()
