import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

import tomllib
from typer.testing import CliRunner

from deviate.cli import cli

runner = CliRunner()


@contextmanager
def chdir(path: Path):
    cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(cwd)


class TestFullInitCycle:
    def test_full_init_cycle_completes(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output

            dot_dir = workdir / ".deviate"
            config_path = dot_dir / "config.toml"
            session_path = dot_dir / "session.json"
            claude_path = workdir / "CLAUDE.md"
            agents_path = workdir / "AGENTS.md"

            const_path = workdir / "specs" / "constitution.md"

            assert config_path.exists()
            assert session_path.exists()
            assert claude_path.exists()
            assert agents_path.exists()
            assert const_path.exists()

            config_text = config_path.read_text()
            assert 'profile = "default"' in config_text

            session_data = json.loads(session_path.read_text())
            assert session_data["current_phase"] == "IDLE"
            assert session_data["active_issue_id"] is None

            claude_text = claude_path.read_text()
            assert "## DeviaTDD Orchestration Rules" in claude_text

            agents_text = agents_path.read_text()
            assert "## DeviaTDD Orchestration Rules" in agents_text

            const_text = const_path.read_text()
            assert "# Project Constitution" in const_text
            assert "## 3. TESTING_PROTOCOLS" in const_text

    def test_full_init_structure_valid_toml(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output

            config_path = workdir / ".deviate" / "config.toml"
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
            assert data.get("profile") == "default"
            assert data.get("timeout_seconds") == 300
            assert data.get("agent_export_mode") == "local"

    def test_full_init_structure_valid_session(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output

            with open(workdir / ".deviate" / "session.json") as f:
                data = json.load(f)
            assert isinstance(data["timestamp"], str)
            assert data["last_command"] == ""

    def test_init_performance_under_500ms(self, tmp_path: Path):
        with chdir(tmp_path):
            start = time.perf_counter()
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            elapsed = time.perf_counter() - start

            assert result.exit_code == 0, result.output
            assert elapsed < 0.5, f"Init took {elapsed:.3f}s, expected < 0.5s"

    def test_init_idempotent_performance(self, tmp_path: Path):
        with chdir(tmp_path):
            result_first = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result_first.exit_code == 0, result_first.output

            start = time.perf_counter()
            result_second = runner.invoke(cli, ["setup", "--agent", "opencode"])
            elapsed = time.perf_counter() - start

            assert result_second.exit_code == 0, result_second.output
            assert elapsed < 0.5, f"Second init took {elapsed:.3f}s, expected < 0.5s"

    def test_init_export_files_not_created_when_existing(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            dot_dir = workdir / ".deviate"
            dot_dir.mkdir()
            config_path = dot_dir / "config.toml"
            config_path.write_text(
                'profile = "custom"\n\n[agent]\nbackend = "opencode"\n'
            )
            session_path = dot_dir / "session.json"
            session_path.write_text('{"current_phase": "RED"}\n')

            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output

            assert config_path.read_text() == (
                'profile = "custom"\n\n[agent]\nbackend = "opencode"\n'
            )
            assert session_path.read_text() == '{"current_phase": "RED"}\n'

    def test_init_idempotency_with_pre_existing_files(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            dot_dir = workdir / ".deviate"
            dot_dir.mkdir()
            config_path = dot_dir / "config.toml"
            original_config = 'profile = "custom"\n\n[agent]\nbackend = "opencode"\n'
            config_path.write_text(original_config)

            session_path = dot_dir / "session.json"
            original_session = '{"current_phase": "RED"}\n'
            session_path.write_text(original_session)

            claude_path = workdir / "CLAUDE.md"
            existing_claude = (
                "# My Project\n\n"
                "## DeviaTDD Orchestration Rules\n"
                "Existing rules\n\n"
                "## Other Section\n"
                "Preserved content\n"
            )
            claude_path.write_text(existing_claude)

            agents_path = workdir / "AGENTS.md"
            existing_agents = "# Existing AGENTS content\n"
            agents_path.write_text(existing_agents)

            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output

            assert config_path.read_text() == original_config
            assert session_path.read_text() == original_session
            assert claude_path.exists()
            content = claude_path.read_text()
            assert "Existing rules" not in content
            assert "Preserved content" in content
            assert "## DeviaTDD Orchestration Rules" in content
            assert "## Other Section" in content

            assert agents_path.exists()
            agents_content = agents_path.read_text()
            assert "## DeviaTDD Orchestration Rules" in agents_content
