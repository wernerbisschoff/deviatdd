from __future__ import annotations

from pathlib import Path

import pytest

from deviate.prompts.assembly import inject_constitution, load_template


class TestLoadTemplate:
    def test_load_template_success(self):
        content = load_template("specify")
        assert content
        assert "<system_instructions>" in content

    def test_load_template_missing_raises(self):
        with pytest.raises(FileNotFoundError):
            load_template("nonexistent")


class TestInjectConstitution:
    def test_inject_constitution_appends_content(self, tmp_path: Path):
        prompt = "## <context>\n<user_input>\n</user_input>"

        const_path = tmp_path / "constitution.md"
        const_path.write_text("# Constitution\nRule 1: Always test.\n")

        result = inject_constitution(prompt, const_path)

        assert "# Constitution" in result
        assert "## <context>" in result

    def test_inject_constitution_missing_file_returns_unchanged(self, tmp_path: Path):
        prompt = "## <context>\n<user_input>\n</user_input>"

        const_path = tmp_path / "nonexistent.md"
        assert not const_path.exists()

        result = inject_constitution(prompt, const_path)

        assert result == prompt


class TestLoadTemplateNoManualOverlayLeak:
    """AC-PLAN-004: the auto composition must emit the canonical auto core only.

    Manual-overlay markers — the manual pre/post-script lifecycle, the rich
    handover manifest, the ``<context><user_input>`` contract block — must never
    leak into the auto path's output."""

    def test_auto_micro_composition_has_no_manual_overlay_leak(self):
        """The auto loader on the micro layer injects the auto lifecycle block and
        emits the core body only. A leaked manual pre/post-script lifecycle block
        or a stray ``<context>`` marker fails this check."""
        for phase in ("red", "green", "refactor", "judge", "execute"):
            composed = load_template(phase)
            assert '<lifecycle mode="auto">' in composed, (
                f"{phase}: expected auto lifecycle block"
            )
            assert '<lifecycle mode="manual">' not in composed, (
                f"{phase}: manual lifecycle leaked into auto composition"
            )
            assert "pre/post-script lifecycle" not in composed.lower(), (
                f"{phase}: manual lifecycle wording leaked into auto composition"
            )
            assert "<context>" not in composed, (
                f"{phase}: manual <context> contract block leaked into auto composition"
            )
        auto_red = load_template("red")
        for marker in ("Retry Contract", "deviate red pre"):
            assert marker not in auto_red, (
                f"manual overlay marker {marker!r} leaked into the auto body"
            )
        assert not any(
            line.strip() == 'status: "FAIL"' for line in auto_red.splitlines()
        ), 'auto red must not emit a standalone `status: "FAIL"` handover entry'
