from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import typer

from deviate.main import app


def _reports(report) -> list[tuple[str, str | None]]:
    return [(args[0], args[1]) for args, _ in report.call_args_list]


def _invoke_app(args: list[str]) -> BaseException | None:
    with patch.object(sys, "argv", ["deviate", *args]):
        try:
            app()
        except BaseException as exc:
            return exc
    return None


def test_micro_run_reports_working_then_idle(tmp_path: Path) -> None:
    with (
        patch("deviate.core.herdr.report_state") as report,
        patch("deviate.cli.micro._resolve_workspace_root", return_value=tmp_path),
        patch("deviate.cli.micro._resolve_agent_config", return_value=None),
        patch("deviate.cli.micro.RunLogger"),
        patch("deviate.cli.micro._run_all"),
    ):
        error = _invoke_app(["micro", "run", "--all"])

    assert isinstance(error, SystemExit) and error.code == 0
    assert _reports(report) == [("working", "deviate micro run"), ("idle", None)]


def test_meso_run_reports_working_then_idle() -> None:
    with (
        patch("deviate.core.herdr.report_state") as report,
        patch("deviate.cli.meso._meso_run"),
    ):
        error = _invoke_app(["meso", "run"])

    assert isinstance(error, SystemExit) and error.code == 0
    assert _reports(report) == [("working", "deviate meso run"), ("idle", None)]


def test_top_level_run_reports_working_then_idle(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    with (
        patch("deviate.core.herdr.report_state") as report,
        patch("deviate.cli._meso_run", return_value=str(worktree)),
        patch("deviate.cli._run_all"),
    ):
        error = _invoke_app(["run"])

    assert isinstance(error, SystemExit) and error.code == 0
    assert _reports(report) == [("working", "deviate run"), ("idle", None)]


def test_top_level_run_reports_blocked_and_preserves_nonzero_exit() -> None:
    with (
        patch("deviate.core.herdr.report_state") as report,
        patch("deviate.cli._meso_run", side_effect=typer.Exit(code=9)),
    ):
        error = _invoke_app(["run"])

    assert isinstance(error, SystemExit) and error.code == 9
    assert _reports(report) == [
        ("working", "deviate run"),
        ("blocked", "deviate run: blocked (exit 9)"),
        ("idle", None),
    ]


def test_usage_error_reports_working_then_blocked() -> None:
    with patch("deviate.core.herdr.report_state") as report:
        error = _invoke_app(["micro", "run", "--profile", "invalid"])

    assert isinstance(error, SystemExit) and error.code == 2
    assert _reports(report) == [
        ("working", "deviate micro run"),
        ("blocked", "deviate micro run: blocked (exit 2)"),
        ("idle", None),
    ]


def test_untracked_command_does_not_report_status() -> None:
    with patch("deviate.core.herdr.report_state") as report:
        error = _invoke_app(["--help"])

    assert isinstance(error, SystemExit) and error.code == 0
    report.assert_not_called()
