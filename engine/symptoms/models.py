"""Public result types for folder symptom scans."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class SymptomResult:
    symptom_id: str
    name: str
    category: str
    severity: Severity
    path: Path
    message: str
    auto_fixable: bool = False
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = self.__dict__.copy()
        result["severity"] = self.severity.value
        result["path"] = str(self.path)
        return result


@dataclass
class SymptomReport:
    folder_path: Path
    results: list[SymptomResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.results)

    @property
    def by_severity(self) -> dict[str, int]:
        return {level.value: sum(r.severity is level for r in self.results) for level in Severity}

    def to_dict(self) -> dict[str, Any]:
        return {"folder_path": str(self.folder_path), "count": self.count,
                "by_severity": self.by_severity,
                "results": [result.to_dict() for result in self.results],
                "errors": list(self.errors)}
