import json
from pathlib import Path

RULES = Path(__file__).resolve().parents[1] / "config" / "rules"


def _load(name):
    return json.loads((RULES / name).read_text(encoding="utf-8"))


def test_guardrails_complete():
    d = _load("guardrails.v1.json")
    assert d["schema"] == "top-ai-fis.guardrails.v1"
    ids = [r["guardrail_id"] for r in d["records"]]
    assert ids == [f"GR-{i:03d}" for i in range(1, 13)]
    gr4 = d["records"][3]
    assert "secrets" in gr4["name"].lower() or "secret" in gr4["description"].lower()


def test_actions_master_complete():
    d = _load("actions_master.v1.json")
    assert len(d["records"]) >= 32
    by_id = {r["action_id"]: r for r in d["records"]}
    assert by_id["delete_later"]["destructive_level"] == "high"
    assert by_id["run_script"]["destructive_level"] == "critical"


def test_action_conditions_and_compatibility():
    cond = _load("action_conditions.v1.json")
    assert len(cond["records"]) == 14
    rename = [r for r in cond["records"] if r.get("action_id") == "rename"]
    assert rename and "protected" in rename[0]["blocked_if"]
    compat = _load("compatibility_matrix.v1.json")
    assert len(compat["records"]) >= 24
