from __future__ import annotations

import json
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

import pytest
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


class TestAdhocCodebaseStructure:
    """adhoc pre creates a codebase structure artifact from source files (TSK-008-06)."""

    @pytest.fixture
    def _mock_gate(self, request: pytest.FixtureRequest) -> None:
        """Mock ComplexityGate.classify to return MEDIUM/DIRECT."""
        patcher = patch("deviate.cli.adhoc.ComplexityGate.classify")
        mock = patcher.start()
        mock.return_value = ClassificationResult(
            level="MEDIUM", execution_mode="DIRECT"
        )
        request.addfinalizer(patcher.stop)

    @patch("deviate.cli.adhoc.ComplexityGate.classify")
    def test_artifact_created(self, mock_classify, tmp_git_repo: Path) -> None:
        """TSK-008-06: adhoc pre creates specs/adhoc/codebase_structure.md
        with ## Codebase Structure header when Python files exist in src/.
        """
        mock_classify.return_value = ClassificationResult(
            level="MEDIUM", execution_mode="DIRECT"
        )

        src_dir = tmp_git_repo / "src"
        src_dir.mkdir(parents=True)
        (src_dir / "greeter.py").write_text(
            "def hello(name: str) -> str:\n    return f'Hello, {name}!'\n"
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["adhoc", "pre", "Build a greeter CLI"])

        assert result.exit_code == 0

        artifact = tmp_git_repo / "specs" / "adhoc" / "codebase_structure.md"
        assert artifact.exists(), (
            "Expected codebase_structure.md to exist after adhoc pre"
        )
        content = artifact.read_text(encoding="utf-8")
        assert "## Codebase Structure" in content
        assert "greeter.py" in content

    @patch("deviate.cli.adhoc.ComplexityGate.classify")
    def test_artifact_contract_includes_path(
        self, mock_classify, tmp_git_repo: Path
    ) -> None:
        """TSK-008-06: adhoc pre contract includes codebase_structure_path key."""
        mock_classify.return_value = ClassificationResult(
            level="MEDIUM", execution_mode="DIRECT"
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["adhoc", "pre", "Build a greeter CLI"])

        assert result.exit_code == 0
        assert "codebase_structure_path" in result.stdout

    @patch("deviate.cli.adhoc.ComplexityGate.classify")
    def test_artifact_includes_file_signatures(
        self, mock_classify, tmp_git_repo: Path
    ) -> None:
        """TSK-008-06: codebase_structure.md contains function/class signatures."""
        mock_classify.return_value = ClassificationResult(
            level="MEDIUM", execution_mode="DIRECT"
        )

        src_dir = tmp_git_repo / "src"
        src_dir.mkdir(parents=True)
        (src_dir / "calculator.py").write_text(
            "def add(a: int, b: int) -> int:\n"
            "    return a + b\n"
            "\n\n"
            "class Calculator:\n"
            "    def multiply(self, x: int, y: int) -> int:\n"
            "        return x * y\n"
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["adhoc", "pre", "Build a calculator"])

        assert result.exit_code == 0

        artifact = tmp_git_repo / "specs" / "adhoc" / "codebase_structure.md"
        assert artifact.exists()
        content = artifact.read_text(encoding="utf-8")
        assert "add" in content
        assert "Calculator" in content
