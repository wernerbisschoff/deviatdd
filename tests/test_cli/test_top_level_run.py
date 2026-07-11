"""Tests for the top-level ``deviate run`` orchestrator.

The new ``deviate run`` is the canonical "go do the next thing" command:
it chains ``deviate meso run`` (which claims the next BACKLOG issue and
creates a per-issue worktree) with ``deviate micro run --all`` (which
drains every PENDING task inside that worktree). This module pins the
orchestration contract so the meso-then-micro contract cannot silently
regress to "run meso only" or "run micro only".
"""

from __future__ import annotations

from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from deviate.cli import cli

runner = CliRunner()


def test_top_level_run_help_lists_orchestrator():
    """``deviate run --help`` documents the full-pipeline orchestrator
    and surfaces the new flag surface (--issue, --force, --profile,
    --no-judge, --no-refactor, --agent, --json).

    These flags are forwarded to the underlying `deviate meso run`
    (--issue, --force) and `deviate micro run --all` (the rest).
    """
    result = runner.invoke(cli, ["run", "--help"])
    assert result.exit_code == 0, result.output

    # Forwarded meso flags
    assert "--issue" in result.output, "--issue must be accepted on `deviate run`"
    assert "--force" in result.output, "--force must be accepted on `deviate run`"

    # Forwarded micro flags
    assert "--profile" in result.output, (
        "--profile must be accepted on `deviate run` (forwarded to micro)"
    )
    assert "--no-judge" in result.output, (
        "--no-judge must be accepted on `deviate run` (forwarded to micro)"
    )
    assert "--no-refactor" in result.output, (
        "--no-refactor must be accepted on `deviate run` (forwarded to micro)"
    )
    assert "--agent" in result.output, (
        "--agent must be accepted on `deviate run` (forwarded to micro)"
    )
    assert "--json" in result.output, (
        "--json must be accepted on `deviate run` (forwarded to micro)"
    )


def test_top_level_run_help_mentions_micro_run():
    """``deviate run --help`` must mention ``deviate micro run`` so
    operators who try to drain a single task or pass ``--all`` at the
    top level discover the new micro subcommand.
    """
    result = runner.invoke(cli, ["run", "--help"])
    assert "`deviate micro run`" in result.output, (
        "Top-level `deviate run --help` must surface the micro subcommand "
        "so operators find the per-task drain path."
    )


def test_top_level_run_chains_meso_then_micro(tmp_git_repo: Path) -> None:
    """End-to-end: ``deviate run`` must call ``_meso_run`` first, capture
    the worktree path it returns, then dispatch ``_run_all`` inside that
    worktree.

    This is the load-bearing orchestration contract. If either side of
    the chain (meso or micro) is skipped, or the chdir boundary is
    removed, the orchestrator regresses to half a pipeline and a real
    user invocation hangs or claims an issue without draining tasks.
    """
    worktree_path = tmp_git_repo / ".worktrees" / "feat" / "demo" / "demo"
    worktree_path.mkdir(parents=True, exist_ok=True)

    call_log: list[str] = []

    def fake_meso_run(*args, **kwargs):
        call_log.append("_meso_run")
        # Mirrors the real contract: _meso_run returns the worktree path
        # on success and exits with SystemExit(1) on hard failure.
        return str(worktree_path)

    def fake_run_all(*args, **kwargs):
        call_log.append("_run_all")

    # A no-op pre-flight: top-level `deviate run` runs in the repo root,
    # so we need .deviate/ + session.json present for the orchestrator's
    # session-update branch to be a no-op rather than a hard fail.
    dot_dir = tmp_git_repo / ".deviate"
    dot_dir.mkdir(exist_ok=True)
    from deviate.state.config import SessionState

    session = SessionState(current_phase="IDLE")
    session.save(dot_dir / "session.json")

    # Avoid having the orchestrator try to talk to a real agent backend.
    with chdir(tmp_git_repo):
        with (
            patch("deviate.cli._meso_run", side_effect=fake_meso_run),
            patch("deviate.cli._run_all", side_effect=fake_run_all),
        ):
            result = runner.invoke(cli, ["run"])

    assert result.exit_code == 0, (
        f"Expected clean exit from chained orchestrator, got "
        f"{result.exit_code}: {result.output}"
    )

    # Order: meso MUST run before micro. The orchestrator's contract
    # is "set up the worktree first, then drain it" — flipping the
    # order would dispatch `micro run --all` against an empty main
    # checkout, missing every task the meso step just claimed.
    assert call_log == ["_meso_run", "_run_all"], (
        f"Orchestrator must call _meso_run before _run_all; got {call_log}"
    )

    # The "MICRO_DRAIN" banner announces the worktree entry — its
    # absence means the chdir/branch step was skipped.
    assert "MICRO_DRAIN" in result.output, (
        f"Expected the MICRO_DRAIN banner that signals the worktree "
        f"handoff; output was:\n{result.output}"
    )


def test_top_level_run_exits_when_meso_returns_no_worktree(tmp_git_repo: Path) -> None:
    """If ``_meso_run`` returns no worktree path (e.g. dry-run consumed
    the return value), the orchestrator must surface RUN_NO_WORKTREE
    and exit non-zero rather than crash dereferencing ``None``.
    """
    dot_dir = tmp_git_repo / ".deviate"
    dot_dir.mkdir(exist_ok=True)
    from deviate.state.config import SessionState

    session = SessionState(current_phase="IDLE")
    session.save(dot_dir / "session.json")

    def fake_meso_run_no_path(*args, **kwargs):
        return None

    with chdir(tmp_git_repo):
        with (
            patch("deviate.cli._meso_run", side_effect=fake_meso_run_no_path),
            patch("deviate.cli._run_all") as mock_run_all,
        ):
            result = runner.invoke(cli, ["run"])

    assert result.exit_code != 0, (
        f"Expected non-zero exit when meso returns no worktree; got {result.output}"
    )
    assert "RUN_NO_WORKTREE" in result.output, (
        f"Expected RUN_NO_WORKTREE signal so operators can distinguish "
        f"'meso had nothing to do' from a real error; got:\n{result.output}"
    )
    # Micro drain must NOT have been dispatched — without a worktree,
    # `_run_all` would run against the main checkout and miss every
    # task the (non-)meso step was supposed to claim.
    mock_run_all.assert_not_called()


def test_top_level_run_exits_when_worktree_missing(tmp_git_repo: Path) -> None:
    """If ``_meso_run`` returns a path that does not exist on disk
    (e.g. the user deleted the worktree between meso and micro), the
    orchestrator must surface RUN_WORKTREE_MISSING and exit non-zero
    rather than crash on the chdir.
    """
    dot_dir = tmp_git_repo / ".deviate"
    dot_dir.mkdir(exist_ok=True)
    from deviate.state.config import SessionState

    session = SessionState(current_phase="IDLE")
    session.save(dot_dir / "session.json")

    fake_path = "/tmp/deviate-this-worktree-should-not-exist-12345"

    def fake_meso_run_missing_path(*args, **kwargs):
        return fake_path

    with chdir(tmp_git_repo):
        with (
            patch("deviate.cli._meso_run", side_effect=fake_meso_run_missing_path),
            patch("deviate.cli._run_all") as mock_run_all,
        ):
            result = runner.invoke(cli, ["run"])

    assert result.exit_code != 0, (
        f"Expected non-zero exit when worktree path is missing; got {result.output}"
    )
    assert "RUN_WORKTREE_MISSING" in result.output, (
        f"Expected RUN_WORKTREE_MISSING signal so operators can recover; "
        f"got:\n{result.output}"
    )
    assert fake_path in result.output, (
        f"Error message should mention the missing path; got: {result.output}"
    )
    mock_run_all.assert_not_called()


def test_top_level_run_forwards_profile_to_micro(tmp_git_repo: Path) -> None:
    """``--profile fast`` must reach ``_run_all`` so the micro drain
    skips JUDGE and REFACTOR. Without forwarding, an operator who
    asked for a fast drain would still pay the full TDD cycle.
    """
    worktree_path = tmp_git_repo / ".worktrees" / "feat" / "demo" / "demo"
    worktree_path.mkdir(parents=True, exist_ok=True)

    dot_dir = tmp_git_repo / ".deviate"
    dot_dir.mkdir(exist_ok=True)
    from deviate.state.config import SessionState

    session = SessionState(current_phase="IDLE")
    session.save(dot_dir / "session.json")

    captured: dict[str, object] = {}

    def fake_meso_run(*args, **kwargs):
        return str(worktree_path)

    def fake_run_all(*args, **kwargs):
        captured.update(kwargs)

    with chdir(tmp_git_repo):
        with (
            patch("deviate.cli._meso_run", side_effect=fake_meso_run),
            patch("deviate.cli._run_all", side_effect=fake_run_all),
        ):
            result = runner.invoke(cli, ["run", "--profile", "fast"])

    assert result.exit_code == 0, result.output

    # fast → no_judge=True, no_refactor=True (per core/profile.py).
    assert captured.get("no_judge") is True, (
        f"`--profile fast` must forward no_judge=True; got {captured}"
    )
    assert captured.get("no_refactor") is True, (
        f"`--profile fast` must forward no_refactor=True; got {captured}"
    )


def test_top_level_run_invalid_profile_rejected(tmp_git_repo: Path) -> None:
    """An invalid ``--profile`` value must be rejected at the CLI layer
    (Typer validation), mirroring the ``deviate micro run --profile X``
    behavior. Without this, the orchestrator would accept any string
    and silently pass garbage to ``resolve_profile``.
    """
    worktree_path = tmp_git_repo / ".worktrees" / "feat" / "demo" / "demo"
    worktree_path.mkdir(parents=True, exist_ok=True)

    dot_dir = tmp_git_repo / ".deviate"
    dot_dir.mkdir(exist_ok=True)
    from deviate.state.config import SessionState

    session = SessionState(current_phase="IDLE")
    session.save(dot_dir / "session.json")

    with chdir(tmp_git_repo):
        with (
            patch("deviate.cli._meso_run") as mock_meso,
            patch("deviate.cli._run_all") as mock_micro,
        ):
            result = runner.invoke(cli, ["run", "--profile", "invalid"])

    assert result.exit_code != 0, (
        f"Expected Typer validation failure for --profile invalid; "
        f"got exit {result.exit_code}: {result.output}"
    )
    # Neither meso nor micro should have been called — the validation
    # failure must short-circuit before any worktree / drain work.
    mock_meso.assert_not_called()
    mock_micro.assert_not_called()
