from pathlib import Path

import pytest

from engine.routing_predicates import decision_concordance, evaluate, prominence_receipt, require_passed_receipt


def test_explicit_title_layers_outweigh_body(tmp_path: Path):
    source = tmp_path / "01_Landauer Boundary.md"
    source.write_text("---\ntitle: Landauer Boundary\n---\n# Landauer Boundary\n\narchive " * 20, encoding="utf-8")
    receipt = prominence_receipt(source, ["landauer", "archive"])
    scores = {row["field"]: row["score"] for row in receipt["layers"]}
    assert scores["filename"] > scores.get("body", 0)
    assert scores["frontmatter_title"] > scores.get("body", 0)


def test_partial_numbered_series_is_held(tmp_path: Path):
    first, second = tmp_path / "01_First.md", tmp_path / "02_Second.md"
    first.write_text("# First", encoding="utf-8")
    second.write_text("# Second", encoding="utf-8")
    target = tmp_path / "out" / first.name
    receipt = evaluate(first, target, batch_targets={str(first): str(target)}, human_approved=True, undo_planned=True)
    assert receipt["verdict"] == "HOLD"
    series = next(row for row in receipt["predicates"] if row["predicate"] == "RP02_SERIES_INTEGRITY")
    assert series["state"] == "HOLD"


def test_complete_series_and_governance_pass(tmp_path: Path):
    first, second = tmp_path / "Law 1 Love.md", tmp_path / "Law 2 Joy.md"
    first.write_text("# Love", encoding="utf-8")
    second.write_text("# Joy", encoding="utf-8")
    out = tmp_path / "out"
    target = out / first.name
    receipt = evaluate(first, target,
                       batch_targets={str(first): str(target), str(second): str(out / second.name)},
                       human_approved=True, undo_planned=True)
    assert receipt["verdict"] == "PASS"
    payload = {"routing_predicates": receipt, "routing_predicates_reviewed": True}
    assert require_passed_receipt(payload, first, target) == receipt


def test_unreviewed_receipt_cannot_execute(tmp_path: Path):
    source = tmp_path / "note.md"
    source.write_text("# Note", encoding="utf-8")
    target = tmp_path / "out" / source.name
    receipt = evaluate(source, target, batch_targets={str(source): str(target)}, human_approved=True, undo_planned=True)
    with pytest.raises(ValueError, match="has not been reviewed"):
        require_passed_receipt({"routing_predicates": receipt}, source, target)


def test_content_and_lineage_agreement_passes():
    result = decision_concordance(
        {"destination": "CURRENT/V3", "confidence": 0.8, "evidence": ["canonical declaration"]},
        {"destination": "current\\v3", "confidence": 0.9, "evidence": ["supersedes v2"]},
    )
    assert result.state.value == "PASS"
    assert result.evidence["joint_confidence"] == 0.98


def test_content_and_lineage_disagreement_holds():
    result = decision_concordance(
        {"destination": "CURRENT/V3", "confidence": 0.9},
        {"destination": "ARCHIVE/V1", "confidence": 0.9},
    )
    assert result.state.value == "HOLD"
    assert "different destinations" in result.reason


def test_single_or_weak_arrow_holds():
    single = decision_concordance({"destination": "CURRENT/V3", "confidence": 0.9}, None)
    weak = decision_concordance(
        {"destination": "CURRENT/V3", "confidence": 0.9},
        {"destination": "CURRENT/V3", "confidence": 0.3},
    )
    assert single.state.value == "HOLD"
    assert weak.state.value == "HOLD"
