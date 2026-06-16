from __future__ import annotations

from pathlib import Path


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
