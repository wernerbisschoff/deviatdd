from __future__ import annotations

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.cli.meso import _AGENT_DIRS, _sync_agent_dirs_to_worktree

runner = CliRunner()


class TestSpecifyPre:
    def test_specify_pre_requires_issue_flag(self):
        """'deviate specify pre' requires --issue flag"""
        result = runner.invoke(cli, ["specify", "pre", "--dry-run"])
        assert result.exit_code == 1, result.output
        assert "ISSUE_ID_REQUIRED" in result.output


class TestSyncAgentDirsToWorktree:
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

        _sync_agent_dirs_to_worktree(repo_root, worktree)

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

        _sync_agent_dirs_to_worktree(repo_root, worktree)

        assert (worktree / ".claude").is_dir()
        assert (worktree / ".opencode").is_dir()
        assert (worktree / ".factory").is_dir()
        assert not (worktree / ".pi").exists()
        assert not (worktree / ".omp").exists()
