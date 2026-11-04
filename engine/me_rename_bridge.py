"""Optional Master Equation intake -> Stage 2B sidecar/rename adapter.

The observe-only intake analyzer remains unchanged. This module only reads its
SQLite output and enriches Stage 2B records.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

import yaml

from engine.stage2b_common import REPO

REFERENCE = REPO / "config" / "master_equation_node.yaml"


def _variable_order() -> list[str]:
    data = yaml.safe_load(REFERENCE.read_text(encoding="utf-8"))
    variables = list((data or {}).get("variables", {}))
    expected = ["G", "M", "E", "S_eff", "T", "K", "R", "Q", "F", "C_W"]
    if variables != expected:
        raise ValueError(f"Canonical ME variable order changed: {variables!r}")
    return variables


VARIABLE_ORDER = _variable_order()
VARIABLE_NUMBER = {name: index + 1 for index, name in enumerate(VARIABLE_ORDER)}


def _decode(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return value
    try:
        result = json.loads(value)
        return result if isinstance(result, list) else []
    except (TypeError, json.JSONDecodeError):
        return [part.strip() for part in str(value).split(",") if part.strip()]


def read_intake(intake_db: str | Path, source_path: str | Path) -> dict[str, Any]:
    db = Path(intake_db).resolve()
    if not db.exists():
        return {}
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM file_instances WHERE source_path=?", (str(Path(source_path)),)
        ).fetchone()
    if row is None:
        return {}
    variables = [VARIABLE_NUMBER[name] for name in _decode(row["meq_variables_json"]) if name in VARIABLE_NUMBER]
    return {
        "me_variables": sorted(set(variables)),
        "me_primary": variables[0] if variables else None,
        "me_lane": row["source_lane"],
        "me_contamination": _decode(row["contamination_flags_json"]),
        "me_reference": str(REFERENCE),
    }


def add_name_context(proposed_name: str | None, me_primary: int | None) -> str | None:
    if not proposed_name or not me_primary:
        return proposed_name
    parts = proposed_name.split("__")
    if len(parts) < 5:
        return proposed_name
    tags = [tag for tag in parts[2].split("-") if tag]
    marker = f"me{me_primary}"
    if marker not in tags:
        tags.insert(0, marker)
    parts[2] = "-".join(tags)
    return "__".join(parts)


def update_work(con: sqlite3.Connection, version_id: str, enrichment: dict[str, Any]) -> None:
    if not enrichment or enrichment.get("me_primary") is None:
        return
    row = con.execute("SELECT work_id FROM versions WHERE version_id=?", (version_id,)).fetchone()
    if row:
        con.execute(
            "UPDATE works SET me_primary=?, me_variables=? WHERE work_id=?",
            (enrichment["me_primary"], ",".join(map(str, enrichment["me_variables"])), row["work_id"]),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("intake_db", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("--registry", type=Path, default=Path("_data/registry.sqlite"))
    args = parser.parse_args(argv)
    print(json.dumps(read_intake(args.intake_db, args.source), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

