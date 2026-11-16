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
            initialize(con)

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
                con.execute('INSERT INTO registry_objects(uuid7) VALUES(?)', (value,))
                con.execute('INSERT INTO document_identities VALUES(?,?,?,?,?)',
                            (key, value, series, position, original_title))
                return dict(con.execute('SELECT * FROM document_identities WHERE registry_id=?', (key,)).fetchone())
        finally:
            con.close()

    def reference(self, path: str | Path, *, con=None) -> dict:
        """Admit an observed path. Unassigned objects have no public document name."""
        if con is None:
            connection = self._connect()
            try:
                with connection:
                    connection.execute('BEGIN IMMEDIATE')
                    return self.reference(path, con=connection)
            finally:
                connection.close()
        initialize(con)
        key = location_key(path)
        row = con.execute('SELECT uuid7,active FROM identity_locations WHERE path=?', (key,)).fetchone()
        if row and row['active']:
            token = row[0]
        else:
            token = _uuid7()
            con.execute('INSERT INTO registry_objects(uuid7) VALUES(?)', (token,))
            con.execute('INSERT INTO identity_locations(path,uuid7,active) VALUES(?,?,1) ON CONFLICT(path) DO UPDATE SET uuid7=excluded.uuid7,active=1', (key, token))
        issued = con.execute('SELECT registry_id FROM document_identities WHERE uuid7=?', (token,)).fetchone()
        return {'uuid7': token, 'registry_id': issued[0] if issued else None}

    def assign(self, path, series, position, original_title, *, con=None) -> dict:
        """Bind an observation to an explicit assignment; supports atomic batches."""
        if con is None:
            connection = self._connect()
            try:
                with connection:
                    connection.execute('BEGIN IMMEDIATE')
                    return self.assign(path, series, position, original_title, con=connection)
            finally:
                connection.close()
        key = document_id(series, position, original_title)
        ref = self.reference(path, con=con)
        existing = con.execute('SELECT * FROM document_identities WHERE registry_id=? OR uuid7=? OR (series=? AND position=?)',
                               (key, ref['uuid7'], series, position)).fetchall()
        if existing:
            if len(existing) != 1 or existing[0]['registry_id'] != key or existing[0]['uuid7'] != ref['uuid7']:
                raise ValueError('assignment conflicts with existing identity; explicit reconciliation required')
            return dict(existing[0])
        con.execute('INSERT INTO document_identities VALUES(?,?,?,?,?)', (key, ref['uuid7'], series, position, original_title))
        return dict(con.execute('SELECT * FROM document_identities WHERE registry_id=?', (key,)).fetchone())

    def alias(self, token, scheme, alias, *, con=None):
        if not isinstance(scheme, str) or not scheme.strip() or not isinstance(alias, str) or not alias.strip():
            raise ValueError('nonempty alias scheme and value required')
        if con is None:
            connection = self._connect()
            try:
                with connection:
                    connection.execute('BEGIN IMMEDIATE')
                    return self.alias(token, scheme, alias, con=connection)
            finally:
                connection.close()
        if not con.execute('SELECT 1 FROM registry_objects WHERE uuid7=?', (token,)).fetchone():
            raise ValueError('alias must reference an issued registry UUID')
        old = con.execute('SELECT uuid7 FROM identity_aliases WHERE scheme=? AND alias=?', (scheme, alias)).fetchone()
        if old and old[0] != token:
            raise ValueError('legacy alias already belongs to another object')
        con.execute('INSERT OR IGNORE INTO identity_aliases VALUES(?,?,?)', (scheme, alias, token))

    def validate_relocation(self, old_path, new_path, token, *, recovery=False):
        con = self._connect()
        try:
            old = con.execute('SELECT uuid7,active FROM identity_locations WHERE path=?', (location_key(old_path),)).fetchone()
            new = con.execute('SELECT uuid7,active FROM identity_locations WHERE path=?', (location_key(new_path),)).fetchone()
            if recovery:
                if old and old['active'] and old['uuid7'] != token:
                    raise ValueError('source registry identity changed after proposal')
                if not ((old and old['active'] and old['uuid7'] == token) or (new and new['active'] and new['uuid7'] == token)):
                    raise ValueError('journal identity is not at either recovery location')
            elif not old or not old['active'] or old['uuid7'] != token:
                raise ValueError('source registry identity changed after proposal')
            if new and new['active'] and new['uuid7'] != token:
                raise ValueError('target belongs to another registry identity')
        finally:
            con.close()

    def relocate(self, old_path, new_path, *, token=None):
        """Transfer an active location after a verified move; retain its history."""
        old_key, new_key = location_key(old_path), location_key(new_path)
        con = self._connect()
        try:
            with con:
                con.execute('BEGIN IMMEDIATE')
                old = con.execute('SELECT uuid7,active FROM identity_locations WHERE path=?', (old_key,)).fetchone()
                new = con.execute('SELECT uuid7,active FROM identity_locations WHERE path=?', (new_key,)).fetchone()
                token = token or (old['uuid7'] if old and old['active'] else None)
                if not token or not con.execute('SELECT 1 FROM registry_objects WHERE uuid7=?', (token,)).fetchone():
                    raise ValueError('move requires an existing registry reference')
                if old and old['active'] and old['uuid7'] != token:
                    raise ValueError('source location belongs to another registry identity')
                if new and new['active'] and new['uuid7'] != token:
                    raise ValueError('target belongs to another registry identity')
                # A journal token permits recovery when the file move committed
                # before its location update. It never mints another document.
                if old_key != new_key:
                    con.execute('INSERT OR IGNORE INTO identity_location_history VALUES(?,?)', (old_key, token))
                    con.execute('UPDATE identity_locations SET active=0 WHERE path=? AND uuid7=?', (old_key, token))
                con.execute('INSERT INTO identity_locations(path,uuid7,active) VALUES(?,?,1) ON CONFLICT(path) DO UPDATE SET uuid7=excluded.uuid7,active=1', (new_key, token))
                row = con.execute('SELECT registry_id FROM document_identities WHERE uuid7=?', (token,)).fetchone()
                return {'uuid7': token, 'registry_id': row[0] if row else None}
        finally:
            con.close()

    def lookup(self, reference: str, scheme: str | None = None) -> dict | None:
        con = self._connect()
        try:
            row = con.execute('SELECT * FROM document_identities WHERE registry_id=? OR uuid7=?',
                              (reference, reference)).fetchone()
            if row:
                return dict(row)
            if con.execute('SELECT 1 FROM registry_objects WHERE uuid7=?', (reference,)).fetchone():
                return {'uuid7': reference, 'registry_id': None}
            sql = 'SELECT DISTINCT uuid7 FROM identity_aliases WHERE alias=?'
            args = (reference,)
            if scheme is not None:
                sql += ' AND scheme=?'
                args = (reference, scheme)
            aliases = con.execute(sql, args).fetchall()
            if len(aliases) > 1:
                raise ValueError('ambiguous legacy alias; specify its scheme')
            if not aliases:
                return None
            token = aliases[0][0]
            row = con.execute('SELECT * FROM document_identities WHERE uuid7=?', (token,)).fetchone()
            return dict(row) if row else {'uuid7': token, 'registry_id': None}
        finally:
            con.close()


def location_key(path):
    # Windows strings must normalize consistently on Linux review/CI too.
    from pathlib import PureWindowsPath
    value = str(path)
    if PureWindowsPath(value).drive:
        return str(PureWindowsPath(value)).replace("\\", "/").casefold()
    return str(Path(value).expanduser().resolve())


def initialize(con):
    # Individual statements preserve the caller's surrounding transaction.
    con.execute("CREATE TABLE IF NOT EXISTS identity_migrations(mapping_hash TEXT PRIMARY KEY, reviewed_by TEXT NOT NULL, mapping_json TEXT NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS registry_objects(uuid7 TEXT PRIMARY KEY)")
    con.execute("CREATE TABLE IF NOT EXISTS identity_locations(path TEXT PRIMARY KEY, uuid7 TEXT NOT NULL REFERENCES registry_objects(uuid7), active INTEGER NOT NULL DEFAULT 1)")
    if 'active' not in {row[1] for row in con.execute('PRAGMA table_info(identity_locations)')}:
        con.execute('ALTER TABLE identity_locations ADD COLUMN active INTEGER NOT NULL DEFAULT 1')
    con.execute('CREATE TABLE IF NOT EXISTS identity_location_history(path TEXT, uuid7 TEXT, PRIMARY KEY(path,uuid7))')
    con.execute("CREATE TABLE IF NOT EXISTS identity_aliases(scheme TEXT, alias TEXT, uuid7 TEXT NOT NULL REFERENCES registry_objects(uuid7), PRIMARY KEY(scheme,alias))")
    con.execute("INSERT OR IGNORE INTO registry_objects SELECT uuid7 FROM document_identities")
