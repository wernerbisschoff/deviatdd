"""Tests for the top-level ``deviate run`` meso orchestrator.

``deviate run`` chains meso into micro end-to-end. The HITL Gate 2 hard gate
(``deviate meso approve`` + ``HITL_GATE_2_APPROVAL_REQUIRED`` enforcement) has
been removed — the system never blocks on human approval.
"""

import re

from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from deviate.cli import cli

runner = CliRunner()


# Strip ANSI codes before substring checks: under FORCE_COLOR (set by GitHub
# Actions runners by default), Rich's option formatter splits `--` from the
# flag name into separate style runs, e.g. `-ESCm-ESCm-issueESCm`. The visual
# text reads `--issue` but the literal `--` is broken across escape codes, so
# substring assertions against `result.output` only work on plain text.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def test_top_level_run_help_lists_meso_options():
    """``deviate run`` exposes only issue preparation options."""
    result = runner.invoke(cli, ["run", "--help"])
    assert result.exit_code == 0, result.output
    output = _ANSI_RE.sub("", result.output)

    assert "--issue" in output
    assert "--force" in output
    assert "--local" in output
    for removed in ("--profile", "--no-judge", "--no-refactor", "--agent", "--json"):
        assert removed not in output


def test_top_level_run_help_does_not_mention_gate_2_or_meso_approve():
    """Gate 2 is removed — the run help must not surface HITL Gate 2 or
    ``deviate meso approve`` as a step the user must take."""
    result = runner.invoke(cli, ["run", "--help"])
    output = _ANSI_RE.sub("", result.output)
    assert "HITL Gate 2" not in output, result.output
    assert "meso approve" not in output, result.output
    assert "AWAITING_HITL_GATE_2" not in output, result.output


def test_top_level_run_forwards_local(tmp_git_repo: Path) -> None:
    """AC-PLAN-003: ``deviate run --local`` forwards ``local=True`` to ``_meso_run``.

    The flag is the same skip-push claim as ``deviate meso run --local``.
    It is not ``--no-setup``.
    """
    from deviate.state.config import SessionState

    worktree_path = tmp_git_repo / ".worktrees" / "feat" / "demo" / "demo"
    worktree_path.mkdir(parents=True, exist_ok=True)
    (worktree_path / ".deviate").mkdir(parents=True, exist_ok=True)
    SessionState(current_phase="IDLE", active_issue_id="ISS-001").save(
        worktree_path / ".deviate" / "session.json"
    )

    with chdir(tmp_git_repo):
        with (
            patch(
                "deviate.cli._meso_run", return_value=str(worktree_path)
            ) as mock_meso,
            patch("deviate.cli._run_all") as mock_run_all,
        ):
            result = runner.invoke(cli, ["run", "--local"])

    assert result.exit_code == 0, result.output
    mock_meso.assert_called_once()
    assert mock_meso.call_args.kwargs.get("local") is True, (
        "deviate run --local must forward local=True into _meso_run; "
        f"got kwargs={mock_meso.call_args.kwargs}"
    )
    assert mock_meso.call_args.kwargs.get("no_setup") is not True, (
        "--local must not be treated as --no-setup; "
        f"got kwargs={mock_meso.call_args.kwargs}"
    )
    mock_run_all.assert_called_once()


def test_top_level_run_chains_into_micro_after_meso(tmp_git_repo: Path) -> None:
    """The top-level command must chain meso into micro automatically —
    Gate 2 is gone, so ``deviate run`` no longer halts for human approval."""
    from deviate.state.config import SessionState

    worktree_path = tmp_git_repo / ".worktrees" / "feat" / "demo" / "demo"
    worktree_path.mkdir(parents=True, exist_ok=True)
    (worktree_path / ".deviate").mkdir(parents=True, exist_ok=True)
    SessionState(current_phase="IDLE", active_issue_id="ISS-001").save(
        worktree_path / ".deviate" / "session.json"
    )

    with chdir(tmp_git_repo):
        with (
            patch("deviate.cli._meso_run", return_value=str(worktree_path)),
            patch("deviate.cli._run_all") as mock_run_all,
        ):
            result = runner.invoke(cli, ["run"])

    assert result.exit_code == 0, result.output
    mock_run_all.assert_called_once()
    assert "AWAITING_HITL_GATE_2" not in result.output
    assert "deviate meso approve" not in result.output


def test_micro_run_does_not_require_gate_2_approval(tmp_git_repo: Path) -> None:
    """``deviate micro run`` must NOT enforce HITL Gate 2 approval. The hard
    gate has been removed; micro runs as soon as it is invoked, regardless of
    whether ``session.hitl_gate_2_*`` fields exist or are populated."""
    from deviate.state.config import SessionState

    dot_dir = tmp_git_repo / ".deviate"
    dot_dir.mkdir()
    SessionState(current_phase="IDLE", active_issue_id="ISS-001").save(
        dot_dir / "session.json"
    )

    with chdir(tmp_git_repo):
        # Patch _run_all so the test doesn't actually run the TDD cycle;
        # the point of this test is that micro no longer fails-fast on a
        # missing approval — it must reach the micro drain.
        with patch("deviate.cli.micro._run_all") as mock_run_all:
            result = runner.invoke(cli, ["micro", "run", "--all"])

    assert "HITL_GATE_2_APPROVAL_REQUIRED" not in result.output
    assert "deviate meso approve" not in result.output
    # _run_all was reached, confirming the gate is not enforced.
    mock_run_all.assert_called_once()


def test_micro_spec_content_marks_plan_contract_authoritative(tmp_path: Path) -> None:
    from deviate.cli.micro import _resolve_spec_md

    issue = tmp_path / "specs" / "demo" / "issues" / "issue.md"
    issue.parent.mkdir(parents=True)
    issue.write_text("## Acceptance Outline\n- **AO-001**: Valid input succeeds.\n")
    artifact_dir = tmp_path / "specs" / "demo" / "issue"
    artifact_dir.mkdir()
    (artifact_dir / "plan.md").write_text(
        "## Acceptance Contract\n"
        "**Scenario AC-PLAN-001: Valid input succeeds**\n"
        "- **Source Outline**: AO-001\n"
        "- **Upstream Traceability**: FR-001-DEMO, AC-001-DEMO-01\n"
        "- **Current-Code Evidence**: src/demo.py:run\n"
        "- **Given**: configured\n- **When**: run\n- **Then**: success\n"
    )
    (tmp_path / "specs" / "issues.jsonl").write_text(
        '{"issue_id":"ISS-001","type":"feature","title":"Demo",'
        '"status":"BACKLOG","source_file":"specs/demo/issues/issue.md",'
        '"timestamp":"2026-01-01T00:00:00Z"}\n'
    )

    content = _resolve_spec_md(tmp_path, {"issue_id": "ISS-001"})

    assert "<macro_issue_intent>" in content
    assert '<authoritative_acceptance_contract source="plan.md">' in content
    assert content.index("## Acceptance Outline") < content.index(
        "## Acceptance Contract"
    )


def test_meso_approve_command_no_longer_exists(tmp_git_repo: Path) -> None:
    """``deviate meso approve`` is removed. Typer must surface a "no such
    command" error rather than silently accept a now-removed subcommand."""
    result = runner.invoke(cli, ["meso", "approve", "--issue", "ISS-001", "--yes"])

    assert result.exit_code != 0, result.output
    lowered = result.output.lower()
    assert (
        "no such command" in lowered
        or "unknown command" in lowered
        or "missing command" in lowered
    ), f"Expected Typer to reject 'meso approve'; got: {result.output}"


def test_top_level_run_does_not_mutate_worktree_micro_state(
    tmp_git_repo: Path,
) -> None:
    worktree_path = tmp_git_repo / ".worktrees" / "feat" / "demo" / "demo"
    worktree_path.mkdir(parents=True)
    dot_dir = worktree_path / ".deviate"
    dot_dir.mkdir()
    from deviate.state.config import SessionState

    SessionState(current_phase="IDLE", active_issue_id="ISS-002").save(
        dot_dir / "session.json"
    )

    with chdir(tmp_git_repo):
        with patch("deviate.cli._meso_run", return_value=str(worktree_path)):
            result = runner.invoke(cli, ["run"])

    assert result.exit_code == 0, result.output
    restored = SessionState.load(dot_dir / "session.json")
    assert restored.last_command == ""


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
