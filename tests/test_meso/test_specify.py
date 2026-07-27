from __future__ import annotations

from contextlib import chdir
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deviate.cli import cli

runner = CliRunner()


class TestSpecifySetup:
    def test_specify_without_issue_fails(self, tmp_git_repo: Path):
        """'deviate specify ISS-001-001' fails without ledger setup"""
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["specify", "ISS-001-001"])
            assert result.exit_code == 1, result.output
            assert "ISSUE_NOT_FOUND" in result.output

    def test_specify_pre_requires_issue_flag(self):
        """'deviate specify pre' without --issue should fail"""
        result = runner.invoke(cli, ["specify", "pre", "--dry-run"])
        assert result.exit_code == 1, result.output
        assert "ISSUE_ID_REQUIRED" in result.output

    def test_specify_post_is_noop(self):
        """'deviate specify post' is a no-op with a clear message"""
        result = runner.invoke(cli, ["specify", "post"])
        assert result.exit_code == 0, result.output
        assert "SETUP_NOOP" in result.output

    def test_specify_bare_arg_auto_discovers_backlog_issue(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Bare `deviate specify` calls select_next_unblocked_issue and claims it."""
        from datetime import datetime, timezone

        from deviate.state.ledger import IssueRecord, append_issue_transition

        # Seed minimal `.deviate/` and a single BACKLOG issue so
        # `_discover_unclaimed` returns a valid ID.
        (tmp_git_repo / ".deviate").mkdir()
        (tmp_git_repo / ".deviate" / "session.json").write_text(
            '{"current_phase": "IDLE", "active_issue_id": null}'
        )
        specs_dir = tmp_git_repo / "specs"
        specs_dir.mkdir()
        (specs_dir / "constitution.md").write_text(
            "# Constitution\ntest_command = pytest\nlint_command = ruff\n"
        )
        ledger = specs_dir / "issues.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        append_issue_transition(
            IssueRecord(
                issue_id="ISS-001-001",
                type="feature",
                title="First Backlog",
                status="BACKLOG",
                source_file="specs/test-epic/issues/iss-001.md",
                timestamp=datetime.now(timezone.utc),
            ),
            ledger,
        )

        # Stub _try_claim_issue so the test does not need a real git
        # worktree + remote. We only care that the bare-arg path routes
        # through _discover_unclaimed and reaches the claim call.
        called: dict[str, object] = {}

        def fake_try_claim(record, **kwargs):  # noqa: ARG001
            called["issue_id"] = record.issue_id
            return {"worktree_path": str(tmp_git_repo / ".worktrees" / "fake")}

        monkeypatch.setattr("deviate.cli.meso._try_claim_issue", fake_try_claim)

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["specify"])

        assert result.exit_code == 0, result.output
        assert called.get("issue_id") == "ISS-001-001", (
            f"Expected auto-discovery to claim ISS-001-001, "
            f"got {called.get('issue_id')}; output={result.output}"
        )
        assert "WORKTREE" in result.output
