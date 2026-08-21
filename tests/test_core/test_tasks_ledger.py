from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError


class TestGenerateJsonlFromMd:
    def test_parses_task_lines_into_jsonl_records(self, tmp_path: Path):
        from deviate.core.tasks_ledger import generate_jsonl_from_md

        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text(
            "# Tasks\n\n"
            "- TSK-005-06: Implement tasks.jsonl proposal pattern\n"
            "  - **Type**: Feature_Batch\n"
            "  - **Mode**: TDD\n"
            "  - **Test Strategy**: Integration\n"
            "  - **Rationale**: US-005-SKILLS\n\n"
            "- TSK-005-07: Do something else\n"
            "  - **Type**: Domain_Batch\n"
            "  - **Mode**: IMMEDIATE\n"
            "  - **Test Strategy**: Sociable_Unit\n"
        )

        records = generate_jsonl_from_md(tasks_md, issue_id="ISS-002-005")

        assert len(records) == 2
        assert records[0].id == "TSK-005-06"
        assert records[0].issue_id == "ISS-002-005"
        assert records[0].description == "Implement tasks.jsonl proposal pattern"
        assert records[0].status == "PENDING"
        assert records[0].execution_mode == "TDD"

        assert records[1].id == "TSK-005-07"
        assert records[1].issue_id == "ISS-002-005"
        assert records[1].description == "Do something else"
        assert records[1].status == "PENDING"
        assert records[1].execution_mode == "IMMEDIATE"

    def test_verification_batch_maps_to_immediate_even_when_mode_is_tdd(
        self, tmp_path: Path
    ):
        from deviate.core.tasks_ledger import generate_jsonl_from_md

        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text(
            "# Tasks\n\n"
            "- TSK-005-03: Row-validator accept/reject cases\n"
            "  - **Type**: Verification_Batch\n"
            "  - **Mode**: TDD\n"
            "  - **Test Strategy**: Sociable_Unit\n"
            "  - **Green**: No production change.\n"
            "- TSK-005-01: Implement the model field\n"
            "  - **Type**: Feature_Batch\n"
            "  - **Mode**: TDD\n"
        )

        records = generate_jsonl_from_md(tasks_md, issue_id="005-002")

        assert len(records) == 2
        assert records[0].execution_mode == "IMMEDIATE"
        assert records[1].execution_mode == "TDD"

    def test_empty_tasks_md_returns_empty_list(self, tmp_path: Path):
        from deviate.core.tasks_ledger import generate_jsonl_from_md

        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text("")

        records = generate_jsonl_from_md(tasks_md, issue_id="ISS-002-005")
        assert records == []

    def test_no_task_lines_returns_empty_list(self, tmp_path: Path):
        from deviate.core.tasks_ledger import generate_jsonl_from_md

        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text("# Just a title\n\nSome text without task lines.\n")

        records = generate_jsonl_from_md(tasks_md, issue_id="ISS-002-005")
        assert records == []

    def test_propagates_acceptance_criteria_links_into_task_records(
        self, tmp_path: Path
    ):
        from deviate.core.tasks_ledger import generate_jsonl_from_md

        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text(
            "# Tasks\n\n"
            "- TSK-005-01: Implement criterion link parsing\n"
            "  - **Mode**: TDD\n"
            "  - **Acceptance Criteria**: AC-PLAN-001 (automated, "
            "tests/test_core/test_tasks_ledger.py), AC-PLAN-002 (manual)\n"
            "  - **Rationale**: US-005-03\n"
        )

        records = generate_jsonl_from_md(tasks_md, issue_id="005-002")

        assert len(records) == 1
        links = records[0].acceptance_criteria
        assert links is not None
        assert len(links) == 2
        assert links[0].criterion_id == "AC-PLAN-001"
        assert links[0].verification_mode == "automated"
        assert links[0].test_ref == "tests/test_core/test_tasks_ledger.py"
        assert links[1].criterion_id == "AC-PLAN-002"
        assert links[1].verification_mode == "manual"
        assert links[1].test_ref is None

    def test_task_without_criteria_bullet_carries_null_not_empty_list(
        self, tmp_path: Path
    ):
        from deviate.core.tasks_ledger import generate_jsonl_from_md

        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text(
            "# Tasks\n\n"
            "- TSK-005-01: Task with criterion references\n"
            "  - **Mode**: TDD\n"
            "  - **Acceptance Criteria**: AC-PLAN-001 (automated, "
            "tests/test_core/test_tasks_ledger.py)\n"
            "- TSK-005-04: Task without criterion references\n"
            "  - **Mode**: TDD\n"
        )

        records = generate_jsonl_from_md(tasks_md, issue_id="005-002")

        assert len(records) == 2
        assert records[0].acceptance_criteria is not None
        dumped = json.loads(records[1].model_dump_json())
        assert dumped["acceptance_criteria"] is None

    def test_malformed_criterion_id_fails_generation_with_named_error(
        self, tmp_path: Path
    ):
        from deviate.core.tasks_ledger import generate_jsonl_from_md

        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text(
            "# Tasks\n\n"
            "- TSK-005-02: Task with a malformed criterion id\n"
            "  - **Mode**: TDD\n"
            "  - **Acceptance Criteria**: AC-PLAN-99 (automated, "
            "tests/test_core/test_tasks_ledger.py)\n"
        )

        with pytest.raises((ValidationError, ValueError)) as excinfo:
            generate_jsonl_from_md(tasks_md, issue_id="005-002")
        assert "AC-PLAN-99" in str(excinfo.value)

    def test_automated_link_without_test_ref_fails_generation(self, tmp_path: Path):
        from deviate.core.tasks_ledger import generate_jsonl_from_md

        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text(
            "# Tasks\n\n"
            "- TSK-005-02: Task with an automated link missing test_ref\n"
            "  - **Mode**: TDD\n"
            "  - **Acceptance Criteria**: AC-PLAN-001 (automated)\n"
        )

        with pytest.raises(ValidationError) as excinfo:
            generate_jsonl_from_md(tasks_md, issue_id="005-002")
        assert "test_ref" in str(excinfo.value)

    def test_invalid_verification_mode_fails_generation(self, tmp_path: Path):
        from deviate.core.tasks_ledger import generate_jsonl_from_md

        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text(
            "# Tasks\n\n"
            "- TSK-005-02: Task with an invalid verification mode\n"
            "  - **Mode**: TDD\n"
            "  - **Acceptance Criteria**: AC-PLAN-001 (soon)\n"
        )

        with pytest.raises((ValidationError, ValueError)) as excinfo:
            generate_jsonl_from_md(tasks_md, issue_id="005-002")
        assert "soon" in str(excinfo.value)

    def test_unparseable_criteria_entry_fails_generation_with_named_error(
        self, tmp_path: Path
    ):
        from deviate.core.tasks_ledger import generate_jsonl_from_md

        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text(
            "# Tasks\n\n"
            "- TSK-005-02: Task with an unparseable criteria entry\n"
            "  - **Mode**: TDD\n"
            "  - **Acceptance Criteria**: AC-PLAN-001 automated\n"
        )

        with pytest.raises(ValueError) as excinfo:
            generate_jsonl_from_md(tasks_md, issue_id="005-002")
        message = str(excinfo.value)
        assert "AC-PLAN-001 automated" in message
        assert "TSK-005-02" in message

    def test_multi_token_test_ref_fails_generation_with_named_error(
        self, tmp_path: Path
    ):
        from deviate.core.tasks_ledger import generate_jsonl_from_md

        tasks_md = tmp_path / "tasks.md"
        tasks_md.write_text(
            "# Tasks\n\n"
            "- TSK-005-02: Task with a multi-token test_ref\n"
            "  - **Mode**: TDD\n"
            "  - **Acceptance Criteria**: AC-PLAN-001 (automated, tests/a.py, "
            "tests/b.py)\n"
        )

        with pytest.raises(ValueError) as excinfo:
            generate_jsonl_from_md(tasks_md, issue_id="005-002")
        message = str(excinfo.value)
        assert "AC-PLAN-001 (automated, tests/a.py, tests/b.py)" in message
        assert "TSK-005-02" in message


class TestResolveExecutionMode:
    def test_verification_batch_is_immediate_even_when_declared_tdd(self):
        from deviate.core.tasks_ledger import resolve_execution_mode

        assert resolve_execution_mode("Verification_Batch", "TDD") == "IMMEDIATE"
        assert resolve_execution_mode("Verification_Batch", "IMMEDIATE") == "IMMEDIATE"

    def test_other_types_keep_declared_mode(self):
        from deviate.core.tasks_ledger import resolve_execution_mode

        assert resolve_execution_mode("Feature_Batch", "TDD") == "TDD"
        assert resolve_execution_mode("Feature_Batch", "IMMEDIATE") == "IMMEDIATE"
        assert resolve_execution_mode("Bugfix", "TDD") == "TDD"
        assert resolve_execution_mode("Config", "IMMEDIATE") == "IMMEDIATE"
        assert resolve_execution_mode(None, "TDD") == "TDD"


class TestValidateTasksJsonl:
    def test_valid_records_pass_validation(self):
        from deviate.core.tasks_ledger import validate_tasks_jsonl

        records = [
            {
                "id": "TSK-005-06",
                "issue_id": "ISS-002-005",
                "description": "Task 1",
                "status": "PENDING",
                "execution_mode": "TDD",
            },
            {
                "id": "TSK-005-07",
                "issue_id": "ISS-002-005",
                "description": "Task 2",
                "status": "PENDING",
                "execution_mode": "IMMEDIATE",
            },
        ]

        errors = validate_tasks_jsonl(records)
        assert errors == []

    def test_invalid_task_id_returns_error(self):
        from deviate.core.tasks_ledger import validate_tasks_jsonl

        records = [
            {
                "id": "INVALID",
                "issue_id": "ISS-002-005",
                "description": "Bad task",
                "status": "PENDING",
                "execution_mode": "TDD",
            },
        ]

        errors = validate_tasks_jsonl(records)
        assert len(errors) > 0
        assert any("INVALID" in err for err in errors)

    def test_missing_required_field_returns_error(self):
        from deviate.core.tasks_ledger import validate_tasks_jsonl

        records = [
            {
                "id": "TSK-005-06",
                "description": "Missing issue_id",
                "status": "PENDING",
                "execution_mode": "TDD",
            },
        ]

        errors = validate_tasks_jsonl(records)
        assert len(errors) > 0

    def test_invalid_status_returns_error(self):
        from deviate.core.tasks_ledger import validate_tasks_jsonl

        records = [
            {
                "id": "TSK-005-06",
                "issue_id": "ISS-002-005",
                "description": "Invalid status",
                "status": "MADE_UP_STATUS",
                "execution_mode": "TDD",
            },
        ]

        errors = validate_tasks_jsonl(records)
        assert len(errors) > 0

    def test_extra_fields_trigger_validation_error(self):
        from deviate.core.tasks_ledger import validate_tasks_jsonl

        records = [
            {
                "id": "TSK-005-06",
                "issue_id": "ISS-002-005",
                "description": "Extra field",
                "status": "PENDING",
                "execution_mode": "TDD",
                "unknown_field": "should_fail",
            },
        ]

        errors = validate_tasks_jsonl(records)
        assert len(errors) > 0

    def test_valid_link_row_passes_validation(self):
        from deviate.core.tasks_ledger import validate_tasks_jsonl

        records = [
            {
                "id": "TSK-005-01",
                "issue_id": "005-002",
                "description": "Task with valid criterion links",
                "status": "PENDING",
                "execution_mode": "TDD",
                "acceptance_criteria": [
                    {
                        "criterion_id": "AC-PLAN-001",
                        "verification_mode": "automated",
                        "test_ref": "tests/test_core/test_tasks_ledger.py",
                    },
                    {
                        "criterion_id": "AC-PLAN-002",
                        "verification_mode": "manual",
                    },
                ],
            }
        ]

        errors = validate_tasks_jsonl(records)
        assert errors == []

    def test_malformed_criterion_id_returns_error_naming_acceptance_criteria(
        self,
    ):
        from deviate.core.tasks_ledger import validate_tasks_jsonl

        records = [
            {
                "id": "TSK-005-01",
                "issue_id": "005-002",
                "description": "Task with a malformed criterion id link",
                "status": "PENDING",
                "execution_mode": "TDD",
                "acceptance_criteria": [
                    {
                        "criterion_id": "AC-PLAN-99",
                        "verification_mode": "manual",
                    }
                ],
            }
        ]

        errors = validate_tasks_jsonl(records)
        assert any("acceptance_criteria" in error for error in errors)
        assert any("AC-PLAN-99" in error for error in errors)

    def test_automated_link_without_test_ref_returns_error_naming_acceptance_criteria(
        self,
    ):
        from deviate.core.tasks_ledger import validate_tasks_jsonl

        records = [
            {
                "id": "TSK-005-01",
                "issue_id": "005-002",
                "description": "Task with an automated link missing test_ref",
                "status": "PENDING",
                "execution_mode": "TDD",
                "acceptance_criteria": [
                    {
                        "criterion_id": "AC-PLAN-001",
                        "verification_mode": "automated",
                    }
                ],
            }
        ]

        errors = validate_tasks_jsonl(records)
        assert any("acceptance_criteria" in error for error in errors)
        assert any("test_ref" in error for error in errors)

    def test_legacy_row_without_acceptance_criteria_passes_validation(self):
        from deviate.core.tasks_ledger import validate_tasks_jsonl

        records = [
            {
                "id": "TSK-005-03",
                "issue_id": "005-002",
                "description": "Legacy row from an older CLI version",
                "status": "PENDING",
                "execution_mode": "TDD",
                "created_at": "2026-07-04T07:49:30Z",
            }
        ]

        errors = validate_tasks_jsonl(records)
        assert errors == []

    def test_link_row_with_unknown_field_still_fails_validation(self):
        from deviate.core.tasks_ledger import validate_tasks_jsonl

        records = [
            {
                "id": "TSK-005-01",
                "issue_id": "005-002",
                "description": "Task with links and an unknown field",
                "status": "PENDING",
                "execution_mode": "TDD",
                "acceptance_criteria": [
                    {
                        "criterion_id": "AC-PLAN-001",
                        "verification_mode": "manual",
                    }
                ],
                "unknown_field": "should_fail",
            }
        ]

        errors = validate_tasks_jsonl(records)
        assert any("unknown_field" in error for error in errors)
