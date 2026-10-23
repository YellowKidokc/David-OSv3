from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from fis_html_index import corpus_stats as db_stats
from fis_html_index import fts_query, list_collections, list_series


DEFAULT_DB = Path(__file__).resolve().parents[1] / "state" / "fis_html.sqlite"
DB_PATH = Path(os.environ.get("FIS_HTML_DB", DEFAULT_DB))
mcp = FastMCP("FIS HTML Intelligence")


def readonly_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@mcp.tool()
def search_html(query: str, limit: int = 8) -> str:
    """Search indexed HTML and return cited exact paths with relevant snippets."""
    conn = readonly_connection()
    try:
        return json.dumps(fts_query(conn, query, limit), indent=2, ensure_ascii=False)
    finally:
        conn.close()


@mcp.tool()
def inspect_page(path: str) -> str:
    """Inspect one exact indexed HTML page, including headings, tags, links, and a bounded text extract."""
    conn = readonly_connection()
    try:
        row = conn.execute(
            "SELECT path,root,relative_path,title,kind,series_key,part_number,sha256,size_bytes,headings,visible_text,metadata,indexed_at FROM pages WHERE path=?",
            (path,),
        ).fetchone()
        if not row:
            return json.dumps({"error": "Page not found", "path": path})
        result = dict(row)
        result["headings"] = json.loads(result["headings"])
        result["metadata"] = json.loads(result["metadata"])
        result["visible_text"] = result["visible_text"][:12000]
        result["tags"] = [dict(r) for r in conn.execute("SELECT tag,source FROM tags WHERE page_path=? ORDER BY tag", (path,))]
        result["links"] = [dict(r) for r in conn.execute("SELECT href,target_path,anchor_text,rel,is_local FROM links WHERE source_path=? LIMIT 200", (path,))]
        return json.dumps(result, indent=2, ensure_ascii=False)
    finally:
        conn.close()


@mcp.tool()
def list_html_series() -> str:
    """List inferred filename series, observed parts, variant counts, and missing part numbers."""
    conn = readonly_connection()
    try:
        return json.dumps(list_series(conn), indent=2, ensure_ascii=False)
    finally:
        conn.close()


@mcp.tool()
def trace_continuity(series_key: str) -> str:
    """Trace explicit and inferred continuity edges for a named series such as drv."""
    conn = readonly_connection()
    try:
        rows = conn.execute(
            "SELECT root,series_key,from_path,to_path,from_part,to_part,relation,confidence,evidence FROM continuity WHERE lower(series_key)=lower(?) ORDER BY root,from_part,to_part,relation",
            (series_key,),
        ).fetchall()
        return json.dumps([dict(row) for row in rows], indent=2, ensure_ascii=False)
    finally:
        conn.close()


@mcp.tool()
def corpus_stats() -> str:
    """Return current index counts for pages, FIS reports, roots, tags, links, series, and continuity."""
    conn = readonly_connection()
    try:
        return json.dumps(db_stats(conn), indent=2, ensure_ascii=False)
    finally:
        conn.close()


@mcp.tool()
def corpus_collections() -> str:
    """List logical corpus collections, their physical roots, authority roles, and indexed page counts."""
    conn = readonly_connection()
    try:
        return json.dumps(list_collections(conn), indent=2, ensure_ascii=False)
    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run(transport="stdio")
