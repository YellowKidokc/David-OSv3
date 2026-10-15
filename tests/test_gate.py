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

def test_blocked_floor_blocks_mutations():
    d = make_gate({"approval_floor": "blocked"}).evaluate("rename", ["a/b.txt"], {"batch_size": 1})
    assert d.verdict == g.BLOCK
    assert any("approval_floor" in r["rule_id"] for r in d.fired_rules)

def test_auto_after_threshold_allows_small_batch():
    d = make_gate({"approval_floor": "auto_after_threshold"}).evaluate(
        "rename", ["a/b.txt"], {"batch_size": 1})
    assert d.verdict == g.ALLOW  # thresholds (review gates) didn't fire; floor permits

def test_profile_protected_flag_reaches_action_conditions():
    d = make_gate({"protected": True, "approval_floor": "preview_only"}).evaluate(
        "rename", ["a/b.txt"], {"batch_size": 1})
    assert d.verdict == g.ASK
    assert any("protected" in r["reason"].lower() for r in d.fired_rules)

def test_no_profile_uses_action_default_floor():
    # rulebook says rename/move/delete default to approval_required; with no profile
    # the folder is unknown, so the action default is the floor — never ALLOW a mutation blind
    for action in ("rename", "move", "archive", "delete_later"):
        d = make_gate().evaluate(action, ["a/b.txt"], {"batch_size": 1})
        assert d.verdict in (g.ASK, g.BLOCK), action

def test_explicit_profile_floor_beats_action_default():
    d = make_gate({"approval_floor": "preview_only"}).evaluate(
        "move", ["a/b.txt"], {"batch_size": 1})
    assert d.verdict == g.PREVIEW
