"""Second-worktree support: re-open the SAME issue in another worktree.

`deviate specify <id> --second-worktree` creates `feat/<epic>/<slug>-rN`
(auto-increment from existing local branches) so two worktrees can carry the
same specs. Branch→issue resolvers strip the `-rN` suffix (exact slug first).
"""

from __future__ import annotations

import subprocess
from contextlib import chdir
from datetime import datetime, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.cli._common import resolve_issue_id_from_branch
from deviate.cli.meso import _try_claim_issue
from deviate.core.review_coverage import resolve_review_issue_id
from deviate.core.worktree import create_worktree
from deviate.state.ledger import (
    IssueRecord,
    append_issue_transition,
    resolve_issue_record,
)
from tests.conftest import _git_env

runner = CliRunner()

EPIC = "test-epic"
SLUG = "iss-001"
ISSUE_ID = "ISS-001-001"


def _seed_claimed_issue(repo: Path) -> None:
    """Commit a claimed issue + ledger row on the repo's current branch."""
    issue_dir = repo / "specs" / EPIC / "issues"
    issue_dir.mkdir(parents=True, exist_ok=True)
    (issue_dir / f"{SLUG}.md").write_text(f"# {ISSUE_ID}\n", encoding="utf-8")
    append_issue_transition(
        IssueRecord(
            issue_id=ISSUE_ID,
            type="feature",
            title="First Issue",
            status="SPECIFIED",
            source_file=f"specs/{EPIC}/issues/{SLUG}.md",
            timestamp=datetime.now(timezone.utc),
        ),
        repo / "specs" / "issues.jsonl",
    )
    subprocess.run(
        ["git", "add", "specs"],
        cwd=repo,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "seed issue"],
        cwd=repo,
        env=_git_env(),
        check=True,
    )


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, env=_git_env(), check=True)


class TestSecondWorktreeClaim:
    def test_second_worktree_creates_suffixed_branch_with_same_specs(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--second-worktree claims onto feat/<epic>/<slug>-r2 with the specs
        already committed on the first worktree's branch."""
        monkeypatch.setattr("deviate.cli.meso._setup_mise", lambda *a, **kw: None)
        _seed_claimed_issue(tmp_git_repo)
        first_wt = create_worktree(
            f"feat/{EPIC}/{SLUG}",
            tmp_git_repo / ".worktrees" / "feat" / EPIC / SLUG,
            repo=tmp_git_repo,
        )

        record = resolve_issue_record(ISSUE_ID, tmp_git_repo / "specs" / "issues.jsonl")
        assert record is not None
        with chdir(tmp_git_repo):
            result = _try_claim_issue(
                record,
                repo_root=tmp_git_repo,
                ledger_path=tmp_git_repo / "specs" / "issues.jsonl",
                local=True,
                second=True,
            )

        assert result is not None
        assert result["branch"] == f"feat/{EPIC}/{SLUG}-r2"
        second_wt = Path(result["worktree_path"])
        assert second_wt.exists()
        assert second_wt != first_wt
        # Specs ride along: the issue file is committed on the base branch.
        assert (second_wt / "specs" / EPIC / "issues" / f"{SLUG}.md").exists()

    def test_second_worktree_autoincrements_suffix(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Existing feat/<epic>/<slug>-rN branches bump the next claim to rN+1."""
        monkeypatch.setattr("deviate.cli.meso._setup_mise", lambda *a, **kw: None)
        _seed_claimed_issue(tmp_git_repo)
        create_worktree(
            f"feat/{EPIC}/{SLUG}",
            tmp_git_repo / ".worktrees" / "feat" / EPIC / SLUG,
            repo=tmp_git_repo,
        )
        create_worktree(
            f"feat/{EPIC}/{SLUG}-r2",
            tmp_git_repo / ".worktrees" / "feat" / EPIC / f"{SLUG}-r2",
            repo=tmp_git_repo,
        )

        record = resolve_issue_record(ISSUE_ID, tmp_git_repo / "specs" / "issues.jsonl")
        assert record is not None
        with chdir(tmp_git_repo):
            result = _try_claim_issue(
                record,
                repo_root=tmp_git_repo,
                ledger_path=tmp_git_repo / "specs" / "issues.jsonl",
                local=True,
                second=True,
            )

        assert result is not None
        assert result["branch"] == f"feat/{EPIC}/{SLUG}-r3"


class TestSecondWorktreeCliFlag:
    def test_specify_second_worktree_flag_passes_through(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`deviate specify <id> --second-worktree` forwards second=True."""
        _seed_claimed_issue(tmp_git_repo)
        captured: dict[str, object] = {}

        def fake_try_claim(record, **kwargs):  # noqa: ARG001
            captured.update(kwargs)
            return {"worktree_path": str(tmp_git_repo / ".worktrees" / "fake")}

        monkeypatch.setattr(
            "deviate.cli.meso.branch_exists_on_remote",
            lambda branch, **kw: False,
        )
        monkeypatch.setattr("deviate.cli.meso._try_claim_issue", fake_try_claim)

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["specify", ISSUE_ID, "--second-worktree"])

        assert result.exit_code == 0, result.output
        assert captured.get("second") is True

    def test_specify_without_flag_keeps_default_branch(
        self, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Default specify never sets second=True."""
        _seed_claimed_issue(tmp_git_repo)
        captured: dict[str, object] = {}

        def fake_try_claim(record, **kwargs):  # noqa: ARG001
            captured.update(kwargs)
            return {"worktree_path": str(tmp_git_repo / ".worktrees" / "fake")}

        monkeypatch.setattr(
            "deviate.cli.meso.branch_exists_on_remote",
            lambda branch, **kw: False,
        )
        monkeypatch.setattr("deviate.cli.meso._try_claim_issue", fake_try_claim)

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["specify", ISSUE_ID])

        assert result.exit_code == 0, result.output
        assert not captured.get("second")


class TestResolverStripsSecondWorktreeSuffix:
    """Branch→issue resolution must strip the -rN suffix (exact slug first)."""

    def _make_worktrees(self, tmp_git_repo: Path) -> tuple[Path, Path]:
        _seed_claimed_issue(tmp_git_repo)
        first_wt = create_worktree(
            f"feat/{EPIC}/{SLUG}",
            tmp_git_repo / ".worktrees" / "feat" / EPIC / SLUG,
            repo=tmp_git_repo,
        )
        second_wt = create_worktree(
            f"feat/{EPIC}/{SLUG}-r2",
            tmp_git_repo / ".worktrees" / "feat" / EPIC / f"{SLUG}-r2",
            repo=tmp_git_repo,
        )
        return first_wt, second_wt

    def test_common_resolver(self, tmp_git_repo: Path) -> None:
        first_wt, second_wt = self._make_worktrees(tmp_git_repo)
        assert resolve_issue_id_from_branch(first_wt) == ISSUE_ID
        assert resolve_issue_id_from_branch(second_wt) == ISSUE_ID

    def test_micro_resolver(self, tmp_git_repo: Path) -> None:
        from deviate.cli.micro import _resolve_issue_id_from_branch

        first_wt, second_wt = self._make_worktrees(tmp_git_repo)
        assert _resolve_issue_id_from_branch(first_wt) == ISSUE_ID
        assert _resolve_issue_id_from_branch(second_wt) == ISSUE_ID

    def test_review_coverage_resolver(self, tmp_git_repo: Path) -> None:
        first_wt, second_wt = self._make_worktrees(tmp_git_repo)
        assert (
            resolve_review_issue_id(
                repo_path=first_wt, branch_name=f"feat/{EPIC}/{SLUG}"
            )
            == ISSUE_ID
        )
        assert (
            resolve_review_issue_id(
                repo_path=second_wt, branch_name=f"feat/{EPIC}/{SLUG}-r2"
            )
            == ISSUE_ID
        )

    def test_exact_slug_wins_over_stripped_suffix(self, tmp_git_repo: Path) -> None:
        """A real issue whose slug IS `iss-001-r2` must not be shadowed."""
        _seed_claimed_issue(tmp_git_repo)
        real_dir = tmp_git_repo / "specs" / EPIC / "issues"
        (real_dir / f"{SLUG}-r2.md").write_text(f"# {ISSUE_ID}-R2\n", encoding="utf-8")
        append_issue_transition(
            IssueRecord(
                issue_id="ISS-001-002",
                type="feature",
                title="Slug Collision Issue",
                status="SPECIFIED",
                source_file=f"specs/{EPIC}/issues/{SLUG}-r2.md",
                timestamp=datetime.now(timezone.utc),
            ),
            tmp_git_repo / "specs" / "issues.jsonl",
        )
        _git("add", "specs", cwd=tmp_git_repo)
        _git("commit", "-m", "seed colliding slug", cwd=tmp_git_repo)
        _git("branch", f"feat/{EPIC}/{SLUG}-r2", cwd=tmp_git_repo)
        _git("checkout", "-q", f"feat/{EPIC}/{SLUG}-r2", cwd=tmp_git_repo)
        assert resolve_issue_id_from_branch(tmp_git_repo) == "ISS-001-002"
