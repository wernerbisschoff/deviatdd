"""Tests for ``deviate.tome.dispatch``.

The dispatch module shells out to a backend CLI. To keep tests fast
and hermetic, we monkey-patch ``BACKEND_COMMANDS`` to point at small
inline Python scripts that simulate backend behavior. Each test
exercises one branch of ``DispatchResult.status``.

The fake scripts read the prompt via stdin and the target file path
via the ``TOME_FAKE_TARGET`` env var (set in the parent process so
``subprocess.run`` inherits it).
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from deviate.tome import dispatch as dispatch_module
from deviate.tome.dispatch import DispatchResult, dispatch_writer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_writers_dir(tmp_path: Path) -> Path:
    """Create ``tmp_path/bin`` with several fake backend scripts.

    The fake backends are tiny Python scripts:

    - ``fake-write`` — reads the prompt from stdin, writes to the path
      in ``TOME_FAKE_TARGET`` (relative to its CWD), and exits 0.
    - ``fake-skip`` — drains stdin, exits 0, writes nothing.
    - ``fake-fail`` — drains stdin, exits 1 with a stderr message.
    - ``fake-hang`` — sleeps for 30s (used to test the timeout path).
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    (bin_dir / "fake-write").write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import os
            import sys
            from pathlib import Path

            target = os.environ.get("TOME_FAKE_TARGET", "")
            sys.stdin.read()
            if target:
                Path(target).parent.mkdir(parents=True, exist_ok=True)
                Path(target).write_text("# fake writer output\\n", encoding="utf-8")
            sys.exit(0)
            """
        )
    )
    (bin_dir / "fake-skip").write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import sys
            sys.stdin.read()
            sys.exit(0)
            """
        )
    )
    (bin_dir / "fake-fail").write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import sys
            sys.stdin.read()
            sys.stderr.write("backend exploded\\n")
            sys.exit(1)
            """
        )
    )
    (bin_dir / "fake-hang").write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import time
            time.sleep(30)
            """
        )
    )

    for script in bin_dir.iterdir():
        script.chmod(0o755)

    return bin_dir


@pytest.fixture
def work_dir(tmp_path: Path) -> Path:
    """A clean CWD where dispatch results can be observed."""
    cwd = tmp_path / "work"
    cwd.mkdir()
    return cwd


@pytest.fixture
def restore_backend_commands():
    """Save and restore ``BACKEND_COMMANDS`` around each test."""
    original = dict(dispatch_module.BACKEND_COMMANDS)
    yield
    dispatch_module.BACKEND_COMMANDS.clear()
    dispatch_module.BACKEND_COMMANDS.update(original)


def _reg(name: str, fake_writers_dir: Path, script_name: str) -> None:
    """Register a fake backend in the dispatch module's command map."""
    dispatch_module.BACKEND_COMMANDS[name] = [
        sys.executable,
        str(fake_writers_dir / script_name),
    ]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_dispatch_writer_writes_file_and_returns_done(
    work_dir: Path, fake_writers_dir: Path, restore_backend_commands, monkeypatch
) -> None:
    target = "docs/setup.md"
    monkeypatch.setenv("TOME_FAKE_TARGET", target)
    _reg("fakewrite", fake_writers_dir, "fake-write")
    result = dispatch_writer(
        backend="fakewrite",
        prompt="write the setup tutorial",
        target_file=target,
        cwd=work_dir,
    )
    assert result.status == "DONE"
    assert result.returncode == 0
    assert result.file_exists is True
    assert (work_dir / target).exists()


def test_dispatch_writer_passes_prompt_via_stdin(
    work_dir: Path, fake_writers_dir: Path, restore_backend_commands, monkeypatch
) -> None:
    monkeypatch.setenv("TOME_FAKE_TARGET", "docs/x.md")
    _reg("fakewrite", fake_writers_dir, "fake-write")
    result = dispatch_writer(
        backend="fakewrite",
        prompt="hello world",
        target_file="docs/x.md",
        cwd=work_dir,
    )
    assert result.returncode == 0
    assert result.status == "DONE"


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


def test_dispatch_writer_unknown_backend_raises() -> None:
    with pytest.raises(ValueError, match="Unknown backend"):
        dispatch_writer(
            backend="not-a-real-backend",
            prompt="x",
            target_file="x.md",
            cwd=Path("/tmp"),
        )


def test_dispatch_writer_missing_binary_returns_fail(
    work_dir: Path, restore_backend_commands
) -> None:
    # Point the backend at a path that definitely doesn't exist.
    dispatch_module.BACKEND_COMMANDS["definitely-missing"] = [
        "/nonexistent/path/does-not-exist-binary-xyz"
    ]
    result = dispatch_writer(
        backend="definitely-missing",
        prompt="x",
        target_file="docs/x.md",
        cwd=work_dir,
        timeout=10,
    )
    assert result.status == "FAIL"
    assert "BINARY_NOT_FOUND" in result.stderr_tail


def test_dispatch_writer_nonzero_exit_returns_fail(
    work_dir: Path, fake_writers_dir: Path, restore_backend_commands
) -> None:
    _reg("fakefail", fake_writers_dir, "fake-fail")
    result = dispatch_writer(
        backend="fakefail",
        prompt="x",
        target_file="docs/x.md",
        cwd=work_dir,
        timeout=10,
    )
    assert result.status == "FAIL"
    assert result.returncode == 1
    assert "backend exploded" in result.stderr_tail


def test_dispatch_writer_zero_exit_but_no_file_returns_missing(
    work_dir: Path, fake_writers_dir: Path, restore_backend_commands
) -> None:
    _reg("fakeskip", fake_writers_dir, "fake-skip")
    result = dispatch_writer(
        backend="fakeskip",
        prompt="x",
        target_file="docs/missing.md",
        cwd=work_dir,
        timeout=10,
    )
    assert result.status == "MISSING"
    assert result.returncode == 0
    assert result.file_exists is False


def test_dispatch_writer_timeout_returns_timed_out(
    work_dir: Path, fake_writers_dir: Path, restore_backend_commands
) -> None:
    _reg("fakehang", fake_writers_dir, "fake-hang")
    result = dispatch_writer(
        backend="fakehang",
        prompt="x",
        target_file="docs/x.md",
        cwd=work_dir,
        timeout=2,
    )
    assert result.status == "TIMEOUT"
    assert result.timed_out is True


def test_dispatch_writer_empty_target_file_skips_existence_check(
    work_dir: Path, fake_writers_dir: Path, restore_backend_commands, monkeypatch
) -> None:
    monkeypatch.delenv("TOME_FAKE_TARGET", raising=False)
    _reg("fakewrite", fake_writers_dir, "fake-write")
    result = dispatch_writer(
        backend="fakewrite",
        prompt="x",
        target_file="",
        cwd=work_dir,
    )
    # With an empty target_file, the file_exists check is skipped,
    # but the fake backend wrote nothing because TOME_FAKE_TARGET is unset.
    assert result.file_exists is False
    assert result.status in {"MISSING", "DONE"}


# ---------------------------------------------------------------------------
# DispatchResult.status property
# ---------------------------------------------------------------------------


def test_dispatch_result_status_property() -> None:
    base = dict(
        target_file="x.md",
        stdout_tail="",
        stderr_tail="",
        duration_seconds=0.1,
    )
    assert DispatchResult(returncode=0, file_exists=True, **base).status == "DONE"
    assert DispatchResult(returncode=1, file_exists=False, **base).status == "FAIL"
    assert DispatchResult(returncode=0, file_exists=False, **base).status == "MISSING"
    assert (
        DispatchResult(returncode=-1, file_exists=False, timed_out=True, **base).status
        == "TIMEOUT"
    )


# ---------------------------------------------------------------------------
# SIGINT / Ctrl+C handling
# ---------------------------------------------------------------------------


def test_dispatch_writer_killable_via_kill_all_running_procs(
    work_dir: Path, fake_writers_dir: Path, restore_backend_commands
) -> None:
    """``kill_all_running_procs()`` must terminate a hang-ing dispatch mid-flight.

    Simulates the SIGINT handler firing while ``dispatch_writer`` is waiting
    on ``proc.communicate``. The tracked Popen should be killed and the
    function should return (with a FAIL or TIMEOUT status, not hang).
    """
    import threading
    import time

    from deviate.tome.dispatch import (
        _RUNNING_PROCS,
        _RUNNING_PROCS_LOCK,
        kill_all_running_procs,
    )

    _reg("fakehang", fake_writers_dir, "fake-hang")

    # Launch the dispatch in a worker thread so the test can fire
    # kill_all_running_procs() while it's blocked in proc.communicate().
    result_box: dict = {}

    def _runner() -> None:
        result_box["result"] = dispatch_writer(
            backend="fakehang",
            prompt="x",
            target_file="docs/x.md",
            cwd=work_dir,
            timeout=30,
        )

    t = threading.Thread(target=_runner, daemon=True)
    t.start()

    # Wait for the Popen to register itself in _RUNNING_PROCS.
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        with _RUNNING_PROCS_LOCK:
            if _RUNNING_PROCS:
                break
        time.sleep(0.01)

    with _RUNNING_PROCS_LOCK:
        procs_before = len(_RUNNING_PROCS)
    assert procs_before >= 1, "dispatch did not register its Popen"

    killed = kill_all_running_procs()
    assert killed >= 1

    t.join(timeout=5.0)
    assert not t.is_alive(), "dispatch_writer did not return after kill"

    with _RUNNING_PROCS_LOCK:
        procs_after = len(_RUNNING_PROCS)
    assert procs_after == 0, f"_RUNNING_PROCS should be drained, got {procs_after}"

    result = result_box["result"]
    # The subprocess was killed; status is FAIL (non-zero returncode) or
    # TIMEOUT if the per-row timeout happened to elapse first.
    assert result.status in {"FAIL", "TIMEOUT"}
