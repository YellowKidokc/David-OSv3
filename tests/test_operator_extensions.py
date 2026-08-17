import json
import struct

import pytest

from hub.config.folder_profiles import FolderProfileConfigError, FolderProfileRegistry
from hub.core.job_manager import JobManager
from hub.storage.db import Database
from hub.storage.job_repo import JobRepo
from hub.watchers.native import build_native_or_polling_watcher
from hub.watchers.runner import PollingWatcher
from hub.workers.classify_worker import classify_file


def test_invalid_folder_profile_config_fails_clearly(tmp_path):
    config = tmp_path / "profiles.json"
    config.write_text(json.dumps({"profiles": [{"path": 123}]}), encoding="utf-8")

    with pytest.raises(FolderProfileConfigError, match="path must be a string"):
        FolderProfileRegistry.load(config)


def test_csv_and_png_metadata_are_deterministic(tmp_path):
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("a,b\n1,2\n", encoding="utf-8")
    png_file = tmp_path / "image.png"
    png_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 3, 2) + b"\x08\x02\x00\x00\x00")

    csv_result = classify_file(str(csv_file))
    png_result = classify_file(str(png_file))

    assert csv_result["category"] == "data"
    assert csv_result["metadata"]["sample_columns"] == 2
    assert png_result["category"] == "media"
    assert png_result["metadata"] == {"format": "png", "width": 3, "height": 2}


def test_review_filtering_by_profile_action_and_deferred_requeue(tmp_path):
    watched = tmp_path / "watched"
    watched.mkdir()
    sample = watched / "notes.txt"
    sample.write_text("hello", encoding="utf-8")
    registry = FolderProfileRegistry.load(_profiles(tmp_path, watched, folder_role="inbox"))
    db = Database(tmp_path / "hub.sqlite3")
    repo = JobRepo(db.conn)
    job = JobManager(repo, profiles=registry).ingest_file_event({"event_type": "created", "path": str(sample)})
    review = repo.list_review_items(folder_role="inbox", action="rename", status="pending")[0]

    repo.decide_review_item(review["id"], "deferred")
    repo.update_job(job["id"], status="deferred", result={"review": review})
    requeued = repo.requeue_job(job["id"])

    assert requeued["status"] == "queued"


def test_native_builder_falls_back_to_polling_when_watchdog_unavailable_or_builds_native(tmp_path):
    watched = tmp_path / "watched"
    watched.mkdir()
    profiles = _profiles(tmp_path, watched)

    watcher = build_native_or_polling_watcher(tmp_path / "hub.sqlite3", profiles)

    assert watcher.__class__.__name__ in {"NativeWatcher", "PollingWatcher"}


def test_app_factory_registers_current_routes():
    pytest.importorskip("fastapi")
    from hub.api.app import create_app

    app = create_app()
    paths = set(app.openapi()["paths"])

    assert "/jobs" in paths
    assert "/reviews" in paths
    assert "/jobs/{job_id}/requeue" in paths
    assert "/jobs/{job_id}/events" in paths
    assert "/jobs/stats" in paths
    assert "/files/cache" in paths
    assert "/files/cache/search" in paths
    assert "/folders" in paths
    assert "/folders/{folder_id}" in paths
    assert "/memory/items" in paths
    assert "/memory/embed-pending" in paths
    assert "/memory/search" in paths
    assert "/operator/commands" in paths
    assert "/operator/file-actions" in paths
    assert "/predict/observe" in paths
    assert "/predict/predict" in paths
    assert "/predict/correct" in paths
    assert "/predict/make-permanent" in paths
    assert "/predict/stats" in paths
    assert "/top-of-mind/messages" in paths
    assert "/top-of-mind/controls/end-all" in paths


def _profiles(tmp_path, watched, *, folder_role="general"):
    config = tmp_path / "profiles.json"
    config.write_text(json.dumps({"profiles": [{"path": str(watched), "folder_role": folder_role, "review_only": True}]}), encoding="utf-8")
    return config
