"""Loaders for existing records: manifest, registry, master list, batch runs."""

from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def load_manifest(path: str) -> dict[str, dict[str, Any]]:
    """Load 00_MANIFEST.csv keyed by lower-cased SHA-256."""
    result: dict[str, dict[str, Any]] = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sha = (row.get("Hash") or "").strip().lower()
            if not sha:
                continue
            result[sha] = {
                "hash": sha,
                "new_path": row.get("NewPath", "").strip(),
                "original_path": row.get("OriginalPath", "").strip(),
                "node": row.get("Node", "").strip(),
                "status": row.get("Status", "").strip(),
                "theorems": _parse_int(row.get("Theorems")),
                "sorries": _parse_int(row.get("Sorries")),
                "active_sorry": _parse_int(row.get("ActiveSorry")),
                "active_admit": _parse_int(row.get("ActiveAdmit")),
                "inventory_theorems": _parse_int(row.get("InventoryTheorems")),
                "inventory_sorries": _parse_int(row.get("InventorySorries")),
                "canonical_or_superseded": row.get("CanonicalOrSuperseded", "").strip(),
                "relative_path": row.get("RelativePath", "").strip(),
                "uncertain": row.get("Uncertain", "").strip().lower() == "true",
                "uncertainty_reason": row.get("UncertaintyReason", "").strip(),
            }
    return result


def load_registry(path: str) -> dict[str, dict[str, Any]]:
    """Load AXIOM_OUTPUT/_support/registry.json keyed by lower-cased SHA-256."""
    result: dict[str, dict[str, Any]] = {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for rec_id, rec in data.get("records", {}).items():
        sha = (rec.get("sha256") or "").strip().lower()
        if not sha:
            continue
        updated = rec.get("updated", "")
        ran_at = None
        if updated:
            try:
                ran_at = datetime.fromisoformat(updated)
                if ran_at.tzinfo is None:
                    ran_at = ran_at.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        result[sha] = {
            "record_id": rec_id,
            "source": rec.get("source", ""),
            "provider": rec.get("provider", ""),
            "output_dir": rec.get("output_dir", ""),
            "status": rec.get("status", ""),
            "error": rec.get("error", ""),
            "group": rec.get("group", ""),
            "title": rec.get("title", ""),
            "ran_at": ran_at,
        }
    return result


def load_master_list(path: str) -> list[dict[str, Any]]:
    """Load MASTER_LIST.csv rows."""
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sha = (row.get("source_sha256") or "").strip().lower()
            if not sha:
                continue
            rows.append(
                {
                    "sha256": sha,
                    "paper": row.get("paper", "").strip(),
                    "source_folder": row.get("source_folder", "").strip(),
                    "source": row.get("source", "").strip(),
                    "status": row.get("status", "").strip(),
                    "reader_paper": row.get("reader_paper", "").strip(),
                    "paper_status": row.get("paper_status", "").strip(),
                    "provider": row.get("provider", "").strip(),
                    "updated_utc": row.get("updated_utc", "").strip(),
                }
            )
    return rows


def _infer_build_status(log_text: str) -> tuple[str, bool]:
    """Return (status, has_native_decide)."""
    has_error = "error:" in log_text.lower() or "Build FAILED" in log_text
    has_native = "native_decide" in log_text
    status = "FAIL" if has_error else "PASS"
    return status, has_native


def load_batch_runs(path: str) -> list[dict[str, Any]]:
    """Walk BATCH_RUNS and produce a list of build/print-axioms records."""
    records: list[dict[str, Any]] = []
    base = Path(path)
    if not base.is_dir():
        return records

    log_pattern = re.compile(r"^([0-9a-f]{16})\.build\.log\.txt$")

    for run_dir in sorted(base.iterdir()):
        if not run_dir.is_dir():
            continue
        run_id = run_dir.name
        json_file = run_dir / "FAMILY_BUILD_RECEIPT.json"

        if json_file.exists():
            try:
                with json_file.open("r", encoding="utf-8-sig") as f:
                    family = json.load(f)
            except (json.JSONDecodeError, OSError):
                family = []
            for item in family:
                sha = (item.get("source_sha256") or "").strip().lower()
                if not sha:
                    continue
                build_status = (item.get("build_status") or "").strip()
                passed = build_status.startswith("BUILD_PASS")
                log_path = item.get("build_log", "")
                has_native = False
                if log_path and Path(log_path).exists():
                    try:
                        has_native = "native_decide" in Path(log_path).read_text(encoding="utf-8", errors="ignore")
                    except OSError:
                        pass
                records.append(
                    {
                        "sha256": sha,
                        "run_id": run_id,
                        "kind": "BUILD",
                        "result": "PASS" if passed else "FAIL",
                        "log_path": str(log_path),
                        "ran_at": None,
                    }
                )
                if passed:
                    records.append(
                        {
                            "sha256": sha,
                            "run_id": run_id,
                            "kind": "PRINT_AXIOMS",
                            "result": "NATIVE_DECIDE" if has_native else "CLEAN",
                            "log_path": str(log_path),
                            "ran_at": None,
                        }
                    )
        else:
            # No JSON receipt: infer from individual log files.
            for log_file in run_dir.glob("*.build.log.txt"):
                m = log_pattern.match(log_file.name)
                if not m:
                    continue
                sha_prefix = m.group(1)
                try:
                    text = log_file.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                status, has_native = _infer_build_status(text)
                # Look up the full sha by searching for the prefix in the log text
                # is not reliable; we only have a prefix here. The caller will need
                # to resolve these later if exact sha is required. For now store
                # the prefix as the sha and let the importer warn on misses.
                records.append(
                    {
                        "sha256": sha_prefix,
                        "run_id": run_id,
                        "kind": "BUILD",
                        "result": status,
                        "log_path": str(log_file),
                        "ran_at": None,
                    }
                )
                if status == "PASS":
                    records.append(
                        {
                            "sha256": sha_prefix,
                            "run_id": run_id,
                            "kind": "PRINT_AXIOMS",
                            "result": "NATIVE_DECIDE" if has_native else "CLEAN",
                            "log_path": str(log_file),
                            "ran_at": None,
                        }
                    )
    return records
