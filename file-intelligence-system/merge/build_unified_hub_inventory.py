#!/usr/bin/env python3
"""Read-only Phase 1 inventory for the Unified File Intelligence Hub merge.

This tool never copies, moves, deletes, alters donor files, or opens donor
SQLite databases for writing. It inventories the seven donors named in
UNIFIED_HUB_MERGE_PLAN.md and writes unified_hub_inventory.json beside them.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(r"D:\DONT TOUCH BOOT UP")
TARGET = Path(r"D:\GitHub\Top-of-Mind-API")
OUTPUT = ROOT / "unified_hub_inventory.json"
IGNORE_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
TEXT_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".md", ".rst", ".txt", ".toml", ".yaml", ".yml", ".json"}
DB_EXTS = {".db", ".sqlite", ".sqlite3"}
ENTRY_NAMES = {"main.py", "app.py", "server.py", "api.py", "__main__.py", "run.py", "manage.py"}

DONORS = [
    ("fastapi_application", ROOT / "FastAPI-application", "reference_donor"),
    ("file_intelligence_hub", ROOT / "file-intelligence-hub", "reference_donor"),
    ("filetagger", ROOT / "filetagger", "module_donor"),
    ("file_integrity_monitor", ROOT / "file-integrity-monitor", "module_donor"),
    ("organize", ROOT / "organize", "module_donor"),
    ("chi_qi_v5_statistical_audit", ROOT / "chi_qi_v5_statistical_audit_package", "module_donor"),
    ("python_master", ROOT / "Python-master", "reference_only"),
]


def iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if any(part.lower() in IGNORE_DIRS for part in path.parts):
            continue
        if path.is_file():
            yield path


def read_text(path: Path, limit: int = 150_000) -> str:
    if path.suffix.lower() not in TEXT_EXTS or path.stat().st_size > 4_000_000:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def routes_in(path: Path, content: str) -> list[str]:
    if not content:
        return []
    patterns = [
        r"@(?:app|router)\.(?:get|post|put|patch|delete|websocket)\(\s*[\"']([^\"']+)",
        r"(?:add_api_route|route)\(\s*[\"']([^\"']+)",
    ]
    found: list[str] = []
    for pattern in patterns:
        found.extend(re.findall(pattern, content))
    return sorted(set(found))


def inspect_database(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"path": str(path), "tables": [], "error": None}
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        result["tables"] = [row[0] for row in rows]
        connection.close()
    except Exception as exc:  # Inventory must continue even on damaged databases.
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def risk_flags(path: Path, content: str) -> list[str]:
    flags: list[str] = []
    lower_path = str(path).lower()
    lower_content = content.lower()
    if "d:\\dont touch boot up\\fis" in lower_content:
        flags.append("forbidden_legacy_fis_path")
    if "shutil.rmtree" in lower_content or "os.remove(" in lower_content or "unlink(" in lower_content:
        flags.append("destructive_operation_review_required")
    if path.suffix.lower() == ".zip":
        flags.append("archive_do_not_merge_blindly")
    if "salvaged" in lower_path or "archive" in lower_path:
        flags.append("archive_or_salvage_reference_only")
    return flags


def inventory_donor(identifier: str, root: Path, role: str) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": identifier,
        "path": str(root),
        "merge_role": role,
        "exists": root.is_dir(),
        "file_count": 0,
        "extension_counts": {},
        "entry_points": [],
        "python_modules": [],
        "databases": [],
        "documents": [],
        "routes": [],
        "startup_scripts": [],
        "risk_flags": [],
        "recommended_handling": "inventory_only",
    }
    if not root.is_dir():
        record["risk_flags"].append("donor_missing")
        return record

    extensions: Counter[str] = Counter()
    risk_map: dict[str, list[str]] = {}
    for file in iter_files(root):
        record["file_count"] += 1
        extensions[file.suffix.lower() or "[no_extension]"] += 1
        rel = relative(file, root)
        content = read_text(file)
        flags = risk_flags(file, content)
        if flags:
            risk_map[rel] = flags
        if file.name.lower() in ENTRY_NAMES or file.name.lower().startswith("start") and file.suffix.lower() in {".bat", ".ps1", ".sh"}:
            record["entry_points"].append(rel)
        if file.suffix.lower() == ".py":
            record["python_modules"].append(rel)
        if file.suffix.lower() in DB_EXTS:
            record["databases"].append(inspect_database(file))
        if file.suffix.lower() in {".md", ".rst"} or file.name.lower().startswith("readme"):
            record["documents"].append(rel)
        if file.suffix.lower() in {".bat", ".ps1", ".sh"}:
            record["startup_scripts"].append(rel)
        for route in routes_in(file, content):
            record["routes"].append({"path": route, "source": rel})

    record["extension_counts"] = dict(extensions.most_common())
    record["entry_points"].sort()
    record["python_modules"].sort()
    record["documents"].sort()
    record["startup_scripts"].sort()
    record["routes"] = sorted(record["routes"], key=lambda item: (item["path"], item["source"]))
    record["risk_flags"] = [{"path": item, "flags": flags} for item, flags in sorted(risk_map.items())]
    if role == "reference_only":
        record["recommended_handling"] = "mine_examples_only"
    elif identifier == "filetagger":
        record["recommended_handling"] = "port_selected_engines_after_legacy_path_review"
    else:
        record["recommended_handling"] = "selective_engine_import_after_api_contract"
    return record


def build_inventory() -> dict[str, Any]:
    donors = [inventory_donor(identifier, root, role) for identifier, root, role in DONORS]
    return {
        "schema": "unified-file-intelligence-hub-inventory.v1",
        "generated_at": iso_now(),
        "phase": "phase_1_inventory",
        "read_only": True,
        "target": {"path": str(TARGET), "exists": TARGET.is_dir(), "phase_2_precondition": "create_target_repository" if not TARGET.is_dir() else "ready"},
        "donors": donors,
        "summary": {
            "donors_requested": len(DONORS),
            "donors_present": sum(1 for donor in donors if donor["exists"]),
            "total_files": sum(donor["file_count"] for donor in donors),
            "databases_found": sum(len(donor["databases"]) for donor in donors),
            "routes_found": sum(len(donor["routes"]) for donor in donors),
            "risk_records": sum(len(donor["risk_flags"]) for donor in donors),
        },
        "next_gate": "human_review_inventory_before_phase_2_api_scaffold",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT, help="Manifest destination.")
    args = parser.parse_args()
    inventory = build_inventory()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(json.dumps(inventory["summary"], indent=2))


if __name__ == "__main__":
    main()
