#!/usr/bin/env python3
"""Index `_bucket.json` files into the TOP AI FIS SQLite database."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "sqlite" / "fis_hub.sqlite"
DEFAULT_MEMORY_ROOT = ROOT / "data" / "memory" / "TopOfMind_Memory"


def index_buckets(db_path: Path = DEFAULT_DB, memory_root: Path = DEFAULT_MEMORY_ROOT) -> int:
    bucket_files = sorted(memory_root.rglob("_bucket.json"))

    with sqlite3.connect(db_path) as conn:
        for bucket_file in bucket_files:
            data = json.loads(bucket_file.read_text(encoding="utf-8"))
            conn.execute(
                """
                INSERT INTO memory_buckets (
                  bucket_id, label, path, owner, visibility, allowed_agents,
                  vector_namespace, requires_approval_to_share, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(bucket_id) DO UPDATE SET
                  label = excluded.label,
                  path = excluded.path,
                  owner = excluded.owner,
                  visibility = excluded.visibility,
                  allowed_agents = excluded.allowed_agents,
                  vector_namespace = excluded.vector_namespace,
                  requires_approval_to_share = excluded.requires_approval_to_share,
                  updated_at = CURRENT_TIMESTAMP
                """,
                (
                    data["bucket_id"],
                    data["label"],
                    str(bucket_file.parent),
                    data.get("owner", "operator"),
                    data.get("visibility", "private"),
                    json.dumps(data.get("allowed_agents", [])),
                    data.get("vector_namespace"),
                    1 if data.get("requires_approval_to_share", True) else 0,
                ),
            )
        conn.commit()

    return len(bucket_files)


def main() -> int:
    parser = argparse.ArgumentParser(description="Index TOP AI FIS memory buckets.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path")
    parser.add_argument("--memory-root", default=str(DEFAULT_MEMORY_ROOT), help="Memory root path")
    args = parser.parse_args()

    count = index_buckets(Path(args.db), Path(args.memory_root))
    print(f"Indexed memory buckets: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

