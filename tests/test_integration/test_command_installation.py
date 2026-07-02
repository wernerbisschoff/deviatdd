from __future__ import annotations

from contextlib import chdir
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deviate.cli import cli

runner = CliRunner()


class TestCommandInstallation:
    """T007: Wire agent detection, command installation, and contract handoff into deviate init."""

    def test_init_installs_commands_to_agent_dirs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """US-005-COMMANDS Scenario 2: command .md copied to detected agent paths."""
        monkeypatch.setattr(
            "deviate.cli._get_agent_command_dir",
            lambda agent, _workdir: tmp_path / f".{agent}" / "commands",
        )
        (tmp_path / ".claude").mkdir(parents=True)
        (tmp_path / ".opencode").mkdir(parents=True)
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0
            assert "INSTALL" in result.output.upper()

    def test_command_idempotency_skip_identical(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """US-005-COMMANDS Scenario 3: skip when content matches."""
        monkeypatch.setattr(
            "deviate.cli._get_agent_command_dir",
            lambda agent, _workdir: tmp_path / f".{agent}" / "commands",
        )
        (tmp_path / ".claude").mkdir(parents=True)
        with chdir(tmp_path):
            # First install — all commands get composed (INSTALL expected)
            first = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert first.exit_code == 0
            # Second install — identical content (SKIP expected)
            second = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert second.exit_code == 0
            assert "SKIP" in second.output

    def test_command_idempotency_overwrite_stale(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """US-005-COMMANDS Scenario 4: overwrite when content differs."""
        monkeypatch.setattr(
            "deviate.cli._get_agent_command_dir",
            lambda agent, _workdir: tmp_path / f".{agent}" / "commands",
        )
        target = tmp_path / ".claude" / "commands" / "deviate-shard.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("STALE CONTENT", encoding="utf-8")
        (tmp_path / ".claude").mkdir(exist_ok=True)
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "claude"])
            assert result.exit_code == 0
            content = target.read_text(encoding="utf-8")
            assert "STALE CONTENT" not in content

    def test_auto_detect_agents_from_cwd(self, tmp_path: Path):
        """US-006-INIT Scenario 1: auto-detect agents from cwd directories."""
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".opencode").mkdir()
        (tmp_path / ".factory").mkdir()
        (tmp_path / ".omp").mkdir()
        from deviate.core import commands as commands_module

        with chdir(tmp_path):
            agents = commands_module.detect_agents()
            assert "opencode" in agents
            assert "claude" in agents
            assert "factory" in agents
            assert "omp" in agents

    def test_agent_flag_overrides_detection(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """US-006-INIT Scenario 2: --agent flag overrides auto-detection."""
        monkeypatch.setattr(
            "deviate.cli._get_agent_command_dir",
            lambda agent, _workdir: tmp_path / f".{agent}" / "commands",
        )
        (tmp_path / ".claude").mkdir()
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0

    def test_contract_handoff_defaults_to_session_json(self, tmp_path: Path):
        """US-006-INIT Scenario 4: contract handoff defaults to .deviate/session.json."""
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0
            assert (tmp_path / ".deviate" / "session.json").exists()
            gitignore = tmp_path / ".deviate" / ".gitignore"
            assert gitignore.exists()
            content = gitignore.read_text(encoding="utf-8")
            assert "session.json" in content

    def test_init_graphite_emits_routing_section_in_pr_command(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """`init --graphite` injects `<graphite_routing>` into installed deviate-pr command."""
        monkeypatch.setattr(
            "deviate.cli._get_agent_command_dir",
            lambda agent, _workdir: tmp_path / f".{agent}" / "commands",
        )
        (tmp_path / ".opencode").mkdir(parents=True)
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "opencode", "--graphite"])
            assert result.exit_code == 0, result.output
            command_path = tmp_path / ".opencode" / "commands" / "deviate-pr.md"
            assert command_path.exists()
            content = command_path.read_text(encoding="utf-8")
            assert "<graphite_routing>" in content
            assert "gt submit --stack" in content

    def test_init_without_graphite_omits_routing_section_in_pr_command(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """`init` (no flag) installs deviate-pr command file without Graphite Routing."""
        monkeypatch.setattr(
            "deviate.cli._get_agent_command_dir",
            lambda agent, _workdir: tmp_path / f".{agent}" / "commands",
        )
        (tmp_path / ".opencode").mkdir(parents=True)
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            command_path = tmp_path / ".opencode" / "commands" / "deviate-pr.md"
            assert command_path.exists()
            content = command_path.read_text(encoding="utf-8")
            assert "<graphite_routing>" not in content
