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
        # worktree + remote. Mock branch_exists_on_remote to False so
        # auto-discovery does not attempt a live network call to origin.
        called: dict[str, object] = {}

        def fake_try_claim(record, **kwargs):  # noqa: ARG001
            called["issue_id"] = record.issue_id
            return {"worktree_path": str(tmp_git_repo / ".worktrees" / "fake")}

        monkeypatch.setattr(
            "deviate.cli.meso.branch_exists_on_remote",
            lambda branch, **kw: False,
        )
        monkeypatch.setattr("deviate.cli.meso._try_claim_issue", fake_try_claim)

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["specify"])

        assert result.exit_code == 0, result.output
        assert called.get("issue_id") == "ISS-001-001", (
            f"Expected auto-discovery to claim ISS-001-001, "
            f"got {called.get('issue_id')}; output={result.output}"
        )
        assert "WORKTREE" in result.output

    def test_specify_bare_arg_skips_remote_claimed_issue(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Bare `deviate specify` skips an issue whose branch is already on
        remote (claimed elsewhere) and claims the next claimable one."""
        from datetime import datetime, timezone

        from deviate.state.ledger import IssueRecord, append_issue_transition

        (tmp_git_repo / ".deviate").mkdir()
        (tmp_git_repo / ".deviate" / "session.json").write_text(
            '{"current_phase": "IDLE", "active_issue_id": null}'
        )
        (tmp_git_repo / ".deviate" / "config.toml").write_text(
            "claim_remote = true\n", encoding="utf-8"
        )
        specs_dir = tmp_git_repo / "specs"
        specs_dir.mkdir()
        (specs_dir / "constitution.md").write_text(
            "# Constitution\ntest_command = pytest\nlint_command = ruff\n"
        )
        ledger = specs_dir / "issues.jsonl"
        now = datetime.now(timezone.utc)
        append_issue_transition(
            IssueRecord(
                issue_id="ISS-001-001",
                type="feature",
                title="First Backlog",
                status="BACKLOG",
                source_file="specs/test-epic/issues/iss-001.md",
                timestamp=now,
            ),
            ledger,
        )
        append_issue_transition(
            IssueRecord(
                issue_id="ISS-001-002",
                type="feature",
                title="Second Backlog",
                status="BACKLOG",
                source_file="specs/test-epic/issues/iss-002.md",
                timestamp=now,
            ),
            ledger,
        )

        called: dict[str, object] = {}

        def fake_try_claim(record, **kwargs):  # noqa: ARG001
            called["issue_id"] = record.issue_id
            return {"worktree_path": str(tmp_git_repo / ".worktrees" / "fake")}

        monkeypatch.setattr("deviate.cli.meso._try_claim_issue", fake_try_claim)
        # The origin remote exists but ISS-001-001's branch is claimed elsewhere.
        monkeypatch.setattr(
            "deviate.cli.meso.branch_exists_on_remote",
            lambda branch, **kw: branch == "feat/test-epic/iss-001",
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["specify"])

        assert result.exit_code == 0, result.output
        assert called.get("issue_id") == "ISS-001-002", (
            "Expected auto-discovery to skip the remote-claimed ",
            "ISS-001-001 and claim ISS-001-002, got ",
            f"{called.get('issue_id')}; output={result.output}",
        )
        assert "WORKTREE" in result.output

    def test_specify_local_flag_claims_locally_when_no_branch(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from datetime import datetime, timezone
        from deviate.state.ledger import IssueRecord, append_issue_transition

        (tmp_git_repo / ".deviate").mkdir()
        (tmp_git_repo / ".deviate" / "session.json").write_text(
            '{"current_phase": "IDLE", "active_issue_id": null}'
        )
        specs_dir = tmp_git_repo / "specs"
        specs_dir.mkdir()
        (specs_dir / "constitution.md").write_text(
            "# Constitution\ntest_command = pytest\n"
        )
        ledger = specs_dir / "issues.jsonl"
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
        called: dict[str, object] = {}

        def fake(record, **kwargs):
            called["local"] = kwargs["local"]
            return {"worktree_path": str(tmp_git_repo / ".worktrees" / "fake")}

        monkeypatch.setattr("deviate.cli.meso._try_claim_issue", fake)
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["specify", "ISS-001-001", "--local"])
        assert result.exit_code == 0, result.output
        assert "WORKTREE" in result.output
        assert called["local"] is True

    def test_specify_local_flag_forwards_to_specify_pre(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from datetime import datetime, timezone
        from deviate.state.ledger import IssueRecord, append_issue_transition

        (tmp_git_repo / ".deviate").mkdir()
        (tmp_git_repo / ".deviate" / "session.json").write_text(
            '{"current_phase": "IDLE", "active_issue_id": null}'
        )
        specs_dir = tmp_git_repo / "specs"
        specs_dir.mkdir()
        (specs_dir / "constitution.md").write_text(
            "# Constitution\ntest_command = pytest\n"
        )
        ledger = specs_dir / "issues.jsonl"
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
        called: dict[str, object] = {}

        def fake_pre(*args, **kwargs):
            called["local"] = kwargs["local"]
            return {"worktree_path": str(tmp_git_repo / ".worktrees" / "fake")}

        monkeypatch.setattr("deviate.cli.meso._specify_pre", fake_pre)
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["specify", "ISS-001-001", "--local"])
        assert result.exit_code == 0, result.output
        assert called["local"] is True

    def test_specify_omitted_local_honors_claim_remote_false(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-PLAN-002: omitted --local with claim_remote=false is effective local."""
        from datetime import datetime, timezone

        from deviate.state.ledger import IssueRecord, append_issue_transition

        (tmp_git_repo / ".deviate").mkdir()
        (tmp_git_repo / ".deviate" / "session.json").write_text(
            '{"current_phase": "IDLE", "active_issue_id": null}'
        )
        (tmp_git_repo / ".deviate" / "config.toml").write_text(
            "claim_remote = false\n", encoding="utf-8"
        )
        specs_dir = tmp_git_repo / "specs"
        specs_dir.mkdir()
        (specs_dir / "constitution.md").write_text(
            "# Constitution\ntest_command = pytest\n"
        )
        ledger = specs_dir / "issues.jsonl"
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
        called: dict[str, object] = {}

        def fake(record, **kwargs):
            called["local"] = kwargs.get("local")
            return {"worktree_path": str(tmp_git_repo / ".worktrees" / "fake")}

        monkeypatch.setattr("deviate.cli.meso._try_claim_issue", fake)
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["specify", "ISS-001-001"])
        assert result.exit_code == 0, result.output
        assert called.get("local") is True, (
            f"omitted --local with claim_remote=false must forward local=True, "
            f"got {called.get('local')}; output={result.output}"
        )
        assert "WORKTREE" in result.output

    def test_specify_omitted_local_honors_absent_claim_remote(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Absent claim_remote key is effective local (no origin push)."""
        from datetime import datetime, timezone

        from deviate.state.ledger import IssueRecord, append_issue_transition

        (tmp_git_repo / ".deviate").mkdir()
        (tmp_git_repo / ".deviate" / "session.json").write_text(
            '{"current_phase": "IDLE", "active_issue_id": null}'
        )
        specs_dir = tmp_git_repo / "specs"
        specs_dir.mkdir()
        (specs_dir / "constitution.md").write_text(
            "# Constitution\ntest_command = pytest\n"
        )
        ledger = specs_dir / "issues.jsonl"
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
        called: dict[str, object] = {}

        def fake(record, **kwargs):
            called["local"] = kwargs.get("local")
            return {"worktree_path": str(tmp_git_repo / ".worktrees" / "fake")}

        monkeypatch.setattr("deviate.cli.meso._try_claim_issue", fake)
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["specify", "ISS-001-001"])
        assert result.exit_code == 0, result.output
        assert called.get("local") is True, (
            f"omitted --local with absent claim_remote must forward local=True, "
            f"got {called.get('local')}; output={result.output}"
        )
        assert "WORKTREE" in result.output

    def test_specify_local_overrides_claim_remote_true(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-PLAN-003: --local wins when claim_remote is true."""
        from datetime import datetime, timezone

        from deviate.state.ledger import IssueRecord, append_issue_transition

        (tmp_git_repo / ".deviate").mkdir()
        (tmp_git_repo / ".deviate" / "session.json").write_text(
            '{"current_phase": "IDLE", "active_issue_id": null}'
        )
        (tmp_git_repo / ".deviate" / "config.toml").write_text(
            "claim_remote = true\n", encoding="utf-8"
        )
        specs_dir = tmp_git_repo / "specs"
        specs_dir.mkdir()
        (specs_dir / "constitution.md").write_text(
            "# Constitution\ntest_command = pytest\n"
        )
        ledger = specs_dir / "issues.jsonl"
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
        called: dict[str, object] = {}

        def fake(record, **kwargs):
            called["local"] = kwargs.get("local")
            return {"worktree_path": str(tmp_git_repo / ".worktrees" / "fake")}

        monkeypatch.setattr("deviate.cli.meso._try_claim_issue", fake)
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["specify", "ISS-001-001", "--local"])
        assert result.exit_code == 0, result.output
        assert called.get("local") is True, (
            f"--local must forward local=True when claim_remote=true, "
            f"got {called.get('local')}; output={result.output}"
        )
        assert "WORKTREE" in result.output

    def test_specify_omitted_local_honors_claim_remote_true(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Existing claim_remote=true still pushes when --local is omitted."""
        from datetime import datetime, timezone

        from deviate.state.ledger import IssueRecord, append_issue_transition

        (tmp_git_repo / ".deviate").mkdir()
        (tmp_git_repo / ".deviate" / "session.json").write_text(
            '{"current_phase": "IDLE", "active_issue_id": null}'
        )
        (tmp_git_repo / ".deviate" / "config.toml").write_text(
            "claim_remote = true\n", encoding="utf-8"
        )
        specs_dir = tmp_git_repo / "specs"
        specs_dir.mkdir()
        (specs_dir / "constitution.md").write_text(
            "# Constitution\ntest_command = pytest\n"
        )
        ledger = specs_dir / "issues.jsonl"
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
        called: dict[str, object] = {}

        def fake(record, **kwargs):
            called["local"] = kwargs.get("local")
            return {"worktree_path": str(tmp_git_repo / ".worktrees" / "fake")}

        monkeypatch.setattr("deviate.cli.meso._try_claim_issue", fake)
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["specify", "ISS-001-001"])
        assert result.exit_code == 0, result.output
        assert called.get("local") is False, (
            f"omitted --local with claim_remote=true must forward local=False, "
            f"got {called.get('local')}; output={result.output}"
        )

    def test_specify_local_flag_short_circuits_when_branch_exists(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`--local` on an existing branch/worktree prints ALREADY_CLAIMED_LOCAL.

        Seeds ``tmp_git_repo`` with a real ``git worktree add`` so the
        ``find_worktree_for_branch`` check inside ``_try_claim_issue``
        returns a path. The CLI must exit 0, emit the short-circuit banner,
        and not write to ``specs/issues.jsonl``.
        """
        import json
        import os
        import subprocess
        from datetime import datetime, timezone

        from deviate.state.ledger import IssueRecord, append_issue_transition

        def _git_env() -> dict[str, str]:
            return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

        # Seed workspace + ledger with one BACKLOG issue.
        (tmp_git_repo / ".deviate").mkdir()
        (tmp_git_repo / ".deviate" / "session.json").write_text(
            '{"current_phase": "IDLE", "active_issue_id": null}'
        )
        specs_dir = tmp_git_repo / "specs"
        specs_dir.mkdir()
        (specs_dir / "constitution.md").write_text(
            "# Constitution\ntest_command = pytest\n"
        )
        ledger = specs_dir / "issues.jsonl"
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

        # Real local branch + registered worktree, matching the claim pattern.
        wt_path = tmp_git_repo.parent / f"{tmp_git_repo.name}-wt"
        subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "-b",
                "feat/test-epic/iss-001",
                str(wt_path),
                "HEAD",
            ],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )

        def _count_specified_rows() -> int:
            count = 0
            for line in ledger.read_text().splitlines():
                if not line.strip():
                    continue
                try:
                    if json.loads(line).get("status") == "SPECIFIED":
                        count += 1
                except json.JSONDecodeError:
                    continue
            return count

        claims_before = _count_specified_rows()

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["specify", "ISS-001-001", "--local"])

        assert result.exit_code == 0, result.output
        assert "ALREADY_CLAIMED_LOCAL" in result.output, result.output

        claims_after = _count_specified_rows()
        assert claims_after == claims_before, (
            f"Short-circuit must not rewrite ledger: "
            f"before={claims_before} after={claims_after}"
        )


class TestSpecifyCollisionRetryKeepsRemoteClaim:
    """AC-PLAN-003: collision retry does not take the local skip path."""

    def test_collision_retry_does_not_call_local_skip_and_keeps_claim_remote_default(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import typer

        from deviate.cli.meso import _specify_pre
        from deviate.state.config import resolve_claim_remote
        from tests.test_cli.test_meso import seed_adhoc_018_origin_rejecting_name

        seed_adhoc_018_origin_rejecting_name(tmp_git_repo)
        (tmp_git_repo / ".deviate").mkdir(exist_ok=True)
        (tmp_git_repo / ".deviate" / "config.toml").write_text(
            "claim_remote = true\n", encoding="utf-8"
        )
        monkeypatch.setattr("deviate.cli.meso._setup_mise", lambda *a, **k: None)

        assert resolve_claim_remote(tmp_git_repo) is True, (
            "collision retry requires claim_remote=true; it is not an opt-out"
        )

        with chdir(tmp_git_repo):
            try:
                result = _specify_pre(issue_id="ISS-ADH-018", local=False)
                exit_code = 0
            except typer.Exit as exc:
                result = None
                exit_code = exc.exit_code

        captured = capsys.readouterr()
        output = captured.out
        assert "LOCAL_ONLY" not in output, (
            f"collision retry must not call the local skip path; output={output!r}"
        )
        assert exit_code == 0, (
            f"specify pre must succeed after 019 retry; "
            f"exit={exit_code} output={output!r}"
        )
        assert result is not None
        assert result["branch"].startswith("feat/adhoc/019-"), (
            f"collision retry must win on 019-*, got {result['branch']!r}"
        )
        assert resolve_claim_remote(tmp_git_repo) is True
