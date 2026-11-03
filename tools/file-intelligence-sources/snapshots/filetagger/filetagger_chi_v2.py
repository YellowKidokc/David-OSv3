#!/usr/bin/env python3
"""filetagger_chi v2 - Full Theophysics file profiler.

Classifies every file against:
  - Chi factors (G M E S T K R Q F C)
  - 10 Domains (physics, theology, epistemology, etc.)
  - 10 Laws (L1-L10)
  - Content type (paper, code, data, config, etc.)
  - Evidence density
  - Fruit/anti-fruit presence

Fast. Incremental. Multicore. Zero dependencies beyond stdlib + pypdf.

Usage:
  python filetagger_chi_v2.py "O:\\_Theophysics_v5"
  python filetagger_chi_v2.py "O:\\_Theophysics_v5" --sidecar --db vault.db
  python filetagger_chi_v2.py --summary --db vault.db
"""
import os, sys, re, hashlib, sqlite3, argparse, datetime
from multiprocessing import Pool, cpu_count
from pathlib import Path

# Add FIS for chi_classifier
FIS_DIR = r"D:\DONT TOUCH BOOT UP\FIS"
if FIS_DIR not in sys.path:
    sys.path.insert(0, FIS_DIR)

from chi_classifier import (
    classify_chi_factor, build_chi_vector, CHI_FACTORS
)

# ── Config ──
SIDECAR_EXT  = ".chi"
SAMPLE_BYTES = 4096
PDF_PAGES    = 2

TEXT_EXTS = {".txt",".md",".markdown",".rst",".csv",".tsv",".log",".json",
             ".yaml",".yml",".html",".htm",".xml",".ini",".cfg",".py",".js",
             ".ts",".css",".bat",".ps1",".sh",".c",".cpp",".h",".java",".sql",
             ".lean",".tex",".bib",".r",".m",".ahk",".toml"}
DOC_EXTS  = {".pdf",".docx"}
SKIP_DIRS = {".git","__pycache__",".venv","node_modules",".obsidian",
             ".next","dist","build","_archive","graveyard",".smart-env",
             ".stversions",".claudian",".claude"}
SKIP_NAMES= {"thumbs.db","desktop.ini",".ds_store"}

STOP = set("the a an and or of to in is it for on with as by at from this that "
    "be are was were will would can could should not no but if then else your our "
    "their his her its my me us them which who what when where how why all any "
    "some more most other into over under out up down off than too very just have "
    "has had do does did been being about also such only there here".split())

# ── Domain Classification (from v4 gold engine) ──
DOMAIN_KEYWORDS = {
    "physics": {"physics","quantum","field","entropy","thermodynamic","relativity",
        "gravity","mass","energy","wave","particle","measurement","tensor",
        "lagrangian","hubble","cosmological","maxwell","shannon"},
    "theology": {"god","christ","jesus","spirit","grace","sin","salvation","cross",
        "resurrection","trinity","logos","scripture","biblical","theism","mercy"},
    "epistemology": {"truth","knowledge","axiom","foundation","ground","munchhausen",
        "circular","regress","assumption","method","falsifiability","prediction"},
    "morality": {"good","evil","justice","moral","ought","obligation","duty",
        "virtue","vice","consequence","accountability"},
    "consciousness": {"consciousness","observer","experience","qualia","mind",
        "cognition","brain","neural","subjective","perception"},
    "information": {"information","signal","noise","channel","compression","entropy",
        "shannon","code","encoding","transmission","fidelity"},
    "history": {"historical","century","ancient","document","transmission","source",
        "record","dated","event","timeline"},
    "psychology": {"behavior","addiction","habit","willpower","therapy","emotion",
        "anxiety","trauma","identity"},
    "sociology": {"society","institution","civilization","culture","community",
        "political","social","collapse","family"},
    "formal_math": {"equation","theorem","proof","formal","lean","operator",
        "function","variable","matrix","score","model"},
}

LAW_KEYWORDS = {
    "L01_Gravity_Grace": {"gravity","curvature","spacetime","mass","grace","draw",
        "attract","geodesic","gravitational"},
    "L02_Motion_Will": {"motion","force","will","repentance","conversion",
        "momentum","acceleration","inertia"},
    "L03_EM_Truth": {"electromagnetic","maxwell","light","truth","deception",
        "witness","signal","glory","doxa"},
    "L04_Strong_Love": {"strong force","quark","binding","love","covenant",
        "confinement","yukawa","agape","fruit"},
    "L05_Thermo_Justice": {"entropy","thermodynamic","justice","mercy","judgment",
        "free energy","decay","heat death"},
    "L06_Info_Logos": {"information","shannon","channel","logos","word","noise",
        "capacity","bandwidth","sanctification"},
    "L07_Quantum_Faith": {"quantum","collapse","superposition","measurement",
        "faith","observer","doubt","uncertainty"},
    "L08_Relativity_Grace": {"relativity","frame","lorentz","relationship",
        "reference","invariant","frame lock"},
    "L09_Weak_Conservation": {"weak force","decay","parity","atonement",
        "moral conservation","irreversible","cp violation"},
    "L10_Coherence_Christ": {"coherence","christ","integration","shalom",
        "kingdom","master equation","decoherence"},
}

EVIDENCE_TERMS = {"data","dataset","measurement","measured","experiment",
    "observation","citation","source","reference","test","prediction",
    "empirical","study","sigma","p-value","sample","peer-reviewed",
    "replication","statistical","correlation","regression"}

FRUIT_TERMS = {"love","joy","peace","patience","kindness","goodness",
    "faithfulness","gentleness","self-control","hope","grace","humility",
    "unity","truth","care","restore","forgive","dignity","mercy","repair"}

ANTI_FRUIT = {"hatred","despair","anxiety","impatience","cruelty","corruption",
    "betrayal","harshness","addiction","rage","domination","coercion",
    "dehumanization","panic","scapegoat","manipulate","contempt"}

# ── Classification Functions ──
def classify_domains(toks, text_lower):
    """Return top 3 domains with scores."""
    scores = {}
    for domain, kws in DOMAIN_KEYWORDS.items():
        count = sum(1 for kw in kws if kw in toks or kw in text_lower)
        if count:
            scores[domain] = round(min(99, (count / min(len(kws), 8)) * 100), 1)
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return ranked[:3]

def classify_laws(text_lower):
    """Return top 3 Laws detected."""
    scores = {}
    for law, kws in LAW_KEYWORDS.items():
        count = sum(1 for kw in kws if kw in text_lower)
        if count:
            scores[law] = round(min(99, (count / min(len(kws), 5)) * 100), 1)
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return ranked[:3]

def score_set(toks, term_set, cap=8):
    """Score presence of a term set in tokens."""
    hits = sum(1 for t in term_set if t in toks)
    return round(min(99, (hits / cap) * 100), 1)

def detect_content_type(ext, tier, keywords):
    """Infer content type from extension and keywords."""
    type_map = {
        ".py": "code", ".js": "code", ".ts": "code", ".css": "code",
        ".sh": "code", ".bat": "code", ".ps1": "code", ".ahk": "code",
        ".lean": "proof", ".tex": "paper",
        ".json": "data", ".csv": "data", ".tsv": "data", ".xlsx": "data",
        ".yaml": "config", ".yml": "config", ".toml": "config",
        ".ini": "config", ".cfg": "config",
        ".png": "image", ".jpg": "image", ".svg": "image", ".gif": "image",
        ".mp3": "audio", ".wav": "audio", ".m4a": "audio",
        ".mp4": "video", ".webm": "video",
        ".pdf": "document", ".docx": "document",
    }
    if ext in type_map:
        return type_map[ext]
    kw_set = set(keywords.split(", ")) if keywords else set()
    if kw_set & {"theorem","proof","lemma","axiom","lean"}: return "proof"
    if kw_set & {"paper","abstract","introduction","conclusion"}: return "paper"
    if kw_set & {"sermon","preach","congregation"}: return "sermon"
    return "document" if tier == "text" else "binary"

# ── Utilities ──
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
    if ext in DOC_EXTS: return "doc"
    return "blob"

def read_sample(path, ext):
    if ext in TEXT_EXTS:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read(SAMPLE_BYTES)
        except Exception: return ""
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            pages = PdfReader(path).pages[:PDF_PAGES]
            return "\n".join((p.extract_text() or "") for p in pages)[:SAMPLE_BYTES]
        except Exception: return ""
    if ext == ".docx":
        try:
            import docx
            out, n = [], 0
            for p in docx.Document(path).paragraphs:
                out.append(p.text); n += len(p.text)
                if n >= SAMPLE_BYTES: break
            return "\n".join(out)[:SAMPLE_BYTES]
        except Exception: return ""
    return ""

def extract_keywords(text, name):
    text = (text or "").strip()
    words = re.findall(r"[a-z]{3,}", (text or name).lower())
    freq = {}
    for w in words:
        if w in STOP: continue
        freq[w] = freq.get(w, 0) + 1
    return sorted(freq, key=lambda w: (-freq[w], w))[:20]

def when(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

# ── Process One File ──
def process_one(job):
    path, force, sidecar = job
    try:
        st = os.stat(path)
        ext = os.path.splitext(path)[1].lower()
        size = st.st_size
        t = tier(ext)
        sample = read_sample(path, ext) if t != "blob" else ""
        keywords = extract_keywords(sample, os.path.basename(path))
        digest = quick_md5(path, size)
        toks = set(k.lower() for k in keywords)
        text_lower = sample.lower() if sample else ""

        # Chi classification
        chi = classify_chi_factor(keywords, sample, os.path.basename(path))
        primary = chi.get('primary_factor') or 'UC'
        secondary = ','.join(chi.get('secondary_factors', []))
        vector = chi.get('vector', 'G0M0E0S0T0K0R0Q0F0C0')
        confidence = chi.get('confidence', 0)

        # Domain classification
        domains = classify_domains(toks, text_lower)
        domain_primary = domains[0][0] if domains else ''
        domain_scores = ';'.join(f"{d}:{s}" for d, s in domains)

        # Law classification
        laws = classify_laws(text_lower)
        law_primary = laws[0][0] if laws else ''
        law_scores = ';'.join(f"{l}:{s}" for l, s in laws)

        # Content type
        kw_str = ", ".join(keywords[:8])
        content_type = detect_content_type(ext, t, kw_str)

        # Evidence + fruit scores
        evidence = score_set(toks, EVIDENCE_TERMS)
        fruit = score_set(toks, FRUIT_TERMS, cap=6)
        anti_fruit = score_set(toks, ANTI_FRUIT, cap=5)

        rec = {
            "path": os.path.abspath(path), "name": os.path.basename(path),
            "ext": ext, "size": size, "md5": digest,
            "created": when(st.st_ctime), "modified": when(st.st_mtime),
            "keywords": kw_str, "tier": t, "mtime": st.st_mtime,
            "scanned": when(datetime.datetime.now().timestamp()),
            "chi_primary": primary, "chi_secondary": secondary,
            "chi_vector": vector, "chi_confidence": confidence,
            "domain_primary": domain_primary, "domain_scores": domain_scores,
            "law_primary": law_primary, "law_scores": law_scores,
            "content_type": content_type,
            "evidence": evidence, "fruit": fruit, "anti_fruit": anti_fruit,
        }

        if sidecar:
            body = f"""# file profile (.chi)
name: {rec['name']}
path: {rec['path']}
ext: {ext}
size: {human(size)} ({size} bytes)
md5: {digest}
created: {rec['created']}
modified: {rec['modified']}

## chi classification
primary: {primary}
secondary: [{secondary}]
vector: {vector}
confidence: {confidence}%

## domains
primary: {domain_primary}
scores: {domain_scores}

## laws
primary: {law_primary}
scores: {law_scores}

## profile
content_type: {content_type}
evidence: {evidence}%
fruit: {fruit}%
anti_fruit: {anti_fruit}%
keywords: {kw_str}
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
  created TEXT, modified TEXT, keywords TEXT, tier TEXT, mtime REAL, scanned TEXT,
  chi_primary TEXT, chi_secondary TEXT, chi_vector TEXT, chi_confidence REAL,
  domain_primary TEXT, domain_scores TEXT,
  law_primary TEXT, law_scores TEXT,
  content_type TEXT,
  evidence REAL, fruit REAL, anti_fruit REAL)"""

COLS = ("path","name","ext","size","md5","created","modified",
        "keywords","tier","mtime","scanned",
        "chi_primary","chi_secondary","chi_vector","chi_confidence",
        "domain_primary","domain_scores",
        "law_primary","law_scores",
        "content_type","evidence","fruit","anti_fruit")

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_chi ON files(chi_primary)",
    "CREATE INDEX IF NOT EXISTS idx_domain ON files(domain_primary)",
    "CREATE INDEX IF NOT EXISTS idx_law ON files(law_primary)",
    "CREATE INDEX IF NOT EXISTS idx_type ON files(content_type)",
    "CREATE INDEX IF NOT EXISTS idx_evidence ON files(evidence)",
    "CREATE INDEX IF NOT EXISTS idx_ext ON files(ext)",
]

def print_summary(db_path):
    db = sqlite3.connect(db_path)
    total = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    print(f"\n{'='*65}")
    print(f"  THEOPHYSICS FILE PROFILE -- {total} files")
    print(f"{'='*65}")

    print("\n  CHI FACTORS:")
    for r in db.execute(
        "SELECT chi_primary, COUNT(*), ROUND(AVG(chi_confidence),1) "
        "FROM files WHERE chi_primary IS NOT NULL AND chi_primary != 'UC' "
        "GROUP BY chi_primary ORDER BY COUNT(*) DESC"):
        print(f"    {r[0]:4s}  {r[1]:6d} files  avg {r[2]}%")

    print("\n  DOMAINS:")
    for r in db.execute(
        "SELECT domain_primary, COUNT(*) FROM files "
        "WHERE domain_primary != '' "
        "GROUP BY domain_primary ORDER BY COUNT(*) DESC LIMIT 12"):
        print(f"    {r[0]:15s}  {r[1]:6d} files")

    print("\n  LAWS:")
    for r in db.execute(
        "SELECT law_primary, COUNT(*) FROM files "
        "WHERE law_primary != '' "
        "GROUP BY law_primary ORDER BY COUNT(*) DESC LIMIT 12"):
        print(f"    {r[0]:25s}  {r[1]:6d} files")

    print("\n  CONTENT TYPES:")
    for r in db.execute(
        "SELECT content_type, COUNT(*) FROM files "
        "GROUP BY content_type ORDER BY COUNT(*) DESC"):
        print(f"    {r[0]:12s}  {r[1]:6d} files")

    print("\n  EVIDENCE DENSITY (top files):")
    for r in db.execute(
        "SELECT name, evidence, chi_primary, domain_primary FROM files "
        "WHERE evidence > 0 ORDER BY evidence DESC LIMIT 8"):
        print(f"    {r[1]:5.1f}%  [{r[2]}] {r[3]:12s}  {r[0][:50]}")

    print(f"\n{'='*65}\n")
    db.close()


def main():
    ap = argparse.ArgumentParser(description="Full Theophysics file profiler.")
    ap.add_argument("path", nargs="?")
    ap.add_argument("--path", dest="path_opt")
    ap.add_argument("--db", default="chi_catalog_v2.db")
    ap.add_argument("--workers", type=int, default=max(1, cpu_count() - 1))
    ap.add_argument("--sidecar", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()

    if a.summary:
        print_summary(a.db)
        return

    root = a.path_opt or a.path
    if not root or not os.path.isdir(root):
        ap.error('give a folder')

    db = sqlite3.connect(a.db)
    db.execute(SCHEMA)
    for idx in INDEXES:
        db.execute(idx)
    db.commit()
    db_name = os.path.basename(a.db)
    seen = {} if a.force else {
        r[0]: r[1] for r in db.execute("SELECT path, mtime FROM files")
    }

    jobs, unchanged = [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if (f.endswith(SIDECAR_EXT) or f.endswith('.fmeta')
                    or f.lower() in SKIP_NAMES or f == db_name):
                continue
            p = os.path.join(dirpath, f)
            try: mt = os.path.getmtime(p)
            except OSError: continue
            if not a.force and abs(seen.get(os.path.abspath(p), -1) - mt) < 1e-6:
                unchanged += 1; continue
            jobs.append((p, a.force, a.sidecar))

    total = len(jobs)
    print(f"{total} files to profile | {unchanged} unchanged | {a.workers} workers")
    if total == 0:
        print_summary(a.db)
        return

    done = err = 0; batch = []
    ins = f"INSERT OR REPLACE INTO files VALUES ({','.join('?' * len(COLS))})"
    with Pool(a.workers) as pool:
        for i, (status, rec) in enumerate(
                pool.imap_unordered(process_one, jobs, chunksize=8), 1):
            if status == "error":
                err += 1; print("  ERROR:", rec); continue
            done += 1
            batch.append(tuple(rec[c] for c in COLS))
            if len(batch) >= 500:
                db.executemany(ins, batch); db.commit(); batch.clear()
            if i % 2000 == 0 or i == total:
                print(f"  {i}/{total}  (profiled {done}, errors {err})")
    if batch:
        db.executemany(ins, batch); db.commit()
    db.close()
    print(f"\ndone: {done} profiled | {unchanged} unchanged | {err} errors")
    print_summary(a.db)


if __name__ == "__main__":
    main()
