from hub.storage.db import Database
from hub.storage.job_repo import JobRepo
from hub.workers.review_worker import apply_approved_review
from hub.workers.runner import WorkerRunner


def test_file_action_worker_writes_and_appends_text(tmp_path):
    db = Database(tmp_path / "hub.sqlite3")
    repo = JobRepo(db.conn)
    target = tmp_path / "notes" / "answer.md"
    repo.create_job("file_action", {"action": "write_text", "target_path": str(target), "text": "# Answer\n"})
    repo.create_job("file_action", {"action": "append_text", "target_path": str(target), "text": "More text\n"})

    processed = WorkerRunner(repo).run_once(limit=2)

    assert [job["status"] for job in processed] == ["completed", "completed"]
    assert target.read_text(encoding="utf-8") == "# Answer\nMore text\n"


def test_file_action_review_can_move_file(tmp_path):
    source = tmp_path / "incoming.txt"
    target = tmp_path / "archive" / "incoming.txt"
    source.write_text("hello", encoding="utf-8")
    db = Database(tmp_path / "hub.sqlite3")
    repo = JobRepo(db.conn)
    job = repo.create_job("file_action", {"action": "move", "source_path": str(source), "target_path": str(target)})
    review = repo.create_review_item(job["id"], reason="test_move", action="file_action", payload=job["payload"])

    repo.decide_review_item(review["id"], "approved")
    result = apply_approved_review(repo, review["id"])

    assert result["moved"] is True
    assert not source.exists()
    assert target.read_text(encoding="utf-8") == "hello"


def test_file_action_http_immediate_write(tmp_path):
    from fastapi.testclient import TestClient

    from hub.api import routes_file_actions
    from hub.api.app import create_app

    routes_file_actions.DEFAULT_DB_PATH = tmp_path / "hub.sqlite3"
    target = tmp_path / "ocr" / "capture.txt"
    client = TestClient(create_app())

    response = client.post(
        "/operator/file-actions",
        json={"action": "write_text", "target_path": str(target), "text": "OCR box text", "review_required": False},
    )

    assert response.status_code == 200
    assert response.json()["job"]["status"] == "completed"
    assert target.read_text(encoding="utf-8") == "OCR box text"
