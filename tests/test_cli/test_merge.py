"""Tests for `deviate merge` CLI — covering staged-then-commit, worktree-aware
branch deletion, and porcelain check semantics.

These tests pin down three regressions discovered in the ISS-ADH-012 squash
merge:

1. ``_merge_run`` short-circuited on ``ALREADY_COMPLETED`` when ``--stage-only``
   was followed by ``--message``, silently skipping the final ``git commit``.
2. ``--delete-branch`` failed with ``branch in use by worktree`` because the CLI
   did not remove the worktree before running ``git branch -D``.
3. The skill template's porcelain check treated staged changes as unstaged,
   spuriously halting every successful squash-merge.
"""

from __future__ import annotations

import os
import subprocess
from contextlib import chdir
from datetime import datetime, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState
from deviate.state.ledger import IssueRecord, resolve_issue_record


def _git_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def merge_repo(tmp_git_repo: Path) -> Path:
    """A tmp_git_repo with a feature branch (ahead of main by exactly one
    feature commit), a worktree that holds the branch, and an active
    DeviaTDD session — the minimal state needed to exercise ``deviate merge``.
    """
    repo = tmp_git_repo
    worktrees_dir = repo / ".worktrees"
    worktrees_dir.mkdir()
    branch = "feat/test-bucket/iss-test-001"
    wt_path = worktrees_dir / "feat-test-bucket-iss-test-001"

    # Create the feature branch (initially at HEAD) and a worktree for it
    subprocess.run(
        ["git", "branch", branch],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git",
            "worktree",
            "add",
            str(wt_path),
            branch,
        ],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )

    # Add one feature commit on the branch (so squash-merge has work to bring in)
    (wt_path / "feature.txt").write_text("new feature\n")
    subprocess.run(
        ["git", "add", "feature.txt"],
        cwd=wt_path,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "feat: add feature"],
        cwd=wt_path,
        env=_git_env(),
        check=True,
        capture_output=True,
    )

    # Seed the .deviate/ directory + session + ledger on the main checkout
    dot_dir = repo / ".deviate"
    dot_dir.mkdir(exist_ok=True)
    session = SessionState(current_phase="TASKS", active_issue_id="ISS-TEST-001")
    session.save(dot_dir / "session.json")

    spec_root = repo / "specs"
    spec_root.mkdir(exist_ok=True)
    (spec_root / "constitution.md").write_text("# Constitution\n")
    issue_dir = spec_root / "test-bucket" / "issues"
    issue_dir.mkdir(parents=True, exist_ok=True)
    (issue_dir / "iss-test-001.md").write_text("# Test issue\n")

    record = IssueRecord(
        issue_id="ISS-TEST-001",
        type="feature",
        title="Test feature for merge",
        status="SPECIFIED",
        source_file="specs/test-bucket/issues/iss-test-001.md",
        timestamp=datetime.now(timezone.utc),
    )
    ledger = spec_root / "issues.jsonl"
    ledger.write_text(record.model_dump_json() + "\n")

    # Commit the ledger + spec files on the main checkout so they're available
    # to ``git merge --squash`` from main's perspective
    subprocess.run(
        ["git", "add", "specs", ".deviate"],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "chore: seed ledger + session"],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )

    return repo


# ---------------------------------------------------------------------------
# Bug (a): _merge_run short-circuits on ALREADY_COMPLETED when --stage-only
# precedes --message.
# ---------------------------------------------------------------------------


def test_merge_stage_only_then_message_creates_commit(merge_repo: Path) -> None:
    """Regression: ``--stage-only`` then ``--message`` must create a single
    commit. The previous implementation printed ``ALREADY_COMPLETED`` and
    skipped the commit because the ledger was already COMPLETED in the JSONL.
    """
    repo = merge_repo
    ledger = repo / "specs" / "issues.jsonl"

    with chdir(repo):
        # Simulate the skill's workflow: squash-merge the feature branch,
        # then stage the ledger via --stage-only, then commit via --message.
        result_merge = subprocess.run(
            ["git", "merge", "--squash", "feat/test-bucket/iss-test-001"],
            cwd=repo,
            env=_git_env(),
            check=True,
            capture_output=True,
            text=True,
        )
        assert "Automatic merge went well" in result_merge.stderr

        # Stage the ledger
        runner = CliRunner()
        stage_result = runner.invoke(
            cli, ["merge", "--issue", "ISS-TEST-001", "--stage-only"]
        )
        assert stage_result.exit_code == 0, stage_result.output
        assert "LEDGER_STAGED" in stage_result.output

        # Now commit — this is the step that short-circuited
        commit_result = runner.invoke(
            cli,
            [
                "merge",
                "--issue",
                "ISS-TEST-001",
                "-m",
                "feat(ISS-TEST-001): squash merge test feature",
                "-m",
                "Body paragraph 1",
                "-m",
                "Body paragraph 2",
                "-m",
                "Closes ISS-TEST-001",
            ],
        )
        assert commit_result.exit_code == 0, commit_result.output
        assert "COMMITTED" in commit_result.output, (
            "Expected COMMITTED output but merge CLI short-circuited on "
            "ALREADY_COMPLETED. Output: " + commit_result.output
        )

        # Verify a commit was actually created
        head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            env=_git_env(),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert head_sha, "HEAD must be a valid sha after commit"

        # Verify the commit message
        log_output = subprocess.run(
            ["git", "log", "-1", "--format=%s%n---%n%b"],
            cwd=repo,
            env=_git_env(),
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert "feat(ISS-TEST-001): squash merge test feature" in log_output
        assert "Body paragraph 1" in log_output
        assert "Body paragraph 2" in log_output
        assert "Closes ISS-TEST-001" in log_output

        # Verify the ledger has the COMPLETED transition (not just SPECIFIED)
        record = resolve_issue_record("ISS-TEST-001", ledger)
        assert record is not None
        assert record.status == "COMPLETED"


# ---------------------------------------------------------------------------
# Bug (b): --delete-branch fails when branch is checked out in a worktree.
# ---------------------------------------------------------------------------


def test_delete_branch_removes_worktree_first(merge_repo: Path) -> None:
    """Regression: --delete-branch must remove the worktree that holds the
    branch before attempting ``git branch -D``. The previous implementation
    crashed with ``cannot delete branch ... used by worktree``.
    """
    repo = merge_repo
    wt_path = repo / ".worktrees" / "feat-test-bucket-iss-test-001"
    branch = "feat/test-bucket/iss-test-001"

    # Sanity: worktree exists and branch is checked out there
    assert wt_path.exists()
    worktree_list = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert branch in worktree_list

    with chdir(repo):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "merge",
                "--issue",
                "ISS-TEST-001",
                "--delete-branch",
            ],
        )

    # The CLI should have removed the worktree and deleted the branch
    # without crashing. We tolerate an ALREADY_COMPLETED warning since
    # the test fixture may already have the issue in COMPLETED state.
    assert result.exit_code == 0, (
        f"--delete-branch crashed when worktree exists:\n{result.output}"
    )
    assert "BRANCH_DELETED" in result.output or "BRANCH_SKIP" in result.output

    # Branch must be gone from git's branch listing
    branch_list = subprocess.run(
        ["git", "branch", "--list", branch],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert branch not in branch_list, (
        f"Branch {branch} should have been deleted but is still present:\n{branch_list}"
    )

    # Worktree must be gone
    assert not wt_path.exists(), f"Worktree at {wt_path} should have been removed"


# ---------------------------------------------------------------------------
# --delete-branch archive tag + remote branch delete
# ---------------------------------------------------------------------------


def test_delete_branch_creates_archive_tag_locally(merge_repo: Path) -> None:
    """``--delete-branch`` must tag the pre-squash branch tip with
    ``archive/<ISSUE_ID>/<YYYY-MM-DD>`` (UTC date) so the per-commit graph
    survives ``git merge --squash``.
    """
    repo = merge_repo
    branch = "feat/test-bucket/iss-test-001"

    pre_branch_tip = subprocess.run(
        ["git", "rev-parse", branch],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    with chdir(repo):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "merge",
                "--issue",
                "ISS-TEST-001",
                "--delete-branch",
            ],
        )

    assert result.exit_code == 0, result.output
    today = datetime.now(timezone.utc).date().isoformat()
    expected_tag = f"archive/ISS-TEST-001/{today}"
    assert expected_tag in result.output, (
        f"Expected archive tag {expected_tag} in output:\n{result.output}"
    )
    assert "ARCHIVE_TAG" in result.output

    tag_sha = subprocess.run(
        ["git", "rev-parse", expected_tag],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert tag_sha == pre_branch_tip, (
        f"Archive tag must point at the pre-squash branch tip "
        f"({pre_branch_tip}); got {tag_sha}"
    )

    branch_list = subprocess.run(
        ["git", "branch", "--list", branch],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert branch not in branch_list, (
        f"Branch {branch} should have been deleted:\n{branch_list}"
    )


def test_delete_branch_pushes_tag_and_deletes_remote_with_bare_origin(
    merge_repo: Path, tmp_path: Path
) -> None:
    """``--delete-branch`` against a real bare ``origin`` must push the
    archive tag to origin and ``git push origin --delete`` the remote
    branch. End-to-end happy path.
    """
    repo = merge_repo
    branch = "feat/test-bucket/iss-test-001"

    bare = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(bare)],
        cwd=tmp_path,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "remote", "remove", "origin"],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare)],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "origin", branch],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    )
    assert (
        subprocess.run(
            ["git", "ls-remote", "--heads", "origin", branch],
            cwd=repo,
            env=_git_env(),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        != ""
    ), "sanity: branch must exist on origin before cleanup"

    with chdir(repo):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "merge",
                "--issue",
                "ISS-TEST-001",
                "--delete-branch",
            ],
        )

    assert result.exit_code == 0, result.output
    assert "ARCHIVE_PUSHED" in result.output, result.output
    assert "REMOTE_BRANCH_DELETED" in result.output, result.output
    assert "BRANCH_DELETED" in result.output, result.output
    assert "WORKTREE_REMOVED" in result.output, result.output

    today = datetime.now(timezone.utc).date().isoformat()
    expected_tag = f"archive/ISS-TEST-001/{today}"
    ls_tags = subprocess.run(
        ["git", "ls-remote", "--tags", "origin", expected_tag],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert ls_tags != "", (
        f"Archive tag {expected_tag} must exist on origin, got: {ls_tags!r}"
    )

    ls_branch = subprocess.run(
        ["git", "ls-remote", "--heads", "origin", branch],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert ls_branch == "", (
        f"Branch {branch} must be deleted from origin, got: {ls_branch!r}"
    )


def test_delete_branch_with_unreachable_origin_warns_and_continues(
    merge_repo: Path,
) -> None:
    """``--delete-branch`` with an unreachable remote must print
    ``PUSH_WARN`` and still complete local cleanup (archive tag, worktree
    removal, branch delete). The archive tag MUST still exist locally —
    losing the squash-merged history is not recoverable from ``main``.
    """
    repo = merge_repo
    # Override the inherited fake origin to a path that fails immediately
    # rather than hanging on DNS.
    subprocess.run(
        [
            "git",
            "remote",
            "set-url",
            "origin",
            "file:///definitely-not-a-real-remote.git",
        ],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )

    with chdir(repo):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "merge",
                "--issue",
                "ISS-TEST-001",
                "--delete-branch",
            ],
        )

    assert result.exit_code == 0, (
        f"--delete-branch must continue past remote failures:\n{result.output}"
    )
    assert "ARCHIVE_TAG" in result.output, result.output
    assert "BRANCH_DELETED" in result.output or "BRANCH_SKIP" in result.output, (
        result.output
    )
    assert "WORKTREE_REMOVED" in result.output, result.output
    assert "PUSH_WARN" in result.output, result.output

    today = datetime.now(timezone.utc).date().isoformat()
    tag = f"archive/ISS-TEST-001/{today}"
    tag_check = subprocess.run(
        ["git", "tag", "--list", tag],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert tag == tag_check, (
        f"Archive tag {tag} must exist locally even when remote push "
        f"fails; got: {tag_check!r}"
    )


def test_delete_branch_with_no_origin_skips_remote_ops_silently(
    merge_repo: Path,
) -> None:
    """Without an ``origin`` remote, ``--delete-branch`` must skip the tag
    push and remote branch delete silently — no ``PUSH_WARN``, since the
    absence of a remote is not an error condition.
    """
    repo = merge_repo
    subprocess.run(
        ["git", "remote", "remove", "origin"],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )

    with chdir(repo):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "merge",
                "--issue",
                "ISS-TEST-001",
                "--delete-branch",
            ],
        )

    assert result.exit_code == 0, result.output
    assert "ARCHIVE_TAG" in result.output, result.output
    assert "BRANCH_DELETED" in result.output or "BRANCH_SKIP" in result.output, (
        result.output
    )
    assert "PUSH_WARN" not in result.output, (
        f"No PUSH_WARN should be emitted when origin is not configured:\n"
        f"{result.output}"
    )
    assert "ARCHIVE_PUSHED" not in result.output
    assert "REMOTE_BRANCH_DELETED" not in result.output
    assert "REMOTE_BRANCH_SKIP" not in result.output


# ---------------------------------------------------------------------------
# Bug (c): Staging check distinguishes staged from unstaged.
#
# This is a skill-template behavior, but we encode it as a helper function
# ``_git_status_unstaged`` so the porcelain interpretation is reproducible
# and pinned.
# ---------------------------------------------------------------------------


def _git_status_unstaged(cwd: Path) -> list[str]:
    """Return only unstaged + untracked lines from ``git status --porcelain``.

    Staged-only lines (``M  foo``, ``A  foo``) are filtered out. `` M foo``,
    `` M foo``, ``D  foo``, and ``?? foo`` are kept.
    """
    out = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=cwd,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    unstaged = []
    for line in out.splitlines():
        if not line:
            continue
        # Porcelain format: XY filename
        # X = index status (staged), Y = worktree status (unstaged)
        # We only want lines where Y is non-space (unstaged change exists)
        if len(line) >= 2 and line[1] != " ":
            unstaged.append(line)
    return unstaged


def test_porcelain_filter_excludes_staged_only_changes(tmp_path: Path) -> None:
    """The staging check used by the merge skill must NOT flag a clean
    squash-merge (where all changes are staged) as a failure.
    """
    repo = tmp_path
    subprocess.run(["git", "init"], cwd=repo, env=_git_env(), check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"],
        cwd=repo,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "T"],
        cwd=repo,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=repo,
        env=_git_env(),
        check=True,
    )

    # Create a new file and stage it (simulate squash-merge result)
    (repo / "new.txt").write_text("content")
    subprocess.run(
        ["git", "add", "new.txt"],
        cwd=repo,
        env=_git_env(),
        check=True,
    )

    # Full porcelain shows the staged change
    full = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "A  new.txt" in full  # staged only

    # But our filtered view (staged-only excluded) must be empty
    unstaged = _git_status_unstaged(repo)
    assert unstaged == [], (
        f"Staged-only changes must not trigger the unstaged-files failure "
        f"check, but got: {unstaged}"
    )


def test_porcelain_filter_detects_actual_unstaged_changes(tmp_path: Path) -> None:
    """Conversely, real unstaged changes (modified file with no `git add`)
    must still be flagged.
    """
    repo = tmp_path
    subprocess.run(["git", "init"], cwd=repo, env=_git_env(), check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"],
        cwd=repo,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "T"],
        cwd=repo,
        env=_git_env(),
        check=True,
    )
    (repo / "tracked.txt").write_text("v1\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, env=_git_env(), check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo,
        env=_git_env(),
        check=True,
    )

    # Modify without staging
    (repo / "tracked.txt").write_text("v2\n")
    unstaged = _git_status_unstaged(repo)
    assert len(unstaged) == 1
    assert " M tracked.txt" in unstaged[0]


# ---------------------------------------------------------------------------
# CONTRIBUTING.md / .commit-convention.md convention detection.
#
# These regression tests pin the contract that ``deviate merge --message`` reads
# the project convention file (CONTRIBUTING.md or .commit-convention.md) and
# routes the subject through ``format_commit_message``.  Without this pin, a
# future refactor of the helper could silently drop the emoji prefix and no
# merge-side test would notice.
#
# **Cost note**: Unlike the rest of ``test_merge.py`` (which stage via the
# CLI's ``--stage-only`` path against a pre-prepared index), these two tests
# drive a full ``git merge --squash`` from a feature branch + a real
# ``deviate merge --stage-only`` + a real ``deviate merge --message`` cycle so
# we can assert on the resulting ``git log -1`` subject end-to-end.  Each test
# takes ~0.3s in isolation.  The pair is bounded at <1s in the suite and
# cannot be replaced with a pure ``format_commit_message`` unit test because
# the regression we are guarding against is a *missed wiring* in
# ``_merge_run``, not in the helper itself.
# ---------------------------------------------------------------------------


def _merge_repo_with_convention(merge_repo: Path, contributing_text: str) -> Path:
    """Write a CONTRIBUTING.md on top of ``merge_repo`` and re-seed the seed
    commit so the file is part of main's history (the merge CLI runs from
    main, and ``git merge --squash`` brings the branch's diff onto main).
    """
    repo = merge_repo
    (repo / "CONTRIBUTING.md").write_text(contributing_text, encoding="utf-8")
    subprocess.run(
        ["git", "add", "CONTRIBUTING.md"],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "docs: add CONTRIBUTING.md"],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )
    return repo


def test_merge_honors_contributing_md_emoji_prefix(merge_repo: Path) -> None:
    """``CONTRIBUTING.md`` declaring an emoji convention must cause
    ``deviate merge --message`` to prefix the HEAD subject with the matching
    gitmoji.  Pins that the merge CLI reads CONTRIBUTING.md (via
    ``format_commit_message`` -> ``detect_uses_emojis`` ->
    ``_read_convention_file``) rather than relying on the no-op default.
    """
    repo = _merge_repo_with_convention(
        merge_repo,
        "# Contributing\n\n"
        "Use gitmoji on every commit, e.g. ✨ for features, 🐛 for fixes.\n",
    )
    runner = CliRunner()

    with chdir(repo):
        subprocess.run(
            ["git", "merge", "--squash", "feat/test-bucket/iss-test-001"],
            cwd=repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        stage = runner.invoke(cli, ["merge", "--issue", "ISS-TEST-001", "--stage-only"])
        assert stage.exit_code == 0, stage.output

        commit = runner.invoke(
            cli,
            [
                "merge",
                "--issue",
                "ISS-TEST-001",
                "-m",
                "feat(ISS-TEST-001): squash merge test feature",
                "-m",
                "Body paragraph 1",
                "-m",
                "Closes ISS-TEST-001",
            ],
        )
        assert commit.exit_code == 0, commit.output
        assert "COMMITTED" in commit.output, commit.output

        log = subprocess.run(
            ["git", "log", "-1", "--format=%s%n---%n%b"],
            cwd=repo,
            env=_git_env(),
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    # Subject is prefixed with the feat gitmoji (✨) and unchanged otherwise.
    assert log.startswith("\u2728 feat(ISS-TEST-001): squash merge test feature"), log
    # Body paragraphs are not rewritten — only the subject gets the prefix.
    assert "Body paragraph 1" in log
    assert "Closes ISS-TEST-001" in log


def test_merge_no_emoji_prefix_when_contributing_md_has_no_emoji(
    merge_repo: Path,
) -> None:
    """When ``CONTRIBUTING.md`` exists but contains no emoji, the merge CLI
    must NOT prepend a prefix.  This locks the no-op path: the convention
    detector falls through to ``_git_log_has_emojis``, which also returns
    False on this clean repo, so the subject passes through unchanged.
    """
    repo = _merge_repo_with_convention(
        merge_repo,
        "# Contributing\n\n"
        "Use the conventional-commit format: <type>(<scope>): <description>.\n"
        "Body lines wrap at 72 characters.\n",
    )
    runner = CliRunner()

    with chdir(repo):
        subprocess.run(
            ["git", "merge", "--squash", "feat/test-bucket/iss-test-001"],
            cwd=repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        stage = runner.invoke(cli, ["merge", "--issue", "ISS-TEST-001", "--stage-only"])
        assert stage.exit_code == 0, stage.output

        commit = runner.invoke(
            cli,
            [
                "merge",
                "--issue",
                "ISS-TEST-001",
                "-m",
                "feat(ISS-TEST-001): squash merge test feature",
                "-m",
                "Body paragraph 1",
            ],
        )
        assert commit.exit_code == 0, commit.output
        assert "COMMITTED" in commit.output, commit.output

        log = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=repo,
            env=_git_env(),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.rstrip("\n")

    # No emoji prefix — the detector returned False.
    assert log == "feat(ISS-TEST-001): squash merge test feature", log
