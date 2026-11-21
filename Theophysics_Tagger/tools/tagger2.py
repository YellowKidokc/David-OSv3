#!/usr/bin/env python3
"""Theophysics Convergence Tagger v2.

Read-only by default. Pipeline (Annif-style):
  1. Lexical layer   - stemmed phrase matching, CamelCase auto-split, per-tag exclusions,
                       title/heading weighting, tf-idf scoring, minimum-hit gate.
  2. Semantic layer  - optional (--semantic): Ollama embeddings of tag definitions vs
                       paragraphs, so "unmerited favor" can find Grace without the word.
  3. Fusion          - noisy-OR of the two scores, threshold, max tags, category roll-up.
  4. Measurement     - gold set (06_REVIEW/gold.csv) -> eval / tune -> tuned_params.json.

Storage: SQLite (02_INDEX/tagger.db), keyed by content hash (frontmatter excluded), so
moved files keep identity, duplicates are detected, and unchanged files are skipped.

Subcommands:
  scan           tag files (default if you start with --source)
  gold-template  write 06_REVIEW/gold_template.csv for hand correction
  eval           precision / recall / F1 against 06_REVIEW/gold.csv
  tune           grid-search params against the gold set, write tuned_params.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import shutil
import sqlite3
import sys
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path

TAGGER_VERSION = "2.0.0"
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = ROOT / "01_REGISTRY" / "combined_tag_registry.csv"
DEFAULT_EXCLUSIONS = ROOT / "01_REGISTRY" / "exclusions.csv"
DEFAULT_INDEX = ROOT / "02_INDEX"
DEFAULT_DB = DEFAULT_INDEX / "tagger.db"
DEFAULT_TAGGED = ROOT / "03_TAGGED"
REVIEW_DIR = ROOT / "06_REVIEW"
TUNED_PARAMS = REVIEW_DIR / "tuned_params.json"

DEFAULT_PARAMS = {
    "title_weight": 3.0,
    "heading_weight": 2.0,
    "min_hits": 2.0,        # weighted hits needed unless semantic is strong
    "threshold": 0.25,      # final score needed to accept a tag
    "max_tags": 12,
    "w_lex": 1.0,
    "w_sem": 0.7,
    "sem_floor": 3.0,       # within-document z-score below this contributes nothing
    "sem_ceil": 4.5,        # z at/above this counts as full semantic support
    "sem_accept": 0.5,      # sem_rel at/above this (z >= 3.75) can accept a tag with few hits
}
SEM_KEY_SUFFIX = "|z1"     # stored semantic scores are within-document z-scores, version 1

# ----------------------------------------------------------------------------- text
try:
    from nltk.stem.snowball import SnowballStemmer
    _stemmer = SnowballStemmer("english").stem
except Exception:  # fallback: crude suffix stripper
    def _stemmer(w: str) -> str:
        for suf in ("ations", "ation", "ings", "ing", "ness", "ments", "ment", "edly", "ed", "es", "s"):
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                return w[: -len(suf)]
        return w

TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['\u2019][A-Za-z]+)?")
FM_RE = re.compile(r"\A\ufeff?---[ \t]*\r?\n.*?\r?\n---[ \t]*\r?\n", re.S)
FENCE_RE = re.compile(r"```.*?```", re.S)


@lru_cache(maxsize=300_000)
def stem(word: str) -> str:
    w = word.lower().replace("\u2019", "'")
    w = re.sub(r"'s$", "", w)
    s = _stemmer(w)
    # unify -ify families: sanctified/sanctification, justified/justification, glorified/glorify
    if len(s) > 5 and s.endswith("i"):
        s = s[:-1]
    return s


def stems_of(text: str) -> list[str]:
    return [stem(m.group()) for m in TOKEN_RE.finditer(text)]


_SENT_START_GAP = re.compile(r"(?:[.!?:;\n#*>|\-\u2014\"\u201c(]\s*)$")


def tokens_of(text: str) -> tuple[list[str], list[str], list[bool]]:
    """(stems, lowercase forms, capitalized-mid-sentence flags)."""
    stems, lowers, caps = [], [], []
    prev_end = 0
    for m in TOKEN_RE.finditer(text):
        w = m.group()
        gap = text[prev_end:m.start()]
        sentence_start = (not stems) or bool(_SENT_START_GAP.search(gap))
        caps.append(w[:1].isupper() and not sentence_start)
        lowers.append(w.lower().replace("\u2019", "'"))
        stems.append(stem(w))
        prev_end = m.end()
    return stems, lowers, caps


def camel_split(s: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", s)


def slugify(value: str) -> str:
    value = camel_split(value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "item"


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    if path.exists():
        h.update(path.read_bytes())
    return h.hexdigest()


# ------------------------------------------------------------------------- registry
@dataclass
class Tag:
    idx: int
    tag: str
    slug: str
    category: str
    parent_path: str
    variable: str
    description: str
    terms: list[str]
    excludes: list[str] = field(default_factory=list)
    weight: float = 1.0
    camel: bool = False


def load_word_list(path: Path | None) -> set[str]:
    if not path or not path.exists():
        return set()
    return {l.strip().lower() for l in path.read_text(encoding="utf-8-sig").splitlines()
            if l.strip() and not l.strip().startswith("#")}


def load_category_weights(path: Path | None) -> dict[str, float]:
    out: dict[str, float] = {}
    if path and path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                try:
                    out[(row.get("category") or "").strip()] = float(row.get("weight") or 1)
                except ValueError:
                    pass
    return out


def load_registry(path: Path, exclusions_path: Path | None, category_weights: dict[str, float] | None = None) -> list[Tag]:
    category_weights = category_weights or {}
    extra_ex: dict[str, list[str]] = defaultdict(list)
    if exclusions_path and exclusions_path.exists():
        with exclusions_path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                t, p = (row.get("tag") or "").strip().lower(), (row.get("phrase") or "").strip().lower()
                if t and p:
                    extra_ex[t].append(p)
    tags: list[Tag] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("tag") or "").strip()
            if not name:
                continue
            if (row.get("route_enabled") or "yes").strip().lower() in ("no", "false", "0"):
                continue
            aliases = [a.strip() for a in (row.get("aliases") or "").split(";") if a.strip()]
            spaced = camel_split(name)
            terms = list(dict.fromkeys([name, spaced, *aliases]))
            excludes = [p.strip().lower() for p in (row.get("exclude") or "").split(";") if p.strip()]
            excludes += extra_ex.get(name.lower(), [])
            try:
                weight = float(row.get("weight") or 1.0)
            except ValueError:
                weight = 1.0
            category = (row.get("category") or "Uncategorized").strip()
            weight *= category_weights.get(category, 1.0)
            tags.append(Tag(
                idx=len(tags), tag=name, slug=(row.get("slug") or slugify(name)).strip(),
                category=category,
                parent_path=(row.get("parent_path") or name).strip(),
                variable=(row.get("master_equation_variable") or "").strip(),
                description=(row.get("description") or "").strip(),
                terms=terms, excludes=excludes, weight=weight,
                camel=(spaced != name and " " not in name),
            ))
    return tags


def build_index(tags: list[Tag], ambiguous: set[str] | None = None):
    """Index entries: (stem_seq, tag_idx, exact_lower_seq_or_None, needs_capital).
    - Terms whose stems collide with a DIFFERENT tag's different word (Pentecost / Pentecostal)
      fall back to exact lowercase matching.
    - Single-word terms listed in ambiguous_terms.txt (rest, will, word, calling ...) only count
      when capitalized mid-sentence ('the Word', 'Free Will', 'Sabbath Rest')."""
    amb_stems = {stem(w) for w in (ambiguous or set())}
    entries = []
    for t in tags:
        for term in t.terms:
            seq = tuple(stems_of(term))
            if seq:
                lseq = tuple(m.group().lower().replace("\u2019", "'") for m in TOKEN_RE.finditer(term))
                entries.append((seq, t.idx, lseq))
    owners: dict[tuple, set] = defaultdict(set)
    for seq, ti, lseq in entries:
        owners[seq].add((ti, lseq))
    index: dict[str, list] = defaultdict(list)
    seen = set()
    for seq, ti, lseq in entries:
        group = owners[seq]
        collide = len({x[0] for x in group}) > 1 and len({x[1] for x in group}) > 1
        exact = lseq if collide else None
        need_cap = len(seq) == 1 and seq[0] in amb_stems
        key = (seq, ti, exact)
        if key in seen:
            continue
        seen.add(key)
        index[seq[0]].append((seq, ti, exact, need_cap))
    for k in index:
        index[k].sort(key=lambda x: -len(x[0]))
    return index


def count_hits(toks, index) -> Counter:
    """Longest-match counting: a tag fully inside a longer phrase match of another tag
    does not count (e.g. 'Holy Spirit' does not also fire Holiness or Spirit)."""
    stems, lowers, caps = toks
    matches: list[tuple[int, int, int]] = []   # (tag, start, end)
    seen: set[tuple[int, int]] = set()
    n = len(stems)
    for i, s in enumerate(stems):
        cands = index.get(s)
        if not cands:
            continue
        for seq, t, exact, need_cap in cands:
            if (t, i) in seen:
                continue
            L = len(seq)
            if i + L > n:
                continue
            if exact is not None:
                ok = tuple(lowers[i:i + L]) == exact
            else:
                ok = L == 1 or tuple(stems[i:i + L]) == seq
            if ok and need_cap and not caps[i]:
                ok = False
            if ok:
                matches.append((t, i, i + L))
                seen.add((t, i))
    long_spans = [(a, b, t) for t, a, b in matches if b - a > 1]
    c: Counter = Counter()
    for t, a, b in matches:
        if any(t2 != t and a2 <= a and b <= b2 and (b2 - a2) > (b - a) for a2, b2, t2 in long_spans):
            continue
        c[t] += 1
    return c


# ------------------------------------------------------------------------ scripture
_BOOKS: dict[str, list[str]] = {
    "Genesis": ["Genesis", "Gen", "Gn"], "Exodus": ["Exodus", "Exod", "Ex"],
    "Leviticus": ["Leviticus", "Lev"], "Numbers": ["Numbers", "Num"],
    "Deuteronomy": ["Deuteronomy", "Deut", "Dt"], "Joshua": ["Joshua", "Josh"],
    "Judges": ["Judges", "Judg"], "Ruth": ["Ruth"], "Ezra": ["Ezra"],
    "Nehemiah": ["Nehemiah", "Neh"], "Esther": ["Esther", "Esth"], "Job": ["Job"],
    "Psalms": ["Psalms", "Psalm", "Ps", "Psa"], "Proverbs": ["Proverbs", "Prov", "Pr"],
    "Ecclesiastes": ["Ecclesiastes", "Eccles", "Eccl", "Ecc"],
    "Song of Solomon": ["Song of Solomon", "Song of Songs"],
    "Isaiah": ["Isaiah", "Isa"], "Jeremiah": ["Jeremiah", "Jer"],
    "Lamentations": ["Lamentations", "Lam"], "Ezekiel": ["Ezekiel", "Ezek"],
    "Daniel": ["Daniel", "Dan"], "Hosea": ["Hosea", "Hos"], "Joel": ["Joel"],
    "Amos": ["Amos"], "Obadiah": ["Obadiah", "Obad"], "Jonah": ["Jonah"],
    "Micah": ["Micah", "Mic"], "Nahum": ["Nahum"], "Habakkuk": ["Habakkuk", "Hab"],
    "Zephaniah": ["Zephaniah", "Zeph"], "Haggai": ["Haggai", "Hag"],
    "Zechariah": ["Zechariah", "Zech"], "Malachi": ["Malachi", "Mal"],
    "Matthew": ["Matthew", "Matt", "Mt"], "Mark": ["Mark", "Mk"], "Luke": ["Luke", "Lk"],
    "John": ["John", "Jn"], "Acts": ["Acts"], "Romans": ["Romans", "Rom"],
    "Galatians": ["Galatians", "Gal"], "Ephesians": ["Ephesians", "Eph"],
    "Philippians": ["Philippians", "Phil"], "Colossians": ["Colossians", "Col"],
    "Titus": ["Titus"], "Philemon": ["Philemon", "Phlm"], "Hebrews": ["Hebrews", "Heb"],
    "James": ["James", "Jas"], "Jude": ["Jude"], "Revelation": ["Revelation", "Rev"],
}
_NUMBERED = {
    "Samuel": (2, ["Samuel", "Sam"]), "Kings": (2, ["Kings", "Kgs"]),
    "Chronicles": (2, ["Chronicles", "Chron", "Chr"]), "Corinthians": (2, ["Corinthians", "Cor"]),
    "Thessalonians": (2, ["Thessalonians", "Thess"]), "Timothy": (2, ["Timothy", "Tim"]),
    "Peter": (2, ["Peter", "Pet"]), "John": (3, ["John", "Jn"]),
}
_ROMAN = {1: "I", 2: "II", 3: "III"}
_ORD = {1: "First", 2: "Second", 3: "Third"}
for base, (count, forms) in _NUMBERED.items():
    for n in range(1, count + 1):
        canon = f"{n} {base}"
        variants = []
        for form in forms:
            variants += [f"{n} {form}", f"{n}{form}", f"{_ROMAN[n]} {form}", f"{_ORD[n]} {form}"]
        _BOOKS[canon] = variants

# chapter-only refs are allowed only for full, unambiguous names
_AMBIGUOUS = {"Job", "Mark", "Acts", "Numbers", "John", "James", "Jude", "Ruth", "Amos",
              "Joel", "Titus", "Jonah", "Daniel", "Micah", "Nahum", "Ezra", "Luke", "Matthew"}
_VARIANT_TO_BOOK = {v: b for b, vs in _BOOKS.items() for v in vs}
_FULL_NAMES = {b for b in _BOOKS} | {"Psalm"}
_SCRIPTURE_RE = re.compile(
    r"(?<![A-Za-z0-9])(" + "|".join(re.escape(v) for v in sorted(_VARIANT_TO_BOOK, key=len, reverse=True))
    + r")\.?\s*(\d{1,3})(?::(\d{1,3}(?:\s*[-\u2013]\s*\d{1,3})?))?(?![\d:])"
)


def find_scripture(text: str) -> list[tuple[str, str, int, str]]:
    out = []
    for m in _SCRIPTURE_RE.finditer(text):
        variant, chap, verse = m.group(1), int(m.group(2)), m.group(3)
        book = _VARIANT_TO_BOOK[variant]
        if not (1 <= chap <= 150):
            continue
        if verse is None and (variant not in _FULL_NAMES or book in _AMBIGUOUS or book[0].isdigit()):
            continue
        verse = re.sub(r"\s+", "", verse or "").replace("\u2013", "-")
        ref = f"{book} {chap}" + (f":{verse}" if verse else "")
        out.append((ref, book, chap, verse))
    return out


# ---------------------------------------------------------------------- doc parsing
def parse_doc(path: Path, text: str) -> tuple[str, str, list[str]]:
    """Return (body_for_hash, title, paragraphs)."""
    body = FM_RE.sub("", text, count=1)
    clean = FENCE_RE.sub("\n", body)
    clean = re.sub(r"\]\([^)]*\)", "]", clean)          # markdown link targets
    clean = re.sub(r"<[^>]+>", " ", clean)               # html tags
    clean = re.sub(r"(?m)^(#{1,6}\s.*)$", r"\n\1\n", clean)  # headings own paragraph
    paras = [p.strip() for p in re.split(r"\n\s*\n", clean) if p.strip()]
    h1 = next((p.lstrip("#").strip() for p in paras if re.match(r"#\s", p)), "")
    title = (path.stem.replace("_", " ").replace("-", " ") + " . " + h1).strip()
    return body, title, paras


def content_hash(body: str) -> str:
    norm = body.replace("\r\n", "\n").strip()
    return hashlib.sha256(norm.encode("utf-8", errors="ignore")).hexdigest()[:20]


# ------------------------------------------------------------------- semantic layer
class Embedder:
    def __init__(self, url: str, model: str):
        self.url, self.model = url.rstrip("/"), model
        self.prefix = "classification: " if "nomic" in model else ""

    def check(self) -> None:
        try:
            with urllib.request.urlopen(self.url + "/api/tags", timeout=5) as r:
                names = [m.get("name", "") for m in json.loads(r.read()).get("models", [])]
        except Exception as exc:
            raise SystemExit(f"[semantic] Ollama not reachable at {self.url} ({exc}). "
                             f"Start it with 'ollama serve' or drop --semantic.")
        if not any(n == self.model or n.startswith(self.model + ":") for n in names):
            raise SystemExit(f"[semantic] model '{self.model}' not pulled. Run: ollama pull {self.model}")

    def embed(self, texts: list[str]):
        import numpy as np
        vecs = []
        for i in range(0, len(texts), 16):
            batch = [self.prefix + t for t in texts[i:i + 16]]
            req = urllib.request.Request(self.url + "/api/embed",
                                         data=json.dumps({"model": self.model, "input": batch}).encode(),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                vecs.extend(json.loads(r.read())["embeddings"])
        arr = np.asarray(vecs, dtype="float32")
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms


def tag_embed_text(t: Tag) -> str:
    desc = f" {t.description}" if t.description else ""
    return f"{camel_split(t.tag)}.{desc} ({t.category}; {t.parent_path.replace('/', ' > ')})"


def load_tag_matrix(con, emb: Embedder, tags: list[Tag]):
    import numpy as np
    have = {}
    for tag, th, blob in con.execute("SELECT tag, text_hash, vec FROM tag_embeddings WHERE model=?", (emb.model,)):
        have[tag] = (th, blob)
    missing, texts = [], []
    for t in tags:
        txt = tag_embed_text(t)
        th = hashlib.sha1(txt.encode()).hexdigest()[:16]
        if have.get(t.tag, (None,))[0] != th:
            missing.append((t, th))
            texts.append(txt)
    if texts:
        print(f"[semantic] embedding {len(texts)} tag definitions ...", file=sys.stderr)
        vecs = emb.embed(texts)
        con.executemany("INSERT OR REPLACE INTO tag_embeddings(tag, model, text_hash, vec) VALUES (?,?,?,?)",
                        [(t.tag, emb.model, th, v.tobytes()) for (t, th), v in zip(missing, vecs)])
        con.commit()
        for (t, th), v in zip(missing, vecs):
            have[t.tag] = (th, v.tobytes())
    return np.vstack([np.frombuffer(have[t.tag][1], dtype="float32") for t in tags])


def semantic_scores(emb: Embedder, tag_matrix, title: str, paras: list[str], top: int = 25):
    """Return (tag_idx, z) where z = how many standard deviations a tag's best paragraph
    similarity stands above this document's median similarity across ALL tags.
    Raw cosine is useless as a cutoff (each document has its own baseline); z is not."""
    body = [p for p in paras if not p.startswith("#") and len(p.split()) >= 8]
    if len(body) > 48:
        step = len(body) / 48
        body = [body[int(i * step)] for i in range(48)]
    chunks = [title] + [p[:1200] for p in body]
    P = emb.embed(chunks)
    sims = (P @ tag_matrix.T).max(axis=0)
    med, sd = float(sorted(sims)[len(sims) // 2]), float(sims.std()) or 1.0
    z = (sims - med) / sd
    order = z.argsort()[::-1][:top]
    return [(int(i), float(z[i])) for i in order if z[i] >= 2.0]


# ------------------------------------------------------------------------- database
SCHEMA = """
CREATE TABLE IF NOT EXISTS documents(path TEXT PRIMARY KEY, content_hash TEXT, title TEXT,
    n_tokens INT, scanned_at TEXT, registry_hash TEXT);
CREATE TABLE IF NOT EXISTS tag_counts(content_hash TEXT, tag TEXT, title_hits INT, heading_hits INT,
    body_hits INT, PRIMARY KEY(content_hash, tag));
CREATE TABLE IF NOT EXISTS sem_scores(content_hash TEXT, tag TEXT, model TEXT, cos REAL,
    PRIMARY KEY(content_hash, tag, model));
CREATE TABLE IF NOT EXISTS para_hits(content_hash TEXT, para_idx INT, tag TEXT, hits INT, snippet TEXT);
CREATE TABLE IF NOT EXISTS scripture(content_hash TEXT, ref TEXT, book TEXT, chapter INT, verse TEXT);
CREATE TABLE IF NOT EXISTS tag_embeddings(tag TEXT, model TEXT, text_hash TEXT, vec BLOB,
    PRIMARY KEY(tag, model));
CREATE TABLE IF NOT EXISTS hashes_scanned(content_hash TEXT, registry_hash TEXT, sem_model TEXT,
    PRIMARY KEY(content_hash, registry_hash));
CREATE TABLE IF NOT EXISTS runs(stamp TEXT PRIMARY KEY, version TEXT, registry_hash TEXT, params TEXT,
    sources TEXT, scanned INT, skipped INT, errors INT);
CREATE INDEX IF NOT EXISTS ix_doc_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS ix_para_hash ON para_hits(content_hash);
CREATE INDEX IF NOT EXISTS ix_scr_hash ON scripture(content_hash);
"""


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.executescript(SCHEMA)
    return con


def load_params(overrides: dict | None = None) -> dict:
    p = dict(DEFAULT_PARAMS)
    if TUNED_PARAMS.exists():
        try:
            p.update({k: v for k, v in json.loads(TUNED_PARAMS.read_text(encoding="utf-8")).items()
                      if k in DEFAULT_PARAMS})
        except Exception:
            pass
    if overrides:
        p.update({k: v for k, v in overrides.items() if v is not None})
    return p


# -------------------------------------------------------------------------- scoring
def gather(con, registry_hash: str, sem_model: str | None):
    """Load raw evidence for every document tagged under the current registry."""
    hashes = [h for (h,) in con.execute(
        "SELECT DISTINCT content_hash FROM documents WHERE registry_hash=?", (registry_hash,))]
    hs = set(hashes)
    counts: dict[str, dict[str, tuple[int, int, int]]] = defaultdict(dict)
    for h, tag, ti, he, bo in con.execute("SELECT content_hash, tag, title_hits, heading_hits, body_hits FROM tag_counts"):
        if h in hs:
            counts[h][tag] = (ti, he, bo)
    sems: dict[str, dict[str, float]] = defaultdict(dict)
    if sem_model:
        for h, tag, cos in con.execute("SELECT content_hash, tag, cos FROM sem_scores WHERE model=?", (sem_model,)):
            if h in hs:
                sems[h][tag] = cos
    df = Counter()
    for h in hashes:
        for tag in counts[h]:
            df[tag] += 1
    return hashes, counts, sems, df


def score_doc(h, counts, sems, df, N, params, tag_by_name) -> list[dict]:
    p = params
    rows = {}
    for tag, (ti, he, bo) in counts.get(h, {}).items():
        t = tag_by_name.get(tag)
        w = t.weight if t else 1.0
        wtf = (p["title_weight"] * ti + p["heading_weight"] * he + bo) * w
        if wtf <= 0:
            continue
        idf = math.log((N + 1) / (df[tag] + 1)) + 1.0
        rows[tag] = {"tag": tag, "wtf": wtf, "lex_raw": (1 + math.log(wtf)) * idf, "cos": None}
    for tag, cos in sems.get(h, {}).items():
        rows.setdefault(tag, {"tag": tag, "wtf": 0.0, "lex_raw": 0.0, "cos": None})["cos"] = cos
    if not rows:
        return []
    mx = max(r["lex_raw"] for r in rows.values()) or 1.0
    span = max(p["sem_ceil"] - p["sem_floor"], 1e-6)
    out = []
    for r in rows.values():
        lex = r["lex_raw"] / mx
        sem = 0.0 if r["cos"] is None else min(1.0, max(0.0, (r["cos"] - p["sem_floor"]) / span))
        score = 1 - (1 - p["w_lex"] * lex) * (1 - p["w_sem"] * sem)
        ok = score >= p["threshold"] and (r["wtf"] >= p["min_hits"] or sem >= p["sem_accept"])
        out.append({**r, "lex": lex, "sem": sem, "score": score, "accepted": ok})
    out.sort(key=lambda r: (-r["score"], r["tag"]))
    kept = 0
    for r in out:
        if r["accepted"]:
            kept += 1
            if kept > p["max_tags"]:
                r["accepted"] = False
    return out


def rollup(accepted: list[dict], tag_by_name) -> tuple[str, dict]:
    cats: Counter = Counter()
    for r in accepted:
        t = tag_by_name.get(r["tag"])
        cats[t.category if t else "Uncategorized"] += r["score"]
    primary = cats.most_common(1)[0][0] if cats else ""
    return primary, dict(cats)


# ----------------------------------------------------------------------------- scan
def iter_files(sources: list[Path], exts: set[str], limit: int | None):
    count = 0
    for source in sources:
        it = [source] if source.is_file() else (source.rglob("*") if source.is_dir() else [])
        for path in it:
            if path.is_file() and path.suffix.lower() in exts and not path.name.startswith("~$"):
                yield path
                count += 1
                if limit and count >= limit:
                    return


def write_frontmatter(path: Path, slugs: list[str]) -> bool:
    text = read_text(path)
    block = "auto_tags:\n" + "".join(f"  - {s}\n" for s in slugs)
    m = FM_RE.match(text)
    if m:
        fm = m.group(0)
        inner = re.sub(r"(?m)^auto_tags:[^\n]*\n(?:[ \t]+-[^\n]*\n)*", "", fm)
        new_fm = re.sub(r"\r?\n---[ \t]*\r?\n\Z", "\n" + block + "---\n", inner)
        new = new_fm + text[m.end():]
    else:
        new = "---\n" + block + "---\n" + text
    if new != text:
        path.write_text(new, encoding="utf-8")
        return True
    return False


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> str:
    fields = fields or (list(rows[0].keys()) if rows else ["empty"])
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return str(path)


def cmd_scan(args) -> int:
    registry = Path(args.registry)
    exclusions = Path(args.exclusions) if args.exclusions else None
    amb_path, cw_path = Path(args.ambiguous), Path(args.category_weights)
    tags = load_registry(registry, exclusions, load_category_weights(cw_path))
    tag_by_name = {t.tag: t for t in tags}
    index = build_index(tags, load_word_list(amb_path))
    registry_hash = hashlib.sha256((file_sha(registry) + file_sha(exclusions or Path("_none_"))
                                    + file_sha(amb_path) + file_sha(cw_path)
                                    + TAGGER_VERSION).encode()).hexdigest()[:16]
    con = open_db(Path(args.db))
    exts = {e.strip().lower() if e.strip().startswith(".") else "." + e.strip().lower()
            for e in args.extensions.split(",") if e.strip()}
    sources = [Path(s) for s in (args.source or [])]
    if args.source_list:
        sources += [Path(l.strip()) for l in Path(args.source_list).read_text(encoding="utf-8-sig").splitlines() if l.strip()]
    if not sources:
        raise SystemExit("provide --source or --source-list")

    emb = tag_matrix = None
    sem_model = None
    if args.semantic:
        emb = Embedder(args.ollama_url, args.embed_model)
        emb.check()
        sem_model = emb.model + SEM_KEY_SUFFIX
        tag_matrix = load_tag_matrix(con, emb, tags)

    done = {h for (h,) in con.execute("SELECT content_hash FROM hashes_scanned WHERE registry_hash=?", (registry_hash,))}
    sem_done = set()
    if sem_model:
        sem_done = {h for (h,) in con.execute("SELECT DISTINCT content_hash FROM sem_scores WHERE model=?", (sem_model,))}

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    seen: dict[str, str] = {}   # path -> hash
    scanned = skipped = errors = 0
    error_rows = []
    for n, path in enumerate(iter_files(sources, exts, args.limit), start=1):
        try:
            text = read_text(path)
        except OSError as exc:
            errors += 1
            error_rows.append({"path": str(path), "error": str(exc)})
            continue
        body, title, paras = parse_doc(path, text)
        h = content_hash(body)
        seen[str(path)] = h
        need_lex = args.force or h not in done
        need_sem = bool(sem_model) and (args.force or h not in sem_done)
        if need_lex:
            con.execute("DELETE FROM tag_counts WHERE content_hash=?", (h,))
            con.execute("DELETE FROM para_hits WHERE content_hash=?", (h,))
            con.execute("DELETE FROM scripture WHERE content_hash=?", (h,))
            title_c = count_hits(tokens_of(title), index)
            tl = title.lower()
            for t in list(title_c):
                if tags[t].excludes and any(x in tl for x in tags[t].excludes):
                    del title_c[t]
            head_c, body_c, prow = Counter(), Counter(), []
            n_tokens = 0
            for pi, para in enumerate(paras):
                toks = tokens_of(para)
                n_tokens += len(toks[0])
                c = count_hits(toks, index)
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
                            [(h, *ref) for ref in find_scripture(FENCE_RE.sub("\n", body))])
            con.execute("INSERT OR REPLACE INTO hashes_scanned VALUES (?,?,?)", (h, registry_hash, sem_model or ""))
            con.execute("INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?)",
                        (str(path), h, title, n_tokens, stamp, registry_hash))
            done.add(h)
            scanned += 1
        else:
            con.execute("INSERT OR REPLACE INTO documents VALUES (?,?,?,COALESCE((SELECT n_tokens FROM documents WHERE path=?),0),?,?)",
                        (str(path), h, title, str(path), stamp, registry_hash))
            skipped += 1
        if need_sem:
            con.execute("DELETE FROM sem_scores WHERE content_hash=? AND model=?", (h, sem_model))
            try:
                pairs = semantic_scores(emb, tag_matrix, title, paras)
                con.executemany("INSERT OR REPLACE INTO sem_scores VALUES (?,?,?,?)",
                                [(h, tags[i].tag, sem_model, cos) for i, cos in pairs])
                sem_done.add(h)
            except Exception as exc:
                error_rows.append({"path": str(path), "error": f"semantic: {exc}"})
        if n % 100 == 0:
            con.commit()
            print(f"  ... {n} files ({scanned} tagged, {skipped} unchanged)", file=sys.stderr)
    con.commit()

    # forget paths that vanished from the scanned folders
    roots = [str(s) for s in sources if s.is_dir()]
    if roots and not args.limit:
        for (p,) in con.execute("SELECT path FROM documents").fetchall():
            if any(p.startswith(r) for r in roots) and p not in seen:
                con.execute("DELETE FROM documents WHERE path=?", (p,))
        con.commit()

    params = load_params(vars_params(args))
    result = export_results(con, args, tags, tag_by_name, registry_hash, sem_model, params, seen, stamp,
                            error_rows)
    con.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?)",
                (stamp, TAGGER_VERSION, registry_hash, json.dumps(params), json.dumps([str(s) for s in sources]),
                 scanned, skipped, errors))
    con.commit()
    result.update({"files_seen": len(seen), "newly_tagged": scanned, "unchanged_skipped": skipped,
                   "read_errors": errors, "semantic": sem_model or "off", "params": params})
    (Path(args.output) / f"{stamp}_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


def vars_params(args) -> dict:
    return {k: getattr(args, k, None) for k in DEFAULT_PARAMS}


def export_results(con, args, tags, tag_by_name, registry_hash, sem_model, params, seen, stamp, error_rows):
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    hashes, counts, sems, df = gather(con, registry_hash, sem_model)
    N = len(hashes)
    by_hash: dict[str, list[str]] = defaultdict(list)
    for p, h in seen.items():
        by_hash[h].append(p)

    doc_rows, folder_rows, fm_written, copied = [], [], 0, 0
    for path, h in sorted(seen.items()):
        scored = score_doc(h, counts, sems, df, N, params, tag_by_name)
        acc = [r for r in scored if r["accepted"]]
        primary_cat, _ = rollup(acc, tag_by_name)
        primary = acc[0]["tag"] if acc else ""
        variables = sorted({tag_by_name[r["tag"]].variable for r in acc
                            if r["tag"] in tag_by_name and tag_by_name[r["tag"]].variable})
        doc_rows.append({
            "path": path, "content_hash": h, "primary_tag": primary, "primary_category": primary_cat,
            "n_tags": len(acc),
            "tags": "; ".join(f"{r['tag']}({r['score']:.2f})" for r in acc),
            "semantic_only": "; ".join(r["tag"] for r in acc if r["wtf"] == 0),
            "variables": ";".join(variables),
            "duplicate_of": "; ".join(p for p in by_hash[h] if p != path),
        })
        if primary:
            t = tag_by_name.get(primary)
            target = Path(args.tagged) / slugify(primary_cat) / (t.slug if t else slugify(primary))
            folder_rows.append({"path": path, "primary_category": primary_cat, "primary_tag": primary,
                                "target_folder": str(target)})
            if args.copy_by_primary_tag:
                target.mkdir(parents=True, exist_ok=True)
                dest = target / Path(path).name
                if dest.exists():
                    dest = target / f"{Path(path).stem}__{h[:8]}{Path(path).suffix}"
                shutil.copy2(path, dest)
                copied += 1
        if args.write_frontmatter and acc and path.lower().endswith(".md"):
            slugs = [tag_by_name[r["tag"]].slug if r["tag"] in tag_by_name else slugify(r["tag"]) for r in acc]
            if write_frontmatter(Path(path), slugs):
                fm_written += 1

    files = {
        "documents": write_csv(out / f"{stamp}_document_tags.csv", doc_rows,
                               ["path", "primary_tag", "primary_category", "n_tags", "tags", "semantic_only",
                                "variables", "duplicate_of", "content_hash"]),
        "folders": write_csv(out / f"{stamp}_folder_suggestions.csv", folder_rows,
                             ["path", "primary_category", "primary_tag", "target_folder"]),
    }
    seen_hashes = set(seen.values())
    scr_rows = []
    path_of = {h: ps[0] for h, ps in by_hash.items()}
    for h, ref, book, chap, verse in con.execute("SELECT content_hash, ref, book, chapter, verse FROM scripture"):
        if h in seen_hashes:
            scr_rows.append({"path": path_of[h], "ref": ref, "book": book, "chapter": chap, "verse": verse})
    files["scripture"] = write_csv(out / f"{stamp}_scripture_refs.csv", scr_rows,
                                   ["path", "ref", "book", "chapter", "verse"])

    # registry audit: which tags actually fire across everything tagged under this registry
    hits_total = Counter()
    for h in hashes:
        for tag, (ti, he, bo) in counts[h].items():
            hits_total[tag] += ti + he + bo
    audit = [{"tag": t.tag, "category": t.category, "docs_with_hits": df[t.tag], "total_hits": hits_total[t.tag],
              "camelcase_autosplit": "yes" if t.camel else "", "has_description": "yes" if t.description else "",
              "match_terms": " | ".join(t.terms)} for t in tags]
    audit.sort(key=lambda r: (r["docs_with_hits"], r["tag"]))
    files["registry_audit"] = write_csv(out / f"{stamp}_registry_audit.csv", audit)
    if error_rows:
        files["errors"] = write_csv(out / f"{stamp}_errors.csv", error_rows, ["path", "error"])
    if args.export_paragraphs:
        prow = [{"path": path_of[h], "paragraph": pi, "tag": tag, "hits": k, "text": sn}
                for h, pi, tag, k, sn in con.execute("SELECT content_hash, para_idx, tag, hits, snippet FROM para_hits")
                if h in seen_hashes]
        files["paragraphs"] = write_csv(out / f"{stamp}_paragraph_tags.csv", prow,
                                        ["path", "paragraph", "tag", "hits", "text"])
    dead = sum(1 for r in audit if r["docs_with_hits"] == 0)
    return {"stamp": stamp, "documents_in_db_current_registry": N,
            "documents_with_tags": sum(1 for r in doc_rows if r["n_tags"]),
            "scripture_refs": len(scr_rows), "tags_never_fired": dead, "frontmatter_written": fm_written,
            "files_copied": copied, "outputs": files}


# ------------------------------------------------------------------ gold / eval / tune
def _norm(s: str) -> str:
    return slugify(s.strip())


def load_gold(path: Path) -> dict[str, set[str]]:
    gold = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            raw = (row.get("correct_tags") or "").strip() or (row.get("tags") or "").strip()
            if row.get("path") and raw:
                gold[row["path"].strip()] = {_norm(x) for x in re.split(r"[;,]", raw) if x.strip()}
    return gold


def _current_registry_hash(con) -> str:
    row = con.execute("SELECT registry_hash FROM runs ORDER BY stamp DESC LIMIT 1").fetchone()
    if not row:
        raise SystemExit("no scan in the database yet - run scan first")
    return row[0]


def _eval_data(con, sem_model):
    rh = _current_registry_hash(con)
    hashes, counts, sems, df = gather(con, rh, sem_model)
    path_hash = dict(con.execute("SELECT path, content_hash FROM documents WHERE registry_hash=?", (rh,)))
    name_hash = {Path(p).name.lower(): h for p, h in path_hash.items()}
    return rh, hashes, counts, sems, df, path_hash, name_hash


def _evaluate(con, gold, params, tags, sem_model, data=None):
    tag_by_name = {t.tag: t for t in tags}
    slug_of = {t.tag: _norm(t.tag) for t in tags}
    if data is None:
        data = _eval_data(con, sem_model)
    rh, hashes, counts, sems, df, path_hash, name_hash = data
    N = len(hashes)
    tp = fp = fn = 0
    fp_tags, fn_tags, missing = Counter(), Counter(), []
    for gpath, gtags in gold.items():
        h = path_hash.get(gpath) or name_hash.get(Path(gpath).name.lower())
        if not h:
            missing.append(gpath)
            continue
        pred = {slug_of.get(r["tag"], _norm(r["tag"]))
                for r in score_doc(h, counts, sems, df, N, params, tag_by_name) if r["accepted"]}
        tp += len(pred & gtags)
        fp += len(pred - gtags)
        fn += len(gtags - pred)
        fp_tags.update(pred - gtags)
        fn_tags.update(gtags - pred)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3), "tp": tp, "fp": fp,
            "fn": fn, "docs_evaluated": len(gold) - len(missing), "docs_missing": missing[:10],
            "top_false_positive_tags": fp_tags.most_common(15), "top_missed_tags": fn_tags.most_common(15)}


def cmd_gold_template(args) -> int:
    con = open_db(Path(args.db))
    tags = load_registry(Path(args.registry), Path(args.exclusions) if args.exclusions else None,
                         load_category_weights(Path(args.category_weights)))
    tag_by_name = {t.tag: t for t in tags}
    rh = _current_registry_hash(con)
    hashes, counts, sems, df = gather(con, rh, (args.embed_model + SEM_KEY_SUFFIX) if args.semantic else None)
    paths = [p for (p,) in con.execute("SELECT path FROM documents WHERE registry_hash=? ORDER BY path", (rh,))]
    random.Random(42).shuffle(paths)
    params = load_params(vars_params(args))
    path_hash = dict(con.execute("SELECT path, content_hash FROM documents"))
    rows = []
    for p in paths[: args.n]:
        acc = [r["tag"] for r in score_doc(path_hash[p], counts, sems, df, len(hashes), params, tag_by_name)
               if r["accepted"]]
        rows.append({"path": p, "suggested_tags": "; ".join(acc), "correct_tags": "; ".join(acc), "notes": ""})
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    out = REVIEW_DIR / "gold_template.csv"
    write_csv(out, rows, ["path", "suggested_tags", "correct_tags", "notes"])
    print(f"wrote {len(rows)} rows -> {out}\nEdit 'correct_tags' (add what's missing, delete what's wrong), "
          f"then save as {REVIEW_DIR / 'gold.csv'} and run: eval / tune")
    return 0


def cmd_eval(args) -> int:
    con = open_db(Path(args.db))
    tags = load_registry(Path(args.registry), Path(args.exclusions) if args.exclusions else None,
                         load_category_weights(Path(args.category_weights)))
    gold = load_gold(Path(args.gold))
    params = load_params(vars_params(args))
    res = _evaluate(con, gold, params, tags, (args.embed_model + SEM_KEY_SUFFIX) if args.semantic else None)
    print(json.dumps({"params": params, **res}, indent=2))
    return 0


def cmd_tune(args) -> int:
    con = open_db(Path(args.db))
    tags = load_registry(Path(args.registry), Path(args.exclusions) if args.exclusions else None,
                         load_category_weights(Path(args.category_weights)))
    gold = load_gold(Path(args.gold))
    sem_model = (args.embed_model + SEM_KEY_SUFFIX) if args.semantic else None
    base = load_params(vars_params(args))
    best = None
    data = _eval_data(con, sem_model)
    grid_sem = [0.0, 0.3, 0.5, 0.7, 1.0] if sem_model else [0.0]
    for th in [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60]:
        for mh in [1.0, 2.0, 3.0, 4.0]:
            for ws in grid_sem:
                for mt in [5, 8, 12, 20]:
                    p = {**base, "threshold": th, "min_hits": mh, "w_sem": ws, "max_tags": mt}
                    r = _evaluate(con, gold, p, tags, sem_model, data)
                    key = (r["f1"], r["precision"])
                    if best is None or key > best[0]:
                        best = (key, p, r)
    _, p, r = best
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    TUNED_PARAMS.write_text(json.dumps(p, indent=2), encoding="utf-8")
    print(json.dumps({"best_params": p, **r, "saved_to": str(TUNED_PARAMS)}, indent=2))
    return 0


# ----------------------------------------------------------------------------- main
def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    common.add_argument("--exclusions", default=str(DEFAULT_EXCLUSIONS),
                        help="CSV with columns tag,phrase - drop a tag in any paragraph containing the phrase")
    common.add_argument("--db", default=str(DEFAULT_DB))
    common.add_argument("--ambiguous", default=str(ROOT / "01_REGISTRY" / "ambiguous_terms.txt"),
                        help="one word per line; these single-word tags count only when capitalized mid-sentence")
    common.add_argument("--category-weights", default=str(ROOT / "01_REGISTRY" / "category_weights.csv"))
    common.add_argument("--semantic", action="store_true", help="use Ollama embeddings (meaning layer)")
    common.add_argument("--embed-model", default="nomic-embed-text")
    common.add_argument("--ollama-url", default="http://localhost:11434")
    for k, v in DEFAULT_PARAMS.items():
        common.add_argument("--" + k.replace("_", "-"), dest=k, type=type(v), default=None)

    ap = argparse.ArgumentParser(description="Theophysics Convergence Tagger v2")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", parents=[common], help="tag files")
    s.add_argument("--source", action="append", help="file or folder; repeatable")
    s.add_argument("--source-list", help="text file with one path per line")
    s.add_argument("--extensions", default=".md,.txt")
    s.add_argument("--limit", type=int)
    s.add_argument("--force", action="store_true", help="re-tag even unchanged files")
    s.add_argument("--output", default=str(DEFAULT_INDEX))
    s.add_argument("--tagged", default=str(DEFAULT_TAGGED))
    s.add_argument("--export-paragraphs", action="store_true")
    s.add_argument("--copy-by-primary-tag", action="store_true", help="COPY files into 03_TAGGED (never moves)")
    s.add_argument("--write-frontmatter", action="store_true",
                   help="WRITE auto_tags: into .md frontmatter (modifies your files; off by default)")
    s.set_defaults(func=cmd_scan)
    g = sub.add_parser("gold-template", parents=[common], help="sample docs for hand-checking")
    g.add_argument("-n", type=int, default=50)
    g.set_defaults(func=cmd_gold_template)
    for name, fn in (("eval", cmd_eval), ("tune", cmd_tune)):
        e = sub.add_parser(name, parents=[common])
        e.add_argument("--gold", default=str(REVIEW_DIR / "gold.csv"))
        e.set_defaults(func=fn)
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0].startswith("-") and argv[0] not in ("-h", "--help"):
        argv.insert(0, "scan")   # v1-style invocation
    args = build_parser().parse_args(argv)
    if getattr(args, "exclusions", None) and not Path(args.exclusions).exists():
        args.exclusions = None
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
