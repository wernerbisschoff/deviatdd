from __future__ import annotations

import pytest

import json
import os
import re
import subprocess
from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.cli.meso import _plan_pre

runner = CliRunner()
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _plain(text: str) -> str:
    return _ANSI_RE.sub("", text)


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
            output = _plain(result.output)
            assert "MIXED_TEST_LAYER" in output
            assert "TSK-001-02" in output
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
            assert "MIXED_TEST_LAYER" in _plain(result.output)

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

    def test_tasks_pre_rejects_missing_verification_mode(self, tmp_path: Path) -> None:
        plan_text = self._contract_plan(mode_line=None)
        result = self._invoke_tasks_pre_with_plan(tmp_path, plan_text)

        assert result.exit_code == 0, result.output
        contract = self._extract_contract(result.output)
        assert contract["status"] == "PLAN_ACCEPTANCE_CONTRACT_INVALID", result.output
        assert "AC-PLAN-001: missing Verification Mode" in result.output
        assert "PLAN_MODE_REPAIR" not in result.output
        plan_path = tmp_path / "specs" / "test-epic" / "ISS-TEST-001" / "plan.md"
        assert "**Verification Mode**: automated" not in plan_path.read_text(
            encoding="utf-8"
        )

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


TRACEABLE_ISSUE_BODY = """
## User Stories Ledger

- **US-055-01**: As a plan agent, I want fail fast. *(Ref: FR-ADHOC-055)*

## Upstream Requirement Tracing

- **Requirements Tokens**: `FR-ADHOC-055`
- **Acceptance Criteria Tokens**: `AC-ADHOC-055-01`

## Acceptance Outline

- **AO-055-01** *(Ref: AC-ADHOC-055-01, US-055-01)*: traceable issue passes.
"""


class TestPlanPreTraceabilityGate:
    @staticmethod
    def _setup_plan_env(path: Path, issue_id: str, body: str | None) -> None:
        TestMesoContracts._setup_git_repo(path)
        TestMesoContracts._setup_minimal_env(
            path, session_phase="PLAN", active_issue_id=issue_id
        )
        specs_dir = path / "specs"
        record = {
            "issue_id": issue_id,
            "type": "feature",
            "title": "Traceability gate",
            "status": "BACKLOG",
            "source_file": f"specs/adhoc/issues/{issue_id}.md",
            "timestamp": "2026-01-01T00:00:00Z",
        }
        (specs_dir / "issues.jsonl").write_text(json.dumps(record) + "\n")
        if body is not None:
            issue_dir = specs_dir / "adhoc" / "issues"
            issue_dir.mkdir(parents=True, exist_ok=True)
            (issue_dir / f"{issue_id}.md").write_text(body, encoding="utf-8")

    @staticmethod
    def _invoke_plan_pre(tmp_path: Path, issue_id: str, capsys) -> dict:
        with chdir(tmp_path):
            _plan_pre(issue_id=issue_id, skip_auto_claim=True)
            out, _ = capsys.readouterr()
        start = out.index("{")
        end = out.rindex("}") + 1
        return json.loads(out[start:end])

    @pytest.mark.behavioral
    def test_plan_pre_not_ready_names_missing_fields(self, tmp_path, capsys) -> None:
        self._setup_plan_env(tmp_path, "ISS-ADH-055", "# Spec\n\nNo sections.\n")
        contract = self._invoke_plan_pre(tmp_path, "ISS-ADH-055", capsys)
        assert contract["status"] == "NOT_READY"
        missing = " ".join(contract["missing_fields"])
        assert "User Stories Ledger" in missing
        assert "Upstream Requirement Tracing" in missing
        assert "Acceptance Outline" in missing
        assert "repair" in contract["repair_hint"].lower()

    @pytest.mark.behavioral
    def test_plan_pre_ready_for_traceable_issue(self, tmp_path, capsys) -> None:
        self._setup_plan_env(tmp_path, "ISS-ADH-055", TRACEABLE_ISSUE_BODY)
        contract = self._invoke_plan_pre(tmp_path, "ISS-ADH-055", capsys)
        assert contract["status"] == "READY"
        assert contract["spec_path"].endswith("specs/adhoc/issues/ISS-ADH-055.md")
        assert contract["plan_target"].endswith("specs/adhoc/ISS-ADH-055/plan.md")

    @pytest.mark.behavioral
    def test_plan_pre_partial_names_only_missing_subset(self, tmp_path, capsys) -> None:
        body = "## User Stories Ledger\n\n- **US-055-01**: present.\n"
        self._setup_plan_env(tmp_path, "ISS-ADH-055", body)
        contract = self._invoke_plan_pre(tmp_path, "ISS-ADH-055", capsys)
        assert contract["status"] == "NOT_READY"
        missing = " ".join(contract["missing_fields"])
        assert "User Stories Ledger" not in missing
        assert "Acceptance Outline" in missing

    @pytest.mark.behavioral
    def test_plan_pre_issue_not_found_preserved(self, tmp_path, capsys) -> None:
        self._setup_plan_env(tmp_path, "ISS-ADH-055", None)
        contract = self._invoke_plan_pre(tmp_path, "ISS-ADH-055", capsys)
        assert contract["status"] == "ISSUE_NOT_FOUND"

    @pytest.mark.behavioral
    def test_plan_pre_ready_shape_keeps_existing_keys(self, tmp_path, capsys) -> None:
        self._setup_plan_env(tmp_path, "ISS-ADH-055", TRACEABLE_ISSUE_BODY)
        contract = self._invoke_plan_pre(tmp_path, "ISS-ADH-055", capsys)
        for key in (
            "issue_id",
            "spec_path",
            "plan_target",
            "worktree_full",
            "constitution_path",
            "timestamp",
            "status",
            "phase",
        ):
            assert key in contract

    @pytest.mark.behavioral
    def test_plan_pre_path_traversal_fails_closed(self, tmp_path, capsys) -> None:
        TestMesoContracts._setup_git_repo(tmp_path)
        TestMesoContracts._setup_minimal_env(
            tmp_path, session_phase="PLAN", active_issue_id="ISS-ADH-055"
        )
        specs_dir = tmp_path / "specs"
        record = {
            "issue_id": "ISS-ADH-055",
            "type": "feature",
            "title": "Traversal",
            "status": "BACKLOG",
            "source_file": "specs/adhoc/issues/../../evil.md",
            "timestamp": "2026-01-01T00:00:00Z",
        }
        (specs_dir / "issues.jsonl").write_text(json.dumps(record) + "\n")
        contract = self._invoke_plan_pre(tmp_path, "ISS-ADH-055", capsys)
        assert contract["status"] == "ISSUE_NOT_FOUND"

    @pytest.mark.behavioral
    def test_plan_pre_legacy_id_gated_like_epic_prefix(self, tmp_path, capsys) -> None:
        self._setup_plan_env(tmp_path, "ISS-001", "# Spec\n\nNo sections.\n")
        contract = self._invoke_plan_pre(tmp_path, "ISS-001", capsys)
        assert contract["status"] == "NOT_READY"
        assert contract["missing_fields"]
        assert "repair" in contract["repair_hint"].lower()
