#!/usr/bin/env python3
"""Create the initial TOP AI FIS SQLite hub database."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "sqlite" / "fis_hub.sqlite"
DEFAULT_SCHEMA = ROOT / "docs" / "schemas" / "hub_schema.sql"


def init_db(db_path: Path = DEFAULT_DB, schema_path: Path = DEFAULT_SCHEMA) -> Path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema = schema_path.read_text(encoding="utf-8")

    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema)
        conn.commit()

    return db_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize TOP AI FIS SQLite database.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="SQL schema path")
    args = parser.parse_args()

    db_path = init_db(Path(args.db), Path(args.schema))
    print(f"Initialized hub database: {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

