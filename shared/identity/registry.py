"""The issuance boundary for SERIES.NN_Original-Title identities and UUIDv7.

Uses the Stage 1 SQLite file; never opens an external drive or renames a file.
An explicit series, position and original title are required. This does not
infer assignments from a hash, classification or changing relation counts.
Legacy records are preserved pending a reviewed alias migration.
"""
from __future__ import annotations

import os
from contextlib import closing
from pathlib import Path
import re
import secrets
import sqlite3
import time
from uuid import UUID

DEFAULT_PATH = Path(__file__).resolve().parents[2] / '_data' / 'registry.sqlite'
SERIES = re.compile(r'[A-Z]{3,5}\Z')


def _uuid7() -> str:
    # RFC 9562: 48-bit Unix milliseconds, version 7, RFC variant, random tail.
    millis = time.time_ns() // 1_000_000
    value = ((millis & ((1 << 48) - 1)) << 80) | (7 << 76)
    value |= secrets.randbits(12) << 64
    value |= (2 << 62) | secrets.randbits(62)
    return str(UUID(int=value))


def document_id(series: str, position: int, original_title: str) -> str:
    """Validate an explicit assignment; this function does not issue an ID."""
    if not isinstance(series, str) or not SERIES.fullmatch(series):
        raise ValueError('series must contain 3–5 uppercase letters')
    if type(position) is not int or not 0 <= position <= 99:
        raise ValueError('position must be an integer from 0 to 99')
    if (not isinstance(original_title, str) or not original_title.strip()
            or original_title != original_title.strip()
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', original_title)
            or original_title.endswith('.')):
        raise ValueError('original title must be nonempty and filename-safe')
    return f'{series}.{position:02d}_{original_title}'


class IdentityRegistry:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path or os.environ.get('DAVID_OS_REGISTRY', DEFAULT_PATH))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as con, con:
            con.execute('''CREATE TABLE IF NOT EXISTS document_identities (
                registry_id TEXT PRIMARY KEY,
                uuid7 TEXT NOT NULL UNIQUE,
                series TEXT NOT NULL,
                position INTEGER NOT NULL CHECK(position BETWEEN 0 AND 99),
                original_title TEXT NOT NULL,
                UNIQUE(series, position))''')

    def _connect(self):
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        return con

    def issue(self, series: str, position: int, original_title: str) -> dict:
        key = document_id(series, position, original_title)
        con = self._connect()
        try:
            with con:
                con.execute('BEGIN IMMEDIATE')
                row = con.execute('SELECT * FROM document_identities WHERE series=? AND position=?',
                                  (series, position)).fetchone()
                if row:
                    if row['registry_id'] != key:
                        raise ValueError('series position already issued; original title is immutable')
                    return dict(row)
                value = _uuid7()
                con.execute('INSERT INTO document_identities VALUES(?,?,?,?,?)',
                            (key, value, series, position, original_title))
                return dict(con.execute('SELECT * FROM document_identities WHERE registry_id=?', (key,)).fetchone())
        finally:
            con.close()

    def lookup(self, reference: str) -> dict | None:
        con = self._connect()
        try:
            row = con.execute('SELECT * FROM document_identities WHERE registry_id=? OR uuid7=?',
                              (reference, reference)).fetchone()
            return dict(row) if row else None
        finally:
            con.close()
