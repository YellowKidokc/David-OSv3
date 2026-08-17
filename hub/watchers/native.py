"""Native filesystem watcher adapter using watchdog when available."""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import time
from pathlib import Path
from typing import Iterable

from hub.config.folder_profiles import FolderProfileRegistry
from hub.core.job_manager import JobManager
from hub.storage.db import Database
from hub.storage.job_repo import JobRepo
from hub.watchers.runner import PollingWatcher


class NativeWatcherUnavailable(RuntimeError):
    """Raised when the optional native watcher dependency is unavailable."""


class NativeWatcher:
    """Watchdog-backed adapter that preserves the same hub ingestion boundary."""

    def __init__(self, roots: Iterable[Path], manager: JobManager) -> None:
        if importlib.util.find_spec("watchdog") is None:
            raise NativeWatcherUnavailable("watchdog is not installed; use polling watcher fallback")
        events_module = importlib.import_module("watchdog.events")
        observers_module = importlib.import_module("watchdog.observers")
        handler_base = events_module.FileSystemEventHandler
        observer_cls = observers_module.Observer
        manager_ref = manager

        class Handler(handler_base):  # type: ignore[misc, valid-type]
            def on_created(self, event: object) -> None:
                self._ingest("created", event)

            def on_modified(self, event: object) -> None:
                self._ingest("modified", event)

            def on_deleted(self, event: object) -> None:
                self._ingest("deleted", event)

            def on_moved(self, event: object) -> None:
                self._ingest("moved", event)

            def _ingest(self, event_type: str, event: object) -> None:
                payload = {
                    "event_type": event_type,
                    "path": str(getattr(event, "src_path")),
                    "is_directory": bool(getattr(event, "is_directory", False)),
                }
                dest_path = getattr(event, "dest_path", None)
                if dest_path:
                    payload["dest_path"] = str(dest_path)
                manager_ref.ingest_file_event(payload, source="native_watcher")

        self.observer = observer_cls()
        self.handler = Handler()
        self.roots = [root for root in roots if root.exists()]
        for root in self.roots:
            self.observer.schedule(self.handler, str(root), recursive=True)

    def run_forever(self) -> None:
        self.observer.start()
        try:
            while True:
                time.sleep(1)
        finally:
            self.observer.stop()
            self.observer.join()


def build_native_or_polling_watcher(
    db_path: str | Path,
    profiles_path: str | Path,
    *,
    interval: float = 1.0,
) -> NativeWatcher | PollingWatcher:
    registry = FolderProfileRegistry.load(profiles_path)
    db = Database(db_path)
    manager = JobManager(JobRepo(db.conn), profiles=registry)
    roots = registry.enabled_roots()
    if importlib.util.find_spec("watchdog") is None:
        return PollingWatcher(roots, manager, interval=interval)
    return NativeWatcher(roots, manager)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the native watcher, falling back to polling when watchdog is unavailable")
    parser.add_argument("--db", default=".data/file-intelligence-hub.sqlite3")
    parser.add_argument("--profiles", default="config/folder_profiles.json")
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args(argv)
    build_native_or_polling_watcher(args.db, args.profiles, interval=args.interval).run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
