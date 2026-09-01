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
    """US-004-TasksList: Tasks list commands.

    Tasks live under each issue directory as ``specs/<bucket>/<slug>/tasks.jsonl``
    (the per-issue append-only ledger). The buggy implementation looked at
    ``specs/tasks.jsonl``, which never exists — these tests exercise the
    real on-disk layout.
    """

    @staticmethod
    def _seed_issue(
        repo: Path,
        issue_id: str,
        bucket: str,
        slug: str,
    ) -> Path:
        source_file = f"specs/{bucket}/issues/{slug}.md"
        issues = repo / "specs" / "issues.jsonl"
        issues.parent.mkdir(parents=True, exist_ok=True)
        with issues.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "issue_id": issue_id,
                        "type": "feature",
                        "title": f"Test {issue_id}",
                        "status": "SPECIFIED",
                        "source_file": source_file,
                        "blocked_by": [],
                        "coordinates_with": [],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                + "\n"
            )
        tasks = repo / "specs" / bucket / slug / "tasks.jsonl"
        tasks.parent.mkdir(parents=True, exist_ok=True)
        return tasks

    @staticmethod
    def _seed_task(tasks_path: Path, record: dict) -> None:
        with tasks_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def test_tasks_list_status_filter(self, tmp_path: Path) -> None:
        tasks = self._seed_issue(
            tmp_path, "ISS-001", "002-embedder-vector-search", "001-embedder-registry"
        )
        for r in [
            {
                "id": "TSK-001-01",
                "issue_id": "ISS-001",
                "description": "Task A",
                "status": "PENDING",
                "execution_mode": "TDD",
            },
            {
                "id": "TSK-001-02",
                "issue_id": "ISS-001",
                "description": "Task B",
                "status": "IN_PROGRESS",
                "execution_mode": "TDD",
            },
            {
                "id": "TSK-001-03",
                "issue_id": "ISS-001",
                "description": "Task C",
                "status": "COMPLETED",
                "execution_mode": "DIRECT",
            },
        ]:
            self._seed_task(tasks, r)
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
        tasks = self._seed_issue(
            tmp_path,
            "ISS-002",
            "002-embedder-vector-search",
            "002-project-config-extensions",
        )
        for r in [
            {
                "id": "TSK-002-01",
                "issue_id": "ISS-002",
                "description": "Task X",
                "status": "PENDING",
                "execution_mode": "TDD",
            },
            {
                "id": "TSK-002-02",
                "issue_id": "ISS-002",
                "description": "Task Y",
                "status": "GREEN",
                "execution_mode": "TDD",
            },
            {
                "id": "TSK-002-03",
                "issue_id": "ISS-002",
                "description": "Task Z",
                "status": "COMPLETED",
                "execution_mode": "E2E",
            },
        ]:
            self._seed_task(tasks, r)
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

    def test_tasks_list_aggregates_across_multiple_issues(self, tmp_path: Path) -> None:
        """AC-006-Tasks-Aggregate: Tasks from multiple issues are aggregated.

        Reproduces the bug reported on the
        ``feat/002-embedder-vector-search/001-embedder-registry`` worktree: a
        tasks ledger at the per-issue path was not visible to
        ``deviate inspect tasks list``.

        Status precedence mirrors ``TestIssuesListCompletedPrecedence``:
        ``COMPLETED`` is terminal — once captured, no later non-``COMPLETED``
        transition (e.g. a ``GREEN`` written after the ``COMPLETED`` during a
        merge flow) may override it. Among non-terminal entries, the last by
        file position wins. Aggregation is per-task across all issues.
        """
        tasks_019 = self._seed_issue(
            tmp_path, "ISS-019", "002-embedder-vector-search", "001-embedder-registry"
        )
        tasks_020 = self._seed_issue(
            tmp_path,
            "ISS-020",
            "002-embedder-vector-search",
            "002-project-config-extensions",
        )
        tasks_adhoc = self._seed_issue(tmp_path, "ISS-021", "adhoc", "007-graphite-cli")
        # TSK-019-01 mid-RG-R: RED then GREEN. Latest non-terminal wins → GREEN.
        self._seed_task(
            tasks_019,
            {
                "id": "TSK-019-01",
                "issue_id": "ISS-019",
                "description": "Declare EmbedderModeConfig",
                "status": "RED",
                "execution_mode": "TDD",
            },
        )
        self._seed_task(
            tasks_019,
            {
                "id": "TSK-019-01",
                "issue_id": "ISS-019",
                "description": "Declare EmbedderModeConfig",
                "status": "GREEN",
                "execution_mode": "TDD",
            },
        )
        self._seed_task(
            tasks_020,
            {
                "id": "TSK-020-01",
                "issue_id": "ISS-020",
                "description": "Extend ProjectConfig",
                "status": "PENDING",
                "execution_mode": "TDD",
            },
        )
        # TSK-021-01: COMPLETED first, then a stray GREEN must NOT downgrade it.
        self._seed_task(
            tasks_adhoc,
            {
                "id": "TSK-021-01",
                "issue_id": "ISS-021",
                "description": "Wire Graphite",
                "status": "COMPLETED",
                "execution_mode": "DIRECT",
            },
        )
        self._seed_task(
            tasks_adhoc,
            {
                "id": "TSK-021-01",
                "issue_id": "ISS-021",
                "description": "Wire Graphite",
                "status": "GREEN",
                "execution_mode": "TDD",
            },
        )
        with chdir(tmp_path):
            result = runner.invoke(cli, ["inspect", "tasks", "list", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        ids = {entry["id"] for entry in data}
        assert ids == {"TSK-019-01", "TSK-020-01", "TSK-021-01"}
        by_id = {entry["id"]: entry for entry in data}
        # Non-terminal: latest entry (GREEN) wins.
        assert by_id["TSK-019-01"]["status"] == "GREEN"
        # Terminal COMPLETED is sticky across the ledger even if a later
        # non-COMPLETED entry was appended.
        assert by_id["TSK-021-01"]["status"] == "COMPLETED"

    def test_tasks_list_ignores_legacy_top_level_ledger(self, tmp_path: Path) -> None:
        """Pinning: a stray top-level ``specs/tasks.jsonl`` is ignored.

        The legacy buggy code path read ``specs/tasks.jsonl``. That file does
        not exist in any real repo; if a user drops one there by mistake the
        inspect command MUST NOT pick it up. Aggregation is sourced from the
        per-issue ``tasks.jsonl`` files only.
        """
        legacy = tmp_path / "specs" / "tasks.jsonl"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(
            json.dumps(
                {
                    "id": "TSK-LEGACY-01",
                    "issue_id": "ISS-XXX",
                    "description": "stale",
                    "status": "PENDING",
                    "execution_mode": "TDD",
                }
            )
            + "\n"
        )
        with chdir(tmp_path):
            result = runner.invoke(cli, ["inspect", "tasks", "list", "--json"])

        assert result.exit_code == 0, result.output
        assert result.stdout.strip() == "[]"


class TestInspectById:
    def test_issues_show_accepts_issue_id(self, tmp_path: Path) -> None:
        _seed_issues_jsonl(tmp_path, [_make_issue("ISS-013", status="BACKLOG")])
        with chdir(tmp_path):
            result = runner.invoke(
                cli, ["inspect", "issues", "show", "ISS-013", "--json"]
            )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["issue_id"] == "ISS-013"

    def test_tasks_show_accepts_task_id(self, tmp_path: Path) -> None:
        # Per-issue tasks ledger at the canonical on-disk location.
        bucket = "001-gloss-v1-mvp"
        slug = "011-watcher-dispatch-wire"
        issues = tmp_path / "specs" / "issues.jsonl"
        issues.parent.mkdir(parents=True, exist_ok=True)
        issues.write_text(
            json.dumps(
                {
                    "issue_id": "ISS-013",
                    "type": "feature",
                    "title": "Target",
                    "status": "SPECIFIED",
                    "source_file": f"specs/{bucket}/issues/{slug}.md",
                    "blocked_by": [],
                    "coordinates_with": [],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        tasks = tmp_path / "specs" / bucket / slug / "tasks.jsonl"
        tasks.parent.mkdir(parents=True, exist_ok=True)
        tasks.write_text(
            json.dumps(
                {
                    "id": "TSK-013-02",
                    "issue_id": "ISS-013",
                    "description": "Target",
                    "status": "PENDING",
                    "execution_mode": "TDD",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        with chdir(tmp_path):
            result = runner.invoke(
                cli, ["inspect", "tasks", "show", "TSK-013-02", "--json"]
            )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["id"] == "TSK-013-02"

    def test_tasks_show_prints_persisted_evidence_when_present(
        self, tmp_path: Path
    ) -> None:
        """GH-84: inspect tasks show displays COMPLETED evidence after session is gone."""
        bucket = "adhoc"
        slug = "084-persist-judge-evidence"
        issues = tmp_path / "specs" / "issues.jsonl"
        issues.parent.mkdir(parents=True, exist_ok=True)
        issues.write_text(
            json.dumps(
                {
                    "issue_id": "ISS-ADH-084",
                    "type": "feature",
                    "title": "Persist evidence",
                    "status": "SPECIFIED",
                    "source_file": f"specs/{bucket}/issues/{slug}.md",
                    "blocked_by": [],
                    "coordinates_with": [],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        tasks = tmp_path / "specs" / bucket / slug / "tasks.jsonl"
        tasks.parent.mkdir(parents=True, exist_ok=True)
        tasks.write_text(
            json.dumps(
                {
                    "id": "TSK-084-01",
                    "issue_id": "ISS-ADH-084",
                    "description": "Completed with evidence",
                    "status": "COMPLETED",
                    "execution_mode": "TDD",
                    "evidence": {
                        "items": [
                            {
                                "ac": "AC-PLAN-001",
                                "test_path": "tests/example.py",
                                "test_quote": "assert increment(2) == 3",
                                "impl_path": "src/example.py",
                                "impl_quote": "return n + 1",
                            }
                        ],
                        "red": "aaa111",
                        "green": "bbb222",
                        "head": "bbb222",
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        with chdir(tmp_path):
            result = runner.invoke(
                cli, ["inspect", "tasks", "show", "TSK-084-01", "--json"]
            )
        assert result.exit_code == 0, result.output
        shown = json.loads(result.stdout)
        evidence = shown["evidence"]
        items = evidence["items"] if isinstance(evidence, dict) else evidence
        assert items[0]["ac"] == "AC-PLAN-001"
        assert items[0]["test_quote"] == "assert increment(2) == 3"
        if isinstance(evidence, dict):
            assert evidence["red"] == "aaa111"
            assert evidence["head"] == "bbb222"
