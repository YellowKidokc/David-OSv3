import json
from pathlib import Path

import pytest

from tools.apply_routing_plan import load_plan, preflight


def test_preflight_accepts_unique_targets_inside_root(tmp_path: Path):
    source = tmp_path / "source.md"
    source.write_text("content", encoding="utf-8")
    target_root = tmp_path / "vault"
    target = target_root / "papers" / "source.md"
    rows = preflight([{"source_path": str(source), "proposed_destination": str(target)}], target_root)
    assert rows[0]["size"] == 7


def test_preflight_rejects_duplicate_targets(tmp_path: Path):
    one, two = tmp_path / "one.md", tmp_path / "two.md"
    one.write_text("one", encoding="utf-8")
    two.write_text("two", encoding="utf-8")
    root, target = tmp_path / "vault", tmp_path / "vault" / "same.md"
    with pytest.raises(ValueError, match="duplicate destination"):
        preflight([
            {"source_path": str(one), "proposed_destination": str(target)},
            {"source_path": str(two), "proposed_destination": str(target)},
        ], root)


def test_load_plan_requires_explicit_approval(tmp_path: Path):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"schema": "vault-transfer-plan/1", "items": [{"status": "PD"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="no approved items"):
        load_plan(path, False)
    _, selected = load_plan(path, True)
    assert len(selected) == 1
