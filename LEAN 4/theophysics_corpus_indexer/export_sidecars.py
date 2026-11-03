"""Export the three L4 sidecar views to CSV manifests in REVIEW/."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import project_dir
from db import get_conn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

REVIEW_ROOT = Path("//192.168.2.50/h_hp/Desktop/REVIEW")

SIDECARS: dict[str, dict[str, Any]] = {
    "l4_qrn": {
        "file": "L4_QRN.csv",
        "query": """
            SELECT f.sha256, f.summary, f.decl_count, l.path
            FROM files f
            JOIN locations l ON l.sha256 = f.sha256
            WHERE f.is_library = true
        """,
        "fields": ["sha256", "summary", "decl_count", "path"],
    },
    "l4_unc": {
        "file": "L4_UNC.csv",
        "query": """
            SELECT f.sha256, f.ext, f.size_bytes, f.summary, l.path
            FROM files f
            JOIN locations l ON l.sha256 = f.sha256
            WHERE f.series IS NULL
        """,
        "fields": ["sha256", "ext", "size_bytes", "summary", "path"],
    },
    "l4_dup": {
        "file": "L4_DUP.csv",
        "query": """
            SELECT f.sha256, f.series, d.cnt, l.path
            FROM files f
            JOIN locations l ON l.sha256 = f.sha256
            JOIN (
                SELECT sha256, COUNT(*) AS cnt
                FROM locations
                GROUP BY sha256
                HAVING COUNT(*) > 1
            ) d ON d.sha256 = f.sha256
            ORDER BY d.cnt DESC
        """,
        "fields": ["sha256", "series", "cnt", "path"],
    },
}


def _create_views(conn) -> None:
    with conn.cursor() as cur:
        for name, spec in SIDECARS.items():
            cur.execute(f"CREATE OR REPLACE VIEW {name} AS {spec['query']}")
            logger.info("Created/updated view %s", name)
    conn.commit()


def _export_view(cur, view_name: str, out_path: Path, fields: list[str]) -> int:
    cur.execute(f"SELECT * FROM {view_name}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in cur:
            writer.writerow(dict(zip(fields, row)))
            count += 1
    return count


def main() -> int:
    started = datetime.now(timezone.utc)
    conn = get_conn()

    _create_views(conn)

    counts: dict[str, int] = {}
    query_hashes: dict[str, str] = {}
    with conn.cursor() as cur:
        for name, spec in SIDECARS.items():
            out_path = REVIEW_ROOT / spec["file"]
            count = _export_view(cur, name, out_path, spec["fields"])
            counts[name] = count
            query_hashes[name] = hashlib.sha256(
                spec["query"].strip().encode()
            ).hexdigest()[:16]
            logger.info("Exported %s: %d rows -> %s", name, count, out_path)

    finished = datetime.now(timezone.utc)
    receipt = {
        "run_id": "l4-sidecars-" + started.strftime("%Y-%m-%dT%H%M%S"),
        "started": started.isoformat(),
        "finished": finished.isoformat(),
        "review_root": str(REVIEW_ROOT),
        "exports": {
            name: {
                "file": spec["file"],
                "view": name,
                "query": spec["query"].strip(),
                "query_hash": query_hashes[name],
                "rows": counts[name],
            }
            for name, spec in SIDECARS.items()
        },
    }

    receipts_dir = project_dir() / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipts_dir / f"{receipt['run_id']}-receipt.json"
    with receipt_path.open("w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, default=str)
    logger.info("Receipt written to %s", receipt_path)

    print("\n=== L4 sidecar export ===")
    for name, spec in SIDECARS.items():
        print(f"  {spec['file']}: {counts[name]} rows")
    print(f"\nReceipt: {receipt_path}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
