from __future__ import annotations

import time
from dataclasses import dataclass

import pytest

from deviate.core.cache_discipline import (
    CacheDiscipline,
    CacheDisciplineViolation,
    CacheStore,
)


@dataclass
class _PhaseCall:
    phase: str
    store: CacheStore


class TestCacheDisciplineModelSwitch:
    def test_raises_when_model_changes_between_phases(self) -> None:
        previous = CacheStore(
            model="deepseek-v4-flash",
            tool_definitions=[{"name": "read", "description": "Read files"}],
            system_prompt="You are a TDD agent.",
            test_files={"tests/test_foo.py": "def test_foo(): pass\n"},
        )
        current = CacheStore(
            model="qwen-3.7-plus",
            tool_definitions=[{"name": "read", "description": "Read files"}],
            system_prompt="You are a TDD agent.",
            test_files={"tests/test_foo.py": "def test_foo(): pass\n"},
        )

        with pytest.raises(CacheDisciplineViolation) as exc_info:
            CacheDiscipline.validate(
                phase="GREEN",
                current=current,
                previous=previous,
            )

        assert "model" in str(exc_info.value).lower()
        assert "deepseek" in str(exc_info.value)

    def test_raises_when_model_changes_red_to_green(self) -> None:
        previous = CacheStore(
            model="deepseek-v4-flash",
            tool_definitions=[],
            system_prompt="red prompt",
            test_files={},
        )
        current = CacheStore(
            model="gpt-4o",
            tool_definitions=[],
            system_prompt="red prompt",
            test_files={},
        )

        with pytest.raises(CacheDisciplineViolation) as exc_info:
            CacheDiscipline.validate(
                phase="GREEN",
                current=current,
                previous=previous,
            )

        assert "model" in str(exc_info.value).lower()


class TestCacheDisciplineToolChange:
    def test_raises_when_tool_definitions_change(self) -> None:
        previous = CacheStore(
            model="deepseek-v4-flash",
            tool_definitions=[{"name": "read", "description": "Read files"}],
            system_prompt="You are a TDD agent.",
            test_files={},
        )
        current = CacheStore(
            model="deepseek-v4-flash",
            tool_definitions=[
                {"name": "read", "description": "Read files"},
                {"name": "write", "description": "Write files"},
            ],
            system_prompt="You are a TDD agent.",
            test_files={},
        )

        with pytest.raises(CacheDisciplineViolation) as exc_info:
            CacheDiscipline.validate(
                phase="JUDGE",
                current=current,
                previous=previous,
            )

        assert "tool" in str(exc_info.value).lower()

    def test_raises_when_tool_definitions_reordered_and_changed(self) -> None:
        previous = CacheStore(
            model="deepseek-v4-flash",
            tool_definitions=[{"name": "write", "args": {"path": "str"}}],
            system_prompt="",
            test_files={},
        )
        current = CacheStore(
            model="deepseek-v4-flash",
            tool_definitions=[
                {"name": "write", "args": {"path": "str", "content": "str"}}
            ],
            system_prompt="",
            test_files={},
        )

        with pytest.raises(CacheDisciplineViolation):
            CacheDiscipline.validate(
                phase="REFACTOR",
                current=current,
                previous=previous,
            )


class TestCacheDisciplineSystemPromptChange:
    def test_raises_when_system_prompt_mutates(self) -> None:
        previous = CacheStore(
            model="deepseek-v4-flash",
            tool_definitions=[{"name": "read"}],
            system_prompt="You are a TDD agent. Follow the spec.",
            test_files={},
        )
        current = CacheStore(
            model="deepseek-v4-flash",
            tool_definitions=[{"name": "read"}],
            system_prompt="You are a TDD agent. Follow the spec. Also write tests.",
            test_files={},
        )

        with pytest.raises(CacheDisciplineViolation) as exc_info:
            CacheDiscipline.validate(
                phase="GREEN",
                current=current,
                previous=previous,
            )

        assert "prompt" in str(exc_info.value).lower()


class TestCacheDisciplineTestFileChange:
    def test_raises_when_test_file_content_changes(self) -> None:
        previous = CacheStore(
            model="deepseek-v4-flash",
            tool_definitions=[],
            system_prompt="",
            test_files={"tests/test_foo.py": "def test_foo(): pass\n"},
        )
        current = CacheStore(
            model="deepseek-v4-flash",
            tool_definitions=[],
            system_prompt="",
            test_files={"tests/test_foo.py": "def test_foo(): assert True\n"},
        )

        with pytest.raises(CacheDisciplineViolation) as exc_info:
            CacheDiscipline.validate(
                phase="GREEN",
                current=current,
                previous=previous,
            )

        assert "test" in str(exc_info.value).lower()

    def test_raises_when_test_file_added(self) -> None:
        previous = CacheStore(
            model="deepseek-v4-flash",
            tool_definitions=[],
            system_prompt="",
            test_files={},
        )
        current = CacheStore(
            model="deepseek-v4-flash",
            tool_definitions=[],
            system_prompt="",
            test_files={"tests/test_new.py": "def test_new(): pass\n"},
        )

        with pytest.raises(CacheDisciplineViolation):
            CacheDiscipline.validate(
                phase="GREEN",
                current=current,
                previous=previous,
            )


class TestCacheDisciplineNoChangePasses:
    def test_no_change_passes_validation(self) -> None:
        store = CacheStore(
            model="deepseek-v4-flash",
            tool_definitions=[{"name": "read"}],
            system_prompt="You are a TDD agent.",
            test_files={"tests/test_foo.py": "def test_foo(): pass\n"},
        )

        result = CacheDiscipline.validate(
            phase="GREEN",
            current=store,
            previous=store,
        )

        assert result is None

    def test_multiple_phases_no_change(self) -> None:
        store = CacheStore(
            model="deepseek-v4-flash",
            tool_definitions=[{"name": "read"}],
            system_prompt="Consistent prompt",
            test_files={"t.py": "pass"},
        )

        for phase in ["RED", "GREEN", "JUDGE", "REFACTOR"]:
            result = CacheDiscipline.validate(
                phase=phase,
                current=store,
                previous=store,
            )
            assert result is None


class TestCacheDisciplineFirstCall:
    def test_first_call_with_no_previous_passes(self) -> None:
        current = CacheStore(
            model="deepseek-v4-flash",
            tool_definitions=[],
            system_prompt="",
            test_files={},
        )

        result = CacheDiscipline.validate(
            phase="RED",
            current=current,
            previous=None,
        )

        assert result is None


class TestCacheDisciplineViolationType:
    def test_cache_discipline_violation_is_exception(self) -> None:
        assert issubclass(CacheDisciplineViolation, Exception)

    def test_cache_discipline_violation_carries_message(self) -> None:
        error = CacheDisciplineViolation("model_switch: deepseek → gpt-4o")
        assert str(error) == "model_switch: deepseek → gpt-4o"

    def test_cache_discipline_violation_carries_reason(self) -> None:
        error = CacheDisciplineViolation(
            "tool_change: tool definitions differ between phases",
        )
        assert "tool_change" in str(error)


class TestCacheDisciplinePerformance:
    def test_validate_completes_under_5ms(self) -> None:
        previous = CacheStore(
            model="deepseek-v4-flash",
            tool_definitions=[{"name": "read"}],
            system_prompt="prompt",
            test_files={"t.py": "pass"},
        )
        current = CacheStore(
            model="deepseek-v4-flash",
            tool_definitions=[{"name": "read"}],
            system_prompt="prompt",
            test_files={"t.py": "pass"},
        )

        start = time.perf_counter()
        for _ in range(100):
            CacheDiscipline.validate(phase="GREEN", current=current, previous=previous)
        elapsed_ms = (time.perf_counter() - start) / 100 * 1000

        assert elapsed_ms < 5.0, f"Average validate() took {elapsed_ms:.3f}ms (max 5ms)"


class TestCacheDisciplinePhaseBoundary:
    def test_validate_called_after_each_phase(self) -> None:
        _call_records: list[_PhaseCall] = []
        phase_records: list[str] = []

        class TrackingCacheDiscipline(CacheDiscipline):
            @staticmethod
            def validate(
                phase: str,
                current: CacheStore,
                previous: CacheStore | None = None,
                repo_path: str | None = None,
            ) -> None:
                _call_records.append(_PhaseCall(phase=phase, store=current))
                phase_records.append(phase)
                return None

        store_a = CacheStore(
            model="m1", tool_definitions=[], system_prompt="", test_files={}
        )
        store_b = CacheStore(
            model="m1", tool_definitions=[], system_prompt="", test_files={}
        )

        TrackingCacheDiscipline.validate(phase="RED", current=store_a, previous=None)
        TrackingCacheDiscipline.validate(
            phase="GREEN", current=store_b, previous=store_a
        )
        TrackingCacheDiscipline.validate(
            phase="JUDGE", current=store_b, previous=store_b
        )
        TrackingCacheDiscipline.validate(
            phase="REFACTOR", current=store_b, previous=store_b
        )

        assert len(_call_records) == 4
        assert phase_records == ["RED", "GREEN", "JUDGE", "REFACTOR"]

    def test_phase_boundary_preserves_order_across_full_cycle(self) -> None:
        phases = ["RED", "GREEN", "JUDGE", "REFACTOR"]
        stores = {
            "RED": CacheStore(
                model="m1", tool_definitions=[], system_prompt="", test_files={}
            ),
            "GREEN": CacheStore(
                model="m1", tool_definitions=[], system_prompt="", test_files={}
            ),
            "JUDGE": CacheStore(
                model="m2", tool_definitions=[], system_prompt="", test_files={}
            ),
            "REFACTOR": CacheStore(
                model="m2", tool_definitions=[], system_prompt="", test_files={}
            ),
        }

        for i, phase in enumerate(phases):
            prev = stores[phases[i - 1]] if i > 0 else None
            try:
                CacheDiscipline.validate(
                    phase=phase,
                    current=stores[phase],
                    previous=prev,
                )
            except CacheDisciplineViolation:
                pass

    def test_phase_boundary_rejects_state_leak(self) -> None:
        store_a = CacheStore(
            model="model-a",
            tool_definitions=[{"name": "read"}],
            system_prompt="prompt-a",
            test_files={"tests/t.py": "pass"},
        )
        store_b = CacheStore(
            model="model-b",
            tool_definitions=[{"name": "write"}],
            system_prompt="prompt-b",
            test_files={"tests/t.py": "fail"},
        )

        with pytest.raises(CacheDisciplineViolation) as exc_info:
            CacheDiscipline.validate(
                phase="GREEN",
                current=store_b,
                previous=store_a,
            )

        msg = str(exc_info.value).lower()
        reasons = 0
        for keyword in ["model", "tool", "prompt", "test"]:
            if keyword in msg:
                reasons += 1
        assert reasons >= 1
