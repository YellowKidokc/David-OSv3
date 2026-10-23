from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup


SKIP_DIRS = {".git", "node_modules", "target", "__pycache__", ".venv", "venv"}
SERIES_RE = re.compile(r"(?i)(?:^|[^a-z0-9])([a-z][a-z0-9]{1,11})[-_ ](\d{1,3})(?:[-_ ]|\b)")


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS pages (
  path TEXT PRIMARY KEY,
  root TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  filename TEXT NOT NULL,
  title TEXT,
  kind TEXT NOT NULL,
  series_key TEXT,
  part_number INTEGER,
  sha256 TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  modified_ns INTEGER NOT NULL,
  headings TEXT NOT NULL,
  visible_text TEXT NOT NULL,
  metadata TEXT NOT NULL,
  indexed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pages_root ON pages(root);
CREATE INDEX IF NOT EXISTS idx_pages_series ON pages(root, series_key, part_number);
CREATE TABLE IF NOT EXISTS tags (
  page_path TEXT NOT NULL,
  tag TEXT NOT NULL,
  source TEXT NOT NULL,
  PRIMARY KEY(page_path, tag, source),
  FOREIGN KEY(page_path) REFERENCES pages(path) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);
CREATE TABLE IF NOT EXISTS links (
  source_path TEXT NOT NULL,
  href TEXT NOT NULL,
  target_path TEXT,
  anchor_text TEXT,
  rel TEXT,
  is_local INTEGER NOT NULL,
  PRIMARY KEY(source_path, href, anchor_text),
  FOREIGN KEY(source_path) REFERENCES pages(path) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS series_parts (
  root TEXT NOT NULL,
  series_key TEXT NOT NULL,
  part_number INTEGER NOT NULL,
  page_count INTEGER NOT NULL,
  representative_path TEXT NOT NULL,
  PRIMARY KEY(root, series_key, part_number)
);
CREATE TABLE IF NOT EXISTS continuity (
  root TEXT NOT NULL,
  series_key TEXT,
  from_path TEXT,
  to_path TEXT,
  from_part INTEGER,
  to_part INTEGER,
  relation TEXT NOT NULL,
  confidence REAL NOT NULL,
  evidence TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_continuity_series ON continuity(root, series_key);
CREATE TABLE IF NOT EXISTS scan_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  root TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  html_count INTEGER NOT NULL DEFAULT 0,
  changed_count INTEGER NOT NULL DEFAULT 0,
  removed_count INTEGER NOT NULL DEFAULT 0,
  error_count INTEGER NOT NULL DEFAULT 0,
  errors TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS collections (
  name TEXT PRIMARY KEY,
  description TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS collection_roots (
  collection_name TEXT NOT NULL,
  root TEXT NOT NULL,
  role TEXT NOT NULL,
  PRIMARY KEY(collection_name, root),
  FOREIGN KEY(collection_name) REFERENCES collections(name) ON DELETE CASCADE
);
CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
  path UNINDEXED,
  title,
  headings,
  visible_text,
  tags,
  tokenize='unicode61 remove_diacritics 2'
);
CREATE VIEW IF NOT EXISTS v_page_catalog AS
SELECT p.path,p.root,p.relative_path,p.filename,p.title,p.kind,p.series_key,p.part_number,
       p.sha256,p.size_bytes,p.indexed_at,
       COALESCE((SELECT group_concat(t.tag, ', ') FROM tags t WHERE t.page_path=p.path),'') AS tags,
       p.headings
FROM pages p;
CREATE VIEW IF NOT EXISTS v_series_catalog AS
SELECT root,series_key,min(part_number) AS first_part,max(part_number) AS last_part,
       count(*) AS observed_parts,sum(page_count) AS page_variants,
       group_concat(part_number, ',') AS observed_part_numbers
FROM series_parts GROUP BY root,series_key;
CREATE VIEW IF NOT EXISTS v_continuity_map AS
SELECT root,series_key,from_part,to_part,relation,confidence,evidence,from_path,to_path
FROM continuity;
CREATE VIEW IF NOT EXISTS v_collection_catalog AS
SELECT c.name AS collection_name,c.description,r.root,r.role,
       (SELECT count(*) FROM pages p WHERE p.root=r.root) AS indexed_pages
FROM collections c JOIN collection_roots r ON r.collection_name=c.name;
CREATE TABLE IF NOT EXISTS schema_guide (
  object_name TEXT PRIMARY KEY,
  purpose TEXT NOT NULL,
  authority_note TEXT NOT NULL
);
INSERT OR REPLACE INTO schema_guide(object_name,purpose,authority_note) VALUES
('v_page_catalog','One row per indexed HTML page with identity, series position, tags, and citation path.','Index metadata only; not a truth or canon ruling.'),
('v_series_catalog','Observed series ranges and representation counts.','Filename-derived inference; missing parts require human confirmation.'),
('v_continuity_map','Explicit and inferred next, previous, adjacent, and gap relationships.','Confidence and evidence must travel with every edge.'),
('v_collection_catalog','Logical collections with physical roots and authority roles.','Collection membership never promotes preserved source into canon.'),
('pages_fts','FTS5 full-text search over titles, headings, visible HTML text, and tags.','Search relevance is not epistemic authority.');
"""


@dataclass
class ExtractedPage:
    title: str
    headings: list[str]
    text: str
    metadata: dict[str, str]
    tags: list[tuple[str, str]]
    links: list[dict[str, str | int | None]]
    series_key: str | None
    part_number: int | None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_path(path: Path) -> str:
    return str(path.resolve())


def io_path(path: Path) -> str:
    """Return an extended-length Windows path for file I/O without changing stored identity."""
    value = str(path)
    if os.name != "nt" or value.startswith("\\\\?\\"):
        return value
    if value.startswith("\\\\"):
        return "\\\\?\\UNC\\" + value.lstrip("\\")
    return "\\\\?\\" + os.path.abspath(value)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def iter_html(root: Path) -> Iterable[Path]:
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.lower().endswith(('.html', '.htm')):
                yield Path(current) / name


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _series_identity(name: str) -> tuple[str | None, int | None]:
    match = SERIES_RE.search(name)
    if not match:
        return None, None
    return match.group(1).lower(), int(match.group(2))


def _resolve_link(source: Path, href: str) -> tuple[str | None, int]:
    parsed = urlparse(href)
    if parsed.scheme not in ("", "file") or href.startswith(("#", "mailto:", "javascript:", "data:")):
        return None, 0
    raw = unquote(parsed.path)
    if not raw:
        return canonical_path(source), 1
    candidate = Path(raw) if Path(raw).is_absolute() else source.parent / raw
    try:
        return canonical_path(candidate), 1
    except OSError:
        return str(candidate), 1


def extract_page(path: Path, html: str) -> ExtractedPage:
    soup = BeautifulSoup(html, "html.parser")
    title = _clean(soup.title.get_text(" ", strip=True) if soup.title else path.stem)
    headings = [_clean(tag.get_text(" ", strip=True)) for tag in soup.find_all(re.compile(r"^h[1-6]$"))]

    metadata: dict[str, str] = {}
    tags: set[tuple[str, str]] = set()
    for meta in soup.find_all("meta"):
        key = _clean(meta.get("name") or meta.get("property") or meta.get("itemprop") or "").lower()
        value = _clean(meta.get("content") or "")
        if not key or not value:
            continue
        metadata[key] = value
        if key in {"keywords", "article:tag", "tags", "domain", "category", "subject"}:
            for item in re.split(r"[,;|]", value):
                item = _clean(item).lower()
                if item:
                    tags.add((item, f"meta:{key}"))

    for node in soup.find_all(True):
        for attr in ("data-domain", "data-tags", "data-category", "data-series", "data-status"):
            if node.has_attr(attr):
                for item in re.split(r"[,;| ]+", str(node.get(attr, ""))):
                    item = _clean(item).lower()
                    if item:
                        tags.add((item, attr))

    series_key, part_number = _series_identity(path.name)
    if series_key:
        tags.add((series_key, "filename-series"))
        tags.add((f"part-{part_number:02d}", "filename-series"))

    links: list[dict[str, str | int | None]] = []
    for anchor in soup.find_all("a", href=True):
        href = _clean(str(anchor.get("href")))
        anchor_text = _clean(anchor.get_text(" ", strip=True))
        rel_values = anchor.get("rel") or []
        rel = " ".join(rel_values) if isinstance(rel_values, list) else str(rel_values)
        target, is_local = _resolve_link(path, href)
        links.append({"href": href, "target_path": target, "anchor_text": anchor_text, "rel": rel, "is_local": is_local})

    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()
    text = _clean(soup.get_text(" ", strip=True))
    return ExtractedPage(title, headings, text, metadata, sorted(tags), links, series_key, part_number)


def _upsert_page(conn: sqlite3.Connection, root: Path, path: Path) -> bool:
    with open(io_path(path), "rb") as handle:
        raw = handle.read()
    digest = hashlib.sha256(raw).hexdigest()
    stat = os.stat(io_path(path))
    p = canonical_path(path)
    old = conn.execute("SELECT sha256, modified_ns FROM pages WHERE path=?", (p,)).fetchone()
    if old and old["sha256"] == digest and old["modified_ns"] == stat.st_mtime_ns:
        return False

    page = extract_page(path, raw.decode("utf-8", errors="replace"))
    root_s = canonical_path(root)
    relative = str(path.relative_to(root))
    kind = "fis-report" if path.name.lower() == "fis.html" else "html-page"
    conn.execute(
        """INSERT INTO pages(path,root,relative_path,filename,title,kind,series_key,part_number,sha256,size_bytes,modified_ns,headings,visible_text,metadata,indexed_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(path) DO UPDATE SET root=excluded.root,relative_path=excluded.relative_path,filename=excluded.filename,title=excluded.title,
        kind=excluded.kind,series_key=excluded.series_key,part_number=excluded.part_number,sha256=excluded.sha256,size_bytes=excluded.size_bytes,
        modified_ns=excluded.modified_ns,headings=excluded.headings,visible_text=excluded.visible_text,metadata=excluded.metadata,indexed_at=excluded.indexed_at""",
        (p, root_s, relative, path.name, page.title, kind, page.series_key, page.part_number, digest, stat.st_size, stat.st_mtime_ns,
         json.dumps(page.headings, ensure_ascii=False), page.text, json.dumps(page.metadata, ensure_ascii=False), utc_now()),
    )
    conn.execute("DELETE FROM tags WHERE page_path=?", (p,))
    conn.executemany("INSERT OR IGNORE INTO tags(page_path,tag,source) VALUES(?,?,?)", [(p, tag, source) for tag, source in page.tags])
    conn.execute("DELETE FROM links WHERE source_path=?", (p,))
    conn.executemany(
        "INSERT OR IGNORE INTO links(source_path,href,target_path,anchor_text,rel,is_local) VALUES(?,?,?,?,?,?)",
        [(p, item["href"], item["target_path"], item["anchor_text"], item["rel"], item["is_local"]) for item in page.links],
    )
    conn.execute("DELETE FROM pages_fts WHERE path=?", (p,))
    conn.execute(
        "INSERT INTO pages_fts(path,title,headings,visible_text,tags) VALUES(?,?,?,?,?)",
        (p, page.title, " | ".join(page.headings), page.text, " ".join(tag for tag, _ in page.tags)),
    )
    return True


def rebuild_continuity(conn: sqlite3.Connection, root: Path) -> None:
    root_s = canonical_path(root)
    conn.execute("DELETE FROM continuity WHERE root=?", (root_s,))
    conn.execute("DELETE FROM series_parts WHERE root=?", (root_s,))
    rows = conn.execute(
        "SELECT series_key,part_number,path FROM pages WHERE root=? AND series_key IS NOT NULL AND part_number IS NOT NULL ORDER BY series_key,part_number,path",
        (root_s,),
    ).fetchall()
    grouped: dict[str, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["series_key"]][row["part_number"]].append(row["path"])

    for series_key, parts in grouped.items():
        ordered = sorted(parts)
        for number in ordered:
            representatives = sorted(parts[number], key=lambda p: (Path(p).name.lower() == "fis.html", len(p), p.lower()))
            conn.execute(
                "INSERT INTO series_parts(root,series_key,part_number,page_count,representative_path) VALUES(?,?,?,?,?)",
                (root_s, series_key, number, len(parts[number]), representatives[0]),
            )
        for left, right in zip(ordered, ordered[1:]):
            relation = "adjacent" if right == left + 1 else "gap"
            evidence = f"filename sequence {series_key}-{left:02d} -> {series_key}-{right:02d}"
            conn.execute(
                "INSERT INTO continuity(root,series_key,from_path,to_path,from_part,to_part,relation,confidence,evidence) VALUES(?,?,?,?,?,?,?,?,?)",
                (root_s, series_key, parts[left][0], parts[right][0], left, right, relation, 0.95 if relation == "adjacent" else 0.90, evidence),
            )

    explicit = conn.execute(
        """SELECT l.source_path,l.target_path,l.anchor_text,l.rel,p.series_key,p.part_number
        FROM links l JOIN pages p ON p.path=l.source_path WHERE p.root=? AND l.is_local=1""",
        (root_s,),
    ).fetchall()
    for row in explicit:
        signal = f"{row['rel']} {row['anchor_text']}".lower()
        relation = "next-link" if "next" in signal else "previous-link" if any(x in signal for x in ("prev", "previous", "back")) else None
        if relation:
            conn.execute(
                "INSERT INTO continuity(root,series_key,from_path,to_path,from_part,to_part,relation,confidence,evidence) VALUES(?,?,?,?,?,?,?,?,?)",
                (root_s, row["series_key"], row["source_path"], row["target_path"], row["part_number"], None, relation, 1.0, signal.strip()),
            )


def scan_root(db_path: Path, root: Path) -> dict:
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    conn = connect(db_path)
    started = utc_now()
    run_id = conn.execute("INSERT INTO scan_runs(root,started_at) VALUES(?,?)", (canonical_path(root), started)).lastrowid
    seen: set[str] = set()
    changed = 0
    errors: list[dict[str, str]] = []
    for path in iter_html(root):
        seen.add(canonical_path(path))
        try:
            changed += int(_upsert_page(conn, root, path))
        except Exception as exc:  # preserve the rest of the scan
            errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
    existing = {row[0] for row in conn.execute("SELECT path FROM pages WHERE root=?", (canonical_path(root),))}
    removed_paths = sorted(existing - seen)
    for path in removed_paths:
        conn.execute("DELETE FROM pages_fts WHERE path=?", (path,))
        conn.execute("DELETE FROM pages WHERE path=?", (path,))
    rebuild_continuity(conn, root)
    conn.execute(
        "UPDATE scan_runs SET completed_at=?,html_count=?,changed_count=?,removed_count=?,error_count=?,errors=? WHERE id=?",
        (utc_now(), len(seen), changed, len(removed_paths), len(errors), json.dumps(errors, ensure_ascii=False), run_id),
    )
    conn.commit()
    stats = corpus_stats(conn)
    conn.close()
    return {"run_id": run_id, "root": canonical_path(root), "html_count": len(seen), "changed_count": changed,
            "removed_count": len(removed_paths), "error_count": len(errors), "errors": errors, "corpus": stats}


def corpus_stats(conn: sqlite3.Connection) -> dict:
    return {
        "pages": conn.execute("SELECT count(*) FROM pages").fetchone()[0],
        "fis_reports": conn.execute("SELECT count(*) FROM pages WHERE kind='fis-report'").fetchone()[0],
        "roots": conn.execute("SELECT count(DISTINCT root) FROM pages").fetchone()[0],
        "tags": conn.execute("SELECT count(*) FROM tags").fetchone()[0],
        "links": conn.execute("SELECT count(*) FROM links").fetchone()[0],
        "series": conn.execute("SELECT count(DISTINCT root || '|' || series_key) FROM series_parts").fetchone()[0],
        "series_parts": conn.execute("SELECT count(*) FROM series_parts").fetchone()[0],
        "continuity_edges": conn.execute("SELECT count(*) FROM continuity").fetchone()[0],
        "collections": conn.execute("SELECT count(*) FROM collections").fetchone()[0],
    }


def register_collection_root(conn: sqlite3.Connection, name: str, root: Path, role: str, description: str = "") -> dict:
    root_s = canonical_path(root)
    conn.execute(
        "INSERT INTO collections(name,description,created_at) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET description=CASE WHEN excluded.description<>'' THEN excluded.description ELSE collections.description END",
        (name, description, utc_now()),
    )
    conn.execute(
        "INSERT INTO collection_roots(collection_name,root,role) VALUES(?,?,?) ON CONFLICT(collection_name,root) DO UPDATE SET role=excluded.role",
        (name, root_s, role),
    )
    conn.commit()
    return {"collection": name, "root": root_s, "role": role}


def list_collections(conn: sqlite3.Connection) -> list[dict]:
    result = []
    for collection in conn.execute("SELECT name,description,created_at FROM collections ORDER BY name"):
        item = dict(collection)
        item["roots"] = [dict(row) for row in conn.execute(
            "SELECT root,role FROM collection_roots WHERE collection_name=? ORDER BY role,root", (collection["name"],)
        )]
        item["indexed_pages"] = conn.execute(
            "SELECT count(*) FROM pages p JOIN collection_roots c ON c.root=p.root WHERE c.collection_name=?", (collection["name"],)
        ).fetchone()[0]
        result.append(item)
    return result


def fts_query(conn: sqlite3.Connection, query: str, limit: int = 10) -> list[dict]:
    tokens = re.findall(r"[\w-]+", query, flags=re.UNICODE)
    if not tokens:
        return []
    expression = " AND ".join(f'"{token.replace(chr(34), "")}"' for token in tokens)
    rows = conn.execute(
        """SELECT p.path,p.title,p.kind,p.series_key,p.part_number,
        snippet(pages_fts,3,'[',']',' … ',24) AS snippet,bm25(pages_fts) AS rank
        FROM pages_fts JOIN pages p ON p.path=pages_fts.path
        WHERE pages_fts MATCH ?
        ORDER BY CASE p.kind WHEN 'html-page' THEN 0 ELSE 1 END, rank LIMIT ?""",
        (expression, max(1, min(limit, 50))),
    ).fetchall()
    return [dict(row) for row in rows]


def list_series(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT root,series_key,min(part_number) AS first_part,max(part_number) AS last_part,
        count(*) AS observed_parts,sum(page_count) AS page_variants
        FROM series_parts GROUP BY root,series_key ORDER BY root,series_key"""
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        observed = {r[0] for r in conn.execute("SELECT part_number FROM series_parts WHERE root=? AND series_key=?", (row["root"], row["series_key"]))}
        item["missing_parts"] = [n for n in range(row["first_part"], row["last_part"] + 1) if n not in observed]
        result.append(item)
    return result
