from hub.core.job_manager import JobManager
from hub.storage.db import Database
from hub.storage.job_repo import JobRepo
from hub.workers.review_worker import apply_approved_review


def test_file_event_creates_review_and_approved_rename_executes(tmp_path):
    sample = tmp_path / "Quarterly Report.txt"
    sample.write_text("hello", encoding="utf-8")
    db = Database(tmp_path / "hub.sqlite3")
    repo = JobRepo(db.conn)

    job = JobManager(repo).ingest_file_event({"event_type": "created", "path": str(sample)})

    assert job["status"] == "waiting_review"
    assert job["result"]["hash"]["digest"]
    reviews = repo.list_review_items(status="pending")
    assert len(reviews) == 1

    repo.decide_review_item(reviews[0]["id"], "approved")
    result = apply_approved_review(repo, reviews[0]["id"])

    assert result["renamed"] is True
    assert not sample.exists()
    assert result["target_path"].endswith(".txt")
    assert repo.get_job(job["id"])["status"] == "completed"
