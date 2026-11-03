"""Postgres schema and data access for the corpus indexer."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import psycopg2

from config import DB_CONFIG

logger = logging.getLogger(__name__)


def get_conn() -> psycopg2.extensions.connection:
    return psycopg2.connect(**DB_CONFIG)


def init_schema(conn: psycopg2.extensions.connection) -> None:
    with conn.cursor() as cur:
        # Defer vector extension until the server has it installed.
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            logger.info("pgvector extension enabled")
        except psycopg2.Error as exc:
            logger.warning("pgvector extension not available: %s", exc)
            conn.rollback()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                sha256        char(64) PRIMARY KEY,
                ext           text NOT NULL,
                size_bytes    bigint NOT NULL,
                first_seen    timestamptz NOT NULL,
                series        text,
                series_conf   real,
                verif_level   text NOT NULL DEFAULT 'UNVERIFIED',
                decl_count    int,
                sorry_active  int,
                is_library    boolean DEFAULT false,
                summary       text
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS locations (
                sha256 char(64) REFERENCES files(sha256) ON DELETE CASCADE,
                path   text NOT NULL,
                PRIMARY KEY (sha256, path)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS declarations (
                sha256 char(64) REFERENCES files(sha256) ON DELETE CASCADE,
                name   text NOT NULL,
                kind   text NOT NULL,
                PRIMARY KEY (sha256, name)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS receipts (
                sha256  char(64) REFERENCES files(sha256) ON DELETE CASCADE,
                run_id  text NOT NULL,
                kind    text NOT NULL,
                result  text,
                log_path text,
                ran_at  timestamptz,
                PRIMARY KEY (sha256, run_id, kind)
            )
            """
        )
        # Only create embeddings table if the vector extension is present.
        cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector';")
        if cur.fetchone():
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS embeddings (
                    sha256 char(64) PRIMARY KEY REFERENCES files(sha256),
                    vec vector(768)
                )
                """
            )
    conn.commit()


def reset_corpus_tables(conn: psycopg2.extensions.connection) -> None:
    """Drop the four corpus tables (useful for a clean rerun)."""
    with conn.cursor() as cur:
        for table in ("declarations", "locations", "receipts", "embeddings", "files"):
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
    conn.commit()


def _s(value: str | None) -> str | None:
    if value is None:
        return None
    return value.replace("\x00", "")


def upsert_file(
    cur: psycopg2.extensions.cursor,
    sha256: str,
    ext: str,
    size_bytes: int,
    first_seen: datetime,
    series: str | None,
    series_conf: float | None,
    decl_count: int | None,
    sorry_active: int | None,
    is_library: bool,
    summary: str | None,
) -> None:
    cur.execute(
        """
        INSERT INTO files (sha256, ext, size_bytes, first_seen, series, series_conf,
                           verif_level, decl_count, sorry_active, is_library, summary)
        VALUES (%(sha256)s, %(ext)s, %(size_bytes)s, %(first_seen)s, %(series)s,
                %(series_conf)s, 'UNVERIFIED', %(decl_count)s, %(sorry_active)s,
                %(is_library)s, %(summary)s)
        ON CONFLICT (sha256) DO UPDATE SET
            ext = EXCLUDED.ext,
            size_bytes = EXCLUDED.size_bytes,
            series = EXCLUDED.series,
            series_conf = EXCLUDED.series_conf,
            decl_count = EXCLUDED.decl_count,
            sorry_active = EXCLUDED.sorry_active,
            is_library = EXCLUDED.is_library,
            summary = EXCLUDED.summary
        """,
        {
            "sha256": sha256,
            "ext": _s(ext),
            "size_bytes": size_bytes,
            "first_seen": first_seen,
            "series": _s(series),
            "series_conf": series_conf,
            "decl_count": decl_count,
            "sorry_active": sorry_active,
            "is_library": is_library,
            "summary": _s(summary),
        },
    )


def insert_location(
    cur: psycopg2.extensions.cursor, sha256: str, path: str
) -> None:
    cur.execute(
        """
        INSERT INTO locations (sha256, path) VALUES (%s, %s)
        ON CONFLICT (sha256, path) DO NOTHING
        """,
        (sha256, _s(path)),
    )


def insert_declaration(
    cur: psycopg2.extensions.cursor, sha256: str, name: str, kind: str
) -> None:
    cur.execute(
        """
        INSERT INTO declarations (sha256, name, kind) VALUES (%s, %s, %s)
        ON CONFLICT (sha256, name) DO NOTHING
        """,
        (sha256, _s(name), _s(kind)),
    )


def insert_receipt(
    cur: psycopg2.extensions.cursor,
    sha256: str,
    run_id: str,
    kind: str,
    result: str | None,
    log_path: str | None,
    ran_at: datetime | None,
) -> None:
    cur.execute(
        """
        INSERT INTO receipts (sha256, run_id, kind, result, log_path, ran_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (sha256, run_id, kind) DO UPDATE SET
            result = EXCLUDED.result,
            log_path = EXCLUDED.log_path,
            ran_at = EXCLUDED.ran_at
        """,
        (sha256, _s(run_id), _s(kind), _s(result), _s(log_path), ran_at),
    )


def compute_verif_levels(conn: psycopg2.extensions.connection) -> None:
    """Set files.verif_level from receipts and sorry_active counts."""
    with conn.cursor() as cur:
        # Reset to UNVERIFIED first, then promote.
        cur.execute("UPDATE files SET verif_level = 'UNVERIFIED';")

        # GAPS: active sorry in the file itself
        cur.execute(
            """
            UPDATE files
            SET verif_level = 'GAPS'
            WHERE sorry_active > 0
              AND verif_level = 'UNVERIFIED'
            """
        )

        # AI_REVIEW: has an AI_REVIEW receipt but no passing BUILD receipt
        cur.execute(
            """
            UPDATE files f
            SET verif_level = 'AI_REVIEW'
            WHERE EXISTS (
                SELECT 1 FROM receipts r
                WHERE r.sha256 = f.sha256 AND r.kind = 'AI_REVIEW'
            )
            AND NOT EXISTS (
                SELECT 1 FROM receipts r2
                WHERE r2.sha256 = f.sha256
                  AND r2.kind = 'BUILD'
                  AND r2.result = 'PASS'
            )
            AND f.verif_level = 'UNVERIFIED'
            """
        )

        # KERNEL_NATIVE_DECIDE: passing BUILD + PRINT_AXIOMS with native_decide
        cur.execute(
            """
            UPDATE files f
            SET verif_level = 'KERNEL_NATIVE_DECIDE'
            WHERE EXISTS (
                SELECT 1 FROM receipts r
                WHERE r.sha256 = f.sha256
                  AND r.kind = 'BUILD' AND r.result = 'PASS'
            )
            AND EXISTS (
                SELECT 1 FROM receipts r2
                WHERE r2.sha256 = f.sha256
                  AND r2.kind = 'PRINT_AXIOMS'
                  AND r2.result = 'NATIVE_DECIDE'
            )
            """
        )

        # KERNEL: passing BUILD + PRINT_AXIOMS clean
        cur.execute(
            """
            UPDATE files f
            SET verif_level = 'KERNEL'
            WHERE EXISTS (
                SELECT 1 FROM receipts r
                WHERE r.sha256 = f.sha256
                  AND r.kind = 'BUILD' AND r.result = 'PASS'
            )
            AND EXISTS (
                SELECT 1 FROM receipts r2
                WHERE r2.sha256 = f.sha256
                  AND r2.kind = 'PRINT_AXIOMS'
                  AND r2.result = 'CLEAN'
            )
            AND f.verif_level NOT IN ('KERNEL_NATIVE_DECIDE')
            """
        )
    conn.commit()


def get_p1_metrics(cur: psycopg2.extensions.cursor) -> dict[str, Any]:
    cur.execute("SELECT COUNT(*) FROM files;")
    unique_files = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM locations;")
    total_locations = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT sha256 FROM locations GROUP BY sha256 HAVING COUNT(*) > 1
        ) dup
        """
    )
    duplicate_hashes = cur.fetchone()[0]

    cur.execute(
        """
        SELECT ext, COUNT(*) FROM files GROUP BY ext ORDER BY COUNT(*) DESC
        """
    )
    per_ext = dict(cur.fetchall())

    per_root: dict[str, int] = {}
    cur.execute("SELECT path FROM locations;")
    for (path,) in cur:
        root = _root_for(path)
        per_root[root] = per_root.get(root, 0) + 1

    return {
        "unique_files": unique_files,
        "total_locations": total_locations,
        "duplicate_hashes": duplicate_hashes,
        "duplicate_ratio": round(duplicate_hashes / unique_files, 4) if unique_files else 0.0,
        "per_ext": per_ext,
        "per_root": per_root,
    }


def get_p2_metrics(cur: psycopg2.extensions.cursor) -> dict[str, Any]:
    cur.execute("SELECT COUNT(*) FROM files;")
    total = cur.fetchone()[0]
    if total == 0:
        return {}

    cur.execute(
        "SELECT COUNT(*) FROM files WHERE series IS NOT NULL AND series_conf >= 0.8"
    )
    classified = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM files WHERE is_library = true")
    library = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM files WHERE series IS NULL")
    unclassified = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(DISTINCT f.sha256)
        FROM files f
        JOIN receipts r ON r.sha256 = f.sha256
        WHERE r.kind IN ('BUILD', 'PRINT_AXIOMS', 'AI_REVIEW')
        """
    )
    with_receipt = cur.fetchone()[0]

    cur.execute(
        """
        SELECT series, COUNT(*) FROM files
        WHERE series IS NOT NULL
        GROUP BY series ORDER BY COUNT(*) DESC
        """
    )
    series_counts = dict(cur.fetchall())

    return {
        "total": total,
        "classified": classified,
        "classified_pct": round(classified / total * 100, 2),
        "library": library,
        "library_pct": round(library / total * 100, 2),
        "unclassified": unclassified,
        "unclassified_pct": round(unclassified / total * 100, 2),
        "with_receipt": with_receipt,
        "with_receipt_pct": round(with_receipt / total * 100, 2),
        "series_counts": series_counts,
    }


def get_spot_check(
    cur: psycopg2.extensions.cursor, limit: int = 50
) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT f.sha256, l.path, f.series, f.series_conf, f.verif_level,
               f.decl_count, f.sorry_active, f.summary
        FROM files f
        JOIN locations l ON l.sha256 = f.sha256
        WHERE f.ext = '.lean'
        ORDER BY RANDOM()
        LIMIT %s
        """,
        (limit,),
    )
    rows = cur.fetchall()
    return [
        {
            "sha256": r[0],
            "path": r[1],
            "series": r[2],
            "series_conf": r[3],
            "verif_level": r[4],
            "decl_count": r[5],
            "sorry_active": r[6],
            "summary": r[7],
        }
        for r in rows
    ]


def _root_for(path: str) -> str:
    """Return the configured source root that contains path, or 'OTHER'."""
    from config import SOURCE_ROOTS

    lower = path.replace("\\", "/").lower()
    for root in SOURCE_ROOTS:
        norm_root = root.replace("\\", "/").lower()
        if lower.startswith(norm_root):
            return root
    return "OTHER"
