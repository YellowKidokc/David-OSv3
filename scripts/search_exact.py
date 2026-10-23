"""Command-line client for the same service used by POST /search/exact."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hub.services.exact_search import search, health
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?")
    parser.add_argument("--root", action="append", dest="roots")
    parser.add_argument("--type", action="append", dest="file_types")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--regex", action="store_true")
    parser.add_argument("--health", action="store_true")
    args = parser.parse_args()
    if not args.health and not args.query:
        parser.error("query or --health is required")
    result = health() if args.health else search(args.query, args.roots, args.file_types, args.limit, args.regex)
    print(json.dumps(result, ensure_ascii=False, indent=2))
