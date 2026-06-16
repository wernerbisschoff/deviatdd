from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CacheStore:
    model: str
    tool_definitions: list = field(default_factory=list)
    system_prompt: str = ""
    test_files: dict[str, str] = field(default_factory=dict)


class CacheDisciplineViolation(Exception):
    pass


class CacheDiscipline:
    @staticmethod
    def _check_drift(
        current_val: object,
        previous_val: object,
        label: str,
        message: str,
    ) -> None:
        if current_val != previous_val:
            raise CacheDisciplineViolation(message)

    @staticmethod
    def validate(
        phase: str,
        current: CacheStore,
        previous: CacheStore | None = None,
        repo_path: str | None = None,
    ) -> None:
        if previous is None:
            return

        CacheDiscipline._check_drift(
            current.model,
            previous.model,
            "model",
            f"model_switch: {previous.model} -> {current.model}",
        )

        CacheDiscipline._check_drift(
            current.tool_definitions,
            previous.tool_definitions,
            "tool_definitions",
            "tool_change: tool definitions differ between phases",
        )

        CacheDiscipline._check_drift(
            current.system_prompt,
            previous.system_prompt,
            "system_prompt",
            "prompt_change: system prompt mutated between phases",
        )

        CacheDiscipline._check_drift(
            current.test_files,
            previous.test_files,
            "test_files",
            "test_change: test files modified between phases",
        )
