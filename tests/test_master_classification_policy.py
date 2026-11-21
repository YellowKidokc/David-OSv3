from engine.classification_policy import ClassificationThresholds, decide_classification


def test_high_local_confidence_carries_cleanly() -> None:
    result = decide_classification({"label": "research", "confidence": 0.94})
    assert result.state == "carry_clean"
    assert result.carry_forward is True
    assert result.notify is False
    assert result.source == "local"


def test_unknown_local_result_requests_deepseek() -> None:
    result = decide_classification({"label": "unknown", "confidence": 0.40})
    assert result.state == "request_deepseek"
    assert result.needs_deepseek is True
    assert result.carry_forward is False


def test_mid_confidence_deepseek_result_carries_and_flags() -> None:
    result = decide_classification(
        {"label": "unknown", "confidence": 0.40},
        {"value": "theophysics", "confidence": 0.78, "needs_human": False},
    )
    assert result.state == "carry_flagged"
    assert result.carry_forward is True
    assert result.provisional is True
    assert result.notify is True


def test_uncertain_deepseek_result_waits_for_human() -> None:
    result = decide_classification(
        {"label": "unknown", "confidence": 0.40},
        {"value": "theophysics", "confidence": 0.55, "needs_human": True},
    )
    assert result.state == "hold_for_review"
    assert result.carry_forward is False
    assert result.notify is True


def test_threshold_order_is_validated() -> None:
    try:
        ClassificationThresholds(deepseek_accept_clean=0.70, deepseek_accept_flagged=0.90)
    except ValueError as error:
        assert "flagged threshold" in str(error)
    else:
        raise AssertionError("invalid threshold order was accepted")
