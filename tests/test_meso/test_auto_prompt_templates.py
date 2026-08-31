from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path

from deviate.prompts.assembly import load_template


def _read_template(name: str) -> str:
    ref = files("deviate.prompts.auto").joinpath(name)
    with as_file(ref) as p:
        return Path(p).read_text(encoding="utf-8")


SLIM_TEMPLATES = [
    "explore.md",
    "research.md",
    "prd.md",
    "shard.md",
    "tasks.md",
]

# Auto phases whose composed prompts must not carry the manual overlay seam.
_AUTO_COMPOSE_PHASES = (
    "explore",
    "research",
    "prd",
    "shard",
    "plan",
    "tasks",
)


class TestSlimPromptTemplatesExist:
    def test_all_slim_template_files_exist(self):
        ref = files("deviate.prompts.auto")
        with as_file(ref) as auto_dir:
            md_files = {p.name for p in Path(auto_dir).glob("*.md")}
        for name in SLIM_TEMPLATES:
            assert name in md_files, f"Missing template: {name}"

    def test_all_slim_templates_have_nonempty_content(self):
        for name in SLIM_TEMPLATES:
            content = _read_template(name)
            assert content, f"{name} should not be empty"

    def test_each_template_has_frontmatter_or_role_header(self):
        for name in SLIM_TEMPLATES:
            content = _read_template(name)
            assert content.startswith("---") or "<" in content[:80], (
                f"{name}: expected frontmatter or XML header"
            )


class TestSlimPromptPattern:
    def test_composed_auto_templates_omit_manual_context_seam(self):
        """Auto composition is orchestrator-injected. ``<context>`` / ``$ARGUMENTS``
        live only on the per-phase manual overlay (7adffcab $ARGUMENTS dedup).
        Derived manuals keep exactly one ``$ARGUMENTS`` seam — pinned by
        ``TestManualDerivationFromAutoCore.test_derived_overlapping_phases_have_one_arguments_seam``.
        """
        for name in _AUTO_COMPOSE_PHASES:
            composed = load_template(name)
            assert "<context>" not in composed, (
                f"{name}: auto composed prompt must not carry the manual <context> seam"
            )
            assert "$ARGUMENTS" not in composed, (
                f"{name}: auto composed prompt must not carry $ARGUMENTS"
            )

    def test_each_template_has_minimum_content_length(self):
        for name in SLIM_TEMPLATES:
            content = _read_template(name)
            assert len(content) >= 100, (
                f"{name}: too short ({len(content)} chars, min 100)"
            )


class TestPromptComposition:
    """Verify that ``load_template`` correctly composes the 3-tier pipeline.

    Assembly order:
        1. ``core/core.md`` — universal invariants
        2. ``core/{layer}.md`` — layer-specific preamble (macro/meso/micro)
        3. ``auto/{template}.md`` — phase-specific instructions
    """

    _CORE_MARKER = "<universal_invariants>"
    _LAYER_MARKERS = {
        "explore": "<macro_layer_model>",
        "research": "<macro_layer_model>",
        "prd": "<macro_layer_model>",
        "shard": "<macro_layer_model>",
        "plan": "<meso_layer_model>",
        "tasks": "<meso_layer_model>",
        "red": "<micro_layer_model>",
        "green": "<micro_layer_model>",
        "refactor": "<micro_layer_model>",
        "judge": "<micro_layer_model>",
    }

    @staticmethod
    def _no_ext(name: str) -> str:
        """Strip the ``.md`` extension for ``load_template``."""
        return name.removesuffix(".md")

    def test_core_appears_in_every_composed_prompt(self):
        for name in SLIM_TEMPLATES:
            composed = load_template(self._no_ext(name))
            assert self._CORE_MARKER in composed, f"{name}: missing core.md content"

    def test_layer_appears_in_every_composed_prompt(self):
        for name, marker in self._LAYER_MARKERS.items():
            composed = load_template(name)
            assert marker in composed, (
                f"{name}: expected {marker!r} from layer preamble"
            )

    def test_core_precedes_layer_precedes_phase(self):
        for name in SLIM_TEMPLATES:
            composed = load_template(self._no_ext(name))
            core_pos = composed.index(self._CORE_MARKER)
            layer_pos = composed.index(self._LAYER_MARKERS[self._no_ext(name)])
            assert core_pos < layer_pos, (
                f"{name}: core should precede layer, got core@{core_pos} layer@{layer_pos}"
            )

    def test_phase_specific_content_at_end(self):
        for name in SLIM_TEMPLATES:
            composed = load_template(self._no_ext(name))
            layer_pos = composed.index(self._LAYER_MARKERS[self._no_ext(name)])
            tail = composed[layer_pos:]
            assert "<context>" in tail or "## Role Definition" in tail, (
                f"{name}: expected phase-specific content after layer preamble"
            )

    def test_composition_has_double_newline_separators(self):
        for name in SLIM_TEMPLATES:
            composed = load_template(self._no_ext(name))
            assert "\n\n<" in composed, (
                f"{name}: expected double-newline separators between tiers"
            )

    def test_constitution_included_when_path_provided(self, tmp_path: Path):
        const = tmp_path / "test-constitution.md"
        const.write_text("# My Constitution\nRule alpha.\n")
        composed = load_template("explore", constitution_path=const)
        assert "# My Constitution" in composed
        assert composed.startswith("# My Constitution"), (
            "constitution should be the first tier"
        )

    def test_constitution_missing_does_not_break_composition(self):
        composed = load_template("explore", constitution_path=Path("/nonexistent"))
        assert self._CORE_MARKER in composed, (
            "core should still be present when constitution is missing"
        )


class TestSlimPromptConstraints:
    def test_no_placeholders_in_explore(self):
        content = _read_template("explore.md")
        assert "${" not in content or "<context>" in content

    def test_no_placeholders_in_research(self):
        content = _read_template("research.md")
        assert "${" not in content or "<context>" in content

    def test_no_placeholders_in_prd(self):
        content = _read_template("prd.md")
        assert "${" not in content or "<context>" in content

    def test_no_placeholders_in_shard(self):
        content = _read_template("shard.md")
        assert "${" not in content or "<context>" in content

    def test_no_placeholders_in_tasks(self):
        content = _read_template("tasks.md")
        assert "${" not in content or "<context>" in content


class TestFlowTripleMandateRemoved:
    def test_flows_prompt_drops_mandated_triple_and_seed(self):
        text = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "deviate"
            / "prompts"
            / "commands"
            / "deviate-flows.md"
        ).read_text(encoding="utf-8")
        assert "No Mandated Triple" in text
        assert "never delete existing flow IDs (FLOW-01/02/03)" not in text
        assert "avoid re-asking about FLOW-01/02/03" not in text
        assert "extend, never regenerate" not in text
        assert "FLOW-01 seed is absent" not in text

    def test_architecture_prompt_drops_flows_precondition(self):
        text = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "deviate"
            / "prompts"
            / "commands"
            / "deviate-architecture.md"
        ).read_text(encoding="utf-8")
        assert "FLOWS_MISSING" not in text
        assert "Flows Precondition Gate" not in text
        assert "Refuse with `[red]FLOWS_MISSING[/]`" not in text
        assert "FLOW-02 Preconditions" not in text
        assert "No Mandatory Flow Precondition" in text

    def test_release_prompt_drops_arch_or_flows_precondition(self):
        text = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "deviate"
            / "prompts"
            / "commands"
            / "deviate-release.md"
        ).read_text(encoding="utf-8")
        assert "ARCH_OR_FLOWS_MISSING" not in text
        assert "Architecture + Flows Precondition Gate" not in text
        assert "FLOW-03 Preconditions" not in text
        assert "No Mandatory Flow or Architecture Precondition" in text

    def test_adhoc_prompt_drops_flow_triple_inference(self):
        text = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "deviate"
            / "prompts"
            / "commands"
            / "deviate-adhoc.md"
        ).read_text(encoding="utf-8")
        assert (
            "canonical FLOW-01 (Flows), FLOW-02 (Architecture), FLOW-03 (Release)"
            not in text
        )
        assert "Existing Flow Mapping" in text

    def test_flows_index_omits_mandated_triple(self):
        index = (
            Path(__file__).resolve().parents[2]
            / "specs"
            / "_product"
            / "flows"
            / "index.md"
        ).read_text(encoding="utf-8")
        assert "| FLOW-01 |" not in index
        assert "| FLOW-02 |" not in index
        assert "| FLOW-03 |" not in index
        assert "no mandated FLOW-01/02/03 triple" in index

    def test_flows_product_seed_is_optional_starter(self):
        seed = (
            Path(__file__).resolve().parents[2]
            / "specs"
            / "_product"
            / "flows"
            / "flows-product.md"
        ).read_text(encoding="utf-8")
        assert "## FLOW-01 Flows" not in seed
        assert "## FLOW-02 Architecture" not in seed
        assert "## FLOW-03 Release" not in seed
        assert "Optional starter" in seed
        assert "no fixed FLOW-01/02/03" in seed


class TestConsumerRepositoryBoundaries:
    def test_auto_macro_and_meso_prompts_reject_meta_work(self):
        for template_name in ("shard", "plan", "tasks"):
            content = load_template(template_name)
            assert "<consumer_repository_boundary>" in content
            assert "META_WORK_NOT_ALLOWED" in content
            assert "application behavior" in content
            assert "existing" in content.lower()
            assert "read-only" in content.lower()

    def test_auto_prompts_require_application_targets_for_empty_flow_refs(self):
        for template_name in ("shard", "plan", "tasks"):
            content = load_template(template_name)
            assert "flow_refs: []" in content
            assert "do not" in content.lower()
            assert "setup" in content.lower()


class TestMergePromptPushGate:
    """The /deviate-merge prompt runs an inline copy of .githooks/pre-push
    before asking the user whether to push. The inline copy must mirror the
    hook so the safety net fires identically whether the gate runs in-process
    or git invokes the hook at push time. These tests pin the high-value
    drift points between the two bodies — a future contributor editing one
    without the other will fail at least one of these.
    """

    @staticmethod
    def _read_prompt() -> str:
        return (
            Path(__file__).resolve().parents[2]
            / "src"
            / "deviate"
            / "prompts"
            / "commands"
            / "deviate-merge.md"
        ).read_text(encoding="utf-8")

    @staticmethod
    def _read_hook() -> str:
        return (
            Path(__file__).resolve().parents[2] / ".githooks" / "pre-push"
        ).read_text(encoding="utf-8")

    def test_inline_push_step_replaces_direct_git_push(self):
        # No numbered "Push to remote" step that just runs `git push`.
        prompt = self._read_prompt()
        assert "**Push to remote**" not in prompt
        assert "git push\n   ```" not in prompt
        # The gate + prompt steps exist by name.
        assert "**Run the push gate**" in prompt
        assert "Ask the user whether to push**" in prompt
        # Failure states the new flow promises.
        assert "Failure_State: Push_Gate_Failed" in prompt
        assert "Failure_State: Push_Deferred" in prompt
        assert "Failure_State: Push_Failed" in prompt

    def test_inline_gate_mirrors_hook_upstream_first_logic(self):
        prompt = self._read_prompt()
        # Upstream preferred, HEAD~1 fallback, no parent → exit 0.
        assert "@{u}" in prompt
        assert 'git merge-base "$upstream" HEAD' in prompt
        assert "HEAD~1" in prompt
        # GIT_DIR reset + trap preserved verbatim from the hook.
        assert 'GIT_DIR_SAVED="${GIT_DIR-}"' in prompt
        assert 'trap \'[ -n "$GIT_DIR_SAVED" ]' in prompt

    def test_inline_gate_mirrors_hook_testmon_fallback(self):
        prompt = self._read_prompt()
        assert "if [ -s .testmondata ]; then" in prompt
        assert "mise run test-affected" in prompt
        assert "mise run test" in prompt
        # The hook's "no Python files changed" no-op branch is preserved.
        assert "# No upstream, no parent — nothing to compare against." in prompt
        assert 'git diff --name-only --diff-filter=ACMR "$base...HEAD"' in prompt

    @staticmethod
    def _gate_block_lines(text: str, *, marker: str | None) -> set[str]:
        """Return the set of non-blank, non-comment lines that make up the
        gate body, scoped to either the hook (marker=None) or the prompt's
        push_gate fenced block (marker='Run the push gate')."""
        if marker is None:
            # Hook: the executable body starts at the first `set -e` line
            # and runs to EOF, skipping the shebang + the top doc comments.
            lines = text.splitlines()
            start = next(i for i, line in enumerate(lines) if line.strip() == "set -e")
            return {
                line.strip()
                for line in lines[start:]
                if line.strip() and not line.strip().startswith("#")
            }
        # Prompt: extract the fenced ```bash block that immediately follows
        # the `**Run the push gate**` heading (the next ```bash opening
        # fence after that heading is the gate body).
        heading = text.find(marker)
        assert heading != -1, f"prompt is missing heading {marker!r}"
        fence_open = text.find("```bash\n", heading)
        assert fence_open != -1, f"no ```bash fence after {marker!r}"
        body_start = fence_open + len("```bash\n")
        fence_close = text.find("```", body_start)
        assert fence_close != -1, f"unterminated gate fence after {marker!r}"
        return {
            line.strip()
            for line in text[body_start:fence_close].splitlines()
            if line.strip() and not line.strip().startswith("#")
        }

    def test_hook_and_prompt_agree_on_gate_body(self):
        # Strongest invariant: the prompt's push_gate fenced body and the
        # .githooks/pre-push executable body share the same set of
        # non-blank, non-comment lines (ignoring indentation). Drift in
        # either direction — a hook line missing from the prompt, or a
        # prompt line missing from the hook — fails this assertion so
        # the two bodies can never silently diverge.
        hook_lines = self._gate_block_lines(self._read_hook(), marker=None)
        prompt_lines = self._gate_block_lines(
            self._read_prompt(), marker="**Run the push gate**"
        )
        assert hook_lines == prompt_lines, (
            "hook/prompt gate-body drift — "
            f"only-in-hook: {sorted(hook_lines - prompt_lines)[:5]}…, "
            f"only-in-prompt: {sorted(prompt_lines - hook_lines)[:5]}…"
        )


class TestMergePromptBaseBranch:
    """GH-93: /deviate-merge squash-merges onto configured base_branch,
    not a hardcoded ``main``. Operational checkout / log / diff / refuse
    instructions must use the ``{base_branch}`` contract token.
    """

    @staticmethod
    def _read_prompt() -> str:
        return (
            Path(__file__).resolve().parents[2]
            / "src"
            / "deviate"
            / "prompts"
            / "commands"
            / "deviate-merge.md"
        ).read_text(encoding="utf-8")

    def test_merge_prompt_targets_configured_base_branch(self):
        prompt = self._read_prompt()
        assert "git checkout {base_branch}" in prompt
        assert "git log {base_branch}.." in prompt
        assert "git diff {base_branch}..." in prompt
        assert "git checkout main" not in prompt
        assert "git log main.." not in prompt
        assert "git diff main..." not in prompt

    def test_merge_prompt_resolves_base_branch_from_pre_contract(self):
        prompt = self._read_prompt()
        assert "deviate merge pre" in prompt
        assert "base_branch" in prompt
        assert "if not `{base_branch}`" in prompt or "if not {base_branch}" in prompt


class TestReviewPromptSecurityTaxonomy:
    """The review prompt's cross-task Security section must align with the
    OWASP/NIST/LLM taxonomy so aggregation findings cite the same baseline as
    the (OWASP/NIST-aware) JUDGE verdicts."""

    @staticmethod
    def _read_prompt() -> str:
        return (
            Path(__file__).resolve().parents[2]
            / "src"
            / "deviate"
            / "prompts"
            / "commands"
            / "deviate-review.md"
        ).read_text(encoding="utf-8")

    def test_review_security_section_names_taxonomy(self):
        prompt = self._read_prompt()
        assert "OWASP" in prompt, (
            "Review Security section must reference the OWASP taxonomy"
        )
        assert "NIST" in prompt, "Review Security section must reference NIST"
        assert "SSDF" in prompt, (
            "Review Security section must reference the NIST SSDF framework"
        )

    def test_review_security_section_cites_llm_and_category_codes(self):
        prompt = self._read_prompt()
        assert "LLM01" in prompt or "LLM" in prompt, (
            "Review Security section must reference the OWASP LLM lens for",
            " LLM-agent-shaped surfaces",
        )
        assert "A#" in prompt or "A##" in prompt, (
            "Review Security section must direct cross-task findings to cite",
            " an OWASP A# category code",
        )


class TestSmallestChangeFoldedIntoExistingPrompts:
    """GH-92 (rescoped): Ponytail smallest-change lives in existing GREEN /
    REFACTOR / review lines — no new Constraints or Minimality heading.
    """

    @staticmethod
    def _read_review() -> str:
        return (
            Path(__file__).resolve().parents[2]
            / "src"
            / "deviate"
            / "prompts"
            / "commands"
            / "deviate-review.md"
        ).read_text(encoding="utf-8")

    def test_green_prefers_reuse_and_named_files_only(self):
        text = _read_template("green.md")
        assert "Minimal Behavioral Implementation" in text
        assert "stdlib" in text
        assert "already-installed" in text
        assert "no speculative features" in text
        assert "did not name" in text
        assert "## Constraints" not in text
        assert "## Minimality" not in text

    def test_refactor_is_in_place_clarity_not_helper_extraction(self):
        text = _read_template("refactor.md")
        assert "in place" in text
        assert "unrequested helpers" in text
        assert (
            "decompose large logical blocks into focused single-purpose functions"
            not in text
        )
        assert "Extract Function/Method" not in text
        assert "## Constraints" not in text
        assert "## Minimality" not in text

    def test_review_keeps_overengineering_and_does_not_promote_helpers(self):
        text = self._read_review()
        assert "Cross-task over-engineering" in text
        assert "into a shared helper" not in text
        assert "Extract the duplicated validation block" not in text
        assert "Skip every `[OPPORTUNITY]`" in text
        assert "## Constraints" not in text
        assert "## Minimality" not in text


class TestVerificationBatchImmediateRouting:
    """GH-57: planner prompts must lock Verification_Batch → IMMEDIATE."""

    def test_auto_tasks_locks_verification_batch_to_immediate(self):
        repo = Path(__file__).resolve().parents[2]
        # Single-source invariant: the manual deviate-tasks.md derives its body
        # from auto/tasks.md at install time, so the lock strings live only in
        # the canonical auto core.
        path = repo / "src" / "deviate" / "prompts" / "auto" / "tasks.md"
        text = path.read_text(encoding="utf-8")
        assert "Verification_Batch" in text
        assert "never TDD" in text, (
            f"{path.name}: must lock Verification_Batch so it cannot emit Mode: TDD"
        )
        assert "Type→Mode lock" in text or "hard type→mode lock" in text


class TestManualDerivationDriftGuard:
    """Drift guards pinning the single-source invariant: the derived manual
    middle must stay byte-identical to the canonical auto core, and the auto
    handover semantics must survive into the derived manual output.

    Every boundary test invokes ``install_command`` against an isolated
    ``tmp_path`` so the installed ``deviate-{phase}.md`` exists on disk. The 15
    commands-only prompts (no auto counterpart) are exempt.
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
        return (TestManualDerivationDriftGuard._AUTO_ROOT / f"{phase}.md").read_text(
            encoding="utf-8"
        )

    @staticmethod
    def _install(name: str, tmp_path: Path) -> str:
        from deviate.core.commands import install_command

        target = tmp_path / "agent" / "commands"
        install_command(name, target)
        return (target / f"{name}.md").read_text(encoding="utf-8")

    def test_auto_and_manual_middle_identical(self, tmp_path):
        """Every derived manual middle equals the canonical auto core byte-for-byte."""
        for phase in self._OVERLAPPING_PHASES:
            installed = self._install(f"deviate-{phase}", tmp_path)
            auto = self._read_auto(phase)
            start = installed.index("<system_instructions>")
            middle = installed[start : start + len(auto)]
            assert middle == auto, (
                f"deviate-{phase}: derived manual middle diverged from auto/{phase}.md"
            )

    def test_auto_red_uses_pass_failure_kind(self):
        """The canonical auto RED carries ``status: \"PASS\"`` + ``failure_kind``."""
        auto = self._read_auto("red")
        assert 'status: "PASS"' in auto
        assert "failure_kind" in auto
        assert "already_satisfied" in auto
        # The string can appear only in negative instructional form; there must
        # be no standalone ``status: "FAIL"`` handover-manifest entry.
        assert not any(line.strip() == 'status: "FAIL"' for line in auto.splitlines())

    def test_manual_red_matches_auto_semantics(self, tmp_path):
        """The derived manual RED must not emit ``status: \"FAIL\"`` or
        abort-on-passing-test; it inherits auto's ``status: \"PASS\"`` +
        ``failure_kind`` semantics."""
        installed = self._install("deviate-red", tmp_path)
        assert not any(
            line.strip() == 'status: "FAIL"' for line in installed.splitlines()
        )
        assert "Abort — test must fail first" not in installed
        assert 'status: "PASS"' in installed
        assert "failure_kind" in installed

    def test_manual_green_matches_auto_role_language(self, tmp_path):
        """The derived manual GREEN inherits auto's "write ONLY production
        code" role language, not the duplicate's "maintain existing functional
        signatures" wording."""
        installed = self._install("deviate-green", tmp_path)
        assert "Write ONLY production code" in installed
        assert (
            "Maintain existing functional signatures — do not change test files"
            not in installed
        )


class TestPrdShardOwnership:
    """GH-141: PRD owns behavior/traceability; shard owns issue topology.

    Pins the ownership split, flexible FR grouping, no fixed issue-count
    ceiling, and the vertical-slice rules (reject pure horizontal splits;
    allow a persistence-only behavior). String pins, not filename-exists.
    """

    @staticmethod
    def _prd() -> str:
        return _read_template("prd.md")

    @staticmethod
    def _shard() -> str:
        return _read_template("shard.md")

    @staticmethod
    def _acceptance_gates_prd() -> str:
        return (
            Path(__file__).resolve().parents[2]
            / "specs"
            / "005-acceptance-gates"
            / "prd.md"
        ).read_text(encoding="utf-8")

    def test_prd_ownership_rules_are_present(self) -> None:
        prd = self._prd()
        assert (
            "PRD owns behavior, constraints, acceptance criteria, and FR "
            "traceability" in prd
        )
        assert "FRs are traceability units only" in prd
        assert "MUST NOT prescribe issue count, issue IDs, or shard topology" in prd
        assert "Issue Sharding Strategy" in prd

    def test_shard_ownership_rules_are_present(self) -> None:
        shard = self._shard()
        assert (
            "Shard owns issue count, grouping, boundaries, and the "
            "dependency DAG" in shard
        )
        assert "all layers required by the behavior" in shard
        assert "no fixed minimum or maximum issue count" in shard
        assert "INCOMPLETE_FR_COVERAGE" in shard

    def test_prompts_do_not_require_one_issue_per_fr(self) -> None:
        combined = f"{self._prd()}\n{self._shard()}"
        lowered = combined.lower()
        assert "one per fr" not in lowered
        assert "one-issue-per-fr" not in lowered
        assert "one issue per fr" not in lowered

    def test_prompts_do_not_require_fixed_issue_count_or_hard_ceiling(self) -> None:
        shard = self._shard()
        assert "SLICE_CAP_EXCEEDED" not in shard
        assert "Hard ceiling: 10" not in shard
        assert "hard ceiling" not in shard.lower()
        assert "maximum 10" not in shard.lower()
        assert "count ≤ 10" not in shard
        assert "count <= 10" not in shard
        assert "no fixed minimum or maximum issue count" in shard

    def test_shard_requires_independent_behavior_and_executable_verification(
        self,
    ) -> None:
        shard = self._shard()
        assert "independently testable" in shard
        assert "one primary observable behavior" in shard
        assert "executable verification command" in shard
        assert "## Demonstration Path" in shard
        assert "## Scope Boundaries" in shard
        assert "acceptance outcomes" in shard

    def test_multi_fr_and_one_fr_multi_issue_slicing_are_allowed(self) -> None:
        shard = self._shard()
        assert "One issue may cover multiple related FRs" in shard
        assert "One FR may span multiple issues" in shard
        assert "distinct observable behavior" in shard

    def test_pure_horizontal_layer_splits_remain_rejected(self) -> None:
        shard = self._shard()
        assert "HORIZONTAL_SLICE_DETECTED" in shard
        assert "pure horizontal" in shard.lower()
        assert "until ≥2 layers" not in shard
        assert "until >=2 layers" not in shard

    def test_persistence_only_vertical_behavior_remains_allowed(self) -> None:
        shard = self._shard()
        assert "persistence-only" in shard.lower()
        assert "database invariant" in shard.lower()
        assert "pure setup work is not a valid issue" in shard.lower()

    def test_existing_issue_file_and_manifest_shape_remain(self) -> None:
        shard = self._shard()
        for token in (
            "title",
            "labels",
            "source_file",
            "blocked_by",
            "coordinates_with",
            "issue_id",
            "flow_refs",
            "## System Topology Mapping",
            "## The Problem Contract",
            "## Scope Boundaries",
            "## Upstream Requirement Tracing",
            "## Multi-Tiered Verification Targets",
            "## Demonstration Path",
            '"type": "feature"',
        ):
            assert token in shard, f"shard prompt dropped compatible field {token!r}"
        assert "included and excluded FR references" in shard

    def test_acceptance_gates_prd_teaches_flexible_grouping_not_one_per_fr(
        self,
    ) -> None:
        example = self._acceptance_gates_prd()
        assert "one per FR" not in example
        assert "one issue per FR" not in example
        assert "does not prescribe issue count" in example
        assert "Shard owns grouping" in example or "shard owns grouping" in example
