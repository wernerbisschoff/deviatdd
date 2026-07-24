"""Tests for the top-level ``deviate run`` meso orchestrator.

``deviate run`` claims the next BACKLOG issue and produces ``plan.md`` plus
``tasks.md``, then stops at HITL Gate 2. The human reviews both artifacts and
starts implementation explicitly with ``deviate micro run --all``.
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
    for removed in ("--profile", "--no-judge", "--no-refactor", "--agent", "--json"):
        assert removed not in output


def test_top_level_run_help_mentions_gate_2_handoff():
    result = runner.invoke(cli, ["run", "--help"])
    assert "HITL Gate 2" in result.output
    assert "deviate meso approve" in result.output
    assert "deviate micro run --all" in result.output


def test_top_level_run_stops_after_meso_for_hitl_review(tmp_git_repo: Path) -> None:
    """The top-level command must not cross Gate 2 into micro automatically."""
    worktree_path = tmp_git_repo / ".worktrees" / "feat" / "demo" / "demo"
    worktree_path.mkdir(parents=True, exist_ok=True)

    with chdir(tmp_git_repo):
        with (
            patch("deviate.cli._meso_run", return_value=str(worktree_path)),
            patch("deviate.cli._run_all") as mock_run_all,
        ):
            result = runner.invoke(cli, ["run"])

    assert result.exit_code == 0, result.output
    mock_run_all.assert_not_called()
    assert "AWAITING_HITL_GATE_2" in result.output
    assert "plan.md" in result.output
    assert "tasks.md" in result.output
    assert "deviate micro run --all" in result.output


def test_micro_run_requires_gate_2_approval(tmp_git_repo: Path) -> None:
    from deviate.state.config import SessionState

    dot_dir = tmp_git_repo / ".deviate"
    dot_dir.mkdir()
    SessionState(current_phase="IDLE", active_issue_id="ISS-001").save(
        dot_dir / "session.json"
    )

    with chdir(tmp_git_repo):
        result = runner.invoke(cli, ["micro", "run", "--all"])

    assert result.exit_code == 1, result.output
    assert "HITL_GATE_2_APPROVAL_REQUIRED" in result.output
    assert "deviate meso" in result.output
    assert "approve" in result.output


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


def test_meso_approve_records_issue_bound_gate_2_approval(tmp_git_repo: Path) -> None:
    from deviate.state.config import SessionState

    dot_dir = tmp_git_repo / ".deviate"
    dot_dir.mkdir()
    SessionState(current_phase="IDLE", active_issue_id="ISS-001").save(
        dot_dir / "session.json"
    )
    artifact_dir = tmp_git_repo / "specs" / "demo" / "issue"
    (tmp_git_repo / "specs").mkdir()
    (tmp_git_repo / "specs" / "issues.jsonl").write_text(
        '{"issue_id":"ISS-001","type":"feature","title":"Demo",'
        '"status":"BACKLOG","source_file":"specs/demo/issues/issue.md",'
        '"timestamp":"2026-01-01T00:00:00Z"}\n'
    )
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "plan.md").write_text(
        "## Acceptance Contract\n"
        "**Scenario AC-PLAN-001: Valid input succeeds**\n"
        "- **Source Outline**: AO-001\n"
        "- **Upstream Traceability**: FR-001-DEMO, AC-001-DEMO-01\n"
        "- **Current-Code Evidence**: src/demo.py:run\n"
        "- **Given**: A configured repository\n"
        "- **When**: The command runs\n"
        "- **Then**: It succeeds\n"
    )
    (artifact_dir / "tasks.md").write_text(
        "# Implementation Tasks\n\n- TSK-001-01: Implement valid input\n"
    )
    with chdir(tmp_git_repo):
        result = runner.invoke(
            cli,
            [
                "meso",
                "approve",
                "--issue",
                "ISS-001",
                "--plan",
                str(artifact_dir / "plan.md"),
                "--tasks",
                str(artifact_dir / "tasks.md"),
            ],
            input="y\n",
        )

    assert result.exit_code == 0, result.output
    session = SessionState.load(dot_dir / "session.json")
    assert session.hitl_gate_2_approved_issue_id == "ISS-001"
    assert "HITL_GATE_2_APPROVED" in result.output
    assert session.hitl_gate_2_plan_sha256
    assert session.hitl_gate_2_tasks_sha256


def test_micro_run_rejects_changed_artifacts_after_approval(tmp_git_repo: Path) -> None:
    from hashlib import sha256

    from deviate.state.config import SessionState

    dot_dir = tmp_git_repo / ".deviate"
    dot_dir.mkdir()
    plan = tmp_git_repo / "plan.md"
    tasks = tmp_git_repo / "tasks.md"
    plan.write_text("approved plan\n")
    tasks.write_text("approved tasks\n")
    SessionState(
        current_phase="IDLE",
        active_issue_id="ISS-001",
        hitl_gate_2_approved_issue_id="ISS-001",
        hitl_gate_2_plan_path="plan.md",
        hitl_gate_2_tasks_path="tasks.md",
        hitl_gate_2_plan_sha256=sha256(plan.read_bytes()).hexdigest(),
        hitl_gate_2_tasks_sha256=sha256(tasks.read_bytes()).hexdigest(),
    ).save(dot_dir / "session.json")
    tasks.write_text("changed after approval\n")

    with chdir(tmp_git_repo):
        result = runner.invoke(cli, ["micro", "run", "--all"])

    assert result.exit_code == 1, result.output
    assert "HITL_GATE_2_APPROVAL_STALE" in result.output


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
