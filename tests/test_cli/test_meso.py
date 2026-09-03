from __future__ import annotations

from contextlib import chdir
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.cli.meso import _AGENT_DIRS, _pr_title, _sync_worktree_assets

runner = CliRunner()


class TestPrTitle:
    def test_uses_numbered_issue_commit_scope(self) -> None:
        assert _pr_title("ISS-001-001", "Feature") == "feat(001-001): Feature"

    def test_uses_adhoc_issue_commit_scope(self) -> None:
        assert _pr_title("ISS-ADH-001", "Fix", "bug") == "fix(ADH-001): Fix"

    @pytest.mark.behavioral
    def test_compound_prefix_strips_to_conventional_form(self) -> None:
        title = _pr_title("ISS-ADH-029", "[FR-029][UI] Fold pruning")
        assert title == "feat(ADH-029): Fold pruning"
        assert re.match(r"^(feat|fix|chore|refactor|docs|test)\([^)]+\): .+", title)

    @pytest.mark.behavioral
    def test_gh_body_file_passes_through_unchanged(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from deviate.cli.meso import _run_gh_pr_create

        body = tmp_path / "body.md"
        body.write_text("summary\nchanges\n", encoding="utf-8")
        with patch("deviate.cli.meso.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "https://github.com/o/r/pull/1\n"
            mock_run.return_value.stderr = ""
            _run_gh_pr_create("feat(ADH-029): Fold pruning", body, cwd=tmp_path)
            argv = mock_run.call_args[0][0]
            assert argv[:5] == [
                "gh",
                "pr",
                "create",
                "--title",
                "feat(ADH-029): Fold pruning",
            ]
            assert argv[5:7] == ["--body-file", str(body)]


class TestSpecifyPre:
    def test_specify_pre_requires_issue_flag(self):
        """'deviate specify pre' requires --issue flag"""
        result = runner.invoke(cli, ["specify", "pre", "--dry-run"])
        assert result.exit_code == 1, result.output
        assert "ISSUE_ID_REQUIRED" in result.output


class TestSyncWorktreeAssets:
    """Regression: worktrees must receive every supported agent skill dir.

    The tuple `_AGENT_DIRS` must stay aligned with the agent platforms that
    `deviate setup` can write into (selected-agent install in
    ``cli/__init__.py`` and ``detect_agents`` in ``core/commands.py``).
    Previously `.pi` and `.omp` were missing from the sync list, so
    worktrees created by `deviate meso run` lacked those skill directories
    on those platforms.
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

    def test_copies_deviate_config_to_worktree(self, tmp_path):
        repo_root = tmp_path / "repo"
        worktree = tmp_path / "wt"
        repo_root.mkdir()
        worktree.mkdir()
        dot_dir = repo_root / ".deviate"
        dot_dir.mkdir()
        (dot_dir / "config.toml").write_text(
            "base_branch = 'develop'\n", encoding="utf-8"
        )

        _sync_worktree_assets(repo_root, worktree)

        assert (worktree / ".deviate" / "config.toml").read_text(
            encoding="utf-8"
        ) == "base_branch = 'develop'\n"

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

    def test_claim_worktree_starts_from_current_branch(self, tmp_git_repo: Path):
        import subprocess
        from datetime import datetime, timezone
        from unittest.mock import patch

        from deviate.cli.meso import _try_claim_issue
        from deviate.state.ledger import IssueRecord
        from tests.conftest import _git_env

        subprocess.run(
            ["git", "checkout", "-b", "current-work"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        ledger_path = tmp_git_repo / "specs" / "issues.jsonl"
        ledger_path.parent.mkdir(parents=True)
        issue = IssueRecord(
            issue_id="ISS-001-BRANCH",
            type="feature",
            title="Use current branch",
            source_file="specs/test-epic/issues/iss-001-branch.md",
            timestamp=datetime.now(timezone.utc),
        )

        with (
            patch(
                "deviate.cli.meso.create_worktree",
                return_value=tmp_git_repo / "wt",
            ) as create,
            patch("deviate.cli.meso.branch_exists_on_remote", return_value=False),
            patch("deviate.cli.meso.claim_issue", return_value=False),
            patch("deviate.cli.meso._sync_worktree_assets"),
            patch("deviate.cli.meso._setup_mise"),
        ):
            _try_claim_issue(issue, tmp_git_repo, ledger_path, remote="origin")

        assert create.call_args.kwargs["start_point"] == "HEAD"


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

    def test_specify_pre_claim_remote_false_skips_remote_lock(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-PLAN-002: omitted local + claim_remote=false skips the remote lock.

        Resolution lives in ``_specify_pre`` so ``_claim_and_setup`` / plan pre
        inherit skip-push. Worktree + SPECIFIED still happen; git push and
        ``branch_exists_on_remote`` do not.
        """
        import json
        import subprocess
        from datetime import datetime, timezone
        from unittest.mock import patch

        from deviate.cli.meso import _specify_pre
        from deviate.state.ledger import IssueRecord, append_issue_transition
        from tests.conftest import _git_env

        (tmp_git_repo / ".deviate").mkdir()
        (tmp_git_repo / ".deviate" / "config.toml").write_text(
            "claim_remote = false\n", encoding="utf-8"
        )
        specs_dir = tmp_git_repo / "specs"
        specs_dir.mkdir()
        ledger = specs_dir / "issues.jsonl"
        append_issue_transition(
            IssueRecord(
                issue_id="ISS-001-LOC",
                type="feature",
                title="Test local flag",
                status="BACKLOG",
                source_file="specs/test-epic/issues/iss-001-loc.md",
                timestamp=datetime.now(timezone.utc),
            ),
            ledger,
        )
        subprocess.run(
            ["git", "add", "specs/issues.jsonl"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "seed backlog"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )

        push_calls: list[list[str]] = []
        real_run = subprocess.run

        def recording(argv, *args, **kwargs):
            argv_list = list(argv)
            if len(argv_list) >= 2 and argv_list[:2] == ["git", "push"]:
                push_calls.append(argv_list)
                return subprocess.CompletedProcess(argv_list, 0, stdout="", stderr="")
            return real_run(argv, *args, **kwargs)

        monkeypatch.setattr("deviate.cli.meso.subprocess.run", recording)
        monkeypatch.setattr("deviate.cli.meso._setup_mise", lambda *a, **k: None)

        printed: list[str] = []
        monkeypatch.setattr(
            "deviate.cli.meso.console.print",
            lambda *a, **k: printed.append(" ".join(str(x) for x in a)),
        )

        with (
            chdir(tmp_git_repo),
            patch("deviate.cli.meso.branch_exists_on_remote") as mock_remote,
        ):
            result = _specify_pre(issue_id="ISS-001-LOC", local=False)

        mock_remote.assert_not_called()
        assert push_calls == [], (
            f"claim_remote=false must not invoke git push: {push_calls}"
        )

        worktree = tmp_git_repo / ".worktrees" / "feat" / "test-epic" / "iss-001-loc"
        assert worktree.is_dir(), f"worktree missing at {worktree}"
        assert result is not None
        assert Path(result["worktree_path"]).resolve() == worktree.resolve()

        wt_ledger = worktree / "specs" / "issues.jsonl"
        assert wt_ledger.is_file()
        statuses = [
            json.loads(line).get("status")
            for line in wt_ledger.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert "SPECIFIED" in statuses

        output = "\n".join(printed)
        assert "LOCAL_ONLY" in output, output

    def test_specify_pre_absent_claim_remote_skips_remote_lock(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Absent claim_remote key skips the remote lock (local default)."""
        import json
        import subprocess
        from datetime import datetime, timezone
        from unittest.mock import patch

        from deviate.cli.meso import _specify_pre
        from deviate.state.ledger import IssueRecord, append_issue_transition
        from tests.conftest import _git_env

        specs_dir = tmp_git_repo / "specs"
        specs_dir.mkdir()
        ledger = specs_dir / "issues.jsonl"
        append_issue_transition(
            IssueRecord(
                issue_id="ISS-001-LOC",
                type="feature",
                title="Test local default",
                status="BACKLOG",
                source_file="specs/test-epic/issues/iss-001-loc.md",
                timestamp=datetime.now(timezone.utc),
            ),
            ledger,
        )
        subprocess.run(
            ["git", "add", "specs/issues.jsonl"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "seed backlog"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )

        push_calls: list[list[str]] = []
        real_run = subprocess.run

        def recording(argv, *args, **kwargs):
            argv_list = list(argv)
            if len(argv_list) >= 2 and argv_list[:2] == ["git", "push"]:
                push_calls.append(argv_list)
                return subprocess.CompletedProcess(argv_list, 0, stdout="", stderr="")
            return real_run(argv, *args, **kwargs)

        monkeypatch.setattr("deviate.cli.meso.subprocess.run", recording)
        monkeypatch.setattr("deviate.cli.meso._setup_mise", lambda *a, **k: None)

        printed: list[str] = []
        monkeypatch.setattr(
            "deviate.cli.meso.console.print",
            lambda *a, **k: printed.append(" ".join(str(x) for x in a)),
        )

        with (
            chdir(tmp_git_repo),
            patch("deviate.cli.meso.branch_exists_on_remote") as mock_remote,
        ):
            result = _specify_pre(issue_id="ISS-001-LOC", local=False)

        mock_remote.assert_not_called()
        assert push_calls == [], (
            f"absent claim_remote must not invoke git push: {push_calls}"
        )

        worktree = tmp_git_repo / ".worktrees" / "feat" / "test-epic" / "iss-001-loc"
        assert worktree.is_dir(), f"worktree missing at {worktree}"
        assert result is not None
        assert Path(result["worktree_path"]).resolve() == worktree.resolve()

        wt_ledger = worktree / "specs" / "issues.jsonl"
        assert wt_ledger.is_file()
        statuses = [
            json.loads(line).get("status")
            for line in wt_ledger.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert "SPECIFIED" in statuses

        output = "\n".join(printed)
        assert "LOCAL_ONLY" in output, output


class TestSpecifyPushFailure:
    """Regression: `git push` failure must surface the real reason.

    Before the fix, ``_try_claim_issue`` swallowed push stderr
    (``capture_output=True`` + no stderr logging) and rolled back the
    worktree+branch with a generic ``PUSH_FAILED ... — race or remote
    error`` message. Operators could not distinguish a hook decline from
    a non-fast-forward from a race. Two contracts pinned here:

    1. The push stderr must reach the operator.
    2. If the push fails but the remote *now* has the branch, the failure
       is a winning race — keep the worktree and local branch, return
       ``None`` with a clear ``BRANCH_ON_REMOTE`` signal, and DO NOT
       invoke ``remove_worktree`` (which would also ``git branch -D`` the
       local branch the operator might want to push to a different
       remote).
    """

    def _make_issue(self):
        from datetime import datetime, timezone

        from deviate.state.ledger import IssueRecord

        return IssueRecord(
            issue_id="ISS-001-PUSH",
            type="feature",
            title="Test push failure",
            source_file="specs/test-epic/issues/iss-001-push.md",
            timestamp=datetime.now(timezone.utc),
        )

    def _push_failing_env(
        self,
        tmp_path: Path,
        *,
        pre_remote_has_branch: bool,
        post_remote_has_branch: bool,
        push_stderr: str,
    ):
        """Wire up a ``_try_claim_issue`` call where ``git push`` fails.

        Returns ``(issue, repo_root, ledger_path, push_calls)``. The push
        call list lets the test assert which subprocess argv triggered
        the failure path.
        """
        import subprocess as _subprocess

        from deviate.cli.meso import _try_claim_issue

        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        ledger_path = tmp_path / "specs" / "issues.jsonl"
        ledger_path.parent.mkdir(parents=True)
        wt_path = tmp_path / "wt"
        wt_path.mkdir()

        # Real git subprocesses (for the non-push plumbing) plus a
        # targeted push failure injected by argv matching.
        push_calls: list[list[str]] = []
        real_run = _subprocess.run

        def selective_run(argv, *args, **kwargs):
            if isinstance(argv, list) and argv[:2] == ["git", "push"]:
                push_calls.append(list(argv))
                return _subprocess.CompletedProcess(
                    args=argv,
                    returncode=1,
                    stdout=b"",
                    stderr=push_stderr.encode("utf-8"),
                )
            return real_run(argv, *args, **kwargs)

        # branch_exists_on_remote is called twice in the new flow:
        # once pre-flight (pre_remote_has_branch), once post-push
        # (post_remote_has_branch). Patch it directly so we control the
        # exact check ordering without needing a real remote.
        remote_states = iter([pre_remote_has_branch, post_remote_has_branch])

        def fake_branch_exists(*_args, **_kwargs):
            return next(remote_states)

        return (
            repo_root,
            ledger_path,
            wt_path,
            _try_claim_issue,
            selective_run,
            fake_branch_exists,
        )

    def test_push_failure_surfaces_stderr_and_rolls_back(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Push fails AND remote has no branch → surface stderr, roll back.

        Pre-fix: operator saw ``PUSH_FAILED ... — race or remote error``
        and the local branch was deleted. Post-fix: operator sees the
        real stderr and the rollback path is taken (real failure, not a
        race).
        """

        (
            repo_root,
            ledger_path,
            wt_path,
            _try_claim,
            selective_run,
            fake_branch_exists,
        ) = self._push_failing_env(
            tmp_path,
            pre_remote_has_branch=False,
            post_remote_has_branch=False,
            push_stderr="remote: hook declined: missing signed-off-by",
        )

        # Track rollback invocations so we can assert it ran.
        rollback_calls: list[tuple[str, Path]] = []

        def fake_remove(branch: str, path: Path, repo=None):  # noqa: ARG001
            rollback_calls.append((branch, path))

        monkeypatch.setattr("deviate.cli.meso.subprocess.run", selective_run)
        monkeypatch.setattr(
            "deviate.cli.meso.find_worktree_for_branch", lambda *a, **k: None
        )
        monkeypatch.setattr("deviate.cli.meso.create_worktree", lambda *a, **k: wt_path)
        monkeypatch.setattr(
            "deviate.cli.meso.branch_exists_on_remote", fake_branch_exists
        )
        monkeypatch.setattr("deviate.cli.meso.claim_issue", lambda *a, **k: True)
        monkeypatch.setattr(
            "deviate.cli.meso._sync_worktree_assets",
            lambda *a, **k: None,
        )
        monkeypatch.setattr("deviate.cli.meso._setup_mise", lambda *a, **k: None)
        monkeypatch.setattr("deviate.cli.meso.remove_worktree", fake_remove)

        result = _try_claim(self._make_issue(), repo_root, ledger_path, remote="origin")

        # Stderr reached the operator.
        captured = capsys.readouterr()
        assert "missing signed-off-by" in captured.out, (
            f"push stderr not surfaced; got output={captured.out!r}"
        )
        assert "PUSH_FAILED" in captured.out

        # Rollback ran because the remote did NOT gain the branch.
        assert result is None
        assert len(rollback_calls) == 1, (
            f"expected exactly one rollback call, got {rollback_calls}"
        )

    def test_push_failure_treated_as_race_when_remote_now_has_branch(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Push fails AND remote now has the branch → race, no rollback.

        Pre-fix: ``remove_worktree`` ran ``git branch -D`` and destroyed
        the operator's local branch even though the claim had already
        landed on origin (just not via THIS push). Post-fix: detect the
        race, log ``BRANCH_ON_REMOTE``, and keep the worktree + local
        branch intact.
        """

        (
            repo_root,
            ledger_path,
            wt_path,
            _try_claim,
            selective_run,
            fake_branch_exists,
        ) = self._push_failing_env(
            tmp_path,
            pre_remote_has_branch=False,
            post_remote_has_branch=True,
            push_stderr="! [rejected] ... non-fast-forward",
        )

        rollback_calls: list[tuple[str, Path]] = []

        def fake_remove(branch: str, path: Path, repo=None):  # noqa: ARG001
            rollback_calls.append((branch, path))

        monkeypatch.setattr("deviate.cli.meso.subprocess.run", selective_run)
        monkeypatch.setattr(
            "deviate.cli.meso.find_worktree_for_branch", lambda *a, **k: None
        )
        monkeypatch.setattr("deviate.cli.meso.create_worktree", lambda *a, **k: wt_path)
        monkeypatch.setattr(
            "deviate.cli.meso.branch_exists_on_remote", fake_branch_exists
        )
        monkeypatch.setattr("deviate.cli.meso.claim_issue", lambda *a, **k: True)
        monkeypatch.setattr(
            "deviate.cli.meso._sync_worktree_assets",
            lambda *a, **k: None,
        )
        monkeypatch.setattr("deviate.cli.meso._setup_mise", lambda *a, **k: None)
        monkeypatch.setattr("deviate.cli.meso.remove_worktree", fake_remove)

        result = _try_claim(self._make_issue(), repo_root, ledger_path, remote="origin")

        captured = capsys.readouterr()
        # Race signal must be present and rollback must NOT have run.
        assert "BRANCH_ON_REMOTE" in captured.out, (
            f"expected BRANCH_ON_REMOTE race signal; got output={captured.out!r}"
        )
        assert rollback_calls == [], (
            f"winning race must not roll back; got {rollback_calls}"
        )
        assert result is None

    def test_push_failure_force_flag_skips_rollback(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``--force`` keeps the worktree on push failure (existing contract)."""

        (
            repo_root,
            ledger_path,
            wt_path,
            _try_claim,
            selective_run,
            fake_branch_exists,
        ) = self._push_failing_env(
            tmp_path,
            pre_remote_has_branch=False,
            post_remote_has_branch=False,
            push_stderr="could not push",
        )

        rollback_calls: list[tuple[str, Path]] = []

        def fake_remove(branch: str, path: Path, repo=None):  # noqa: ARG001
            rollback_calls.append((branch, path))

        monkeypatch.setattr("deviate.cli.meso.subprocess.run", selective_run)
        monkeypatch.setattr(
            "deviate.cli.meso.find_worktree_for_branch", lambda *a, **k: None
        )
        monkeypatch.setattr("deviate.cli.meso.create_worktree", lambda *a, **k: wt_path)
        monkeypatch.setattr(
            "deviate.cli.meso.branch_exists_on_remote", fake_branch_exists
        )
        monkeypatch.setattr("deviate.cli.meso.claim_issue", lambda *a, **k: True)
        monkeypatch.setattr(
            "deviate.cli.meso._sync_worktree_assets",
            lambda *a, **k: None,
        )
        monkeypatch.setattr("deviate.cli.meso._setup_mise", lambda *a, **k: None)
        monkeypatch.setattr("deviate.cli.meso.remove_worktree", fake_remove)

        result = _try_claim(
            self._make_issue(),
            repo_root,
            ledger_path,
            remote="origin",
            force=True,
        )

        captured = capsys.readouterr()
        assert "PUSH_FAILED" in captured.out
        assert "continuing (--force)" in captured.out
        assert rollback_calls == [], (
            f"--force must keep the worktree; got {rollback_calls}"
        )
        assert result is not None
        assert result["worktree_path"] == str(wt_path)


def seed_adhoc_018_origin_rejecting_name(repo: Path) -> Path:
    """Seed ``ISS-ADH-018`` and a bare origin that rejects ``018-*`` names.

    The update hook declines ``refs/heads/feat/adhoc/018-*`` with
    ``already exists`` so the claim path hits a rejected push, not the
    ``BRANCH_ON_REMOTE`` pre-check. Returns the bare origin path.
    """
    import subprocess
    from datetime import datetime, timezone

    from deviate.state.ledger import IssueRecord, append_issue_transition
    from tests.conftest import _git_env

    specs = repo / "specs"
    specs.mkdir(exist_ok=True)
    ledger = specs / "issues.jsonl"
    append_issue_transition(
        IssueRecord(
            issue_id="ISS-ADH-018",
            type="feature",
            title="Collision retry",
            status="BACKLOG",
            source_file="specs/adhoc/issues/018-collision.md",
            timestamp=datetime.now(timezone.utc),
        ),
        ledger,
    )
    subprocess.run(
        ["git", "add", "specs/issues.jsonl"],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "seed ISS-ADH-018"],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )

    bare = repo.parent / f"{repo.name}-origin.git"
    subprocess.run(
        ["git", "init", "--bare", str(bare)],
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    hook = bare / "hooks" / "update"
    hook.write_text(
        "#!/bin/sh\n"
        "refname=$1\n"
        'case "$refname" in\n'
        "refs/heads/feat/adhoc/018-*)\n"
        '  echo "already exists" >&2\n'
        "  exit 1\n"
        "  ;;\n"
        "esac\n"
        "exit 0\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    subprocess.run(
        ["git", "remote", "set-url", "origin", str(bare)],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "origin", "HEAD:refs/heads/main"],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "update-ref", "refs/remotes/origin/main", "HEAD"],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    return bare


def _adhoc_018_issue():
    from datetime import datetime, timezone

    from deviate.state.ledger import IssueRecord

    return IssueRecord(
        issue_id="ISS-ADH-018",
        type="feature",
        title="Collision retry",
        status="BACKLOG",
        source_file="specs/adhoc/issues/018-collision.md",
        timestamp=datetime.now(timezone.utc),
    )


class TestSpecifyPushNameCollisionRetry:
    """AC-PLAN-003: rejected ``feat/adhoc/018-*`` push increments and retries.

    Default claim mode stays on (``local=False``). A name-collision push
    must retry ``019`` and must not win via ``--local`` or keep the
    colliding ``018`` name.
    """

    def test_rejected_018_push_retries_019_and_does_not_set_local(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import subprocess

        from deviate.cli.meso import _try_claim_issue
        from tests.conftest import _git_env

        seed_adhoc_018_origin_rejecting_name(tmp_git_repo)
        monkeypatch.setattr("deviate.cli.meso._setup_mise", lambda *a, **k: None)

        push_calls: list[list[str]] = []
        real_run = subprocess.run

        def recording(argv, *args, **kwargs):
            if isinstance(argv, list) and argv[:2] == ["git", "push"]:
                push_calls.append(list(argv))
            return real_run(argv, *args, **kwargs)

        monkeypatch.setattr("deviate.cli.meso.subprocess.run", recording)

        result = _try_claim_issue(
            _adhoc_018_issue(),
            tmp_git_repo,
            tmp_git_repo / "specs" / "issues.jsonl",
            remote="origin",
            local=False,
        )

        captured = capsys.readouterr()
        assert "LOCAL_ONLY" not in captured.out, (
            f"collision retry must not skip push via --local; output={captured.out!r}"
        )
        assert result is not None, (
            "expected claim to succeed after incrementing to 019; "
            f"output={captured.out!r} pushes={push_calls!r}"
        )
        assert result["branch"].startswith("feat/adhoc/019-"), (
            f"winner must be 019-*, not the colliding 018 name: {result['branch']!r}"
        )
        assert not result["branch"].startswith("feat/adhoc/018-"), (
            f"colliding 018 name must not remain the winner: {result['branch']!r}"
        )

        pushed_branches = [call[-1] for call in push_calls if call]
        assert any(
            branch.startswith("feat/adhoc/018-") for branch in pushed_branches
        ), f"first push must attempt 018-*: {push_calls!r}"
        assert any(
            branch.startswith("feat/adhoc/019-") for branch in pushed_branches
        ), f"retry push must attempt 019-*: {push_calls!r}"

        remote_019 = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", result["branch"]],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
            text=True,
        )
        assert remote_019.stdout.strip(), (
            "winning branch must exist on origin (not a local-only win): "
            f"{result['branch']!r}"
        )
