from __future__ import annotations

import json
import subprocess
import tomllib
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.cli.init import _generate_mise_toml
from deviate.cli.micro import _run_test_cmd
from deviate.core.constitution import extract_commands


runner = CliRunner()


def test_unknown_project_mise_dispatches_test_and_lint(tmp_path: Path) -> None:
    config = tomllib.loads(_generate_mise_toml("unknown", tmp_path))

    assert config["tasks"]["test"]["run"] == "pytest"
    assert config["tasks"]["lint"]["run"] == "ruff check && ruff format --check"


def test_init_pre_scaffolds_mise_for_unknown_project(tmp_git_repo: Path) -> None:
    with chdir(tmp_git_repo):
        result = runner.invoke(cli, ["init", "pre"])

    assert result.exit_code == 0, result.output
    contract = json.loads(result.output[result.output.find("{") :])
    assert contract["project_type"] == "unknown"
    assert contract["existing_artifacts"]["mise_toml"] is True

    config = tomllib.loads((tmp_git_repo / "mise.toml").read_text(encoding="utf-8"))
    assert config["tasks"]["test"]["run"] == "pytest"


def test_init_pre_preserves_existing_mise(tmp_git_repo: Path) -> None:
    original = '[tasks.test]\nrun = "custom-test"\n'
    mise_path = tmp_git_repo / "mise.toml"
    mise_path.write_text(original, encoding="utf-8")

    with chdir(tmp_git_repo):
        result = runner.invoke(cli, ["init", "pre"])

    assert result.exit_code == 0, result.output
    assert mise_path.read_text(encoding="utf-8") == original


def test_extract_python_test_command_alias(tmp_path: Path) -> None:
    path = tmp_path / "constitution.md"
    path.write_text("- PYTHON_TEST_COMMAND: pytest\n")

    assert extract_commands(path)["python_test_command"] == "pytest"


def test_task_verification_has_priority(tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict]] = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, "passed", "")

    with patch("deviate.cli.micro.subprocess.run", side_effect=fake_run):
        result = _run_test_cmd(
            tmp_path,
            {"verification": "pytest tests/test_specific.py -q"},
        )

    assert result.returncode == 0
    assert calls[0][0] == ["sh", "-c", "pytest tests/test_specific.py -q"]


def test_constitution_command_used_without_mise_task(tmp_path: Path) -> None:
    constitution = tmp_path / "specs" / "constitution.md"
    constitution.parent.mkdir()
    constitution.write_text("- TEST_COMMAND: pytest\n", encoding="utf-8")

    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "passed", "")

    with patch("deviate.cli.micro.subprocess.run", side_effect=fake_run):
        result = _run_test_cmd(tmp_path)

    assert result.returncode == 0
    assert calls == [["sh", "-c", "pytest"]]


def test_missing_mise_task_falls_back_to_constitution(tmp_path: Path) -> None:
    (tmp_path / "mise.toml").write_text(
        '[tasks.test]\nrun = "pytest"\n', encoding="utf-8"
    )
    constitution = tmp_path / "specs" / "constitution.md"
    constitution.parent.mkdir()
    constitution.write_text("- TEST_COMMAND: pytest fallback\n", encoding="utf-8")

    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args == ["mise", "run", "test"]:
            return subprocess.CompletedProcess(
                args, 1, "", "mise ERROR unknown command: test"
            )
        return subprocess.CompletedProcess(args, 0, "passed", "")

    with patch("deviate.cli.micro.subprocess.run", side_effect=fake_run):
        result = _run_test_cmd(tmp_path)

    assert result.returncode == 0
    assert calls == [["mise", "run", "test"], ["sh", "-c", "pytest fallback"]]


def test_nested_python_manifest_is_used_when_root_is_unconfigured(
    tmp_path: Path,
) -> None:
    service = tmp_path / "services" / "solver_service"
    service.mkdir(parents=True)
    (service / "pyproject.toml").write_text("[project]\nname='solver'\n")

    calls: list[tuple[list[str], dict]] = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, "passed", "")

    with patch("deviate.cli.micro.subprocess.run", side_effect=fake_run):
        result = _run_test_cmd(tmp_path)

    assert result.returncode == 0
    assert calls[0][0] == ["sh", "-c", "pytest"]
    assert calls[0][1]["cwd"] == service
