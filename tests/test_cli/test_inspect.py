from __future__ import annotations

import json
import subprocess
from contextlib import chdir
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from deviate.cli import cli

runner = CliRunner()


def _seed_issues_jsonl(path: Path, records: list[dict]) -> Path:
    ledger = path / "specs" / "issues.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return ledger


def _make_issue(
    issue_id: str,
    type: str = "feature",
    title: str = "Test Issue",
    status: str = "DRAFT",
    source_file: str = "",
) -> dict:
    return {
        "issue_id": issue_id,
        "type": type,
        "title": title,
        "status": status,
        "source_file": source_file,
        "blocked_by": [],
        "coordinates_with": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class TestIssuesListJSON:
    """AC-006-01 (US-003-01): --json flag emits valid JSON array."""

    def test_issues_list_json(self, tmp_path: Path) -> None:
        records = [
            _make_issue("ISS-001", status="BACKLOG"),
            _make_issue(
                "ISS-002",
                status="SPECIFIED",
                source_file="specs/epic/issues/iss-002.md",
            ),
            _make_issue("ISS-003", status="COMPLETED"),
        ]
        _seed_issues_jsonl(tmp_path, records)
        with chdir(tmp_path):
            result = runner.invoke(cli, ["inspect", "issues", "list", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 3
        for entry in data:
            assert "issue_id" in entry
            assert "title" in entry
            assert "status" in entry
            assert "type" in entry


class TestIssuesListEmpty:
    """AC-006-01 (US-003-02): Empty ledger returns empty array."""

    def test_issues_list_empty_ledger(self, tmp_path: Path) -> None:
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir(parents=True, exist_ok=True)
        with chdir(tmp_path):
            result = runner.invoke(cli, ["inspect", "issues", "list", "--json"])

        assert result.exit_code == 0, result.output
        assert result.stdout.strip() == "[]"


class TestIssuesListOrphanClaim:
    """AC-006-02 (US-003-03): Orphan claim detection for SPECIFIED issues."""

    @patch("deviate.cli.inspect.detect_remote")
    @patch("deviate.cli.inspect.subprocess.run")
    def test_orphan_claim_detected(self, mock_run, mock_detect, tmp_path: Path) -> None:
        mock_detect.return_value = "origin"
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "ls-remote", "--heads", "origin", "feat/epic/iss-orphan"],
            returncode=0,
            stdout="",
            stderr="",
        )

        records = [
            _make_issue(
                "ISS-ORPHAN",
                status="SPECIFIED",
                source_file="specs/epic/issues/iss-orphan.md",
            ),
        ]
        _seed_issues_jsonl(tmp_path, records)
        with chdir(tmp_path):
            result = runner.invoke(cli, ["inspect", "issues", "list", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["orphan_claim"] is True

    @patch("deviate.cli.inspect.detect_remote")
    @patch("deviate.cli.inspect.subprocess.run")
    def test_orphan_claim_branch_exists(
        self, mock_run, mock_detect, tmp_path: Path
    ) -> None:
        mock_detect.return_value = "origin"
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "ls-remote", "--heads", "origin", "feat/epic/iss-existing"],
            returncode=0,
            stdout="abc123\trefs/heads/feat/epic/iss-existing\n",
            stderr="",
        )

        records = [
            _make_issue(
                "ISS-EXISTS",
                status="SPECIFIED",
                source_file="specs/epic/issues/iss-existing.md",
            ),
        ]
        _seed_issues_jsonl(tmp_path, records)
        with chdir(tmp_path):
            result = runner.invoke(cli, ["inspect", "issues", "list", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["orphan_claim"] is False

    @patch("deviate.cli.inspect.detect_remote")
    @patch("deviate.cli.inspect.subprocess.run")
    def test_orphan_claim_remote_unreachable(
        self, mock_run, mock_detect, tmp_path: Path
    ) -> None:
        mock_detect.return_value = "origin"
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="git ls-remote", timeout=30
        )

        records = [
            _make_issue(
                "ISS-UNREACH",
                status="SPECIFIED",
                source_file="specs/epic/issues/iss-unreach.md",
            ),
        ]
        _seed_issues_jsonl(tmp_path, records)
        with chdir(tmp_path):
            result = runner.invoke(cli, ["inspect", "issues", "list", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["orphan_claim"] is None


class TestIssuesListFilter:
    """AC-006-03 (US-003-06): --type and --status filters narrow results."""

    def test_issues_list_type_status_filter(self, tmp_path: Path) -> None:
        records = [
            _make_issue("ISS-F1", type="feature", status="BACKLOG"),
            _make_issue("ISS-F2", type="feature", status="COMPLETED"),
            _make_issue("ISS-B1", type="bug", status="BACKLOG"),
        ]
        _seed_issues_jsonl(tmp_path, records)
        with chdir(tmp_path):
            result = runner.invoke(
                cli,
                [
                    "inspect",
                    "issues",
                    "list",
                    "--type",
                    "feature",
                    "--status",
                    "BACKLOG",
                    "--json",
                ],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["issue_id"] == "ISS-F1"


class TestIssuesListMalformed:
    """AC-006-04 (US-003-07): Malformed JSONL line fails immediately."""

    def test_issues_list_malformed_jsonl_fails(self, tmp_path: Path) -> None:
        ledger = tmp_path / "specs" / "issues.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        valid = _make_issue("ISS-VALID", status="DRAFT")
        ledger.write_text(
            json.dumps(valid) + "\n{invalid json line\n",
            encoding="utf-8",
        )
        with chdir(tmp_path):
            result = runner.invoke(cli, ["inspect", "issues", "list", "--json"])

        assert result.exit_code != 0


class TestIssuesListCompletedPrecedence:
    """COMPLETED is terminal — a later SPECIFIED entry must not override it.

    Regression test for the bug where ``_deduplicate_issues`` surfaced the
    last record by file position, so a SPECIFIED entry appended after the
    COMPLETED write during a merge flow was returned instead of the
    authoritative COMPLETED status.
    """

    def test_deduplicate_issues_completed_over_specified(self, tmp_path: Path) -> None:
        # COMPLETED written first, SPECIFIED written second.
        records = [
            _make_issue(
                "ISS-002",
                status="COMPLETED",
                source_file="specs/epic/issues/iss-002.md",
            ),
            _make_issue(
                "ISS-002",
                status="SPECIFIED",
                source_file="specs/epic/issues/iss-002.md",
            ),
        ]
        _seed_issues_jsonl(tmp_path, records)
        with chdir(tmp_path):
            result = runner.invoke(cli, ["inspect", "issues", "list", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["issue_id"] == "ISS-002"
        assert data[0]["status"] == "COMPLETED"
        assert data[0]["orphan_claim"] is None

    def test_deduplicate_issues_last_wins_among_non_completed(
        self, tmp_path: Path
    ) -> None:
        # Among non-COMPLETED entries, last-by-file-position still wins.
        records = [
            _make_issue("ISS-A", status="BACKLOG"),
            _make_issue(
                "ISS-A",
                status="SPECIFIED",
                source_file="specs/epic/issues/iss-a.md",
            ),
        ]
        _seed_issues_jsonl(tmp_path, records)
        with chdir(tmp_path):
            result = runner.invoke(cli, ["inspect", "issues", "list", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["status"] == "SPECIFIED"


class TestTasksList:
    """US-004-TasksList: Tasks list commands."""

    def _seed_tasks_jsonl(self, path: Path, records: list[dict]) -> Path:
        ledger = path / "tasks.jsonl"
        with ledger.open("a", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        return ledger

    def test_tasks_list_status_filter(self, tmp_path: Path) -> None:
        self._seed_tasks_jsonl(
            tmp_path,
            [
                {
                    "id": "TSK-001-01",
                    "issue_id": "iss-001",
                    "description": "Task A",
                    "status": "PENDING",
                    "execution_mode": "TDD",
                },
                {
                    "id": "TSK-001-02",
                    "issue_id": "iss-001",
                    "description": "Task B",
                    "status": "IN_PROGRESS",
                    "execution_mode": "TDD",
                },
                {
                    "id": "TSK-001-03",
                    "issue_id": "iss-001",
                    "description": "Task C",
                    "status": "COMPLETED",
                    "execution_mode": "DIRECT",
                },
            ],
        )
        with chdir(tmp_path):
            result = runner.invoke(
                cli,
                ["inspect", "tasks", "list", "--status", "PENDING", "--json"],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["id"] == "TSK-001-01"
        assert data[0]["status"] == "PENDING"

    def test_tasks_list_json(self, tmp_path: Path) -> None:
        self._seed_tasks_jsonl(
            tmp_path,
            [
                {
                    "id": "TSK-002-01",
                    "issue_id": "iss-002",
                    "description": "Task X",
                    "status": "PENDING",
                    "execution_mode": "TDD",
                },
                {
                    "id": "TSK-002-02",
                    "issue_id": "iss-002",
                    "description": "Task Y",
                    "status": "GREEN",
                    "execution_mode": "TDD",
                },
                {
                    "id": "TSK-002-03",
                    "issue_id": "iss-002",
                    "description": "Task Z",
                    "status": "COMPLETED",
                    "execution_mode": "E2E",
                },
            ],
        )
        with chdir(tmp_path):
            result = runner.invoke(cli, ["inspect", "tasks", "list", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 3
        for entry in data:
            assert "id" in entry
            assert "issue_id" in entry
            assert "description" in entry
            assert "status" in entry

    def test_tasks_list_empty_ledger(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(cli, ["inspect", "tasks", "list", "--json"])

        assert result.exit_code == 0, result.output
        assert result.stdout.strip() == "[]"
