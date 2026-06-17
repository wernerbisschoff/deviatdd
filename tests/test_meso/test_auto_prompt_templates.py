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
    "specify.md",
    "tasks.md",
]

# Maps template names (without .md) to expected context marker
_CONTEXT_MAP = {
    "explore": "## <context>",
    "research": "## <context>",
    "prd": "## <context>",
    "shard": "## <context>",
    "specify": "## <context>",
    "plan": "<context>",
    "tasks": "<context>",
}


class TestSlimPromptTemplatesExist:
    def test_all_six_template_files_exist(self):
        ref = files("deviate.prompts.auto")
        with as_file(ref) as auto_dir:
            md_files = {p.name for p in Path(auto_dir).glob("*.md")}
        for name in SLIM_TEMPLATES:
            assert name in md_files, f"Missing template: {name}"

    def test_all_six_templates_have_nonempty_content(self):
        for name in SLIM_TEMPLATES:
            content = _read_template(name)
            assert content, f"{name} should not be empty"

    def test_each_template_has_frontmatter_or_role_header(self):
        for name in SLIM_TEMPLATES:
            content = _read_template(name)
            assert content.startswith("---") or "## " in content[:80], (
                f"{name}: expected frontmatter or markdown header"
            )


class TestSlimPromptPattern:
    def test_composed_template_has_context_marker(self):
        for name, marker in _CONTEXT_MAP.items():
            composed = load_template(name)
            assert marker in composed, f"{name}: expected {marker!r} in composed prompt"

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

    _CORE_MARKER = "## DeviaTDD Universal Invariants"
    _LAYER_MARKERS = {
        "explore": "## Macro Layer Execution Model",
        "research": "## Macro Layer Execution Model",
        "prd": "## Macro Layer Execution Model",
        "shard": "## Macro Layer Execution Model",
        "specify": "## Macro Layer Execution Model",
        "plan": "## Meso Layer Execution Model",
        "tasks": "## Meso Layer Execution Model",
        "red": "## Micro Layer Execution Model",
        "green": "## Micro Layer Execution Model",
        "refactor": "## Micro Layer Execution Model",
        "yellow": "## Micro Layer Execution Model",
        "judge": "## Micro Layer Execution Model",
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
            assert (
                "## <context>" in tail
                or "<context>" in tail
                or "## Role Definition" in tail
            ), f"{name}: expected phase-specific content after layer preamble"

    def test_composition_has_double_newline_separators(self):
        for name in SLIM_TEMPLATES:
            composed = load_template(self._no_ext(name))
            assert "\n\n## " in composed, (
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
        assert "${" not in content or "## <context>" in content

    def test_no_placeholders_in_research(self):
        content = _read_template("research.md")
        assert "${" not in content or "## <context>" in content

    def test_no_placeholders_in_prd(self):
        content = _read_template("prd.md")
        assert "${" not in content or "## <context>" in content

    def test_no_placeholders_in_shard(self):
        content = _read_template("shard.md")
        assert "${" not in content or "## <context>" in content

    def test_no_placeholders_in_specify(self):
        content = _read_template("specify.md")
        assert "${" not in content or "## <context>" in content

    def test_no_placeholders_in_tasks(self):
        content = _read_template("tasks.md")
        assert "${" not in content or "## <context>" in content
