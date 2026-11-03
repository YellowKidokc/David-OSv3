"""Re-classify every unique file in the corpus from its own content.

This fixes two problems in the first run:
1. The original run classified per-location and the last location won, so files
   with both a Theophysics copy and a Mathlib copy were often mislabeled.
2. Non-.lean files were not classified because their content was not read.

The script reads one representative path per SHA, re-parses .lean declarations,
and updates files + declarations. It then recomputes verification levels and
writes a fresh receipt + spot-check sheet.
"""

from __future__ import annotations

import csv
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2

from classifier import classify
from config import CONFIG_HASH, project_dir
from db import (
    compute_verif_levels,
    get_conn,
    get_p1_metrics,
    get_p2_metrics,
    get_spot_check,
    insert_declaration,
)
from inventory import _read_sample

import argparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _norm(path: str) -> str:
    return path.replace("\\", "/").lower()


def _path_suggests_library(paths: list[str]) -> bool:
    for p in paths:
        if "mathlib" in _norm(p).split("/"):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-classify corpus from content")
    parser.add_argument("--batch", type=int, default=500, help="Update batch size")
    args = parser.parse_args()

    started = datetime.now(timezone.utc)
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT sha256, ext FROM files")
    rows = cur.fetchall()
    logger.info("Re-classifying %d unique files", len(rows))

    updated = 0
    for idx, (sha, ext) in enumerate(rows, 1):
        cur.execute("SELECT path FROM locations WHERE sha256 = %s", (sha,))
        paths = [r[0] for r in cur.fetchall()]
        if not paths:
            continue

        # Prefer a path that exposes library provenance.
        library_by_path = _path_suggests_library(paths)
        if library_by_path:
            rep_path = next(p for p in paths if "mathlib" in _norm(p).split("/"))
        else:
            rep_path = paths[0]

        ext_lower = ext.lower()
        try:
            text = _read_sample(
                rep_path, sample_bytes=None if ext_lower == ".lean" else 8192
            )
        except OSError as exc:
            logger.warning("Cannot read %s: %s", rep_path, exc)
            continue

        series, conf, is_library, decl_count, sorry_active, decls, summary = classify(
            rep_path, ext, text
        )

        # If another location clearly screams Mathlib, force library quarantine.
        if library_by_path and not is_library:
            series, conf, is_library = "LIBRARY", 1.0, True

        cur.execute(
            """
            UPDATE files
            SET series = %s,
                series_conf = %s,
                is_library = %s,
                decl_count = COALESCE(%s, decl_count),
                sorry_active = COALESCE(%s, sorry_active)
            WHERE sha256 = %s
            """,
            (series, conf, is_library, decl_count, sorry_active, sha),
        )

        cur.execute("DELETE FROM declarations WHERE sha256 = %s", (sha,))
        for kind, name in decls:
            insert_declaration(cur, sha, name, kind)

        if idx % args.batch == 0:
            conn.commit()
            logger.info("Re-classified %d / %d files...", idx, len(rows))

    conn.commit()
    logger.info("Re-classified %d files", len(rows))

    compute_verif_levels(conn)

    p1 = get_p1_metrics(cur)
    p2 = get_p2_metrics(cur)
    spot_check = get_spot_check(cur, limit=50)

    finished = datetime.now(timezone.utc)
    receipt = {
        "run_id": "reclassify-" + started.strftime("%Y-%m-%dT%H%M%S"),
        "started": started.isoformat(),
        "finished": finished.isoformat(),
        "config_hash": CONFIG_HASH,
        "p1": p1,
        "p2": p2,
    }

    receipts_dir = project_dir() / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipts_dir / f"{receipt['run_id']}-receipt.json"
    with receipt_path.open("w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, default=str)
    logger.info("Receipt written to %s", receipt_path)

    spot_path = project_dir() / "spot_check.csv"
    with spot_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "sha256", "path", "series", "series_conf", "verif_level",
                "decl_count", "sorry_active", "summary",
            ],
        )
        writer.writeheader()
        writer.writerows(spot_check)
    logger.info("Spot-check sheet written to %s", spot_path)

    print("\n=== P2 CLASSIFICATION GATE (after re-classification) ===")
    total = p2["total"]
    print(
        f"{total} unique files: "
        f"{p2['classified_pct']}% classified at >=0.8 confidence, "
        f"{p2['library_pct']}% LIBRARY quarantined, "
        f"{p2['unclassified_pct']}% unclassified, "
        f"{p2['with_receipt_pct']}% carrying a receipt above AI_REVIEW."
    )
    print("Series counts:")
    for series, count in sorted(p2["series_counts"].items(), key=lambda x: -x[1]):
        print(f"  {series}: {count}")

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
