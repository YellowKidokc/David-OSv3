"""Decision boundary for master classification.

This module has no network or filesystem side effects.  It decides whether a
local classification is sufficient, whether DeepSeek should be consulted, and
whether the resulting metadata may continue cleanly, provisionally, or only
after human review.  Carrying forward never authorizes a move or rename.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ClassificationThresholds:
    local_accept_clean: float = 0.90
    deepseek_accept_clean: float = 0.90
    deepseek_accept_flagged: float = 0.60

    def __post_init__(self) -> None:
        values = (
            self.local_accept_clean,
            self.deepseek_accept_clean,
            self.deepseek_accept_flagged,
        )
        if any(value < 0 or value > 1 for value in values):
            raise ValueError("classification thresholds must be between 0 and 1")
        if self.deepseek_accept_flagged > self.deepseek_accept_clean:
            raise ValueError("flagged threshold cannot exceed clean threshold")


@dataclass(frozen=True)
class ClassificationDecision:
    state: str
    label: str | None
    confidence: float
    source: str
    carry_forward: bool
    notify: bool
    needs_deepseek: bool
    provisional: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _confidence(value: object) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _label(result: Mapping[str, Any] | None) -> str | None:
    if not result:
        return None
    value = result.get("label") or result.get("value") or result.get("category")
    if value is None:
        return None
    text = str(value).strip()
    return text if text and text.casefold() not in {"unknown", "unclassified", "none"} else None


def decide_classification(
    local: Mapping[str, Any],
    deepseek: Mapping[str, Any] | None = None,
    thresholds: ClassificationThresholds | None = None,
) -> ClassificationDecision:
    """Return the next governed state for one file's classification metadata."""
    limits = thresholds or ClassificationThresholds()
    local_label = _label(local)
    local_confidence = _confidence(local.get("confidence"))

    if local_label and local_confidence >= limits.local_accept_clean:
        return ClassificationDecision(
            "carry_clean", local_label, local_confidence, "local", True, False, False, False,
            "local classifier met the clean acceptance threshold",
        )

    if deepseek is None:
        return ClassificationDecision(
            "request_deepseek", local_label, local_confidence, "local", False, False, True, False,
            "local classifier was unknown or below the clean threshold",
        )

    deepseek_label = _label(deepseek)
    deepseek_confidence = _confidence(deepseek.get("confidence"))
    needs_human = bool(deepseek.get("needs_human"))

    if deepseek_label and not needs_human and deepseek_confidence >= limits.deepseek_accept_clean:
        return ClassificationDecision(
            "carry_clean", deepseek_label, deepseek_confidence, "deepseek", True, False, False, False,
            "DeepSeek met the clean acceptance threshold",
        )

    if deepseek_label and not needs_human and deepseek_confidence >= limits.deepseek_accept_flagged:
        return ClassificationDecision(
            "carry_flagged", deepseek_label, deepseek_confidence, "deepseek", True, True, False, True,
            "DeepSeek met the provisional threshold; human review remains open",
        )

    return ClassificationDecision(
        "hold_for_review", deepseek_label or local_label, deepseek_confidence, "deepseek",
        False, True, False, False,
        "classification remained uncertain or DeepSeek requested human judgment",
    )
