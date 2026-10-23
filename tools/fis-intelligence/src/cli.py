from __future__ import annotations

import argparse
import json
from pathlib import Path

from fis_html_index import connect, corpus_stats, fts_query, list_collections, list_series, register_collection_root, scan_root


DEFAULT_DB = Path(__file__).resolve().parents[1] / "state" / "fis_html.sqlite"


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only HTML intelligence index")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan")
    scan.add_argument("--root", type=Path, required=True)
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)
    sub.add_parser("stats")
    sub.add_parser("series")
    collection = sub.add_parser("collection-root")
    collection.add_argument("--name", required=True)
    collection.add_argument("--root", type=Path, required=True)
    collection.add_argument("--role", required=True)
    collection.add_argument("--description", default="")
    sub.add_parser("collections")
    args = parser.parse_args()

    if args.command == "scan":
        result = scan_root(args.db, args.root)
    else:
        conn = connect(args.db)
        if args.command == "search":
            result = fts_query(conn, args.query, args.limit)
        elif args.command == "series":
            result = list_series(conn)
        elif args.command == "collection-root":
            result = register_collection_root(conn, args.name, args.root, args.role, args.description)
        elif args.command == "collections":
            result = list_collections(conn)
        else:
            result = corpus_stats(conn)
        conn.close()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
