"""Real-process integration test for ``run_safe_command`` timeout.

Spawns an actual ``pytest`` process whose test code ignores SIGTERM
and forks a grandchild that also ignores SIGTERM — mirroring the
Gloss hang shape (tokio's signal handler refused to unstick the
MCP loop, so the immediate child stayed parked on stdin EOF). The
orchestrator's process-group SIGKILL escalation must terminate the
whole subtree. ``os.kill(pid, 0)`` confirms both PIDs cease to
exist (no orphan descendants survive).

This is the proof the retained-PID ``Popen`` refactor addresses the
original GREEN-phase hang. If a future refactor moves back to
``subprocess.run`` (which does not reliably populate
``TimeoutExpired.pid``) or skips the killpg escalation, the
process-exit assertions below will fail.
"""

from __future__ import annotations

import os
import shutil
import signal
import tempfile
import textwrap
import time
from pathlib import Path

import pytest

from deviate.cli._safe_commands import (
    TEST_TIMEOUT_EXIT_CODE,
    run_safe_command,
)


# Only run on POSIX (killpg semantics differ on Windows).
if os.name != "posix":
    pytest.skip("requires POSIX process-group semantics", allow_module_level=True)


def _pid_is_alive(pid: int) -> bool:
    """Return True iff ``pid`` exists. ``os.kill(pid, 0)`` semantics."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we can't signal it — still alive.
        return True
    return True


def _read_pid_after_delay(path: Path, deadline_s: float) -> int | None:
    """Poll *path* for a non-empty PID file until the deadline elapses."""
    end = time.monotonic() + deadline_s
    while time.monotonic() < end:
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
            if text:
                try:
                    return int(text)
                except ValueError:
                    pass
        time.sleep(0.05)
    return None


def test_run_safe_command_kills_sigterm_ignoring_descendants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: spawn pytest that ignores SIGTERM, fork a SIGTERM-
    ignoring grandchild, bound by ``run_safe_command(timeout=...)``.
    After the deadline the whole subtree MUST be reaped.
    """
    # Compress the production SIGTERM→SIGKILL grace window from 5s to
    # 0.2s so the whole suite stays under the <30s performance budget;
    # the test only needs to prove killpg reaches the grandchild.
    monkeypatch.setattr("deviate.cli._safe_commands._TIMEOUT_GRACE_SECONDS", 0.2)
    workdir = Path(tempfile.mkdtemp(prefix="deviate-test-"))
    parent_pid_file = workdir / "parent.pid"
    grandchild_pid_file = workdir / "grandchild.pid"
    tests_dir = workdir / "tests"
    tests_dir.mkdir(exist_ok=True)
    body = textwrap.dedent(
        f"""
        import os, signal, sys, time

        PARENT_PID_FILE  = {str(parent_pid_file)!r}
        GRANDCHILD_PID_FILE = {str(grandchild_pid_file)!r}

        def test_fork_and_hang():
            with open(PARENT_PID_FILE, 'w') as f:
                f.write(str(os.getpid()))
                f.flush(); os.fsync(f.fileno())
            pid = os.fork()
            if pid == 0:
                # Grandchild — only SIGKILL can reap this.
                with open(GRANDCHILD_PID_FILE, 'w') as f:
                    f.write(str(os.getpid()))
                    f.flush(); os.fsync(f.fileno())
                signal.signal(signal.SIGTERM, lambda *a, **k: None)
                time.sleep(300)
                sys.exit(0)
            # Parent ignores SIGTERM too — mirrors tokio's drain.
            signal.signal(signal.SIGTERM, lambda *a, **k: None)
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass
            time.sleep(300)
        """
    ).strip()
    (tests_dir / "test_fork_hang.py").write_text(body, encoding="utf-8")

    deadline_seconds = 3.0
    captured: dict[str, int | None] = {"parent": None, "grandchild": None}
    try:
        start = time.monotonic()
        result = run_safe_command(
            "pytest",
            workdir,
            timeout=deadline_seconds,
        )
        elapsed = time.monotonic() - start

        # Deterministic timeout sentinel.
        assert result.returncode == TEST_TIMEOUT_EXIT_CODE
        # Deadline + compressed 0.2s grace. The 2s upper bound keeps
        # a future regression from silently re-introducing a long
        # sleep between SIGTERM and SIGKILL.
        assert elapsed >= deadline_seconds, elapsed
        assert elapsed < deadline_seconds + 2.0, elapsed
        assert "timeout" in (result.stderr or "").lower()

        # Both PID files must have been written before the deadline.
        captured["parent"] = _read_pid_after_delay(parent_pid_file, 5.0)
        captured["grandchild"] = _read_pid_after_delay(grandchild_pid_file, 5.0)
        assert captured["parent"] is not None, (
            f"parent never wrote its PID file; stderr={result.stderr!r}"
        )
        assert captured["grandchild"] is not None, (
            f"grandchild never wrote its PID file; stderr={result.stderr!r}"
        )
        parent_pid = captured["parent"]
        grandchild_pid = captured["grandchild"]
        assert parent_pid != grandchild_pid
        # Both must be reaped by SIGKILL escalation. Brief settle so
        # the kernel finishes reaping after SIGKILL.
        time.sleep(1.0)
        parent_alive = _pid_is_alive(parent_pid)
        grandchild_alive = _pid_is_alive(grandchild_pid)
        assert not parent_alive, (
            f"parent PID {parent_pid} still alive after SIGKILL escalation "
            f"(elapsed={elapsed:.2f}s); SIGTERM was ignored as expected but "
            f"SIGKILL must reach it. grandchild_alive={grandchild_alive}"
        )
        assert not grandchild_alive, (
            f"grandchild PID {grandchild_pid} still alive — SIGKILL did not "
            f"reach the orphaned grandchild (process group was not reaped). "
            f"parent_alive={parent_alive}"
        )
    finally:
        # Belt-and-braces: SIGKILL anything still alive so a failed
        # assertion cannot leak a 300-second sleep loop.
        for pid in (captured["parent"], captured["grandchild"]):
            if pid is not None and _pid_is_alive(pid):
                try:
                    os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
        shutil.rmtree(workdir, ignore_errors=True)
