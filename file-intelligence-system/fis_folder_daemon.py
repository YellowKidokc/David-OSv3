#!/usr/bin/env python3
"""
FIS Folder Tracker — independent daemon, runs alongside fis_daemon.py (file tracker).

What this does:
  - Watches every drive for new folders being created, moved, or deleted (real-time)
  - Crawls all drives slowly in the background, classifying every folder it finds
  - Writes a .fisnote manifest inside each folder it classifies (read-only for humans)
  - Updates the shared fis_catalog.db `folders` table so the file tracker can read
    folder roles when it classifies files

Naming schema (FOLDER):
    {class}_{topic}_{date-range}          ← suggested folder rename (not applied yet)
    .fisnote                              ← written inside each classified folder

  Classes: system / media / document / project / dump / archive
  Topic:   derived from dominant file type or existing folder name
  Date:    year-month range of files inside (e.g. 2024-2026)

Launch headless:
    pythonw fis_folder_daemon.py

Registered as a Windows startup task by INSTALL_STARTUP.bat.
Shares fis_catalog.db with fis_daemon.py via WAL mode — safe to run in parallel.
"""

import hashlib, json, logging, os, sqlite3, threading, time
from datetime import datetime
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    import sys; sys.exit("pip install watchdog")

try:
    from fis_classifier import classify_folder, FolderClass, ALLOWED_ACTIONS
    CLASSIFIER_AVAILABLE = True
except ImportError:
    CLASSIFIER_AVAILABLE = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FIS_DIR     = Path(__file__).resolve().parent
CONFIG_FILE = FIS_DIR / "fis_config.json"
DB_FILE     = FIS_DIR / "fis_catalog.db"
STATUS_FILE = FIS_DIR / "fis_folder_status.json"
LOG_FILE    = FIS_DIR / "fis_folder.log"

FISNOTE_FILENAME = ".fisnote"

# Folders that must NEVER receive a .fisnote write
NO_WRITE_DIRS = {
    "windows", "system32", "syswow64", "$recycle.bin",
    "programdata", "program files", "program files (x86)",
    "appdata", "system volume information", ".git", "__pycache__",
    "node_modules", ".venv", "venv",
}

DEFAULT_CONFIG = {
    "watch_folders":        ["D:\\DONT TOUCH BOOT UP"],
    "crawl_folders":        ["D:\\"],
    "auto_discover_drives": True,
    "skip_drives":          ["C:\\"],
    "skip_dirs": [
        ".git", "__pycache__", ".venv", "venv", "node_modules",
        ".obsidian", "Windows", "System Volume Information",
        "$Recycle.Bin", "AppData", "ProgramData",
    ],
    "crawl_sleep_ms":       50,
    "status_interval_s":    30,
    "write_fisnotes":       True,
    "fisnote_min_files":    2,
    "skip_system_write":    True,
}

# ---------------------------------------------------------------------------
# Folder ID (stable hash of the absolute path — changes on rename/move by design,
# but the DB record carries moved_from so we can re-link them)
# ---------------------------------------------------------------------------

def make_folder_id(path: str) -> str:
    h = hashlib.sha256(path.encode("utf-8", errors="replace")).hexdigest()[:8]
    return f"FLD-{datetime.now().strftime('%Y%m%d')}-{h}"

# ---------------------------------------------------------------------------
# .fisnote writer
# ---------------------------------------------------------------------------

def can_write_fisnote(folder_path: str, folder_class: str, dep_risk: float,
                      file_count: int, cfg: dict) -> bool:
    if not cfg.get("write_fisnotes", True):
        return False
    p = Path(folder_path)
    # never write to drive root
    if p.parent == p:
        return False
    # never write to known system dirs
    parts_lower = {part.lower() for part in p.parts}
    if parts_lower & NO_WRITE_DIRS:
        return False
    # skip tiny folders
    if file_count < cfg.get("fisnote_min_files", 2):
        return False
    # skip system folders when protection is on
    if cfg.get("skip_system_write", True) and folder_class == FolderClass.SYSTEM:
        return False
    if dep_risk > 0.5:
        return False
    return True


def write_fisnote(folder_path: str, result: dict):
    """Write or update the .fisnote manifest inside a folder."""
    p    = Path(folder_path)
    note = p / FISNOTE_FILENAME
    fc   = result.get("folder_class", "unknown")
    conf = result.get("confidence", 0.0)
    dep  = result.get("dependency_risk", 0.0)
    fam  = result.get("dominant_family", "mixed")
    rat  = result.get("dominant_ratio", 0.0)
    cnt  = result.get("file_count", 0)
    ts   = result.get("classified_at", datetime.now().isoformat(timespec="seconds"))
    acts = result.get("allowed_actions", [])
    fid  = result.get("folder_id", make_folder_id(folder_path))
    markers = result.get("system_markers_found", [])
    notes_list = result.get("notes", [])

    # derive topic slug from folder name
    topic = p.name.lower()
    topic = "".join(c if c.isalnum() or c in "-_" else "-" for c in topic).strip("-")

    # suggested rename (informational only — never applied automatically)
    suggested = f"{fc}_{topic}" if fc not in ("project", "unknown") else topic

    frontmatter = {
        "fis_schema":        "folder-index.v1",
        "folder_id":         fid,
        "folder":            str(p.relative_to(p.anchor)) if p.anchor else str(p),
        "folder_class":      fc,
        "confidence":        round(conf, 3),
        "dependency_risk":   round(dep, 3),
        "dominant_family":   fam,
        "dominant_ratio":    round(rat, 3),
        "file_count":        cnt,
        "classified_at":     ts,
        "allowed_actions":   acts,
        "suggested_name":    suggested,
    }
    if markers:
        frontmatter["system_markers"] = markers[:6]

    lines = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, list):
            lines.append(f'{k}: {json.dumps(v)}')
        elif isinstance(v, str):
            lines.append(f'{k}: "{v}"')
        else:
            lines.append(f'{k}: {v}')
    lines.append("---")
    lines.append("")
    lines.append(f"# FIS Folder Index: {p.name}")
    lines.append("")
    lines.append(f"**Class**: {fc}  ·  **Confidence**: {round(conf*100)}%  "
                 f"·  **Files**: {cnt}  ·  **Dominant**: {fam} ({round(rat*100)}%)")
    if notes_list:
        lines.append("")
        for n in notes_list:
            lines.append(f"> {n}")
    lines.append("")
    lines.append("## Allowed actions")
    if acts:
        for a in acts:
            lines.append(f"- {a}")
    else:
        lines.append("- index only")
    lines.append("")
    if fc == FolderClass.SYSTEM:
        lines.append("**PROTECTED** — no rename, move, or delete operations.")
    else:
        lines.append(f"**Suggested name**: `{suggested}`  (not applied — review before use)")
    lines.append("")
    lines.append("<!-- FIS folder-index.v1: parseable note; safe to regenerate. -->")
    lines.append("")

    try:
        note.write_text("\n".join(lines), encoding="utf-8")
    except OSError as e:
        logging.debug("fisnote write failed %s: %s", folder_path, e)


# ---------------------------------------------------------------------------
# Shared DB (same file as fis_daemon.py, WAL mode)
# ---------------------------------------------------------------------------

FOLDER_COLS = (
    "path","folder_id","folder_class","confidence","dependency_risk",
    "dominant_family","dominant_ratio","file_count","system_markers",
    "allowed_actions","notes","suggested_name","classified_at",
    "moved_from","moved_to","moved_at","deleted_at",
)

FOLDER_SCHEMA = """
CREATE TABLE IF NOT EXISTS folders (
    path              TEXT PRIMARY KEY,
    folder_id         TEXT,
    folder_class      TEXT,
    confidence        REAL,
    dependency_risk   REAL,
    dominant_family   TEXT,
    dominant_ratio    REAL,
    file_count        INTEGER,
    system_markers    TEXT,
    allowed_actions   TEXT,
    notes             TEXT,
    suggested_name    TEXT,
    classified_at     TEXT,
    moved_from        TEXT,
    moved_to          TEXT,
    moved_at          TEXT,
    deleted_at        TEXT
);
CREATE INDEX IF NOT EXISTS idx_fld_class  ON folders (folder_class);
CREATE INDEX IF NOT EXISTS idx_fld_dep    ON folders (dependency_risk);
CREATE INDEX IF NOT EXISTS idx_fld_ts     ON folders (classified_at);
"""

FOLDER_MIGRATE = [
    "ALTER TABLE folders ADD COLUMN folder_id      TEXT",
    "ALTER TABLE folders ADD COLUMN dominant_ratio REAL",
    "ALTER TABLE folders ADD COLUMN suggested_name TEXT",
    "ALTER TABLE folders ADD COLUMN moved_from     TEXT",
    "ALTER TABLE folders ADD COLUMN moved_to       TEXT",
    "ALTER TABLE folders ADD COLUMN moved_at       TEXT",
    "ALTER TABLE folders ADD COLUMN deleted_at     TEXT",
]


class FolderDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.lock    = threading.Lock()
        self._init()

    def _conn(self):
        c = sqlite3.connect(self.db_path, timeout=20)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        return c

    def _init(self):
        with self.lock:
            c = self._conn()
            c.executescript(FOLDER_SCHEMA)
            c.commit()
            for sql in FOLDER_MIGRATE:
                try: c.execute(sql); c.commit()
                except Exception: pass
            c.close()

    def upsert(self, rec: dict):
        vals = [rec.get(col) for col in FOLDER_COLS]
        sql  = (f"INSERT OR REPLACE INTO folders ({','.join(FOLDER_COLS)}) "
                f"VALUES ({','.join('?'*len(FOLDER_COLS))})")
        with self.lock:
            c = self._conn(); c.execute(sql, vals); c.commit(); c.close()

    def mark_deleted(self, path: str):
        with self.lock:
            c = self._conn()
            c.execute("UPDATE folders SET deleted_at=? WHERE path=?",
                      (datetime.now().isoformat(), path))
            c.commit(); c.close()

    def mark_moved(self, src: str, dest: str):
        with self.lock:
            c = self._conn()
            c.execute("UPDATE folders SET moved_to=?, moved_at=? WHERE path=?",
                      (dest, datetime.now().isoformat(), src))
            c.commit(); c.close()

    def get_classified_at(self, path: str):
        with self.lock:
            c   = self._conn()
            row = c.execute("SELECT classified_at FROM folders WHERE path=?", (path,)).fetchone()
            c.close()
        return row[0] if row else None

    def stats(self) -> dict:
        with self.lock:
            c = self._conn()
            try:
                total    = c.execute("SELECT COUNT(*) FROM folders").fetchone()[0]
                by_class = c.execute(
                    "SELECT folder_class, COUNT(*) FROM folders "
                    "WHERE deleted_at IS NULL GROUP BY folder_class"
                ).fetchall()
                recent   = c.execute(
                    "SELECT path, folder_class, classified_at FROM folders "
                    "ORDER BY classified_at DESC LIMIT 8"
                ).fetchall()
            except Exception:
                total = 0; by_class = []; recent = []
            c.close()
        return {
            "total":    total,
            "by_class": {r[0]: r[1] for r in by_class},
            "recent":   [{"path": r[0], "class": r[1], "at": r[2]} for r in recent],
        }


# ---------------------------------------------------------------------------
# Build a folder record from classifier output
# ---------------------------------------------------------------------------

def build_folder_record(path: str, result: dict) -> dict:
    fid = result.get("folder_id") or make_folder_id(path)
    return {
        "path":             path,
        "folder_id":        fid,
        "folder_class":     result.get("folder_class", "unknown"),
        "confidence":       result.get("confidence", 0.0),
        "dependency_risk":  result.get("dependency_risk", 0.0),
        "dominant_family":  result.get("dominant_family", "mixed"),
        "dominant_ratio":   result.get("dominant_ratio", 0.0),
        "file_count":       result.get("file_count", 0),
        "system_markers":   json.dumps(result.get("system_markers_found", [])),
        "allowed_actions":  json.dumps(result.get("allowed_actions", [])),
        "notes":            json.dumps(result.get("notes", [])),
        "suggested_name":   _suggested_name(path, result),
        "classified_at":    datetime.now().isoformat(timespec="seconds"),
        "moved_from":       None,
        "moved_to":         None,
        "moved_at":         None,
        "deleted_at":       None,
    }


def _suggested_name(path: str, result: dict) -> str:
    fc    = result.get("folder_class", "unknown")
    topic = Path(path).name.lower()
    topic = "".join(c if c.isalnum() or c in "-_" else "-" for c in topic).strip("-")
    if fc in ("project", "unknown"):
        return topic
    return f"{fc}_{topic}"


# ---------------------------------------------------------------------------
# Classify + write helper
# ---------------------------------------------------------------------------

def process_folder(path: str, db: FolderDB, cfg: dict):
    """Classify a folder, store in DB, write .fisnote if appropriate."""
    if not CLASSIFIER_AVAILABLE:
        return
    try:
        result = classify_folder(path)
    except Exception as e:
        logging.debug("classify_folder failed %s: %s", path, e)
        return

    rec = build_folder_record(path, result)
    db.upsert(rec)

    if can_write_fisnote(path, result.get("folder_class", ""),
                          result.get("dependency_risk", 1.0),
                          result.get("file_count", 0), cfg):
        result["folder_id"] = rec["folder_id"]
        result["classified_at"] = rec["classified_at"]
        write_fisnote(path, result)
        logging.debug("fisnote  %s (%s)", path, result.get("folder_class"))

    logging.info("FOLDER   %-10s conf=%.0f%%  %s",
                 result.get("folder_class","?"),
                 result.get("confidence",0)*100, path)


def should_skip_dir(path: str, skip_dirs: set) -> bool:
    return any(part in skip_dirs for part in Path(path).parts)


def get_crawl_drives(cfg: dict) -> list:
    """
    Same logic as the file tracker — returns the list of roots to walk this pass.
    Auto-discovers all available drives if auto_discover_drives is True.
    """
    import string
    skip = {d.upper().rstrip("\\") + "\\" for d in cfg.get("skip_drives", [])}

    if cfg.get("auto_discover_drives", False):
        drives = []
        for letter in string.ascii_uppercase:
            root = f"{letter}:\\"
            if root.upper() in skip:
                continue
            try:
                if os.path.exists(root):
                    drives.append(root)
            except OSError:
                pass
        for p in cfg.get("crawl_folders", []):
            if len(p) > 3 and p not in drives:
                drives.append(p)
        return drives
    else:
        return [p for p in cfg.get("crawl_folders", [])
                if p.upper().rstrip("\\") + "\\" not in skip]


# ---------------------------------------------------------------------------
# Real-time watcher for folder events
# ---------------------------------------------------------------------------

class FolderEventHandler(FileSystemEventHandler):
    def __init__(self, db: FolderDB, skip_dirs: set, cfg: dict):
        self.db        = db
        self.skip_dirs = skip_dirs
        self.cfg       = cfg
        self._debounce: dict = {}
        self._lk       = threading.Lock()

    def _debounced(self, path: str, window: float = 2.0) -> bool:
        t = time.time()
        with self._lk:
            if t - self._debounce.get(path, 0) < window:
                return False
            self._debounce[path] = t
        return True

    def on_created(self, event):
        if not event.is_directory: return
        if should_skip_dir(event.src_path, self.skip_dirs): return
        if not self._debounced(event.src_path): return
        logging.info("DIR NEW  %s", event.src_path)
        # brief delay so files inside it can settle
        time.sleep(2)
        try:
            process_folder(event.src_path, self.db, self.cfg)
        except Exception as e:
            logging.debug("on_created dir %s: %s", event.src_path, e)

    def on_deleted(self, event):
        if not event.is_directory: return
        path = str(Path(event.src_path).resolve())
        self.db.mark_deleted(path)
        logging.info("DIR DEL  %s", event.src_path)

    def on_moved(self, event):
        if not event.is_directory: return
        src  = str(Path(event.src_path).resolve())
        dest = str(Path(event.dest_path).resolve())
        self.db.mark_moved(src, dest)
        logging.info("DIR MOVE %s -> %s", src, dest)
        # re-classify at new location
        time.sleep(1)
        try:
            process_folder(dest, self.db, self.cfg)
        except Exception as e:
            logging.debug("on_moved dir %s: %s", dest, e)


# ---------------------------------------------------------------------------
# Background folder crawler
# ---------------------------------------------------------------------------

def folder_crawler(cfg: dict, db: FolderDB, stop_event: threading.Event):
    """
    Walks every available drive, classifying directories, forever.

    Pass structure:
      1. Detect all drives right now (auto or from config).
      2. Walk each drive top-to-bottom, classifying every folder.
         Skip folders classified within the last 24h unless something changed.
      3. After all drives done, rest 120s.
      4. Re-detect drives (new USB drives appear here).
      5. Repeat.

    Writes .fisnote inside qualifying folders (non-system, non-risky, ≥ 2 files).
    Runs at double the sleep of the file tracker to keep combined I/O impact low.
    """
    skip_dirs  = set(cfg["skip_dirs"])
    sleep_s    = cfg.get("crawl_sleep_ms", 50) / 1000.0
    reclassify_h = 24

    logging.info("Folder crawler started (sleep=%.0fms)", sleep_s*1000)

    pass_num = 0
    while not stop_event.is_set():
        pass_num += 1
        pass_new = pass_skip = 0

        drives = get_crawl_drives(cfg)
        if not drives:
            logging.warning("Folder crawler: no drives found, retrying in 120s")
            stop_event.wait(120)
            continue

        logging.info("=== Folder pass #%d — %d drive(s): %s ===",
                     pass_num, len(drives), ", ".join(drives))

        for drive in drives:
            if stop_event.is_set():
                return
            if not Path(drive).exists():
                logging.info("Folder crawler: drive %s not available", drive)
                continue

            drive_new = drive_skip = 0
            logging.info("Folder crawler → drive %s", drive)

            for dirpath, dirnames, _ in os.walk(drive, onerror=lambda e: None):
                if stop_event.is_set():
                    return

                dirnames[:] = [d for d in dirnames
                                if d not in skip_dirs
                                and d.lower() != ".fis"]

                abs_path = str(Path(dirpath).resolve())

                last = db.get_classified_at(abs_path)
                if last:
                    try:
                        age_h = (datetime.now() - datetime.fromisoformat(last)).total_seconds() / 3600
                        if age_h < reclassify_h:
                            drive_skip += 1
                            time.sleep(sleep_s)
                            continue
                    except Exception:
                        pass

                try:
                    process_folder(abs_path, db, cfg)
                    drive_new += 1
                except Exception as e:
                    logging.debug("folder crawler dir %s: %s", abs_path, e)

                time.sleep(sleep_s)

            logging.info("Folder crawler ✓ drive %s — %d classified, %d skipped",
                         drive, drive_new, drive_skip)
            pass_new  += drive_new
            pass_skip += drive_skip

        logging.info(
            "=== Folder pass #%d complete — %d classified, %d skipped — resting 120s ===",
            pass_num, pass_new, pass_skip
        )
        stop_event.wait(120)


# ---------------------------------------------------------------------------
# Status writer
# ---------------------------------------------------------------------------

def status_writer(cfg: dict, db: FolderDB, stop_event: threading.Event,
                  observers: list, start_ts: float):
    interval = cfg.get("status_interval_s", 30)
    while not stop_event.is_set():
        s = db.stats()
        payload = {
            "running":         True,
            "daemon":          "folder_tracker",
            "pid":             os.getpid(),
            "started_at":      datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "uptime_s":        round(time.time() - start_ts),
            "classifier":      CLASSIFIER_AVAILABLE,
            "write_fisnotes":  cfg.get("write_fisnotes", True),
            "watch_folders":   cfg["watch_folders"],
            "crawl_folders":   cfg["crawl_folders"],
            "observers_alive": sum(1 for o in observers if o.is_alive()),
            **s,
        }
        try:
            STATUS_FILE.write_text(json.dumps(payload, indent=2))
        except Exception as e:
            logging.warning("status write failed: %s", e)
        stop_event.wait(interval)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    start_ts = time.time()

    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            cfg = {**DEFAULT_CONFIG, **json.load(f)}
    else:
        cfg = DEFAULT_CONFIG.copy()

    logging.basicConfig(
        filename=str(LOG_FILE),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.info("=== FIS Folder Tracker starting (PID %d) ===", os.getpid())
    logging.info("Watch: %s", cfg["watch_folders"])
    logging.info("Crawl: %s", cfg["crawl_folders"])
    logging.info("Write .fisnotes: %s", cfg.get("write_fisnotes", True))

    db         = FolderDB(str(DB_FILE))
    stop_event = threading.Event()
    skip_dirs  = set(cfg["skip_dirs"])

    # --- watchdog observers (real-time directory events) ---
    handler   = FolderEventHandler(db, skip_dirs, cfg)
    observers = []
    for folder in cfg["watch_folders"]:
        if not Path(folder).exists():
            logging.warning("Watch folder missing: %s", folder)
            continue
        obs = Observer()
        obs.schedule(handler, folder, recursive=True)
        obs.start()
        observers.append(obs)
        logging.info("Watching dirs: %s", folder)

    # --- background threads ---
    threads = [
        threading.Thread(target=folder_crawler, args=(cfg, db, stop_event),
                         name="FolderCrawler", daemon=True),
        threading.Thread(target=status_writer,
                         args=(cfg, db, stop_event, observers, start_ts),
                         name="FolderStatusWriter", daemon=True),
    ]
    for t in threads:
        t.start()

    logging.info("FIS Folder Tracker fully started.")

    try:
        while True:
            time.sleep(5)
            for obs in observers:
                if not obs.is_alive():
                    logging.warning("Observer died, restarting…")
                    try: obs.start()
                    except Exception as e: logging.error("restart failed: %s", e)
    except KeyboardInterrupt:
        logging.info("Shutting down…")
    finally:
        stop_event.set()
        for obs in observers: obs.stop()
        for obs in observers: obs.join(timeout=3)
        logging.info("=== FIS Folder Tracker stopped ===")


if __name__ == "__main__":
    main()
