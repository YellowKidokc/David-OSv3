"""Owned state, separate from source trees. No import-time filesystem writes."""
import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def uid():
    return uuid.uuid4().hex


class Store:
    def __init__(self, path=None):
        self.home = Path(path or os.environ.get("FIS_HOME", Path.home() / ".fis-standalone")).resolve()
        self.home.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript('''
            CREATE TABLE IF NOT EXISTS items(kind TEXT, id TEXT, value TEXT NOT NULL,
              PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS contents(hash TEXT PRIMARY KEY, bytes INTEGER);
            CREATE TABLE IF NOT EXISTS instances(path TEXT PRIMARY KEY, hash TEXT, value TEXT);
            CREATE TABLE IF NOT EXISTS operations(run TEXT, seq INTEGER, value TEXT NOT NULL,
              PRIMARY KEY(run,seq));
            ''')

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.home / "index.sqlite", timeout=30)
        con.execute("PRAGMA synchronous=FULL")
        try:
            with con:
                yield con
        finally:
            con.close()

    def put(self, kind, key, value):
        with self.connect() as con:
            con.execute("INSERT OR REPLACE INTO items VALUES(?,?,?)", (kind, key, canonical(value)))

    def get(self, kind, key, default=None):
        with self.connect() as con:
            row = con.execute("SELECT value FROM items WHERE kind=? AND id=?", (kind, key)).fetchone()
        return json.loads(row[0]) if row else default

    def all(self, kind):
        with self.connect() as con:
            rows = con.execute("SELECT value FROM items WHERE kind=? ORDER BY rowid DESC", (kind,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def record(self, row):
        with self.connect() as con:
            con.execute("INSERT OR IGNORE INTO contents VALUES(?,?)", (row['sha256'], row['size']))
            con.execute("INSERT OR REPLACE INTO instances VALUES(?,?,?)", (row['path'], row['sha256'], canonical(row)))

    def search(self, query):
        # Literal substring search: user wildcards are not SQL wildcards.
        with self.connect() as con:
            rows = con.execute("SELECT value FROM instances").fetchall()
        return [json.loads(r[0]) for r in rows if query.casefold() in r[0].casefold()]

    def op(self, run, seq, value):
        with self.connect() as con:
            con.execute("INSERT OR REPLACE INTO operations VALUES(?,?,?)", (run, seq, canonical(value)))

    def ops(self, run):
        with self.connect() as con:
            rows = con.execute("SELECT value FROM operations WHERE run=? ORDER BY seq", (run,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    @contextmanager
    def lock(self):
        """OS releases the state mutex even if the worker is killed."""
        handle = open(self.home / "executor.lock", "a+b")
        handle.seek(0)
        if handle.read(1) == b"":
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.close()
