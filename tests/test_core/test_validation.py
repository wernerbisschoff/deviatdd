from __future__ import annotations

from deviate.core.validation import (
    extract_section_body,
    validate_gherkin_syntax,
    validate_sections,
    validate_task_id,
    validate_yaml_frontmatter,
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


class TestValidateSections:
    def test_validate_explore_sections_detects_missing(self):
        content = (
            "## DISCOVERY_AUDIT_RESULTS\n"
            "\n"
            "Found some things\n"
            "\n"
            "## FILE_REGISTRY\n"
            "\n"
            "- src/file.py\n"
        )
        required = [
            "PROBLEM_DEFINITION",
            "DISCOVERY_AUDIT_RESULTS",
            "CONSTITUTION_QUOTES",
            "FILE_REGISTRY",
            "STATUS_SUMMARY",
        ]
        missing = validate_sections(content, required)
        assert "PROBLEM_DEFINITION" in missing
        assert "CONSTITUTION_QUOTES" in missing
        assert "STATUS_SUMMARY" in missing
        assert "DISCOVERY_AUDIT_RESULTS" not in missing
        assert "FILE_REGISTRY" not in missing

    def test_validate_sections_returns_empty_when_all_present(self):
        content = "## AAA\ncontent\n\n## BBB\ncontent\n\n## CCC\ncontent\n"
        missing = validate_sections(content, ["AAA", "BBB", "CCC"])
        assert missing == []

    def test_validate_sections_empty_content_all_missing(self):
        missing = validate_sections("", ["A", "B"])
        assert missing == ["A", "B"]

    def test_validate_sections_whitespace_only_treated_as_empty(self):
        missing = validate_sections("   \n\n  \n", ["X", "Y"])
        assert missing == ["X", "Y"]

    def test_validate_research_artifacts_detects_missing(self):
        design_sections = [
            "PROBLEM_DEFINITION",
            "SYSTEM_TOPOLOGY_MAPPING",
            "THE_PROBLEM_CONTRACT",
            "SCOPE_BOUNDARIES",
            "PERFORMANCE_CONSTRAINTS",
            "MULTI_TIERED_VERIFICATION_TARGETS",
            "ATDD_ACCEPTANCE_CRITERIA_LEDGER",
            "SYSTEM_STATUS_SUMMARY",
            "DESIGN_TRADE_OFF_MATRIX",
        ]
        content = (
            "## PROBLEM_DEFINITION\ncontent\n"
            "## SYSTEM_TOPOLOGY_MAPPING\ncontent\n"
            "## THE_PROBLEM_CONTRACT\ncontent\n"
            "## SCOPE_BOUNDARIES\ncontent\n"
            "## PERFORMANCE_CONSTRAINTS\ncontent\n"
            "## MULTI_TIERED_VERIFICATION_TARGETS\ncontent\n"
            "## ATDD_ACCEPTANCE_CRITERIA_LEDGER\ncontent\n"
            "## SYSTEM_STATUS_SUMMARY\ncontent\n"
        )
        missing = validate_sections(content, design_sections)
        assert "DESIGN_TRADE_OFF_MATRIX" in missing
        assert len(missing) == 1

    def test_validate_sections_handles_nonexistent_file_path(self):
        result = validate_sections(None, ["A"])
        assert result is not None


class TestValidateYamlFrontmatter:
    def test_validate_shard_frontmatter_validates_yaml(self):
        content = (
            "---\ntitle: Task 001\nissue_id: ISS-007\nfr: FR-001\n---\n\nBody content\n"
        )
        assert validate_yaml_frontmatter(content) is True

    def test_validate_yaml_frontmatter_invalid_syntax_fails(self):
        content = "---\ntitle: unmatched quote\nfr: 'broken\n---\n\nBody\n"
        assert validate_yaml_frontmatter(content) is False

    def test_validate_yaml_frontmatter_missing_delimiters_fails(self):
        content = "No frontmatter delimiters here\n"
        assert validate_yaml_frontmatter(content) is False

    def test_validate_yaml_frontmatter_empty_after_delimiter_fails(self):
        content = "---\n---\n\nBody\n"
        assert validate_yaml_frontmatter(content) is True


class TestValidateTaskId:
    def test_validate_task_ids_accepts_TSK_format(self):
        assert validate_task_id("TSK-007-01") is True
        assert validate_task_id("TSK-123-99") is True
        assert validate_task_id("TSK-000-00") is True

    def test_validate_task_ids_rejects_malformed(self):
        assert validate_task_id("T001") is False
        assert validate_task_id("TASK_1") is False
        assert validate_task_id("TSK001") is False
        assert validate_task_id("T01") is False
        assert validate_task_id("T0001") is False
        assert validate_task_id("TSK-007-1") is False
        assert validate_task_id("TSK-07-01") is False
        assert validate_task_id("") is False
