"""
FIS Desktop Watcher — reports file events to NAS via webhook.
Runs at startup, watches configured folders, POSTs changes to n8n.

Install: pip install watchdog requests
Startup: drop shortcut to this script in shell:startup
         or create a scheduled task: "At log on" → python fis_watcher.py

50 lines of real logic. The rest is config.
"""
import hashlib, json, time, sys
from pathlib import Path
from datetime import datetime, timezone
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import requests

# ── CONFIG ──────────────────────────────────────────────────
WEBHOOK = "https://n8n.dlowehomelab.com/webhook/file-event"
WATCH_ROOTS = [
    r"H:\Desktop",
    r"H:\Desktop 2",
    r"D:\GitHub",
    r"H:\Documents",
]

IGNORE_DIRS  = {".git", "__pycache__", "node_modules", ".venv", ".obsidian"}
IGNORE_EXTS  = {".tmp", ".crdownload", ".part", ".lock"}
RETRY_DELAY  = 5
BATCH_WINDOW = 1.0   # seconds to batch rapid events
LOG_FILE     = Path(__file__).parent / "fis_watcher.log"
# ────────────────────────────────────────────────────────────


def sha256_quick(path, max_bytes=65536):
    """Fast partial hash for identity — not full-file, just enough to match."""
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read(max_bytes)).hexdigest()[:16]
    except Exception:
        return None


def should_ignore(path_str):
    p = Path(path_str)
    if any(part in IGNORE_DIRS for part in p.parts):
        return True
    if p.suffix.lower() in IGNORE_EXTS:
        return True
    if p.name.startswith("~") or p.name.startswith("."):
        return True
    return False


def post_event(event_type, src, dest=None):
    """POST to n8n webhook. Fire and forget — failures log locally."""
    payload = {
        "event": event_type,
        "path": str(src),
        "dest": str(dest) if dest else None,
        "hash": sha256_quick(dest or src),
        "size": None,
        "ts": datetime.now(timezone.utc).isoformat(),
        "machine": "desktop",
    }
    try:
        s = Path(dest or src)
        if s.exists():
            payload["size"] = s.stat().st_size
    except Exception:
        pass

    line = f"{payload['ts']} {event_type:10s} {src}"
    if dest:
        line += f" → {dest}"
    print(line)

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

    for attempt in range(3):
        try:
            r = requests.post(WEBHOOK, json=payload, timeout=5)
            if r.ok:
                return
        except Exception:
            pass
        time.sleep(RETRY_DELAY)


class FISHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory or should_ignore(event.src_path):
            return
        post_event("created", event.src_path)

    def on_modified(self, event):
        if event.is_directory or should_ignore(event.src_path):
            return
        post_event("modified", event.src_path)

    def on_deleted(self, event):
        if event.is_directory or should_ignore(event.src_path):
            return
        post_event("deleted", event.src_path)

    def on_moved(self, event):
        if event.is_directory:
            return
        if should_ignore(event.src_path) and should_ignore(event.dest_path):
            return
        post_event("moved", event.src_path, event.dest_path)


def main():
    print("=" * 60)
    print("  FIS Desktop Watcher")
    print(f"  Webhook: {WEBHOOK}")
    print(f"  Watching {len(WATCH_ROOTS)} roots:")
    for r in WATCH_ROOTS:
        exists = Path(r).exists()
        print(f"    {'✓' if exists else '✗'} {r}")
    print(f"  Log: {LOG_FILE}")
    print("=" * 60)

    observer = Observer()
    handler = FISHandler()
    active = 0

    for root in WATCH_ROOTS:
        if Path(root).exists():
            observer.schedule(handler, root, recursive=True)
            active += 1
        else:
            print(f"  SKIP (not found): {root}")

    if active == 0:
        print("No valid roots. Exiting.")
        sys.exit(1)

    observer.start()
    print(f"\nWatching {active} roots. Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nStopped.")
    observer.join()


if __name__ == "__main__":
    main()
