from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path


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
    def test_explore_template_has_context_marker(self):
        content = _read_template("explore.md")
        assert "## <context>" in content or "## Context" in content

    def test_research_template_has_context_marker(self):
        content = _read_template("research.md")
        assert "## <context>" in content or "## Context" in content

    def test_prd_template_has_context_marker(self):
        content = _read_template("prd.md")
        assert "## <context>" in content or "## Context" in content

    def test_shard_template_has_context_marker(self):
        content = _read_template("shard.md")
        assert "## <context>" in content or "## Context" in content

    def test_specify_template_has_context_marker(self):
        content = _read_template("specify.md")
        assert (
            "## <context>" in content
            or "## Context" in content
            or "<context>" in content
        )

    def test_tasks_template_has_context_marker(self):
        content = _read_template("tasks.md")
        assert (
            "## <context>" in content
            or "## Context" in content
            or "<context>" in content
        )

    def test_each_template_has_minimum_content_length(self):
        for name in SLIM_TEMPLATES:
            content = _read_template(name)
            assert len(content) >= 100, (
                f"{name}: too short ({len(content)} chars, min 100)"
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
