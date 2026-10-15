import json
import sys
from pathlib import Path

CLS = Path(__file__).resolve().parents[1] / "03_CLASSIFY" / "02_CLASSIFICATION"
sys.path.insert(0, str(CLS))
from harness.adapters import gate_events  # noqa: E402

def _write_ledger(p, rows):
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

def test_reads_overrides_as_events(tmp_path):
    lg = tmp_path / "file_events.jsonl"
    _write_ledger(lg, [
        {"ts": "2026-10-15T10:00:00", "event": "gate_override",
         "path": "D:/x/a.md", "folder": "D:/x", "action_id": "rename",
         "verdict": "ask", "choice": "approve_once"},
        {"ts": "2026-10-15T10:01:00", "event": "something_else", "path": "D:/x/b.md"},
    ])
    evs = gate_events.read(lg)
    assert len(evs) == 1
    assert evs[0].subject == "D:/x"
    assert evs[0].action == "gate:override"
    assert evs[0].context["choice"] == "approve_once"

def test_stable_ids_no_double_count(tmp_path):
    lg = tmp_path / "file_events.jsonl"
    row = {"ts": "2026-10-15T10:00:00", "event": "gate_override", "path": "D:/x/a.md",
           "folder": "D:/x", "action_id": "rename", "verdict": "ask", "choice": "reject"}
    _write_ledger(lg, [row])
    first = gate_events.read(lg)[0].id
    assert gate_events.read(lg)[0].id == first
    assert first.startswith("go-")

def test_missing_ledger_returns_empty(tmp_path):
    assert gate_events.read(tmp_path / "nope.jsonl") == []
