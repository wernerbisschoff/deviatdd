"""Tests for AC-ADHOC-012-13: 15 phase skill prompts each carry a Write instruction.

Scenario 012-13 from ``specs/adhoc/issues/012-deviate-content.md`` —
each ``src/deviate/prompts/commands/<name>.md`` for the 15 listed
phase skills contains a one-sentence Write instruction that references
the canonical ``handover_path()`` target.

Canonical list per ``specs/plans/deviate-content.md:79-87``:

* Micro layer (10 skills): ``deviate-red``, ``deviate-green``,
  ``deviate-yellow``, ``deviate-judge``, ``deviate-refactor``,
  ``deviate-execute``, ``deviate-e2e``, ``deviate-hotfix``,
  ``deviate-prune``, ``deviate-review``
* Macro layer (5 skills): ``deviate-research``, ``deviate-prd``,
  ``deviate-shard``, ``deviate-plan``, ``deviate-tasks``

The instruction uses the deterministic marker ``handover_path()`` so
the append operation is idempotent against repeated re-runs (per
``specs/adhoc/issues/012-deviate-content.md`` Edge Cases and
Boundaries: "Re-running the implementation against an updated 15-skill
list: The append operation must be idempotent. ... Use a deterministic
marker (e.g., the literal string ``handover_path()``) to detect
presence.").

The instruction lives inside the terminal-contract section of each
skill — either the ``## Handover Persistence (FLOW-11)`` heading inside
the ``<output_format_schemas>`` block (14 of 15 skills) or the
``<handover_persistence>`` XML tag (``deviate-review``).
"""

from __future__ import annotations

import pytest

from deviate.core.commands import resolve_command


# Canonical list per specs/plans/deviate-content.md:79-87.
# Total: 15 skills (10 micro + 5 macro).
PHASE_COMMANDS: list[str] = [
    # Micro layer (10 skills)
    "deviate-red",
    "deviate-green",
    "deviate-yellow",
    "deviate-judge",
    "deviate-refactor",
    "deviate-execute",
    "deviate-e2e",
    "deviate-hotfix",
    "deviate-prune",
    "deviate-review",
    # Macro layer (5 skills)
    "deviate-research",
    "deviate-prd",
    "deviate-shard",
    "deviate-plan",
    "deviate-tasks",
]

_MICRO_COMMANDS: list[str] = [
    "deviate-red",
    "deviate-green",
    "deviate-yellow",
    "deviate-judge",
    "deviate-refactor",
    "deviate-execute",
    "deviate-e2e",
    "deviate-hotfix",
    "deviate-prune",
    "deviate-review",
]

_MACRO_COMMANDS: list[str] = [
    "deviate-research",
    "deviate-prd",
    "deviate-shard",
    "deviate-plan",
    "deviate-tasks",
]


def _extract_terminal_section(text: str) -> str | None:
    """Return the substring that hosts the Write instruction.

    Returns ``None`` when no recognized terminal-contract marker is
    present. The function never raises — callers assert on the return
    value. Recognized section shapes:

    * ``<handover_persistence>...</handover_persistence>`` (deviate-review)
    * ``<output_format_schemas>...</output_format_schemas>``
    * ``<output_format_schemas_design_md>...</output_format_schemas_design_md>``
      (deviate-research — paired design/data-model schema blocks)
    * ``<output_format_schemas_data_model_md>...</output_format_schemas_data_model_md>``
    * Markdown heading ``## Handover Persistence (FLOW-11)`` when no XML
      wrapper exists (deviate-refactor, deviate-e2e, deviate-prune).
    """
    # Prefer XML-tag-wrapped sections (most specific). Match both the
    # singular form and the design/data-model suffixed forms.
    xml_open_tags = (
        "<handover_persistence>",
        "<output_format_schemas>",
        "<output_format_schemas_design_md>",
        "<output_format_schemas_data_model_md>",
    )
    xml_close_tags = (
        "</handover_persistence>",
        "</output_format_schemas>",
        "</output_format_schemas_design_md>",
        "</output_format_schemas_data_model_md>",
    )
    for open_tag, close_tag in zip(xml_open_tags, xml_close_tags, strict=True):
        if open_tag in text and close_tag in text:
            start = text.find(open_tag)
            end = text.find(close_tag, start)
            if start < end:
                return text[start:end]
    # Fallback: markdown heading without XML wrapper.
    if "## Handover Persistence (FLOW-11)" in text:
        start = text.find("## Handover Persistence (FLOW-11)")
        return text[start:]
    return None


class TestCommandPromptHandoverInstruction:
    """AC-ADHOC-012-13 — all 15 listed phase skills carry the Write instruction.

    The instruction must reference the canonical ``handover_path()``
    target at ``.deviate/feat/<epic>/<issue>/[<task>/]<phase>.yaml``.
    """

    @pytest.mark.parametrize("command_name", PHASE_COMMANDS)
    def test_command_has_write_instruction(self, command_name: str) -> None:
        """Each phase command file contains the Write tool reference."""
        path = resolve_command(command_name)
        text = path.read_text(encoding="utf-8")
        assert "Write tool" in text, (
            f"Skill '{command_name}' at {path} is missing the Write tool reference"
        )
        assert "handover_path()" in text, (
            f"Skill '{command_name}' at {path} is missing the deterministic "
            f"marker 'handover_path()'"
        )

    @pytest.mark.parametrize("command_name", PHASE_COMMANDS)
    def test_command_references_canonical_handover_path(
        self, command_name: str
    ) -> None:
        """Each phase skill references the canonical handover path format.

        The instruction must show the ``.deviate/feat/<epic>/<issue>/
        [<task>/]<phase>.yaml`` shape so the skill actor can construct
        the destination without ambiguity.
        """
        path = resolve_command(command_name)
        text = path.read_text(encoding="utf-8")
        assert ".deviate/feat/" in text, (
            f"Skill '{command_name}' does not reference the .deviate/feat/ path"
        )
        for placeholder in ("<epic>", "<issue>", "<phase>"):
            assert placeholder in text, (
                f"Skill '{command_name}' is missing path placeholder '{placeholder}'"
            )

    @pytest.mark.parametrize("command_name", PHASE_COMMANDS)
    def test_command_instruction_lives_in_terminal_contract_section(
        self, command_name: str
    ) -> None:
        """The Write instruction sits inside the terminal-contract section.

        Two accepted shapes:

        * ``## Handover Persistence (FLOW-11)`` heading inside the
          ``<output_format_schemas>`` block (most skills).
        * ``<handover_persistence>`` XML tag (``deviate-review``).
        """
        path = resolve_command(command_name)
        text = path.read_text(encoding="utf-8")

        section = _extract_terminal_section(text)
        assert section is not None, (
            f"Skill '{command_name}' is missing the terminal-contract section "
            "for the handover Write instruction "
            "(expected '## Handover Persistence (FLOW-11)' heading or "
            "'<handover_persistence>' XML tag)"
        )
        assert "Write tool" in section, (
            f"Skill '{command_name}': Write tool reference not located inside "
            "the terminal-contract section"
        )
        assert "handover_path()" in section, (
            f"Skill '{command_name}': 'handover_path()' marker not located "
            "inside the terminal-contract section"
        )

    @pytest.mark.parametrize("command_name", PHASE_COMMANDS)
    def test_command_instruction_is_idempotent(self, command_name: str) -> None:
        """The deterministic marker appears exactly once per skill.

        Re-running the append operation against an already-instrumented
        skill must be a no-op. The contract requires ``handover_path()``
        to occur exactly once; duplicates indicate a non-idempotent
        implementation.
        """
        path = resolve_command(command_name)
        text = path.read_text(encoding="utf-8")
        marker_count = text.count("handover_path()")
        assert marker_count == 1, (
            f"Skill '{command_name}' carries 'handover_path()' {marker_count} "
            "times; expected exactly one occurrence (idempotent append "
            "contract)."
        )


class TestCommandPromptHandoverCoverage:
    """Sanity coverage for the canonical 15-skill list."""

    def test_canonical_skill_list_has_exactly_fifteen(self) -> None:
        assert len(PHASE_COMMANDS) == 15, (
            f"Expected 15 phase skills, got {len(PHASE_COMMANDS)}: {PHASE_COMMANDS}"
        )

    def test_canonical_skill_list_has_no_duplicates(self) -> None:
        assert len(PHASE_COMMANDS) == len(set(PHASE_COMMANDS)), (
            f"Duplicate skill names in canonical list: {PHASE_COMMANDS}"
        )

    def test_micro_layer_covers_ten_skills(self) -> None:
        for name in _MICRO_COMMANDS:
            assert name in PHASE_COMMANDS, f"Missing micro skill: {name}"
        assert len(_MICRO_COMMANDS) == 10
        assert sum(1 for s in PHASE_COMMANDS if s in set(_MICRO_COMMANDS)) == 10

    def test_macro_layer_covers_five_skills(self) -> None:
        for name in _MACRO_COMMANDS:
            assert name in PHASE_COMMANDS, f"Missing macro skill: {name}"
        assert len(_MACRO_COMMANDS) == 5
        assert sum(1 for s in PHASE_COMMANDS if s in set(_MACRO_COMMANDS)) == 5

    @pytest.mark.parametrize("command_name", PHASE_COMMANDS)
    def test_command_file_resolves_and_exists(self, command_name: str) -> None:
        """Each canonical command resolves to an existing .md file on disk."""
        path = resolve_command(command_name)
        assert path.exists(), f"Command file not found: {path}"
        assert path.suffix == ".md"
        assert path.stem == command_name


class TestCommandPromptHandoverNonRegressions:
    """Append is the only allowed modification — no other content drift."""

    @pytest.mark.parametrize("command_name", PHASE_COMMANDS)
    def test_command_keeps_frontmatter_name(self, command_name: str) -> None:
        """Each skill's frontmatter still declares ``name: <skill>``."""
        path = resolve_command(command_name)
        text = path.read_text(encoding="utf-8")
        assert f"name: {command_name}" in text, (
            f"Skill '{command_name}' frontmatter is missing "
            f"'name: {command_name}' (frontmatter regression?)"
        )

    @pytest.mark.parametrize("command_name", PHASE_COMMANDS)
    def test_command_keeps_output_format_schemas_close_tag(
        self, command_name: str
    ) -> None:
        """For skills that wrap their terminal contract in an
        ``<output_format_schemas>`` block, the closing tag must remain
        present so the append stays inside the existing structure.
        Skills that use ``<handover_persistence>``, plural-form
        ``<output_format_schemas_*_md>`` blocks, or no XML wrapper at
        all are unaffected.
        """
        path = resolve_command(command_name)
        text = path.read_text(encoding="utf-8")
        if "<output_format_schemas>" in text:
            assert "</output_format_schemas>" in text, (
                f"Skill '{command_name}' opened an <output_format_schemas> "
                "block but lost its closing tag — the append must be inside "
                "the existing block, not after it."
            )
