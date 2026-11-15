#!/usr/bin/env python3
"""Generate _folder.chi sidecars and persist folder metadata."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

DB_PATH = Path(os.environ.get("CHI_DB_PATH", Path(__file__).with_name("organize.db")))
CHI_NAME = "_folder.chi"
SKIP_DIRS = {"node_modules", "__pycache__", ".git", ".hg", ".svn", ".mypy_cache", ".pytest_cache"}
HUMAN_FIELDS = {
    "primary_chi", "secondary_chi", "role", "domain", "tags", "state", "risk",
    "notes", "location_history", "last_human_edit",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS chi_metadata (
    id INTEGER PRIMARY KEY,
    folder_path TEXT UNIQUE NOT NULL,
    primary_chi TEXT DEFAULT '',
    secondary_chi TEXT DEFAULT '',
    role TEXT DEFAULT '',
    domain TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    state TEXT DEFAULT 'W',
    risk TEXT DEFAULT '',
    confidence REAL DEFAULT 0.0,
    needs_review INTEGER DEFAULT 1,
    file_count INTEGER DEFAULT 0,
    total_size INTEGER DEFAULT 0,
    extensions TEXT DEFAULT '',
    chi_file_exists INTEGER DEFAULT 0,
    last_scanned TEXT,
    last_human_edit TEXT,
    created TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_chi_folder ON chi_metadata(folder_path);
CREATE INDEX IF NOT EXISTS idx_chi_primary ON chi_metadata(primary_chi);
CREATE INDEX IF NOT EXISTS idx_chi_domain ON chi_metadata(domain);
"""


def connect_db() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.execute("PRAGMA busy_timeout=30000")
    db.executescript(SCHEMA)
    db.commit()
    return db


def should_skip_dir(name: str) -> bool:
    if name in SKIP_DIRS:
        return True
    return name.startswith(".") and name != ".obsidian"


def child_listing(folder: Path) -> tuple[list[str], list[str]]:
    files, dirs = [], []
    try:
        for item in folder.iterdir():
            if item.is_dir():
                dirs.append(item.name)
            elif item.is_file():
                files.append(item.name)
    except OSError:
        pass
    return files, dirs


def detect_role_domain(folder: Path, filenames: list[str], dirnames: list[str], ext_counts: Counter[str]) -> tuple[list[str], str]:
    roles: list[str] = []
    names_lower = [f.lower() for f in filenames]
    dirs_lower = [d.lower() for d in dirnames]
    path_lower = str(folder).lower()

    if ".git" in dirs_lower:
        roles.append("repo")
    if ".obsidian" in dirs_lower:
        roles.append("obsidian")
    if "package.json" in names_lower:
        roles.append("node_project")
    if any(f in names_lower for f in ("pyproject.toml", "setup.py", "requirements.txt")):
        roles.append("python_project")
    if "cargo.toml" in names_lower:
        roles.append("rust_project")
    if "lakefile.lean" in names_lower or "lean-toolchain" in names_lower:
        roles.append("lean_project")

    file_count = sum(ext_counts.values())
    html_count = ext_counts.get(".html", 0) + ext_counts.get(".htm", 0)
    if file_count >= 5 and html_count / max(file_count, 1) >= 0.5:
        roles.append("html_output")

    domain = ""
    if any(t in path_lower for t in ("faiththruphysics", "theophysics", "logos_v", "mda-build", "genesis_to_quantum", "gtq")):
        domain = "theophysics"
    return roles, domain


def folder_stats(folder: Path) -> dict[str, Any]:
    ext_counts: Counter[str] = Counter()
    total_size = 0
    file_count = 0
    for item in folder.iterdir():
        if not item.is_file() or item.name == CHI_NAME:
            continue
        try:
            total_size += item.stat().st_size
        except OSError:
            continue
        file_count += 1
        ext_counts[item.suffix.lower() or "[none]"] += 1
    return {"file_count": file_count, "total_size": total_size, "extensions": dict(sorted(ext_counts.items()))}


def infer_chi(roles: list[str], domain: str, extensions: dict[str, int]) -> tuple[str, list[str], float]:
    role_set = set(roles)
    total = sum(extensions.values()) or 1
    if "lean_project" in role_set:
        return "K", ["C"], 0.72
    if "repo" in role_set and domain == "theophysics":
        return "K", ["M"], 0.76
    if "obsidian" in role_set:
        return "K", [], 0.74
    if "html_output" in role_set and domain == "theophysics":
        return "E", ["K"], 0.78
    data_count = extensions.get(".xlsx", 0) + extensions.get(".csv", 0)
    if data_count / total >= 0.35:
        return "T", ["S"], 0.68
    if "python_project" in role_set or "node_project" in role_set or "rust_project" in role_set:
        return "M", [], 0.66
    return "", [], 0.35


def read_chi(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, ""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    data = yaml.safe_load(parts[1]) or {}
    return data, parts[2].lstrip()


def render_chi(folder: Path, meta: dict[str, Any], roles: list[str], confidence: float) -> str:
    contents = [f"- {count} {ext} files" for ext, count in meta["extensions"].items()]
    role_line = ", ".join([r for r in roles + ([meta["domain"]] if meta.get("domain") else []) if r]) or "unknown"
    frontmatter = yaml.safe_dump(meta, sort_keys=False, allow_unicode=False).strip()
    confidence_pct = round(confidence * 100)
    review = "below threshold, needs human review" if meta.get("needs_review") else "accepted for automation"
    return (
        f"---\n{frontmatter}\n---\n\n"
        f"# {folder}\n\n"
        "## Contents\n"
        + ("\n".join(contents) if contents else "- empty")
        + "\n\n## Auto-detected Role\n"
        f"{role_line}\n\n"
        "## Classification Confidence\n"
        f"{confidence_pct}% - {review}\n"
    )


def upsert_db(db: sqlite3.Connection, folder: Path, meta: dict[str, Any], exists: bool) -> None:
    db.execute(
        """INSERT INTO chi_metadata
           (folder_path, primary_chi, secondary_chi, role, domain, tags, state, risk,
            confidence, needs_review, file_count, total_size, extensions, chi_file_exists,
            last_scanned, last_human_edit)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(folder_path) DO UPDATE SET
            primary_chi=excluded.primary_chi, secondary_chi=excluded.secondary_chi,
            role=excluded.role, domain=excluded.domain, tags=excluded.tags,
            state=excluded.state, risk=excluded.risk, confidence=excluded.confidence,
            needs_review=excluded.needs_review, file_count=excluded.file_count,
            total_size=excluded.total_size, extensions=excluded.extensions,
            chi_file_exists=excluded.chi_file_exists, last_scanned=excluded.last_scanned,
            last_human_edit=excluded.last_human_edit""",
        (
            str(folder),
            meta.get("primary_chi", ""),
            json.dumps(meta.get("secondary_chi", [])),
            meta.get("role", ""),
            meta.get("domain", ""),
            json.dumps(meta.get("tags", [])),
            meta.get("state", "W"),
            meta.get("risk", ""),
            float(meta.get("confidence", 0.0)),
            int(bool(meta.get("needs_review", True))),
            int(meta.get("file_count", 0)),
            int(meta.get("total_size", 0)),
            json.dumps(meta.get("extensions", {})),
            int(exists),
            meta.get("last_scanned"),
            meta.get("last_human_edit", ""),
        ),
    )


def build_metadata(folder: Path, update_existing: bool) -> tuple[dict[str, Any], list[str], bool]:
    chi_path = folder / CHI_NAME
    old_meta, _ = read_chi(chi_path)
    exists = chi_path.exists()
    files, dirs = child_listing(folder)
    stats = folder_stats(folder)
    roles, domain = detect_role_domain(folder, files, dirs, Counter(stats["extensions"]))
    primary, secondary, confidence = infer_chi(roles, domain, stats["extensions"])
    now = datetime.now().replace(microsecond=0).isoformat()

    meta = {
        "primary_chi": primary,
        "secondary_chi": secondary,
        "role": ",".join(roles),
        "domain": domain,
        "tags": [],
        "state": "W",
        "risk": "R2" if domain == "theophysics" else "",
        "file_count": stats["file_count"],
        "total_size_mb": round(stats["total_size"] / 1024 / 1024, 2),
        "total_size": stats["total_size"],
        "extensions": stats["extensions"],
        "confidence": round(confidence, 2),
        "needs_review": confidence < 0.70,
        "last_scanned": now,
        "created_by": "chi-generator",
        "location_history": [{"path": str(folder), "date": now[:10]}],
        "notes": "",
    }

    if exists and update_existing:
        for key in HUMAN_FIELDS:
            if key in old_meta and old_meta[key] not in (None, "", []):
                meta[key] = old_meta[key]
        old_history = old_meta.get("location_history") or []
        if old_history:
            meta["location_history"] = old_history
        if not old_meta.get("primary_chi"):
            meta["primary_chi"] = primary
    return meta, roles, exists


def iter_folders(root: Path, depth: int):
    root = root.resolve()
    stack = [(root, 0)]
    while stack:
        folder, level = stack.pop()
        yield folder
        if level >= depth:
            continue
        try:
            children = [p for p in folder.iterdir() if p.is_dir() and not should_skip_dir(p.name)]
        except OSError:
            continue
        stack.extend((child, level + 1) for child in reversed(children))


def scan(root: str, depth: int, update_existing: bool) -> None:
    root_path = Path(root)
    db = connect_db()
    created = updated = skipped = 0
    try:
        for folder in iter_folders(root_path, depth):
            chi_path = folder / CHI_NAME
            if chi_path.exists() and not update_existing:
                meta, roles, exists = build_metadata(folder, True)
                upsert_db(db, folder, meta, exists)
                skipped += 1
                continue
            meta, roles, exists = build_metadata(folder, update_existing)
            chi_path.write_text(render_chi(folder, meta, roles, float(meta["confidence"])), encoding="utf-8")
            upsert_db(db, folder, meta, True)
            created += int(not exists)
            updated += int(exists)
        db.commit()
    finally:
        db.close()
    print(f"CHI scan complete: created={created}, updated={updated}, skipped={skipped}, root={root_path}")


def read(folder: str) -> None:
    chi_path = Path(folder) / CHI_NAME
    if not chi_path.exists():
        raise SystemExit(f"Missing {chi_path}")
    print(chi_path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate _folder.chi sidecars.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    scan_p = sub.add_parser("scan")
    scan_p.add_argument("root")
    scan_p.add_argument("--depth", type=int, default=3)
    scan_p.add_argument("--update", action="store_true")
    read_p = sub.add_parser("read")
    read_p.add_argument("folder")
    args = parser.parse_args()
    if args.cmd == "scan":
        scan(args.root, args.depth, args.update)
    elif args.cmd == "read":
        read(args.folder)


if __name__ == "__main__":
    main()
