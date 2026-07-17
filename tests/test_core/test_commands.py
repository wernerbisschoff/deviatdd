from __future__ import annotations

from pathlib import Path

from deviate.core.commands import (
    discover_commands,
    install_command,
    resolve_command,
)

_SOURCE_COMMANDS_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "deviate" / "prompts" / "commands"
)


class TestDiscoverCommands:
    def test_discover_commands_lists_flat_files(self, tmp_path: Path):
        commands_root = tmp_path / "commands"
        commands_root.mkdir(parents=True)
        (commands_root / "deviate-red.md").write_text("# red", encoding="utf-8")
        (commands_root / "deviate-green.md").write_text("# green", encoding="utf-8")
        result = discover_commands(commands_root=commands_root)
        assert "deviate-red" in result
        assert "deviate-green" in result

    def test_discover_commands_skips_non_md_files(self, tmp_path: Path):
        commands_root = tmp_path / "commands"
        commands_root.mkdir(parents=True)
        (commands_root / "with-cmd.md").write_text("# ok", encoding="utf-8")
        (commands_root / "no-extension").write_text("# ignored", encoding="utf-8")
        (commands_root / "wrong-extension.txt").write_text(
            "# ignored", encoding="utf-8"
        )
        result = discover_commands(commands_root=commands_root)
        assert "with-cmd" in result
        assert "no-extension" not in result
        assert "wrong-extension" not in result

    def test_discover_commands_empty_dir_returns_empty_list(self, tmp_path: Path):
        commands_root = tmp_path / "commands"
        commands_root.mkdir(parents=True)
        result = discover_commands(commands_root=commands_root)
        assert result == []


class TestInstallCommandGraphiteRouting:
    """Conditional `## Graphite Routing` section in deviate-pr based on config."""

    @staticmethod
    def _seed_graphite_config(workdir: Path, value: bool | None) -> None:
        dot_dir = workdir / ".deviate"
        dot_dir.mkdir(parents=True, exist_ok=True)
        config_path = dot_dir / "config.toml"
        if value is None:
            config_path.write_text('profile = "default"\n', encoding="utf-8")
        else:
            config_path.write_text(
                f'profile = "default"\ngraphite = {"true" if value else "false"}\n',
                encoding="utf-8",
            )

    def test_install_deviate_pr_appends_graphite_when_configured(self, tmp_path: Path):
        """graphite = true in config → installed command contains routing section."""
        workdir = tmp_path / "repo"
        workdir.mkdir()
        self._seed_graphite_config(workdir, True)
        target = tmp_path / "agent" / "commands"

        assert install_command("deviate-pr", target, workdir=workdir) is True
        installed = target / "deviate-pr.md"
        assert installed.exists()
        content = installed.read_text(encoding="utf-8")
        assert "<graphite_routing>" in content
        assert "gt submit --stack" in content

    def test_install_deviate_pr_omits_graphite_when_unset(self, tmp_path: Path):
        """graphite key absent from config → no routing section emitted."""
        workdir = tmp_path / "repo"
        workdir.mkdir()
        self._seed_graphite_config(workdir, None)
        target = tmp_path / "agent" / "commands"

        install_command("deviate-pr", target, workdir=workdir)
        installed = target / "deviate-pr.md"
        assert installed.exists()
        content = installed.read_text(encoding="utf-8")
        assert "<graphite_routing>" not in content

    def test_install_deviate_pr_omits_graphite_when_false(self, tmp_path: Path):
        """graphite = false in config → no routing section emitted."""
        workdir = tmp_path / "repo"
        workdir.mkdir()
        self._seed_graphite_config(workdir, False)
        target = tmp_path / "agent" / "commands"

        install_command("deviate-pr", target, workdir=workdir)
        content = (target / "deviate-pr.md").read_text(encoding="utf-8")
        assert "<graphite_routing>" not in content

    def test_install_deviate_pr_graphite_idempotent_on_repeat(self, tmp_path: Path):
        """Second install with same config → no duplicate section, file unchanged."""
        workdir = tmp_path / "repo"
        workdir.mkdir()
        self._seed_graphite_config(workdir, True)
        target = tmp_path / "agent" / "commands"

        install_command("deviate-pr", target, workdir=workdir)
        first = (target / "deviate-pr.md").read_text(encoding="utf-8")

        assert install_command("deviate-pr", target, workdir=workdir) is False
        second = (target / "deviate-pr.md").read_text(encoding="utf-8")
        assert first == second
        assert second.count("<graphite_routing>") == 1

    def test_install_deviate_pr_removes_graphite_when_disabled_after_enable(
        self, tmp_path: Path
    ):
        """Toggle graphite false → re-install removes the routing section."""
        workdir = tmp_path / "repo"
        workdir.mkdir()
        self._seed_graphite_config(workdir, True)
        target = tmp_path / "agent" / "commands"

        install_command("deviate-pr", target, workdir=workdir)
        assert "<graphite_routing>" in (target / "deviate-pr.md").read_text(
            encoding="utf-8"
        )

        self._seed_graphite_config(workdir, False)
        assert install_command("deviate-pr", target, workdir=workdir) is True
        content = (target / "deviate-pr.md").read_text(encoding="utf-8")
        assert "<graphite_routing>" not in content

    def test_install_deviate_pr_without_workdir_skips_graphite_check(
        self, tmp_path: Path
    ):
        """No workdir passed → no graphite injection (callers must opt in)."""
        target = tmp_path / "agent" / "commands"
        install_command("deviate-pr", target)
        content = (target / "deviate-pr.md").read_text(encoding="utf-8")
        assert "<graphite_routing>" not in content

    def test_install_other_commands_unaffected_by_graphite(self, tmp_path: Path):
        """graphite = true must not inject the section into non-deviate-pr commands."""
        workdir = tmp_path / "repo"
        workdir.mkdir()
        self._seed_graphite_config(workdir, True)
        target = tmp_path / "agent" / "commands"

        install_command("deviate-red", target, workdir=workdir)
        content = (target / "deviate-red.md").read_text(encoding="utf-8")
        assert "<graphite_routing>" not in content


class TestShardCommandIssueIdFormat:
    """deviate-shard command must use the flat ``ISS-<NNN>`` format.

    The ``next_issue_id`` returned by ``deviate shard pre`` is the flat global
    counter (``ISS-001``, ``ISS-002``, ...). The command must instruct the LLM
    to consume ``next_issue_id`` directly and increment per shard — it must
    NEVER concatenate the epic identifier, which would produce duplicate
    ``ISS-<epic>-<NNN>`` IDs across epics.
    """

    @staticmethod
    def _command_text() -> str:
        return resolve_command("deviate-shard").read_text(encoding="utf-8")

    def test_instruction_uses_flat_format_not_epic_prefixed(self):
        """Issue ID assignment rule must show flat ``ISS-<NNN>`` examples."""
        text = self._command_text()
        assert "ISS-001-004" not in text
        assert "ISS-001-005" not in text

    def test_blocked_by_and_coordinates_with_examples_use_flat_format(self):
        """blocked_by / coordinates_with examples must reference flat IDs."""
        text = self._command_text()
        assert 'blocked_by: ["ISS-001-004"]' not in text

    def test_manifest_schema_uses_flat_format(self):
        """Manifest schema must declare ``ISS-<NNN>``, not ``ISS-<epic>-<NNN>``."""
        text = self._command_text()
        assert "ISS-<epic>-<NNN>" not in text

    def test_manifest_example_uses_flat_format(self):
        """Manifest example must show flat IDs (e.g. ``ISS-003``, not ``ISS-003-001``)."""
        text = self._command_text()
        assert "ISS-003-001" not in text
        assert "ISS-003-002" not in text

    def test_instruction_references_flat_counter_format(self):
        """The rule must explicitly show the flat counter pattern."""
        text = self._command_text()
        assert "ISS-003" in text or "ISS-004" in text


class TestDeviateFlowsCommitAtSignOff:
    """``/deviate-flows`` v1.4.0 contract: draft-on-disk, commit-only-on-sign-off,
    one ``stage_and_commit`` call with the explicit flow/index file list.

    Regression contract for the v1.3.0 → v1.4.0 protocol change. These four
    guards describe user-visible behavior; they intentionally avoid parsing
    python code blocks or asserting prose phrasing beyond the contract.
    """

    @staticmethod
    def _command_text() -> str:
        return resolve_command(
            "deviate-flows", commands_root=_SOURCE_COMMANDS_ROOT
        ).read_text(encoding="utf-8")

    def test_drafts_remain_uncommitted_during_conversation(self):
        """Phase A writes flow files + index rows to disk but does NOT
        commit them mid-conversation. The skill must defer all commits
        until explicit sign-off.
        """
        text = self._command_text()
        # The invariant must describe a Phase A draft step and forbid
        # any commit during it.
        assert "Phase A" in text and "Draft" in text
        assert "No commit fires during Phase A" in text or (
            "no commit fires during phase a" in text.lower()
        )

    def test_explicit_user_sign_off_required(self):
        """Committing requires explicit user approval. Recognized signals
        are listed in the prompt; silence is not sign-off.
        """
        text = self._command_text()
        for signal in ("commit", "looks good", "done", "ship it", "approve", "lgtm"):
            assert signal in text, f"Sign-off signal {signal!r} missing from prompt"
        # Negative guard: silence / topic change must not count.
        assert (
            "Silence is not sign-off" in text
            or "silence is not sign-off" in text.lower()
        )

    def test_one_stage_and_commit_with_explicit_flow_index_list(self):
        """The single end-of-session commit MUST be invoked via
        ``stage_and_commit`` exactly once, with ``files=`` covering every
        session-authored flow file plus ``index.md``. Calling the older
        ``commit_artifact(path, msg)`` helper (one commit per path) or
        ``git add -A`` (sweeps unrelated work) is forbidden.
        """
        text = self._command_text()
        assert "stage_and_commit" in text
        assert "EXACTLY ONCE" in text or "exactly once" in text.lower()
        assert "files=" in text
        assert "flows-<domain>.md" in text
        assert "index.md" in text
        assert "git add -A" in text  # must mention to forbid it
        # commit_artifact is mentioned only as a "do NOT" warning.
        assert "commit_artifact" in text

    def test_old_two_commits_wording_is_gone(self):
        """Guard against the v1.3.0 ambiguity regressing. The old prompt
        said ``create a single git commit (or two commits, one per file)``
        — that wording must never return.
        """
        text = self._command_text()
        assert "or two commits, one per file" not in text
        assert "create a single git commit (or two commits" not in text


class TestDeviateArchitectureCommitAtSignOff:
    """``/deviate-architecture`` v1.3.0 contract: draft-on-disk, commit-only-on-sign-off,
    one ``stage_and_commit`` call with the explicit architecture/domain-model file list.

    Regression contract for the v1.2.0 → v1.3.0 protocol change. The v1.2.0
    prompt auto-committed each file via ``commit_artifact(path, msg)`` after
    every write, producing one-commit-per-edit chains across what should be
    a single architectural change. These guards describe user-visible behavior;
    they intentionally avoid parsing python code blocks or asserting prose
    phrasing beyond the contract.
    """

    @staticmethod
    def _command_text() -> str:
        return resolve_command(
            "deviate-architecture", commands_root=_SOURCE_COMMANDS_ROOT
        ).read_text(encoding="utf-8")

    def test_drafts_remain_uncommitted_during_conversation(self):
        """Phase A writes architecture and domain-model files to disk but does
        NOT commit them mid-conversation. The skill must defer all commits
        until explicit sign-off.
        """
        text = self._command_text()
        # The invariant must describe a Phase A draft step and forbid any
        # commit during it.
        assert "Phase A" in text and "Draft" in text
        assert "No commit fires" in text or "do NOT fire any commit" in text

    def test_explicit_user_sign_off_required(self):
        """Committing requires explicit user approval. Recognized signals are
        listed in the prompt; silence is not sign-off.
        """
        text = self._command_text()
        for signal in ("commit", "looks good", "done", "ship it", "approve", "lgtm"):
            assert signal in text, f"Sign-off signal {signal!r} missing from prompt"
        # Negative guard: silence / topic change must not count.
        assert (
            "Silence is NOT sign-off" in text
            or "silence is not sign-off" in text.lower()
        )

    def test_one_stage_and_commit_with_explicit_file_list(self):
        """The single end-of-session commit MUST be invoked via
        ``stage_and_commit`` exactly once, with ``files=`` covering every
        session-authored architecture and domain-model file. Calling the
        older ``commit_artifact(path, msg)`` helper (one commit per path)
        or ``git add -A`` (sweeps unrelated work) is forbidden.
        """
        text = self._command_text()
        assert "stage_and_commit" in text
        assert "EXACTLY ONCE" in text or "exactly once" in text.lower()
        assert "files=" in text
        assert "architecture.md" in text
        assert "domain-model.md" in text
        assert "git add -A" in text  # must mention to forbid it
        # commit_artifact is mentioned only as a "do NOT" warning.
        assert "commit_artifact" in text

    def test_old_two_commits_wording_is_gone(self):
        """Guard against the v1.2.0 wording regressing. The old prompt said
        ``create git commits using deviate.core.commit.commit_artifact`` and
        emitted two commit subjects ``docs(architecture): <summary>`` and
        ``docs(architecture): sync domain model with architecture.md`` — that
        per-file commit pattern must never return.
        """
        text = self._command_text()
        # The old per-file commit-orchestration prose must be gone.
        assert (
            "create git commits using `deviate.core.commit.commit_artifact`" not in text
        )
        assert "sync domain model with architecture.md" not in text


class TestPlatformFrontmatter:
    """On-disk command frontmatter is minimal and platform-agnostic."""

    def test_installed_command_has_only_name_and_description(self, tmp_path: Path):
        target = tmp_path / "agent" / "commands"
        install_command("deviate-red", target)
        content = (target / "deviate-red.md").read_text(encoding="utf-8")
        # Frontmatter block: only `description:` and `name:` (no category,
        # version, aliases, or other DeviaTDD-internal keys).
        fm = content.split("---\n", 2)[1]
        lines = [line.strip() for line in fm.splitlines() if line.strip()]
        keys = [line.split(":", 1)[0].strip() for line in lines]
        assert set(keys) <= {"name", "description"}

    def test_installed_command_drops_layer_from_frontmatter(self, tmp_path: Path):
        """The internal `layer:` key (used for composition) is stripped on install."""
        target = tmp_path / "agent" / "commands"
        install_command("deviate-red", target)
        content = (target / "deviate-red.md").read_text(encoding="utf-8")
        fm = content.split("---\n", 2)[1]
        assert "layer:" not in fm

    def test_installed_command_body_preserved_after_strip(self, tmp_path: Path):
        """Body (post-frontmatter) is the composed body, layer prefix included."""
        target = tmp_path / "agent" / "commands"
        install_command("deviate-red", target)
        content = (target / "deviate-red.md").read_text(encoding="utf-8")
        # The universal-invariants block is part of the composed body and
        # must remain in the installed output (proves core prefix is composed).
        assert "<universal_invariants>" in content
