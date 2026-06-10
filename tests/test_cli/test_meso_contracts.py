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


class TestMesoContracts:
    TASKS_REQUIRED_FIELDS = frozenset(
        {
            "issue_id",
            "spec_path",
            "worktree_full",
            "constitution_path",
            "constitution_test_command",
            "constitution_lint_command",
            "timestamp",
            "status",
            "phase",
        }
    )

    PR_REQUIRED_FIELDS = frozenset(
        {
            "branch_name",
            "base_branch",
            "pr_title",
            "pr_body",
            "git_state",
            "timestamp",
            "status",
            "phase",
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
    def _setup_minimal_env(
        path: Path,
        session_phase: str = "IDLE",
        active_issue_id: str | None = None,
    ) -> None:
        dot_dir = path / ".deviate"
        dot_dir.mkdir(parents=True, exist_ok=True)
        session_data: dict[str, object] = {"current_phase": session_phase}
        if active_issue_id:
            session_data["active_issue_id"] = active_issue_id
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

    def test_tasks_pre_contract_has_required_fields(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(tmp_path, session_phase="SPECIFY")

            epic_dir = tmp_path / "specs" / "test-epic"
            epic_dir.mkdir(parents=True, exist_ok=True)
            (epic_dir / "spec.md").write_text("# Spec\n\nTest spec.\n")

            result = runner.invoke(cli, ["tasks", "pre"])
            assert result.exit_code == 0, result.output

            contract = self._extract_contract(result.output)

            for field in sorted(self.TASKS_REQUIRED_FIELDS):
                assert field in contract, (
                    f"Missing field in tasks pre contract: {field!r}"
                )

    def test_pr_pre_contract_has_required_fields(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(
                tmp_path, session_phase="TASKS", active_issue_id="ISS-001"
            )

            specs_dir = tmp_path / "specs"
            issue_record = {
                "issue_id": "ISS-001",
                "type": "feature",
                "title": "Test feature",
                "status": "BACKLOG",
                "source_file": "specs/test-epic/issues/ISS-001.md",
                "timestamp": "2026-01-01T00:00:00Z",
            }
            ledger_path = specs_dir / "issues.jsonl"
            ledger_path.write_text(json.dumps(issue_record) + "\n")

            result = runner.invoke(cli, ["pr", "pre"])
            assert result.exit_code == 0, result.output

            contract = self._extract_contract(result.output)

            for field in sorted(self.PR_REQUIRED_FIELDS):
                assert field in contract, f"Missing field in pr pre contract: {field!r}"

    def test_tasks_pre_dry_run_does_not_append_ledger(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(tmp_path, session_phase="SPECIFY")

            epic_dir = tmp_path / "specs" / "test-epic"
            epic_dir.mkdir(parents=True, exist_ok=True)
            (epic_dir / "spec.md").write_text("# Spec\n\nTest spec.\n")

            ledger_path = epic_dir / "tasks.jsonl"
            ledger_path.write_text("")

            result = runner.invoke(cli, ["tasks", "pre", "--dry-run"])

            assert result.exit_code == 0, result.output

            assert ledger_path.read_text() == ""

    def test_tasks_post_issue_id_resolves_correct_spec(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(
                tmp_path, session_phase="TASKS", active_issue_id="ISS-006"
            )

            specs_dir = tmp_path / "specs"
            issue_record = {
                "issue_id": "ISS-006",
                "type": "feature",
                "title": "Issue with explicit spec",
                "status": "BACKLOG",
                "source_file": "specs/test-epic/issues/ISS-006.md",
                "timestamp": "2026-01-01T00:00:00Z",
            }
            ledger_path = specs_dir / "issues.jsonl"
            ledger_path.write_text(json.dumps(issue_record) + "\n")

            (specs_dir / "test-epic" / "ISS-006").mkdir(parents=True, exist_ok=True)
            tasks_md = specs_dir / "test-epic" / "ISS-006" / "tasks.md"
            tasks_md.write_text("- [x] T001: Complete task\n  - Verification: pytest\n")

            ledger_path.parent.mkdir(parents=True, exist_ok=True)

            result = runner.invoke(cli, ["tasks", "post", "--issue-id", "ISS-006"])

            assert result.exit_code == 0, result.output
