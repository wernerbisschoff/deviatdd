"""CLI smoke tests for ``deviate tome`` subcommand.

These tests use Typer's ``CliRunner`` to exercise the subcommand
without actually shelling out to an agent backend. We use the
``--dry-run`` flag to verify argument parsing and report resolution
without dispatching any writers.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from deviate.cli.tome import tome_app


SAMPLE_REPORT = """# Classification Report — abc1234

**Status**: mixed

## Summary
Test report.

## Capabilities
| capability | evidence | audience | doc_type | action | target_file | confidence |
|------------|----------|----------|----------|--------|-------------|------------|
| Setup workspace | `pyproject.toml:34` | developer | how-to | create | apps/docs/src/content/docs/how-to/setup.md | 0.85 |
| CLI flags | `pyproject.toml:34` | developer | reference | create | apps/docs/src/content/docs/reference/flags.md | 0.80 |
| Architecture | `specs/arch.md` | developer | explanation | update | apps/docs/src/content/docs/explanation/arch.md | 0.75 |
| Setup required | — | developer | how-to | setup-required | null | 0.50 |
"""


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def work_dir(tmp_path: Path) -> Path:
    cwd = tmp_path / "work"
    cwd.mkdir()
    return cwd


@pytest.fixture
def report_file(work_dir: Path) -> Path:
    p = work_dir / "report.md"
    p.write_text(SAMPLE_REPORT, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------


def test_tome_help_lists_subcommands(runner: CliRunner) -> None:
    result = runner.invoke(tome_app, ["--help"])
    assert result.exit_code == 0
    assert "write" in result.stdout
    assert "list" in result.stdout


def test_tome_write_help_describes_options(runner: CliRunner) -> None:
    result = runner.invoke(tome_app, ["write", "--help"])
    assert result.exit_code == 0
    assert "--from-report" in result.stdout
    assert "--workers" in result.stdout
    assert "--timeout" in result.stdout
    assert "--backend" in result.stdout
    assert "--actions" in result.stdout
    assert "--no-resume" in result.stdout
    assert "--log" in result.stdout
    assert "--dry-run" in result.stdout


def test_tome_list_help(runner: CliRunner) -> None:
    result = runner.invoke(tome_app, ["list", "--help"])
    assert result.exit_code == 0
    assert "--from-report" in result.stdout
    assert "--json" in result.stdout


# ---------------------------------------------------------------------------
# deviate tome list
# ---------------------------------------------------------------------------


def test_tome_list_prints_table(runner: CliRunner, report_file: Path) -> None:
    result = runner.invoke(tome_app, ["list", "--from-report", str(report_file)])
    assert result.exit_code == 0
    assert "Setup workspace" in result.stdout
    assert "CLI flags" in result.stdout
    assert "Architecture" in result.stdout


def test_tome_list_prints_json(runner: CliRunner, report_file: Path) -> None:
    result = runner.invoke(
        tome_app, ["list", "--from-report", str(report_file), "--json"]
    )
    assert result.exit_code == 0
    import json

    data = json.loads(result.stdout)
    assert len(data) == 4
    assert data[0]["capability"] == "Setup workspace"
    assert data[0]["doc_type"] == "how-to"
    assert data[0]["action"] == "create"
    assert data[0]["target_file"] == "apps/docs/src/content/docs/how-to/setup.md"


def test_tome_list_missing_report(runner: CliRunner, work_dir: Path) -> None:
    missing = work_dir / "does-not-exist.md"
    result = runner.invoke(tome_app, ["list", "--from-report", str(missing)])
    # Typer's `exists=True` on the option rejects the path before our
    # code runs; we get Typer's standard "does not exist" message.
    assert result.exit_code != 0
    out = (result.stdout or "") + (result.stderr or "")
    assert "does not" in out or "exist" in out


# ---------------------------------------------------------------------------
# deviate tome write --dry-run
# ---------------------------------------------------------------------------


def test_tome_write_dry_run_prints_plan(runner: CliRunner, report_file: Path) -> None:
    result = runner.invoke(
        tome_app,
        [
            "write",
            "--from-report",
            str(report_file),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "Dry run" in result.stdout
    assert "Setup workspace" in result.stdout
    assert "CLI flags" in result.stdout
    assert "Architecture" in result.stdout
    # setup-required row is filtered by default actions={"create", "update"}.
    assert "Setup required" not in result.stdout


def test_tome_write_dry_run_includes_setup_required_when_filtered(
    runner: CliRunner, report_file: Path
) -> None:
    result = runner.invoke(
        tome_app,
        [
            "write",
            "--from-report",
            str(report_file),
            "--actions",
            "create,update,setup-required",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "Setup required" in result.stdout


def test_tome_write_dry_run_shows_config(runner: CliRunner, report_file: Path) -> None:
    result = runner.invoke(
        tome_app,
        [
            "write",
            "--from-report",
            str(report_file),
            "--workers",
            "8",
            "--timeout",
            "300",
            "--backend",
            "droid",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "droid" in result.stdout
    assert "8" in result.stdout
    assert "300" in result.stdout


def test_tome_write_missing_report(runner: CliRunner, work_dir: Path) -> None:
    missing = work_dir / "does-not-exist.md"
    result = runner.invoke(tome_app, ["write", "--from-report", str(missing)])
    # Typer's `exists=True` rejects the path with its standard error.
    assert result.exit_code != 0
    out = (result.stdout or "") + (result.stderr or "")
    assert "does not" in out or "exist" in out


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_tome_write_rejects_zero_workers(runner: CliRunner, report_file: Path) -> None:
    result = runner.invoke(
        tome_app,
        [
            "write",
            "--from-report",
            str(report_file),
            "--workers",
            "0",
        ],
    )
    # Typer validates the int range and exits with code 2.
    assert result.exit_code != 0
