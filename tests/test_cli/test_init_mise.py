"""`deviate init pre` scaffolds named mise tasks RED/GREEN resolve."""

from __future__ import annotations

import tomllib
from contextlib import chdir
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.cli.init import _generate_mise_toml

runner = CliRunner()

_PROJECT_MARKERS: dict[str, tuple[str, str]] = {
    "python": ("pyproject.toml", "[project]\nname = 'demo'\n"),
    "elixir_phoenix": ("mix.exs", "defmodule Demo.MixProject do\nend\n"),
    "node": ("package.json", '{"name":"demo"}\n'),
    "rust": ("Cargo.toml", "[package]\nname = 'demo'\nversion = '0.1.0'\n"),
    "go": ("go.mod", "module example.com/demo\n"),
}

_UNIT_DIR = {
    "python": "tests/unit",
    "elixir_phoenix": "test",
    "node": "tests/unit",
    "rust": "tests/unit",
    "go": "tests/unit",
    "unknown": "tests/unit",
}

_INTEGRATION_DIR = {
    "python": "tests/integration",
    "elixir_phoenix": "test/integration",
    "node": "tests/integration",
    "rust": "tests/integration",
    "go": "tests/integration",
    "unknown": "tests/integration",
}

_UNIT_CMD_TOKEN = {
    "python": "tests/unit",
    "elixir_phoenix": "mix test",
    "node": "tests/unit",
    "rust": "--lib",
    "go": "tests/unit",
    "unknown": "tests/unit",
}

_INTEGRATION_CMD_TOKEN = {
    "python": "tests/integration",
    "elixir_phoenix": "test/integration",
    "node": "tests/integration",
    "rust": "--tests",
    "go": "tests/integration",
    "unknown": "tests/integration",
}


def _task_run(config: dict, name: str) -> str:
    task = config["tasks"][name]
    if isinstance(task, str):
        return task
    return str(task["run"])


def _task_depends(config: dict, name: str) -> list[str]:
    task = config["tasks"][name]
    assert isinstance(task, dict), f"expected table for tasks.{name}, got {task!r}"
    depends = task["depends"]
    if isinstance(depends, str):
        return [depends]
    return list(depends)


def _init_pre(repo: Path) -> None:
    with chdir(repo):
        result = runner.invoke(cli, ["init", "pre"])
    assert result.exit_code == 0, result.output


def _seed_project(repo: Path, project_type: str) -> None:
    rel, body = _PROJECT_MARKERS[project_type]
    (repo / rel).write_text(body, encoding="utf-8")


def _load_mise(repo: Path) -> dict:
    return tomllib.loads((repo / "mise.toml").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "project_type",
    ["python", "elixir_phoenix", "node", "rust", "go", "unknown"],
)
def test_fresh_init_defines_unit_and_integration_not_e2e(
    tmp_git_repo: Path, project_type: str
) -> None:
    if project_type != "unknown":
        _seed_project(tmp_git_repo, project_type)

    _init_pre(tmp_git_repo)
    config = _load_mise(tmp_git_repo)
    tasks = config["tasks"]

    assert "unit" in tasks
    assert "integration" in tasks
    assert "doctor" in tasks
    assert "integ" not in tasks
    assert "e2e" not in tasks

    unit_run = _task_run(config, "unit")
    integration_run = _task_run(config, "integration")
    assert "|| true" not in unit_run
    assert "|| true" not in integration_run
    assert _UNIT_CMD_TOKEN[project_type] in unit_run
    assert _INTEGRATION_CMD_TOKEN[project_type] in integration_run
    if project_type != "elixir_phoenix":
        assert _INTEGRATION_DIR[project_type] not in unit_run

    assert (tmp_git_repo / _UNIT_DIR[project_type]).is_dir()
    assert (tmp_git_repo / _INTEGRATION_DIR[project_type]).is_dir()
    assert not (tmp_git_repo / "tests" / "e2e").exists()
    assert not (tmp_git_repo / "e2e").exists()
    assert not (tmp_git_repo / "test" / "e2e").exists()


@pytest.mark.parametrize(
    "project_type", ["python", "elixir_phoenix", "node", "rust", "go"]
)
def test_fresh_init_pre_push_depends_on_unit_only(
    tmp_git_repo: Path, project_type: str
) -> None:
    _seed_project(tmp_git_repo, project_type)
    _init_pre(tmp_git_repo)
    config = _load_mise(tmp_git_repo)
    assert _task_depends(config, "pre-push") == ["unit"]
    pre_commit = _task_depends(config, "pre-commit")
    assert "integration" not in pre_commit
    assert "integ" not in pre_commit
    assert "e2e" not in pre_commit
    assert "unit" not in pre_commit


def test_python_empty_integration_treats_pytest_exit_5_as_success(
    tmp_git_repo: Path,
) -> None:
    _seed_project(tmp_git_repo, "python")
    _init_pre(tmp_git_repo)
    config = _load_mise(tmp_git_repo)
    integration = _task_run(config, "integration")
    unit = _task_run(config, "unit")
    assert "$? -eq 5" in integration
    assert "$? -eq 5" not in unit
    assert "|| true" not in integration


def test_e2e_task_added_only_when_layer_exists(tmp_git_repo: Path) -> None:
    _seed_project(tmp_git_repo, "python")
    (tmp_git_repo / "tests" / "e2e").mkdir(parents=True)

    _init_pre(tmp_git_repo)
    config = _load_mise(tmp_git_repo)
    assert "e2e" in config["tasks"]
    assert "tests/e2e" in _task_run(config, "e2e")
    assert "|| true" not in _task_run(config, "e2e")


def test_existing_layer_dir_is_not_wiped(tmp_git_repo: Path) -> None:
    _seed_project(tmp_git_repo, "python")
    existing = tmp_git_repo / "tests" / "integration"
    existing.mkdir(parents=True)
    marker = existing / "test_already_there.py"
    marker.write_text("def test_keep():\n    assert True\n", encoding="utf-8")

    _init_pre(tmp_git_repo)
    assert marker.exists()
    assert "tests/integration" in _task_run(_load_mise(tmp_git_repo), "integration")


def test_elixir_uses_test_root_for_unit(tmp_git_repo: Path) -> None:
    _seed_project(tmp_git_repo, "elixir_phoenix")
    _init_pre(tmp_git_repo)
    config = _load_mise(tmp_git_repo)
    assert _task_run(config, "unit") == "mix test"
    assert (tmp_git_repo / "test" / "integration").is_dir()
    assert not (tmp_git_repo / "test" / "e2e").exists()
    assert not (tmp_git_repo / "test" / "unit").exists()


def test_existing_mise_without_named_tasks_adds_unit_and_integration(
    tmp_git_repo: Path,
) -> None:
    _seed_project(tmp_git_repo, "python")
    (tmp_git_repo / "mise.toml").write_text(
        '[tools]\npython = "3.11"\n\n[tasks.custom]\nrun = "echo keep-me"\n',
        encoding="utf-8",
    )

    _init_pre(tmp_git_repo)
    config = _load_mise(tmp_git_repo)
    assert config["tools"]["python"] == "3.11"
    assert _task_run(config, "custom") == "echo keep-me"
    assert "unit" in config["tasks"]
    assert "integration" in config["tasks"]
    assert "doctor" in config["tasks"]
    assert "integ" not in config["tasks"]
    assert "e2e" not in config["tasks"]
    assert "|| true" not in _task_run(config, "unit")


def test_existing_mise_with_unit_does_not_rewrite_command(tmp_git_repo: Path) -> None:
    _seed_project(tmp_git_repo, "python")
    (tmp_git_repo / "mise.toml").write_text(
        '[tasks.unit]\nrun = "custom-unit"\n\n[tasks.watch]\nrun = "echo watch"\n',
        encoding="utf-8",
    )

    _init_pre(tmp_git_repo)
    config = _load_mise(tmp_git_repo)
    assert _task_run(config, "unit") == "custom-unit"
    assert _task_run(config, "watch") == "echo watch"
    assert "integration" in config["tasks"]
    assert "e2e" not in config["tasks"]


def test_init_mise_merge_is_idempotent(tmp_git_repo: Path) -> None:
    _seed_project(tmp_git_repo, "python")
    _init_pre(tmp_git_repo)
    first = (tmp_git_repo / "mise.toml").read_text(encoding="utf-8")
    _init_pre(tmp_git_repo)
    second = (tmp_git_repo / "mise.toml").read_text(encoding="utf-8")
    assert first == second


def test_doctor_includes_compose_config_when_compose_exists(
    tmp_git_repo: Path,
) -> None:
    _seed_project(tmp_git_repo, "python")
    (tmp_git_repo / "compose.yaml").write_text("services: {}\n", encoding="utf-8")

    _init_pre(tmp_git_repo)
    doctor = _task_run(_load_mise(tmp_git_repo), "doctor")
    assert "docker compose config" in doctor
    assert "docker compose up" not in doctor


def test_generate_unknown_emits_unit_and_integration_not_e2e(tmp_path: Path) -> None:
    config = tomllib.loads(_generate_mise_toml("unknown", tmp_path))
    assert "unit" in config["tasks"]
    assert _task_run(config, "unit") == "pytest tests/unit"
    assert "|| true" not in _task_run(config, "unit")
    assert "integration" in config["tasks"]
    assert "doctor" in config["tasks"]
    assert "integ" not in config["tasks"]
    assert "e2e" not in config["tasks"]
    assert "$? -eq 5" in _task_run(config, "integration")
