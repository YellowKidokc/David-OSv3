import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "engine"))
import gate as g  # noqa: E402

RULES = REPO / "config" / "rules"

def make_gate(profile=None):
    return g.Gate.load(RULES, profile or {})

def test_clean_rename_in_permissive_folder_allows_or_previews():
    d = make_gate({"approval_floor": "preview_only"}).evaluate(
        "rename", ["some/folder/a.md", "some/folder/b.md"], {"batch_size": 2})
    assert d.verdict in (g.ALLOW, g.PREVIEW)

def test_env_file_hard_blocks_whole_batch():
    d = make_gate().evaluate("rename", ["x/.env", "x/notes.md"], {"batch_size": 2})
    assert d.verdict == g.BLOCK
    assert any(r["rule_id"] == "GR-004" for r in d.fired_rules)

def test_system_folder_hard_blocks():
    d = make_gate().evaluate("move", [r"C:\Windows\System32\drivers\etc\hosts"], {})
    assert d.verdict == g.BLOCK
    assert any(r["rule_id"] == "GR-001" for r in d.fired_rules)

def test_project_root_rename_asks():
    d = make_gate().evaluate("rename", ["repo/pyproject.toml"], {"batch_size": 1})
    assert d.verdict == g.ASK
    assert any(r["rule_id"] == "GR-003" for r in d.fired_rules)

def test_bulk_threshold_asks():
    paths = [f"inbox/file{i:02d}.txt" for i in range(21)]
    d = make_gate().evaluate("rename", paths, {"batch_size": 21})
    assert d.verdict == g.ASK
    assert any("bulk" in r["reason"].lower() or ">" in r["reason"] for r in d.fired_rules)

def test_profile_blocked_action_asks_not_blocks():
    d = make_gate({"blocked_actions": ["move"]}).evaluate("move", ["a/b.txt"], {"batch_size": 1})
    assert d.verdict == g.ASK
    assert any("profile" in r["rule_id"].lower() for r in d.fired_rules)

def test_irrelevant_action_drops():
    d = make_gate({"irrelevant_actions": ["dedupe"]}).evaluate("dedupe", ["a/b.txt"], {})
    assert d.verdict == g.DROP

def test_missing_profile_fails_closed():
    d = make_gate({}).evaluate("delete_later", ["a/b.txt"], {"batch_size": 1})
    assert d.verdict in (g.ASK, g.BLOCK)   # never allow a delete with no profile

def test_corrupt_rules_fail_closed(tmp_path):
    bad = tmp_path / "rules"; bad.mkdir()
    (bad / "guardrails.v1.json").write_text("{not json", encoding="utf-8")
    gate = g.Gate.load(bad, {})
    assert gate.load_error is not None
    d = gate.evaluate("rename", ["a/b.txt"], {"batch_size": 1})
    assert d.verdict == g.ASK and any("load error" in r["reason"].lower() for r in d.fired_rules)

def test_decision_json_shape_stable():
    d = make_gate().evaluate("rename", ["a/b.txt"], {"batch_size": 1})
    j = d.to_json()
    assert set(j) == {"verdict", "fired_rules", "required_guardrails"}
    json.dumps(j)  # must be JSON-serializable (Rust contract)
