import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
import tomllib
import yaml
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.core.skills import _resolve_skills_root
from deviate.core.skills import discover_skills

runner = CliRunner()

_PRODUCT_LAYER_SKILLS = ("deviate-flows", "deviate-architecture", "deviate-release")


@contextmanager
def chdir(path: Path):
    cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(cwd)


def _assert_product_layer_skill_installed(
    installed: Path, source: Path, skill_name: str
) -> None:
    """Verify an installed Product-layer skill preserves its source content.

    The installation path (``compose_skill_body`` at ``src/deviate/core/skills.py:57``)
    prepends ``core.md`` invariants between the source frontmatter and the source
    body, so the installed file is NOT byte-equal to the source. The contract is:
        1. Source frontmatter is preserved verbatim (byte-equal).
        2. Source body text is preserved as a substring (compose only inserts
           content BETWEEN frontmatter and body — never mutates either).
        3. Frontmatter parses to a dict with the expected fields.
    """
    assert installed.exists(), f"Installed skill missing: {installed}"
    assert source.exists(), f"Source skill template missing: {source}"

    src_text = source.read_text(encoding="utf-8")
    dst_text = installed.read_text(encoding="utf-8")

    src_fm = src_text.split("---", 2)[1]
    dst_fm = dst_text.split("---", 2)[1]
    assert src_fm == dst_fm, (
        f"{skill_name}: source frontmatter not byte-equal in installed file. "
        f"Source fm: {src_fm!r}\nInstalled fm: {dst_fm!r}"
    )

    src_body = src_text.split("---", 2)[2]
    assert src_body.strip() in dst_text, (
        f"{skill_name}: source body content missing from installed file. "
        f"Source body[:120]: {src_body[:120]!r}"
    )

    fm = yaml.safe_load(src_fm)
    assert fm["name"] == skill_name, (
        f"{skill_name}: frontmatter name mismatch (got {fm.get('name')!r})"
    )
    assert fm["category"] == "deviatdd-product-layer", (
        f"{skill_name}: category must be 'deviatdd-product-layer' "
        f"(got {fm.get('category')!r})"
    )


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


class TestProductLayerSkillExportCycle:
    """TSK-010-06: full-cycle integration verification for Product-layer skills.

    Verifies that ``deviate setup --agent {claude,opencode}`` installs the three
    new Product-layer skills (``deviate-flows``, ``deviate-architecture``,
    ``deviate-release``) into the agent-specific skills directory with source
    frontmatter and body content preserved (per ``specs/_product/release-next.md:26``
    acceptance criterion).
    """

    def test_init_export_cycle_installs_product_layer_skills_claude(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-ADHOC-010-03: ``deviate setup --agent claude`` installs the three
        Product-layer skills into ``.claude/skills/`` with source content preserved.
        """
        monkeypatch.setattr(
            "deviate.cli._get_agent_skill_dir",
            lambda agent, _workdir: tmp_path / f".{agent}" / "skills",
        )
        (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)

        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["setup", "--agent", "claude"])
            assert result.exit_code == 0, result.output

            skills_root = _resolve_skills_root()
            for skill_name in _PRODUCT_LAYER_SKILLS:
                installed = workdir / ".claude" / "skills" / skill_name / "SKILL.md"
                source = skills_root / skill_name / "SKILL.md"
                _assert_product_layer_skill_installed(installed, source, skill_name)

    def test_init_export_cycle_installs_product_layer_skills_opencode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-ADHOC-010-05: ``deviate setup --agent opencode`` installs the three
        Product-layer skills into ``.opencode/skills/`` with source content preserved.
        """
        monkeypatch.setattr(
            "deviate.cli._get_agent_skill_dir",
            lambda agent, _workdir: tmp_path / f".{agent}" / "skills",
        )
        (tmp_path / ".opencode").mkdir(parents=True, exist_ok=True)

        with chdir(tmp_path):
            workdir = tmp_path
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output

            skills_root = _resolve_skills_root()
            for skill_name in _PRODUCT_LAYER_SKILLS:
                installed = workdir / ".opencode" / "skills" / skill_name / "SKILL.md"
                source = skills_root / skill_name / "SKILL.md"
                _assert_product_layer_skill_installed(installed, source, skill_name)

    def test_init_export_cycle_product_layer_skills_idempotent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-ADHOC-010-04: re-running ``deviate setup --agent claude`` against a
        workdir where the three Product-layer skill files are already installed
        emits a ``[yellow]SKIP[/]`` log line for each present skill and produces
        no errors (per existing ``_install_skills_to_agents`` skip logic at
        ``src/deviate/cli/__init__.py:518-531``).
        """
        monkeypatch.setattr(
            "deviate.cli._get_agent_skill_dir",
            lambda agent, _workdir: tmp_path / f".{agent}" / "skills",
        )
        (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)

        with chdir(tmp_path):
            first = runner.invoke(cli, ["setup", "--agent", "claude"])
            assert first.exit_code == 0, first.output

            for skill_name in _PRODUCT_LAYER_SKILLS:
                installed = tmp_path / ".claude" / "skills" / skill_name / "SKILL.md"
                assert installed.exists(), (
                    f"first setup did not install {skill_name}: {installed}"
                )

            second = runner.invoke(cli, ["setup", "--agent", "claude"])
            assert second.exit_code == 0, second.output

            for skill_name in _PRODUCT_LAYER_SKILLS:
                assert f"SKIP {skill_name}" in second.output, (
                    f"second setup did not emit SKIP log for {skill_name}; "
                    f"got: {second.output!r}"
                )


class TestFullInitCyclePiBackend:
    """TSK-009-06: E2E integration test for Pi setup + export cycle.

    Exercises the full ``deviate setup --agent pi`` flow end-to-end and
    verifies the artifacts the Pi backend needs at runtime — config.toml
    and the project-local ``<workdir>/.pi/skills/<name>/SKILL.md`` files.
    No writes to ``~/.pi/agent/`` and no ``settings.json`` generation.
    ``Path.home()`` is monkeypatched to the per-test ``tmp_path`` so the
    test can assert that DeviaTDD did not write to the user's home
    directory.
    """

    def test_init_export_pi_backend_full_cycle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """AC-ADHOC-009-02 + AC-ADHOC-009-04: Full Pi setup cycle creates
        config.toml and project-local skill files; no global writes.
        """
        fake_home = tmp_path / "fake-home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        skills = discover_skills()
        assert skills, "Test invariant violated: no skills discovered"

        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "pi"])
            assert result.exit_code == 0, result.output

            config_path = tmp_path / ".deviate" / "config.toml"
            assert config_path.exists(), ".deviate/config.toml not created"
            parsed = tomllib.loads(config_path.read_text())
            assert parsed["agent"]["backend"] == "pi", (
                f"Expected backend='pi', got: {parsed.get('agent')}"
            )

            pi_skills_dir = tmp_path / ".pi" / "skills"
            assert pi_skills_dir.is_dir(), (
                f"Project-local Pi skills dir not created at {pi_skills_dir}"
            )

            for skill_name in skills:
                skill_file = pi_skills_dir / skill_name / "SKILL.md"
                assert skill_file.is_file(), (
                    f"Skill file missing for '{skill_name}' at {skill_file}"
                )
                assert not skill_file.is_symlink(), (
                    f"Skill file unexpectedly a symlink: {skill_file}"
                )

            # No writes to operator's global Pi config.
            home_pi = fake_home / ".pi"
            assert not home_pi.exists(), (
                f"DeviaTDD wrote to the user's home dir at {home_pi}"
            )

            # No settings.json anywhere.
            assert not (tmp_path / ".pi" / "settings.json").exists()
            assert not (fake_home / ".pi" / "agent" / "settings.json").exists()

    def test_init_export_pi_backend_performance_under_500ms(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Performance constraint: L_max ≤ 500ms for full Pi setup cycle.

        Covers skill file copy (≤ 200ms for 20 skills) + config.toml write
        + governance file writes — all must complete within the 500ms L_max.
        """
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with chdir(tmp_path):
            start = time.perf_counter()
            result = runner.invoke(cli, ["setup", "--agent", "pi"])
            elapsed = time.perf_counter() - start

            assert result.exit_code == 0, result.output
            assert elapsed < 0.5, (
                f"Pi setup took {elapsed:.3f}s, expected < 0.5s (L_max constraint)"
            )

    def test_init_export_pi_backend_idempotent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Re-running setup does not duplicate skill files; second run
        also stays within 500ms.
        """
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        skills = discover_skills()

        with chdir(tmp_path):
            r1 = runner.invoke(cli, ["setup", "--agent", "pi"])
            assert r1.exit_code == 0, r1.output

            pi_skills_dir = tmp_path / ".pi" / "skills"
            first_files = sorted(
                str(p.relative_to(pi_skills_dir))
                for p in pi_skills_dir.rglob("SKILL.md")
            )
            assert len(first_files) == len(skills)

            start = time.perf_counter()
            r2 = runner.invoke(cli, ["setup", "--agent", "pi"])
            elapsed = time.perf_counter() - start

            assert r2.exit_code == 0, r2.output
            assert elapsed < 0.5, (
                f"Second Pi setup took {elapsed:.3f}s, expected < 0.5s"
            )

            second_files = sorted(
                str(p.relative_to(pi_skills_dir))
                for p in pi_skills_dir.rglob("SKILL.md")
            )
            assert second_files == first_files, (
                f"Idempotent re-run changed skill file layout: "
                f"{first_files!r} -> {second_files!r}"
            )

            for skill_name in skills:
                skill_file = pi_skills_dir / skill_name / "SKILL.md"
                assert skill_file.is_file(), (
                    f"Skill file removed on re-run: {skill_file}"
                )
                assert not skill_file.is_symlink(), (
                    f"Skill file unexpectedly a symlink: {skill_file}"
                )

    def test_init_export_pi_backend_skill_files_contain_frontmatter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Each ``<workdir>/.pi/skills/<name>/SKILL.md`` carries the
        ``name:`` YAML frontmatter field — so Pi's native skill discovery
        actually registers each skill.
        """
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        skills = discover_skills()

        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "pi"])
            assert result.exit_code == 0, result.output

            pi_skills_dir = tmp_path / ".pi" / "skills"
            for skill_name in skills:
                skill_file = pi_skills_dir / skill_name / "SKILL.md"
                content = skill_file.read_text(encoding="utf-8")
                assert f"name: {skill_name}" in content, (
                    f"Skill file for '{skill_name}' does not declare its name"
                )

    def test_init_export_pi_backend_does_not_create_global_settings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """DeviaTDD does NOT generate a ``settings.json`` for Pi.

        Model/provider selection is the operator's responsibility via Pi's
        own configuration mechanism. Verify no ``settings.json`` exists at
        any path DeviaTDD might be tempted to write to.
        """
        fake_home = tmp_path / "fake-home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        with chdir(tmp_path):
            dot_dir = tmp_path / ".deviate"
            dot_dir.mkdir(parents=True)
            config_path = dot_dir / "config.toml"
            config_path.write_text(
                'profile = "default"\n'
                "\n[models]\n"
                'default = "anthropic/claude-sonnet-4-5"\n'
                'judge = "openai/gpt-5-pro"\n',
                encoding="utf-8",
            )

            result = runner.invoke(cli, ["setup", "--agent", "pi"])
            assert result.exit_code == 0, result.output

            # No project-local settings.json.
            assert not (tmp_path / ".pi" / "settings.json").exists()
            # No global settings.json under operator's mocked home.
            assert not (fake_home / ".pi" / "agent" / "settings.json").exists()
            # No spurious .pi under operator's home.
            assert not (fake_home / ".pi").exists()

    def test_init_export_pi_backend_preserves_existing_user_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """If the operator already has a ``~/.pi/agent/`` directory with
        content, DeviaTDD must NOT touch it.
        """
        fake_home = tmp_path / "fake-home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        pi_agent_dir = fake_home / ".pi" / "agent"
        pi_agent_dir.mkdir(parents=True)
        user_settings = pi_agent_dir / "settings.json"
        user_settings.write_text('{"operatorManaged": true}', encoding="utf-8")

        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "pi"])
            assert result.exit_code == 0, result.output

            # Operator's settings.json is untouched.
            assert user_settings.exists(), (
                f"Operator's settings.json was removed: {user_settings}"
            )
            assert user_settings.read_text() == '{"operatorManaged": true}', (
                f"Operator's settings.json was modified: {user_settings}"
            )

    def test_init_export_pi_backend_config_toml_round_trip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Config round-trips through TOML parse after setup preserves
        the ``[agent].backend = 'pi'`` setting without data loss.
        """
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "pi"])
            assert result.exit_code == 0, result.output

            config_path = tmp_path / ".deviate" / "config.toml"
            raw = config_path.read_text()
            assert 'backend = "pi"' in raw, (
                f'backend = "pi" not found in config.toml:\n{raw}'
            )

            parsed = tomllib.loads(raw)
            assert parsed["agent"]["backend"] == "pi"

            session_path = tmp_path / ".deviate" / "session.json"
            assert session_path.exists()
            session_data = json.loads(session_path.read_text())
            assert session_data["current_phase"] == "IDLE"
