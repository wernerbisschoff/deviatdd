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


class TestJudgeTemplate:
    """judge.md prompt template references ## Structured Diff Summary.

    AC-ADHOC-008-01: Structured diff injected into JUDGE prompt
    """

    def test_judge_md_references_structured_diff(self) -> None:
        """judge.md must reference ## Structured Diff Summary section."""
        template = load_template("judge")
        assert "## Structured Diff Summary" in template, (
            "judge.md template should reference ## Structured Diff Summary"
        )


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
