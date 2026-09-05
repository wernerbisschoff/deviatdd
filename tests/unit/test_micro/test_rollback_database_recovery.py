"""RED: JUDGE rollback database recovery hook (TSK-044-01).

AC-PLAN-001: migration-bearing revert runs the recovery hook.
AC-PLAN-004: non-migration revert skips the hook, trace unchanged.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from tests.conftest import _git_env


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit_file(repo: Path, rel: str, content: str, msg: str) -> str:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    subprocess.run(
        ["git", "add", rel], cwd=repo, env=_git_env(), check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    return _head(repo)


class _HookCapture:
    """Wrap subprocess.run: git goes through, non-git calls are hook probes."""

    def __init__(self, real_run) -> None:
        self.real_run = real_run
        self.hook_calls: list[tuple[list[str], dict]] = []

    def __call__(self, cmd, **kwargs):
        argv = list(cmd) if isinstance(cmd, (list, tuple)) else [str(cmd)]
        if argv and argv[0] == "git":
            return self.real_run(cmd, **kwargs)
        self.hook_calls.append((argv, kwargs))
        return CompletedProcess(argv, 0, stdout="recovered", stderr="")


def _run_rollback_with_capture(repo: Path, monkeypatch, boundary: str):
    import deviate.cli.micro as micro

    real_run = subprocess.run
    capture = _HookCapture(real_run)
    monkeypatch.setattr(micro.subprocess, "run", capture)
    monkeypatch.setattr(
        micro, "_run_pytest", lambda *a, **k: CompletedProcess([], 0, "", "")
    )
    trace = micro._execute_rollback(
        repo,
        boundary_sha=boundary,
        reason="judge revert",
        phase="JUDGE",
        task_id="TSK-044-01",
        attempt=1,
    )
    return trace, capture


@pytest.mark.behavioral
def test_migration_path_constant_covers_layouts() -> None:
    import deviate.cli.micro as micro

    patterns = getattr(micro, "MIGRATION_PATH_PATTERNS", None)
    assert patterns is not None, "MIGRATION_PATH_PATTERNS is missing"
    joined = " ".join(str(p) for p in patterns)
    assert "alembic/versions" in joined
    assert "migrations" in joined
    assert "db/migrate" in joined


@pytest.mark.behavioral
def test_migration_bearing_revert_runs_hook(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given a reverted diff touching a migration path, the hook runs."""
    (tmp_git_repo / ".deviate").mkdir(parents=True, exist_ok=True)
    (tmp_git_repo / ".deviate" / "config.toml").write_text(
        '[rollback]\ncommand = ["fake-recovery-hook"]\ntimeout_seconds = 30\n',
        encoding="utf-8",
    )
    boundary = _head(tmp_git_repo)
    _commit_file(tmp_git_repo, "alembic/versions/abc.py", "x = 1\n", "green migration")

    trace, capture = _run_rollback_with_capture(tmp_git_repo, monkeypatch, boundary)

    assert len(capture.hook_calls) == 1, "recovery hook did not run"
    argv, kwargs = capture.hook_calls[0]
    assert argv == ["fake-recovery-hook"]
    env = kwargs.get("env", {})
    assert env.get("DEVIATE_ROLLBACK_BOUNDARY_SHA") == boundary
    assert env.get("DEVIATE_ROLLBACK_TASK_ID") == "TSK-044-01"
    assert trace.reset_to == boundary


@pytest.mark.behavioral
def test_non_migration_revert_skips_hook(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given a reverted diff with zero migration paths, no hook runs."""
    (tmp_git_repo / ".deviate").mkdir(parents=True, exist_ok=True)
    (tmp_git_repo / ".deviate" / "config.toml").write_text(
        '[rollback]\ncommand = ["fake-recovery-hook"]\ntimeout_seconds = 30\n',
        encoding="utf-8",
    )
    boundary = _head(tmp_git_repo)
    _commit_file(tmp_git_repo, "docs/notes.md", "# hi\n", "green docs")

    trace, capture = _run_rollback_with_capture(tmp_git_repo, monkeypatch, boundary)

    assert capture.hook_calls == [], "hook must not run on non-migration revert"
    assert trace.reset_to == boundary
    assert trace.head_sha != trace.reset_to


@pytest.mark.behavioral
def test_missing_hook_raises_named_error_at_boundary(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Migration revert with zero hook stops naming hook plus manual action."""
    import deviate.cli.micro as micro

    boundary = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_git_repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _commit_file(tmp_git_repo, "alembic/versions/b.py", "y = 2\n", "green mig 2")
    monkeypatch.setattr(
        micro, "_run_pytest", lambda *a, **k: CompletedProcess([], 0, "", "")
    )
    with pytest.raises(
        micro.PhaseFailedError, match="ROLLBACK_RECOVERY_HOOK_MISSING"
    ) as ei:
        micro._execute_rollback(
            tmp_git_repo,
            boundary_sha=boundary,
            reason="judge revert",
            phase="JUDGE",
            task_id="TSK-044-02",
            attempt=1,
        )
    assert "[rollback]" in str(ei.value)
    assert "manually restore the isolated database" in str(ei.value)
    assert boundary in str(ei.value)
    head_now = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_git_repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert head_now == boundary


@pytest.mark.behavioral
def test_hook_failure_attaches_output(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-zero hook exit raises with hook output attached, never silent."""
    import deviate.cli.micro as micro

    (tmp_git_repo / ".deviate").mkdir(parents=True, exist_ok=True)
    (tmp_git_repo / ".deviate" / "config.toml").write_text(
        '[rollback]\ncommand = ["fake-recovery-hook"]\ntimeout_seconds = 30\n',
        encoding="utf-8",
    )
    boundary = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_git_repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _commit_file(tmp_git_repo, "migrations/001.py", "z = 3\n", "green mig 3")
    real_run = subprocess.run

    def fake_run(cmd, **kwargs):
        argv = list(cmd) if isinstance(cmd, (list, tuple)) else [str(cmd)]
        if argv and argv[0] == "git":
            return real_run(cmd, **kwargs)
        assert isinstance(cmd, (list, tuple)), (
            "hook must run via arg list without shell"
        )
        assert kwargs.get("shell") is not True
        return CompletedProcess(argv, 1, stdout="boom-out", stderr="boom-err")

    monkeypatch.setattr(micro.subprocess, "run", fake_run)
    monkeypatch.setattr(
        micro, "_run_pytest", lambda *a, **k: CompletedProcess([], 0, "", "")
    )
    with pytest.raises(micro.PhaseFailedError) as ei:
        micro._execute_rollback(
            tmp_git_repo,
            boundary_sha=boundary,
            reason="judge revert",
            phase="JUDGE",
            task_id="TSK-044-02",
            attempt=1,
        )
    assert "ROLLBACK_RECOVERY_HOOK_FAILED" in str(ei.value)
    assert "boom-out" in str(ei.value)
    assert "fake-recovery-hook" in str(ei.value)
    assert boundary in str(ei.value)
    head_now = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_git_repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert head_now == boundary


@pytest.mark.behavioral
def test_hook_timeout_attaches_output(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hook timeout raises loudly with output attached."""
    import deviate.cli.micro as micro

    (tmp_git_repo / ".deviate").mkdir(parents=True, exist_ok=True)
    (tmp_git_repo / ".deviate" / "config.toml").write_text(
        '[rollback]\ncommand = ["fake-recovery-hook"]\ntimeout_seconds = 5\n',
        encoding="utf-8",
    )
    boundary = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_git_repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _commit_file(tmp_git_repo, "db/migrate/001.py", "w = 4\n", "green mig 4")
    real_run = subprocess.run

    def fake_run(cmd, **kwargs):
        argv = list(cmd) if isinstance(cmd, (list, tuple)) else [str(cmd)]
        if argv and argv[0] == "git":
            return real_run(cmd, **kwargs)
        raise subprocess.TimeoutExpired(
            cmd, 5, output="partial-out", stderr="partial-err"
        )

    monkeypatch.setattr(micro.subprocess, "run", fake_run)
    monkeypatch.setattr(
        micro, "_run_pytest", lambda *a, **k: CompletedProcess([], 0, "", "")
    )
    with pytest.raises(micro.PhaseFailedError) as ei:
        micro._execute_rollback(
            tmp_git_repo,
            boundary_sha=boundary,
            reason="judge revert",
            phase="JUDGE",
            task_id="TSK-044-02",
            attempt=1,
        )
    assert "ROLLBACK_RECOVERY_HOOK_FAILED" in str(ei.value)
    assert "fake-recovery-hook" in str(ei.value)
    assert "partial-out" in str(ei.value)
    assert boundary in str(ei.value)
    head_now = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_git_repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert head_now == boundary


@pytest.mark.behavioral
def test_boundary_refusals_unchanged(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing or stale boundary SHA keeps current ROLLBACK_* refusal text."""
    import deviate.cli.micro as micro

    monkeypatch.setattr(
        micro, "_run_pytest", lambda *a, **k: CompletedProcess([], 0, "", "")
    )
    with pytest.raises(micro.PhaseFailedError, match="ROLLBACK_BOUNDARY_MISSING"):
        micro._execute_rollback(
            tmp_git_repo,
            boundary_sha="  ",
            reason="judge revert",
            phase="JUDGE",
            task_id="TSK-044-02",
            attempt=1,
        )
    with pytest.raises(micro.PhaseFailedError, match="ROLLBACK_STALE_BOUNDARY"):
        micro._execute_rollback(
            tmp_git_repo,
            boundary_sha="0" * 40,
            reason="judge revert",
            phase="JUDGE",
            task_id="TSK-044-02",
            attempt=1,
        )


@pytest.mark.behavioral
def test_mise_test_reset_fallback_runs_without_config_hook(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Migration revert with test:reset task but zero [rollback] hook runs mise."""
    import deviate.cli.micro as micro

    (tmp_git_repo / "mise.toml").write_text(
        '[tasks."test:reset"]\nrun = "echo reset"\n', encoding="utf-8"
    )
    _commit_file(
        tmp_git_repo,
        "mise.toml",
        '[tasks."test:reset"]\nrun = "echo reset"\n',
        "add test:reset",
    )
    boundary = _head(tmp_git_repo)
    _commit_file(tmp_git_repo, "alembic/versions/c.py", "z = 3\n", "green mig 3")
    real_run = subprocess.run
    capture = _HookCapture(real_run)
    monkeypatch.setattr(micro.subprocess, "run", capture)
    monkeypatch.setattr(
        micro, "_run_pytest", lambda *a, **k: CompletedProcess([], 0, "", "")
    )
    micro._execute_rollback(
        tmp_git_repo,
        boundary_sha=boundary,
        reason="judge revert",
        phase="JUDGE",
        task_id="TSK-044-02",
        attempt=1,
    )
    assert capture.hook_calls, "test:reset fallback did not run"
    argv, kwargs = capture.hook_calls[0]
    assert argv == ["mise", "run", "test:reset"]
    assert kwargs.get("timeout") == 300
    assert kwargs["env"]["DEVIATE_ROLLBACK_BOUNDARY_SHA"] == boundary
