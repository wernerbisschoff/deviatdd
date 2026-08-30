import subprocess
import tomllib
from contextlib import chdir
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deviate.cli import (
    _optional_pack_prompt_choices,
    _packs_from_selector_picks,
    _prompt_agent_selection,
    _prompt_pack_selection,
    _resolve_install_agents,
    cli,
)
from deviate.core.commands import OPTIONAL_PACK_NAMES, commands_for_packs

from tests.conftest import _git_env

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

    def test_setup_droid_is_backend_alias_without_install_dir(
        self, tmp_path: Path
    ) -> None:
        """``--agent droid`` persists the backend and writes no install dir.

        ``droid`` is a backend-only alias: it is not an installable agent
        platform, so setup creates no ``.droid/`` or ``.factory/`` tree.
        """
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "droid"])
            assert result.exit_code == 0, result.output
        assert not (tmp_path / ".droid").exists()
        assert not (tmp_path / ".factory").exists()
        _assert_only_agent_trees(tmp_path)


class TestSetupCodex:
    """ChatGPT Codex is a first-class backend that installs skills only."""

    def test_setup_codex_writes_skills_and_backend(self, tmp_path: Path) -> None:
        commands = commands_for_packs()
        assert commands, "No default-pack commands — test invariant violated"

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
        assert not (
            tmp_path / ".agents" / "skills" / "deviate-pr" / "SKILL.md"
        ).exists()

        _assert_only_agent_trees(tmp_path, ".agents")
        assert not (tmp_path / ".codex").exists()
        assert not (tmp_path / ".agents" / "prompts").exists()
        assert not (tmp_path / ".agents" / "commands").exists()

        parsed = tomllib.loads(
            (tmp_path / ".deviate" / "config.toml").read_text(encoding="utf-8")
        )
        assert parsed["agent"]["backend"] == "codex"
        assert parsed["models"]["default"] == "gpt-5.6-luna"
        assert parsed["agent"]["reasoning_effort"] == "high"
        assert 'backend = "codex"' in (tmp_path / ".deviate" / "config.toml").read_text(
            encoding="utf-8"
        )

    def test_setup_codex_existing_upserts_luna_and_high_reasoning(
        self, tmp_path: Path
    ) -> None:
        """Existing config gets Luna + high thinking without rewriting other keys."""
        dot = tmp_path / ".deviate"
        dot.mkdir()
        config_path = dot / "config.toml"
        config_path.write_text(
            'timeout_seconds = 999\n\n[agent]\nbackend = "pi"\ntimeout = 1800\n',
            encoding="utf-8",
        )

        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "codex"])
            assert result.exit_code == 0, result.output

        parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert parsed["agent"]["backend"] == "codex"
        assert parsed["agent"]["reasoning_effort"] == "high"
        assert parsed["agent"]["timeout"] == 1800
        assert parsed["models"]["default"] == "gpt-5.6-luna"
        assert parsed["timeout_seconds"] == 999
        assert config_path.read_text(encoding="utf-8").count("[agent]") == 1

        with chdir(tmp_path):
            again = runner.invoke(cli, ["setup", "--agent", "codex"])
            assert again.exit_code == 0, again.output
        rerun = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert rerun["agent"]["backend"] == "codex"
        assert rerun["agent"]["reasoning_effort"] == "high"
        assert rerun["models"]["default"] == "gpt-5.6-luna"
        assert config_path.read_text(encoding="utf-8").count("[agent]") == 1

    def test_setup_codex_does_not_clobber_custom_models_default(
        self, tmp_path: Path
    ) -> None:
        """A user-set ``[models].default`` survives Codex setup."""
        dot = tmp_path / ".deviate"
        dot.mkdir()
        config_path = dot / "config.toml"
        config_path.write_text(
            "[models]\n"
            'default = "gpt-5.4-custom"\n'
            'judge = "gpt-5.4"\n\n'
            "[agent]\n"
            'backend = "codex"\n',
            encoding="utf-8",
        )

        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "codex"])
            assert result.exit_code == 0, result.output

        parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert parsed["models"]["default"] == "gpt-5.4-custom"
        assert parsed["models"]["judge"] == "gpt-5.4"
        assert parsed["agent"]["backend"] == "codex"
        assert parsed["agent"]["reasoning_effort"] == "high"

    def test_setup_codex_does_not_clobber_custom_reasoning_effort(
        self, tmp_path: Path
    ) -> None:
        """A user-set ``[agent].reasoning_effort`` survives Codex setup."""
        dot = tmp_path / ".deviate"
        dot.mkdir()
        config_path = dot / "config.toml"
        config_path.write_text(
            '[agent]\nbackend = "codex"\nreasoning_effort = "low"\n',
            encoding="utf-8",
        )

        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "codex"])
            assert result.exit_code == 0, result.output

        parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert parsed["agent"]["reasoning_effort"] == "low"
        assert parsed["models"]["default"] == "gpt-5.6-luna"

    def test_setup_pi_does_not_write_luna_or_reasoning(self, tmp_path: Path) -> None:
        """Non-Codex setup must not seed Luna or a reasoning key."""
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "pi"])
            assert result.exit_code == 0, result.output

        parsed = tomllib.loads(
            (tmp_path / ".deviate" / "config.toml").read_text(encoding="utf-8")
        )
        assert parsed["agent"]["backend"] == "pi"
        assert "reasoning_effort" not in parsed.get("agent", {})
        models = parsed.get("models") or {}
        assert models.get("default") != "gpt-5.6-luna"


class TestSetupPacks:
    def test_default_setup_installs_layer_packs_only(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
        commands = tmp_path / ".opencode" / "commands"
        assert (commands / "deviate-red.md").is_file()
        assert (commands / "deviate-explore.md").is_file()
        assert (commands / "deviate-plan.md").is_file()
        assert (commands / "deviate-flows.md").is_file()
        assert (tmp_path / ".opencode" / "skills" / "deviatdd" / "SKILL.md").is_file()
        for optional in (
            "deviate-pr",
            "deviate-merge",
            "deviate-review",
            "deviate-walkthrough",
            "deviate-html",
            "deviate-hotfix",
            "deviate-triage",
            "deviate-prune",
            "deviate-e2e",
        ):
            assert not (commands / f"{optional}.md").exists(), optional

    def test_packs_pr_review_adds_only_those(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(
                cli, ["setup", "--agent", "opencode", "--packs", "pr,review"]
            )
            assert result.exit_code == 0, result.output
        commands = tmp_path / ".opencode" / "commands"
        assert (commands / "deviate-pr.md").is_file()
        assert (commands / "deviate-review.md").is_file()
        assert not (commands / "deviate-merge.md").exists()

    def test_unknown_pack_fails_closed(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(
                cli, ["setup", "--agent", "opencode", "--packs", "graphite"]
            )
        assert result.exit_code != 0
        assert not (tmp_path / ".opencode" / "commands" / "deviate-red.md").exists()

    def test_packs_none_installs_layer_packs_only(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(
                cli, ["setup", "--agent", "opencode", "--packs", "none"]
            )
            assert result.exit_code == 0, result.output
        commands = tmp_path / ".opencode" / "commands"
        assert (commands / "deviate-red.md").is_file()
        assert not (commands / "deviate-merge.md").exists()
        assert not (commands / "deviate-prune.md").exists()

    def test_pack_prompt_choices_list_every_optional_pack(self) -> None:
        choices = _optional_pack_prompt_choices()
        assert choices[0] == "none"
        assert "all-optional" in choices
        for name in (
            "merge",
            "pr",
            "review",
            "walkthrough",
            "html",
            "hotfix",
            "triage",
            "prune",
            "e2e",
        ):
            assert name in choices
        assert tuple(name for name in choices if name in OPTIONAL_PACK_NAMES) == (
            OPTIONAL_PACK_NAMES
        )

    def test_prompt_pack_selection_default_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        def fake_ask(message: str, **kwargs: object) -> object:
            captured.update(kwargs)
            return kwargs.get("default")

        monkeypatch.setattr("deviate.cli.is_interactive", lambda: True)
        monkeypatch.setattr("deviate.cli.Prompt.ask", fake_ask)
        assert _prompt_pack_selection() == ()
        assert captured.get("default") == "none"
        choices = captured.get("choices")
        assert isinstance(choices, list)
        assert "merge" in choices
        assert "prune" in choices
        assert "all-optional" in choices

    def test_packs_from_selector_picks_none_and_all(self) -> None:
        assert _packs_from_selector_picks(["none"]) == ()
        assert _packs_from_selector_picks(["all-optional"]) == OPTIONAL_PACK_NAMES
        assert _packs_from_selector_picks(["merge", "prune"]) == ("merge", "prune")


class TestSetupConfigAllowlist:
    def test_fresh_claude_config_is_tidy(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "claude"])
            assert result.exit_code == 0, result.output
        text = (tmp_path / ".deviate" / "config.toml").read_text(encoding="utf-8")
        parsed = tomllib.loads(text)
        assert parsed["profile"] == "full"
        assert parsed["base_branch"] == "main"
        assert parsed["claim_remote"] is False
        assert "use_libref" not in parsed
        assert "libref" not in text.lower()
        agent = parsed["agent"]
        assert agent["backend"] == "claude"
        assert "timeout" in agent
        assert "pi_rpc" not in agent
        assert "transport" not in agent

    def test_pi_writes_transport_not_pi_rpc(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "pi"])
            assert result.exit_code == 0, result.output
        parsed = tomllib.loads(
            (tmp_path / ".deviate" / "config.toml").read_text(encoding="utf-8")
        )
        assert parsed["agent"]["backend"] == "pi"
        assert parsed["agent"].get("transport") == "rpc"
        assert "pi_rpc" not in parsed["agent"]

    def test_switch_pi_to_codex_strips_dead_keys(self, tmp_path: Path) -> None:
        dot = tmp_path / ".deviate"
        dot.mkdir()
        config_path = dot / "config.toml"
        config_path.write_text(
            "[agent]\n"
            'backend = "pi"\n'
            "timeout = 1800\n"
            "pi_rpc = false\n"
            'transport = "rpc"\n',
            encoding="utf-8",
        )
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "codex"])
            assert result.exit_code == 0, result.output
        parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert parsed["agent"]["backend"] == "codex"
        assert parsed["agent"]["timeout"] == 1800
        assert "pi_rpc" not in parsed["agent"]
        assert "transport" not in parsed["agent"]
        assert parsed["agent"]["reasoning_effort"] == "high"
        assert parsed["models"]["default"] == "gpt-5.6-luna"


class TestSetupLibrefOptIn:
    def test_no_libref_flag_omits_every_mention(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0, result.output
        config = (tmp_path / ".deviate" / "config.toml").read_text(encoding="utf-8")
        assert "libref" not in config.lower()
        for path in (
            tmp_path / "CLAUDE.md",
            tmp_path / "AGENTS.md",
            tmp_path / ".opencode" / "commands" / "deviate-red.md",
            tmp_path / ".opencode" / "skills" / "deviatdd" / "SKILL.md",
        ):
            text = path.read_text(encoding="utf-8")
            assert "libref" not in text.lower(), path

    def test_libref_flag_writes_key_and_seed(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "opencode", "--libref"])
            assert result.exit_code == 0, result.output
        parsed = tomllib.loads(
            (tmp_path / ".deviate" / "config.toml").read_text(encoding="utf-8")
        )
        assert parsed["use_libref"] is True
        assert "libref" in (tmp_path / "CLAUDE.md").read_text(encoding="utf-8").lower()


class TestSetupNextStepHint:
    """Successful setup must tell a new user to run ``/deviate-init`` next."""

    def test_successful_setup_prints_deviate_init_hint(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
        assert result.exit_code == 0, result.output
        assert "/deviate-init" in result.output
        assert "no-op" in result.output
        assert "already scaffolded" in result.output

    def test_failed_setup_omits_init_hint(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup"])
        assert result.exit_code != 0
        assert "NO_AGENT_SELECTED" in result.output
        assert "/deviate-init" not in result.output


class TestReadmeNewUserPath:
    """README Quickstart must match the two-step setup → ``/deviate-init`` path."""

    def test_quickstart_names_setup_then_deviate_init(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        quickstart = readme.split("## Quickstart", 1)[1].split("\n## ", 1)[0]
        assert "deviate setup" in quickstart
        assert "/deviate-init" in quickstart
        assert "first prompt" in quickstart.lower()
        assert "deviate-init" in quickstart
        assert "one shot" not in quickstart.lower()
        assert "scaffolds .deviate/, specs/constitution.md" not in quickstart

    def test_readme_does_not_claim_setup_scaffolds_constitution(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        assert "scaffolds .deviate/, specs/constitution.md" not in readme
        bootstrap = next(
            line for line in readme.splitlines() if line.startswith("| **Bootstrap")
        )
        assert "specs/constitution.md" not in bootstrap
        assert "/deviate-init" in readme


runner = CliRunner()

ACTIVE_AGENTS = ("claude", "opencode", "factory", "pi", "omp")


def _mock_agent_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Route command and skill installs into the isolated temp tree."""
    monkeypatch.setattr(
        "deviate.cli._get_agent_command_dir",
        lambda agent, _workdir: tmp_path / f".{agent}" / "commands",
    )
    monkeypatch.setattr(
        "deviate.cli._get_agent_skill_dir",
        lambda _workdir, agent: tmp_path / f".{agent}" / "skills",
    )


def _installed_files(root: Path, subdir: str) -> list[Path]:
    """Return the command/skill files written under ``root/.<agent>/<subdir>``."""
    target = root / subdir
    if not target.exists():
        return []
    return [p for p in target.rglob("deviate-*.md")] + [
        p for p in target.rglob("SKILL.md")
    ]


class TestSetupPerAgentInstall:
    """``deviate setup`` installs exactly one selected agent."""

    def test_setup_single_agent_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """``setup --agent opencode`` writes only under the opencode agent dir."""
        _mock_agent_dirs(tmp_path, monkeypatch)
        (tmp_path / ".claude").mkdir(parents=True)
        (tmp_path / ".opencode").mkdir(parents=True)
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0
            assert "INSTALL" in result.output.upper()
            assert _installed_files(tmp_path, ".opencode/commands")
            assert _installed_files(tmp_path, ".opencode/skills")
            for agent in ACTIVE_AGENTS:
                if agent == "opencode":
                    continue
                assert not _installed_files(tmp_path, f".{agent}/commands")
                assert not _installed_files(tmp_path, f".{agent}/skills")

    def test_bare_setup_does_not_spray_leftover_agent_dirs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Non-TTY bare ``setup`` fail-closes; leftover dirs are not sprayed."""
        _mock_agent_dirs(tmp_path, monkeypatch)
        (tmp_path / ".claude").mkdir(parents=True)
        (tmp_path / ".opencode").mkdir(parents=True)
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup"])
        assert result.exit_code != 0
        assert "NO_AGENT_SELECTED" in result.output
        for agent in ACTIVE_AGENTS:
            assert not _installed_files(tmp_path, f".{agent}/commands")
            assert not _installed_files(tmp_path, f".{agent}/skills")

    def test_tty_setup_installs_one_agent_despite_leftover_dirs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """TTY-mocked bare setup installs the picked agent only."""
        (tmp_path / ".claude" / "commands").mkdir(parents=True)
        (tmp_path / ".opencode" / "commands").mkdir(parents=True)
        monkeypatch.setattr("deviate.cli._prompt_agent_selection", lambda *_: "pi")
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup"])
        assert result.exit_code == 0, result.output
        assert (tmp_path / ".pi" / "prompts" / "deviate-red.md").is_file()
        assert (tmp_path / ".pi" / "skills" / "deviatdd" / "SKILL.md").is_file()
        assert not (tmp_path / ".claude" / "commands" / "deviate-red.md").exists()
        assert not (tmp_path / ".opencode" / "commands" / "deviate-red.md").exists()
        assert not (tmp_path / ".claude" / "skills" / "deviatdd" / "SKILL.md").exists()
        assert not (
            tmp_path / ".opencode" / "skills" / "deviatdd" / "SKILL.md"
        ).exists()

    def test_tty_setup_existing_config_empty_dirs_prompts_and_installs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Config present + no agent dirs: TTY still picks one agent and installs it.

        Werner repro: delete ``.claude`` / ``.factory`` / ``.omp`` /
        ``.opencode`` / ``.pi``, keep ``.deviate/config.toml``, run bare
        ``deviate setup``. Empty ``detect_agents`` must not skip the
        picker or install zero command files.
        """
        from deviate.core.commands import detect_agents

        (tmp_path / ".deviate").mkdir()
        (tmp_path / ".deviate" / "config.toml").write_text(
            '[agent]\nbackend = "pi"\n', encoding="utf-8"
        )
        assert detect_agents(tmp_path) == []

        captured: dict[str, dict[str, object]] = {}

        def fake_ask(message: str, **kwargs: object) -> object:
            captured[str(message)] = kwargs
            return kwargs.get("default")

        monkeypatch.setattr("deviate.cli.is_interactive", lambda: True)
        monkeypatch.setattr("deviate.cli.Prompt.ask", fake_ask)

        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup"])
        assert result.exit_code == 0, result.output
        assert "Select agent platform" in captured
        agent_kwargs = captured["Select agent platform"]
        assert agent_kwargs.get("default") == "pi"
        assert "pi" in agent_kwargs.get("choices", [])
        pack_kwargs = captured["Optional command packs"]
        assert pack_kwargs.get("default") == "none"
        assert "merge" in pack_kwargs.get("choices", [])
        assert "prune" in pack_kwargs.get("choices", [])
        assert "all-optional" in pack_kwargs.get("choices", [])
        assert "INSTALL" in result.output.upper()
        assert (tmp_path / ".pi" / "prompts" / "deviate-red.md").is_file()
        assert (tmp_path / ".pi" / "skills" / "deviatdd" / "SKILL.md").is_file()
        for leftover in (".claude", ".factory", ".omp", ".opencode"):
            assert not (tmp_path / leftover / "commands" / "deviate-red.md").exists()
            assert not (tmp_path / leftover / "prompts" / "deviate-red.md").exists()

    def test_prompt_agent_selection_defaults_to_existing_backend(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = tmp_path / ".deviate" / "config.toml"
        config.parent.mkdir()
        config.write_text('[agent]\nbackend = "pi"\n', encoding="utf-8")
        captured: dict[str, object] = {}

        def fake_ask(message: str, **kwargs: object) -> object:
            captured.update(kwargs)
            return kwargs.get("default")

        monkeypatch.setattr("deviate.cli.is_interactive", lambda: True)
        monkeypatch.setattr("deviate.cli.Prompt.ask", fake_ask)
        assert _prompt_agent_selection(tmp_path, config) == "pi"
        assert captured.get("default") == "pi"
        assert "pi" in captured.get("choices", [])

    def test_agent_flag_pins_despite_leftover_dirs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """``--agent pi`` installs pi even when leftover agent dirs exist."""
        _mock_agent_dirs(tmp_path, monkeypatch)
        (tmp_path / ".claude").mkdir(parents=True)
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "pi"])
        assert result.exit_code == 0, result.output
        assert _installed_files(tmp_path, ".pi/commands")
        assert _installed_files(tmp_path, ".pi/skills")
        assert not _installed_files(tmp_path, ".claude/commands")
        assert not _installed_files(tmp_path, ".claude/skills")

    def test_resolve_install_agents_is_exactly_one(self) -> None:
        assert _resolve_install_agents("pi") == ["pi"]
        assert _resolve_install_agents("claude") == ["claude"]

    def test_setup_unknown_agent_fails_closed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """A name outside ``AGENT_CHOICES`` fails without partial install."""
        _mock_agent_dirs(tmp_path, monkeypatch)
        (tmp_path / ".claude").mkdir(parents=True)
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "not-an-agent"])
            assert result.exit_code != 0
            for agent in ACTIVE_AGENTS:
                assert not _installed_files(tmp_path, f".{agent}/commands")
                assert not _installed_files(tmp_path, f".{agent}/skills")


class TestSetupGitignoreDotdeviate:
    """AC-PLAN-001: ``deviate setup`` git-ignores ``.deviate/`` by default."""

    def test_setup_gitignores_dotdeviate(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """After setup, ``git check-ignore .deviate/`` resolves and the
        directory never appears as an untracked git status candidate."""
        _mock_agent_dirs(tmp_git_repo, monkeypatch)
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
            assert result.exit_code == 0
            assert "INSTALL" in result.output.upper()

        check = subprocess.run(
            ["git", "check-ignore", ".deviate/"],
            cwd=tmp_git_repo,
            env=_git_env(),
            capture_output=True,
            text=True,
        )
        assert check.returncode == 0, (
            "AC-PLAN-001: setup must provision an ignore rule resolving "
            f".deviate/; stderr={check.stderr.strip()!r}"
        )
        assert check.stdout.strip() == ".deviate/"

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=tmp_git_repo,
            env=_git_env(),
            capture_output=True,
            text=True,
        )
        assert "?? .deviate" not in status.stdout, status.stdout
