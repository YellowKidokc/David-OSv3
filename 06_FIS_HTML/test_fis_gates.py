import json
from pathlib import Path
from unittest import mock

import pytest

import fis_gates as g


def make_vault(tmp: Path) -> Path:
    v = tmp / "vault"
    (v / ".obsidian").mkdir(parents=True)
    (v / ".obsidian" / "app.json").write_text("{}")
    n = v / "notes"
    n.mkdir()
    (n / "paper.md").write_text("---\nid: 1\ncard: card.json\n---\nbody")
    (n / "card.json").write_text('{"a":1}')
    (n / "table.xlsx").write_bytes(b"xx")
    (n / "view.base").write_text("{}")
    (n / "map.canvas").write_text("{}")
    (n / "OBSIDIAN_REGISTRY.html").write_text("<p>page</p>")
    (n / "FIS.html").write_text("<p>old</p>")
    s = v / "kimi_axiom_series"
    s.mkdir()
    (s / "a.html").write_text('<a href="b.html">b</a>')
    (s / "b.html").write_text("x")
    return v


def test_gate1_stops_when_disk_full(tmp_path):
    with mock.patch("fis_gates.free_gb", return_value=0.0):
        with pytest.raises(g.GateError, match="Gate 1"):
            g.check_space(tmp_path)


def test_gate3_protected():
    assert g.is_protected(Path("v/.obsidian/app.json"))
    assert g.is_protected(Path("v/x.base")) and g.is_protected(Path("v/x.canvas"))
    assert not g.is_protected(Path("v/x.json"))


def test_gate2_built_set_detected_by_sibling_links(tmp_path):
    d = tmp_path / "plain"
    d.mkdir()
    (d / "a.html").write_text('<a href="b.html">b</a>')
    (d / "b.html").write_text("x")
    assert g.is_built_set(d)
    (d / "a.html").write_text('<a href="https://x.com">x</a>')
    assert not g.is_built_set(d)


def test_gate5_lane_and_conflict(tmp_path):
    v = make_vault(tmp_path)
    rep = g.page_report(v / "notes")
    assert rep["lane"] == "obsidian" and rep["page"] == "OBSIDIAN_REGISTRY.html"
    assert rep["extra_pages_found"] == ["FIS.html"]
    assert g.lane_for(tmp_path) == "fis"


def test_gate4_simulate_apply_undo(tmp_path):
    v = make_vault(tmp_path)
    receipt = g.simulate(v, out_dir=tmp_path / "r")
    r = json.loads(receipt.read_text())
    names = sorted(Path(m["src"]).name for m in r["moves"])
    assert names == ["card.json", "table.xlsx"]  # no .base/.canvas/.obsidian/pages/built set
    assert any("built set" in s["reason"] for s in r["skipped"])
    assert r["frontmatter_rewrites"][0]["new"] == ".data/card.json"
    assert (v / "notes" / "card.json").exists()  # simulation moved nothing

    undo_file = g.apply_receipt(receipt)
    n = v / "notes"
    assert (n / ".data" / "card.json").exists() and not (n / "card.json").exists()
    assert "card: .data/card.json" in (n / "paper.md").read_text()
    assert (n / "view.base").exists() and (v / ".obsidian" / "app.json").exists()

    assert g.undo(undo_file) == 2
    assert (n / "card.json").exists() and "card: card.json" in (n / "paper.md").read_text()


def test_gate4_refuses_changed_file(tmp_path):
    v = make_vault(tmp_path)
    receipt = g.simulate(v, out_dir=tmp_path / "r")
    (v / "notes" / "card.json").write_text("changed")
    with pytest.raises(g.GateError, match="changed since simulation"):
        g.apply_receipt(receipt)
