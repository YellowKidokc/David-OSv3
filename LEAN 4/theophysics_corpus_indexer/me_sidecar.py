"""Build the Master Equation convergence sidecar.

- Finds the governing canonical document under 04_MASTER_EQUATION.
- Creates the ME claim record (status K = CORE).
- Imports every file in the 04_MASTER_EQUATION workspace as a presentation,
  mapping its folder to a kind code.
- Imports every corpus file already classified as MASTER_EQUATION as a PRF
  presentation.
- Computes an initial drift report (presentations not yet pinned to the claim).
- Exports a live sidecar CSV to REVIEW/ME.csv and writes a receipt.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2

from config import project_dir
from db import get_conn
from me_schema import init_me_schema, reset_me_tables

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ME_ROOT = Path("C:/Users/David/Documents/faiththruphysics.com/04_MASTER_EQUATION")
REVIEW_ROOT = Path("//192.168.2.50/h_hp/Desktop/REVIEW")

CLAIM_ID = "ME"

# Folder-prefix -> kind code, longest prefix first.
FOLDER_KIND_MAP: list[tuple[str, str]] = [
    ("00_EQUATION_DEFINITION_BOOK", "DEF"),
    ("020_LAW_EXPANSIONS", "LAW"),
    ("025_CANONICAL_TESTS", "TST"),
    ("030_SPIRITUAL_TERMS", "SPI"),
    ("040_PHYSICAL_TERMS", "PHY"),
    ("050_LEAN_PROOFS", "PRF"),
    ("050_MATH_TRANSLATION_BLOCKS", "MTB"),
    ("055_MATHEMATICAL_AUDIT_AND_EXTENSIONS", "AUD"),
    ("060_MISTAKES_RETIRED_FORMS", "RET"),
    ("070_LEAN_RECEIPTS", "RCP"),
    ("080_HTML_BLOCK_SPECS", "WEB"),
    ("090_INTAKE_LEDGERS", "INT"),
    ("015_HISTORICAL_ARCS", "HIS"),
    ("010_MAIN_INTRO_AND_HUB", "HUB"),
    ("000_START_HERE", "STH"),
    ("999_ARCHIVE_SOURCE_COPIES", "ARC"),
]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_canonical_document(root: Path) -> tuple[Path, str] | None:
    candidates = list(root.rglob("THE_MASTER_EQUATION_CANONICAL_DOCUMENT*.md"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    doc = candidates[0]
    return doc, _sha256_file(doc)


def _kind_from_path(path: str) -> str:
    # Inside the ME workspace, derive kind from folder name.
    norm = path.replace("\\", "/")
    for prefix, kind in FOLDER_KIND_MAP:
        if prefix in norm:
            return kind
    # Lean proofs from the broader corpus that are series=MASTER_EQUATION
    if norm.endswith(".lean"):
        return "PRF"
    return "ARC"  # fallback archive/other


def _resolve_sha_for_path(cur: psycopg2.extensions.cursor, path: str) -> str | None:
    cur.execute("SELECT sha256 FROM locations WHERE path = %s", (path,))
    row = cur.fetchone()
    return row[0] if row else None


def _insert_presentation(
    cur: psycopg2.extensions.cursor,
    claim_id: str,
    sha256: str,
    path: str,
    kind: str,
    status: str = "U",
) -> None:
    cur.execute(
        """
        INSERT INTO me_presentations (claim_id, sha256, path, kind, status)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (claim_id, sha256, path) DO UPDATE SET
            kind = EXCLUDED.kind,
            status = EXCLUDED.status
        """,
        (claim_id, sha256, path, kind, status),
    )


def main() -> int:
    started = datetime.now(timezone.utc)
    conn = get_conn()
    reset_me_tables(conn)
    init_me_schema(conn)

    # ------------------------------------------------------------------
    # Governing claim
    # ------------------------------------------------------------------
    canonical = _find_canonical_document(ME_ROOT)
    if not canonical:
        logger.error("No Master Equation canonical document found under %s", ME_ROOT)
        return 1
    canonical_path, canonical_sha = canonical
    statement_version = canonical_sha[:16]
    logger.info("Governing claim document: %s (sha=%s)", canonical_path, canonical_sha)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO me_claims (claim_id, title, canonical_path, sha256,
                                   statement_version, status, created_at)
            VALUES (%s, %s, %s, %s, %s, 'K', NOW())
            ON CONFLICT (claim_id) DO UPDATE SET
                title = EXCLUDED.title,
                canonical_path = EXCLUDED.canonical_path,
                sha256 = EXCLUDED.sha256,
                statement_version = EXCLUDED.statement_version
            """,
            (
                CLAIM_ID,
                "THE MASTER EQUATION — CANONICAL DOCUMENT",
                str(canonical_path),
                canonical_sha,
                statement_version,
            ),
        )

        # Ensure the canonical document itself is in files table.
        existing_sha = _resolve_sha_for_path(cur, str(canonical_path))
        if not existing_sha:
            logger.warning("Canonical document not in corpus files table; inserting stub record")
            size = canonical_path.stat().st_size
            cur.execute(
                """
                INSERT INTO files (sha256, ext, size_bytes, first_seen, series,
                                   series_conf, verif_level, is_library, summary)
                VALUES (%s, '.md', %s, NOW(), 'MASTER_EQUATION', 0.95, 'UNVERIFIED',
                        false, %s)
                ON CONFLICT (sha256) DO NOTHING
                """,
                (canonical_sha, size, "THE MASTER EQUATION — CANONICAL DOCUMENT"),
            )
            cur.execute(
                "INSERT INTO locations (sha256, path) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (canonical_sha, str(canonical_path)),
            )
            existing_sha = canonical_sha

        # The canonical document is its own presentation, status K.
        _insert_presentation(cur, CLAIM_ID, existing_sha, str(canonical_path), "DEF", "K")

    conn.commit()

    # ------------------------------------------------------------------
    # Presentations from the 04_MASTER_EQUATION workspace
    # ------------------------------------------------------------------
    workspace_count = 0
    with conn.cursor() as cur:
        for dirpath, dirnames, filenames in os.walk(ME_ROOT):
            # Skip archived pass folders and zips to avoid duplicates.
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith("MASTER_EQUATION_MAXIMAL_REBUILD_PASS_")
                and not d.endswith(".zip")
            ]
            for fn in filenames:
                path = os.path.join(dirpath, fn)
                ext = os.path.splitext(fn)[1].lower()
                if ext not in {".lean", ".md", ".txt", ".tex", ".py", ".csv", ".json"}:
                    continue
                sha = _resolve_sha_for_path(cur, path)
                if not sha:
                    # Not yet indexed: compute and add a stub location/files row.
                    sha = _sha256_file(Path(path))
                    size = os.path.getsize(path)
                    cur.execute(
                        """
                        INSERT INTO files (sha256, ext, size_bytes, first_seen, series,
                                           series_conf, verif_level, is_library, summary)
                        VALUES (%s, %s, %s, NOW(), 'MASTER_EQUATION', 0.95, 'UNVERIFIED',
                                false, %s)
                        ON CONFLICT (sha256) DO NOTHING
                        """,
                        (sha, ext, size, os.path.basename(path)),
                    )
                    cur.execute(
                        "INSERT INTO locations (sha256, path) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (sha, path),
                    )
                kind = _kind_from_path(path)
                # The canonical doc was already inserted as K; skip re-inserting as U.
                if sha == canonical_sha and path == str(canonical_path):
                    continue
                _insert_presentation(cur, CLAIM_ID, sha, path, kind, "U")
                workspace_count += 1
                if workspace_count % 500 == 0:
                    conn.commit()
                    logger.info("Imported %d workspace presentations...", workspace_count)
    conn.commit()
    logger.info("Imported %d workspace presentations", workspace_count)

    # ------------------------------------------------------------------
    # Presentations from corpus files already classified MASTER_EQUATION
    # ------------------------------------------------------------------
    corpus_count = 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT f.sha256, l.path, f.ext
            FROM files f
            JOIN locations l ON l.sha256 = f.sha256
            WHERE f.series = 'MASTER_EQUATION'
            """
        )
        for sha, path, ext in cur.fetchall():
            # Skip the canonical doc if it somehow appears again.
            if sha == canonical_sha and path == str(canonical_path):
                continue
            kind = "PRF" if ext == ".lean" else _kind_from_path(path)
            _insert_presentation(cur, CLAIM_ID, sha, path, kind, "U")
            corpus_count += 1
            if corpus_count % 500 == 0:
                conn.commit()
                logger.info("Imported %d corpus MASTER_EQUATION presentations...", corpus_count)
    conn.commit()
    logger.info("Imported %d corpus MASTER_EQUATION presentations", corpus_count)

    # ------------------------------------------------------------------
    # Drift report
    # ------------------------------------------------------------------
    drift_count = 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT sha256, path, pinned_version
            FROM me_presentations
            WHERE claim_id = %s AND status != 'K'
            """,
            (CLAIM_ID,),
        )
        for sha, path, pinned in cur.fetchall():
            drift_type = "NO_PIN" if pinned is None else "VERSION_MISMATCH"
            detail = f"pinned={pinned}, current={statement_version}"
            cur.execute(
                """
                INSERT INTO me_drift (claim_id, sha256, path, drift_type, detail)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (CLAIM_ID, sha, path, drift_type, detail),
            )
            drift_count += 1
    conn.commit()
    logger.info("Drift report: %d presentations need review", drift_count)

    # ------------------------------------------------------------------
    # Export sidecar CSV and receipt
    # ------------------------------------------------------------------
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.sha256, p.kind, p.status, f.summary, p.path
            FROM me_presentations p
            JOIN files f ON f.sha256 = p.sha256
            WHERE p.claim_id = %s
            ORDER BY p.kind, p.path
            """,
            (CLAIM_ID,),
        )
        rows = cur.fetchall()

    REVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    me_csv = REVIEW_ROOT / "ME.csv"
    with me_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sha256", "kind", "status", "summary", "path"])
        writer.writerows(rows)
    logger.info("Exported ME sidecar CSV: %s (%d rows)", me_csv, len(rows))

    finished = datetime.now(timezone.utc)
    receipt = {
        "run_id": "me-sidecar-" + started.strftime("%Y-%m-%dT%H%M%S"),
        "started": started.isoformat(),
        "finished": finished.isoformat(),
        "claim_id": CLAIM_ID,
        "canonical_path": str(canonical_path),
        "canonical_sha256": canonical_sha,
        "statement_version": statement_version,
        "counts": {
            "workspace_presentations": workspace_count,
            "corpus_presentations": corpus_count,
            "total_presentations": len(rows),
            "drift_items": drift_count,
        },
        "exports": {
            "ME.csv": {
                "path": str(me_csv),
                "rows": len(rows),
                "query": "SELECT p.sha256, p.kind, p.status, f.summary, p.path FROM me_presentations p JOIN files f ON f.sha256 = p.sha256 WHERE p.claim_id = 'ME' ORDER BY p.kind, p.path",
            }
        },
    }

    receipts_dir = project_dir() / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipts_dir / f"{receipt['run_id']}-receipt.json"
    with receipt_path.open("w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, default=str)
    logger.info("Receipt written to %s", receipt_path)

    print("\n=== ME sidecar ===")
    print(f"  Claim:        {canonical_path}")
    print(f"  Version:      {statement_version}")
    print(f"  Workspace:    {workspace_count}")
    print(f"  Corpus ME:    {corpus_count}")
    print(f"  Total rows:   {len(rows)}")
    print(f"  Drift items:  {drift_count}")
    print(f"  CSV:          {me_csv}")
    print(f"  Receipt:      {receipt_path}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
