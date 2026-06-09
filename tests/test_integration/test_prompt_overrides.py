from __future__ import annotations

import importlib.resources
from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.core.prompts import interpolate, resolve_command, resolve_prompt

runner = CliRunner()


def _init_project(tmp_path: Path) -> Path:
    with chdir(tmp_path):
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0, result.output
    return tmp_path


class TestPromptOverrideIntegration:
    def test_prompt_override_full_cycle(self, tmp_path: Path):
        workdir = _init_project(tmp_path)
        overrides_root = workdir / ".deviate" / "prompts"
        custom = "CUSTOM OVERRIDE CONTENT"
        (overrides_root / "auto" / "red.md").write_text(custom)

        result = resolve_prompt("auto/red.md", overrides_root=overrides_root)

        assert result == custom

    def test_prompt_override_fallback_cycle(self, tmp_path: Path):
        workdir = _init_project(tmp_path)
        overrides_root = workdir / ".deviate" / "prompts"
        (overrides_root / "auto" / "red.md").unlink()

        pkg_root = importlib.resources.files("deviate.prompts")
        expected = (pkg_root / "auto" / "red.md").read_text(encoding="utf-8")
        result = resolve_prompt("auto/red.md", overrides_root=overrides_root)

        assert result == expected

    def test_command_override_full_cycle(self, tmp_path: Path):
        workdir = _init_project(tmp_path)
        overrides_root = workdir / ".deviate" / "prompts"
        custom = "CUSTOM COMMAND CONTENT"
        (overrides_root / "commands" / "deviate-red.md").write_text(custom)

        result = resolve_command("deviate-red", overrides_root=overrides_root)

        assert result == custom

    def test_command_agent_installation(self, tmp_path: Path):
        workdir = tmp_path
        opencode_commands = workdir / ".opencode" / "commands"
        opencode_commands.mkdir(parents=True)
        (opencode_commands / "deviate-red.md").write_text("INITIAL SEED")

        with chdir(workdir):
            init1 = runner.invoke(cli, ["init"])
            assert init1.exit_code == 0, init1.output

        override_content = "OVERRIDE CONTENT FROM USER"
        override_path = workdir / ".deviate" / "prompts" / "commands" / "deviate-red.md"
        override_path.parent.mkdir(parents=True, exist_ok=True)
        override_path.write_text(override_content)

        with chdir(workdir):
            init2 = runner.invoke(cli, ["init"])
            assert init2.exit_code == 0, init2.output

        installed = workdir / ".opencode" / "skills" / "commands" / "deviate-red.md"
        assert installed.exists()
        assert installed.read_text() == override_content

    def test_prompt_interpolation_with_overrides(self, tmp_path: Path):
        workdir = _init_project(tmp_path)
        overrides_root = workdir / ".deviate" / "prompts"
        template = "Hello ${USER}, your task is ${TASK}"
        (overrides_root / "auto" / "red.md").write_text(template)

        resolved = resolve_prompt("auto/red.md", overrides_root=overrides_root)
        result = interpolate(resolved, {"USER": "Alice", "TASK": "testing"})

        assert result == "Hello Alice, your task is testing"

    def test_refresh_prompts_resets_overrides(self, tmp_path: Path):
        workdir = _init_project(tmp_path)
        overrides_root = workdir / ".deviate" / "prompts"
        (overrides_root / "auto" / "red.md").write_text("CUSTOM OVERRIDE")

        pkg_root = importlib.resources.files("deviate.prompts")
        expected = (pkg_root / "auto" / "red.md").read_text(encoding="utf-8")

        with chdir(workdir):
            result = runner.invoke(cli, ["init", "--refresh-prompts"], input="N\n")
            assert result.exit_code == 0, result.output

        assert (overrides_root / "auto" / "red.md").read_text() == expected

    def test_partial_override_set(self, tmp_path: Path):
        workdir = _init_project(tmp_path)
        overrides_root = workdir / ".deviate" / "prompts"
        auto_dir = overrides_root / "auto"
        pkg_root = importlib.resources.files("deviate.prompts")

        (auto_dir / "red.md").write_text("CUSTOM RED")
        (auto_dir / "explore.md").unlink()

        red_result = resolve_prompt("auto/red.md", overrides_root=overrides_root)
        assert red_result == "CUSTOM RED"

        explore_result = resolve_prompt(
            "auto/explore.md", overrides_root=overrides_root
        )
        expected_explore = (pkg_root / "auto" / "explore.md").read_text(
            encoding="utf-8"
        )
        assert explore_result == expected_explore
