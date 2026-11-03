"""Master Equation sidecar schema: claims, presentations, drift, receipts."""

from __future__ import annotations

import logging

import psycopg2

logger = logging.getLogger(__name__)

ME_KINDS = [
    "DEF", "LAW", "TST", "SPI", "PHY", "PRF", "MTB", "AUD", "RET",
    "RCP", "WEB", "INT", "HIS", "HUB", "STH", "ARC", "DER",
]
ME_STATUSES = ["U", "P", "B", "D", "X", "K"]


def init_me_schema(conn: psycopg2.extensions.connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS me_claims (
                claim_id        text PRIMARY KEY,
                title           text NOT NULL,
                canonical_path  text,
                sha256          char(64) REFERENCES files(sha256),
                statement_version text,
                status          char(1) NOT NULL DEFAULT 'U'
                                CHECK (status IN ({','.join("'"+s+"'" for s in ME_STATUSES)})),
                ruled_at        timestamptz,
                ruled_by        text,
                created_at      timestamptz NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS me_presentations (
                id              serial PRIMARY KEY,
                claim_id        text NOT NULL REFERENCES me_claims(claim_id) ON DELETE CASCADE,
                sha256          char(64) NOT NULL REFERENCES files(sha256),
                path            text NOT NULL,
                kind            text NOT NULL
                                CHECK (kind IN ({','.join("'"+k+"'" for k in ME_KINDS)})),
                status          char(1) NOT NULL DEFAULT 'U'
                                CHECK (status IN ({','.join("'"+s+"'" for s in ME_STATUSES)})),
                pinned_version  text,
                inserted_at     timestamptz NOT NULL DEFAULT NOW(),
                UNIQUE (claim_id, sha256, path)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS me_drift (
                id              serial PRIMARY KEY,
                claim_id        text NOT NULL REFERENCES me_claims(claim_id) ON DELETE CASCADE,
                sha256          char(64) NOT NULL REFERENCES files(sha256),
                path            text NOT NULL,
                drift_type      text NOT NULL,
                detail          text,
                detected_at     timestamptz NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS me_claim_receipts (
                id              serial PRIMARY KEY,
                claim_id        text NOT NULL REFERENCES me_claims(claim_id) ON DELETE CASCADE,
                kind            text NOT NULL,
                result          text,
                log_path        text,
                ran_at          timestamptz NOT NULL DEFAULT NOW()
            )
            """
        )
    conn.commit()


def reset_me_tables(conn: psycopg2.extensions.connection) -> None:
    with conn.cursor() as cur:
        for table in ("me_drift", "me_claim_receipts", "me_presentations", "me_claims"):
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    conn.commit()
