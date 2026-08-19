#!/usr/bin/env python3
"""
FIS — File Intelligence System daemon.

Three parallel systems running forever:

  1. WATCHER    — watchdog OS-level events (instant: create/modify/delete/move)
  2. CRAWLER    — slow background walk of all configured drives (low CPU)
  3. RECONCILER — periodic MD5 cross-reference to catch moves/deletes the
                   watcher missed (external drives, network shares, bulk ops)

Classification layer (fis_classifier.py):

  FOLDER PASS — detects folder role (system/media/document/project/dump/archive)
               before touching any files inside; folder role gates allowed actions.
  FILE PASS   — scores each file against the 12-variable master equation
               (G M E S T K R Q F C + Domain + Law, each 1-3).
  AI FALLBACK — files with confidence < threshold are queued for Claude API call.

Launch headless (no window):
    pythonw fis_daemon.py

Status file (fis_status.json) is written every 30s.
"""

import hashlib, json, logging, os, sqlite3, sys, threading, time
from datetime import datetime
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    sys.exit("pip install watchdog")

try:
    from fis_classifier import classify_folder, classify_file, FolderClass, FALLBACK_THRESHOLD
    CLASSIFIER_AVAILABLE = True
except ImportError:
    pass  # handled below

try:
    from fis_namer import run_auto_approve
    NAMER_AVAILABLE = True
except ImportError:
    NAMER_AVAILABLE = False

try:
    from fis_classifier import classify_folder, classify_file, FolderClass, FALLBACK_THRESHOLD
    CLASSIFIER_AVAILABLE = True
except ImportError:
    CLASSIFIER_AVAILABLE = False
    logging.warning("fis_classifier.py not found — classification disabled")

# ---------------------------------------------------------------------------
# Paths & defaults
# ---------------------------------------------------------------------------

FIS_DIR     = Path(__file__).resolve().parent
CONFIG_FILE = FIS_DIR / "fis_config.json"
DB_FILE     = FIS_DIR / "fis_catalog.db"
STATUS_FILE = FIS_DIR / "fis_status.json"
LOG_FILE    = FIS_DIR / "fis.log"

DEFAULT_CONFIG = {
    "watch_folders":       ["D:\\DONT TOUCH BOOT UP"],
    # crawl_folders is used when auto_discover_drives is false
    "crawl_folders":       ["D:\\"],
    # if true: ignores crawl_folders and auto-detects all drives every pass
    "auto_discover_drives": True,
    # drives to always skip even when auto-discovering (e.g. system drive)
    "skip_drives":         ["C:\\"],
    "skip_dirs": [
        ".git", "__pycache__", ".venv", "venv", "node_modules",
        ".obsidian", "Windows", "System Volume Information",
        "$Recycle.Bin", "AppData", "ProgramData", ".fis",
    ],
    "skip_names":           ["thumbs.db", "desktop.ini", ".ds_store"],
    "skip_exts":            [".chi", ".fisnote"],
    "crawl_sleep_ms":       25,
    "reconcile_interval_s": 600,
    "status_interval_s":    30,
    "classify":             True,
    "ai_fallback":          False,
    # approval queue notifications
    "notify_threshold":     100,    # pop up when this many items are pending
    "notify_interval_min":  30,     # re-notify every N minutes if still pending
    "notify_snooze_max":    3,      # after this many ignores, shorten interval to 10 min
}

TEXT_EXTS = {
    ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx", ".css", ".html",
    ".htm", ".json", ".yaml", ".yml", ".xml", ".ini", ".cfg", ".bat",
    ".ps1", ".sh", ".sql", ".csv", ".log", ".rst", ".ahk", ".ahk2",
    ".toml", ".env", ".gitignore", ".editorconfig",
}

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def quick_md5(path: str, size: int) -> str:
    h = hashlib.md5(str(size).encode())
    try:
        with open(path, "rb") as fh:
            h.update(fh.read(65536))
            if size > 131072:
                fh.seek(-65536, os.SEEK_END)
                h.update(fh.read(65536))
    except OSError:
        pass
    return h.hexdigest()


def build_record(path: str) -> dict:
    p   = Path(path)
    st  = p.stat()
    ext = p.suffix.lower()
    sz  = st.st_size
    return {
        "path":             str(p.resolve()),
        "name":             p.name,
        "ext":              ext,
        "size":             sz,
        "md5":              quick_md5(path, sz),
        "created":          datetime.fromtimestamp(st.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
        "modified":         datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "mtime":            st.st_mtime,
        "tier":             "text" if ext in TEXT_EXTS else "blob",
        "scanned":          now_str(),
        "status":           "active",
        "moved_from":       None,
        "moved_to":         None,
        "moved_at":         None,
        "deleted_at":       None,
        # classification fields (populated by apply_classification)
        "folder_class":     None,
        "folder_confidence": None,
        "chi_json":         None,
        "chi_sum":          None,
        "dominant_chi":     None,
        "chi_domain":       None,
        "chi_law":          None,
        "chi_confidence":   None,
        "file_role":        None,
        "classified_at":    None,
        "needs_review":     0,
    }


def apply_classification(rec: dict, folder_class: str = "", folder_confidence: float = 0.0) -> dict:
    """
    Apply all 5 non-negotiable tags + full CHI vector to a file record.
    Called on every create, modify, and move — never skipped.
    """
    if not CLASSIFIER_AVAILABLE:
        return rec
    try:
        result = classify_file(rec["path"], folder_class=folder_class)
        rec["folder_class"]      = folder_class or "unknown"
        rec["folder_confidence"] = round(folder_confidence, 3)
        rec["chi_json"]          = json.dumps(result["chi"])
        rec["chi_sum"]           = result["chi_sum"]
        rec["dominant_chi"]      = result["chi_factor"]          # tag 2
        rec["chi_domain"]        = result["domain"]["name"]      # tag 1
        rec["chi_law"]           = result["law"]["name"]         # tag 3
        rec["chi_confidence"]    = result["confidence"]
        rec["content_type"]      = result["content_type"]        # tag 4
        rec["evidence"]          = result["evidence"]            # tag 5
        rec["fruit"]             = result.get("fruit", 0.0)
        rec["anti_fruit"]        = result.get("anti_fruit", 0.0)
        rec["file_role"]         = result["file_role"]
        rec["classified_at"]     = now_str()
        rec["needs_review"]      = 1 if result.get("needs_ai_fallback") else 0
    except Exception as e:
        logging.debug("classify_file failed for %s: %s", rec["path"], e)
    return rec


def get_crawl_drives(cfg: dict) -> list:
    """
    Returns the list of root paths to crawl this pass.

    If auto_discover_drives is True:
      - Checks every drive letter A-Z to see which ones actually exist
      - Removes any drives in skip_drives
      - Merges with crawl_folders (explicit additions like network paths)
    If False:
      - Returns crawl_folders exactly as configured

    Re-called at the start of every crawl pass so newly attached drives
    (USB, external HDDs) are picked up automatically.
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
        # also include any explicit non-drive-root paths in crawl_folders
        for p in cfg.get("crawl_folders", []):
            if len(p) > 3 and p not in drives:   # not a bare drive root
                drives.append(p)
        return drives
    else:
        return [p for p in cfg.get("crawl_folders", [])
                if p.upper().rstrip("\\") + "\\" not in skip]


def should_skip(path: str, skip_dirs: set, skip_names: set, skip_exts: set = frozenset()) -> bool:
    p = Path(path)
    if p.name.lower() in skip_names:
        return True
    if skip_exts and p.suffix.lower() in skip_exts:
        return True  # never crawl .chi or .fisnote sidecars
    return any(part in skip_dirs for part in p.parts)


# ---------------------------------------------------------------------------
# Folder classification cache
# ---------------------------------------------------------------------------

class FolderCache:
    """
    Thread-safe cache of folder classifications.
    Avoids re-classifying the same folder for every file inside it.
    TTL defaults to 300s — enough for a full crawler pass through a large folder.
    """

    def __init__(self, ttl_s: int = 300):
        self._cache: dict[str, tuple] = {}  # path -> (folder_class, confidence, ts)
        self._lock  = threading.Lock()
        self._ttl   = ttl_s
        self._stats = {"hits": 0, "misses": 0}

    def get(self, folder_path: str) -> tuple[str, float]:
        """Return (folder_class, confidence). Classifies on miss."""
        with self._lock:
            if folder_path in self._cache:
                fc, conf, ts = self._cache[folder_path]
                if time.time() - ts < self._ttl:
                    self._stats["hits"] += 1
                    return fc, conf
        # cache miss or stale
        self._stats["misses"] += 1
        try:
            result = classify_folder(folder_path)
            fc   = result.get("folder_class", "project")
            conf = result.get("confidence", 0.5)
        except Exception as e:
            logging.debug("classify_folder failed for %s: %s", folder_path, e)
            fc, conf = "project", 0.3
        with self._lock:
            self._cache[folder_path] = (fc, conf, time.time())
        return fc, conf

    def invalidate(self, folder_path: str):
        with self._lock:
            self._cache.pop(folder_path, None)

    @property
    def stats(self) -> dict:
        with self._lock:
            return dict(self._stats)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    path              TEXT PRIMARY KEY,
    name              TEXT,
    ext               TEXT,
    size              INTEGER,
    md5               TEXT,
    created           TEXT,
    modified          TEXT,
    mtime             REAL,
    tier              TEXT,
    scanned           TEXT,
    status            TEXT DEFAULT 'active',
    moved_from        TEXT,
    moved_to          TEXT,
    moved_at          TEXT,
    deleted_at        TEXT,
    -- classification layer (5 non-negotiable tags + full CHI vector)
    folder_class      TEXT,
    folder_confidence REAL,
    chi_json          TEXT,
    chi_sum           INTEGER,
    dominant_chi      TEXT,
    chi_domain        TEXT,
    chi_law           TEXT,
    chi_confidence    REAL,
    content_type      TEXT,
    evidence          REAL,
    fruit             REAL,
    anti_fruit        REAL,
    file_role         TEXT,
    classified_at     TEXT,
    needs_review      INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS folders (
    path              TEXT PRIMARY KEY,
    folder_class      TEXT,
    confidence        REAL,
    dependency_risk   REAL,
    dominant_family   TEXT,
    file_count        INTEGER,
    system_markers    TEXT,
    allowed_actions   TEXT,
    notes             TEXT,
    classified_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_md5          ON files (md5);
CREATE INDEX IF NOT EXISTS idx_status       ON files (status);
CREATE INDEX IF NOT EXISTS idx_ext          ON files (ext);
CREATE INDEX IF NOT EXISTS idx_mtime        ON files (mtime);
CREATE INDEX IF NOT EXISTS idx_folder_class ON files (folder_class);
CREATE INDEX IF NOT EXISTS idx_chi_domain   ON files (chi_domain);
CREATE INDEX IF NOT EXISTS idx_needs_review ON files (needs_review);
"""

# Columns that might not exist in old databases
MIGRATE = [
    "ALTER TABLE files ADD COLUMN moved_from        TEXT",
    "ALTER TABLE files ADD COLUMN moved_to          TEXT",
    "ALTER TABLE files ADD COLUMN moved_at          TEXT",
    "ALTER TABLE files ADD COLUMN deleted_at        TEXT",
    "ALTER TABLE files ADD COLUMN folder_class      TEXT",
    "ALTER TABLE files ADD COLUMN folder_confidence REAL",
    "ALTER TABLE files ADD COLUMN chi_json          TEXT",
    "ALTER TABLE files ADD COLUMN chi_sum           INTEGER",
    "ALTER TABLE files ADD COLUMN dominant_chi      TEXT",
    "ALTER TABLE files ADD COLUMN chi_domain        TEXT",
    "ALTER TABLE files ADD COLUMN chi_law           TEXT",
    "ALTER TABLE files ADD COLUMN chi_confidence    REAL",
    "ALTER TABLE files ADD COLUMN content_type      TEXT",
    "ALTER TABLE files ADD COLUMN evidence          REAL",
    "ALTER TABLE files ADD COLUMN fruit             REAL",
    "ALTER TABLE files ADD COLUMN anti_fruit        REAL",
    "ALTER TABLE files ADD COLUMN file_role         TEXT",
    "ALTER TABLE files ADD COLUMN classified_at     TEXT",
    "ALTER TABLE files ADD COLUMN needs_review      INTEGER DEFAULT 0",
]

COLS = (
    "path","name","ext","size","md5","created","modified","mtime",
    "tier","scanned","status","moved_from","moved_to","moved_at","deleted_at",
    # 5 non-negotiable tags + full CHI vector
    "folder_class","folder_confidence","chi_json","chi_sum","dominant_chi",
    "chi_domain","chi_law","chi_confidence",
    "content_type","evidence","fruit","anti_fruit",
    "file_role","classified_at","needs_review",
)

FOLDER_COLS = (
    "path","folder_class","confidence","dependency_risk","dominant_family",
    "file_count","system_markers","allowed_actions","notes","classified_at",
)


class FisDB:
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
            c.executescript(SCHEMA)
            c.commit()
            for sql in MIGRATE:
                try:
                    c.execute(sql); c.commit()
                except Exception:
                    pass
            c.close()

    def upsert(self, rec: dict):
        vals = [rec.get(col) for col in COLS]
        sql  = (f"INSERT OR REPLACE INTO files ({','.join(COLS)}) "
                f"VALUES ({','.join('?'*len(COLS))})")
        with self.lock:
            c = self._conn()
            c.execute(sql, vals)
            c.commit()
            c.close()

    def upsert_folder(self, result: dict):
        """Store a folder classification result."""
        rec = {
            "path":             result.get("path", ""),
            "folder_class":     result.get("folder_class", "project"),
            "confidence":       result.get("confidence", 0.0),
            "dependency_risk":  result.get("dependency_risk", 0.0),
            "dominant_family":  result.get("dominant_family", ""),
            "file_count":       result.get("file_count", 0),
            "system_markers":   json.dumps(result.get("system_markers_found", [])),
            "allowed_actions":  json.dumps(result.get("allowed_actions", [])),
            "notes":            json.dumps(result.get("notes", [])),
            "classified_at":    now_str(),
        }
        vals = [rec.get(col) for col in FOLDER_COLS]
        sql  = (f"INSERT OR REPLACE INTO folders ({','.join(FOLDER_COLS)}) "
                f"VALUES ({','.join('?'*len(FOLDER_COLS))})")
        with self.lock:
            c = self._conn()
            c.execute(sql, vals)
            c.commit()
            c.close()

    def mark_deleted(self, path: str):
        with self.lock:
            c = self._conn()
            c.execute("UPDATE files SET status='deleted', deleted_at=? WHERE path=?",
                      (now_str(), path))
            c.commit()
            c.close()

    def mark_moved(self, src: str, dest: str):
        with self.lock:
            c = self._conn()
            c.execute("UPDATE files SET status='moved', moved_to=?, moved_at=? WHERE path=?",
                      (dest, now_str(), src))
            c.commit()
            c.close()

    def get_mtime(self, path: str):
        with self.lock:
            c   = self._conn()
            row = c.execute("SELECT mtime FROM files WHERE path=?", (path,)).fetchone()
            c.close()
        return row[0] if row else None

    def active_mtimes(self) -> dict:
        with self.lock:
            c    = self._conn()
            rows = c.execute("SELECT path, mtime FROM files WHERE status='active'").fetchall()
            c.close()
        return {r[0]: r[1] for r in rows}

    def find_by_md5(self, md5: str) -> list:
        with self.lock:
            c    = self._conn()
            rows = c.execute(
                "SELECT path FROM files WHERE md5=? AND status='active'", (md5,)
            ).fetchall()
            c.close()
        return [r[0] for r in rows]

    def stale_actives(self) -> list:
        """Return active records whose path no longer exists on disk."""
        with self.lock:
            c    = self._conn()
            rows = c.execute(
                "SELECT path, md5 FROM files WHERE status='active'"
            ).fetchall()
            c.close()
        return [(path, md5) for path, md5 in rows if not Path(path).exists()]

    def stats(self) -> dict:
        with self.lock:
            c = self._conn()
            try:
                total        = c.execute("SELECT COUNT(*) FROM files").fetchone()[0]
                active       = c.execute("SELECT COUNT(*) FROM files WHERE status='active'").fetchone()[0]
                deleted      = c.execute("SELECT COUNT(*) FROM files WHERE status='deleted'").fetchone()[0]
                moved        = c.execute("SELECT COUNT(*) FROM files WHERE status='moved'").fetchone()[0]
                classified   = c.execute("SELECT COUNT(*) FROM files WHERE classified_at IS NOT NULL").fetchone()[0]
                needs_review = c.execute("SELECT COUNT(*) FROM files WHERE needs_review=1 AND status='active'").fetchone()[0]
                # top CHI domains
                domain_rows  = c.execute(
                    "SELECT chi_domain, COUNT(*) as n FROM files "
                    "WHERE chi_domain IS NOT NULL AND status='active' "
                    "GROUP BY chi_domain ORDER BY n DESC LIMIT 5"
                ).fetchall()
                # top folder classes
                fclass_rows  = c.execute(
                    "SELECT folder_class, COUNT(*) as n FROM files "
                    "WHERE folder_class IS NOT NULL AND status='active' "
                    "GROUP BY folder_class ORDER BY n DESC"
                ).fetchall()
                recent       = c.execute(
                    "SELECT path, status, scanned FROM files ORDER BY scanned DESC LIMIT 8"
                ).fetchall()
            except Exception:
                total = active = deleted = moved = classified = needs_review = 0
                domain_rows = fclass_rows = recent = []
            c.close()
        return {
            "total":        total,
            "active":       active,
            "deleted":      deleted,
            "moved":        moved,
            "classified":   classified,
            "needs_review": needs_review,
            "top_domains":  {r[0]: r[1] for r in domain_rows},
            "folder_classes": {r[0]: r[1] for r in fclass_rows},
            "recent":       [{"path": r[0], "status": r[1], "scanned": r[2]} for r in recent],
        }


# ---------------------------------------------------------------------------
# Real-time watcher (watchdog)
# ---------------------------------------------------------------------------

class FisEventHandler(FileSystemEventHandler):
    def __init__(self, db: FisDB, skip_dirs: set, skip_names: set, skip_exts: set = frozenset(),
                 classify: bool = False, folder_cache: "FolderCache | None" = None):
        self.db           = db
        self.skip_dirs    = skip_dirs
        self.skip_names   = skip_names
        self.skip_exts    = skip_exts
        self.classify     = classify
        self.folder_cache = folder_cache
        self._debounce: dict = {}
        self._lk          = threading.Lock()

    def _debounced(self, path: str, window: float = 1.5) -> bool:
        t = time.time()
        with self._lk:
            if t - self._debounce.get(path, 0) < window:
                return False
            self._debounce[path] = t
        return True

    def _process(self, path: str):
        rec = build_record(path)
        if self.classify and CLASSIFIER_AVAILABLE and self.folder_cache:
            folder = str(Path(path).parent)
            fc, conf = self.folder_cache.get(folder)
            apply_classification(rec, fc, conf)
        self.db.upsert(rec)

    def on_created(self, event):
        if event.is_directory: return
        if should_skip(event.src_path, self.skip_dirs, self.skip_names, self.skip_exts): return
        if not self._debounced(event.src_path): return
        try:
            self._process(event.src_path)
            logging.info("NEW      %s", event.src_path)
        except Exception as e:
            logging.debug("on_created %s: %s", event.src_path, e)

    def on_modified(self, event):
        if event.is_directory: return
        if should_skip(event.src_path, self.skip_dirs, self.skip_names, self.skip_exts): return
        if not self._debounced(event.src_path): return
        try:
            self._process(event.src_path)
            logging.info("MODIFIED %s", event.src_path)
        except Exception as e:
            logging.debug("on_modified %s: %s", event.src_path, e)

    def on_deleted(self, event):
        if event.is_directory: return
        if should_skip(event.src_path, self.skip_dirs, self.skip_names, self.skip_exts): return
        path = str(Path(event.src_path).resolve())
        self.db.mark_deleted(path)
        logging.info("DELETED  %s", event.src_path)

    def on_moved(self, event):
        if event.is_directory:
            if self.folder_cache:
                self.folder_cache.invalidate(str(Path(event.src_path).resolve()))
            return
        src  = str(Path(event.src_path).resolve())
        dest = str(Path(event.dest_path).resolve())
        self.db.mark_moved(src, dest)
        try:
            rec = build_record(event.dest_path)
            rec["moved_from"] = src
            if self.classify and CLASSIFIER_AVAILABLE and self.folder_cache:
                folder = str(Path(event.dest_path).parent)
                fc, conf = self.folder_cache.get(folder)
                apply_classification(rec, fc, conf)
            self.db.upsert(rec)
            logging.info("MOVED    %s  ->  %s", src, dest)
        except Exception as e:
            logging.debug("on_moved %s->%s: %s", src, dest, e)


# ---------------------------------------------------------------------------
# Background crawler (slow continuous scan of all drives)
# ---------------------------------------------------------------------------

def background_crawler(cfg: dict, db: FisDB, stop_event: threading.Event,
                       folder_cache: "FolderCache | None"):
    """
    Trickles through every available drive, one file at a time, forever.

    Pass structure:
      1. Detect all drives that exist right now (auto or from config).
      2. Walk each drive completely before moving to the next.
      3. After all drives are done, rest 60s.
      4. Re-detect drives (catches newly attached USB/external drives).
      5. Repeat.

    Skips files whose mtime hasn't changed since last scan — only hashes
    and classifies new or modified files, so subsequent passes are very fast
    on drives where nothing changed.
    """
    skip_dirs   = set(cfg["skip_dirs"])
    skip_names  = set(n.lower() for n in cfg["skip_names"])
    sleep_s     = cfg.get("crawl_sleep_ms", 25) / 1000.0
    do_classify = cfg.get("classify", True) and CLASSIFIER_AVAILABLE

    logging.info("Crawler started (sleep=%.0fms, classify=%s)", sleep_s * 1000, do_classify)

    pass_num = 0
    while not stop_event.is_set():
        pass_num  += 1
        pass_total = pass_new = pass_skip = 0

        # ── detect drives for this pass ──────────────────────────────────────
        drives = get_crawl_drives(cfg)
        if not drives:
            logging.warning("Crawler: no drives found, retrying in 60s")
            stop_event.wait(60)
            continue

        logging.info("=== Crawl pass #%d — %d drive(s): %s ===",
                     pass_num, len(drives), ", ".join(drives))

        # ── walk each drive in turn ──────────────────────────────────────────
        for drive in drives:
            if stop_event.is_set():
                return
            if not Path(drive).exists():
                logging.info("Crawler: drive %s not available, skipping", drive)
                continue

            drive_new = drive_skip = 0
            logging.info("Crawler → starting drive %s", drive)

            for dirpath, dirnames, filenames in os.walk(drive, onerror=lambda e: None):
                if stop_event.is_set():
                    return

                dirnames[:] = [d for d in dirnames if d not in skip_dirs]

                # get folder class once per directory
                folder_class = "project"
                folder_conf  = 0.5
                if do_classify and folder_cache:
                    try:
                        folder_class, folder_conf = folder_cache.get(dirpath)
                    except Exception:
                        pass

                for fname in filenames:
                    if stop_event.is_set():
                        return
                    if fname.lower() in skip_names:
                        continue

                    full = os.path.join(dirpath, fname)
                    try:
                        mt = os.path.getmtime(full)
                    except OSError:
                        continue

                    abs_path  = str(Path(full).resolve())
                    cached_mt = db.get_mtime(abs_path)

                    if cached_mt is not None and abs(cached_mt - mt) < 1e-6:
                        drive_skip += 1
                    else:
                        try:
                            rec = build_record(full)
                            if do_classify:
                                apply_classification(rec, folder_class, folder_conf)
                            db.upsert(rec)
                            drive_new += 1
                        except Exception as e:
                            logging.debug("crawler skip %s: %s", full, e)

                    time.sleep(sleep_s)

            logging.info("Crawler ✓ drive %s done — %d new/changed, %d unchanged",
                         drive, drive_new, drive_skip)
            pass_new  += drive_new
            pass_skip += drive_skip
            pass_total += drive_new + drive_skip

        # ── pass complete ─────────────────────────────────────────────────────
        logging.info(
            "=== Pass #%d complete — %d files total, %d new/changed, %d unchanged ===",
            pass_num, pass_total, pass_new, pass_skip
        )
        if folder_cache:
            cs = folder_cache.stats
            logging.debug("FolderCache: hits=%d misses=%d", cs["hits"], cs["misses"])

        # ── auto-approve naming on first pass (and whenever new files appear) ──
        if NAMER_AVAILABLE and do_classify and pass_new > 0:
            try:
                counts = run_auto_approve(str(DB_FILE))
                logging.info(
                    "AutoApprove — approved=%d queued=%d skipped=%d",
                    counts["auto_approved"], counts["queued"], counts["skipped"]
                )
            except Exception as e:
                logging.warning("AutoApprove failed: %s", e)

        stop_event.wait(60)


# ---------------------------------------------------------------------------
# Reconciler (MD5-based move / stale delete detection)
# ---------------------------------------------------------------------------

def reconciler(cfg: dict, db: FisDB, stop_event: threading.Event):
    interval = cfg.get("reconcile_interval_s", 600)
    logging.info("Reconciler started (interval=%ds)", interval)

    while not stop_event.is_set():
        stop_event.wait(interval)
        if stop_event.is_set():
            break

        stale = db.stale_actives()
        if not stale:
            continue

        logging.info("Reconciler: %d stale actives to check", len(stale))
        moved = deleted = 0

        for path, md5 in stale:
            if Path(path).exists():
                continue
            matches = db.find_by_md5(md5)
            matches = [m for m in matches if m != path and Path(m).exists()]
            if matches:
                dest = matches[0]
                db.mark_moved(path, dest)
                moved += 1
                logging.info("RECONCILE MOVE  %s  ->  %s", path, dest)
            else:
                db.mark_deleted(path)
                deleted += 1
                logging.info("RECONCILE DELETE %s", path)

        logging.info("Reconciler done: %d moved, %d deleted", moved, deleted)


# ---------------------------------------------------------------------------
# AI review queue (processes files marked needs_review=1)
# ---------------------------------------------------------------------------

def ai_review_worker(cfg: dict, db: FisDB, stop_event: threading.Event):
    """
    Checks every 5 minutes for files with needs_review=1.
    Calls Claude API (if ANTHROPIC_API_KEY set) to classify them.
    Only runs if cfg["ai_fallback"] is True.
    """
    if not cfg.get("ai_fallback") or not CLASSIFIER_AVAILABLE:
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        logging.info("AI review worker: no ANTHROPIC_API_KEY, skipping")
        return

    from fis_classifier import ai_classify, _read_sample

    logging.info("AI review worker started")
    while not stop_event.is_set():
        stop_event.wait(300)  # check every 5 min
        if stop_event.is_set():
            break
        try:
            with db.lock:
                c    = db._conn()
                rows = c.execute(
                    "SELECT path, folder_class, chi_json, chi_sum, dominant_chi, "
                    "chi_domain, chi_law, chi_confidence, file_role "
                    "FROM files WHERE needs_review=1 AND status='active' LIMIT 20"
                ).fetchall()
                c.close()
            for row in rows:
                if stop_event.is_set():
                    break
                path = row[0]
                if not Path(path).exists():
                    continue
                local = {
                    "chi":           json.loads(row[2] or "{}"),
                    "chi_sum":       row[3] or 0,
                    "dominant_chi":  row[4] or "none",
                    "domain":        {"name": row[5] or "unknown", "score": 0},
                    "law":           {"name": row[6] or "none",    "score": 0},
                    "chi_confidence": row[7] or 0.0,
                    "file_role":     row[8] or "unknown",
                    "needs_ai_fallback": True,
                }
                sample = _read_sample(path)
                result = ai_classify(path, sample, local)
                if "ai_domain" in result:
                    with db.lock:
                        c = db._conn()
                        c.execute(
                            "UPDATE files SET chi_domain=?, file_role=?, "
                            "chi_confidence=?, needs_review=0, classified_at=? "
                            "WHERE path=?",
                            (result.get("ai_domain", row[5]),
                             result.get("ai_role", row[8]),
                             result.get("ai_confidence", row[7]),
                             now_str(), path)
                        )
                        c.commit()
                        c.close()
                    logging.info("AI classified: %s → %s", path, result.get("ai_role"))
                time.sleep(1)  # rate limit
        except Exception as e:
            logging.error("AI review worker error: %s", e)


# ---------------------------------------------------------------------------
# Approval queue notifications
# ---------------------------------------------------------------------------

import subprocess as _sp

class ApprovalNotifier:
    """
    Fires a Windows toast when the pending approval count crosses notify_threshold.
    Re-fires every notify_interval_min if still pending.
    After notify_snooze_max ignores, interval shrinks to 10 min so it gets persistent.
    """
    def __init__(self, cfg: dict):
        self.threshold   = cfg.get("notify_threshold",   100)
        self.interval    = cfg.get("notify_interval_min", 30) * 60   # seconds
        self.snooze_max  = cfg.get("notify_snooze_max",   3)
        self._last_fired = 0.0
        self._snoozes    = 0

    def check(self, pending_count: int):
        if pending_count < self.threshold:
            self._snoozes = 0   # reset when queue drains below threshold
            return
        now = time.time()
        interval = 600 if self._snoozes >= self.snooze_max else self.interval
        if now - self._last_fired < interval:
            return
        self._last_fired = now
        self._snoozes   += 1
        self._toast(pending_count)

    def _toast(self, count: int):
        title = "FIS · Approval Queue"
        msg   = (f"{count:,} files are waiting for your naming approval.\n"
                 "Open the FIS workbench to review.")
        notifier = FIS_DIR / "approval-gui" / "notify.ps1"
        if not notifier.exists():
            logging.warning("approval notifier missing: %s", notifier)
            return
        try:
            _sp.Popen(
                [
                    "powershell",
                    "-ExecutionPolicy", "Bypass",
                    "-WindowStyle", "Hidden",
                    "-File", str(notifier),
                    "-Count", str(count),
                ],
                stdout=_sp.DEVNULL, stderr=_sp.DEVNULL
            )
            logging.info("NOTIFY  pending=%d snooze=%d", count, self._snoozes)
        except Exception as e:
            logging.warning("toast failed: %s", e)


# ---------------------------------------------------------------------------
# Status writer
# ---------------------------------------------------------------------------

def status_writer(cfg: dict, db: FisDB, stop_event: threading.Event,
                  observers: list, start_ts: float):
    interval = cfg.get("status_interval_s", 30)
    notifier = ApprovalNotifier(cfg)
    while not stop_event.is_set():
        s = db.stats()
        payload = {
            "running":           True,
            "pid":               os.getpid(),
            "started_at":        datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at":        now_str(),
            "uptime_s":          round(time.time() - start_ts),
            "watch_folders":     cfg["watch_folders"],
            "crawl_folders":     cfg["crawl_folders"],
            "observers_alive":   sum(1 for o in observers if o.is_alive()),
            "classifier":        CLASSIFIER_AVAILABLE,
            "ai_fallback":       cfg.get("ai_fallback", False),
            **s,
        }
        try:
            with open(STATUS_FILE, "w") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            logging.warning("status write failed: %s", e)
        # check approval queue and notify if needed
        notifier.check(s.get("needs_review", 0))
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
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)

    logging.basicConfig(
        filename=str(LOG_FILE),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.info("=== FIS daemon starting (PID %d) ===", os.getpid())
    logging.info("Watch: %s", cfg["watch_folders"])
    logging.info("Crawl: %s", cfg["crawl_folders"])
    logging.info("Classifier: %s  AI fallback: %s",
                 CLASSIFIER_AVAILABLE, cfg.get("ai_fallback", False))

    db           = FisDB(str(DB_FILE))
    stop_event   = threading.Event()
    folder_cache = FolderCache(ttl_s=300) if CLASSIFIER_AVAILABLE else None

    skip_dirs  = set(cfg["skip_dirs"])
    skip_names = set(n.lower() for n in cfg["skip_names"])
    skip_exts  = set(e.lower() for e in cfg.get("skip_exts", [".chi", ".fisnote"]))

    do_classify = cfg.get("classify", True) and CLASSIFIER_AVAILABLE

    # --- watchdog observers (one per drive root + any extra watch_folders) ---
    # Watches the root of every drive so no move/create/delete goes untagged
    # regardless of which folder the file ends up in.
    handler = FisEventHandler(db, skip_dirs, skip_names, skip_exts,
                              classify=do_classify, folder_cache=folder_cache)
    observers = []

    # Collect roots to watch: all auto-discovered drives + explicit watch_folders
    watch_roots = list(get_crawl_drives(cfg))
    for wf in cfg.get("watch_folders", []):
        # add sub-folder paths that aren't already covered by a drive root
        if not any(str(wf).upper().startswith(r.upper()) for r in watch_roots):
            watch_roots.append(wf)

    for root in watch_roots:
        if not Path(root).exists():
            logging.warning("Watch root missing: %s", root)
            continue
        try:
            obs = Observer()
            obs.schedule(handler, root, recursive=True)
            obs.start()
            observers.append(obs)
            logging.info("Watching: %s", root)
        except Exception as e:
            logging.warning("Could not watch %s: %s", root, e)

    # --- background threads ---
    threads = [
        threading.Thread(target=background_crawler,
                         args=(cfg, db, stop_event, folder_cache),
                         name="Crawler", daemon=True),
        threading.Thread(target=reconciler, args=(cfg, db, stop_event),
                         name="Reconciler", daemon=True),
        threading.Thread(target=status_writer,
                         args=(cfg, db, stop_event, observers, start_ts),
                         name="StatusWriter", daemon=True),
        threading.Thread(target=ai_review_worker, args=(cfg, db, stop_event),
                         name="AIReview", daemon=True),
    ]
    for t in threads:
        t.start()

    logging.info("FIS daemon fully started.")

    try:
        while True:
            time.sleep(5)
            for obs in observers:
                if not obs.is_alive():
                    logging.warning("Observer died, restarting...")
                    try:
                        obs.start()
                    except Exception as e:
                        logging.error("Observer restart failed: %s", e)
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    finally:
        stop_event.set()
        for obs in observers:
            obs.stop()
        for obs in observers:
            obs.join(timeout=3)
        logging.info("=== FIS daemon stopped ===")


if __name__ == "__main__":
    main()
