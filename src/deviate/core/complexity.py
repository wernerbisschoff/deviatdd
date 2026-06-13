from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = [
    "ClassificationResult",
    "ComplexityGate",
]


@dataclass(frozen=True)
class ClassificationResult:
    level: Literal["LOW", "MEDIUM", "HIGH"]
    execution_mode: Literal["DIRECT", "TDD"]


class ComplexityGate:
    _CLASSIFICATION_TABLE = {
        "LOW": ClassificationResult(level="LOW", execution_mode="DIRECT"),
        "MEDIUM": ClassificationResult(level="MEDIUM", execution_mode="DIRECT"),
        "HIGH": ClassificationResult(level="HIGH", execution_mode="TDD"),
    }

    @classmethod
    def classify(
        cls,
        description: str,
        _stub: str | None = None,
    ) -> ClassificationResult:
        if _stub is not None:
            if _stub not in cls._CLASSIFICATION_TABLE:
                raise ValueError(f"Unknown stub value: {_stub}")
            return cls._CLASSIFICATION_TABLE[_stub]

        return cls._CLASSIFICATION_TABLE["LOW"]
