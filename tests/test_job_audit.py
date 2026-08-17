from hub.storage.db import Database
from hub.storage.job_repo import JobRepo
from hub.workers.runner import WorkerRunner


def test_job_events_and_attempts_track_state_transitions(tmp_path):
    db = Database(tmp_path / "hub.sqlite3")
    repo = JobRepo(db.conn)
    job = repo.create_job("file_event", {"event": {"source": "test", "event_type": "created", "path": str(tmp_path / "missing.txt"), "is_directory": False}}, max_attempts=2)

    processed = WorkerRunner(repo).run_once(limit=1)[0]
    events = repo.list_job_events(job["id"])

    assert processed["status"] == "failed_retryable"
    assert processed["attempts"] == 1
    assert [event["to_status"] for event in events] == ["queued", "running", "failed_retryable"]
    assert repo.job_stats()["failed_retryable"] == 1


def test_retryable_job_becomes_terminal_at_max_attempts(tmp_path):
    db = Database(tmp_path / "hub.sqlite3")
    repo = JobRepo(db.conn)
    job = repo.create_job("file_event", {"event": {"source": "test", "event_type": "created", "path": str(tmp_path / "missing.txt"), "is_directory": False}}, max_attempts=1)

    processed = WorkerRunner(repo).run_once(limit=1)[0]
    terminal = repo.get_job(job["id"])

    assert processed["status"] == "failed_terminal"
    assert terminal["attempts"] == 1
    assert repo.list_job_events(job["id"])[-1]["to_status"] == "failed_terminal"
