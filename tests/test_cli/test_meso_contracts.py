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
            self._setup_minimal_env(
                tmp_path, session_phase="SPECIFY", active_issue_id="ISS-TEST-001"
            )

            specs_dir = tmp_path / "specs"
            issue_record = {
                "issue_id": "ISS-TEST-001",
                "type": "feature",
                "title": "Test",
                "status": "BACKLOG",
                "source_file": "specs/test-epic/issues/ISS-TEST-001.md",
                "timestamp": "2026-01-01T00:00:00Z",
            }
            (specs_dir / "issues.jsonl").write_text(json.dumps(issue_record) + "\n")

            issue_dir = specs_dir / "test-epic" / "issues"
            issue_dir.mkdir(parents=True, exist_ok=True)
            (issue_dir / "ISS-TEST-001.md").write_text("# Spec\n\nTest spec.\n")

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
                tmp_path, session_phase="TASKS", active_issue_id="ISS-001-001"
            )

            specs_dir = tmp_path / "specs"
            issue_record = {
                "issue_id": "ISS-001-001",
                "type": "feature",
                "title": "Test feature",
                "status": "BACKLOG",
                "source_file": "specs/test-epic/issues/ISS-001-001.md",
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
            self._setup_minimal_env(
                tmp_path, session_phase="SPECIFY", active_issue_id="ISS-TEST-002"
            )

            specs_dir = tmp_path / "specs"
            issue_record = {
                "issue_id": "ISS-TEST-002",
                "type": "feature",
                "title": "Test",
                "status": "BACKLOG",
                "source_file": "specs/test-epic/issues/ISS-TEST-002.md",
                "timestamp": "2026-01-01T00:00:00Z",
            }
            (specs_dir / "issues.jsonl").write_text(json.dumps(issue_record) + "\n")

            issue_dir = specs_dir / "test-epic" / "issues"
            issue_dir.mkdir(parents=True, exist_ok=True)
            (issue_dir / "ISS-TEST-002.md").write_text("# Spec\n\nTest spec.\n")

            epic_dir = tmp_path / "specs" / "test-epic"
            epic_dir.mkdir(parents=True, exist_ok=True)

            ledger_path = epic_dir / "tasks.jsonl"
            ledger_path.write_text("")

            result = runner.invoke(cli, ["tasks", "pre", "--dry-run"])

            assert result.exit_code == 0, result.output

            assert ledger_path.read_text() == ""

    def test_tasks_post_issue_id_resolves_correct_spec(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(
                tmp_path, session_phase="TASKS", active_issue_id="ISS-001-006"
            )

            specs_dir = tmp_path / "specs"
            issue_record = {
                "issue_id": "ISS-001-006",
                "type": "feature",
                "title": "Issue with explicit spec",
                "status": "BACKLOG",
                "source_file": "specs/test-epic/issues/ISS-001-006.md",
                "timestamp": "2026-01-01T00:00:00Z",
            }
            ledger_path = specs_dir / "issues.jsonl"
            ledger_path.write_text(json.dumps(issue_record) + "\n")

            (specs_dir / "test-epic" / "ISS-001-006").mkdir(parents=True, exist_ok=True)
            tasks_md = specs_dir / "test-epic" / "ISS-001-006" / "tasks.md"
            tasks_md.write_text("- [x] T001: Complete task\n  - Verification: pytest\n")

            ledger_path.parent.mkdir(parents=True, exist_ok=True)

            result = runner.invoke(cli, ["tasks", "post", "--issue-id", "ISS-001-006"])

            assert result.exit_code == 0, result.output

    def _write_issue_tasks(
        self, tmp_path: Path, issue_id: str, tasks_body: str
    ) -> Path:
        self._setup_git_repo(tmp_path)
        self._setup_minimal_env(
            tmp_path, session_phase="TASKS", active_issue_id=issue_id
        )
        specs_dir = tmp_path / "specs"
        issue_record = {
            "issue_id": issue_id,
            "type": "feature",
            "title": "Layer stamp issue",
            "status": "BACKLOG",
            "source_file": f"specs/test-epic/issues/{issue_id}.md",
            "timestamp": "2026-01-01T00:00:00Z",
        }
        (specs_dir / "issues.jsonl").write_text(json.dumps(issue_record) + "\n")
        (specs_dir / "test-epic" / issue_id).mkdir(parents=True, exist_ok=True)
        tasks_md = specs_dir / "test-epic" / issue_id / "tasks.md"
        tasks_md.write_text(tasks_body)
        return tasks_md

    def test_tasks_post_rejects_mixed_layer_tdd_card(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            tasks_md = self._write_issue_tasks(
                tmp_path,
                "ISS-001-006",
                "# Tasks\n\n"
                "- TSK-001-02: Crypto withdrawal\n"
                "  - **Type**: Feature_Batch\n"
                "  - **Mode**: TDD\n"
                "  - **Test Strategy**: unit\n"
                "  - **Verification**: `pytest tests/unit/test_crypto_withdrawal.py "
                "tests/integration/test_crypto_withdrawal.py`\n"
                "  - **Files**:\n"
                "    - `src/wallet/withdraw.py`\n"
                "    - `tests/unit/test_crypto_withdrawal.py`\n"
                "    - `tests/integration/test_crypto_withdrawal.py`\n",
            )
            before = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=tmp_path,
                env=_git_env(),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            result = runner.invoke(cli, ["tasks", "post", "--issue-id", "ISS-001-006"])

            assert result.exit_code != 0
            assert "MIXED_TEST_LAYER" in result.output
            assert "TSK-001-02" in result.output
            after = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=tmp_path,
                env=_git_env(),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            assert after == before
            log = subprocess.run(
                ["git", "log", "--oneline"],
                cwd=tmp_path,
                env=_git_env(),
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            assert "create tasks.md" not in log
            session = json.loads((tmp_path / ".deviate" / "session.json").read_text())
            assert session["current_phase"] == "TASKS"
            assert tasks_md.exists()

    def test_tasks_post_force_still_rejects_mixed_layer_card(
        self, tmp_path: Path
    ) -> None:
        with chdir(tmp_path):
            self._write_issue_tasks(
                tmp_path,
                "ISS-001-006",
                "# Tasks\n\n"
                "- TSK-001-02: Mixed stamps\n"
                "  - **Type**: Feature_Batch\n"
                "  - **Mode**: TDD\n"
                "  - **Test Strategy**: unit/integration\n"
                "  - **Verification**: `mise unit`\n"
                "  - **Files**:\n"
                "    - `src/wallet/withdraw.py`\n",
            )

            result = runner.invoke(
                cli, ["tasks", "post", "--force", "--issue-id", "ISS-001-006"]
            )

            assert result.exit_code != 0
            assert "MIXED_TEST_LAYER" in result.output

    def test_tasks_post_commits_single_layer_tdd_card(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            self._write_issue_tasks(
                tmp_path,
                "ISS-001-006",
                "# Tasks\n\n"
                "- TSK-001-01: Withdrawal unit contract\n"
                "  - **Type**: Feature_Batch\n"
                "  - **Mode**: TDD\n"
                "  - **Test Strategy**: unit\n"
                "  - **Verification**: `mise unit`\n"
                "  - **Files**:\n"
                "    - `src/wallet/withdraw.py`\n"
                "    - `tests/unit/test_crypto_withdrawal.py`\n"
                "  - **Details**:\n"
                "    - **Red**: Write failing unit tests in `tests/unit/` — "
                "forbid `tests/integration` / e2e in this RED.\n",
            )

            result = runner.invoke(cli, ["tasks", "post", "--issue-id", "ISS-001-006"])

            assert result.exit_code == 0, result.output
            assert "MIXED_TEST_LAYER" not in result.output
            log = subprocess.run(
                ["git", "log", "-1", "--oneline"],
                cwd=tmp_path,
                env=_git_env(),
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            assert "create tasks.md" in log
            session = json.loads((tmp_path / ".deviate" / "session.json").read_text())
            assert session["current_phase"] == "IDLE"

    def test_tasks_pre_resolves_issue_from_branch(self, tmp_path: Path) -> None:
        """`tasks pre` derives the issue from the feature branch when the
        session has no active_issue_id."""
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(tmp_path, session_phase="SPECIFY")

            specs_dir = tmp_path / "specs"
            issue_record = {
                "issue_id": "ISS-BR-021",
                "type": "feature",
                "title": "Branch-resolved issue",
                "status": "BACKLOG",
                "source_file": "specs/002-embedder-vector-search/issues/003-config-embedder-cli.md",
                "timestamp": "2026-01-01T00:00:00Z",
            }
            (specs_dir / "issues.jsonl").write_text(json.dumps(issue_record) + "\n")

            issue_file = specs_dir / "002-embedder-vector-search" / "issues"
            issue_file.mkdir(parents=True, exist_ok=True)
            (issue_file / "003-config-embedder-cli.md").write_text(
                "# Spec", encoding="utf-8"
            )

            # plan.md present so tasks pre does not gate on PLAN_NOT_FOUND.
            feature_dir = (
                specs_dir / "002-embedder-vector-search" / "003-config-embedder-cli"
            )
            feature_dir.mkdir(parents=True, exist_ok=True)
            (feature_dir / "plan.md").write_text("# Plan", encoding="utf-8")

            subprocess.run(
                [
                    "git",
                    "checkout",
                    "-b",
                    "feat/002-embedder-vector-search/003-config-embedder-cli",
                ],
                cwd=tmp_path,
                env=_git_env(),
                check=True,
                capture_output=True,
            )

            result = runner.invoke(cli, ["tasks", "pre"])
            assert result.exit_code == 0, result.output

            contract = self._extract_contract(result.output)
            assert contract.get("issue_id") == "ISS-BR-021", (
                "tasks pre must resolve the issue from the feature branch when "
                f"the session is empty; got issue_id={contract.get('issue_id')!r}"
            )
            assert contract.get("tasks_target", "").endswith(
                "002-embedder-vector-search/003-config-embedder-cli/tasks.md"
            )

    @staticmethod
    def _contract_plan(mode_line: str | None) -> str:
        """Build a plan.md whose single AC-PLAN scenario omits or keeps the mode."""
        lines = [
            "## Acceptance Contract",
            "",
            "**Scenario AC-PLAN-001: A valid criterion**",
            "**Source Outline**: AO-001",
            "**Upstream Traceability**: US-005-01, FR-005-01, AC-005-01-01",
            "**Current-Code Evidence**: src/demo.py:run",
            "**Given**: A configured repository.",
            "**When**: The meso pipeline validates the contract.",
            "**Then**: The criterion is enforceable.",
        ]
        if mode_line is not None:
            lines.append(mode_line)
        return "\n".join(lines)

    def _invoke_tasks_pre_with_plan(self, tmp_path: Path, plan_text: str):
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(
                tmp_path, session_phase="SPECIFY", active_issue_id="ISS-TEST-001"
            )

            specs_dir = tmp_path / "specs"
            issue_record = {
                "issue_id": "ISS-TEST-001",
                "type": "feature",
                "title": "Test",
                "status": "BACKLOG",
                "source_file": "specs/test-epic/issues/ISS-TEST-001.md",
                "timestamp": "2026-01-01T00:00:00Z",
            }
            (specs_dir / "issues.jsonl").write_text(json.dumps(issue_record) + "\n")

            issue_dir = specs_dir / "test-epic" / "issues"
            issue_dir.mkdir(parents=True, exist_ok=True)
            (issue_dir / "ISS-TEST-001.md").write_text("# Spec\n\nTest spec.\n")

            feature_dir = specs_dir / "test-epic" / "ISS-TEST-001"
            feature_dir.mkdir(parents=True, exist_ok=True)
            (feature_dir / "plan.md").write_text(plan_text)

            return runner.invoke(cli, ["tasks", "pre"])

    def test_tasks_pre_repairs_missing_verification_mode(self, tmp_path: Path) -> None:
        plan_text = self._contract_plan(mode_line=None)
        result = self._invoke_tasks_pre_with_plan(tmp_path, plan_text)

        assert result.exit_code == 0, result.output
        contract = self._extract_contract(result.output)
        assert contract["status"] == "READY", result.output
        assert "PLAN_MODE_REPAIR" in result.output
        plan_path = tmp_path / "specs" / "test-epic" / "ISS-TEST-001" / "plan.md"
        repaired = plan_path.read_text(encoding="utf-8")
        assert "**Verification Mode**: automated" in repaired

    def test_tasks_pre_blocks_on_illegal_verification_mode(
        self, tmp_path: Path
    ) -> None:
        plan_text = self._contract_plan(mode_line="**Verification Mode**: soon")
        result = self._invoke_tasks_pre_with_plan(tmp_path, plan_text)

        assert result.exit_code == 0, result.output
        contract = self._extract_contract(result.output)
        assert contract["status"] == "PLAN_ACCEPTANCE_CONTRACT_INVALID", result.output
        flat_output = " ".join(result.output.split())
        assert (
            "AC-PLAN-001: invalid Verification Mode 'soon'; "
            "expected one of automated|manual|deferred"
        ) in flat_output

    def test_tasks_pre_passes_on_valid_verification_mode(self, tmp_path: Path) -> None:
        plan_text = self._contract_plan(mode_line="**Verification Mode**: automated")
        result = self._invoke_tasks_pre_with_plan(tmp_path, plan_text)

        assert result.exit_code == 0, result.output
        contract = self._extract_contract(result.output)
        assert contract["status"] == "READY", result.output
        assert "export_plan" not in contract
