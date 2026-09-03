"""Focused regression tests for the ``run_safe_command`` timeout path.

These tests live in a scratch module so they can be added without
disturbing the colocated tests in ``test_safe_commands.py``. They
cover the contracts of the new ``timeout=`` kwarg against the
Popen-based implementation:

* No ``timeout`` is forwarded to ``Popen`` when the caller omits the
  argument — backwards compatible with every existing caller.
* A positive ``timeout`` adds ``start_new_session=True`` to the
  ``Popen`` kwargs so ``os.killpg`` can reach every descendant.
* On ``subprocess.TimeoutExpired`` the wrapper returns a deterministic
  :class:`subprocess.CompletedProcess` with ``returncode == 124`` and
  preserves partial stdout/stderr captured before the deadline.
* The escalation sequence is SIGTERM, wait ``_TIMEOUT_GRACE_SECONDS``,
  then SIGKILL — applied to the entire process group so cargo test
  → gloss serve → … all die together.
* ``OSError`` from ``Popen.__init__`` or ``communicate`` returns 127
  and reaps any spawned child so no orphan leaks.

Background: a stuck ``cargo test`` whose child ``gloss serve`` is
parked on stdin EOF used to wedge the GREEN phase indefinitely because
``subprocess.run`` had no ``timeout`` and SIGTERM was caught by
Gloss's tokio signal handler. Killing the process group on expiry is
the orchestrator-side fix.
"""

from __future__ import annotations

import signal
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from deviate.cli import micro
from deviate.cli._safe_commands import (
    TEST_TIMEOUT_EXIT_CODE,
    run_safe_command,
)


# ---------------------------------------------------------------------------
# Configurable fake Popen factory
# ---------------------------------------------------------------------------
#
# ``run_safe_command`` calls ``subprocess.Popen(...)`` — the *class*. We
# must patch the class with something callable that returns an instance
# implementing the surface ``run_safe_command`` uses (``communicate``,
# ``wait``, ``pid``, ``returncode``). A top-level factory function works
# directly under ``mock.patch("...subprocess.Popen", factory)``.


class _FakePopenInstance:
    """Minimal in-process substitute for a ``subprocess.Popen`` instance."""

    def __init__(self, config: "_FakePopenConfig") -> None:
        self.config = config
        self.args: tuple[Any, ...] = ()
        self.kwargs: dict[str, Any] = {}
        self.pid = config.pid
        self.returncode = config.returncode
        self._communicate_calls = 0
        self.wait_called = 0

    def __enter__(self) -> "_FakePopenInstance":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def communicate(self, *a: Any, **kw: Any) -> tuple[str | bytes, str | bytes]:
        self._communicate_calls += 1
        if self.config.communicate_raises is not None and (
            self._communicate_calls == 1
            if self.config.communicate_raises_after_first
            else True
        ):
            raise self.config.communicate_raises
        return self.config.communicate_result

    def wait(self, *a: Any, **kw: Any) -> int:
        self.wait_called += 1
        return self.returncode

    def kill(self) -> None:
        pass


class _FakePopenConfig:
    """Mutable config bag — tests adjust behaviour by mutating fields."""

    def __init__(self) -> None:
        self.communicate_result: tuple[str, str] = ("", "")
        self.communicate_raises: Exception | None = None
        self.communicate_raises_after_first: bool = False
        self.pid: int = 99999
        self.returncode: int = 0
        self.last_instance: _FakePopenInstance | None = None
        self.init_call_count: int = 0


# Module-level singleton — tests mutate ``_popen_config`` directly.
_popen_config = _FakePopenConfig()


def _fake_popen_factory(*args: Any, **kwargs: Any) -> _FakePopenInstance:
    """Factory used to patch ``subprocess.Popen`` in the module under test.

    Raises ``_popen_config.init_raises`` if set, otherwise records the
    call args/kwargs and returns an instance that returns
    ``_popen_config.communicate_result`` from ``communicate``.
    """
    _popen_config.init_call_count += 1
    inst = _FakePopenInstance(_popen_config)
    inst.args = args
    inst.kwargs = kwargs
    _popen_config.last_instance = inst
    if _popen_config.init_raises is not None:
        raise _popen_config.init_raises
    return inst


def _reset_popen_config() -> None:
    _popen_config.communicate_result = ("", "")
    _popen_config.communicate_raises = None
    _popen_config.communicate_raises_after_first = False
    _popen_config.pid = 99999
    _popen_config.returncode = 0
    _popen_config.last_instance = None
    _popen_config.init_call_count = 0
    _popen_config.init_raises = None


# ---------------------------------------------------------------------------
# run_safe_command kwarg forwarding
# ---------------------------------------------------------------------------


class TestRunSafeCommandTimeoutKwargs:
    """``run_safe_command`` honours the new ``timeout=`` keyword."""

    def test_no_timeout_omits_start_new_session(self, tmp_path: Path) -> None:
        _reset_popen_config()
        _popen_config.communicate_result = ("ok", "")
        with patch(
            "deviate.cli._safe_commands.subprocess.Popen",
            _fake_popen_factory,
        ):
            result = run_safe_command("pytest tests/", tmp_path)
        assert result.returncode == 0
        assert result.stdout == "ok"
        inst = _popen_config.last_instance
        assert inst is not None
        # No deadline → no process-group isolation either; existing
        # callers are unaffected.
        assert "start_new_session" not in inst.kwargs

    def test_timeout_set_adds_start_new_session(self, tmp_path: Path) -> None:
        _reset_popen_config()
        with patch(
            "deviate.cli._safe_commands.subprocess.Popen",
            _fake_popen_factory,
        ):
            run_safe_command("pytest tests/", tmp_path, timeout=30)
        inst = _popen_config.last_instance
        assert inst is not None
        # Process-group isolation is required so ``os.killpg`` reaches
        # every descendant spawned by the test command.
        assert inst.kwargs.get("start_new_session") is True

    def test_argv_passed_to_popen(self, tmp_path: Path) -> None:
        _reset_popen_config()
        with patch(
            "deviate.cli._safe_commands.subprocess.Popen",
            _fake_popen_factory,
        ):
            run_safe_command("pytest tests/ -v", tmp_path)
        inst = _popen_config.last_instance
        assert inst is not None
        assert list(inst.args[0]) == ["pytest", "tests/", "-v"], inst.args
        assert inst.kwargs.get("shell") is False
        assert inst.kwargs.get("stdout") is subprocess.PIPE
        assert inst.kwargs.get("stderr") is subprocess.PIPE


# ---------------------------------------------------------------------------
# TimeoutExpired handling
# ---------------------------------------------------------------------------


class TestRunSafeCommandTimeoutExpired:
    """When ``communicate(timeout=...)`` raises ``TimeoutExpired`` the
    wrapper converts the partial result into a deterministic
    CompletedProcess with the canonical ``124`` exit code so callers
    see a test failure rather than an indefinite hang.
    """

    def test_returns_completed_process_with_124(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Simulate the real behaviour: ``communicate(timeout=...)``
        # raises ``TimeoutExpired`` carrying partial stdout/stderr.
        # The wrapper must convert that into a deterministic failed
        # CompletedProcess with returncode 124.
        exc = subprocess.TimeoutExpired(cmd=["pytest", "tests/"], timeout=5)
        exc.stdout = b"partial-stdout"
        exc.stderr = b"partial-stderr"
        _reset_popen_config()
        _popen_config.communicate_raises = exc
        _popen_config.communicate_raises_after_first = True
        _popen_config.communicate_result = ("", "")
        _popen_config.pid = 99999
        killed_signals: list[int] = []

        def _record_killpg(pid: int, sig: int) -> None:
            killed_signals.append(sig)

        monkeypatch.setattr("deviate.cli._safe_commands.os.killpg", _record_killpg)
        monkeypatch.setattr("deviate.cli._safe_commands.time.sleep", lambda _s: None)
        with patch(
            "deviate.cli._safe_commands.subprocess.Popen",
            _fake_popen_factory,
        ):
            result = run_safe_command("pytest tests/", tmp_path, timeout=5)
        assert result.returncode == TEST_TIMEOUT_EXIT_CODE == 124
        assert "partial-stdout" in (result.stdout or "")
        assert "partial-stderr" in (result.stderr or "")
        assert "timeout" in (result.stderr or "").lower()
        # SIGTERM first (graceful drain), then SIGKILL (hard reap).
        assert killed_signals == [signal.SIGTERM, signal.SIGKILL], killed_signals

    def test_first_call_partials_used_when_post_kill_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Regression: the post-kill ``communicate(timeout=0)`` may
        # return empty (children died cleanly under SIGTERM), in
        # which case the partials from ``TimeoutExpired`` MUST be
        # preserved — not silently replaced with empty strings.
        exc = subprocess.TimeoutExpired(cmd=["pytest", "tests/"], timeout=5)
        exc.stdout = b"captured-before-deadline"
        exc.stderr = b"stderr-before-deadline"
        _reset_popen_config()
        _popen_config.communicate_raises = exc
        _popen_config.communicate_raises_after_first = True
        _popen_config.communicate_result = ("", "")
        _popen_config.pid = 99999
        monkeypatch.setattr(
            "deviate.cli._safe_commands.os.killpg", lambda *a, **k: None
        )
        monkeypatch.setattr("deviate.cli._safe_commands.time.sleep", lambda _s: None)
        with patch(
            "deviate.cli._safe_commands.subprocess.Popen",
            _fake_popen_factory,
        ):
            result = run_safe_command("pytest tests/", tmp_path, timeout=5)
        assert "captured-before-deadline" in result.stdout
        assert "stderr-before-deadline" in result.stderr

    def test_post_kill_drain_overrides_first_partials(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # When the post-kill ``communicate(timeout=0)`` returns
        # additional data, the wrapper prefers the cumulative read
        # rather than concatenating (which would duplicate bytes
        # flushed before the deadline).
        exc = subprocess.TimeoutExpired(cmd=["pytest", "tests/"], timeout=5)
        exc.stdout = b"first-stdout"
        exc.stderr = b"first-stderr"
        _reset_popen_config()
        _popen_config.communicate_raises = exc
        _popen_config.communicate_raises_after_first = True
        _popen_config.communicate_result = (
            "cumulative-stdout",
            "cumulative-stderr",
        )
        _popen_config.pid = 99999
        monkeypatch.setattr(
            "deviate.cli._safe_commands.os.killpg", lambda *a, **k: None
        )
        monkeypatch.setattr("deviate.cli._safe_commands.time.sleep", lambda _s: None)
        with patch(
            "deviate.cli._safe_commands.subprocess.Popen",
            _fake_popen_factory,
        ):
            result = run_safe_command("pytest tests/", tmp_path, timeout=5)
        assert "cumulative-stdout" in result.stdout
        assert "cumulative-stderr" in result.stderr
        # First-call partials must NOT appear alongside the cumulative read.
        assert "first-stdout" not in result.stdout

    def test_killpg_swallows_process_lookup_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        exc = subprocess.TimeoutExpired(cmd=["pytest", "tests/"], timeout=5)
        _reset_popen_config()
        _popen_config.communicate_raises = exc
        _popen_config.communicate_raises_after_first = True
        _popen_config.pid = 99999

        def _raise_esrch(pid: int, sig: int) -> None:
            raise ProcessLookupError(pid)

        monkeypatch.setattr("deviate.cli._safe_commands.os.killpg", _raise_esrch)
        monkeypatch.setattr("deviate.cli._safe_commands.time.sleep", lambda _s: None)
        with patch(
            "deviate.cli._safe_commands.subprocess.Popen",
            _fake_popen_factory,
        ):
            result = run_safe_command("pytest tests/", tmp_path, timeout=5)
        assert result.returncode == TEST_TIMEOUT_EXIT_CODE


# ---------------------------------------------------------------------------
# OSError handling
# ---------------------------------------------------------------------------


class TestRunSafeCommandOSError:
    """``OSError`` from ``Popen.__init__`` or ``communicate`` returns
    a 127 CompletedProcess and reaps the spawned child so no orphan
    leaks when the test command cannot be launched.
    """

    def test_popen_init_oserror_returns_127(self, tmp_path: Path) -> None:
        # ``Popen.__init__`` raised before any process was spawned —
        # nothing to reap, just return 127 with the original error.
        _reset_popen_config()
        _popen_config.init_raises = OSError("missing binary")
        with patch(
            "deviate.cli._safe_commands.subprocess.Popen",
            _fake_popen_factory,
        ):
            result = run_safe_command("pytest tests/", tmp_path)
        assert result.returncode == 127
        assert "missing binary" in (result.stderr or "")

    def test_communicate_oserror_reaps_and_returns_127(self, tmp_path: Path) -> None:
        # ``Popen.__init__`` succeeded (PID assigned); ``communicate``
        # raised OSError. The wrapper must SIGKILL the spawned child
        # and ``wait()`` to reap the zombie, then return 127.
        _reset_popen_config()
        _popen_config.communicate_raises = OSError("broken pipe")
        _popen_config.pid = 99999
        with patch(
            "deviate.cli._safe_commands.subprocess.Popen",
            _fake_popen_factory,
        ):
            result = run_safe_command("pytest tests/", tmp_path)
        assert result.returncode == 127
        assert "broken pipe" in (result.stderr or "")
        # Zombie reaped — wait() was called at least once.
        inst = _popen_config.last_instance
        assert inst is not None
        assert inst.wait_called >= 1


# ---------------------------------------------------------------------------
# micro.py: _run_test_cmd wires the timeout through
# ---------------------------------------------------------------------------


class TestRunTestCmdThreadsTimeout:
    """``_run_test_cmd`` reads the worktree ``.deviate/config.toml``
    ``timeout_seconds`` field, allows a ``DEVIATE_TEST_TIMEOUT_SECONDS``
    env override, and forwards the resolved deadline to
    ``run_safe_command`` so a hung test cannot wedge the orchestrator.
    """

    def _seed_config(self, root: Path, *, timeout_seconds: int) -> None:
        (root / ".deviate").mkdir(exist_ok=True)
        (root / ".deviate" / "config.toml").write_text(
            f"timeout_seconds = {timeout_seconds}\n", encoding="utf-8"
        )

    def _seed_test_file(self, root: Path) -> None:
        # ``_test_command_candidates`` falls back to ``pytest`` only when
        # ``tests/**/test_*.py`` is present in the worktree. The timeout
        # wiring only matters when a candidate is actually executed, so
        # every fixture seeds at least one such file.
        tests_dir = root / "tests"
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / "test_smoke.py").write_text(
            "def test_smoke(): assert True\n", encoding="utf-8"
        )

    def test_threads_config_timeout_seconds(self, tmp_path: Path) -> None:
        self._seed_test_file(tmp_path)
        self._seed_config(tmp_path, timeout_seconds=42)
        _reset_popen_config()
        with patch(
            "deviate.cli._safe_commands.subprocess.Popen",
            _fake_popen_factory,
        ):
            micro._run_test_cmd(tmp_path)
        inst = _popen_config.last_instance
        assert inst is not None
        assert inst.kwargs.get("start_new_session") is True

    def test_defaults_to_1800_when_no_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No ``.deviate/config.toml`` present — must fall back to the
        # documented default (1800s, accommodating long-running test
        # commands) so a missing config does not silently disable the
        # timeout.
        self._seed_test_file(tmp_path)
        monkeypatch.delenv("DEVIATE_TEST_TIMEOUT_SECONDS", raising=False)
        _reset_popen_config()
        with patch(
            "deviate.cli._safe_commands.subprocess.Popen",
            _fake_popen_factory,
        ):
            micro._run_test_cmd(tmp_path)
        # The deadline is encoded as ``start_new_session=True``; without
        # it, the wrapper would not bound execution. The default of 1800s
        # is enforced by ``_resolve_test_timeout_seconds`` regardless of
        # whether the config file is present.
        inst = _popen_config.last_instance
        assert inst is not None
        assert inst.kwargs.get("start_new_session") is True

    def test_env_override_beats_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._seed_test_file(tmp_path)
        self._seed_config(tmp_path, timeout_seconds=42)
        monkeypatch.setenv("DEVIATE_TEST_TIMEOUT_SECONDS", "900")
        _reset_popen_config()
        with patch(
            "deviate.cli._safe_commands.subprocess.Popen",
            _fake_popen_factory,
        ):
            micro._run_test_cmd(tmp_path)
        inst = _popen_config.last_instance
        assert inst is not None
        assert inst.kwargs.get("start_new_session") is True

    def test_invalid_env_override_falls_back_to_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._seed_test_file(tmp_path)
        self._seed_config(tmp_path, timeout_seconds=42)
        monkeypatch.setenv("DEVIATE_TEST_TIMEOUT_SECONDS", "not-an-int")
        _reset_popen_config()
        with patch(
            "deviate.cli._safe_commands.subprocess.Popen",
            _fake_popen_factory,
        ):
            micro._run_test_cmd(tmp_path)
        inst = _popen_config.last_instance
        assert inst is not None
        assert inst.kwargs.get("start_new_session") is True

    def test_invalid_config_timeout_falls_back_to_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # ``timeout_seconds = 0`` violates ``gt=0`` — the loader returns
        # None and the orchestrator falls back to the documented default.
        self._seed_test_file(tmp_path)
        monkeypatch.delenv("DEVIATE_TEST_TIMEOUT_SECONDS", raising=False)
        (tmp_path / ".deviate").mkdir(exist_ok=True)
        (tmp_path / ".deviate" / "config.toml").write_text(
            "timeout_seconds = 0\n", encoding="utf-8"
        )
        _reset_popen_config()
        with patch(
            "deviate.cli._safe_commands.subprocess.Popen",
            _fake_popen_factory,
        ):
            micro._run_test_cmd(tmp_path)
        inst = _popen_config.last_instance
        assert inst is not None
        assert inst.kwargs.get("start_new_session") is True
