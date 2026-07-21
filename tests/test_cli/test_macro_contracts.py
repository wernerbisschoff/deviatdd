from __future__ import annotations

import json
import os
import subprocess
from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli

runner = CliRunner()


def _git_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


class TestMacroContracts:
    EXPLORE_REQUIRED_FIELDS = frozenset(
        {
            "repo_root",
            "git_branch",
            "constitution_path",
            "test_cmd",
            "lint_cmd",
            "type_check_cmd",
            "epic_id",
            "is_greenfield",
            "timestamp",
            "status",
            "phase",
            "issue_id",
            "feature_bucket",
            "feature_dir",
            "explore_path",
        }
    )

    RESEARCH_REQUIRED_FIELDS = frozenset(
        {
            "repo_root",
            "git_branch",
            "constitution_path",
            "test_cmd",
            "lint_cmd",
            "type_check_cmd",
            "is_greenfield",
            "timestamp",
            "status",
            "phase",
            "issue_id",
            "feature_bucket",
            "explore_path",
            "design_target",
            "data_model_target",
        }
    )

    PRD_REQUIRED_FIELDS = frozenset(
        {
            "repo_root",
            "git_branch",
            "constitution_path",
            "test_cmd",
            "lint_cmd",
            "type_check_cmd",
            "timestamp",
            "status",
            "phase",
            "issue_id",
            "feature_bucket",
            "design_path",
            "data_model_path",
            "explore_md_path",
            "plan_target",
        }
    )

    SHARD_REQUIRED_FIELDS = frozenset(
        {
            "repo_root",
            "git_branch",
            "constitution_path",
            "issues_dir",
            "plan_target",
            "dry_run",
            "timestamp",
            "status",
            "phase",
            "issue_id",
            "prd_path",
            "shard_count",
        }
    )

    @staticmethod
    def _setup_git_repo(path: Path) -> None:
        subprocess.run(
            ["git", "init"], cwd=path, env=_git_env(), check=True, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.email", "runner@test.local"],
            cwd=path,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test Runner"],
            cwd=path,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "initial"],
            cwd=path,
            env=_git_env(),
            check=True,
            capture_output=True,
        )

    @staticmethod
    def _setup_minimal_env(path: Path, session_phase: str = "IDLE") -> None:
        dot_dir = path / ".deviate"
        dot_dir.mkdir(parents=True, exist_ok=True)
        session_data = {"current_phase": session_phase}
        (dot_dir / "session.json").write_text(json.dumps(session_data))

        specs_dir = path / "specs"
        specs_dir.mkdir(parents=True, exist_ok=True)
        constitution = (
            "# Project Constitution\n\n"
            "## [TESTING_PROTOCOLS]\n"
            "- `TEST_COMMAND`: pytest\n"
            "- `LINT_COMMAND`: ruff check .\n"
            "- `TYPE_CHECK_COMMAND`: (none)\n"
        )
        (specs_dir / "constitution.md").write_text(constitution)

    @staticmethod
    def _extract_contract(output: str) -> dict:
        start = output.index("{")
        end = output.rindex("}") + 1
        return json.loads(output[start:end])

    def test_explore_pre_contract_has_all_fields(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(tmp_path, session_phase="IDLE")

            result = runner.invoke(
                cli, ["explore", "pre", "test problem", "--slug", "test-feature"]
            )
            assert result.exit_code == 0, result.output

            contract = self._extract_contract(result.output)

            for field in sorted(self.EXPLORE_REQUIRED_FIELDS):
                assert field in contract, (
                    f"Missing field in explore pre contract: {field!r}"
                )

    def test_research_pre_contract_has_all_fields(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(tmp_path, session_phase="EXPLORE")

            explore_dir = tmp_path / "specs" / "explore"
            explore_dir.mkdir(parents=True, exist_ok=True)
            (explore_dir / "test-feature.md").write_text(
                "# Explore\n\nDiscovered facts.\n"
            )

            result = runner.invoke(cli, ["research", "pre", "--slug", "test-feature"])
            assert result.exit_code == 0, result.output

            contract = self._extract_contract(result.output)

            for field in sorted(self.RESEARCH_REQUIRED_FIELDS):
                assert field in contract, (
                    f"Missing field in research pre contract: {field!r}"
                )

    def test_prd_pre_contract_has_all_fields(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(tmp_path, session_phase="RESEARCH")

            epic_dir = tmp_path / "specs" / "test-epic"
            epic_dir.mkdir(parents=True, exist_ok=True)
            (epic_dir / "explore.md").write_text("# Explore\n\nFacts.\n")
            (epic_dir / "design.md").write_text("# Design\n\nDesign details.\n")
            (epic_dir / "data-model.md").write_text("# Data Model\n\nSchema details.\n")

            result = runner.invoke(cli, ["prd", "pre"])
            assert result.exit_code == 0, result.output

            contract = self._extract_contract(result.output)

            for field in sorted(self.PRD_REQUIRED_FIELDS):
                assert field in contract, (
                    f"Missing field in prd pre contract: {field!r}"
                )

    def test_shard_pre_contract_has_all_fields(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(tmp_path, session_phase="PRD")

            epic_dir = tmp_path / "specs" / "test-epic"
            epic_dir.mkdir(parents=True, exist_ok=True)
            (epic_dir / "explore.md").write_text("# Explore\n\nFacts.\n")
            (epic_dir / "design.md").write_text("# Design\n\nDesign details.\n")
            (epic_dir / "data-model.md").write_text("# Data Model\n\nSchema details.\n")
            (epic_dir / "prd.md").write_text("# PRD\n\nPRD details.\n")

            result = runner.invoke(cli, ["shard", "pre"])
            assert result.exit_code == 0, result.output

            contract = self._extract_contract(result.output)

            for field in sorted(self.SHARD_REQUIRED_FIELDS):
                assert field in contract, (
                    f"Missing field in shard pre contract: {field!r}"
                )

    def test_prd_pre_dry_run_does_not_create_artifacts(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(tmp_path, session_phase="RESEARCH")

            epic_dir = tmp_path / "specs" / "test-epic"
            epic_dir.mkdir(parents=True, exist_ok=True)
            (epic_dir / "explore.md").write_text("# Explore\n\nFacts.\n")
            (epic_dir / "design.md").write_text("# Design\n\nDesign details.\n")
            (epic_dir / "data-model.md").write_text("# Data Model\n\nSchema details.\n")

            session_path = tmp_path / ".deviate" / "session.json"
            before = json.loads(session_path.read_text())
            assert before["current_phase"] == "RESEARCH"

            result = runner.invoke(cli, ["prd", "pre", "--dry-run"])

            assert result.exit_code == 0, result.output

            session_after = json.loads(session_path.read_text())
            assert session_after["current_phase"] == "RESEARCH"

    def test_shard_pre_dry_run_does_not_create_issues(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(tmp_path, session_phase="PRD")

            epic_dir = tmp_path / "specs" / "test-epic"
            epic_dir.mkdir(parents=True, exist_ok=True)
            (epic_dir / "explore.md").write_text("# Explore\n\nFacts.\n")
            (epic_dir / "design.md").write_text("# Design\n\nDesign details.\n")
            (epic_dir / "data-model.md").write_text("# Data Model\n\nSchema details.\n")
            (epic_dir / "prd.md").write_text("# PRD\n\nPRD details.\n")

            ledger_path = tmp_path / "specs" / "issues.jsonl"
            (tmp_path / "specs").mkdir(parents=True, exist_ok=True)
            ledger_path.write_text("")

            result = runner.invoke(cli, ["shard", "pre", "--dry-run"])

            assert result.exit_code == 0, result.output

            assert ledger_path.read_text() == ""
