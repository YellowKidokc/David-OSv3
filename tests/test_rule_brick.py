import pytest

from rule_brick import RuleBrick, Signal, score_signals


def test_sparse_evidence_is_shrunk_toward_unknown():
    result = score_signals([Signal("folder_name", 1, 1.0, 1.0, "Parent is Master Equation")])
    assert result["score"] == 0.6
    assert result["coverage"] == 0.2


def test_conflicting_evidence_remains_visible():
    result = score_signals(
        [
            Signal("matching_code", 1, 2.0, 1.0, "ME aligns with Master Equation"),
            Signal("unrelated_media", -1, 1.0, 1.0, "Unrelated image set"),
        ]
    )
    assert result["support"] == 2.0
    assert result["opposition"] == 1.0
    assert 0.5 < result["score"] < 0.67


def test_before_prediction_after_lifecycle(tmp_path):
    brick = RuleBrick(tmp_path)
    before = brick.before_work(agent_id="codex", intent="inspect hierarchy", roots=["D:/Example"])
    prediction = brick.record_prediction(
        session_id=before["session_id"],
        question_id="name_fit",
        subject_path="D:/Example/MEQU.01.md",
        engine="test_engine",
        signals=[Signal("series", 1, 5.0, 1.0, "Ordered series corroborates code")],
        unknowns=["No backlink scan yet"],
        recommendation="keep current name",
    )
    assert prediction["score"] == 1.0
    receipt = brick.after_work(session_id=before["session_id"], status="complete", outcome="No changes")
    assert receipt["prediction_count"] == 1
    with pytest.raises(ValueError):
        brick.record_prediction(
            session_id=before["session_id"], question_id="name_fit",
            subject_path="x", engine="test", signals=[]
        )
    brick.close()
