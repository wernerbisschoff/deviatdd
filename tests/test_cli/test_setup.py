from __future__ import annotations

import tomllib
from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.core.commands import discover_commands

runner = CliRunner()

_OTHER_AGENT_TREES = (
    ".claude",
    ".opencode",
    ".factory",
    ".pi",
    ".omp",
    ".agents",
    ".codex",
)


def _assert_only_agent_trees(workdir: Path, *present: str) -> None:
    for name in _OTHER_AGENT_TREES:
        path = workdir / name
        if name in present:
            assert path.exists(), f"expected install tree {name} to exist"
        else:
            assert not path.exists(), f"did not expect install tree {name}"


class TestSetupSelectedAgentIsolation:
    """``deviate setup --agent X`` installs only X (droid → factory)."""

    def test_setup_single_agent_only(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
        assert (tmp_path / ".opencode" / "commands" / "deviate-red.md").is_file()
        assert (tmp_path / ".opencode" / "skills" / "deviatdd" / "SKILL.md").is_file()
        _assert_only_agent_trees(tmp_path, ".opencode")

    def test_setup_claude_does_not_write_other_agents(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "claude"])
            assert result.exit_code == 0, result.output
        assert (tmp_path / ".claude" / "commands" / "deviate-red.md").is_file()
        assert (tmp_path / ".claude" / "skills" / "deviatdd" / "SKILL.md").is_file()
        _assert_only_agent_trees(tmp_path, ".claude")

    def test_setup_factory_writes_factory_only(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "factory"])
            assert result.exit_code == 0, result.output
        assert (tmp_path / ".factory" / "commands" / "deviate-red.md").is_file()
        assert (tmp_path / ".factory" / "skills" / "deviatdd" / "SKILL.md").is_file()
        _assert_only_agent_trees(tmp_path, ".factory")
        assert not (tmp_path / ".droid").exists()

    def test_setup_droid_writes_factory_only(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "droid"])
            assert result.exit_code == 0, result.output
        assert (tmp_path / ".factory" / "commands" / "deviate-red.md").is_file()
        assert (tmp_path / ".factory" / "skills" / "deviatdd" / "SKILL.md").is_file()
        _assert_only_agent_trees(tmp_path, ".factory")
        assert not (tmp_path / ".droid").exists()


class TestSetupCodex:
    """ChatGPT Codex is a first-class backend that installs skills only."""

    def test_setup_codex_writes_skills_and_backend(self, tmp_path: Path) -> None:
        commands = discover_commands()
        assert commands, "No commands discovered — test invariant violated"

        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "codex"])
            assert result.exit_code == 0, result.output

        skill = tmp_path / ".agents" / "skills" / "deviatdd" / "SKILL.md"
        assert skill.is_file(), f"Codex packaged skill missing: {skill}"
        for command_name in commands:
            command_skill = tmp_path / ".agents" / "skills" / command_name / "SKILL.md"
            assert command_skill.is_file(), f"missing Codex skill {command_skill}"
            body = command_skill.read_text(encoding="utf-8")
            assert body.startswith("---\n"), f"{command_name} missing YAML frontmatter"
            assert f"name: {command_name}" in body
            assert "description:" in body

        _assert_only_agent_trees(tmp_path, ".agents")
        assert not (tmp_path / ".codex").exists()
        assert not (tmp_path / ".agents" / "prompts").exists()
        assert not (tmp_path / ".agents" / "commands").exists()

        parsed = tomllib.loads(
            (tmp_path / ".deviate" / "config.toml").read_text(encoding="utf-8")
        )
        assert parsed["agent"]["backend"] == "codex"
        assert 'backend = "codex"' in (tmp_path / ".deviate" / "config.toml").read_text(
            encoding="utf-8"
        )
