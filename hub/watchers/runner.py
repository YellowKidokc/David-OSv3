"""Filesystem watcher runner that feeds normalized events into the hub."""
from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from hub.config.folder_profiles import FolderProfileRegistry
from hub.core.job_manager import JobManager
from hub.storage.db import Database
from hub.storage.job_repo import JobRepo


@dataclass(frozen=True)
class FileState:
    mtime_ns: int
    size: int


class PollingWatcher:
    """A dependency-free watcher suitable for local v1 control-plane runs."""

    def __init__(self, roots: Iterable[Path], manager: JobManager, *, interval: float = 1.0, debounce_seconds: float = 0.5) -> None:
        self.roots = [root for root in roots if root.exists()]
        self.manager = manager
        self.interval = interval
        self.debounce_seconds = debounce_seconds
        self._snapshot = self._scan()
        self._last_emitted: dict[tuple[str, str], float] = {}

    def run_forever(self) -> None:
        while True:
            self.poll_once()
            time.sleep(self.interval)

    def poll_once(self) -> list[dict[str, object]]:
        current = self._scan()
        events: list[dict[str, object]] = []
        previous_paths = set(self._snapshot)
        current_paths = set(current)

        created = sorted(current_paths - previous_paths)
        deleted = sorted(previous_paths - current_paths)
        moved_sources: set[str] = set()
        moved_targets: set[str] = set()
        for old_path in deleted:
            for new_path in created:
                if new_path in moved_targets:
                    continue
                if self._snapshot[old_path] == current[new_path]:
                    events.append(self._emit("moved", old_path, dest_path=new_path))
                    moved_sources.add(old_path)
                    moved_targets.add(new_path)
                    break
        for path in created:
            if path not in moved_targets:
                events.append(self._emit("created", path))
        for path in deleted:
            if path not in moved_sources:
                events.append(self._emit("deleted", path))
        for path in sorted(current_paths & previous_paths):
            if current[path] != self._snapshot[path]:
                events.append(self._emit("modified", path))

        self._snapshot = current
        return [event for event in events if event]

    def _emit(self, event_type: str, path: str, *, dest_path: str | None = None) -> dict[str, object]:
        now = time.monotonic()
        key = (event_type, path)
        last = self._last_emitted.get(key, 0.0)
        if now - last < self.debounce_seconds:
            return {}
        self._last_emitted[key] = now
        event = {"event_type": event_type, "path": path, "is_directory": False}
        if dest_path:
            event["dest_path"] = dest_path
        self.manager.ingest_file_event(event, source="polling_watcher")
        return event

    def _scan(self) -> dict[str, FileState]:
        snapshot: dict[str, FileState] = {}
        for root in self.roots:
            if root.is_file():
                self._add_path(root, snapshot)
                continue
            for path in root.rglob("*"):
                if path.is_file():
                    self._add_path(path, snapshot)
        return snapshot

    @staticmethod
    def _add_path(path: Path, snapshot: dict[str, FileState]) -> None:
        try:
            stat = path.stat()
        except OSError:
            return
        snapshot[str(path)] = FileState(mtime_ns=stat.st_mtime_ns, size=stat.st_size)


def build_watcher(db_path: str | Path, profiles_path: str | Path, *, interval: float = 1.0) -> PollingWatcher:
    registry = FolderProfileRegistry.load(profiles_path)
    db = Database(db_path)
    manager = JobManager(JobRepo(db.conn), profiles=registry)
    return PollingWatcher(registry.enabled_roots(), manager, interval=interval)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the file intelligence polling watcher")
    parser.add_argument("--db", default=".data/file-intelligence-hub.sqlite3")
    parser.add_argument("--profiles", default="config/folder_profiles.json")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--once", action="store_true", help="poll once and exit")
    args = parser.parse_args(argv)

    watcher = build_watcher(args.db, args.profiles, interval=args.interval)
    if args.once:
        watcher.poll_once()
        return 0
    watcher.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
