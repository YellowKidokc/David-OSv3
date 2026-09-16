"""One-route search over fis_folder_memory.sqlite.

Run:  python fis_search.py
Then: http://127.0.0.1:10779/search?q=MEQ
Optional filters: &doc_type=ART &chi=R &domain=theology &address=LOSS__
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "fis_folder_memory.sqlite"
PORT = 10779

app = Flask(__name__)


def search_files(query: str, doc_type: str = "", chi: str = "",
                 address: str = "", domain: str = "", limit: int = 50) -> list[dict]:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    clauses, params = [], []
    needle = f"%{(query or '').strip().lower()}%"
    if query.strip():
        clauses.append(
            "(lower(name) LIKE ? OR lower(IFNULL(doc_type,'')) LIKE ? "
            "OR lower(IFNULL(lossless_address,'')) LIKE ? OR lower(IFNULL(domain,'')) LIKE ? "
            "OR lower(IFNULL(keywords_text,'')) LIKE ? OR lower(IFNULL(proposed_name,'')) LIKE ? "
            "OR lower(IFNULL(lossless_format,'')) LIKE ? "
            "OR lower(IFNULL(local_classification_json,'')) LIKE ? OR lower(path) LIKE ?)"
        )
        params.extend([needle] * 9)
    if doc_type:
        clauses.append("lower(IFNULL(doc_type,'')) = ?")
        params.append(doc_type.lower())
    if domain:
        clauses.append("lower(IFNULL(domain,'')) LIKE ?")
        params.append(f"%{domain.lower()}%")
    if address:
        clauses.append("lower(IFNULL(lossless_address,'')) LIKE ?")
        params.append(f"%{address.lower()}%")
    if chi:
        clauses.append("lower(IFNULL(local_classification_json,'')) LIKE ?")
        params.append(f"%\"chi_factor\": \"{chi.lower()}\"%")
    where = " AND ".join(clauses) if clauses else "1=1"
    rows = conn.execute(
        f"""SELECT file_id, path, name, doc_type, type_confidence, domain,
                   lossless_address, proposed_name, lossless_format, keywords_text,
                   local_classification_json
            FROM file_memory WHERE {where}
            ORDER BY last_scanned DESC LIMIT ?""",
        (*params, max(1, min(limit, 200))),
    ).fetchall()
    conn.close()
    results = []
    for row in rows:
        local = {}
        try:
            local = json.loads(row["local_classification_json"] or "{}")
        except json.JSONDecodeError:
            pass
        results.append({
            "file_id": row["file_id"],
            "name": row["name"],
            "path": row["path"],
            "doc_type": row["doc_type"],
            "type_confidence": row["type_confidence"],
            "domain": row["domain"] or local.get("domain", {}).get("name", ""),
            "chi": local.get("chi_factor") or local.get("chi_name", ""),
            "law": (local.get("law") or {}).get("name", ""),
            "lossless_address": row["lossless_address"],
            "lossless_format": row["lossless_format"] or row["proposed_name"],
            "keywords": row["keywords_text"],
        })
    return results


@app.route("/search")
def search():
    query = request.args.get("q") or request.args.get("query") or ""
    results = search_files(
        query,
        doc_type=request.args.get("doc_type", ""),
        chi=request.args.get("chi", ""),
        address=request.args.get("address") or request.args.get("lossless_address", ""),
        domain=request.args.get("domain", ""),
        limit=int(request.args.get("limit") or 50),
    )
    return jsonify({"query": query, "count": len(results), "results": results})


if __name__ == "__main__":
    print(f"FIS search -> http://127.0.0.1:{PORT}/search?q=")
    print(f"db: {DB_PATH}")
    app.run(host="127.0.0.1", port=PORT, debug=False)
