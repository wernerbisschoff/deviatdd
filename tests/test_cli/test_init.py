import subprocess
import tomllib
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.cli.__init__ import resolve_graphite_config
from deviate.core.commands import _resolve_commands_root
from tests.conftest import _git_env

runner = CliRunner()

_PRODUCT_LAYER_SKILLS = ("deviate-flows", "deviate-architecture", "deviate-release")


class TestInitCommand:
    def test_init_creates_dotfile_structure(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            assert (workdir / ".deviate" / "config.toml").exists()
            assert (workdir / ".deviate" / "session.json").exists()

    def test_init_appends_governance_to_nonexistent_file(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            claude_path = workdir / "CLAUDE.md"
            assert claude_path.exists()
            content = claude_path.read_text()
            # Phase Architecture block was removed (project-internal, did not
            # help consuming projects). The libref block is still seeded.
            assert "## 🛠 DeviaTDD Phase Architecture" not in content
            assert "## 📚 Offline Documentation (libref)" in content

    def test_init_replaces_governance_block_in_place(self, tmp_path: Path):
        """Existing governance block is replaced without duplication; unrelated sections are preserved."""
        with chdir(tmp_path):
            workdir = tmp_path
            claude_path = workdir / "CLAUDE.md"
            existing_content = (
                "# My Project\n\n"
                "## 📚 Offline Documentation (libref)\n"
                "Old docs content\n\n"
                "## Other Section\n"
                "Preserved content\n"
            )
            claude_path.write_text(existing_content)

            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output

            content = claude_path.read_text()
            assert "Old docs content" not in content
            assert "Preserved content" in content
            assert "## Other Section" in content
            assert content.count("## 📚 Offline Documentation (libref)") == 1

    def test_init_normalized_heading_replaces_annotated_heading(self, tmp_path: Path):
        """Existing heading has emoji/parenthetical that seed lacks; normalized match finds it."""
        with chdir(tmp_path):
            workdir = tmp_path
            claude_path = workdir / "CLAUDE.md"
            existing_content = (
                "# Project\n\n"
                "## 📚 Offline Documentation (libref) — MANDATORY\n"
                "Old docs content\n\n"
                "## Other Section\n"
                "Preserved\n"
            )
            claude_path.write_text(existing_content)

            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output

            content = claude_path.read_text()
            assert "Old docs content" not in content
            assert "Preserved" in content
            assert "## Other Section" in content
            assert content.count("## 📚 Offline Documentation (libref)") == 1

    def test_init_skip_existing_dotfiles(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            dotfile_dir = workdir / ".deviate"
            dotfile_dir.mkdir()
            config_path = dotfile_dir / "config.toml"
            original_content = 'profile = "custom"\n\n[agent]\nbackend = "opencode"\n'
            config_path.write_text(original_content)

            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
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

            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            assert session_path.exists()

    def test_init_detects_libref(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            with patch("shutil.which") as mock_which:
                mock_which.return_value = "/usr/local/bin/libref"
                result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            config_path = workdir / ".deviate" / "config.toml"
            content = config_path.read_text()
            assert "use_libref = true" in content

    def test_init_missing_libref(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            with patch("shutil.which") as mock_which:
                mock_which.return_value = None
                result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            config_path = workdir / ".deviate" / "config.toml"
            content = config_path.read_text()
            assert "use_libref = false" in content

    def test_init_libref_governance_block(self, tmp_path: Path):
        with chdir(tmp_path):
            workdir = tmp_path
            with patch("shutil.which") as mock_which:
                mock_which.return_value = "/usr/local/bin/libref"
                result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output

            claude_path = workdir / "CLAUDE.md"
            assert claude_path.exists()
            claude_content = claude_path.read_text()
            assert "## 📚 Offline Documentation (libref)" in claude_content
            assert "libref query" in claude_content
            assert "libref list" in claude_content
            assert "libref add" in claude_content

            agents_path = workdir / "AGENTS.md"
            assert agents_path.exists()
            agents_content = agents_path.read_text()
            assert "## 📚 Offline Documentation (libref)" in agents_content

    def test_init_libref_flag_overrides_missing_binary(self, tmp_path: Path):
        """--libref forces use_libref=true even when shutil.which returns None."""
        with chdir(tmp_path):
            workdir = tmp_path
            with patch("shutil.which") as mock_which:
                mock_which.return_value = None
                result = runner.invoke(
                    cli, ["setup", "--agent", "opencode", "--libref"]
                )
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
                result = runner.invoke(
                    cli, ["setup", "--agent", "opencode", "--libref"]
                )
            assert result.exit_code == 0, result.output
            config_path = workdir / ".deviate" / "config.toml"
            content = config_path.read_text()
            assert "use_libref = true" in content

    def test_init_graphite_key_at_toml_top_level(self, tmp_path: Path):
        """--graphite persists `graphite` at TOML top-level, not nested under [models]."""
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["setup", "--agent", "opencode", "--graphite"])
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
                result = runner.invoke(
                    cli, ["setup", "--agent", "opencode", "--libref"]
                )
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
                    cli, ["setup", "--agent", "opencode", "--graphite", "--libref"]
                )
            assert result.exit_code == 0, result.output

            config_path = workdir / ".deviate" / "config.toml"
            parsed = tomllib.loads(config_path.read_text())
            assert parsed.get("graphite") is True
            assert parsed.get("use_libref") is True

            for fname in ["CLAUDE.md", "AGENTS.md"]:
                content = (workdir / fname).read_text()
                assert "## Graphite Stacked Changes Workflow" in content
                assert "## 📚 Offline Documentation (libref)" in content

    def test_resolve_graphite_config_round_trip_after_init(self, tmp_path: Path):
        """init --graphite produces a config that resolve_graphite_config() reads as True."""
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["setup", "--agent", "opencode", "--graphite"])
            assert result.exit_code == 0, result.output
            assert resolve_graphite_config(workdir) is True

    def test_init_graphite_updates_existing_config(self, tmp_path: Path):
        """Re-running init --graphite on existing repo persists graphite = true."""
        with chdir(tmp_path):
            workdir = tmp_path
            runner.invoke(cli, ["setup", "--agent", "opencode"])
            config_path = workdir / ".deviate" / "config.toml"
            assert "graphite = false" in config_path.read_text()

            result = runner.invoke(cli, ["setup", "--agent", "opencode", "--graphite"])
            assert result.exit_code == 0, result.output
            parsed = tomllib.loads(config_path.read_text())
            assert parsed.get("graphite") is True

    def test_init_libref_updates_existing_config(self, tmp_path: Path):
        """Re-running init --libref on existing repo persists use_libref = true."""
        with chdir(tmp_path):
            workdir = tmp_path
            with patch("shutil.which", return_value=None):
                runner.invoke(cli, ["setup", "--agent", "opencode"])
            config_path = workdir / ".deviate" / "config.toml"
            assert "use_libref = false" in config_path.read_text()

            with patch("shutil.which", return_value=None):
                result = runner.invoke(
                    cli, ["setup", "--agent", "opencode", "--libref"]
                )
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

            result = runner.invoke(cli, ["setup", "--agent", "opencode", "--graphite"])
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

            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
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

    def test_init_creates_product_layer_skills(self) -> None:
        """TSK-010-01: three Product-layer SKILL.md templates exist with canonical
        YAML frontmatter (``name``, ``category: deviatdd-product-layer``,
        ``aliases`` containing slash-command forms).

        Source: ``specs/_product/release-next.md:26`` (acceptance criterion) and
        ``src/deviate/prompts/commands/deviate-constitution.md:1-11``
        (canonical frontmatter schema reference).
        """
        commands_root = _resolve_commands_root()

        for skill_name in _PRODUCT_LAYER_SKILLS:
            skill_path = commands_root / f"{skill_name}.md"
            assert skill_path.exists(), (
                f"Product-layer skill template missing: {skill_path}"
            )

            content = skill_path.read_text(encoding="utf-8")
            assert content.lstrip().startswith("---"), (
                f"{skill_name}: SKILL.md missing YAML frontmatter delimiter"
            )

            fm = yaml.safe_load(content.split("---", 2)[1])
            assert isinstance(fm, dict), (
                f"{skill_name}: frontmatter did not parse to a dict"
            )

            assert fm.get("name") == skill_name, (
                f"{skill_name}: frontmatter name mismatch (got {fm.get('name')!r})"
            )
            assert fm.get("category") == "deviatdd-product-layer", (
                f"{skill_name}: category must be 'deviatdd-product-layer' "
                f"(got {fm.get('category')!r})"
            )

            aliases = fm.get("aliases")
            assert isinstance(aliases, list) and aliases, (
                f"{skill_name}: aliases must be a non-empty flat YAML list"
            )
            assert f"/{skill_name}" in aliases, (
                f"{skill_name}: aliases must include slash-command /{skill_name} "
                f"(got {aliases!r})"
            )
            assert f"spec:{skill_name.split('-', 1)[1]}" in aliases, (
                f"{skill_name}: aliases must include spec:<skill> form "
                f"(got {aliases!r})"
            )

            description = fm.get("description")
            assert isinstance(description, str) and "\n" not in description, (
                f"{skill_name}: description must be a single-line string"
            )

    def test_init_product_layer_skills_idempotent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TSK-010-01: re-running ``deviate setup --agent claude`` against a workdir
        where the three Product-layer skill files are already installed produces
        SKIP log lines (no errors, no duplicate writes).

        Source: ``src/deviate/cli/__init__.py:518-531`` (``_install_commands_to_agents``)
        existing skip-on-equal-content logic.
        """
        monkeypatch.setattr(
            "deviate.cli._get_agent_command_dir",
            lambda agent, _workdir: tmp_path / f".{agent}" / "commands",
        )
        (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)

        with chdir(tmp_path):
            first = runner.invoke(cli, ["setup", "--agent", "claude"])
            assert first.exit_code == 0, first.output

            for skill_name in _PRODUCT_LAYER_SKILLS:
                installed = tmp_path / ".claude" / "commands" / f"{skill_name}.md"
                assert installed.exists(), (
                    f"first setup did not install {skill_name}: {installed}"
                )

            second = runner.invoke(cli, ["setup", "--agent", "claude"])
            assert second.exit_code == 0, second.output

            for skill_name in _PRODUCT_LAYER_SKILLS:
                assert "SKIP" in second.output, (
                    f"second setup did not emit SKIP log for {skill_name}; "
                    f"got: {second.output!r}"
                )

    def test_init_discover_commands_enumerates_product_layer(self) -> None:
        """TSK-010-06: ``discover_commands()`` enumerates >= 23 skill names and
        includes the three new Product-layer skills (``deviate-flows``,
        ``deviate-architecture``, ``deviate-release``) exactly once each.

        Source: AC-ADHOC-010-02 (``discover_commands()`` must return 23 names after
        the three Product-layer skills are added; >= 23 chosen for forward
        compatibility per ``specs/adhoc/010-deviate-setup-product-layer/tasks.md``
        §`Risk Hotspots`).
        """
        from deviate.core.commands import discover_commands

        skills = discover_commands()

        assert len(skills) >= 23, (
            f"discover_commands() returned {len(skills)} skill names; "
            f"expected >= 23. Got: {sorted(skills)}"
        )

        for skill_name in _PRODUCT_LAYER_SKILLS:
            assert skill_name in skills, (
                f"Product-layer skill '{skill_name}' missing from "
                f"discover_commands() output. Got: {sorted(skills)}"
            )
            assert skills.count(skill_name) == 1, (
                f"Product-layer skill '{skill_name}' appears "
                f"{skills.count(skill_name)} times in discover_commands() output; "
                f"expected exactly 1. Got: {sorted(skills)}"
            )

    def test_init_user_input_injection_seam_convention(self) -> None:
        """Every skill declares exactly one ``<user_input>$ARGUMENTS</user_input>``
        runtime injection seam and exactly one ``$ARGUMENTS`` literal in the
        entire file.

        Locks in the convention that the literal user message is never baked
        into a skill and that the runtime substitution anchor is present
        exactly once. Skills may carry inline ``<example>`` fixtures higher
        in the file (e.g. the ``<few_shot_examples>`` block in
        ``deviate-constitution``), but those MUST NOT use the
        ``<user_input>`` tag — that tag name is reserved for the runtime
        injection seam only.

        Source: regression guard for the refiner bug that embedded the
        literal text ``"and update the above prompt in place"`` into
        ``deviate-flows/SKILL.md`` and the literal Go/Postgres example into
        ``deviate-constitution/SKILL.md``.
        """
        import re

        from deviate.core.commands import discover_commands

        commands_root = _resolve_commands_root()
        user_input_re = re.compile(
            r"<user_input>\s*(\$ARGUMENTS)\s*</user_input>", re.DOTALL
        )

        violations: list[str] = []
        for skill_name in discover_commands():
            skill_path = commands_root / f"{skill_name}.md"
            if not skill_path.exists():
                continue
            content = skill_path.read_text(encoding="utf-8")

            arguments_count = content.count("$ARGUMENTS")
            if arguments_count != 1:
                violations.append(
                    f"{skill_name}: expected exactly one $ARGUMENTS literal "
                    f"(got {arguments_count})"
                )
                continue

            matches = list(user_input_re.finditer(content))
            if len(matches) != 1:
                violations.append(
                    f"{skill_name}: expected exactly one canonical "
                    f"<user_input>$ARGUMENTS</user_input> block (got "
                    f"{len(matches)}). Inline example fixtures must use a "
                    f"different tag, e.g. <example_user_input>."
                )

        assert not violations, (
            "user_input injection seam convention violations:\n  - "
            + "\n  - ".join(violations)
        )


class TestInitGraphiteFlag:
    """RED phase tests for TSK-007-02: --graphite flag on deviate init."""

    def test_init_with_graphite_flag(self, tmp_path: Path):
        """AC-ADHOC-007-01: --graphite flag writes graphite = true in config.toml."""
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["setup", "--agent", "opencode", "--graphite"])
            assert result.exit_code == 0, result.output
            config_path = workdir / ".deviate" / "config.toml"
            assert config_path.exists()
            content = config_path.read_text()
            assert "graphite = true" in content

    def test_init_without_graphite_flag(self, tmp_path: Path):
        """AC-ADHOC-007-02: Default init either omits graphite or sets false."""
        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
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
            result = runner.invoke(cli, ["setup", "--agent", "opencode", "--graphite"])
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
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
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
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
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
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output

            const_path = tmp_path / "specs" / "constitution.md"
            original = const_path.read_text()

            result2 = runner.invoke(cli, ["setup", "--agent", "opencode"])
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
            result = runner.invoke(cli, ["setup", "--agent", "factory"])
            assert result.exit_code == 0, result.output
            config_path = tmp_path / ".deviate" / "config.toml"
            parsed = tomllib.loads(config_path.read_text())
            assert parsed["agent"]["backend"] == "droid"

    def test_init_agent_droid_writes_droid_backend(self, tmp_path: Path):
        """`--agent droid` persists ``backend = "droid"``."""
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "droid"])
            assert result.exit_code == 0, result.output
            config_path = tmp_path / ".deviate" / "config.toml"
            parsed = tomllib.loads(config_path.read_text())
            assert parsed["agent"]["backend"] == "droid"

    def test_init_agent_claude_writes_claude_backend(self, tmp_path: Path):
        """`--agent claude` persists ``backend = "claude"``."""
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "claude"])
            assert result.exit_code == 0, result.output
            config_path = tmp_path / ".deviate" / "config.toml"
            parsed = tomllib.loads(config_path.read_text())
            assert parsed["agent"]["backend"] == "claude"

    def test_init_agent_opencode_writes_opencode_backend(self, tmp_path: Path):
        """`--agent opencode` persists ``backend = "opencode"``."""
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            config_path = tmp_path / ".deviate" / "config.toml"
            parsed = tomllib.loads(config_path.read_text())
            assert parsed["agent"]["backend"] == "opencode"

    def test_init_agent_factory_overwrites_existing_backend(self, tmp_path: Path):
        """`--agent factory` overwrites a previously persisted `opencode` backend."""
        with chdir(tmp_path):
            runner.invoke(cli, ["setup", "--agent", "opencode"])
            config_path = tmp_path / ".deviate" / "config.toml"
            assert (
                tomllib.loads(config_path.read_text())["agent"]["backend"] == "opencode"
            )

            result = runner.invoke(cli, ["setup", "--agent", "factory"])
            assert result.exit_code == 0, result.output
            assert tomllib.loads(config_path.read_text())["agent"]["backend"] == "droid"

    def test_init_agent_rejects_unknown_value(self, tmp_path: Path):
        """`--agent` rejects values outside the supported set."""
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "aider"])
            assert result.exit_code != 0
            assert "aider" in result.output

    def test_init_agent_droid_routes_skills_to_detected_dirs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """`--agent droid` shares the Factory Droid IDE skills directory.

        Both ``droid`` and ``factory`` dispatch to the same backend binary and
        install skills into ``.factory/skills/deviate-*/`` — there is no
        ``.droid/skills/`` directory.
        """
        monkeypatch.setattr(
            "deviate.cli._get_agent_command_dir",
            lambda agent, _workdir: tmp_path / f".{agent}" / "commands",
        )
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "droid"])
            assert result.exit_code == 0, result.output
            assert (tmp_path / ".factory" / "commands").exists()
            assert not (tmp_path / ".droid").exists()

    def test_init_agent_droid_writes_root_gitignore_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """`--agent droid` does NOT create a ``.droid/`` directory.

        The root ``.gitignore`` covers ``*/commands/deviate-*.md``
        so no per-agent ``.gitignore`` is created.
        ``droid`` is normalised to ``factory`` for the command directory.
        """
        monkeypatch.setattr(
            "deviate.cli._get_agent_command_dir",
            lambda agent, _workdir: tmp_path / f".{agent}" / "commands",
        )
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "droid"])
            assert result.exit_code == 0, result.output
            assert not (tmp_path / ".droid").exists()
            assert not (tmp_path / ".factory" / ".gitignore").exists()
            root_gi = (tmp_path / ".gitignore").read_text(encoding="utf-8")
            assert "*/commands/deviate-*.md" in root_gi

    def test_init_writes_root_gitignore_for_all_agent_dirs(self, tmp_path: Path):
        """``deviate setup`` writes four ``*/commands/`` and ``*/prompts/``
        patterns to the project-root ``.gitignore``.

        The single-level ``*/`` prefix scopes the patterns to one directory
        before ``commands/`` or ``prompts/`` — broad enough to cover every
        supported agent (``.claude/``, ``.opencode/``, ``.factory/``,
        ``.pi/``) but tight enough NOT to match the project's own source
        paths (e.g. ``src/deviate/prompts/commands/``, which is three
        directories deep).
        """
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            root_gi = (tmp_path / ".gitignore").read_text(encoding="utf-8")
            assert "*/commands/deviate-*.md" in root_gi
            assert "*/prompts/deviate-*.md" in root_gi

    def test_init_installs_commands_to_all_agent_dirs(self, tmp_path: Path):
        """``deviate setup --agent <x>`` installs the command library into
        EVERY agent's command directory, not just the one selected.

        ``--agent`` is the meso/micro backend selector; command installation
        is intentionally unconditional so a single ``setup`` run prepares
        the workspace for any of the supported agents.
        """
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            for agent_dir, sub in (
                (".claude", "commands"),
                (".opencode", "commands"),
                (".factory", "commands"),
                (".pi", "prompts"),
            ):
                sample = tmp_path / agent_dir / sub / "deviate-red.md"
                assert sample.exists(), (
                    f"Expected {sample} to exist — setup installs into ALL "
                    f"agent dirs regardless of --agent"
                )

    def test_init_root_gitignore_preserves_user_content(self, tmp_path: Path):
        """User-authored entries in the root ``.gitignore`` are preserved when
        DeviaTDD writes its agent-command exclusion entries.
        """
        (tmp_path / ".gitignore").write_text(
            "# user content\ncustom-thing/\n", encoding="utf-8"
        )
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            root_gi = (tmp_path / ".gitignore").read_text(encoding="utf-8")
            assert "# user content" in root_gi
            assert "custom-thing/" in root_gi
            assert "*/commands/deviate-*.md" in root_gi

    def test_init_root_gitignore_idempotent_across_runs(self, tmp_path: Path):
        """Re-running ``deviate setup`` does not duplicate the gitignore entries."""
        with chdir(tmp_path):
            runner.invoke(cli, ["setup", "--agent", "opencode"])
            runner.invoke(cli, ["setup", "--agent", "opencode"])
            root_gi = (tmp_path / ".gitignore").read_text(encoding="utf-8")
            for entry in (
                "*/commands/deviate-*.md",
                "*/prompts/deviate-*.md",
            ):
                assert root_gi.count(entry) == 1, (
                    f"{entry} duplicated in root .gitignore"
                )

    # ------------------------------------------------------------------
    # .gitattributes — append-only JSONL ledger union-merge strategy
    # ------------------------------------------------------------------
    def test_init_writes_root_gitattributes_with_union_driver(self, tmp_path: Path):
        """``deviate setup`` writes ``.gitattributes`` with ``merge=union``
        applied to the append-only JSONL ledgers declared by the
        Append-Only Ledger Protocol (constitution §1).

        Without this, concurrent ``deviate shard`` runs on feature
        branches produce line-level conflicts in ``specs/issues.jsonl``
        at merge time. ``merge=union`` resolves those conflicts
        automatically by keeping the line-wise union of all sides.
        """
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            attr_path = tmp_path / ".gitattributes"
            assert attr_path.exists(), ".gitattributes not written by setup"
            content = attr_path.read_text(encoding="utf-8")
            assert "specs/issues.jsonl merge=union" in content
            assert "specs/**/tasks.jsonl merge=union" in content

    def test_init_root_gitattributes_preserves_user_content(self, tmp_path: Path):
        """User-authored entries in the root ``.gitattributes`` are
        preserved when ``deviate setup`` adds its union-merge rules.
        """
        (tmp_path / ".gitattributes").write_text(
            "# user content\n*.log binary\n", encoding="utf-8"
        )
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            content = (tmp_path / ".gitattributes").read_text(encoding="utf-8")
            assert "# user content" in content
            assert "*.log binary" in content
            assert "specs/issues.jsonl merge=union" in content
            assert "specs/**/tasks.jsonl merge=union" in content

    def test_init_root_gitattributes_idempotent_across_runs(self, tmp_path: Path):
        """Re-running ``deviate setup`` does not duplicate the
        union-merge entries in ``.gitattributes``.
        """
        with chdir(tmp_path):
            runner.invoke(cli, ["setup", "--agent", "opencode"])
            runner.invoke(cli, ["setup", "--agent", "opencode"])
            content = (tmp_path / ".gitattributes").read_text(encoding="utf-8")
            for line in (
                "specs/issues.jsonl merge=union",
                "specs/**/tasks.jsonl merge=union",
            ):
                assert content.count(line) == 1, (
                    f"{line!r} duplicated in root .gitattributes"
                )

    def test_init_root_gitattributes_union_driver_recognised_by_git(
        self, tmp_path: Path, tmp_git_repo: Path
    ):
        """Integration guarantee: after ``deviate setup``, git itself
        recognises the ``merge=union`` driver for the ledgers — this
        is what prevents merge conflicts in practice.

        Uses ``tmp_git_repo`` (a real git repo) because ``git check-attr``
        requires being inside a working tree.
        """
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
        # ``git check-attr`` is the canonical way to verify a
        # .gitattributes rule is in effect for a given path.
        attr_out = subprocess.check_output(
            [
                "git",
                "check-attr",
                "-a",
                "specs/issues.jsonl",
            ],
            cwd=tmp_git_repo,
            env=_git_env(),
            text=True,
        )
        assert "merge: union" in attr_out, (
            f"git does not see merge=union for specs/issues.jsonl:\n{attr_out}"
        )
        task_attr_out = subprocess.check_output(
            [
                "git",
                "check-attr",
                "-a",
                "specs/001-test/tasks.jsonl",
            ],
            cwd=tmp_git_repo,
            env=_git_env(),
            text=True,
        )
        assert "merge: union" in task_attr_out, (
            f"git does not see merge=union for "
            f"specs/001-test/tasks.jsonl:\n{task_attr_out}"
        )

    def test_init_pre_writes_root_gitattributes(self, tmp_git_repo: Path):
        """``deviate init pre`` (the Typer sub-group used by skills)
        also provisions ``.gitattributes``. Without this wiring,
        skill-orchestrated init runs would skip the merge strategy
        — a pre-existing asymmetry versus ``deviate setup``.
        """
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["init", "pre"])
            assert result.exit_code == 0, result.output
            content = (tmp_git_repo / ".gitattributes").read_text(encoding="utf-8")
            assert "specs/issues.jsonl merge=union" in content
            assert "specs/**/tasks.jsonl merge=union" in content

    def test_init_seeds_flows_jsonl_merge_union(self, tmp_path: Path):
        """``deviate setup`` seeds ``specs/_product/flows.jsonl merge=union``
        in the root ``.gitattributes``, extending the constitution v0.4.0
        union-merge strategy for the append-only JSONL ledgers.
        """
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
            content = (tmp_path / ".gitattributes").read_text(encoding="utf-8")
            assert "specs/_product/flows.jsonl merge=union" in content
            assert "specs/issues.jsonl merge=union" in content
            assert "specs/**/tasks.jsonl merge=union" in content

    def test_init_no_agent_no_config_non_interactive_errors(self, tmp_path: Path):
        """Without `--agent`, no config, and no TTY → init exits with a clear error."""
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup"])
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

            result = runner.invoke(cli, ["setup"])
            assert result.exit_code == 0, result.output
            parsed = tomllib.loads((dot_dir / "config.toml").read_text())
            assert parsed["agent"]["backend"] == "claude"

    def test_init_interactive_prompt_writes_choice_to_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """When interactive, the user-selected agent is persisted to config."""
        monkeypatch.setattr("deviate.cli._prompt_agent_selection", lambda *_: "factory")
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup"])
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

        assert set(AGENT_CHOICES) == {
            "factory",
            "droid",
            "claude",
            "opencode",
            "pi",
            "omp",
        }

    def test_init_agent_to_backend_mapping(self):
        from deviate.cli import AGENT_TO_BACKEND

        assert AGENT_TO_BACKEND["factory"] == "droid"
        assert AGENT_TO_BACKEND["droid"] == "droid"
        assert AGENT_TO_BACKEND["claude"] == "claude"
        assert AGENT_TO_BACKEND["opencode"] == "opencode"
        # ``pi`` and ``omp`` are canonical backends (not aliases) — each
        # spawns its own binary (``pi -p`` / ``omp -p``).
        assert AGENT_TO_BACKEND["pi"] == "pi"
        assert AGENT_TO_BACKEND["omp"] == "omp"


class TestInitPiBackend:
    """Tests for TSK-009-02: Pi is a project-local agent.

    Validates that ``deviate setup --agent pi``:
        1. Exposes 'pi' in the AGENT_CHOICES / AGENT_TO_BACKEND constants.
        2. File-copies each DeviaTDD skill into
           ``<workdir>/.pi/prompts/<skill-name>/SKILL.md`` (same path convention
           as ``.claude/``, ``.opencode/``, ``.factory/``).
        3. Does NOT write to ``~/.pi/agent/`` (operator's global Pi config is
           out of scope).
        4. Does NOT generate a ``settings.json`` (model/provider selection is
           the operator's responsibility).
        5. Is idempotent — re-running does not duplicate skill files and does
           not corrupt the project state.
    """

    def test_agent_choices_includes_pi(self):
        """AC-ADHOC-009-04: ``AGENT_CHOICES`` exposes 'pi' to users."""
        from deviate.cli import AGENT_CHOICES

        assert "pi" in AGENT_CHOICES

    def test_agent_to_backend_maps_pi(self):
        """AC-ADHOC-009-04: ``AGENT_TO_BACKEND['pi'] == 'pi'``."""
        from deviate.cli import AGENT_TO_BACKEND

        assert AGENT_TO_BACKEND["pi"] == "pi"

    def test_resolve_agent_to_backend_pi_passthrough(self):
        """``_resolve_agent_to_backend('pi')`` returns 'pi' (identity mapping)."""
        from deviate.cli import _resolve_agent_to_backend

        assert _resolve_agent_to_backend("pi") == "pi"

    def test_init_agent_pi_persists_pi_backend(self, tmp_path: Path):
        """``--agent pi`` persists ``backend = 'pi'`` in ``.deviate/config.toml``."""
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "pi"])
            assert result.exit_code == 0, result.output
            config_path = tmp_path / ".deviate" / "config.toml"
            parsed = tomllib.loads(config_path.read_text())
            assert parsed["agent"]["backend"] == "pi"

    def test_init_creates_pi_skill_files(self, tmp_path: Path):
        """AC-ADHOC-009-02: ``--agent pi`` file-copies each DeviaTDD command.

        Each command is written to ``<workdir>/.pi/prompts/<command-name>.md``
        — the flat-file convention Pi discovers natively per its
        documented slash-command convention.
        """
        from deviate.core.commands import discover_commands

        skills = discover_commands()
        assert skills, "No skills discovered — test invariant violated"

        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "pi"])
            assert result.exit_code == 0, result.output

            pi_skills_dir = tmp_path / ".pi" / "prompts"
            assert pi_skills_dir.is_dir(), (
                f"Pi skills directory not created: {pi_skills_dir}"
            )

            for skill_name in skills:
                skill_file = pi_skills_dir / f"{skill_name}.md"
                assert skill_file.is_file(), (
                    f"Skill file missing for '{skill_name}' at {skill_file}"
                )
                content = skill_file.read_text(encoding="utf-8")
                assert content.strip(), (
                    f"Skill file is empty for '{skill_name}' at {skill_file}"
                )
                # Each skill file should declare its name in YAML frontmatter.
                assert f"name: {skill_name}" in content, (
                    f"Skill file for '{skill_name}' does not declare its name"
                )

    def test_init_does_not_write_to_user_home_pi_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """DeviaTDD must NOT touch ``~/.pi/`` — operator's global Pi config.

        The user's ``~/.pi/agent/`` directory is operator-managed. DeviaTDD
        manages only project-local ``<workdir>/.pi/prompts/`` and must leave
        the user's home directory untouched.
        """
        from deviate.core.commands import discover_commands

        # Point the user's HOME at a separate directory so the test can
        # assert that the home ``.pi/`` stays empty while the project
        # workdir (also tmp_path) gets its ``.pi/prompts/`` written normally.
        fake_home = tmp_path / "fake-home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "pi"])
            assert result.exit_code == 0, result.output

            home_pi = fake_home / ".pi"
            assert not home_pi.exists(), (
                f"DeviaTDD wrote into the user's home directory at {home_pi} "
                f"— operator's global Pi config is out of scope"
            )

            home_pi_agent = fake_home / ".pi" / "agent"
            assert not home_pi_agent.exists(), (
                f"DeviaTDD wrote to the user's ~/.pi/agent/ at {home_pi_agent}"
            )

            # Project-local skill files were still written (sanity check).
            project_pi = tmp_path / ".pi" / "prompts"
            assert project_pi.is_dir(), (
                f"Project-local .pi/skills was not created: {project_pi}"
            )

            skills = discover_commands()
            assert skills, "No skills discovered — test invariant violated"

    def test_init_does_not_generate_settings_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """DeviaTDD must NOT generate a ``settings.json`` for Pi.

        Model/provider selection is the operator's responsibility and is
        configured via Pi's own configuration mechanism, not DeviaTDD.
        """
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "pi"])
            assert result.exit_code == 0, result.output

            project_settings = tmp_path / ".pi" / "settings.json"
            assert not project_settings.exists(), (
                f"DeviaTDD generated an unexpected settings.json at {project_settings}"
            )

            home_settings = tmp_path / ".pi" / "agent" / "settings.json"
            assert not home_settings.exists(), (
                f"DeviaTDD wrote a settings.json into the user's home at "
                f"{home_settings}"
            )

    def test_init_idempotent_pi_setup(self, tmp_path: Path):
        """Re-running setup does not duplicate skill files or corrupt state.

        The existing ``install_command`` contract compares file content before
        writing, so re-running setup with identical source skills is a no-op
        at the file level. The ``.pi/prompts/`` directory layout is preserved.
        """
        from deviate.core.commands import discover_commands

        skills = discover_commands()
        assert skills, "No skills discovered — test invariant violated"

        with chdir(tmp_path):
            r1 = runner.invoke(cli, ["setup", "--agent", "pi"])
            assert r1.exit_code == 0, r1.output

            pi_skills_dir = tmp_path / ".pi" / "prompts"
            first_run_skill_files = sorted(
                str(p.relative_to(pi_skills_dir)) for p in pi_skills_dir.glob("*.md")
            )
            assert len(first_run_skill_files) == len(skills), (
                f"Expected {len(skills)} skill files, found "
                f"{len(first_run_skill_files)}: {first_run_skill_files!r}"
            )

            r2 = runner.invoke(cli, ["setup", "--agent", "pi"])
            assert r2.exit_code == 0, r2.output

            second_run_skill_files = sorted(
                str(p.relative_to(pi_skills_dir)) for p in pi_skills_dir.glob("*.md")
            )
            assert second_run_skill_files == first_run_skill_files, (
                f"Idempotent re-run changed skill file layout: "
                f"{first_run_skill_files!r} -> {second_run_skill_files!r}"
            )

            for skill_name in skills:
                skill_file = pi_skills_dir / f"{skill_name}.md"
                assert skill_file.is_file(), (
                    f"Skill file removed on re-run: {skill_file}"
                )
                # Files are real, not symlinks (project-local file copy).
                assert not skill_file.is_symlink(), (
                    f"Skill file unexpectedly a symlink: {skill_file}"
                )


def test_version():
    """`deviate --version` prints the installed distribution version.

    Asserts the CLI output matches `importlib.metadata.version("deviatdd")`
    directly — re-deriving the expected string via the same broken lookup
    would let a regression slip through.
    """
    from importlib.metadata import version

    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == f"deviate {version('deviatdd')}"
