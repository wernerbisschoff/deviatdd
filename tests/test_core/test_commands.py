from __future__ import annotations

from pathlib import Path

import yaml

from deviate.core.commands import (
    DEFAULT_LAYER_PACKS,
    DEFAULT_PACK_NAMES,
    OPTIONAL_PACK_NAMES,
    OPTIONAL_PACKS,
    UnknownPackError,
    classify_packaged_stems,
    commands_for_packs,
    compose_command_body,
    discover_commands,
    install_command,
    parse_optional_packs,
    redact_libref,
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


class TestShardCommandIssueIdFormat:
    """``deviate-shard`` command must use per-epic ``<epic-prefix>-<ordinal>`` ids.

    New issues in numbered epic buckets (``001-…``, ``002-…``) emit per-epic
    ids of the form ``<epic-prefix>-<ordinal>`` (e.g. ``002-001``), where
    ``<epic-prefix>`` is the leading 3-digit segment of the epic bucket dir.
    The adhoc bucket and bootstrap contexts fall back to the legacy global
    counter ``ISS-NNN``. The command must instruct the LLM to consume
    ``next_issue_id`` directly and increment per shard — it must NEVER
    concatenate the epic identifier into a 3-segment ``ISS-<epic>-<NNN>``
    shape, which would produce duplicate ids and break the resolve layer.
    """

    @staticmethod
    def _command_text() -> str:
        return resolve_command("deviate-shard").read_text(encoding="utf-8")

    def test_instruction_uses_per_epic_format(self):
        """Issue ID assignment rule must show per-epic ``002-001`` examples."""
        text = self._command_text()
        assert "002-001" in text
        assert "002-002" in text

    def test_blocked_by_examples_use_per_epic_format(self):
        """blocked_by example must reference per-epic ids, not flat ``ISS-NNN-NNN``."""
        text = self._command_text()
        assert 'blocked_by: ["002-001"]' in text
        assert 'blocked_by: ["ISS-001-004"]' not in text

    def test_manifest_schema_uses_per_epic_format(self):
        """Manifest schema must declare per-epic shape, not 3-segment legacy."""
        text = self._command_text()
        assert "<epic-prefix>-<ordinal>" in text
        assert "ISS-<epic>-<NNN>" not in text

    def test_manifest_example_uses_per_epic_format(self):
        """Manifest example must show per-epic ids (``002-001``, not 3-segment legacy)."""
        text = self._command_text()
        assert '"issue_id": "002-001"' in text
        assert "ISS-003-001" not in text
        assert "ISS-003-002" not in text

    def test_instruction_references_legacy_fallback(self):
        """The rule must explicitly call out the legacy ``ISS-NNN`` fallback."""
        text = self._command_text()
        assert "ISS-NNN" in text


class TestDeviateFlowsCommitAtSignOff:
    """``/deviate-flows`` v1.4.0 contract: draft-on-disk and
    commit-only-on-sign-off.

    These guards describe the remaining user-visible sign-off behavior.
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

    def test_old_two_commits_wording_is_gone(self):
        """Guard against the v1.3.0 ambiguity regressing. The old prompt
        said ``create a single git commit (or two commits, one per file)``
        — that wording must never return.
        """
        text = self._command_text()
        assert "or two commits, one per file" not in text
        assert "create a single git commit (or two commits" not in text


class TestDeviateArchitectureCommitAtSignOff:
    """``/deviate-architecture`` v1.3.0 contract: draft-on-disk and
    commit-only-on-sign-off.

    These guards describe the remaining user-visible sign-off behavior.
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

    def test_installed_command_strips_constitution_when_no_constitution_in_workdir(
        self, tmp_path: Path
    ):
        """When no ``specs/constitution.md`` exists in ``workdir``, the installed
        command does not embed a stray constitution block. This guards the
        greenfield case where ``deviate setup`` runs before ``deviate research``
        scaffolds the constitution.
        """
        workdir = tmp_path / "repo"
        workdir.mkdir()
        target = tmp_path / "agent" / "commands"

        install_command("deviate-red", target, workdir=workdir)
        content = (target / "deviate-red.md").read_text(encoding="utf-8")
        # No constitution present → no fake constitution text injected.
        assert "Tech Stack Standards" not in content
        assert "## Constitution" not in content

    def test_installed_command_includes_constitution_when_workdir_has_one(
        self, tmp_path: Path
    ):
        """When ``workdir/specs/constitution.md`` exists, ``install_command``
        prepends it to the installed slash command so manual-mode agents
        see the constitution at the top of the prompt — same parity as the
        auto path's ``load_template()``. This closes the gap where an agent
        running ``/deviate-red`` saw the core invariants but never the
        constitution, and could silently substitute a mandated tech-stack
        component (e.g., deferring Phoenix LiveView for a framework-free shell).
        """
        workdir = tmp_path / "repo"
        workdir.mkdir()
        specs_dir = workdir / "specs"
        specs_dir.mkdir()
        const_path = specs_dir / "constitution.md"
        const_path.write_text(
            "# Tech Stack Standards\n\n"
            "## Backend\n"
            "- Phoenix LiveView 1.2+ (HEEx + Tailwind, WebSocket transport)\n",
            encoding="utf-8",
        )

        target = tmp_path / "agent" / "commands"
        install_command("deviate-red", target, workdir=workdir)
        content = (target / "deviate-red.md").read_text(encoding="utf-8")

        # The constitution content must appear in the installed file.
        assert "Tech Stack Standards" in content
        assert "Phoenix LiveView" in content
        # The constitution must be the first tier (precede core invariants).
        constitution_pos = content.index("Tech Stack Standards")
        core_pos = content.index("<universal_invariants>")
        assert constitution_pos < core_pos, (
            "constitution must precede <universal_invariants> in the composed body"
        )


class TestDeviateHtmlCommand:
    """``/deviate-html`` slash command — manual, on-demand HTML authoring prompt.

    The CLI side (``deviate html <phase>``) is covered by
    ``tests/test_cli/test_html.py``. This class pins the *slash command*
    side: the prompt file exists at the canonical source path, gets picked
    up by ``discover_commands()`` (so ``deviate setup`` installs it for
    every agent platform), and carries valid frontmatter with the
    expected ``name`` / ``description``.
    """

    def test_source_file_exists(self) -> None:
        """The prompt lives next to the rest of the command library."""
        path = _SOURCE_COMMANDS_ROOT / "deviate-html.md"
        assert path.is_file(), (
            f"Slash command source missing: {path}. ``deviate setup`` will "
            f"not install ``/deviate-html`` for any agent platform."
        )

    def test_discover_commands_includes_deviate_html(self) -> None:
        """``discover_commands()`` returns ``deviate-html`` from the source vault.

        This is what ``deviate setup`` iterates over to install commands into
        ``.claude/commands/``, ``.opencode/commands/``, ``.factory/commands/``,
        ``.pi/prompts/``, ``.omp/prompts/``. A future rename or accidental
        deletion of ``deviate-html.md`` will fail this test before any agent
        platform silently loses the command.
        """
        result = discover_commands(commands_root=_SOURCE_COMMANDS_ROOT)
        assert "deviate-html" in result, (
            f"deviate-html missing from discovered command set: {result}"
        )

    def test_frontmatter_parses_with_correct_name(self) -> None:
        """The YAML frontmatter parses and the ``name`` field equals the file stem."""
        path = _SOURCE_COMMANDS_ROOT / "deviate-html.md"
        content = path.read_text(encoding="utf-8")
        assert content.startswith("---\n"), (
            f"{path.name}: missing leading YAML frontmatter delimiter"
        )
        # ``split("---", 2)[1]`` returns the block between the leading
        # delimiter and the next one. The frontmatter is a flat mapping with
        # no nested documents, so a naive split is sufficient.
        fm_block = content.split("---\n", 2)[1]
        fm = yaml.safe_load(fm_block)
        assert isinstance(fm, dict), f"{path.name}: frontmatter did not parse to a dict"
        assert fm.get("name") == "deviate-html", (
            f"{path.name}: frontmatter name mismatch "
            f"(got {fm.get('name')!r}, expected 'deviate-html')"
        )

    def test_frontmatter_description_is_nonempty(self) -> None:
        """The ``description`` field is present and non-empty — it's surfaced
        in the agent platform's command palette and used for discovery."""
        path = _SOURCE_COMMANDS_ROOT / "deviate-html.md"
        content = path.read_text(encoding="utf-8")
        fm_block = content.split("---\n", 2)[1]
        fm = yaml.safe_load(fm_block)
        description = fm.get("description")
        assert isinstance(description, str) and description.strip(), (
            f"{path.name}: description must be a non-empty string (got {description!r})"
        )


class TestConsumerRepositoryPromptBoundaries:
    def test_issue_and_task_commands_have_valid_frontmatter_and_boundary(self):
        for command_name in (
            "deviate-adhoc",
            "deviate-shard",
            "deviate-plan",
            "deviate-tasks",
        ):
            content = resolve_command(
                command_name, commands_root=_SOURCE_COMMANDS_ROOT
            ).read_text(encoding="utf-8")
            parts = content.split("---", 2)
            assert len(parts) == 3, f"{command_name}: malformed frontmatter"
            frontmatter = yaml.safe_load(parts[1])
            assert isinstance(frontmatter, dict)
            assert frontmatter["name"] == command_name
            assert isinstance(frontmatter.get("aliases"), list)

            body = parts[2]
            assert "<consumer_repository_boundary>" in body
            assert "META_WORK_NOT_ALLOWED" in body
            assert "application behavior" in body
            assert "read-only" in body.lower()

    def test_commands_keep_dev_repo_setup_out_of_generated_work(self):
        for command_name in (
            "deviate-adhoc",
            "deviate-shard",
            "deviate-plan",
            "deviate-tasks",
        ):
            content = resolve_command(
                command_name, commands_root=_SOURCE_COMMANDS_ROOT
            ).read_text(encoding="utf-8")
            assert "agent skill" in content
            assert "flow authoring" in content.lower()
            assert "do not" in content.lower()


class TestComposeCommandBodyConstitutionInjection:
    """``compose_command_body`` must prepend the constitution as the first
    tier when ``constitution_path`` resolves to a real file — closing the
    manual/slash-command parity gap with the auto path's
    ``deviate.prompts.assembly.load_template``. Without this, agents running
    via ``/deviate-*`` slash commands never see the constitution at the top
    of the prompt and can silently substitute a mandated tech-stack
    component (e.g., deferring Phoenix LiveView for a framework-free shell).
    """

    @staticmethod
    def _core_dir() -> Path:
        return (
            Path(__file__).resolve().parents[2] / "src" / "deviate" / "prompts" / "core"
        )

    @staticmethod
    def _sample_command() -> str:
        return (
            "---\n"
            "name: test-command\n"
            "description: sample\n"
            "layer: micro\n"
            "---\n"
            "\n"
            "# Body\n"
            "This is the command body.\n"
        )

    def test_constitution_prepended_when_path_provided(self, tmp_path: Path):
        const = tmp_path / "constitution.md"
        const.write_text(
            "# Constitution\nMandated: Phoenix LiveView.\n", encoding="utf-8"
        )

        composed = compose_command_body(
            self._sample_command(), self._core_dir(), constitution_path=const
        )
        assert composed is not None
        assert "Mandated: Phoenix LiveView." in composed
        # Constitution content must appear before the core invariants.
        const_pos = composed.index("Mandated: Phoenix LiveView.")
        core_pos = composed.index("<universal_invariants>")
        assert const_pos < core_pos, (
            "constitution must precede <universal_invariants> in the composed body"
        )

    def test_no_constitution_injection_when_path_is_none(self, tmp_path: Path):
        composed = compose_command_body(
            self._sample_command(), self._core_dir(), constitution_path=None
        )
        assert composed is not None
        assert "<universal_invariants>" in composed

    def test_no_constitution_injection_when_file_missing(self, tmp_path: Path):
        missing = tmp_path / "absent.md"
        assert not missing.exists()

        composed = compose_command_body(
            self._sample_command(), self._core_dir(), constitution_path=missing
        )
        assert composed is not None
        assert "<universal_invariants>" in composed


class TestComposeCommandBodyProductLayerLifecycle:
    """``layer: product`` commands (deviate-release, deviate-architecture,
    deviate-flows) must NOT inherit the manual-mode pre/post-script
    lifecycle, which assumes ``deviate <phase> pre`` exists for every phase.
    Product-layer commands write a single artifact and commit via
    ``deviate.core.commit.commit_artifact`` — there is no pre-script and no
    post-script. The composer must route these commands to the product-layer
    shared lifecycle block instead of ``lifecycle-manual.md``.
    """

    @staticmethod
    def _core_dir() -> Path:
        return (
            Path(__file__).resolve().parents[2] / "src" / "deviate" / "prompts" / "core"
        )

    @staticmethod
    def _sample_command() -> str:
        return (
            "---\n"
            "name: test-product-command\n"
            "description: sample\n"
            "layer: product\n"
            "---\n"
            "\n"
            "# Body\n"
            "This is the command body.\n"
        )

    def test_product_layer_skips_manual_lifecycle_block(self):
        composed = compose_command_body(self._sample_command(), self._core_dir())
        assert composed is not None
        # The <lifecycle mode="manual"> block must be absent — that block
        # instructs agents to run ``deviate <phase> pre`` which does not
        # exist for product-layer commands (no release/architecture/flows
        # pre-script subcommand). The product-shared block may mention the
        # phrase in negated form ("there is **no** deviate <phase> pre");
        # we test the structural marker, not the phrase.
        assert '<lifecycle mode="manual">' not in composed, (
            "product-layer commands must not inherit the manual pre/post-script "
            "lifecycle block; release has no deviate <phase> pre subcommand"
        )

    def test_product_layer_includes_product_shared_block(self):
        composed = compose_command_body(self._sample_command(), self._core_dir())
        assert composed is not None
        assert "commit_artifact" in composed, (
            "product-layer lifecycle block must reference commit_artifact"
        )
        assert '<lifecycle mode="product">' in composed, (
            'product-layer lifecycle block must be tagged with mode="product"'
        )

    def test_micro_layer_still_uses_manual_lifecycle(self):
        """Regression guard: only ``layer: product`` skips the manual block;
        ``layer: micro`` and ``layer: meso`` and ``layer: macro`` keep it."""
        raw = (
            "---\n"
            "name: test-micro-command\n"
            "description: sample\n"
            "layer: micro\n"
            "---\n"
            "\n"
            "# Body\n"
        )
        composed = compose_command_body(raw, self._core_dir())
        assert composed is not None
        assert '<lifecycle mode="manual">' in composed
        assert '<lifecycle mode="product">' not in composed


class TestManualDerivationFromAutoCore:
    """AC-PLAN-001/003/004: the manual slash-command derives from the canonical
    ``auto/{phase}.md`` core plus the per-phase manual overlay — never from a
    hand-maintained duplicate middle file.

    ``install_command`` must splice the auto core body verbatim into the installed
    command. The overlay (frontmatter, manual lifecycle block, rich handover
    manifest, ``<context><user_input>``) lives outside the shared middle, so the
    middle region of the installed file stays byte-identical to ``auto/{phase}.md``.
    """

    _AUTO_ROOT = (
        Path(__file__).resolve().parents[2] / "src" / "deviate" / "prompts" / "auto"
    )
    _OVERLAPPING_PHASES = sorted(
        [
            "explore",
            "research",
            "prd",
            "shard",
            "plan",
            "tasks",
            "red",
            "green",
            "refactor",
            "judge",
            "execute",
        ]
    )

    @staticmethod
    def _read_auto(phase: str) -> str:
        return (TestManualDerivationFromAutoCore._AUTO_ROOT / f"{phase}.md").read_text(
            encoding="utf-8"
        )

    @staticmethod
    def _installed(name: str, tmp_path: Path) -> str:
        target = tmp_path / "agent" / "commands"
        install_command(name, target)
        return (target / f"{name}.md").read_text(encoding="utf-8")

    def test_installed_red_embeds_auto_core(self, tmp_path):
        """The canonical ``auto/red.md`` body appears verbatim in the installed manual.

        Every overlapping phase body is composed from the auto core. A manual
        command whose middle originates from the old hand-maintained duplicate
        fails this check.
        """
        installed = self._installed("deviate-red", tmp_path)
        assert self._read_auto("red") in installed

    def test_installed_red_middle_is_byte_identical_to_auto(self, tmp_path):
        """The installed middle region — from the first ``<system_instructions>``
        tag, which every ``auto/{phase}.md`` opens with — must equal ``auto/red.md``
        byte-for-byte. The overlay may add content only outside this region."""
        installed = self._installed("deviate-red", tmp_path)
        auto = self._read_auto("red")
        start = installed.index("<system_instructions>")
        assert installed[start : start + len(auto)] == auto

    def test_all_11_phases_derive_identical_middle(self, tmp_path):
        """Drift guard: every overlapping phase's derived manual middle is
        byte-identical to its canonical ``auto/{phase}.md`` core."""
        for phase in self._OVERLAPPING_PHASES:
            installed = self._installed(f"deviate-{phase}", tmp_path)
            auto = self._read_auto(phase)
            start = installed.index("<system_instructions>")
            assert installed[start : start + len(auto)] == auto, (
                f"deviate-{phase}: derived manual middle diverged from auto/{phase}.md"
            )

    def test_derived_red_carries_no_manual_duplicate_middle(self, tmp_path):
        """Hand-maintained duplicate content — the retry contract, the
        ledger-wording drift, and abort-on-passing-test — must not reappear in
        the derived output."""
        installed = self._installed("deviate-red", tmp_path)
        assert "Retry Contract (test_defect)" not in installed
        assert "test has a PENDING status in the `tasks.jsonl` ledger" not in installed
        assert "Abort — test must fail first" not in installed
        assert not any(
            line.strip() == 'status: "FAIL"' for line in installed.splitlines()
        )

    def test_derived_red_carries_auto_handover_semantics(self, tmp_path):
        """Auto's ``status: "PASS"`` + ``failure_kind`` handover semantics
        survive into the derived manual."""
        installed = self._installed("deviate-red", tmp_path)
        assert 'status: "PASS"' in installed
        assert "failure_kind" in installed
        assert "already_satisfied" in installed

    def test_derived_green_carries_auto_role_language(self, tmp_path):
        """GREEN derives auto's "write ONLY production code" instruction, not
        the duplicate's "maintain existing functional signatures" wording."""
        installed = self._installed("deviate-green", tmp_path)
        assert "Write ONLY production code" in installed
        assert (
            "Maintain existing functional signatures — do not change test files"
            not in installed
        )

    def test_derived_install_remains_idempotent(self, tmp_path):
        """AC-PLAN-004: re-install with identical canonical resources returns
        ``False`` and leaves the on-disk command unchanged."""
        target = tmp_path / "agent" / "commands"
        assert install_command("deviate-red", target) is True
        first = (target / "deviate-red.md").read_text(encoding="utf-8")
        assert install_command("deviate-red", target) is False
        assert (target / "deviate-red.md").read_text(encoding="utf-8") == first

    def test_derived_overlapping_phases_have_one_arguments_seam(self, tmp_path):
        """Auto cores must not carry a second $ARGUMENTS seam; the overlay owns it."""
        for phase in self._OVERLAPPING_PHASES:
            installed = self._installed(f"deviate-{phase}", tmp_path)
            auto = self._read_auto(phase)
            assert "$ARGUMENTS" not in auto, f"auto/{phase}.md still has $ARGUMENTS"
            assert installed.count("$ARGUMENTS") == 1, (
                f"deviate-{phase}: expected one $ARGUMENTS after derive "
                f"(got {installed.count('$ARGUMENTS')})"
            )



_PRODUCT_BUNDLE = ("deviate-flows", "deviate-architecture", "deviate-release")


class TestCommandPacks:
    def test_every_packaged_stem_is_classified(self) -> None:
        assert classify_packaged_stems() == []

    def test_default_packs_are_execution_layers_only(self) -> None:
        assert DEFAULT_PACK_NAMES == ("macro", "meso", "micro")
        assert tuple(DEFAULT_LAYER_PACKS) == ("macro", "meso", "micro")
        assert "product" not in DEFAULT_LAYER_PACKS
        assert "deviate-init" in DEFAULT_LAYER_PACKS["macro"]

    def test_product_is_optional_bundle(self) -> None:
        assert OPTIONAL_PACKS["product"] == _PRODUCT_BUNDLE
        assert OPTIONAL_PACK_NAMES[0] == "product"
        stems = commands_for_packs()
        assert "deviate-red" in stems
        assert "deviate-explore" in stems
        assert "deviate-plan" in stems
        assert "deviate-init" in stems
        assert "deviate-pr" not in stems
        for stem in _PRODUCT_BUNDLE:
            assert stem not in stems

    def test_commands_for_packs_product_writes_all_three(self) -> None:
        stems = commands_for_packs(("product",))
        for stem in _PRODUCT_BUNDLE:
            assert stem in stems
        assert "deviate-pr" not in stems
        assert "deviate-merge" not in stems

    def test_parse_optional_packs_names(self) -> None:
        assert parse_optional_packs("none") == ()
        assert parse_optional_packs("pr,review") == ("pr", "review")
        assert parse_optional_packs("product") == ("product",)
        assert parse_optional_packs("merge,pr") == ("merge", "pr")
        all_optional = parse_optional_packs("all-optional")
        assert "product" in all_optional
        assert "pr" in all_optional
        assert all_optional[0] == "product"

    def test_parse_unknown_pack_raises(self) -> None:
        try:
            parse_optional_packs("graphite")
        except UnknownPackError:
            return
        raise AssertionError("expected UnknownPackError")

    def test_redact_libref_drops_matching_lines(self) -> None:
        text = "keep\nuse libref query foo\nkeep2\n"
        assert "libref" not in redact_libref(text).lower()
        assert "keep" in redact_libref(text)
