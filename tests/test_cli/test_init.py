import tomllib
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.cli.__init__ import resolve_graphite_config

runner = CliRunner()


class TestInitCommand:
    def test_init_creates_dotfile_structure(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["init", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            assert (workdir / ".deviate" / "config.toml").exists()
            assert (workdir / ".deviate" / "session.json").exists()

    def test_init_appends_governance_to_nonexistent_file(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["init", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            claude_path = workdir / "CLAUDE.md"
            assert claude_path.exists()
            content = claude_path.read_text()
            assert "## DeviaTDD Orchestration Rules" in content

    def test_init_overwrites_governance_block_when_exists(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            claude_path = workdir / "CLAUDE.md"
            existing_content = (
                "# My Project\n\n"
                "## DeviaTDD Orchestration Rules\n"
                "Old content\n\n"
                "## Other Section\n"
                "Preserved content\n"
            )
            claude_path.write_text(existing_content)

            result = runner.invoke(cli, ["init", "--agent", "opencode"])
            assert result.exit_code == 0, result.output

            content = claude_path.read_text()
            assert "Old content" not in content
            assert "Preserved content" in content
            assert "## DeviaTDD Orchestration Rules" in content
            assert "## Other Section" in content

    def test_init_replaces_multi_section_governance_block(self, tmp_path: Path):
        """Seed has multiple sections; each is replaced independently without duplication."""
        with chdir(tmp_path):
            workdir = tmp_path
            claude_path = workdir / "CLAUDE.md"
            existing_content = (
                "# My Project\n\n"
                "## DeviaTDD Orchestration Rules\n"
                "Old orchestration content\n\n"
                "## Offline Documentation System\n"
                "Old docs content\n\n"
                "## Other Section\n"
                "Preserved content\n"
            )
            claude_path.write_text(existing_content)

            result = runner.invoke(cli, ["init", "--agent", "opencode"])
            assert result.exit_code == 0, result.output

            content = claude_path.read_text()
            assert "Old orchestration content" not in content
            assert "Old docs content" not in content
            assert "Preserved content" in content
            assert "## Other Section" in content
            assert content.count("## DeviaTDD Orchestration Rules") == 1
            assert content.count("## Offline Documentation System") == 1

    def test_init_normalized_heading_replaces_annotated_heading(self, tmp_path: Path):
        """Existing heading has emoji/parenthetical that seed lacks; normalized match finds it."""
        with chdir(tmp_path):
            workdir = tmp_path
            claude_path = workdir / "CLAUDE.md"
            existing_content = (
                "# Project\n\n"
                "## \U0001f4da Offline Documentation System (MANDATORY)\n"
                "Old docs content\n\n"
                "## Other Section\n"
                "Preserved\n"
            )
            claude_path.write_text(existing_content)

            result = runner.invoke(cli, ["init", "--agent", "opencode"])
            assert result.exit_code == 0, result.output

            content = claude_path.read_text()
            assert "Old docs content" not in content
            assert "Preserved" in content
            assert "## Other Section" in content
            assert content.count("## Offline Documentation System") == 1

    def test_init_skip_existing_dotfiles(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            dotfile_dir = workdir / ".deviate"
            dotfile_dir.mkdir()
            config_path = dotfile_dir / "config.toml"
            original_content = 'profile = "custom"\n\n[agent]\nbackend = "opencode"\n'
            config_path.write_text(original_content)

            result = runner.invoke(cli, ["init", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            assert config_path.read_text() == original_content
            assert "skip" in result.output.lower() or "already" in result.output.lower()

    def test_init_recover_partial_scaffold(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            dotfile_dir = workdir / ".deviate"
            dotfile_dir.mkdir()
            config_path = dotfile_dir / "config.toml"
            config_path.write_text('profile = "default"\n')
            session_path = dotfile_dir / "session.json"

            result = runner.invoke(cli, ["init", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            assert session_path.exists()

    def test_init_detects_libref(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            with patch("shutil.which") as mock_which:
                mock_which.return_value = "/usr/local/bin/libref"
                result = runner.invoke(cli, ["init", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            config_path = workdir / ".deviate" / "config.toml"
            content = config_path.read_text()
            assert "use_libref = true" in content

    def test_init_missing_libref(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            with patch("shutil.which") as mock_which:
                mock_which.return_value = None
                result = runner.invoke(cli, ["init", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            config_path = workdir / ".deviate" / "config.toml"
            content = config_path.read_text()
            assert "use_libref = false" in content

    def test_init_libref_governance_block(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            with patch("shutil.which") as mock_which:
                mock_which.return_value = "/usr/local/bin/libref"
                result = runner.invoke(cli, ["init", "--agent", "opencode"])
            assert result.exit_code == 0, result.output

            claude_path = workdir / "CLAUDE.md"
            assert claude_path.exists()
            claude_content = claude_path.read_text()
            assert "## Offline Documentation System" in claude_content
            assert "libref query" in claude_content
            assert "libref list" in claude_content
            assert "libref add" in claude_content

            agents_path = workdir / "AGENTS.md"
            assert agents_path.exists()
            agents_content = agents_path.read_text()
            assert "## Offline Documentation System" in agents_content

    def test_init_libref_flag_overrides_missing_binary(self, tmp_path: Path):
        """--libref forces use_libref=true even when shutil.which returns None."""
        with chdir(tmp_path):
            workdir = tmp_path
            with patch("shutil.which") as mock_which:
                mock_which.return_value = None
                result = runner.invoke(cli, ["init", "--agent", "opencode", "--libref"])
            assert result.exit_code == 0, result.output
            config_path = workdir / ".deviate" / "config.toml"
            content = config_path.read_text()
            assert "use_libref = true" in content

    def test_init_libref_flag_overrides_detected_binary(self, tmp_path: Path):
        """--libref stays true when binary is detected (no double-flip)."""
        with chdir(tmp_path):
            workdir = tmp_path
            with patch("shutil.which") as mock_which:
                mock_which.return_value = "/usr/local/bin/libref"
                result = runner.invoke(cli, ["init", "--agent", "opencode", "--libref"])
            assert result.exit_code == 0, result.output
            config_path = workdir / ".deviate" / "config.toml"
            content = config_path.read_text()
            assert "use_libref = true" in content

    def test_init_graphite_key_at_toml_top_level(self, tmp_path: Path):
        """--graphite persists `graphite` at TOML top-level, not nested under [models]."""
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["init", "--agent", "opencode", "--graphite"])
            assert result.exit_code == 0, result.output
            config_path = workdir / ".deviate" / "config.toml"
            parsed = tomllib.loads(config_path.read_text())
            assert parsed.get("graphite") is True, (
                f"graphite missing at top-level; got keys: {list(parsed.keys())} / "
                f"models={parsed.get('models')}"
            )

    def test_init_use_libref_key_at_toml_top_level(self, tmp_path: Path):
        """--libref persists `use_libref` at TOML top-level, not nested under [models]."""
        with chdir(tmp_path):
            workdir = tmp_path
            with patch("shutil.which") as mock_which:
                mock_which.return_value = None
                result = runner.invoke(cli, ["init", "--agent", "opencode", "--libref"])
            assert result.exit_code == 0, result.output
            config_path = workdir / ".deviate" / "config.toml"
            parsed = tomllib.loads(config_path.read_text())
            assert parsed.get("use_libref") is True, (
                f"use_libref missing at top-level; got keys: {list(parsed.keys())} / "
                f"models={parsed.get('models')}"
            )

    def test_init_graphite_and_libref_combined(self, tmp_path: Path):
        """--graphite --libref together: both flags at top-level AND both governance sections."""
        with chdir(tmp_path):
            workdir = tmp_path
            with patch("shutil.which") as mock_which:
                mock_which.return_value = None
                result = runner.invoke(
                    cli, ["init", "--agent", "opencode", "--graphite", "--libref"]
                )
            assert result.exit_code == 0, result.output

            config_path = workdir / ".deviate" / "config.toml"
            parsed = tomllib.loads(config_path.read_text())
            assert parsed.get("graphite") is True
            assert parsed.get("use_libref") is True

            for fname in ["CLAUDE.md", "AGENTS.md"]:
                content = (workdir / fname).read_text()
                assert "## Graphite Stacked Changes Workflow" in content
                assert "## Offline Documentation System" in content

    def test_resolve_graphite_config_round_trip_after_init(self, tmp_path: Path):
        """init --graphite produces a config that resolve_graphite_config() reads as True."""
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["init", "--agent", "opencode", "--graphite"])
            assert result.exit_code == 0, result.output
            assert resolve_graphite_config(workdir) is True

    def test_init_graphite_updates_existing_config(self, tmp_path: Path):
        """Re-running init --graphite on existing repo persists graphite = true."""
        with chdir(tmp_path):
            workdir = tmp_path
            runner.invoke(cli, ["init", "--agent", "opencode"])
            config_path = workdir / ".deviate" / "config.toml"
            assert "graphite = false" in config_path.read_text()

            result = runner.invoke(cli, ["init", "--agent", "opencode", "--graphite"])
            assert result.exit_code == 0, result.output
            parsed = tomllib.loads(config_path.read_text())
            assert parsed.get("graphite") is True

    def test_init_libref_updates_existing_config(self, tmp_path: Path):
        """Re-running init --libref on existing repo persists use_libref = true."""
        with chdir(tmp_path):
            workdir = tmp_path
            with patch("shutil.which", return_value=None):
                runner.invoke(cli, ["init", "--agent", "opencode"])
            config_path = workdir / ".deviate" / "config.toml"
            assert "use_libref = false" in config_path.read_text()

            with patch("shutil.which", return_value=None):
                result = runner.invoke(cli, ["init", "--agent", "opencode", "--libref"])
            assert result.exit_code == 0, result.output
            parsed = tomllib.loads(config_path.read_text())
            assert parsed.get("use_libref") is True

    def test_init_graphite_preserves_other_config_keys(self, tmp_path: Path):
        """init --graphite on existing config preserves user [models] section."""
        with chdir(tmp_path):
            workdir = tmp_path
            dot_dir = workdir / ".deviate"
            dot_dir.mkdir()
            config_path = dot_dir / "config.toml"
            config_path.write_text(
                'profile = "custom"\n\n[models]\ndefault = "opencode/deepseek-v4-flash"\n',
                encoding="utf-8",
            )

            result = runner.invoke(cli, ["init", "--agent", "opencode", "--graphite"])
            assert result.exit_code == 0, result.output
            parsed = tomllib.loads(config_path.read_text())
            assert parsed.get("graphite") is True
            assert parsed.get("profile") == "custom"
            assert parsed["models"]["default"] == "opencode/deepseek-v4-flash"

    def test_init_no_flags_preserves_existing_config(self, tmp_path: Path):
        """init (no flags) on existing config does NOT touch the file."""
        with chdir(tmp_path):
            workdir = tmp_path
            dot_dir = workdir / ".deviate"
            dot_dir.mkdir()
            config_path = dot_dir / "config.toml"
            original = 'profile = "preserved"\n\n[agent]\nbackend = "opencode"\n'
            config_path.write_text(original, encoding="utf-8")

            result = runner.invoke(cli, ["init", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            assert config_path.read_text() == original

    def test_resolve_graphite_config_true(self, tmp_path: Path) -> None:
        dot_dir = tmp_path / ".deviate"
        dot_dir.mkdir(parents=True)
        config_path = dot_dir / "config.toml"
        config_path.write_text("graphite = true\n", encoding="utf-8")
        assert resolve_graphite_config(tmp_path) is True

    def test_resolve_graphite_config_false(self, tmp_path: Path) -> None:
        dot_dir = tmp_path / ".deviate"
        dot_dir.mkdir(parents=True)
        config_path = dot_dir / "config.toml"
        config_path.write_text("graphite = false\n", encoding="utf-8")
        assert resolve_graphite_config(tmp_path) is False

    def test_resolve_graphite_config_key_absent(self, tmp_path: Path) -> None:
        dot_dir = tmp_path / ".deviate"
        dot_dir.mkdir(parents=True)
        config_path = dot_dir / "config.toml"
        config_path.write_text('profile = "default"\n', encoding="utf-8")
        assert resolve_graphite_config(tmp_path) is False

    def test_resolve_graphite_config_no_config(self, tmp_path: Path) -> None:
        assert resolve_graphite_config(tmp_path) is False


class TestInitGraphiteFlag:
    """RED phase tests for TSK-007-02: --graphite flag on deviate init."""

    def test_init_with_graphite_flag(self, tmp_path: Path):
        """AC-ADHOC-007-01: --graphite flag writes graphite = true in config.toml."""
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["init", "--agent", "opencode", "--graphite"])
            assert result.exit_code == 0, result.output
            config_path = workdir / ".deviate" / "config.toml"
            assert config_path.exists()
            content = config_path.read_text()
            assert "graphite = true" in content

    def test_init_without_graphite_flag(self, tmp_path: Path):
        """AC-ADHOC-007-02: Default init either omits graphite or sets false."""
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["init", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            config_path = workdir / ".deviate" / "config.toml"
            assert config_path.exists()
            content = config_path.read_text()
            if "graphite" in content:
                assert "graphite = false" in content

    def test_init_graphite_governance_section(self, tmp_path: Path):
        """AC-ADHOC-007-03: Graphite section appears in governance seeds when enabled."""
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["init", "--agent", "opencode", "--graphite"])
            assert result.exit_code == 0, result.output
            for fname in ["CLAUDE.md", "AGENTS.md"]:
                fpath = workdir / fname
                assert fpath.exists()
                content = fpath.read_text()
                assert "## Graphite Stacked Changes Workflow" in content

    def test_init_graphite_governance_absent_when_disabled(self, tmp_path: Path):
        """AC-ADHOC-007-04: No Graphite section when graphite disabled."""
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["init", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            for fname in ["CLAUDE.md", "AGENTS.md"]:
                fpath = workdir / fname
                assert fpath.exists()
                content = fpath.read_text()
                assert "## Graphite Stacked Changes Workflow" not in content

    def test_scaffold_dotfiles_with_graphite_true(self, tmp_path: Path):
        """_scaffold_dotfiles(graphite=True) writes graphite = true."""
        from deviate.cli import _scaffold_dotfiles

        _scaffold_dotfiles(tmp_path, "local", graphite=True)
        config_path = tmp_path / ".deviate" / "config.toml"
        assert config_path.exists()
        content = config_path.read_text()
        assert "graphite = true" in content

    def test_scaffold_dotfiles_with_graphite_false(self, tmp_path: Path):
        """_scaffold_dotfiles(graphite=False) omits graphite or sets false."""
        from deviate.cli import _scaffold_dotfiles

        _scaffold_dotfiles(tmp_path, "local", graphite=False)
        config_path = tmp_path / ".deviate" / "config.toml"
        assert config_path.exists()
        content = config_path.read_text()
        if "graphite" in content:
            assert "graphite = false" in content

    def test_apply_governance_with_graphite(self, tmp_path: Path):
        """_apply_governance(graphite=True) emits Graphite section."""
        from deviate.cli import _apply_governance

        _apply_governance(tmp_path, graphite=True)
        for fname in ["CLAUDE.md", "AGENTS.md"]:
            fpath = tmp_path / fname
            assert fpath.exists()
            content = fpath.read_text()
            assert "## Graphite Stacked Changes Workflow" in content
            assert "gt create -am" in content
            assert "gt submit --stack" in content

    def test_apply_governance_without_graphite(self, tmp_path: Path):
        """_apply_governance(graphite=False) omits Graphite section."""
        from deviate.cli import _apply_governance

        _apply_governance(tmp_path, graphite=False)
        for fname in ["CLAUDE.md", "AGENTS.md"]:
            fpath = tmp_path / fname
            assert fpath.exists()
            content = fpath.read_text()
            assert "## Graphite Stacked Changes Workflow" not in content

    def test_init_scaffolds_constitution_placeholder(self, tmp_path: Path):
        """Init writes a placeholder specs/constitution.md when none exists."""
        with chdir(tmp_path):
            result = runner.invoke(cli, ["init", "--agent", "opencode"])
            assert result.exit_code == 0, result.output

            const_path = tmp_path / "specs" / "constitution.md"
            assert const_path.exists()
            content = const_path.read_text()
            assert "# Project Constitution" in content
            assert "TBD" in content
            assert "## 3. TESTING_PROTOCOLS" in content

    def test_init_scaffold_constitution_idempotent(self, tmp_path: Path):
        """Re-running init preserves existing specs/constitution.md."""
        with chdir(tmp_path):
            result = runner.invoke(cli, ["init", "--agent", "opencode"])
            assert result.exit_code == 0, result.output

            const_path = tmp_path / "specs" / "constitution.md"
            original = const_path.read_text()

            result2 = runner.invoke(cli, ["init", "--agent", "opencode"])
            assert result2.exit_code == 0, result2.output
            assert const_path.read_text() == original

    def test_init_graphite_governance_section_present(self, tmp_path: Path):
        """AC-ADHOC-007-03: Graphite section present via _apply_governance."""
        from deviate.cli import _apply_governance

        _apply_governance(tmp_path, graphite=True)
        for fname in ["CLAUDE.md", "AGENTS.md"]:
            fpath = tmp_path / fname
            assert fpath.exists()
            content = fpath.read_text()
            assert "## Graphite Stacked Changes Workflow" in content

    def test_init_graphite_governance_section_absent(self, tmp_path: Path):
        """AC-ADHOC-007-04: Graphite section absent via _apply_governance."""
        from deviate.cli import _apply_governance

        _apply_governance(tmp_path, graphite=False)
        for fname in ["CLAUDE.md", "AGENTS.md"]:
            fpath = tmp_path / fname
            assert fpath.exists()
            content = fpath.read_text()
            assert "## Graphite Stacked Changes Workflow" not in content

    def test_init_graphite_governance_idempotent(self, tmp_path: Path):
        """Re-running _apply_governance updates existing Graphite section."""
        from deviate.cli import _apply_governance

        _apply_governance(tmp_path, graphite=True)
        claude_path = tmp_path / "CLAUDE.md"
        original = claude_path.read_text()
        assert "## Graphite Stacked Changes Workflow" in original

        outdated_section = "\n\n## Graphite Stacked Changes Workflow\n\nOutdated content\n\n## Unrelated\nKept\n"
        claude_path.write_text(outdated_section, encoding="utf-8")

        _apply_governance(tmp_path, graphite=True)
        updated = claude_path.read_text()
        assert "Outdated content" not in updated
        assert "gt create -am" in updated
        assert "gt submit --stack" in updated
        assert "## Unrelated" in updated
        assert "Kept" in updated


class TestInitAgentFlag:
    """RED phase tests for the --agent flag persistence contract.

    The flag must:
        1. Write ``[agent].backend`` to ``.deviate/config.toml``.
        2. Map user-facing agent names to the underlying meso/micro backend.
        3. Be rejected at the Typer layer for unknown values.
        4. Drive interactive selection when neither flag nor config provides
           a choice.
    """

    def test_init_agent_factory_writes_droid_backend(self, tmp_path: Path):
        """`--agent factory` persists ``backend = "droid"`` (Factory IDE → droid binary)."""
        with chdir(tmp_path):
            result = runner.invoke(cli, ["init", "--agent", "factory"])
            assert result.exit_code == 0, result.output
            config_path = tmp_path / ".deviate" / "config.toml"
            parsed = tomllib.loads(config_path.read_text())
            assert parsed["agent"]["backend"] == "droid"

    def test_init_agent_droid_writes_droid_backend(self, tmp_path: Path):
        """`--agent droid` persists ``backend = "droid"``."""
        with chdir(tmp_path):
            result = runner.invoke(cli, ["init", "--agent", "droid"])
            assert result.exit_code == 0, result.output
            config_path = tmp_path / ".deviate" / "config.toml"
            parsed = tomllib.loads(config_path.read_text())
            assert parsed["agent"]["backend"] == "droid"

    def test_init_agent_claude_writes_claude_backend(self, tmp_path: Path):
        """`--agent claude` persists ``backend = "claude"``."""
        with chdir(tmp_path):
            result = runner.invoke(cli, ["init", "--agent", "claude"])
            assert result.exit_code == 0, result.output
            config_path = tmp_path / ".deviate" / "config.toml"
            parsed = tomllib.loads(config_path.read_text())
            assert parsed["agent"]["backend"] == "claude"

    def test_init_agent_opencode_writes_opencode_backend(self, tmp_path: Path):
        """`--agent opencode` persists ``backend = "opencode"``."""
        with chdir(tmp_path):
            result = runner.invoke(cli, ["init", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            config_path = tmp_path / ".deviate" / "config.toml"
            parsed = tomllib.loads(config_path.read_text())
            assert parsed["agent"]["backend"] == "opencode"

    def test_init_agent_factory_overwrites_existing_backend(self, tmp_path: Path):
        """`--agent factory` overwrites a previously persisted `opencode` backend."""
        with chdir(tmp_path):
            runner.invoke(cli, ["init", "--agent", "opencode"])
            config_path = tmp_path / ".deviate" / "config.toml"
            assert (
                tomllib.loads(config_path.read_text())["agent"]["backend"] == "opencode"
            )

            result = runner.invoke(cli, ["init", "--agent", "factory"])
            assert result.exit_code == 0, result.output
            assert tomllib.loads(config_path.read_text())["agent"]["backend"] == "droid"

    def test_init_agent_rejects_unknown_value(self, tmp_path: Path):
        """`--agent` rejects values outside the supported set."""
        with chdir(tmp_path):
            result = runner.invoke(cli, ["init", "--agent", "aider"])
            assert result.exit_code != 0
            assert "aider" in result.output

    def test_init_agent_droid_routes_skills_to_detected_dirs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """`--agent droid` does not own a skills dir; pre-existing dirs still receive skills."""
        monkeypatch.setattr(
            "deviate.cli._get_agent_skill_dir",
            lambda agent, _workdir: tmp_path / f".{agent}" / "skills",
        )
        (tmp_path / ".claude").mkdir()
        with chdir(tmp_path):
            result = runner.invoke(cli, ["init", "--agent", "droid"])
            assert result.exit_code == 0, result.output
            assert (tmp_path / ".claude" / "skills").exists()

    def test_init_no_agent_no_config_non_interactive_errors(self, tmp_path: Path):
        """Without `--agent`, no config, and no TTY → init exits with a clear error."""
        with chdir(tmp_path):
            result = runner.invoke(cli, ["init"])
            assert result.exit_code != 0
            assert "NO_AGENT_SELECTED" in result.output

    def test_init_no_agent_uses_existing_config(self, tmp_path: Path):
        """Without `--agent` but with a pre-populated ``[agent].backend``, init uses it."""
        with chdir(tmp_path):
            dot_dir = tmp_path / ".deviate"
            dot_dir.mkdir()
            (dot_dir / "config.toml").write_text(
                '[agent]\nbackend = "claude"\n', encoding="utf-8"
            )

            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0, result.output
            parsed = tomllib.loads((dot_dir / "config.toml").read_text())
            assert parsed["agent"]["backend"] == "claude"

    def test_init_interactive_prompt_writes_choice_to_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """When interactive, the user-selected agent is persisted to config."""
        monkeypatch.setattr("deviate.cli._prompt_agent_selection", lambda *_: "factory")
        with chdir(tmp_path):
            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0, result.output
            config_path = tmp_path / ".deviate" / "config.toml"
            assert tomllib.loads(config_path.read_text())["agent"]["backend"] == "droid"

    def test_init_interactive_prompt_default_is_existing_backend(self, tmp_path: Path):
        """The interactive prompt should pre-select the current backend as default."""
        from deviate.cli import _read_agent_backend_from_config

        dot_dir = tmp_path / ".deviate"
        dot_dir.mkdir()
        config_path = dot_dir / "config.toml"
        config_path.write_text('[agent]\nbackend = "droid"\n', encoding="utf-8")
        assert _read_agent_backend_from_config(config_path) == "droid"

    def test_init_agent_choice_constant_exposes_supported_set(self):
        from deviate.cli import AGENT_CHOICES

        assert set(AGENT_CHOICES) == {"factory", "droid", "claude", "opencode"}

    def test_init_agent_to_backend_mapping(self):
        from deviate.cli import AGENT_TO_BACKEND

        assert AGENT_TO_BACKEND["factory"] == "droid"
        assert AGENT_TO_BACKEND["droid"] == "droid"
        assert AGENT_TO_BACKEND["claude"] == "claude"
        assert AGENT_TO_BACKEND["opencode"] == "opencode"


def test_version():
    from importlib.metadata import version

    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"deviate {version('deviate')}"
