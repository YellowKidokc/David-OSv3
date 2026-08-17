import json

from hub.config.folder_profiles import FolderProfileRegistry
from hub.storage.db import Database, SCHEMA_VERSION, current_version
from hub.storage.job_repo import JobRepo
from hub.watchers.runner import PollingWatcher
from hub.workers.classify_worker import classify_file
from hub.workers.runner import WorkerRunner
from hub.core.job_manager import JobManager


def test_folder_profile_defaults_and_best_match(tmp_path):
    root = tmp_path / "inbox"
    nested = root / "protected"
    nested.mkdir(parents=True)
    config = tmp_path / "profiles.json"
    config.write_text(json.dumps({
        "defaults": {"folder_role": "general", "review_only": True},
        "profiles": [
            {"path": str(root), "folder_role": "inbox", "review_only": False},
            {"path": str(nested), "folder_role": "protected", "protected": True},
        ],
    }), encoding="utf-8")

    registry = FolderProfileRegistry.load(config)

    assert registry.match(root / "a.txt").folder_role == "inbox"
    assert registry.match(nested / "b.txt").protected is True
    assert registry.enabled_roots() == [root, nested]


def test_classifier_uses_content_signature_without_suffix(tmp_path):
    pdf = tmp_path / "download"
    pdf.write_bytes(b"%PDF-1.7\nbody")

    result = classify_file(str(pdf))

    assert result["category"] == "document"
    assert result["reason"] == "pdf_signature"


def test_worker_runner_processes_queued_job(tmp_path):
    sample = tmp_path / "notes.txt"
    sample.write_text("hello", encoding="utf-8")
    db = Database(tmp_path / "hub.sqlite3")
    repo = JobRepo(db.conn)
    repo.create_job("file_event", {"event": {"source": "test", "event_type": "created", "path": str(sample), "is_directory": False}})

    processed = WorkerRunner(repo).run_once(limit=1)

    assert len(processed) == 1
    assert processed[0]["status"] in {"waiting_review", "completed"}


def test_polling_watcher_detects_create_and_feeds_manager(tmp_path):
    root = tmp_path / "watch"
    root.mkdir()
    db = Database(tmp_path / "hub.sqlite3")
    repo = JobRepo(db.conn)
    manager = JobManager(repo)
    watcher = PollingWatcher([root], manager, debounce_seconds=0)

    sample = root / "new.txt"
    sample.write_text("hello", encoding="utf-8")
    events = watcher.poll_once()

    assert events == [{"event_type": "created", "path": str(sample), "is_directory": False}]
    assert repo.list_jobs()[0]["status"] == "waiting_review"


def test_schema_version_migration_is_recorded(tmp_path):
    db = Database(tmp_path / "hub.sqlite3")

    assert current_version(db.conn) == SCHEMA_VERSION
    rows = db.conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    assert [row["version"] for row in rows] == list(range(1, SCHEMA_VERSION + 1))
