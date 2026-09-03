from __future__ import annotations

import json
import subprocess
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord
from deviate.cli.micro import (
    _find_task_record,
    _resolve_issue_id_from_branch,
    _resolve_task_context,
)

runner = CliRunner()


def _git_env() -> dict[str, str]:
    return {
        k: v for k, v in __import__("os").environ.items() if not k.startswith("GIT_")
    }


def _make_task_record(
    task_id: str = "TSK-004-01",
    issue_id: str = "ISS-001-004",
    description: str = "E2E phase task",
    status: str = "COMPLETED",
    execution_mode: str = "E2E",
) -> TaskRecord:
    return TaskRecord(
        id=task_id,
        issue_id=issue_id,
        description=description,
        status=status,
        execution_mode=execution_mode,
    )


def _write_ledger(ledger_path: Path, *records: TaskRecord) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    for r in records:
        line = r.model_dump_json() + "\n"
        ledger_path.open("a", encoding="utf-8").write(line)


class TestE2ePre:
    def test_e2e_pre_verifies_all_tasks_complete(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            task = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-004",
                description="E2E task one",
                status="COMPLETED",
                execution_mode="TDD",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, task)

            result = runner.invoke(cli, ["e2e", "pre"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            data = json.loads(result.output)
            assert "test_paths" in data

    def test_e2e_pre_rejects_incomplete_tasks(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            completed = _make_task_record(
                task_id="TSK-004-01",
                issue_id="ISS-001-004",
                description="Completed task",
                status="COMPLETED",
            )
            pending = _make_task_record(
                task_id="TSK-004-02",
                issue_id="ISS-001-004",
                description="Pending task",
                status="PENDING",
            )
            ledger_path = Path("specs") / "004-micro-layer" / "tasks.jsonl"
            _write_ledger(ledger_path, completed, pending)

            result = runner.invoke(cli, ["e2e", "pre"])

            assert result.exit_code != 0, (
                f"Expected non-zero exit for incomplete tasks, got {result.exit_code}: {result.output}"
            )
            assert "INCOMPLETE_TASKS" in result.output


class TestE2ePreBranchScoping:
    """`deviate e2e pre` must scope the completeness check to the branch's issue.

    Regression: it previously checked every specs/**/tasks.jsonl repo-wide, so
    running e2e in a multi-issue worktree aborted with INCOMPLETE_TASKS because
    an *unrelated* issue's tasks were still pending — even when the branch's own
    issue was complete. It also emitted only {test_paths}, omitting the
    spec_dir / tasks_file / git_branch fields the /deviate-e2e contract documents.
    """

    @staticmethod
    def _seed_issue(
        root: Path, issue_id: str, bucket: str, slug: str, complete: bool
    ) -> None:
        spec_dir = root / "specs"
        if not (spec_dir / "issues.jsonl").exists():
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "issues.jsonl").write_text("", encoding="utf-8")
        with open(spec_dir / "issues.jsonl", "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "issue_id": issue_id,
                        "source_file": f"specs/{bucket}/issues/{slug}.md",
                    }
                )
                + "\n"
            )
        feature_dir = spec_dir / bucket / slug
        feature_dir.mkdir(parents=True, exist_ok=True)
        tid = f"TSK-{issue_id[-3:]}-01"
        rec = {
            "id": tid,
            "issue_id": issue_id,
            "description": "task",
            "status": "COMPLETED" if complete else "PENDING",
            "execution_mode": "TDD",
        }
        (feature_dir / "tasks.jsonl").write_text(
            json.dumps(rec) + "\n", encoding="utf-8"
        )
        (feature_dir / "tasks.md").write_text(
            f"# Tasks\n\n- {tid}: task\n", encoding="utf-8"
        )

    @staticmethod
    def _checkout(root: Path, branch: str) -> None:
        subprocess.run(
            ["git", "checkout", "-b", branch],
            cwd=root,
            env=_git_env(),
            check=True,
        )

    def test_e2e_pre_scopes_to_branch_issue(self, tmp_git_repo: Path):
        # An unrelated issue with an incomplete task must NOT abort E2E for
        # the branch's own (complete) issue.
        self._seed_issue(
            tmp_git_repo, "ISS-UNREL-004", "001-stale-slice", "004-stale-task", False
        )
        self._seed_issue(
            tmp_git_repo,
            "ISS-INT-021",
            "002-embedder-vector-search",
            "003-config-embedder-cli",
            True,
        )
        self._checkout(
            tmp_git_repo, "feat/002-embedder-vector-search/003-config-embedder-cli"
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["e2e", "pre"])

        assert result.exit_code == 0, (
            f"Expected exit 0 (branch issue complete), got {result.exit_code}: {result.output}"
        )
        data = json.loads(result.output)
        assert "test_paths" in data
        assert data.get("git_branch") == (
            "feat/002-embedder-vector-search/003-config-embedder-cli"
        )
        tasks_file = data.get("tasks_file", "")
        assert "002-embedder-vector-search" in tasks_file
        assert "003-config-embedder-cli" in tasks_file


class TestE2ePost:
    def test_e2e_post_commits_results(self, tmp_git_repo: Path):
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="E2E")
            session.save(dot_dir / "session.json")

            e2e_result = Path("e2e-results.md")
            e2e_result.write_text("# E2E Tests\nAll pass\n")

            subprocess.run(
                ["git", "add", "."], cwd=tmp_git_repo, env=_git_env(), check=True
            )

            result = runner.invoke(cli, ["e2e", "post"])

            assert result.exit_code == 0, (
                f"Expected exit 0, got {result.exit_code}: {result.output}"
            )
            log = subprocess.run(
                ["git", "log", "--oneline", "-1"],
                cwd=tmp_git_repo,
                capture_output=True,
                text=True,
                env=_git_env(),
            )
            assert log.returncode == 0
            assert len(log.stdout.strip()) > 0


class TestCrossIssueTaskIdCollision:
    """A task id namespaced per issue must not be shadowed by an unrelated
    issue's ledger.

    Regression: `deviate micro run` resolved the 'latest' record by task id
    alone. Every issue reuses the same ``TSK-NNN-NN`` numbering, so a same-
    numbered task in a later-sorting ledger (e.g. ``specs/adhoc/*``) shadowed
    the active issue's records --- "no ledger entry" against a committed
    ledger, and explicit ``<tid>`` dispatch hitting the wrong issue's task.",
    """

    @staticmethod
    def _seed_ledger(
        root: Path, issue_id: str, bucket: str, slug: str, status: str
    ) -> None:
        tid = "TSK-005-01"
        rec = {
            "id": tid,
            "issue_id": issue_id,
            "description": "task",
            "status": status,
            "execution_mode": "TDD",
        }
        ledger = root / "specs" / bucket / slug / "tasks.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text(json.dumps(rec) + "\n", encoding="utf-8")

    @staticmethod
    def _seed_tasks_md(root: Path, bucket: str, slug: str) -> None:
        md = root / "specs" / bucket / slug / "tasks.md"
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text("# Tasks\n\n- TSK-005-01: task\n", encoding="utf-8")

    @staticmethod
    def _append_issue(root: Path, issue_id: str, bucket: str, slug: str) -> None:
        spec_dir = root / "specs"
        spec_dir.mkdir(parents=True, exist_ok=True)
        with (spec_dir / "issues.jsonl").open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "issue_id": issue_id,
                        "source_file": f"specs/{bucket}/issues/{slug}.md",
                    }
                )
                + "\n"
            )

    @staticmethod
    def _write_tasks_md(root: Path, bucket: str, slug: str, body: str) -> None:
        md = root / "specs" / bucket / slug / "tasks.md"
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(body, encoding="utf-8")

    def _checkout(self, root: Path, branch: str) -> None:
        subprocess.run(
            ["git", "checkout", "-b", branch],
            cwd=root,
            env=_git_env(),
            check=True,
        )

    def _seed_empty_active_with_sibling_completed(
        self,
        root: Path,
        *,
        tasks_md_body: str,
    ) -> None:
        """Sibling COMPLETED TSK-001-04; active 001-002 has zero JSONL rows."""
        sibling = {
            "id": "TSK-001-04",
            "issue_id": "001-001",
            "description": "sibling already done",
            "status": "COMPLETED",
            "execution_mode": "TDD",
        }
        sibling_ledger = (
            root / "specs" / "001-phone-to-pi-relay" / "001-handshake" / "tasks.jsonl"
        )
        sibling_ledger.parent.mkdir(parents=True, exist_ok=True)
        sibling_ledger.write_text(json.dumps(sibling) + "\n", encoding="utf-8")
        self._append_issue(root, "001-001", "001-phone-to-pi-relay", "001-handshake")
        self._append_issue(
            root,
            "001-002",
            "001-phone-to-pi-relay",
            "002-node-pairing-and-presence",
        )
        self._write_tasks_md(
            root,
            "001-phone-to-pi-relay",
            "002-node-pairing-and-presence",
            tasks_md_body,
        )
        self._checkout(
            root,
            "feat/001-phone-to-pi-relay/002-node-pairing-and-presence",
        )

    def test_find_task_record_prefers_branch_issue(self, tmp_git_repo: Path):
        # Active issue 005-001 owns its own TSK-005-01. A same-numbered task
        # in a later-sorting adhoc ledger by id-only dedup used to shadow it.
        self._seed_ledger(tmp_git_repo, "ISS-ADH-014", "adhoc", "014-x", "COMPLETED")
        self._seed_ledger(
            tmp_git_repo,
            "005-001",
            "005-acceptance-gates",
            "001-verification",
            "COMPLETED",
        )
        self._seed_tasks_md(tmp_git_repo, "005-acceptance-gates", "001-verification")
        # issues.jsonl maps the branch slug back to issue 005-001.
        (tmp_git_repo / "specs" / "issues.jsonl").write_text(
            json.dumps(
                {
                    "issue_id": "005-001",
                    "source_file": "specs/005-acceptance-gates/issues/001-verification.md",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "checkout", "-b", "feat/005-acceptance-gates/001-verification"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        with chdir(tmp_git_repo):
            branch_issue = _resolve_issue_id_from_branch(tmp_git_repo)
            assert branch_issue == "005-001", f"got {branch_issue!r}"
            hit = _find_task_record(tmp_git_repo, "TSK-005-01")
            assert hit is not None
            rec, ledger_file = hit
            assert rec.get("issue_id") == "005-001", (
                f"found the shadow issue {rec.get('issue_id')}, expected 005-001"
            )
            assert "005-acceptance-gates" in str(ledger_file)

    def test_find_task_record_empty_ledger_never_returns_sibling_completed(
        self, tmp_git_repo: Path
    ) -> None:
        """AC-PLAN-003: a known branch issue must not receive a sibling row.

        Hole: sibling COMPLETED TSK-001-04 exists, active 001-002 has zero
        JSONL rows. `_find_task_record` must return None or a 001-002 record,
        never the sibling COMPLETED row.
        """
        self._seed_empty_active_with_sibling_completed(
            tmp_git_repo,
            tasks_md_body=("# Tasks\n\n- [ ] TSK-001-04: pair node presence\n"),
        )

        with chdir(tmp_git_repo):
            branch_issue = _resolve_issue_id_from_branch(tmp_git_repo)
            assert branch_issue == "001-002", f"got {branch_issue!r}"
            hit = _find_task_record(tmp_git_repo, "TSK-001-04")

        if hit is not None:
            rec, _ = hit
            assert rec.get("issue_id") == "001-002", (
                "known active issue 001-002 must not receive sibling "
                f"{rec.get('issue_id')} COMPLETED TSK-001-04"
            )
            assert rec.get("status") != "COMPLETED" or rec.get("issue_id") == (
                "001-002"
            )

    def test_find_task_record_resolve_synthesizes_pending_for_branch_issue(
        self, tmp_git_repo: Path
    ) -> None:
        """AC-PLAN-003: pinned miss synthesizes this issue's PENDING task."""
        self._seed_empty_active_with_sibling_completed(
            tmp_git_repo,
            tasks_md_body=("# Tasks\n\n- [ ] TSK-001-04: pair node presence\n"),
        )

        with chdir(tmp_git_repo):
            task, _ledger = _resolve_task_context("TSK-001-04", tmp_git_repo)

        assert task.get("id") == "TSK-001-04"
        assert task.get("issue_id") == "001-002", (
            "pinned resolve must synthesize PENDING for 001-002, "
            f"got issue_id={task.get('issue_id')!r} status={task.get('status')!r}"
        )
        assert task.get("status") == "PENDING"

    def test_find_task_record_TASK_NOT_FOUND_when_issue_omits_pin(
        self, tmp_git_repo: Path
    ) -> None:
        """AC-PLAN-004: omit the pin here → TASK_NOT_FOUND, not a sibling bind."""
        self._seed_empty_active_with_sibling_completed(
            tmp_git_repo,
            tasks_md_body="# Tasks\n\n- [ ] TSK-001-01: other work\n",
        )

        printed: list[str] = []

        def _capture(msg: object, *args: object, **kwargs: object) -> None:
            printed.append(str(msg))

        with chdir(tmp_git_repo):
            with patch("deviate.cli.micro.console.print", side_effect=_capture):
                with pytest.raises(typer.Exit) as excinfo:
                    _resolve_task_context("TSK-001-04", tmp_git_repo)

        assert excinfo.value.exit_code == 1
        assert any("TASK_NOT_FOUND" in line for line in printed), (
            f"expected TASK_NOT_FOUND, printed={printed!r}"
        )
