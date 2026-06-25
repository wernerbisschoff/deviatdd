from __future__ import annotations

import json
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.core.complexity import ClassificationResult

runner = CliRunner()


class TestAdhocPre:
    @patch("deviate.cli.adhoc.ComplexityGate.classify")
    def test_pre_low_complexity(self, mock_classify, tmp_path: Path) -> None:
        mock_classify.return_value = ClassificationResult(
            level="LOW", execution_mode="DIRECT"
        )
        with chdir(tmp_path):
            result = runner.invoke(cli, ["adhoc", "pre", "Fix typo"])

        assert result.exit_code == 0
        assert "DIRECT" in result.stdout

    @patch("deviate.cli.adhoc.ComplexityGate.classify")
    def test_pre_medium_complexity(self, mock_classify, tmp_path: Path) -> None:
        mock_classify.return_value = ClassificationResult(
            level="MEDIUM", execution_mode="DIRECT"
        )
        with chdir(tmp_path):
            result = runner.invoke(cli, ["adhoc", "pre", "Add form validation"])

        assert result.exit_code == 0
        assert "DIRECT" in result.stdout

    @patch("deviate.cli.adhoc.ComplexityGate.classify")
    def test_pre_high_complexity_rejected(self, mock_classify, tmp_path: Path) -> None:
        mock_classify.return_value = ClassificationResult(
            level="HIGH", execution_mode="TDD"
        )
        with chdir(tmp_path):
            result = runner.invoke(
                cli, ["adhoc", "pre", "Build auth system with OAuth, JWT, RBAC"]
            )

        assert result.exit_code != 0
        assert "COMPLEXITY_GATE_REJECTION" in result.stdout

    @patch("deviate.cli.adhoc.ComplexityGate.classify")
    def test_pre_high_complexity_skip_gates(
        self, mock_classify, tmp_path: Path
    ) -> None:
        mock_classify.return_value = ClassificationResult(
            level="HIGH", execution_mode="TDD"
        )
        with chdir(tmp_path):
            result = runner.invoke(
                cli,
                [
                    "adhoc",
                    "pre",
                    "--skip-gates",
                    "Build auth system with OAuth, JWT, RBAC",
                ],
            )

        assert result.exit_code == 0

    @patch("deviate.cli.adhoc.ComplexityGate.classify")
    def test_pre_default_flow_refs_is_empty(
        self, mock_classify, tmp_path: Path
    ) -> None:
        mock_classify.return_value = ClassificationResult(
            level="LOW", execution_mode="DIRECT"
        )
        with chdir(tmp_path):
            result = runner.invoke(cli, ["adhoc", "pre", "Fix typo"])

        assert result.exit_code == 0
        ledger = tmp_path / "specs" / "adhoc.jsonl"
        assert ledger.exists()
        records = [
            json.loads(line)
            for line in ledger.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(records) == 1
        assert records[0].get("flow_refs") == []

    @patch("deviate.cli.adhoc.ComplexityGate.classify")
    def test_pre_flow_ref_single_value_accepted(
        self, mock_classify, tmp_path: Path
    ) -> None:
        mock_classify.return_value = ClassificationResult(
            level="LOW", execution_mode="DIRECT"
        )
        with chdir(tmp_path):
            result = runner.invoke(
                cli,
                ["adhoc", "pre", "Touch flows", "--flow-ref", "FLOW-01"],
            )

        assert result.exit_code == 0
        ledger = tmp_path / "specs" / "adhoc.jsonl"
        records = [
            json.loads(line)
            for line in ledger.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(records) == 1
        assert records[0]["flow_refs"] == ["FLOW-01"]

    @patch("deviate.cli.adhoc.ComplexityGate.classify")
    def test_pre_flow_ref_comma_separated_parsed(
        self, mock_classify, tmp_path: Path
    ) -> None:
        mock_classify.return_value = ClassificationResult(
            level="LOW", execution_mode="DIRECT"
        )
        with chdir(tmp_path):
            result = runner.invoke(
                cli,
                [
                    "adhoc",
                    "pre",
                    "Touch multiple flows",
                    "--flow-ref",
                    "FLOW-01,FLOW-02",
                ],
            )

        assert result.exit_code == 0
        ledger = tmp_path / "specs" / "adhoc.jsonl"
        records = [
            json.loads(line)
            for line in ledger.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(records) == 1
        assert records[0]["flow_refs"] == ["FLOW-01", "FLOW-02"]

    @patch("deviate.cli.adhoc.ComplexityGate.classify")
    def test_pre_flow_ref_whitespace_normalized(
        self, mock_classify, tmp_path: Path
    ) -> None:
        mock_classify.return_value = ClassificationResult(
            level="LOW", execution_mode="DIRECT"
        )
        with chdir(tmp_path):
            result = runner.invoke(
                cli,
                [
                    "adhoc",
                    "pre",
                    "Touch flows with spaces",
                    "--flow-ref",
                    " FLOW-01 , FLOW-03 ",
                ],
            )

        assert result.exit_code == 0
        ledger = tmp_path / "specs" / "adhoc.jsonl"
        records = [
            json.loads(line)
            for line in ledger.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(records) == 1
        assert records[0]["flow_refs"] == ["FLOW-01", "FLOW-03"]

    @patch("deviate.cli.adhoc.ComplexityGate.classify")
    def test_pre_flow_ref_single_digit_rejected(
        self, mock_classify, tmp_path: Path
    ) -> None:
        mock_classify.return_value = ClassificationResult(
            level="LOW", execution_mode="DIRECT"
        )
        with chdir(tmp_path):
            result = runner.invoke(
                cli,
                ["adhoc", "pre", "Bad flow id", "--flow-ref", "FLOW-1"],
            )

        assert result.exit_code != 0
        assert "INVALID_FLOW_REF" in result.stdout

    @patch("deviate.cli.adhoc.ComplexityGate.classify")
    def test_pre_flow_ref_lowercase_rejected(
        self, mock_classify, tmp_path: Path
    ) -> None:
        mock_classify.return_value = ClassificationResult(
            level="LOW", execution_mode="DIRECT"
        )
        with chdir(tmp_path):
            result = runner.invoke(
                cli,
                ["adhoc", "pre", "Bad flow id", "--flow-ref", "flow-01"],
            )

        assert result.exit_code != 0
        assert "INVALID_FLOW_REF" in result.stdout

    @patch("deviate.cli.adhoc.ComplexityGate.classify")
    def test_pre_flow_ref_mixed_valid_and_invalid_rejected(
        self, mock_classify, tmp_path: Path
    ) -> None:
        mock_classify.return_value = ClassificationResult(
            level="LOW", execution_mode="DIRECT"
        )
        with chdir(tmp_path):
            result = runner.invoke(
                cli,
                [
                    "adhoc",
                    "pre",
                    "Mixed flow ids",
                    "--flow-ref",
                    "FLOW-01,FLOW-1",
                ],
            )

        assert result.exit_code != 0
        assert "INVALID_FLOW_REF" in result.stdout


class TestAdhocPost:
    def test_post_completes_record(self, tmp_path: Path) -> None:
        manifest_id = "adhoc-test-001"
        record = {
            "issue_id": manifest_id,
            "description": "Fix typo in README",
            "execution_mode": "DIRECT",
            "status": "PENDING",
        }
        adhoc_dir = tmp_path / "specs"
        adhoc_dir.mkdir(parents=True, exist_ok=True)
        adhoc_file = adhoc_dir / "adhoc.jsonl"
        adhoc_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

        with chdir(tmp_path):
            result = runner.invoke(cli, ["adhoc", "post", manifest_id])

        assert result.exit_code == 0
        assert "COMPLETED" in result.stdout

    def test_post_missing_manifest(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(cli, ["adhoc", "post", "nonexistent-id"])

        assert result.exit_code != 0
        assert "MANIFEST_NOT_FOUND" in result.stdout
