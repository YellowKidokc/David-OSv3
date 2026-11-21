#!/usr/bin/env python3
"""
Capture a pre-change audit packet for the local organize source tree.

This is intentionally independent of organize's runtime code. It records:
- file hashes and sizes for the organize package
- inventory metadata for the selected Backside model folders
- a small model-context packet for the next AI partner or pass
- a root ledger entry pointing at the exact snapshot files

The model folders are inspected read-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "_backside_audit"
SNAPSHOT_DIR = AUDIT_DIR / "snapshots"
CONTEXT_DIR = AUDIT_DIR / "context_packets"
PPK_DIR = AUDIT_DIR / "ppk"
LEDGER_PATH = ROOT / "BACKSIDE_CHANGE_LEDGER.md"
PPK_SCRIPT_PATH = (
    Path(r"\\dlowenas\brain\Backside\_models\_Models\17_portable_preference_kernel")
    / "fis_addons"
    / "portable_preference_kernel.py"
)

MODEL_PATHS = [
    Path(r"\\dlowenas\brain\Backside\_models\_Models\17_portable_preference_kernel"),
    Path(r"\\dlowenas\brain\Backside\_models\_Models\13_preference_implicit"),
    Path(r"\\dlowenas\brain\Backside\_models\_Models\18_river_streaming"),
    Path(r"\\dlowenas\brain\Backside\_models\_Models\19_markovify_text"),
]

EXCLUDE_DIR_NAMES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "_backside_audit",
    "build",
    "dist",
}

EXCLUDE_FILE_SUFFIXES = {".pyc", ".pyo"}

SENSITIVE_KEYS = {
    "text",
    "content",
    "clipboard",
    "clipboard_text",
    "raw_text",
    "body",
    "email",
    "password",
    "token",
    "api_key",
    "secret",
    "screenshot",
    "image",
}


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_read_text(path: Path, max_chars: int = 4000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[:max_chars]


def sanitize_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value if abs(value) < 10_000_000 else "large_int"
    if isinstance(value, float):
        return round(value, 4) if math.isfinite(value) else "nonfinite"
    if isinstance(value, str):
        trimmed = value.strip()
        if len(trimmed) > 80:
            digest = hashlib.sha256(trimmed.encode("utf-8", errors="ignore")).hexdigest()
            return f"hash:{digest[:16]}"
        return trimmed
    if isinstance(value, list):
        return [sanitize_value(item) for item in value[:20]]
    if isinstance(value, dict):
        return sanitize_features(value)
    return str(type(value).__name__)


def sanitize_features(features: Dict[str, Any]) -> Dict[str, Any]:
    clean: Dict[str, Any] = {}
    for key, value in (features or {}).items():
        lowered = str(key).lower()
        if any(sensitive in lowered for sensitive in SENSITIVE_KEYS):
            if isinstance(value, str):
                digest = hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()
                clean[f"{key}_len"] = len(value)
                clean[f"{key}_hash"] = digest[:16]
            continue
        clean[key] = sanitize_value(value)
    return clean


def iter_files(root: Path) -> Iterable[Path]:
    for current_root, dirs, files in os.walk(root):
        current = Path(current_root)
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIR_NAMES]
        if any(part in EXCLUDE_DIR_NAMES for part in current.relative_to(root).parts):
            continue
        for name in sorted(files):
            path = current / name
            if path.suffix.lower() in EXCLUDE_FILE_SUFFIXES:
                continue
            yield path


def git_status() -> Dict[str, Any]:
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return {"available": False, "error": str(exc)}
    return {
        "available": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def package_summary() -> Dict[str, Any]:
    pyproject = safe_read_text(ROOT / "pyproject.toml")
    name_match = re.search(r'^name\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    version_match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    return {
        "root": str(ROOT),
        "package_name": name_match.group(1) if name_match else None,
        "version": version_match.group(1) if version_match else None,
        "has_git": (ROOT / ".git").exists(),
        "git_status": git_status(),
    }


def source_inventory() -> Dict[str, Any]:
    files: List[Dict[str, Any]] = []
    total_bytes = 0
    for path in sorted(iter_files(ROOT), key=lambda p: str(p.relative_to(ROOT)).lower()):
        try:
            stat = path.stat()
        except OSError:
            continue
        total_bytes += stat.st_size
        files.append(
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "size_bytes": stat.st_size,
                "mtime_utc": datetime.fromtimestamp(
                    stat.st_mtime, timezone.utc
                ).isoformat(timespec="seconds"),
                "sha256": sha256_path(path),
            }
        )
    return {
        "file_count": len(files),
        "total_bytes": total_bytes,
        "files": files,
    }


def model_inventory(model_path: Path) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "path": str(model_path),
        "exists": model_path.exists(),
        "read_only_intent": True,
    }
    if not model_path.exists():
        return item

    files: List[Dict[str, Any]] = []
    dir_count = 0
    total_bytes = 0
    for current_root, dirs, names in os.walk(model_path):
        dir_count += len(dirs)
        current = Path(current_root)
        for name in sorted(names):
            path = current / name
            try:
                stat = path.stat()
            except OSError:
                continue
            total_bytes += stat.st_size
            files.append(
                {
                    "path": str(path.relative_to(model_path)).replace("\\", "/"),
                    "size_bytes": stat.st_size,
                    "mtime_utc": datetime.fromtimestamp(
                        stat.st_mtime, timezone.utc
                    ).isoformat(timespec="seconds"),
                    "sha256": sha256_path(path),
                }
            )

    readme = model_path / "README.md"
    item.update(
        {
            "file_count": len(files),
            "dir_count": dir_count,
            "total_bytes": total_bytes,
            "top_level_entries": sorted(p.name for p in model_path.iterdir()),
            "readme_excerpt": safe_read_text(readme, max_chars=2000),
            "files": files,
        }
    )
    return item


def build_snapshot(note: str) -> Dict[str, Any]:
    source = source_inventory()
    models = [model_inventory(path) for path in MODEL_PATHS]
    package = package_summary()
    ppk_features = sanitize_features(
        {
            "package_name": package.get("package_name"),
            "package_version": package.get("version"),
            "source_file_count": source["file_count"],
            "source_total_bytes": source["total_bytes"],
            "has_git_checkout": package["has_git"],
            "has_cli": any(f["path"] == "organize/cli.py" for f in source["files"]),
            "has_jsonl_output": any(
                f["path"] == "organize/output/jsonl.py" for f in source["files"]
            ),
            "has_runtime_logger": any(
                f["path"] == "organize/logger.py" for f in source["files"]
            ),
            "has_tests": any(f["path"].startswith("tests/") for f in source["files"]),
            "selected_model_spine": "17_portable_preference_kernel",
            "support_models_available": [
                Path(model["path"]).name for model in models if model.get("exists")
            ],
            "behavior_code_changed": False,
            "model_dirs_mutated": False,
        }
    )
    return {
        "schema": "theophysics.backside.organize_audit.v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": note,
        "scope": {
            "target_package": str(ROOT),
            "model_paths": [str(p) for p in MODEL_PATHS],
            "behavior_code_changed": False,
            "model_dirs_mutated": False,
        },
        "model_ranking_for_this_lane": [
            {
                "rank": 1,
                "folder": "17_portable_preference_kernel",
                "role": "routing and preference decision spine",
            },
            {
                "rank": 2,
                "folder": "13_preference_implicit",
                "role": "future collaborative filtering support",
            },
            {
                "rank": 3,
                "folder": "18_river_streaming",
                "role": "future online learning support",
            },
            {
                "rank": 4,
                "folder": "19_markovify_text",
                "role": "future text-prediction support",
            },
        ],
        "package": package,
        "source_inventory": source,
        "models": models,
        "ppk_intake_features": ppk_features,
    }


def run_ppk_prediction(features_path: Path, prediction_path: Path) -> Dict[str, Any]:
    handoff: Dict[str, Any] = {
        "model_spine": "17_portable_preference_kernel",
        "script_path": str(PPK_SCRIPT_PATH),
        "features_path": str(features_path),
        "prediction_path": str(prediction_path),
        "ran_prediction": False,
    }
    if not PPK_SCRIPT_PATH.exists():
        handoff["error"] = "PPK script not found"
        prediction_path.write_text(json.dumps(handoff, indent=2), encoding="utf-8")
        return handoff

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [
            sys.executable,
            str(PPK_SCRIPT_PATH),
            "predict",
            "--features",
            str(features_path),
            "--top-k",
            "8",
        ],
        cwd=PPK_SCRIPT_PATH.parent,
        env=env,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
    )
    handoff.update(
        {
            "returncode": result.returncode,
            "stderr": result.stderr.strip(),
        }
    )
    if result.returncode == 0:
        try:
            prediction = json.loads(result.stdout)
        except json.JSONDecodeError:
            prediction = {"raw_stdout": result.stdout}
        prediction_path.write_text(
            json.dumps(prediction, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        handoff["ran_prediction"] = True
    else:
        handoff["stdout"] = result.stdout.strip()
        prediction_path.write_text(json.dumps(handoff, indent=2), encoding="utf-8")
    return handoff


def write_context_packet(snapshot: Dict[str, Any], path: Path) -> None:
    source = snapshot["source_inventory"]
    models = snapshot["models"]
    package = snapshot["package"]
    lines = [
        "# Backside Organize Model Context Packet",
        "",
        f"Created UTC: {snapshot['created_at_utc']}",
        f"Target package: `{package['root']}`",
        f"Package: `{package.get('package_name')}` v`{package.get('version')}`",
        f"Audit note: {snapshot['note']}",
        "",
        "## Boundary",
        "",
        "- This packet is pre-change context only.",
        "- No organize runtime behavior has been changed by the audit pass.",
        "- Backside model folders were inspected read-only.",
        "- Treat model rack folders as DO_NOT_MOVE unless David explicitly opens a migration lane.",
        "",
        "## Model Choice",
        "",
        "Use `17_portable_preference_kernel` as the current best decision spine.",
        "`13_preference_implicit`, `18_river_streaming`, and `19_markovify_text` are support candidates, not the first integration point.",
        "",
        "## Source Baseline",
        "",
        f"- File count: {source['file_count']}",
        f"- Total bytes: {source['total_bytes']}",
        f"- Git checkout present: {package['has_git']}",
        f"- Git status available: {package['git_status']['available']}",
        "",
        "## PPK Intake",
        "",
        "The full snapshot JSON is the durable model input. The `ppk_intake_features` object is the compact first-pass feature vector for `17_portable_preference_kernel`.",
        f"- Features sidecar: `{snapshot.get('ppk_handoff', {}).get('features_path', 'not written')}`",
        f"- Prediction sidecar: `{snapshot.get('ppk_handoff', {}).get('prediction_path', 'not written')}`",
        f"- Prediction ran: {snapshot.get('ppk_handoff', {}).get('ran_prediction', False)}",
        "",
        "## Model Baseline",
        "",
    ]
    for model in models:
        lines.extend(
            [
                f"### {Path(model['path']).name}",
                "",
                f"- Path: `{model['path']}`",
                f"- Exists: {model['exists']}",
                f"- Files: {model.get('file_count', 0)}",
                f"- Directories: {model.get('dir_count', 0)}",
                f"- Bytes: {model.get('total_bytes', 0)}",
                "",
            ]
        )
    lines.extend(
        [
            "## Next Rule",
            "",
            "Before any behavior change, run:",
            "",
            "```powershell",
            "python tools\\backside_audit.py --note \"before <change-name>\"",
            "```",
            "",
            "After a behavior change, run the same command with an `after` note and compare snapshot hashes.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def ensure_ledger() -> None:
    if LEDGER_PATH.exists():
        return
    LEDGER_PATH.write_text(
        "\n".join(
            [
                "# Backside Organize Change Ledger",
                "",
                "This ledger records pre-change and post-change audit packets for the local organize source tree.",
                "",
                "## Standing Boundary",
                "",
                "- Log before behavior changes.",
                "- Keep Backside model folders read-only unless David explicitly opens a migration lane.",
                "- Use `17_portable_preference_kernel` as the first decision spine for this lane.",
                "- Keep generated snapshots under `_backside_audit/`.",
                "",
                "## Entries",
                "",
            ]
        ),
        encoding="utf-8",
    )


def append_ledger(snapshot: Dict[str, Any], snapshot_path: Path, context_path: Path) -> None:
    ensure_ledger()
    source = snapshot["source_inventory"]
    models = snapshot["models"]
    snapshot_rel = str(snapshot_path.relative_to(ROOT)).replace("\\", "/")
    context_rel = str(context_path.relative_to(ROOT)).replace("\\", "/")
    entry = [
        "",
        f"### {snapshot['created_at_utc']}",
        "",
        f"- Note: {snapshot['note']}",
        f"- Snapshot: `{snapshot_rel}`",
        f"- Context packet: `{context_rel}`",
        f"- Source files: {source['file_count']}",
        f"- Source bytes: {source['total_bytes']}",
        "- Models inspected: "
        + ", ".join(
            f"{Path(model['path']).name} ({model.get('file_count', 0)} files)"
            for model in models
        ),
        "- Behavior code changed by this audit: no",
        "",
    ]
    with LEDGER_PATH.open("a", encoding="utf-8") as f:
        f.write("\n".join(entry))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--note",
        default="pre-change baseline before organize behavior modifications",
        help="Human-readable reason for this audit snapshot.",
    )
    args = parser.parse_args()

    stamp = utc_stamp()
    snapshot = build_snapshot(args.note)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    PPK_DIR.mkdir(parents=True, exist_ok=True)

    snapshot_path = SNAPSHOT_DIR / f"{stamp}_organize_baseline.json"
    context_path = CONTEXT_DIR / f"{stamp}_model_context.md"
    features_path = PPK_DIR / f"{stamp}_ppk_features.json"
    prediction_path = PPK_DIR / f"{stamp}_ppk_prediction.json"
    features_path.write_text(
        json.dumps(snapshot["ppk_intake_features"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    snapshot["ppk_handoff"] = run_ppk_prediction(features_path, prediction_path)
    snapshot_path.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_context_packet(snapshot, context_path)
    append_ledger(snapshot, snapshot_path, context_path)

    print(f"snapshot={snapshot_path}")
    print(f"context={context_path}")
    print(f"ledger={LEDGER_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
