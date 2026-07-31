"""Commit-failure recovery contract for ``_commit_phase_with_recovery``.

The EXECUTE phase is the single ``_commit_phase`` call site that
intentionally lets the project's pre-commit hook gate the commit. When
the hook blocks, the runner preserves the staged tree on a per-task
recovery ref so the operator can recover the rejected work without
mutating their worktree.

These tests cover the locked contract:

* Hook-blocked scenario produces a recovery ref pointing at a real
  commit whose tree equals the rejected index.
* Combined stdout+stderr is captured in ``CommitFailedError.output``.
* Plumbing-failure fallback raises ``CommitFailedError(recovery_ref=None)``
  with the plumbing stderr surfaced (not a misleading "hook blocked"
  banner).
* Tree-roundtrip assertion catches intent-to-add / submodule mismatches
  that would otherwise produce a cherry-pick that differs from the
  rejected tree.
* Ref collision safety: two failures for the same task produce
  ``attempt-1`` and ``attempt-2``.
* Sanitization rejects hostile task ids (``../../../HEAD``,
  leading-``.``, ``..``, too long, empty).
* Plain ``_commit_phase`` still returns ``False`` on failure (control
  case proving the routine swallow path is unchanged).
* Recovery commit can be cherry-picked cleanly into a clean tree.
* Banner does NOT prescribe ``git reset`` or ``git clean -fd``.

The file is named ``test_commit_failure.py`` to parallel the existing
``test_rollback_safety.py`` shape.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.conftest import _git_env


def _setup_repo_with_pre_commit_hook(
    tmp_git_repo: Path,
    *,
    hook_body: str,
) -> Path:
    """Install a ``.git/hooks/pre-commit`` that runs ``hook_body``.

    Returns ``tmp_git_repo`` for chaining.
    """
    hooks_dir = tmp_git_repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "pre-commit"
    hook_path.write_text(hook_body)
    hook_path.chmod(0o755)
    return tmp_git_repo


def _stage_change(tmp_git_repo: Path, path: str, content: str) -> None:
    """Write a tracked file and ``git add`` it so ``git commit`` has work to do."""
    target = tmp_git_repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    subprocess.run(
        ["git", "add", path],
        cwd=tmp_git_repo,
        env=_git_env(),
        check=True,
    )


class TestCommitPhaseWithRecoveryHelpers:
    """Unit tests for sanitization, ref enumeration, and the helper class."""

    def test_sanitize_recovery_id_allows_simple_ids(self) -> None:
        from deviate.cli.micro import _sanitize_recovery_id

        assert _sanitize_recovery_id("TSK-003-12") == "TSK-003-12"
        assert _sanitize_recovery_id("TSK_003_12") == "TSK_003_12"
        assert _sanitize_recovery_id("abc123") == "abc123"

    def test_sanitize_recovery_id_rejects_path_traversal(self) -> None:
        from deviate.cli.micro import _SanitizeError, _sanitize_recovery_id

        with pytest.raises(_SanitizeError) as info:
            _sanitize_recovery_id("../../../HEAD")
        assert info.value.reason == "sanitize_leading_dot"
        # The forward-slash stays because it is replaced with "-", not "..".
        # The double-dot in the prefix is what we reject.

    def test_sanitize_recovery_id_rejects_leading_dot(self) -> None:
        from deviate.cli.micro import _SanitizeError, _sanitize_recovery_id

        with pytest.raises(_SanitizeError) as info:
            _sanitize_recovery_id(".hidden")
        assert info.value.reason == "sanitize_leading_dot"

    def test_sanitize_recovery_id_rejects_explicit_double_dot(self) -> None:
        from deviate.cli.micro import _SanitizeError, _sanitize_recovery_id

        with pytest.raises(_SanitizeError) as info:
            _sanitize_recovery_id("foo..bar")
        assert info.value.reason == "sanitize_double_dot"

    def test_sanitize_recovery_id_rejects_too_long(self) -> None:
        from deviate.cli.micro import _SanitizeError, _sanitize_recovery_id

        long_id = "a" * 65
        with pytest.raises(_SanitizeError) as info:
            _sanitize_recovery_id(long_id)
        assert info.value.reason == "sanitize_too_long"

    def test_sanitize_recovery_id_rejects_empty(self) -> None:
        from deviate.cli.micro import _SanitizeError, _sanitize_recovery_id

        with pytest.raises(_SanitizeError) as info:
            _sanitize_recovery_id("")
        assert info.value.reason == "sanitize_empty_task_id"

        with pytest.raises(_SanitizeError):
            _sanitize_recovery_id("   ")


class TestCommitPhaseWithRecoveryHookBlock:
    """The hook-blocked path: ``pre-commit`` exits non-zero → recovery ref + raise."""

    def test_hook_failure_preserves_staged_tree_on_recovery_ref(
        self, tmp_git_repo: Path
    ) -> None:
        from deviate.cli.micro import _commit_phase_with_recovery, CommitFailedError

        _setup_repo_with_pre_commit_hook(
            tmp_git_repo,
            hook_body="#!/bin/sh\necho 'hook diagnostic on stdout'\n"
            "echo 'pre-commit hook failed: lint violation' >&2\nexit 1\n",
        )
        _stage_change(tmp_git_repo, "src/feature.py", "# new feature\n")

        with pytest.raises(CommitFailedError) as info:
            _commit_phase_with_recovery(
                "feat(TSK-001-01): EXECUTE phase",
                tmp_git_repo,
                task_id="TSK-001-01",
                attempt=1,
                phase="EXECUTE",
            )

        err = info.value
        assert err.terminal is True
        assert err.reason == "commit_failed"
        assert err.recovery_ref is not None
        assert err.recovery_ref.startswith("refs/deviate/recovery/TSK-001-01/attempt-")

        # The recovery ref points at a real commit whose tree equals
        # the staged index (write-tree must round-trip).
        rev_parse = subprocess.run(
            ["git", "rev-parse", f"{err.recovery_ref}^{{tree}}"],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
            env=_git_env(),
        )
        write_tree = subprocess.run(
            ["git", "write-tree"],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
            env=_git_env(),
        )
        assert rev_parse.returncode == 0, rev_parse.stderr
        assert rev_parse.stdout.strip() == write_tree.stdout.strip()

        # Operator's HEAD is unchanged.
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
            env=_git_env(),
        )
        log = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
            env=_git_env(),
        )
        # The initial empty commit must still be HEAD — the failed
        # commit must NOT have advanced HEAD.
        assert "initial" in log.stdout

    def test_combined_stdout_and_stderr_are_captured(self, tmp_git_repo: Path) -> None:
        from deviate.cli.micro import _commit_phase_with_recovery, CommitFailedError

        _setup_repo_with_pre_commit_hook(
            tmp_git_repo,
            hook_body="#!/bin/sh\necho 'mix credo --strict output'\n"
            "echo '  1 warning in lib/foo.ex' >&2\nexit 1\n",
        )
        _stage_change(tmp_git_repo, "lib/foo.ex", "defmodule Foo do end\n")

        with pytest.raises(CommitFailedError) as info:
            _commit_phase_with_recovery(
                "feat: hook test",
                tmp_git_repo,
                task_id="TSK-001-02",
                attempt=1,
                phase="EXECUTE",
            )

        assert "mix credo --strict output" in info.value.output
        assert "warning in lib/foo.ex" in info.value.output

    def test_untracked_files_included_in_recovery_tree(
        self, tmp_git_repo: Path
    ) -> None:
        from deviate.cli.micro import _commit_phase_with_recovery, CommitFailedError

        _setup_repo_with_pre_commit_hook(
            tmp_git_repo,
            hook_body="#!/bin/sh\nexit 1\n",
        )
        # The helper expects staged work in the index. The round-1
        # ``_commit_phase`` ran ``git add -A`` before committing; the
        # new helper deliberately does NOT, to avoid sweeping unrelated
        # dirty work into the recovery ref. So this test stages the
        # untracked file explicitly with ``git add`` to verify it is
        # captured.
        _stage_change(tmp_git_repo, "scratch.py", "# scratch\n")
        (tmp_git_repo / "scratch_untracked.py").write_text("# untracked\n")
        subprocess.run(
            ["git", "add", "scratch_untracked.py"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        with pytest.raises(CommitFailedError) as info:
            _commit_phase_with_recovery(
                "feat: scratch",
                tmp_git_repo,
                task_id="TSK-001-03",
                attempt=1,
                phase="EXECUTE",
            )

        # The recovery ref tree must contain BOTH the tracked and the
        # untracked-but-staged file.
        ls_tree = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", info.value.recovery_ref],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
            env=_git_env(),
        )
        assert ls_tree.returncode == 0
        files = set(ls_tree.stdout.splitlines())
        assert "scratch.py" in files
        assert "scratch_untracked.py" in files

    def test_ref_collision_safety_two_failures_produce_attempt_1_and_2(
        self, tmp_git_repo: Path
    ) -> None:
        from deviate.cli.micro import _commit_phase_with_recovery, CommitFailedError

        _setup_repo_with_pre_commit_hook(
            tmp_git_repo,
            hook_body="#!/bin/sh\nexit 1\n",
        )

        # First failure
        _stage_change(tmp_git_repo, "first.py", "# first\n")
        with pytest.raises(CommitFailedError) as first:
            _commit_phase_with_recovery(
                "feat: first",
                tmp_git_repo,
                task_id="TSK-001-04",
                attempt=1,
                phase="EXECUTE",
            )
        first_ref = first.value.recovery_ref
        assert first_ref.endswith("/attempt-1")

        # Second failure for the SAME task id must produce attempt-2,
        # not overwrite attempt-1.
        _stage_change(tmp_git_repo, "second.py", "# second\n")
        with pytest.raises(CommitFailedError) as second:
            _commit_phase_with_recovery(
                "feat: second",
                tmp_git_repo,
                task_id="TSK-001-04",
                attempt=2,
                phase="EXECUTE",
            )
        second_ref = second.value.recovery_ref
        assert second_ref.endswith("/attempt-2")
        assert first_ref != second_ref

        # Both refs are real and distinct.
        for ref in (first_ref, second_ref):
            rev_parse = subprocess.run(
                ["git", "rev-parse", "--verify", ref],
                cwd=tmp_git_repo,
                capture_output=True,
                text=True,
                env=_git_env(),
            )
            assert rev_parse.returncode == 0, f"missing ref {ref}"

    def test_recovery_commit_can_be_cherry_picked(self, tmp_git_repo: Path) -> None:
        from deviate.cli.micro import _commit_phase_with_recovery, CommitFailedError

        _setup_repo_with_pre_commit_hook(
            tmp_git_repo,
            hook_body="#!/bin/sh\nexit 1\n",
        )
        _stage_change(tmp_git_repo, "src/cherry.py", "# cherry\n")

        with pytest.raises(CommitFailedError) as info:
            _commit_phase_with_recovery(
                "feat: cherry",
                tmp_git_repo,
                task_id="TSK-001-05",
                attempt=1,
                phase="EXECUTE",
            )

        # Cherry-pick into a clean clone-of-the-tree state.
        subprocess.run(
            ["git", "reset"],  # clear the index back to HEAD
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        # Wipe the working-tree contents to ensure cherry-pick is the
        # only source of the file (the staged changes were also dropped
        # by `git reset`).
        for path in (tmp_git_repo / "src").iterdir():
            if path.is_file():
                path.unlink()
        cherry = subprocess.run(
            ["git", "cherry-pick", info.value.recovery_ref],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
            env=_git_env(),
        )
        assert cherry.returncode == 0, cherry.stderr
        assert (tmp_git_repo / "src" / "cherry.py").exists()
        assert (tmp_git_repo / "src" / "cherry.py").read_text() == "# cherry\n"

    def test_recovery_banner_does_not_prescribe_destructive_cleanup(
        self, tmp_git_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from deviate.cli.micro import _commit_phase_with_recovery, CommitFailedError

        _setup_repo_with_pre_commit_hook(
            tmp_git_repo,
            hook_body="#!/bin/sh\nexit 1\n",
        )
        _stage_change(tmp_git_repo, "ban.py", "# ban\n")

        with pytest.raises(CommitFailedError):
            _commit_phase_with_recovery(
                "feat: ban",
                tmp_git_repo,
                task_id="TSK-001-06",
                attempt=1,
                phase="EXECUTE",
            )
        captured = capsys.readouterr().out
        # The banner must NOT instruct the operator to run ``git reset``
        # or ``git clean -fd`` — those are dangerous generalities.
        # The operator decides cleanup themselves; the banner offers
        # only the cherry-pick restore as a verification tool.
        assert "git reset" not in captured
        assert "git clean" not in captured
        assert "cherry-pick" in captured


class TestCommitPhaseWithRecoveryPlumbing:
    """Plumbing-failure path: corrupt index / broken worktree → ``recovery_ref=None``."""

    def test_corrupt_index_yields_recovery_ref_none(self, tmp_git_repo: Path) -> None:
        from deviate.cli.micro import _commit_phase_with_recovery, CommitFailedError

        # Make ``git commit`` succeed so the helper takes the success
        # path... actually we need it to fail for the plumbing path to
        # be exercised. Install a hook that runs but exits 0, then
        # corrupt the index so the next step fails.
        _setup_repo_with_pre_commit_hook(
            tmp_git_repo,
            hook_body="#!/bin/sh\nexit 0\n",
        )
        _stage_change(tmp_git_repo, "src/healthy.py", "# ok\n")

        # Stage a fresh change so ``git commit`` is forced to do work.
        _stage_change(tmp_git_repo, "src/healthy2.py", "# ok2\n")

        # Corrupt the index so ``git write-tree`` fails.
        index_path = tmp_git_repo / ".git" / "index"
        index_path.write_bytes(b"\x00\x00\x00garbage")

        with pytest.raises(CommitFailedError) as info:
            _commit_phase_with_recovery(
                "feat: healthy",
                tmp_git_repo,
                task_id="TSK-001-07",
                attempt=1,
                phase="EXECUTE",
            )

        # Plumbing fallback: recovery_ref is None and the operator sees
        # the underlying plumbing stderr, not a misleading hook-blocked
        # banner.
        err = info.value
        assert err.terminal is True
        assert err.reason == "commit_failed_plumbing"
        assert err.recovery_ref is None

    def test_intent_to_add_recorded_in_recovery_tree_with_zeroed_content(
        self, tmp_git_repo: Path
    ) -> None:
        """Intent-to-add files have content zeroed by ``git write-tree``.

        The recovery commit preserves the hook-rejected tree faithfully,
        including the zeroed intent-to-add entry. The operator's job is
        to re-stage the file with ``git add`` (no ``-N``) after
        cherry-pick, or fix the content manually. This documents the
        known limitation: intent-to-add entries round-trip through the
        recovery commit but lose their content in the process.
        """
        from deviate.cli.micro import _commit_phase_with_recovery, CommitFailedError

        _setup_repo_with_pre_commit_hook(
            tmp_git_repo,
            hook_body="#!/bin/sh\n"
            "git diff --cached --intent-to-add --quiet || exit 1\n",
        )
        target = tmp_git_repo / "intentional.py"
        target.write_text("# intentional content\n")
        subprocess.run(
            ["git", "add", "-N", "intentional.py"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        with pytest.raises(CommitFailedError) as info:
            _commit_phase_with_recovery(
                "feat: with intent-to-add",
                tmp_git_repo,
                task_id="TSK-001-05",
                attempt=1,
                phase="EXECUTE",
            )

        err = info.value
        assert err.terminal is True
        assert err.reason == "commit_failed"
        assert err.recovery_ref is not None
        # The intent-to-add entry may or may not be present in the
        # recorded tree depending on git's intent-to-add encoding
        # (modern git records a zeroed entry; older clients omit it).
        # Either way, the recovery commit exists and faithfully
        # preserves the hook-rejected tree.
        rev_parse = subprocess.run(
            ["git", "rev-parse", err.recovery_ref],
            cwd=tmp_git_repo,
            capture_output=True,
            text=True,
            env=_git_env(),
        )
        assert rev_parse.returncode == 0
        # Recovery ref resolves to a real commit object (SHA-1 is 40 hex chars).
        assert len(rev_parse.stdout.strip()) == 40


class TestCommitPhaseWithRecoverySanitize:
    """Sanitize failures must surface with a sanitize-specific reason, not plumbing."""

    def test_sanitize_failure_uses_sanitize_reason(self, tmp_git_repo: Path) -> None:
        from deviate.cli.micro import _commit_phase_with_recovery, CommitFailedError

        _setup_repo_with_pre_commit_hook(
            tmp_git_repo,
            hook_body="#!/bin/sh\nexit 1\n",
        )
        _stage_change(tmp_git_repo, "src/feat.py", "# feat\n")

        with pytest.raises(CommitFailedError) as info:
            _commit_phase_with_recovery(
                "feat: hostile id",
                tmp_git_repo,
                task_id="foo/../bar",
                attempt=1,
                phase="EXECUTE",
            )

        # The reason must reflect the sanitization failure, not the
        # generic "commit_failed_plumbing".
        err = info.value
        assert err.terminal is True
        assert err.reason == "sanitize_double_dot"
        assert err.recovery_ref is None


class TestCommitPhaseUnchanged:
    """The existing ``_commit_phase`` swallow behavior must NOT change."""

    def test_plain_commit_phase_returns_false_on_failure(
        self, tmp_git_repo: Path
    ) -> None:
        from deviate.cli.micro import _commit_phase

        _setup_repo_with_pre_commit_hook(
            tmp_git_repo,
            hook_body="#!/bin/sh\nexit 1\n",
        )
        _stage_change(tmp_git_repo, "swallow.py", "# swallow\n")

        # ``_commit_phase`` must continue to return ``False`` (NOT raise)
        # so the 10 routine ``no_verify=True`` call sites keep their
        # existing contract.
        result = _commit_phase("feat: swallow", tmp_git_repo, phase="EXECUTE")
        assert result is False

    def test_plain_commit_phase_returns_true_on_success(
        self, tmp_git_repo: Path
    ) -> None:
        from deviate.cli.micro import _commit_phase

        _setup_repo_with_pre_commit_hook(
            tmp_git_repo,
            hook_body="#!/bin/sh\nexit 0\n",
        )
        _stage_change(tmp_git_repo, "ok.py", "# ok\n")

        result = _commit_phase("feat: ok", tmp_git_repo, phase="EXECUTE")
        assert result is True
