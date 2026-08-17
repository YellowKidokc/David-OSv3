"""Self-healing node health and safe repair primitives."""
from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path

from hub.config.folder_profiles import FolderProfileConfigError, FolderProfileRegistry
from hub.storage.db import SCHEMA_VERSION, current_version
from hub.storage.job_repo import JobRepo
from hub.storage.node_repo import NodeRepo

SAFE_REPAIR_PREFIXES = ("schemas/", "config/", "prompts/", "templates/", "static_rules/")
BLOCKED_REPAIR_PARTS = ("secret", "credential", ".sqlite", ".db", "review")


class RepairPolicy:
    def is_safe_artifact(self, artifact_path: str | Path) -> bool:
        normalized = str(Path(artifact_path)).replace("\\", "/")
        return normalized.startswith(SAFE_REPAIR_PREFIXES) and not any(part in normalized.lower() for part in BLOCKED_REPAIR_PARTS)


class NodeHealthService:
    def __init__(self, node_repo: NodeRepo, job_repo: JobRepo, *, node_id: str = "local", repo_root: str | Path = ".") -> None:
        self.node_repo = node_repo
        self.job_repo = job_repo
        self.node_id = node_id
        self.repo_root = Path(repo_root)
        self.repair_policy = RepairPolicy()

    def heartbeat(
        self,
        *,
        node_role: str = "hub",
        hostname: str | None = None,
        capabilities: list[str] | None = None,
        priority: int = 50,
        hub_url: str | None = None,
        leader_status: str = "primary",
        is_primary: bool = True,
        status: str | None = None,
    ) -> dict[str, object]:
        health = self.check_local_health()
        node = {
            "node_id": self.node_id,
            "node_role": node_role,
            "hostname": hostname or platform.node(),
            "capabilities": capabilities or ["api_host", "inspect_folder", "tag_file", "rename_plan"],
            "status": status or health["status"],
            "priority": priority,
            "hub_url": hub_url or os.environ.get("FIHUB_BASE_URL"),
            "leader_status": leader_status,
            "is_primary": is_primary,
            "resources": health["resources"],
            "local_queue_depth": health["queue"]["queued"],
            "version": "0.1.0",
            "build_signature": f"schema-{SCHEMA_VERSION}",
        }
        return self.node_repo.heartbeat(node)

    def receive_peer_heartbeat(self, payload: dict[str, object]) -> dict[str, object]:
        node = {
            "node_id": str(payload["node_id"]),
            "node_role": str(payload.get("node_role") or payload.get("role", "peer")),
            "hostname": str(payload.get("hostname", "")),
            "capabilities": list(payload.get("capabilities", [])),
            "status": str(payload.get("status", "isolated_but_running")),
            "priority": int(payload.get("priority", 100)),
            "hub_url": payload.get("hub_url"),
            "leader_status": str(payload.get("leader_status", "helper")),
            "is_primary": bool(payload.get("is_primary", False)),
            "resources": dict(payload.get("resources", {})),
            "local_queue_depth": int(payload.get("local_queue_depth", 0)),
            "version": str(payload.get("version", "unknown")),
            "build_signature": str(payload.get("build_signature", "unknown")),
        }
        return self.node_repo.heartbeat(node)

    def check_local_health(self) -> dict[str, object]:
        checks = {
            "sqlite_writable": self._sqlite_writable(),
            "schema_current": current_version(self.node_repo.conn) == SCHEMA_VERSION,
            "folder_profiles_valid": self._profiles_valid(),
            "required_assets_present": (self.repo_root / "schemas/folder_profiles.schema.json").exists(),
            "watcher_health": "unknown_not_running_under_service",
            "worker_runner_health": "available",
            "api_reachability": "local_app_factory_available",
        }
        queue = {
            "queued": len(self.job_repo.list_jobs(status="queued")),
            "failed_retryable": len(self.job_repo.list_jobs(status="failed_retryable")),
            "waiting_review": len(self.job_repo.list_jobs(status="waiting_review")),
        }
        status = classify_health(checks, queue)
        return {"node_id": self.node_id, "status": status, "checks": checks, "queue": queue, "resources": self._resource_snapshot()}

    def repair_safe_artifact(self, artifact_path: str, *, source_root: str | Path, source_node: str | None = None) -> dict[str, object]:
        if not self.repair_policy.is_safe_artifact(artifact_path):
            return self.node_repo.log_repair({
                "repair_type": "safe_asset_copy", "scope": "peer-assisted", "transfer_mode": "blocked",
                "artifact_path": artifact_path, "outcome": "blocked_by_policy", "source_node": source_node,
            })
        source = Path(source_root) / artifact_path
        target = self.repo_root / artifact_path
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            return self.node_repo.log_repair({
                "repair_type": "safe_asset_copy", "scope": "peer-assisted", "transfer_mode": "copied",
                "artifact_path": artifact_path, "outcome": "success", "source_node": source_node,
            })
        except OSError as exc:
            return self.node_repo.log_repair({
                "repair_type": "safe_asset_copy", "scope": "peer-assisted", "transfer_mode": "copy_failed",
                "artifact_path": artifact_path, "outcome": "failed", "error": str(exc), "source_node": source_node,
            })

    def _sqlite_writable(self) -> bool:
        try:
            self.node_repo.conn.execute("CREATE TEMP TABLE IF NOT EXISTS health_write_check (id INTEGER)")
            self.node_repo.conn.execute("DROP TABLE health_write_check")
            return True
        except OSError:
            return False

    def _profiles_valid(self) -> bool:
        try:
            FolderProfileRegistry.load(self.repo_root / "config/folder_profiles.json")
            return True
        except (FolderProfileConfigError, OSError, ValueError):
            return False

    def _resource_snapshot(self) -> dict[str, object]:
        return {"machine": platform.node(), "platform": platform.platform(), "python": platform.python_version()}


def classify_health(checks: dict[str, object], queue: dict[str, int]) -> str:
    if not checks.get("sqlite_writable") or not checks.get("schema_current"):
        return "critical"
    if not checks.get("required_assets_present"):
        return "needs_peer_assist"
    if queue.get("failed_retryable", 0) >= 10:
        return "repairable_local"
    if queue.get("failed_retryable", 0) > 0 or queue.get("queued", 0) > 100:
        return "degraded_local"
    if checks.get("watcher_health") == "unknown_not_running_under_service":
        return "isolated_but_running"
    return "healthy"
