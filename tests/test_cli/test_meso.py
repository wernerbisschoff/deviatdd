from __future__ import annotations

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.cli.meso import _AGENT_DIRS, _pr_title, _sync_worktree_assets

runner = CliRunner()


class TestPrTitle:
    def test_uses_numbered_issue_commit_scope(self) -> None:
        assert _pr_title("ISS-001-001", "Feature") == "feat(001-001): Feature"

    def test_uses_adhoc_issue_commit_scope(self) -> None:
        assert _pr_title("ISS-ADH-001", "Fix", "bug") == "fix(ADH-001): Fix"


class TestSpecifyPre:
    def test_specify_pre_requires_issue_flag(self):
        """'deviate specify pre' requires --issue flag"""
        result = runner.invoke(cli, ["specify", "pre", "--dry-run"])
        assert result.exit_code == 1, result.output
        assert "ISSUE_ID_REQUIRED" in result.output


class TestSyncWorktreeAssets:
    """Regression: worktrees must receive every supported agent skill dir.

    The tuple `_AGENT_DIRS` must stay aligned with the agent platforms that
    `deviate setup` writes into (``active_agents`` in ``cli/__init__.py`` and
    ``detect_agents`` in ``core/commands.py``). Previously `.pi` and `.omp`
    were missing from the sync list, so worktrees created by
    `deviate meso run` lacked those skill directories on those platforms.
    """

    def test_copies_every_supported_agent_dir_when_present(self, tmp_path):
        repo_root = tmp_path / "repo"
        worktree = tmp_path / "wt"
        repo_root.mkdir()
        worktree.mkdir()

        for agent_dir in _AGENT_DIRS:
            src = repo_root / agent_dir
            src.mkdir()
            (src / "marker.txt").write_text(agent_dir, encoding="utf-8")

        _sync_worktree_assets(repo_root, worktree)

        for agent_dir in _AGENT_DIRS:
            copied = worktree / agent_dir / "marker.txt"
            assert copied.exists(), f"{agent_dir} not synced to worktree"
            assert copied.read_text(encoding="utf-8") == agent_dir

    def test_skips_missing_agent_dirs_without_creating_them(self, tmp_path):
        repo_root = tmp_path / "repo"
        worktree = tmp_path / "wt"
        repo_root.mkdir()
        worktree.mkdir()

        # Only populate the original three; .pi and .omp absent in the repo.
        for agent_dir in (".claude", ".opencode", ".factory"):
            (repo_root / agent_dir).mkdir()

        _sync_worktree_assets(repo_root, worktree)

        assert (worktree / ".claude").is_dir()
        assert (worktree / ".opencode").is_dir()
        assert (worktree / ".factory").is_dir()
        assert not (worktree / ".pi").exists()
        assert not (worktree / ".omp").exists()

    def test_copies_env_file_when_present(self, tmp_path):
        repo_root = tmp_path / "repo"
        worktree = tmp_path / "wt"
        repo_root.mkdir()
        worktree.mkdir()

        env_content = "DATABASE_URL=postgres://localhost:5432/mydb\n"
        (repo_root / ".env").write_text(env_content, encoding="utf-8")

        _sync_worktree_assets(repo_root, worktree)

        dst = worktree / ".env"
        assert dst.is_file(), ".env not synced to worktree"
        assert dst.read_text(encoding="utf-8") == env_content

    def test_skips_missing_env_file_gracefully(self, tmp_path):
        repo_root = tmp_path / "repo"
        worktree = tmp_path / "wt"
        repo_root.mkdir()
        worktree.mkdir()

        # No .env in repo — should not error and not create a stray file
        _sync_worktree_assets(repo_root, worktree)

        assert not (worktree / ".env").exists()


class TestWorktreeAssetSyncOrdering:
    """_sync_worktree_assets must run before _setup_mise.

    If mise setup runs before asset sync, .env is not available
    during setup. This test verifies the call order by recording
    each invocation in a shared list.
    """

    def test_sync_before_setup_in_try_claim_issue(self, tmp_path):
        from datetime import datetime, timezone
        from unittest.mock import patch

        from deviate.cli.meso import _try_claim_issue
        from deviate.state.ledger import IssueRecord

        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        wt_path = tmp_path / "wt"
        ledger_path = tmp_path / "specs" / "issues.jsonl"
        ledger_path.parent.mkdir(parents=True)

        issue = IssueRecord(
            issue_id="ISS-001-ORD",
            type="feature",
            title="Test ordering",
            source_file="specs/test-epic/issues/ISS-001-ORD/",
            timestamp=datetime.now(timezone.utc),
        )

        call_order: list[str] = []

        with (
            patch("deviate.cli.meso._sync_worktree_assets") as mock_sync,
            patch("deviate.cli.meso._setup_mise") as mock_setup,
            patch(
                "deviate.cli.meso.create_worktree",
                return_value=wt_path,
            ),
            patch(
                "deviate.cli.meso.branch_exists_on_remote",
                return_value=False,
            ),
            patch("deviate.cli.meso.claim_issue", return_value=False),
        ):
            mock_sync.side_effect = lambda *_: call_order.append("sync")
            mock_setup.side_effect = lambda *_: call_order.append("setup")

            _try_claim_issue(issue, repo_root, ledger_path, remote="origin")

        assert call_order == ["sync", "setup"], (
            f"Expected sync before setup, got {call_order}"
        )


class TestSpecifyLocalFlag:
    """`_try_claim_issue(..., local=True)` skips remote interaction.

    The `--local` flag is the no-remote workflow: worktree + ledger only.
    These tests pin the contract that ``branch_exists_on_remote`` and the
    ``git push`` subprocess are NEVER invoked, and that an existing local
    branch short-circuits with a fully-populated metadata dict.
    """

    def _make_issue(self):
        from datetime import datetime, timezone

        from deviate.state.ledger import IssueRecord

        return IssueRecord(
            issue_id="ISS-001-LOC",
            type="feature",
            title="Test local flag",
            source_file="specs/test-epic/issues/iss-001-loc.md",
            timestamp=datetime.now(timezone.utc),
        )

    def test_local_skips_branch_exists_on_remote_call(self, tmp_path):
        from unittest.mock import patch

        from deviate.cli.meso import _try_claim_issue

        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        ledger_path = tmp_path / "specs" / "issues.jsonl"
        ledger_path.parent.mkdir(parents=True)

        # Patch find_worktree_for_branch to return None so the short-circuit
        # does NOT fire — we want the function to fall through to the
        # post-short-circuit code path where branch_exists_on_remote would
        # have been called if not for the local guard.
        with (
            patch("deviate.cli.meso.find_worktree_for_branch", return_value=None),
            patch(
                "deviate.cli.meso.create_worktree", return_value=tmp_path / "wt"
            ) as mock_create,
            patch("deviate.cli.meso.claim_issue", return_value=False),
            patch("deviate.cli.meso._sync_worktree_assets"),
            patch("deviate.cli.meso._setup_mise"),
            patch("deviate.cli.meso.branch_exists_on_remote") as mock_remote,
        ):
            _try_claim_issue(self._make_issue(), repo_root, ledger_path, local=True)

        mock_create.assert_called_once()
        mock_remote.assert_not_called()

    def test_local_skips_git_push_subprocess(self, tmp_path, monkeypatch):
        import subprocess

        from deviate.cli.meso import _try_claim_issue

        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        ledger_path = tmp_path / "specs" / "issues.jsonl"
        ledger_path.parent.mkdir(parents=True)

        calls: list[list[str]] = []
        real_run = subprocess.run

        def recording(argv, *args, **kwargs):
            calls.append(list(argv))
            return real_run(argv, *args, **kwargs)

        monkeypatch.setattr("deviate.cli.meso.subprocess.run", recording)
        monkeypatch.setattr(
            "deviate.cli.meso.find_worktree_for_branch", lambda *a, **k: None
        )
        monkeypatch.setattr(
            "deviate.cli.meso.create_worktree", lambda *a, **k: tmp_path / "wt"
        )
        monkeypatch.setattr("deviate.cli.meso.claim_issue", lambda *a, **k: True)
        monkeypatch.setattr(
            "deviate.cli.meso._sync_worktree_assets", lambda *a, **k: None
        )
        monkeypatch.setattr("deviate.cli.meso._setup_mise", lambda *a, **k: None)

        _try_claim_issue(self._make_issue(), repo_root, ledger_path, local=True)

        push_calls = [a for a in calls if a[:2] == ["git", "push"]]
        assert push_calls == [], f"local mode must not invoke `git push`: {push_calls}"

    def test_local_short_circuits_on_existing_branch(self, tmp_path):
        from unittest.mock import MagicMock, patch

        from deviate.cli.meso import _try_claim_issue

        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        ledger_path = tmp_path / "specs" / "issues.jsonl"
        ledger_path.parent.mkdir(parents=True)
        existing_path = tmp_path / "wt" / "feat-test-epic-iss-001-loc"
        existing_path.mkdir(parents=True)

        with (
            patch(
                "deviate.cli.meso.find_worktree_for_branch",
                return_value=existing_path,
            ),
            patch(
                "deviate.cli.meso.create_worktree", new_callable=MagicMock
            ) as mock_create,
            patch("deviate.cli.meso.branch_exists_on_remote"),
            patch("deviate.cli.meso.claim_issue"),
            patch("deviate.cli.meso._sync_worktree_assets"),
            patch("deviate.cli.meso._setup_mise"),
        ):
            result = _try_claim_issue(
                self._make_issue(), repo_root, ledger_path, local=True
            )

        assert isinstance(result, dict)
        assert result["worktree_path"] == str(existing_path)
        mock_create.assert_not_called()

    def test_local_returns_coherent_metadata_dict(self, tmp_path):
        from unittest.mock import patch

        from deviate.cli.meso import _try_claim_issue

        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        ledger_path = tmp_path / "specs" / "issues.jsonl"
        ledger_path.parent.mkdir(parents=True)
        existing_path = tmp_path / "wt" / "feat-test-epic-iss-001-loc"
        existing_path.mkdir(parents=True)

        with (
            patch(
                "deviate.cli.meso.find_worktree_for_branch",
                return_value=existing_path,
            ),
            patch("deviate.cli.meso.create_worktree"),
            patch("deviate.cli.meso.branch_exists_on_remote"),
            patch("deviate.cli.meso.claim_issue"),
            patch("deviate.cli.meso._sync_worktree_assets"),
            patch("deviate.cli.meso._setup_mise"),
        ):
            result = _try_claim_issue(
                self._make_issue(), repo_root, ledger_path, local=True
            )

        assert set(result) == {
            "resolved_id",
            "issue",
            "epic_slug",
            "issue_slug",
            "branch",
            "spec_target_rel",
            "worktree_path",
        }, f"metadata dict missing keys: {set(result)}"
        assert result["resolved_id"] == "ISS-001-LOC"
        assert result["epic_slug"] == "test-epic"
        assert result["issue_slug"] == "iss-001-loc"
        assert result["branch"] == "feat/test-epic/iss-001-loc"
        assert result["spec_target_rel"] == "specs/test-epic/iss-001-loc/spec.md"
        assert result["worktree_path"] == str(existing_path)
        assert result["issue"] is not None
