#!/usr/bin/env python3
"""Theophysics Convergence Tagger v3 - tagger2's engine with filetagger's reach.

Everything tagger2 does (stemmed registry matching, disambiguation, Ollama meaning layer,
scripture refs, gold-set eval/tune) plus, from filetagger / foldertagger / filetagger_daemon:

  * more formats    - .pdf (PyMuPDF, falls back to pypdf), .docx (headings kept as headings),
                      .html, alongside .md / .txt. Extracted text is cached by size+mtime, so
                      a rerun does not re-read PDFs. Extraction runs on all cores.
  * file catalog    - --catalog records EVERY file under the sources (any type): size, dates,
                      quick hash, read tier, keywords for untagged text files, duplicates.
  * sidecars        - --write-sidecars writes <file>.fmeta beside each tagged document with its
                      registry tags (only rewritten when something changed).
  * folder markers  - --write-folder-markers writes .folder.fmeta into each folder: a folder_id
                      that survives moves, previous paths, and the folder's top categories/tags
                      rolled up from the documents inside it. Your own category:/notes: lines
                      in a marker are kept.
  * watch           - re-tags automatically when files change (watchdog), writing latest_*.csv.

Same database as tagger2 (02_INDEX/tagger.db) and the same registry hash, so documents tagged
by v2 are reused, not re-tagged, and fistag.py keeps working.

Subcommands:
  scan           tag files (default if you start with --source)
  catalog        catalog every file (metadata, hash, duplicates) without tagging
  watch          initial scan, then re-scan on every change until Ctrl+C
  gold-template  write 06_REVIEW/gold_template.csv for hand correction
  eval           precision / recall / F1 against 06_REVIEW/gold.csv
  tune           grid-search params against the gold set, write tuned_params.json
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sqlite3
import sys
import time
import zlib
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tagger2 as T2  # noqa: E402  (the tagging engine)

TAGGER_VERSION = "3.0.0"
ROOT = T2.ROOT
DEFAULT_DOC_EXTS = ".md,.markdown,.txt,.pdf,.docx,.html,.htm"
SIDECAR_EXT = ".fmeta"
MARKER_NAME = ".folder.fmeta"
CACHED_EXTS = {".pdf", ".docx"}          # slow to extract -> cache the text
MAX_EXTRACTED = 8_000_000                # chars kept from a PDF/DOCX (a 1,000-page book is ~3M)
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".obsidian", ".trash",
             ".next", "dist", "build", ".wrangler"}
SKIP_NAMES = {"thumbs.db", "desktop.ini", ".ds_store", MARKER_NAME}
SKIP_SUFFIXES = (SIDECAR_EXT, ".fistag", ".fmeta.chi", ".chi")
TEXT_TIER = {".txt", ".md", ".markdown", ".rst", ".csv", ".tsv", ".log", ".json", ".yaml", ".yml",
             ".html", ".htm", ".xml", ".ini", ".cfg", ".py", ".js", ".ts", ".css", ".bat", ".ps1",
             ".sh", ".c", ".cpp", ".h", ".java", ".sql", ".tex", ".ahk"}
DOC_TIER = {".pdf", ".docx"}

EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS extract_cache(path TEXT PRIMARY KEY, size INT, mtime REAL, text BLOB, error TEXT);
CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, name TEXT, ext TEXT, size INT, mtime REAL,
    created TEXT, modified TEXT, quick_hash TEXT, full_hash TEXT, tier TEXT, keywords TEXT, scanned TEXT);
CREATE TABLE IF NOT EXISTS folders(folder_id TEXT PRIMARY KEY, path TEXT, previous_paths TEXT,
    first_seen TEXT, last_seen TEXT);
CREATE INDEX IF NOT EXISTS ix_files_qh ON files(quick_hash);
"""


def open_db(path: Path) -> sqlite3.Connection:
    con = T2.open_db(path)
    con.executescript(EXTRA_SCHEMA)
    return con


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def when(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def human(n: float) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{int(n)} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return str(n)


def skip_file(name: str) -> bool:
    low = name.lower()
    return low in SKIP_NAMES or low.startswith("~$") or low.endswith(SKIP_SUFFIXES)


def walk(source: Path):
    """Yield (dirpath, filenames) under source, skipping tool/system folders."""
    for dirpath, dirnames, filenames in os.walk(source):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        yield Path(dirpath), [f for f in filenames if not skip_file(f)]


def iter_docs(sources: list[Path], exts: set[str], limit: int | None):
    count = 0
    for source in sources:
        if source.is_file():
            items = [source] if source.suffix.lower() in exts else []
        elif source.is_dir():
            items = (d / f for d, fs in walk(source) for f in fs if Path(f).suffix.lower() in exts)
        else:
            print(f"[warn] source not found: {source}", file=sys.stderr)
            items = []
        for path in items:
            yield path
            count += 1
            if limit and count >= limit:
                return


# ------------------------------------------------------------------------ extraction
def _html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|nav|footer|svg)\b.*?</\1>", " ", raw)
    raw = re.sub(r"(?is)<h([1-6])[^>]*>(.*?)</h\1>", lambda m: "\n\n" + "#" * int(m.group(1)) + " "
                 + re.sub(r"<[^>]+>|\s+", " ", m.group(2)).strip() + "\n\n", raw)
    raw = re.sub(r"(?i)</(p|div|li|tr|section|article|blockquote|br)\s*>|<br\s*/?>", "\n\n", raw)
    return html.unescape(re.sub(r"<[^>]+>", " ", raw))


def _pdf_text(path: str) -> str:
    try:
        import fitz  # PyMuPDF: fast, and gives text blocks we can use as paragraphs
        out = []
        with fitz.open(path) as doc:
            for page in doc:
                for b in page.get_text("blocks"):
                    t = (b[4] or "").strip()
                    if t:
                        out.append(re.sub(r"-\n(?=[a-z])", "", t).replace("\n", " "))
        return "\n\n".join(out)
    except ImportError:
        from pypdf import PdfReader
        return "\n\n".join((p.extract_text() or "") for p in PdfReader(path).pages)


def _docx_text(path: str) -> str:
    import docx
    out = []
    for p in docx.Document(path).paragraphs:
        t = p.text.strip()
        if not t:
            continue
        style = (p.style.name or "").lower() if p.style is not None else ""
        m = re.match(r"heading (\d)", style)
        if style == "title":
            t = "# " + t
        elif m:
            t = "#" * min(int(m.group(1)) + 1, 6) + " " + t
        out.append(t)
    return "\n\n".join(out)


def extract(path_str: str) -> tuple[str, str]:
    """(text, error). Runs in worker processes, so it must stay a top-level function."""
    ext = os.path.splitext(path_str)[1].lower()
    try:
        if ext == ".pdf":
            return _pdf_text(path_str)[:MAX_EXTRACTED], ""
        if ext == ".docx":
            return _docx_text(path_str)[:MAX_EXTRACTED], ""
        if ext in (".html", ".htm"):
            return _html_to_text(T2.read_text(Path(path_str))), ""
        return T2.read_text(Path(path_str)), ""
    except Exception as exc:
        if os.path.exists(path_str) and os.path.getsize(path_str) == 0:
            return "", "empty file (0 bytes)"
        return "", f"{type(exc).__name__}: {exc}"


def get_texts(con, paths: list[Path], workers: int) -> dict[Path, tuple[str, str]]:
    out: dict[Path, tuple[str, str]] = {}
    misses: list[tuple[Path, int, float]] = []
    for p in paths:
        try:
            st = p.stat()
        except OSError as exc:
            out[p] = ("", str(exc))
            continue
        if p.suffix.lower() in CACHED_EXTS:
            row = con.execute("SELECT size, mtime, text, error FROM extract_cache WHERE path=?", (str(p),)).fetchone()
            if row and row[0] == st.st_size and abs(row[1] - st.st_mtime) < 1e-6:
                out[p] = (zlib.decompress(row[2]).decode("utf-8") if row[2] else "", row[3] or "")
                continue
            misses.append((p, st.st_size, st.st_mtime))
        else:
            out[p] = extract(str(p))
    if misses:
        names = [str(p) for p, _, _ in misses]
        if workers > 1 and len(misses) > 2:
            with ProcessPoolExecutor(max_workers=workers) as ex:
                results = list(ex.map(extract, names, chunksize=2))
        else:
            results = [extract(n) for n in names]
        for (p, size, mtime), (text, err) in zip(misses, results):
            out[p] = (text, err)
            con.execute("INSERT OR REPLACE INTO extract_cache VALUES (?,?,?,?,?)",
                        (str(p), size, mtime, zlib.compress(text.encode("utf-8")), err))
        con.commit()
    return out


# ---------------------------------------------------------------------------- context
@dataclass
class Ctx:
    tags: list
    tag_by_name: dict
    index: dict
    registry_hash: str
    sem_model: str | None = None
    emb: object = None
    tag_matrix: object = None
    done: set = field(default_factory=set)
    sem_done: set = field(default_factory=set)


def registry_ctx(args, con, semantic: bool | None = None) -> Ctx:
    registry = Path(args.registry)
    exclusions = Path(args.exclusions) if args.exclusions else None
    amb_path, cw_path = Path(args.ambiguous), Path(args.category_weights)
    tags = T2.load_registry(registry, exclusions, T2.load_category_weights(cw_path))
    # Same recipe and version string as tagger2, so v2's work in tagger.db is reused.
    registry_hash = hashlib.sha256((T2.file_sha(registry) + T2.file_sha(exclusions or Path("_none_"))
                                    + T2.file_sha(amb_path) + T2.file_sha(cw_path)
                                    + T2.TAGGER_VERSION).encode()).hexdigest()[:16]
    ctx = Ctx(tags=tags, tag_by_name={t.tag: t for t in tags},
              index=T2.build_index(tags, T2.load_word_list(amb_path)), registry_hash=registry_hash)
    if args.semantic if semantic is None else semantic:
        ctx.emb = T2.Embedder(args.ollama_url, args.embed_model)
        ctx.emb.check()
        ctx.sem_model = ctx.emb.model + T2.SEM_KEY_SUFFIX
        ctx.tag_matrix = T2.load_tag_matrix(con, ctx.emb, tags)
    return ctx


# ------------------------------------------------------------------------- tagging
def index_doc(con, ctx: Ctx, path: Path, text: str, stamp: str, force: bool, errors: list) -> tuple[str, bool]:
    """Tag one document's text into the DB (same evidence tables as tagger2). Returns (hash, newly_tagged)."""
    tags = ctx.tags
    body, title, paras = T2.parse_doc(path, text)
    h = T2.content_hash(body)
    need_lex = force or h not in ctx.done
    need_sem = bool(ctx.sem_model) and (force or h not in ctx.sem_done)
    if need_lex:
        for table in ("tag_counts", "para_hits", "scripture"):
            con.execute(f"DELETE FROM {table} WHERE content_hash=?", (h,))
        title_c = T2.count_hits(T2.tokens_of(title), ctx.index)
        tl = title.lower()
        for t in list(title_c):
            if tags[t].excludes and any(x in tl for x in tags[t].excludes):
                del title_c[t]
        head_c, body_c, prow, n_tokens = Counter(), Counter(), [], 0
        for pi, para in enumerate(paras):
            toks = T2.tokens_of(para)
            n_tokens += len(toks[0])
            c = T2.count_hits(toks, ctx.index)
            if not c:
                continue
            pl = para.lower()
            for t in list(c):
                if tags[t].excludes and any(x in pl for x in tags[t].excludes):
                    del c[t]
            (head_c if para.startswith("#") else body_c).update(c)
            prow += [(h, pi, tags[t].tag, k, para[:300]) for t, k in c.items()]
        all_t = set(title_c) | set(head_c) | set(body_c)
        con.executemany("INSERT OR REPLACE INTO tag_counts VALUES (?,?,?,?,?)",
                        [(h, tags[t].tag, title_c[t], head_c[t], body_c[t]) for t in all_t])
        con.executemany("INSERT INTO para_hits VALUES (?,?,?,?,?)", prow)
        con.executemany("INSERT INTO scripture VALUES (?,?,?,?,?)",
                        [(h, *ref) for ref in T2.find_scripture(T2.FENCE_RE.sub("\n", body))])
        con.execute("INSERT OR REPLACE INTO hashes_scanned VALUES (?,?,?)", (h, ctx.registry_hash, ctx.sem_model or ""))
        con.execute("INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?)",
                    (str(path), h, title, n_tokens, stamp, ctx.registry_hash))
        ctx.done.add(h)
    else:
        con.execute("INSERT OR REPLACE INTO documents VALUES (?,?,?,COALESCE((SELECT n_tokens FROM documents WHERE path=?),0),?,?)",
                    (str(path), h, title, str(path), stamp, ctx.registry_hash))
    if need_sem:
        con.execute("DELETE FROM sem_scores WHERE content_hash=? AND model=?", (h, ctx.sem_model))
        try:
            pairs = T2.semantic_scores(ctx.emb, ctx.tag_matrix, title, paras)
            con.executemany("INSERT OR REPLACE INTO sem_scores VALUES (?,?,?,?)",
                            [(h, tags[i].tag, ctx.sem_model, z) for i, z in pairs])
            ctx.sem_done.add(h)
        except Exception as exc:
            errors.append({"path": str(path), "error": f"semantic: {exc}"})
    return h, need_lex


def doc_results(con, ctx: Ctx, params: dict, seen: dict[str, str]) -> dict[str, dict]:
    """path -> accepted tags, primary tag/category, variables, scripture refs."""
    hashes, counts, sems, df = T2.gather(con, ctx.registry_hash, ctx.sem_model)
    N = len(hashes)
    want = set(seen.values())
    scr: dict[str, list[str]] = defaultdict(list)
    for h, ref in con.execute("SELECT content_hash, ref FROM scripture"):
        if h in want:
            scr[h].append(ref)
    by_hash: dict[str, list[str]] = defaultdict(list)
    for p, h in seen.items():
        by_hash[h].append(p)
    out = {}
    for path, h in seen.items():
        acc = [r for r in T2.score_doc(h, counts, sems, df, N, params, ctx.tag_by_name) if r["accepted"]]
        primary_cat, cats = T2.rollup(acc, ctx.tag_by_name)
        out[path] = {
            "hash": h, "accepted": acc, "primary_tag": acc[0]["tag"] if acc else "",
            "primary_category": primary_cat, "categories": cats,
            "variables": sorted({ctx.tag_by_name[r["tag"]].variable for r in acc
                                 if r["tag"] in ctx.tag_by_name and ctx.tag_by_name[r["tag"]].variable}),
            "scripture": list(dict.fromkeys(scr.get(h, []))),
            "duplicates": [p for p in by_hash[h] if p != path],
        }
    return out


def all_results(db: Path, args) -> dict[str, dict]:
    """Results for every document in the DB under the current registry (used by the GUI)."""
    con = open_db(db)
    ctx = registry_ctx(args, con, semantic=False)
    if args.semantic:
        ctx.sem_model = args.embed_model + T2.SEM_KEY_SUFFIX
    seen = dict(con.execute("SELECT path, content_hash FROM documents WHERE registry_hash=?", (ctx.registry_hash,)))
    return doc_results(con, ctx, T2.load_params(T2.vars_params(args)), seen)


# ------------------------------------------------------------------- write-outs
def write_if_changed(path: Path, body: str, volatile: tuple[str, ...] = ()) -> bool:
    """Write only when content differs (ignoring lines that start with a volatile key), so a
    rerun does not touch files that did not change - which also keeps watch mode from looping."""
    def stable(s: str) -> str:
        return "\n".join(l for l in s.splitlines() if not l.startswith(volatile)) if volatile else s
    try:
        if path.exists() and stable(path.read_text(encoding="utf-8", errors="ignore")) == stable(body):
            return False
    except OSError:
        pass
    path.write_text(body, encoding="utf-8", newline="\n")
    return True


def sidecar_body(path: Path, res: dict, registry_hash: str) -> str:
    st = path.stat()
    lines = [
        "# file meta (Theophysics Convergence Tagger v3)",
        f"name: {path.name}",
        f"path: {path}",
        f"ext: {path.suffix.lower()}",
        f"size: {human(st.st_size)} ({st.st_size} bytes)",
        f"modified: {when(st.st_mtime)}",
        f"content_hash: {res['hash']}",
        f"primary_tag: {res['primary_tag']}",
        f"primary_category: {res['primary_category']}",
        # no scores here: they are corpus-relative, so every new document would rewrite every sidecar
        f"tags: {'; '.join(sorted(r['tag'] for r in res['accepted']))}",
        f"variables: {', '.join(res['variables'])}",
        f"scripture: {'; '.join(res['scripture'][:40])}" + (" ..." if len(res["scripture"]) > 40 else ""),
        f"duplicate_of: {' | '.join(res['duplicates'])}",
        f"registry: {registry_hash}",
        "",
    ]
    return "\n".join(lines)


def read_marker(folder: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for line in (folder / MARKER_NAME).read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("## "):
                break
            if ":" in line and not line.startswith("#"):
                k, v = line.split(":", 1)
                out[k.strip()] = v.strip()
    except OSError:
        pass
    return out


def write_folder_markers(con, sources: list[Path], results: dict[str, dict], all_folders: bool,
                         dry_run: bool = False) -> int:
    direct: dict[str, list[dict]] = defaultdict(list)
    subtree: dict[str, list[dict]] = defaultdict(list)
    roots = [s.resolve() for s in sources if s.is_dir()]
    for p, res in results.items():
        pp = Path(p).resolve()
        direct[str(pp.parent)].append(res)
        for parent in pp.parents:
            if not any(parent == r or r in parent.parents for r in roots):
                break
            subtree[str(parent)].append(res)

    def top_tags(rs: list[dict], n: int) -> str:
        c = Counter(r["tag"] for res in rs for r in res["accepted"])
        return ", ".join(f"{t} ({k})" for t, k in c.most_common(n))

    def top_cats(rs: list[dict], n: int) -> list[tuple[str, float]]:
        c: Counter = Counter()
        for res in rs:
            for cat, s in res["categories"].items():
                c[cat] += s
        return c.most_common(n)

    written = 0
    for root in roots:
        for folder, files in walk(root):
            key = str(folder.resolve())
            if not subtree.get(key) and not all_folders:
                continue
            old = read_marker(folder)
            current = key
            previous = old.get("current_path", "")
            moved = bool(previous) and previous.lower() != current.lower()
            prev_paths = [x.strip() for x in old.get("previous_paths", "").split(" | ") if x.strip()]
            if moved and previous not in prev_paths:
                prev_paths.append(previous)
            folder_id = old.get("folder_id") or f"FLD-{datetime.now():%Y%m%d}-{hashlib.sha1(current.encode()).hexdigest()[:8]}"
            try:
                subdirs = sorted(d.name for d in folder.iterdir() if d.is_dir() and d.name not in SKIP_DIRS)
            except OSError:
                subdirs = []
            exts: Counter = Counter()
            total = 0
            for f in files:
                exts[Path(f).suffix.lower() or "[none]"] += 1
                try:
                    total += (folder / f).stat().st_size
                except OSError:
                    pass
            cats = top_cats(subtree.get(key, []), 5)
            outline = [f"- [dir] {d}" for d in subdirs[:40]]
            outline += [f"- [file] {f}" for f in sorted(files)[: max(0, 40 - len(outline))]]
            if len(subdirs) + len(files) > 40:
                outline.append(f"- ... {len(subdirs) + len(files) - 40} more")
            body = "\n".join([
                "# folder meta (Theophysics Convergence Tagger v3)",
                f"folder_id: {folder_id}",
                f"name: {folder.name}",
                f"current_path: {current}",
                f"previous_paths: {' | '.join(prev_paths)}",
                f"moved_since_last_scan: {'yes' if moved else 'no'}",
                f"first_scanned: {old.get('first_scanned') or now()}",
                f"last_scanned: {now()}",
                f"child_folder_count: {len(subdirs)}",
                f"file_count: {len(files)}",
                f"total_file_bytes: {total}",
                f"extensions: {', '.join(f'{e}={k}' for e, k in exts.most_common(12)) or 'none'}",
                f"documents_tagged_here: {len(direct.get(key, []))}",
                f"documents_tagged_below: {len(subtree.get(key, []))}",
                f"primary_category: {cats[0][0] if cats else ''}",
                f"top_categories: {', '.join(f'{c} ({s:.1f})' for c, s in cats)}",
                f"top_tags_here: {top_tags(direct.get(key, []), 10)}",
                f"top_tags_below: {top_tags(subtree.get(key, []), 15)}",
                f"category: {old.get('category', '')}",
                f"notes: {old.get('notes', '')}",
                "",
                "## outline",
                *(outline or ["- [empty]"]),
                "",
            ])
            if dry_run:
                print(f"would write {folder / MARKER_NAME}")
                written += 1
                continue
            if write_if_changed(folder / MARKER_NAME, body, volatile=("last_scanned:",)):
                written += 1
            con.execute("INSERT INTO folders VALUES (?,?,?,?,?) ON CONFLICT(folder_id) DO UPDATE SET "
                        "path=excluded.path, previous_paths=excluded.previous_paths, last_seen=excluded.last_seen",
                        (folder_id, current, " | ".join(prev_paths), now(), now()))
    con.commit()
    return written


# --------------------------------------------------------------------------- catalog
STOP = set("the a an and or of to in is it for on with as by at from this that be are was were will would can "
           "could should i you he she they we not no but if then else your our their his her its my me us them "
           "which who what when where how why all any some more most other into over under out up down off than "
           "too very just have has had do does did been being about also such only there here".split())


def quick_hash(path: Path, size: int) -> str:
    h = hashlib.sha1(str(size).encode())
    with path.open("rb") as fh:
        h.update(fh.read(65536))
        if size > 131072:
            fh.seek(-65536, os.SEEK_END)
            h.update(fh.read(65536))
    return h.hexdigest()[:20]


def full_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def keywords(text: str, name: str, n: int = 5) -> str:
    text = (text or "").strip()[:4096]
    if text:
        try:
            import yake
            kw = [k.lower() for k, _ in yake.KeywordExtractor(n=1, top=n).extract_keywords(text)]
            if kw:
                return ", ".join(kw)
        except Exception:
            pass
    words = re.findall(r"[a-z]{3,}", (text or name).lower())
    return ", ".join(w for w, _ in Counter(w for w in words if w not in STOP).most_common(n))


def run_catalog(con, sources: list[Path], tagged_paths: set[str], full: bool, force: bool) -> dict:
    known = {} if force else {p: (s, m) for p, s, m in con.execute("SELECT path, size, mtime FROM files")}
    seen, new, errs, stamp = set(), 0, 0, now()
    for source in sources:
        if not source.is_dir():
            continue
        for folder, files in walk(source):
            for f in files:
                p = folder / f
                try:
                    st = p.stat()
                except OSError:
                    errs += 1
                    continue
                key = str(p)
                seen.add(key)
                old = known.get(key)
                if old and old[0] == st.st_size and abs(old[1] - st.st_mtime) < 1e-6:
                    continue
                ext = p.suffix.lower()
                tier = "text" if ext in TEXT_TIER else "doc" if ext in DOC_TIER else "blob"
                try:
                    qh = quick_hash(p, st.st_size)
                    fh = full_hash(p) if full else ""
                except OSError:
                    errs += 1
                    continue
                kw = ""
                if key not in tagged_paths and tier == "text":
                    try:
                        with p.open("r", encoding="utf-8", errors="ignore") as fh_:
                            kw = keywords(fh_.read(4096), p.stem)
                    except OSError:
                        pass
                elif tier == "blob":
                    kw = keywords("", p.stem.replace("_", " ").replace("-", " "))
                con.execute("INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (key, p.name, ext, st.st_size, st.st_mtime, when(st.st_ctime), when(st.st_mtime),
                             qh, fh, tier, kw, stamp))
                new += 1
                if new % 500 == 0:
                    con.commit()
                    print(f"  ... catalog {new} files", file=sys.stderr)
    roots = [str(s) for s in sources if s.is_dir()]
    for (p,) in con.execute("SELECT path FROM files").fetchall():
        if any(p.startswith(r) for r in roots) and p not in seen:
            con.execute("DELETE FROM files WHERE path=?", (p,))
    con.commit()
    return {"files_seen": len(seen), "cataloged_new_or_changed": new, "catalog_errors": errs, "paths": seen}


def export_catalog(con, out: Path, stamp: str, paths: set[str], results: dict[str, dict]) -> dict:
    rows = []
    for p, name, ext, size, created, modified, qh, fh, tier, kw in con.execute(
            "SELECT path, name, ext, size, created, modified, quick_hash, full_hash, tier, keywords FROM files"):
        if p not in paths:
            continue
        res = results.get(p, {})
        rows.append({"path": p, "name": name, "ext": ext, "size": size, "size_h": human(size), "tier": tier,
                     "created": created, "modified": modified, "quick_hash": qh, "sha256": fh,
                     "primary_tag": res.get("primary_tag", ""), "primary_category": res.get("primary_category", ""),
                     "keywords": kw})
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["size"]:
            groups[(r["sha256"] or r["quick_hash"]) + f":{r['size']}"].append(r)
    dupes = []
    for g, rs in groups.items():
        if len(rs) > 1:
            for r in sorted(rs, key=lambda x: x["path"]):
                dupes.append({"group": g.split(":")[0][:12], "copies": len(rs), "size_h": r["size_h"],
                              "wasted_bytes": r["size"] * (len(rs) - 1), "path": r["path"]})
    dupes.sort(key=lambda r: (-r["wasted_bytes"], r["group"], r["path"]))
    files = {"catalog": T2.write_csv(out / f"{stamp}_catalog.csv", rows,
                                     ["path", "name", "ext", "size_h", "tier", "created", "modified",
                                      "primary_tag", "primary_category", "keywords", "quick_hash", "sha256", "size"]),
             "duplicates": T2.write_csv(out / f"{stamp}_duplicates.csv", dupes,
                                        ["group", "copies", "size_h", "wasted_bytes", "path"])}
    reclaimable = sum(rs[0]["size"] * (len(rs) - 1) for rs in groups.values() if len(rs) > 1)
    return {"outputs": files, "catalog_files": len(rows), "duplicate_files": len(dupes),
            "duplicate_space_reclaimable": human(reclaimable), "by_tier": dict(Counter(r["tier"] for r in rows))}


# ------------------------------------------------------------------------------ scan
def parse_exts(s: str) -> set[str]:
    return {e.strip().lower() if e.strip().startswith(".") else "." + e.strip().lower() for e in s.split(",") if e.strip()}


def get_sources(args) -> list[Path]:
    sources = [Path(s) for s in (args.source or [])]
    if getattr(args, "source_list", None):
        sources += [Path(l.strip()) for l in Path(args.source_list).read_text(encoding="utf-8-sig").splitlines()
                    if l.strip() and not l.strip().startswith("#")]
    if not sources:
        raise SystemExit("provide --source or --source-list")
    return sources


def run_scan(args, con, ctx: Ctx, stamp: str | None = None, quiet: bool = False) -> dict:
    t0 = time.time()
    sources = get_sources(args)
    run_stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stamp = stamp or run_stamp
    exts = parse_exts(args.extensions)
    ctx.done = {h for (h,) in con.execute("SELECT content_hash FROM hashes_scanned WHERE registry_hash=?",
                                          (ctx.registry_hash,))}
    if ctx.sem_model:
        ctx.sem_done = {h for (h,) in con.execute("SELECT DISTINCT content_hash FROM sem_scores WHERE model=?",
                                                  (ctx.sem_model,))}
    seen: dict[str, str] = {}
    scanned = skipped = 0
    error_rows: list[dict] = []
    paths = list(iter_docs(sources, exts, args.limit))
    by_ext = Counter(p.suffix.lower() for p in paths)
    if not quiet:
        print(f"[scan] {len(paths)} documents ({', '.join(f'{e} {n}' for e, n in by_ext.most_common())})",
              file=sys.stderr)
    for start in range(0, len(paths), 200):
        batch = paths[start:start + 200]
        texts = get_texts(con, batch, args.workers)
        for path in batch:
            text, err = texts.get(path, ("", "missing"))
            if err:
                error_rows.append({"path": str(path), "error": err})
                continue
            if not text.strip():
                error_rows.append({"path": str(path), "error": "no extractable text (scanned image PDF?)"})
                continue
            h, new = index_doc(con, ctx, path, text, run_stamp, args.force, error_rows)
            seen[str(path)] = h
            scanned += new
            skipped += not new
        con.commit()
        if not quiet and len(paths) > 200:
            print(f"  ... {min(start + 200, len(paths))}/{len(paths)} ({scanned} tagged, {skipped} unchanged)",
                  file=sys.stderr)

    roots = [str(s) for s in sources if s.is_dir()]
    if roots and not args.limit:
        for (p,) in con.execute("SELECT path FROM documents").fetchall():
            if any(p.startswith(r) for r in roots) and p not in seen:
                con.execute("DELETE FROM documents WHERE path=?", (p,))
        con.commit()

    params = T2.load_params(T2.vars_params(args))
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    result = T2.export_results(con, args, ctx.tags, ctx.tag_by_name, ctx.registry_hash, ctx.sem_model, params,
                               seen, stamp, error_rows)
    results = doc_results(con, ctx, params, seen)

    if args.write_sidecars:
        n = 0
        for p, res in results.items():
            if res["accepted"] and write_if_changed(Path(p + SIDECAR_EXT), sidecar_body(Path(p), res, ctx.registry_hash)):
                n += 1
        result["sidecars_written"] = n
    if args.write_folder_markers:
        result["folder_markers_written"] = write_folder_markers(con, sources, results, args.all_folders)
    if args.catalog:
        cat = run_catalog(con, sources, set(seen), args.full_hash, args.force)
        exp = export_catalog(con, out, stamp, cat.pop("paths"), results)
        result["outputs"].update(exp.pop("outputs"))
        result.update(cat)
        result.update(exp)

    con.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?)",
                (run_stamp, TAGGER_VERSION, ctx.registry_hash, json.dumps(params),
                 json.dumps([str(s) for s in sources]), scanned, skipped, len(error_rows)))
    con.commit()
    result.update({"documents_seen": len(seen), "documents_by_type": dict(by_ext), "newly_tagged": scanned,
                   "unchanged_skipped": skipped, "problems": len(error_rows), "semantic": ctx.sem_model or "off",
                   "seconds": round(time.time() - t0, 1), "params": params})
    (out / f"{stamp}_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def cmd_scan(args) -> int:
    con = open_db(Path(args.db))
    ctx = registry_ctx(args, con)
    print(json.dumps(run_scan(args, con, ctx), indent=2))
    return 0


def cmd_catalog(args) -> int:
    con = open_db(Path(args.db))
    sources = get_sources(args)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tagged = {p for (p,) in con.execute("SELECT path FROM documents")}
    cat = run_catalog(con, sources, tagged, args.full_hash, args.force)
    ctx = registry_ctx(args, con, semantic=False)
    seen = {p: h for p, h in con.execute("SELECT path, content_hash FROM documents WHERE registry_hash=?",
                                         (ctx.registry_hash,)) if p in cat["paths"]}
    results = doc_results(con, ctx, T2.load_params(T2.vars_params(args)), seen)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    exp = export_catalog(con, out, stamp, cat.pop("paths"), results)
    print(json.dumps({**cat, **exp}, indent=2))
    return 0


def cmd_watch(args) -> int:
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        raise SystemExit("watch needs watchdog:  pip install watchdog")
    sources = [s for s in get_sources(args) if s.is_dir()]
    if not sources:
        raise SystemExit("watch needs at least one folder in --source")
    exts = parse_exts(args.extensions)
    out_dir = Path(args.output).resolve()
    state = {"dirty": True, "last": 0.0}

    class Handler(FileSystemEventHandler):
        def on_any_event(self, event):
            if event.is_directory:
                return
            for raw in (getattr(event, "src_path", ""), getattr(event, "dest_path", "")):
                if not raw:
                    continue
                p = Path(raw)
                if skip_file(p.name) or any(part in SKIP_DIRS for part in p.parts):
                    continue
                try:
                    if out_dir in p.resolve().parents:
                        continue
                except OSError:
                    pass
                if args.catalog or p.suffix.lower() in exts:
                    state["dirty"], state["last"] = True, time.time()
                    return

    con = open_db(Path(args.db))
    ctx = registry_ctx(args, con)
    obs = Observer()
    for s in sources:
        obs.schedule(Handler(), str(s), recursive=True)
    obs.start()
    print(f"[watch] watching {len(sources)} folder(s); results -> {out_dir}\\latest_*.csv  (Ctrl+C to stop)")
    try:
        while True:
            if state["dirty"] and time.time() - state["last"] >= args.debounce:
                state["dirty"] = False
                r = run_scan(args, con, ctx, stamp="latest", quiet=True)
                print(f"[{now()}] {r['documents_seen']} docs | {r['newly_tagged']} re-tagged | "
                      f"{r['problems']} problems | {r['seconds']}s"
                      + (f" | sidecars {r.get('sidecars_written', 0)}" if args.write_sidecars else "")
                      + (f" | markers {r.get('folder_markers_written', 0)}" if args.write_folder_markers else ""),
                      flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        obs.stop()
        obs.join()
    return 0


# ------------------------------------------------------------------------------ main
def add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--registry", default=str(T2.DEFAULT_REGISTRY))
    p.add_argument("--exclusions", default=str(T2.DEFAULT_EXCLUSIONS),
                   help="CSV tag,phrase - drop a tag in any paragraph containing the phrase")
    p.add_argument("--db", default=str(T2.DEFAULT_DB))
    p.add_argument("--ambiguous", default=str(ROOT / "01_REGISTRY" / "ambiguous_terms.txt"))
    p.add_argument("--category-weights", default=str(ROOT / "01_REGISTRY" / "category_weights.csv"))
    p.add_argument("--semantic", action="store_true", help="use Ollama embeddings (meaning layer)")
    p.add_argument("--embed-model", default="nomic-embed-text")
    p.add_argument("--ollama-url", default="http://localhost:11434")
    for k, v in T2.DEFAULT_PARAMS.items():
        p.add_argument("--" + k.replace("_", "-"), dest=k, type=type(v), default=None)


def add_scan_opts(p: argparse.ArgumentParser) -> None:
    p.add_argument("--source", action="append", help="file or folder; repeatable")
    p.add_argument("--source-list", help="text file with one path per line")
    p.add_argument("--extensions", default=DEFAULT_DOC_EXTS, help=f"documents to tag (default {DEFAULT_DOC_EXTS})")
    p.add_argument("--limit", type=int)
    p.add_argument("--force", action="store_true", help="re-tag even unchanged files")
    p.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1),
                   help="processes for PDF/DOCX extraction")
    p.add_argument("--output", default=str(T2.DEFAULT_INDEX))
    p.add_argument("--tagged", default=str(T2.DEFAULT_TAGGED))
    p.add_argument("--export-paragraphs", action="store_true")
    p.add_argument("--catalog", action="store_true", help="also catalog EVERY file (any type) + duplicates")
    p.add_argument("--full-hash", action="store_true", help="catalog: full sha256 instead of quick hash")
    p.add_argument("--write-sidecars", action="store_true", help="WRITE <file>.fmeta beside each tagged document")
    p.add_argument("--write-folder-markers", action="store_true", help="WRITE .folder.fmeta into folders")
    p.add_argument("--all-folders", action="store_true", help="markers in every folder, not only ones with tagged docs")
    p.add_argument("--copy-by-primary-tag", action="store_true", help="COPY files into 03_TAGGED (never moves)")
    p.add_argument("--write-frontmatter", action="store_true",
                   help="WRITE auto_tags: into .md frontmatter (modifies your files; off by default)")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Theophysics Convergence Tagger v3")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="tag documents")
    add_common(s)
    add_scan_opts(s)
    s.set_defaults(func=cmd_scan)
    c = sub.add_parser("catalog", help="catalog every file without tagging")
    add_common(c)
    c.add_argument("--source", action="append")
    c.add_argument("--source-list")
    c.add_argument("--full-hash", action="store_true")
    c.add_argument("--force", action="store_true")
    c.add_argument("--output", default=str(T2.DEFAULT_INDEX))
    c.set_defaults(func=cmd_catalog)
    w = sub.add_parser("watch", help="scan, then re-scan whenever files change")
    add_common(w)
    add_scan_opts(w)
    w.add_argument("--debounce", type=float, default=5.0, help="seconds of quiet before re-scanning")
    w.set_defaults(func=cmd_watch)
    g = sub.add_parser("gold-template", help="sample docs for hand-checking")
    add_common(g)
    g.add_argument("-n", type=int, default=50)
    g.set_defaults(func=T2.cmd_gold_template)
    for name, fn in (("eval", T2.cmd_eval), ("tune", T2.cmd_tune)):
        e = sub.add_parser(name)
        add_common(e)
        e.add_argument("--gold", default=str(T2.REVIEW_DIR / "gold.csv"))
        e.set_defaults(func=fn)
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0].startswith("-") and argv[0] not in ("-h", "--help"):
        argv.insert(0, "scan")
    args = build_parser().parse_args(argv)
    if getattr(args, "exclusions", None) and not Path(args.exclusions).exists():
        args.exclusions = None
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
