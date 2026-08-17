"""Intentional worker queue runner for queued hub jobs."""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from hub.core.job_manager import JobManager
from hub.storage.db import Database
from hub.storage.intelligence_repo import IntelligenceRepo
from hub.storage.job_repo import JobRepo
from hub.workers.command_worker import execute_command_line
from hub.workers.file_action_worker import execute_file_action
from hub.workers.folder_summary_worker import FolderSummaryWorker


class WorkerRunner:
    def __init__(self, repo: JobRepo) -> None:
        self.repo = repo
        self.manager = JobManager(repo)

    def process_next(self) -> dict[str, object] | None:
        job = self.repo.next_queued_job()
        if not job:
            return None
        if job["type"] == "file_event":
            try:
                return self.manager.process_file_event(job["id"])
            except FileNotFoundError as exc:
                return self.repo.update_job(job["id"], status="failed_retryable", error=str(exc))
            except (PermissionError, OSError, ValueError) as exc:
                return self.repo.update_job(job["id"], status="failed_terminal", error=str(exc))
        if job["type"] == "folder_summary":
            try:
                summary = FolderSummaryWorker(IntelligenceRepo(self.repo.conn), self.repo).summarize_folder(job["payload"]["folder_path"])
                return self.repo.update_job(job["id"], status="completed", result={"folder_summary": summary})
            except FileNotFoundError as exc:
                return self.repo.update_job(job["id"], status="failed_retryable", error=str(exc))
            except (PermissionError, OSError, ValueError) as exc:
                return self.repo.update_job(job["id"], status="failed_terminal", error=str(exc))
        if job["type"] == "file_action":
            try:
                result = execute_file_action(job["payload"])
                self.repo.add_ledger_entry(
                    job_id=job["id"],
                    action=f"file_action:{job['payload']['action']}",
                    before=job["payload"],
                    after=result,
                )
                return self.repo.update_job(job["id"], status="completed", result=result)
            except FileNotFoundError as exc:
                return self.repo.update_job(job["id"], status="failed_retryable", error=str(exc))
            except (FileExistsError, PermissionError, OSError, ValueError) as exc:
                return self.repo.update_job(job["id"], status="failed_terminal", error=str(exc))
        if job["type"] == "command_line":
            try:
                result = execute_command_line(job["payload"])
                self.repo.add_ledger_entry(job_id=job["id"], action="command_line", before=job["payload"], after=result)
                return self.repo.update_job(job["id"], status="completed", result=result)
            except FileNotFoundError as exc:
                return self.repo.update_job(job["id"], status="failed_retryable", error=str(exc))
            except (PermissionError, OSError, TimeoutError, ValueError) as exc:
                return self.repo.update_job(job["id"], status="failed_terminal", error=str(exc))
        return self.repo.update_job(job["id"], status="failed_terminal", error=f"unsupported job type: {job['type']}")

    def run_once(self, *, limit: int | None = None) -> list[dict[str, object]]:
        processed: list[dict[str, object]] = []
        while limit is None or len(processed) < limit:
            result = self.process_next()
            if result is None:
                break
            processed.append(result)
        return processed

    def run_forever(self, *, interval: float = 1.0) -> None:
        while True:
            self.run_once(limit=1)
            time.sleep(interval)


def build_runner(db_path: str | Path) -> WorkerRunner:
    db = Database(db_path)
    return WorkerRunner(JobRepo(db.conn))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Process queued file intelligence hub jobs")
    parser.add_argument("--db", default=".data/file-intelligence-hub.sqlite3")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--forever", action="store_true")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--requeue", type=int, help="requeue a failed_retryable or deferred job id")
    args = parser.parse_args(argv)

    runner = build_runner(args.db)
    if args.requeue is not None:
        runner.repo.requeue_job(args.requeue)
        return 0
    if args.forever:
        runner.run_forever(interval=args.interval)
    else:
        runner.run_once(limit=args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
