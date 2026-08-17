"""Apply approved review decisions."""
from __future__ import annotations

from hub.storage.job_repo import JobRepo
from hub.workers.command_worker import execute_command_line
from hub.workers.file_action_worker import execute_file_action
from hub.workers.rename_worker import execute_rename


def apply_approved_review(repo: JobRepo, review_id: int) -> dict[str, object]:
    review = repo.get_review_item(review_id)
    if review["status"] != "approved":
        raise ValueError("review item must be approved before execution")
    if review["action"] == "rename":
        before = {"path": review["payload"]["source_path"]}
        result = execute_rename(review["payload"])
        action = "rename"
    elif review["action"] == "file_action":
        before = review["payload"]
        result = execute_file_action(review["payload"])
        action = f"file_action:{review['payload']['action']}"
    elif review["action"] == "command_line":
        before = review["payload"]
        result = execute_command_line(review["payload"])
        action = "command_line"
    else:
        raise ValueError(f"unsupported review action {review['action']}")
    repo.add_ledger_entry(job_id=review["job_id"], action=action, before=before, after=result)
    repo.update_job(review["job_id"], status="completed", result=result)
    return result
