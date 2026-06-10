from __future__ import annotations

import enum
import os
import subprocess
from pathlib import Path, PurePath


class TamperContext(enum.Enum):
    RED_TEST_CREATION = "red_test_creation"
    GREEN_IMPLEMENTATION = "green_implementation"
    YELLOW_AMENDMENT = "yellow_amendment"


class TamperVerdict(enum.Enum):
    TAMPER_PASS = "tamper_pass"
    TAMPER_DETECTED = "tamper_detected"


class TamperGuard:
    @staticmethod
    def _clean_env() -> dict[str, str]:
        return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

    @staticmethod
    def evaluate(
        context: TamperContext,
        repo_path: Path | None = None,
        approved_mods: list[str] | None = None,
    ) -> TamperVerdict:
        repo = repo_path or Path.cwd()
        approved = set(approved_mods or [])
        env = TamperGuard._clean_env()

        result = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
        )

        changed_files = [f.strip() for f in result.stdout.splitlines() if f.strip()]

        if not changed_files:
            return TamperVerdict.TAMPER_PASS

        detected = False
        for filepath in changed_files:
            if filepath in approved:
                continue
            if TamperGuard._is_protected(filepath, context):
                detected = True
                subprocess.run(
                    ["git", "restore", filepath],
                    cwd=repo,
                    env=env,
                    capture_output=True,
                )

        return TamperVerdict.TAMPER_DETECTED if detected else TamperVerdict.TAMPER_PASS

    @staticmethod
    def _is_test_file(filepath: str) -> bool:
        return PurePath(filepath).parts[0] == "tests"

    @staticmethod
    def _is_spec_file(filepath: str) -> bool:
        return PurePath(filepath).parts[0] == "specs"

    @staticmethod
    def _is_config_file(filepath: str) -> bool:
        return ".deviate" in PurePath(filepath).parts

    @staticmethod
    def _is_protected(filepath: str, context: TamperContext) -> bool:
        if context == TamperContext.RED_TEST_CREATION:
            return False
        return (
            TamperGuard._is_test_file(filepath)
            or TamperGuard._is_spec_file(filepath)
            or TamperGuard._is_config_file(filepath)
        )

    @staticmethod
    def check(
        repo_path: Path | None = None,
        context: TamperContext | None = None,
        approved_mods: list[str] | None = None,
    ) -> TamperVerdict:
        return TamperGuard.evaluate(
            context=context or TamperContext.GREEN_IMPLEMENTATION,
            repo_path=repo_path,
            approved_mods=approved_mods,
        )
