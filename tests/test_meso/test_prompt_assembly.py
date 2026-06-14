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

        claude_path = tmp_path / "CLAUDE.md"
        claude_path.write_text("# Claude Rules\nBe concise.\n")

        result = inject_constitution(prompt, const_path, claude_path)

        assert "# Constitution" in result
        assert "# Claude Rules" in result
        assert "## <context>" in result

    def test_inject_constitution_missing_claude_skips(self, tmp_path: Path):
        prompt = "## <context>\n<user_input>\n</user_input>"

        const_path = tmp_path / "constitution.md"
        const_path.write_text("# Constitution\nRule 1: Always test.\n")

        claude_path = tmp_path / "CLAUDE.md"
        assert not claude_path.exists()

        result = inject_constitution(prompt, const_path, claude_path)

        assert "# Constitution" in result
        assert "## <context>" in result
