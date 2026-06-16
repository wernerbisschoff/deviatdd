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
    def validate(
        phase: str,
        current: CacheStore,
        previous: CacheStore | None = None,
        repo_path: str | None = None,
    ) -> None:
        if previous is None:
            return

        if current.model != previous.model:
            raise CacheDisciplineViolation(
                f"model_switch: {previous.model} -> {current.model}"
            )

        if current.tool_definitions != previous.tool_definitions:
            raise CacheDisciplineViolation(
                "tool_change: tool definitions differ between phases"
            )

        if current.system_prompt != previous.system_prompt:
            raise CacheDisciplineViolation(
                "prompt_change: system prompt mutated between phases"
            )

        if current.test_files != previous.test_files:
            raise CacheDisciplineViolation(
                "test_change: test files modified between phases"
            )
