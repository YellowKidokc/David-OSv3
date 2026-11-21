#!/usr/bin/env python3
"""FileTagger Daemon — always-on background file watcher + cataloger.

On start:
  1. Incremental scan of watched folders → catalog.db (skips unchanged)
  2. watchdog observer fires on every create/modify/delete/move → DB updated live
  3. Writes daemon_status.json every 30s for the status page

Launch headless:  pythonw filetagger_daemon.py
Stop:             kill via Task Manager or tray (PID is in daemon_status.json)
"""

import hashlib, json, logging, os, sqlite3, sys, threading, time
from datetime import datetime
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    sys.exit("watchdog not installed — run:  pip install watchdog")

# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "daemon_config.json"

DEFAULT_CONFIG = {
    "watch_folders": ["D:\\DONT TOUCH BOOT UP"],
    "db_path": str(APP_DIR / "catalog.db"),
    "status_file": str(APP_DIR / "daemon_status.json"),
    "log_file": str(APP_DIR / "daemon.log"),
    "skip_dirs": [".git", "__pycache__", ".venv", "node_modules", ".obsidian",
                  "salvaged", "sample"],
    "skip_names": ["thumbs.db", "desktop.ini", ".ds_store"],
    "status_interval_s": 30,
}

TEXT_EXTS = {
    ".txt", ".md", ".py", ".js", ".ts", ".css", ".html", ".htm",
    ".json", ".yaml", ".yml", ".xml", ".ini", ".cfg", ".bat",
    ".ps1", ".sh", ".sql", ".csv", ".log", ".rst", ".ahk",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS files(
  path      TEXT PRIMARY KEY,
  name      TEXT,
  ext       TEXT,
  size      INTEGER,
  md5       TEXT,
  created   TEXT,
  modified  TEXT,
  accessed  TEXT,
  tags      TEXT,
  category  TEXT,
  tier      TEXT,
  mtime     REAL,
  scanned   TEXT,
  status    TEXT DEFAULT 'active',
  moved_from TEXT DEFAULT NULL,
  moved_to   TEXT DEFAULT NULL,
  moved_at   TEXT DEFAULT NULL,
  deleted_at TEXT DEFAULT NULL
)
"""

MIGRATE_COLS = [
    ("status",     "TEXT DEFAULT 'active'"),
    ("moved_from", "TEXT DEFAULT NULL"),
    ("moved_to",   "TEXT DEFAULT NULL"),
    ("moved_at",   "TEXT DEFAULT NULL"),
    ("deleted_at", "TEXT DEFAULT NULL"),
]

_start_ts = time.time()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def quick_md5(path: str, size: int) -> str:
    h = hashlib.md5(str(size).encode())
    with open(path, "rb") as fh:
        h.update(fh.read(65536))
        if size > 131072:
            fh.seek(-65536, os.SEEK_END)
            h.update(fh.read(65536))
    return h.hexdigest()


def file_record(path: str) -> dict:
    p = Path(path)
    st = p.stat()
    ext = p.suffix.lower()
    size = st.st_size
    return {
        "path":       str(p.resolve()),
        "name":       p.name,
        "ext":        ext,
        "size":       size,
        "md5":        quick_md5(path, size),
        "created":    datetime.fromtimestamp(st.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
        "modified":   datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "accessed":   datetime.fromtimestamp(st.st_atime).strftime("%Y-%m-%d %H:%M:%S"),
        "tags":       "",
        "category":   "",
        "tier":       "text" if ext in TEXT_EXTS else "blob",
        "mtime":      st.st_mtime,
        "scanned":    ts(),
        "status":     "active",
        "moved_from": None,
        "moved_to":   None,
        "moved_at":   None,
        "deleted_at": None,
    }


# ---------------------------------------------------------------------------
# Thread-safe DB wrapper
# ---------------------------------------------------------------------------

class DaemonDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_schema()

    def _conn(self):
        return sqlite3.connect(self.db_path, timeout=15)

    def _init_schema(self):
        with self.lock:
            db = self._conn()
            db.execute(SCHEMA)
            db.commit()
            for col, coltype in MIGRATE_COLS:
                try:
                    db.execute(f"ALTER TABLE files ADD COLUMN {col} {coltype}")
                    db.commit()
                except Exception:
                    pass
            db.close()

    def upsert(self, rec: dict):
        cols = list(rec.keys())
        sql = (f"INSERT OR REPLACE INTO files ({','.join(cols)}) "
               f"VALUES ({','.join('?'*len(cols))})")
        with self.lock:
            db = self._conn()
            db.execute(sql, [rec[c] for c in cols])
            db.commit()
            db.close()

    def mark_deleted(self, path: str):
        with self.lock:
            db = self._conn()
            db.execute(
                "UPDATE files SET status='deleted', deleted_at=? WHERE path=?",
                (ts(), path)
            )
            db.commit()
            db.close()

    def mark_moved(self, src: str, dest: str):
        with self.lock:
            db = self._conn()
            db.execute(
                "UPDATE files SET status='moved', moved_to=?, moved_at=? WHERE path=?",
                (dest, ts(), src)
            )
            db.commit()
            db.close()

    def get_stats(self) -> dict:
        with self.lock:
            db = self._conn()
            try:
                total   = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
                active  = db.execute("SELECT COUNT(*) FROM files WHERE status='active'").fetchone()[0]
                deleted = db.execute("SELECT COUNT(*) FROM files WHERE status='deleted'").fetchone()[0]
                moved   = db.execute("SELECT COUNT(*) FROM files WHERE status='moved'").fetchone()[0]
                recent  = db.execute(
                    "SELECT path, status, scanned FROM files ORDER BY scanned DESC LIMIT 5"
                ).fetchall()
            except Exception:
                total = active = deleted = moved = 0
                recent = []
            db.close()
        return {
            "total":   total,
            "active":  active,
            "deleted": deleted,
            "moved":   moved,
            "recent":  [{"path": r[0], "status": r[1], "scanned": r[2]} for r in recent],
        }

    def existing_mtimes(self) -> dict:
        with self.lock:
            db = self._conn()
            rows = db.execute(
                "SELECT path, mtime FROM files WHERE status='active'"
            ).fetchall()
            db.close()
        return {r[0]: r[1] for r in rows}


# ---------------------------------------------------------------------------
# watchdog event handler
# ---------------------------------------------------------------------------

class WatchHandler(FileSystemEventHandler):
    def __init__(self, db: DaemonDB, skip_dirs: set, skip_names: set):
        self.db = db
        self.skip_dirs = skip_dirs
        self.skip_names = skip_names
        self._last: dict[str, float] = {}
        self._lk = threading.Lock()

    def _skip(self, path: str) -> bool:
        p = Path(path)
        if p.name.lower() in self.skip_names:
            return True
        return any(part in self.skip_dirs for part in p.parts)

    def _debounce(self, path: str, window: float = 1.5) -> bool:
        now = time.time()
        with self._lk:
            if now - self._last.get(path, 0) < window:
                return False
            self._last[path] = now
        return True

    def on_created(self, event):
        if event.is_directory or self._skip(event.src_path) or not self._debounce(event.src_path):
            return
        try:
            self.db.upsert(file_record(event.src_path))
            logging.info("NEW      %s", event.src_path)
        except Exception as e:
            logging.warning("on_created %s: %s", event.src_path, e)

    def on_modified(self, event):
        if event.is_directory or self._skip(event.src_path) or not self._debounce(event.src_path):
            return
        try:
            self.db.upsert(file_record(event.src_path))
            logging.info("MODIFIED %s", event.src_path)
        except Exception as e:
            logging.warning("on_modified %s: %s", event.src_path, e)

    def on_deleted(self, event):
        if event.is_directory or self._skip(event.src_path):
            return
        path = str(Path(event.src_path).resolve())
        self.db.mark_deleted(path)
        logging.info("DELETED  %s", event.src_path)

    def on_moved(self, event):
        if event.is_directory:
            return
        src  = str(Path(event.src_path).resolve())
        dest = str(Path(event.dest_path).resolve())
        self.db.mark_moved(src, dest)
        try:
            rec = file_record(event.dest_path)
            rec["moved_from"] = src
            self.db.upsert(rec)
        except Exception as e:
            logging.warning("on_moved %s -> %s: %s", src, dest, e)
        logging.info("MOVED    %s  ->  %s", src, dest)


# ---------------------------------------------------------------------------
# Initial scan
# ---------------------------------------------------------------------------

def initial_scan(folders, db: DaemonDB, skip_dirs: set, skip_names: set):
    logging.info("Initial scan starting...")
    seen = db.existing_mtimes()
    count = skip = err = 0

    for folder in folders:
        for dirpath, dirnames, filenames in os.walk(folder):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for fname in filenames:
                if fname.lower() in skip_names:
                    continue
                full = os.path.join(dirpath, fname)
                try:
                    mt = os.path.getmtime(full)
                except OSError:
                    continue
                abs_path = str(Path(full).resolve())
                if abs_path in seen and abs(seen[abs_path] - mt) < 1e-6:
                    skip += 1
                    continue
                try:
                    db.upsert(file_record(full))
                    count += 1
                    if count % 250 == 0:
                        logging.info("  ...%d new/changed so far", count)
                except Exception as e:
                    err += 1
                    logging.debug("scan skip %s: %s", full, e)

    logging.info("Initial scan done: %d new/changed, %d unchanged, %d errors", count, skip, err)


# ---------------------------------------------------------------------------
# Status writer
# ---------------------------------------------------------------------------

def write_status(cfg: dict, db: DaemonDB, observers: list):
    stats = db.get_stats()
    payload = {
        "running":         True,
        "pid":             os.getpid(),
        "started_at":      datetime.fromtimestamp(_start_ts).strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at":      ts(),
        "uptime_s":        round(time.time() - _start_ts),
        "watch_folders":   cfg["watch_folders"],
        "db_path":         cfg["db_path"],
        "observers_alive": sum(1 for o in observers if o.is_alive()),
        **stats,
    }
    try:
        with open(cfg["status_file"], "w") as f:
            json.dump(payload, f, indent=2)
    except Exception as e:
        logging.warning("write_status failed: %s", e)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # load / create config
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            cfg = {**DEFAULT_CONFIG, **json.load(f)}
    else:
        cfg = DEFAULT_CONFIG.copy()
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)

    logging.basicConfig(
        filename=cfg["log_file"],
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.info("=== FileTagger Daemon starting (PID %d) ===", os.getpid())
    logging.info("Watching: %s", cfg["watch_folders"])

    db = DaemonDB(cfg["db_path"])

    skip_dirs  = set(cfg["skip_dirs"])
    skip_names = set(n.lower() for n in cfg["skip_names"])

    # initial scan runs in background so watchdog starts immediately
    threading.Thread(
        target=initial_scan,
        args=(cfg["watch_folders"], db, skip_dirs, skip_names),
        daemon=True,
    ).start()

    # start watchdog observers
    handler   = WatchHandler(db, skip_dirs, skip_names)
    observers = []
    for folder in cfg["watch_folders"]:
        if not Path(folder).exists():
            logging.warning("Watch folder not found, skipping: %s", folder)
            continue
        obs = Observer()
        obs.schedule(handler, folder, recursive=True)
        obs.start()
        observers.append(obs)
        logging.info("Observer started: %s", folder)

    try:
        while True:
            write_status(cfg, db, observers)
            time.sleep(cfg.get("status_interval_s", 30))
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt — shutting down")
    finally:
        for obs in observers:
            obs.stop()
        for obs in observers:
            obs.join(timeout=3)
        logging.info("=== FileTagger Daemon stopped ===")


if __name__ == "__main__":
    main()
