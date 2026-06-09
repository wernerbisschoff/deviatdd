from __future__ import annotations

import enum
from pathlib import Path


class TamperContext(enum.Enum):
    RED_TEST_CREATION = "red_test_creation"
    GREEN_IMPLEMENTATION = "green_implementation"
    YELLOW_AMENDMENT = "yellow_amendment"


class TamperVerdict(enum.Enum):
    TAMPER_PASS = "tamper_pass"
    TAMPER_DETECTED = "tamper_detected"


class TamperGuard:
    @staticmethod
    def evaluate(
        context: TamperContext,
        repo_path: Path | None = None,
        approved_mods: list[str] | None = None,
    ) -> TamperVerdict:
        raise NotImplementedError

    @staticmethod
    def check(
        repo_path: Path | None = None,
        context: TamperContext | None = None,
        approved_mods: list[str] | None = None,
    ) -> TamperVerdict:
        raise NotImplementedError
