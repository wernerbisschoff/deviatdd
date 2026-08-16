from __future__ import annotations

from deviate.core.validation import (
    extract_section_body,
    validate_acceptance_contract,
    validate_acceptance_outline,
    validate_gherkin_syntax,
    validate_sections,
    validate_source_file,
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

    def test_validate_gherkin_syntax_ac_block_valid(self):
        content = (
            "**AC-1-01: First acceptance criterion**\n"
            "\n"
            "- **Given**: A precondition\n"
            "- **When**: An action occurs\n"
            "- **Then**: An outcome is expected\n"
        )
        errors = validate_gherkin_syntax(content)
        assert errors == []

    def test_validate_gherkin_syntax_ac_block_missing_given(self):
        content = (
            "**AC-2-03: AC missing given**\n"
            "\n"
            "- **When**: An action occurs\n"
            "- **Then**: An outcome is expected\n"
        )
        errors = validate_gherkin_syntax(content)
        assert any("Given" in e for e in errors)
        assert any("AC-2-03" in e for e in errors)

    def test_validate_gherkin_syntax_mixed_scenario_and_ac(self):
        content = (
            "**Scenario 1: First**\n"
            "\n"
            "- **Given**: Pre\n"
            "- **When**: Act\n"
            "- **Then**: Assert\n"
            "\n"
            "**AC-3-02: AC follows scenario**\n"
            "\n"
            "- **Given**: Pre2\n"
            "- **When**: Act2\n"
            "- **Then**: Assert2\n"
        )
        errors = validate_gherkin_syntax(content)
        assert errors == []


class TestAcceptanceOwnershipValidation:
    def test_acceptance_outline_rejects_gherkin_leak(self):
        content = (
            "## Acceptance Outline\n"
            "- **AO-001**: Valid input succeeds.\n"
            "  - **Given** a configured repository\n"
            "  - **When** the command runs\n"
            "  - **Then** it exits successfully\n"
        )

        assert validate_acceptance_outline(content) == [
            "GHERKIN_LEAK_DETECTED: Acceptance Outline must not contain "
            "Given/When/Then clauses"
        ]

    def test_acceptance_outline_requires_outline_id(self):
        content = "## Acceptance Outline\n- Valid input succeeds.\n"

        assert validate_acceptance_outline(content) == [
            "Acceptance Outline must contain at least one AO-NNN token"
        ]

    def test_acceptance_contract_requires_complete_scenario(self):
        content = (
            "## Acceptance Contract\n"
            "**Scenario AC-PLAN-001: Valid input succeeds**\n"
            "- **Source Outline**: AO-001\n"
            "- **Upstream Traceability**: FR-001-DEMO, AC-001-DEMO-01\n"
            "- **Current-Code Evidence**: src/demo.py:run\n"
            "- **Given**: A configured repository\n"
            "- **Then**: The command succeeds\n"
            "- **Verification Mode**: automated\n"
        )

        errors = validate_acceptance_contract(content)

        assert errors == ["AC-PLAN-001: missing 'When'"]

    def test_acceptance_contract_requires_outline_traceability(self):
        content = (
            "## Acceptance Contract\n"
            "**Scenario AC-PLAN-001: Valid input succeeds**\n"
            "- **Given**: A configured repository\n"
            "- **Upstream Traceability**: FR-001-DEMO, AC-001-DEMO-01\n"
            "- **Current-Code Evidence**: src/demo.py:run\n"
            "- **When**: The command runs\n"
            "- **Then**: It succeeds\n"
            "- **Verification Mode**: automated\n"
        )

        assert validate_acceptance_contract(content) == [
            "AC-PLAN-001: missing Source Outline AO-NNN traceability"
        ]

    def test_acceptance_contract_requires_upstream_and_code_evidence(self):
        content = (
            "## Acceptance Contract\n"
            "**Scenario AC-PLAN-001: Valid input succeeds**\n"
            "- **Source Outline**: AO-001\n"
            "- **Given**: A configured repository\n"
            "- **When**: The command runs\n"
            "- **Then**: It succeeds\n"
            "- **Verification Mode**: automated\n"
        )

        assert validate_acceptance_contract(content) == [
            "AC-PLAN-001: missing Upstream Traceability",
            "AC-PLAN-001: missing Current-Code Evidence",
        ]


def _contract_scenario(
    scenario_id: str = "AC-PLAN-001",
    *,
    mode_line: str = "- **Verification Mode**: automated",
    include_source: bool = True,
    include_upstream: bool = True,
    include_evidence: bool = True,
    include_gherkin: bool = True,
) -> str:
    lines = [f"**Scenario {scenario_id}: Some criterion**"]
    if include_source:
        lines.append("- **Source Outline**: AO-001")
    if include_upstream:
        lines.append("- **Upstream Traceability**: FR-005-01, AC-005-01-01")
    if include_evidence:
        lines.append("- **Current-Code Evidence**: src/demo.py:run")
    if include_gherkin:
        lines += [
            "- **Given**: A configured repository",
            "- **When**: The command runs",
            "- **Then**: The outcome holds",
        ]
    lines.append(mode_line)
    return "\n".join(lines)


def _wrap_contract(scenario_bodies: list[str]) -> str:
    return "## Acceptance Contract\n" + "\n\n".join(scenario_bodies)


class TestVerificationModeValidation:
    def test_accepts_each_verification_mode_literal(self):
        for mode in ("automated", "manual", "deferred"):
            content = _wrap_contract(
                [_contract_scenario(mode_line=f"- **Verification Mode**: {mode}")]
            )
            assert validate_acceptance_contract(content) == [], mode

    def test_accepts_case_variant_literal(self):
        content = _wrap_contract(
            [_contract_scenario(mode_line="- **Verification Mode**: Deferred")]
        )
        assert validate_acceptance_contract(content) == []

    def test_accepts_surrounding_whitespace_around_literal(self):
        content = _wrap_contract(
            [_contract_scenario(mode_line="- **Verification Mode**:   automated  ")]
        )
        assert validate_acceptance_contract(content) == []

    def test_accepts_all_deferred_contract(self):
        bodies = [
            _contract_scenario(
                "AC-PLAN-001", mode_line="- **Verification Mode**: deferred"
            ),
            _contract_scenario(
                "AC-PLAN-002", mode_line="- **Verification Mode**: Deferred"
            ),
        ]
        assert validate_acceptance_contract(_wrap_contract(bodies)) == []

    def test_rejects_missing_verification_mode(self):
        content = _wrap_contract(
            [_contract_scenario(mode_line="", include_source=True)]
        )
        assert validate_acceptance_contract(content) == [
            "AC-PLAN-001: missing Verification Mode"
        ]

    def test_rejects_empty_verification_mode_value(self):
        content = _wrap_contract(
            [_contract_scenario(mode_line="- **Verification Mode**:")]
        )
        assert validate_acceptance_contract(content) == [
            "AC-PLAN-001: missing Verification Mode"
        ]

    def test_rejects_illegal_verification_mode_value(self):
        content = _wrap_contract(
            [_contract_scenario(mode_line="- **Verification Mode**: soon")]
        )
        assert validate_acceptance_contract(content) == [
            "AC-PLAN-001: invalid Verification Mode 'soon'; expected one of automated|manual|deferred"
        ]

    def test_rejects_case_variant_outside_literals(self):
        content = _wrap_contract(
            [_contract_scenario(mode_line="- **Verification Mode**: Soon")]
        )
        assert validate_acceptance_contract(content) == [
            "AC-PLAN-001: invalid Verification Mode 'Soon'; expected one of automated|manual|deferred"
        ]

    def test_rejects_duplicate_verification_mode_lines(self):
        body = _contract_scenario() + "\n- **Verification Mode**: deferred"
        content = _wrap_contract([body])
        assert validate_acceptance_contract(content) == [
            "AC-PLAN-001: duplicate Verification Mode lines"
        ]

    def test_valid_mode_does_not_waive_mandatory_clauses(self):
        content = _wrap_contract(
            [
                _contract_scenario(
                    include_upstream=False,
                    mode_line="- **Verification Mode**: automated",
                )
            ]
        )
        assert validate_acceptance_contract(content) == [
            "AC-PLAN-001: missing Upstream Traceability",
        ]

    def test_valid_mode_does_not_waive_gherkin_clauses(self):
        content = _wrap_contract(
            [
                _contract_scenario(
                    include_gherkin=False,
                    mode_line="- **Verification Mode**: automated",
                )
            ]
        )
        assert validate_acceptance_contract(content) == [
            "AC-PLAN-001: missing 'Given'",
            "AC-PLAN-001: missing 'When'",
            "AC-PLAN-001: missing 'Then'",
        ]

    def test_mixed_modes_validate_independently(self):
        bodies = [
            _contract_scenario(
                "AC-PLAN-001", mode_line="- **Verification Mode**: automated"
            ),
            _contract_scenario(
                "AC-PLAN-002", mode_line="- **Verification Mode**: manual"
            ),
            _contract_scenario(
                "AC-PLAN-003", mode_line="- **Verification Mode**: deferred"
            ),
        ]
        assert validate_acceptance_contract(_wrap_contract(bodies)) == []

    def test_mixed_modes_report_error_on_the_offending_scenario_only(self):
        bodies = [
            _contract_scenario(
                "AC-PLAN-001", mode_line="- **Verification Mode**: automated"
            ),
            _contract_scenario(
                "AC-PLAN-002", mode_line="- **Verification Mode**: soon"
            ),
        ]
        assert validate_acceptance_contract(_wrap_contract(bodies)) == [
            "AC-PLAN-002: invalid Verification Mode 'soon'; expected one of automated|manual|deferred",
        ]

    def test_zero_scenario_contract_keeps_existing_error(self):
        content = "## Acceptance Contract\n\nNo scenarios here.\n"
        assert validate_acceptance_contract(content) == [
            "Acceptance Contract must contain at least one AC-PLAN-NNN scenario"
        ]

    def test_missing_contract_section_keeps_existing_error(self):
        content = "## Other Section\nbody\n"
        assert validate_acceptance_contract(content) == [
            "PLAN_ACCEPTANCE_CONTRACT_MISSING"
        ]


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
        content = "---\ntitle: Task 001\nissue_id: ISS-001-007\nfr: FR-001\n---\n\nBody content\n"
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


class TestValidateSourceFile:
    def test_accepts_matching_issue_file(self):
        assert (
            validate_source_file(
                "specs/001-deviate-cli-python/issues/008-meso-macro.md",
                "001-deviate-cli-python",
            )
            is True
        )

    def test_accepts_kebab_slug_under_issues_dir(self):
        assert (
            validate_source_file(
                "specs/002-deviatdd-gap-analysis/issues/005-micro-layer-integrity.md",
                "002-deviatdd-gap-analysis",
            )
            is True
        )

    def test_rejects_prd_reference(self):
        assert (
            validate_source_file(
                "specs/001-deviate-cli-python/prd.md",
                "001-deviate-cli-python",
            )
            is False
        )

    def test_rejects_design_reference(self):
        assert (
            validate_source_file(
                "specs/001-deviate-cli-python/design.md",
                "001-deviate-cli-python",
            )
            is False
        )

    def test_rejects_data_model_reference(self):
        assert (
            validate_source_file(
                "specs/001-deviate-cli-python/data-model.md",
                "001-deviate-cli-python",
            )
            is False
        )

    def test_rejects_explore_reference(self):
        assert (
            validate_source_file(
                "specs/explore/some-slug.md",
                "001-deviate-cli-python",
            )
            is False
        )

    def test_rejects_empty_source_file(self):
        assert validate_source_file("", "001-deviate-cli-python") is False

    def test_rejects_absolute_path(self):
        assert (
            validate_source_file(
                "/specs/001-deviate-cli-python/issues/001-foo.md",
                "001-deviate-cli-python",
            )
            is False
        )

    def test_rejects_wrong_epic_slug(self):
        assert (
            validate_source_file(
                "specs/002-other-epic/issues/001-foo.md",
                "001-deviate-cli-python",
            )
            is False
        )

    def test_rejects_non_md_extension(self):
        assert (
            validate_source_file(
                "specs/001-deviate-cli-python/issues/001-foo.txt",
                "001-deviate-cli-python",
            )
            is False
        )

    def test_rejects_missing_issues_dir_segment(self):
        assert (
            validate_source_file(
                "specs/001-deviate-cli-python/001-foo.md",
                "001-deviate-cli-python",
            )
            is False
        )

    def test_rejects_relative_path_without_specs_prefix(self):
        assert (
            validate_source_file(
                "001-deviate-cli-python/issues/001-foo.md",
                "001-deviate-cli-python",
            )
            is False
        )
