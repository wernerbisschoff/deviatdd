from __future__ import annotations

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.cli.meso import _AGENT_DIRS, _sync_worktree_assets

runner = CliRunner()


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
