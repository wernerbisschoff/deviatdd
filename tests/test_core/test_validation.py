from __future__ import annotations

from deviate.core.validation import (
    extract_section_body,
    validate_gherkin_syntax,
)


class TestExtractSectionBody:
    def test_extract_section_body_found(self):
        content = (
            "## [TESTING_PROTOCOLS]\n"
            "\n"
            "pytest is the test runner\n"
            "\n"
            "## [ANOTHER_SECTION]\n"
        )
        body = extract_section_body(content, "[TESTING_PROTOCOLS]")
        assert body is not None
        assert "pytest is the test runner" in body

    def test_extract_section_body_not_found(self):
        content = "## [OTHER]\ncontent\n"
        body = extract_section_body(content, "[MISSING]")
        assert body is None

    def test_extract_section_body_empty(self):
        content = "## [EMPTY]\n\n## [NEXT]\n"
        body = extract_section_body(content, "[EMPTY]")
        assert body is not None
        assert body.strip() == ""


class TestValidateGherkinSyntax:
    def test_validate_gherkin_syntax_valid_block(self):
        content = (
            "**Scenario 1: Something happens**\n"
            "\n"
            "- **Given**: A precondition\n"
            "- **When**: An action occurs\n"
            "- **Then**: An outcome is expected\n"
        )
        errors = validate_gherkin_syntax(content)
        assert errors == []

    def test_validate_gherkin_syntax_missing_given(self):
        content = (
            "**Scenario 1: Missing given**\n"
            "\n"
            "- **When**: An action occurs\n"
            "- **Then**: An outcome is expected\n"
        )
        errors = validate_gherkin_syntax(content)
        assert len(errors) >= 1
        assert any("Given" in e for e in errors)

    def test_validate_gherkin_syntax_no_scenarios(self):
        content = "Just some random text without scenarios.\n"
        errors = validate_gherkin_syntax(content)
        assert errors == []

    def test_validate_gherkin_syntax_multiple_scenarios(self):
        content = (
            "**Scenario 1: First**\n"
            "\n"
            "- **Given**: Pre\n"
            "- **When**: Act\n"
            "- **Then**: Assert\n"
            "\n"
            "**Scenario 2: Second**\n"
            "\n"
            "- **Given**: Pre2\n"
            "- **When**: Act2\n"
            "- **Then**: Assert2\n"
        )
        errors = validate_gherkin_syntax(content)
        assert errors == []
