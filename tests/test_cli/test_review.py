from __future__ import annotations

import json
import re
import subprocess
from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from tests.conftest import _git_env

runner = CliRunner()

_REVIEW_PROMPT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "deviate"
    / "prompts"
    / "commands"
    / "deviate-review.md"
).read_text(encoding="utf-8")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=repo, env=_git_env(), check=True, capture_output=True
    )


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _seed_named_brief(
    repo: Path,
    *,
    issue_id: str = "ISS-ADH-035",
    slug: str = "035-gate3",
    token: str = "AC-ADHOC-035-01",
    extra: str = "",
) -> Path:
    """Put a this-issue brief with a named check on ``feat/adhoc/<slug>``."""
    _git(repo, "checkout", "-B", f"feat/adhoc/{slug}")
    issues_dir = repo / "specs" / "adhoc" / "issues"
    issues_dir.mkdir(parents=True, exist_ok=True)
    brief = issues_dir / f"{slug}.md"
    brief.write_text(f"# gate3\n\n{token} named check\n{extra}", encoding="utf-8")
    _write_jsonl(
        repo / "specs" / "issues.jsonl",
        [
            {
                "issue_id": issue_id,
                "source_file": f"specs/adhoc/issues/{slug}.md",
            }
        ],
    )
    return brief


class TestReviewCommentsOnly:
    """AC-ADHOC-035-02 / 04: review is comments-only; incomplete brief stops."""

    def test_review_prompt_has_no_apply_or_commit_or_request_changes(self) -> None:
        text = _REVIEW_PROMPT
        assert "COMMENTS_ONLY" in text
        assert "There is no STEP 4" in text
        assert "Autonomous Fix Application" not in text
        assert "apply N review fixes" not in text
        assert "Do not `git add`" in text
        assert "Do not `git commit`" in text
        assert "Never emit `REQUEST_CHANGES`" in text
        assert "brief incomplete" in text

    def test_review_pre_incomplete_brief_emits_exact_phrase(
        self, tmp_git_repo: Path
    ) -> None:
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code != 0
        assert result.stdout.strip() == "brief incomplete"

    def test_review_pre_brief_without_named_checks_is_incomplete(
        self, tmp_git_repo: Path
    ) -> None:
        _git(tmp_git_repo, "checkout", "-b", "feat/adhoc/035-empty")
        issues = tmp_git_repo / "specs" / "adhoc" / "issues"
        issues.mkdir(parents=True, exist_ok=True)
        (issues / "035-empty.md").write_text("# no tokens here\n", encoding="utf-8")
        _write_jsonl(
            tmp_git_repo / "specs" / "issues.jsonl",
            [
                {
                    "issue_id": "ISS-ADH-035",
                    "source_file": "specs/adhoc/issues/035-empty.md",
                }
            ],
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code != 0
        assert result.stdout.strip() == "brief incomplete"

    def test_review_pre_includes_issue_brief_path(self, tmp_git_repo: Path) -> None:
        brief = _seed_named_brief(tmp_git_repo)

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0, result.stdout
        contract = json.loads(result.stdout)
        assert contract["issue_brief_path"] == str(brief.resolve())
        assert contract["plan_path"] is None

    def test_review_cli_source_has_no_apply_or_commit(self) -> None:
        source = (
            Path(__file__).resolve().parents[2] / "src" / "deviate" / "cli" / "review.py"
        ).read_text(encoding="utf-8")
        assert "git add" not in source
        assert "git commit" not in source
        assert "REQUEST_CHANGES" not in source


class TestReviewPost:
    """RED-phase tests for TSK-004-04: post command — report persistence with no-commit enforcement."""

    def test_review_post_persists_report(self, tmp_git_repo: Path) -> None:
        """UT-10: Post writes report to .deviate/review/reports/review-report-{timestamp}.md."""
        _seed_named_brief(tmp_git_repo)
        report_content = "# Review Report\n\n## Summary\nAll good."
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "post", report_content])

        assert result.exit_code == 0
        reports_dir = tmp_git_repo / ".deviate" / "review" / "reports"
        assert reports_dir.is_dir(), "reports directory should exist"
        files = list(reports_dir.iterdir())
        assert len(files) == 1, "Expected exactly one report file"
        report_file = files[0]
        assert re.match(r"review-report-\d{8}T\d{6}\.md$", report_file.name), (
            f"Unexpected report filename: {report_file.name}"
        )
        assert report_file.read_text(encoding="utf-8") == report_content

    def test_review_post_no_artifact(self, tmp_git_repo: Path) -> None:
        """UT-11: Graceful handling when no report data provided."""
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "post"])

        assert result.exit_code == 0
        reports_dir = tmp_git_repo / ".deviate" / "review" / "reports"
        assert not reports_dir.exists(), "No reports directory should be created"
        assert (
            "no report content provided" in result.stdout.lower()
            or "skip" in result.stdout.lower()
        )

    def test_review_post_no_commit(self, tmp_git_repo: Path) -> None:
        """UT-12: After post, git status shows no staged/committed changes."""
        subprocess.run(
            ["git", "branch", "-m", "main"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        (tmp_git_repo / "dummy.txt").write_text("project file\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "dummy.txt"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "initial project content"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        _seed_named_brief(tmp_git_repo)
        report_content = "# Review Report\n\nReview findings."
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "post", report_content])

        assert result.exit_code == 0

        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=tmp_git_repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert not staged, f"Found staged changes: {staged}"

        reports_dir = tmp_git_repo / ".deviate" / "review" / "reports"
        assert reports_dir.is_dir(), "report should have been written"
        files = list(reports_dir.iterdir())
        assert len(files) == 1
        report_file = files[0]
        assert report_file.read_text(encoding="utf-8") == report_content


class TestReviewPreCore:
    """RED-phase tests for TSK-004-02: pre command core — contract emission, git diff, constitution path resolution."""

    def test_review_pre_emits_contract(self, tmp_git_repo: Path) -> None:
        """UT-01: deviate review pre emits valid JSON contract with all required keys."""
        _seed_named_brief(tmp_git_repo)
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0, result.stdout
        contract = json.loads(result.stdout)
        assert isinstance(contract, dict)
        assert "status" in contract
        assert "diff" in contract
        assert "issue_brief_path" in contract
        assert "constitution_path" in contract
        assert "prd_path" in contract
        assert "base_branch" in contract
        assert "report_exists" in contract
        assert "timestamp" in contract
        assert contract["status"] == "READY"

    def test_review_pre_finds_constitution(self, tmp_git_repo: Path) -> None:
        """UT-02: Contract constitution_path points to resolved absolute path of specs/constitution.md."""
        specs_dir = tmp_git_repo / "specs"
        specs_dir.mkdir(parents=True, exist_ok=True)
        const_path = specs_dir / "constitution.md"
        const_path.write_text("# Test Constitution\n", encoding="utf-8")
        _seed_named_brief(tmp_git_repo)

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0
        contract = json.loads(result.stdout)
        resolved = str(const_path.resolve())
        assert contract["constitution_path"] == resolved

    def test_review_pre_diff_against_main(self, tmp_git_repo: Path) -> None:
        """UT-06: diff field contains unified diff of changes against merge-base with main."""
        subprocess.run(
            ["git", "branch", "-m", "main"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        (tmp_git_repo / "existing.txt").write_text("original\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "existing.txt"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "base content"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        subprocess.run(
            ["git", "checkout", "-b", "feature-branch"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        (tmp_git_repo / "new.txt").write_text("new content\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "new.txt"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add new file"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        _seed_named_brief(tmp_git_repo)

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0, result.stdout
        contract = json.loads(result.stdout)
        assert contract["diff"], (
            "Expected non-empty diff when branch has changes vs main"
        )
        assert "new.txt" in contract["diff"]

    def test_review_pre_empty_diff(self, tmp_git_repo: Path) -> None:
        """UT-07: Contract emitted with empty diff string when no changes vs main."""
        subprocess.run(
            ["git", "branch", "-m", "main"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        _seed_named_brief(tmp_git_repo)

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0, result.stdout
        contract = json.loads(result.stdout)
        assert contract["diff"] == ""

    def test_review_pre_resolves_prd_epic_first(self, tmp_git_repo: Path) -> None:
        """UT-03: Contract prd_path points to epic PRD over adhoc PRD."""
        subprocess.run(
            ["git", "branch", "-m", "main"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "checkout", "-b", "feat/test-epic/test-issue"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        epic_prd_dir = tmp_git_repo / "specs" / "test-epic"
        epic_prd_dir.mkdir(parents=True, exist_ok=True)
        epic_prd = epic_prd_dir / "prd.md"
        epic_prd.write_text("# Epic PRD\n", encoding="utf-8")

        adhoc_prd_dir = tmp_git_repo / "specs" / "adhoc"
        adhoc_prd_dir.mkdir(parents=True, exist_ok=True)
        adhoc_prd = adhoc_prd_dir / "prd.md"
        adhoc_prd.write_text("# Adhoc PRD\n", encoding="utf-8")

        subprocess.run(
            ["git", "add", "-A"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        issues_dir = tmp_git_repo / "specs" / "test-epic" / "issues"
        issues_dir.mkdir(parents=True, exist_ok=True)
        (issues_dir / "test-issue.md").write_text(
            "# brief\n\nAC-ADHOC-035-01 named check\n", encoding="utf-8"
        )
        _write_jsonl(
            tmp_git_repo / "specs" / "issues.jsonl",
            [
                {
                    "issue_id": "ISS-035-001",
                    "source_file": "specs/test-epic/issues/test-issue.md",
                }
            ],
        )
        subprocess.run(
            ["git", "add", "-A"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add PRD files"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0, result.stdout
        contract = json.loads(result.stdout)
        assert contract["prd_path"] == str(epic_prd.resolve())
        assert not contract.get("prd_warning", False)

    def test_review_pre_falls_back_to_adhoc_prd(self, tmp_git_repo: Path) -> None:
        """UT-04: When epic PRD absent, contract prd_path points to specs/adhoc/prd.md."""
        subprocess.run(
            ["git", "branch", "-m", "main"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "checkout", "-b", "feat/test-epic/test-issue"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        adhoc_prd_dir = tmp_git_repo / "specs" / "adhoc"
        adhoc_prd_dir.mkdir(parents=True, exist_ok=True)
        adhoc_prd = adhoc_prd_dir / "prd.md"
        adhoc_prd.write_text("# Adhoc PRD\n", encoding="utf-8")
        issues_dir = tmp_git_repo / "specs" / "test-epic" / "issues"
        issues_dir.mkdir(parents=True, exist_ok=True)
        (issues_dir / "test-issue.md").write_text(
            "# brief\n\nAC-ADHOC-035-01 named check\n", encoding="utf-8"
        )
        _write_jsonl(
            tmp_git_repo / "specs" / "issues.jsonl",
            [
                {
                    "issue_id": "ISS-035-001",
                    "source_file": "specs/test-epic/issues/test-issue.md",
                }
            ],
        )

        subprocess.run(
            ["git", "add", "-A"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add adhoc PRD"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0, result.stdout
        contract = json.loads(result.stdout)
        assert contract["prd_path"] == str(adhoc_prd.resolve())
        assert not contract.get("prd_warning", False)

    def test_review_pre_no_prd_warning(self, tmp_git_repo: Path) -> None:
        """UT-05: When no PRD found, contract emits prd_warning: true and prd_path: null."""
        subprocess.run(
            ["git", "branch", "-m", "main"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "checkout", "-b", "feat/test-epic/test-issue"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        (tmp_git_repo / "dummy.txt").write_text("dummy\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "dummy.txt"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "dummy commit"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        issues_dir = tmp_git_repo / "specs" / "test-epic" / "issues"
        issues_dir.mkdir(parents=True, exist_ok=True)
        (issues_dir / "test-issue.md").write_text(
            "# brief\n\nAC-ADHOC-035-01 named check\n", encoding="utf-8"
        )
        _write_jsonl(
            tmp_git_repo / "specs" / "issues.jsonl",
            [
                {
                    "issue_id": "ISS-035-001",
                    "source_file": "specs/test-epic/issues/test-issue.md",
                }
            ],
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0, result.stdout
        contract = json.loads(result.stdout)
        assert contract["prd_warning"] is True
        assert contract["prd_path"] is None

    def test_review_pre_custom_base(self, tmp_git_repo: Path) -> None:
        """UT-08: --base develop overrides default main merge-base."""
        subprocess.run(
            ["git", "branch", "-m", "main"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        (tmp_git_repo / "base.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "base.txt"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "base on main"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        subprocess.run(
            ["git", "checkout", "-b", "develop"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        (tmp_git_repo / "dev.txt").write_text("dev\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "dev.txt"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "dev change"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        subprocess.run(
            ["git", "checkout", "-b", "feature-branch"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        (tmp_git_repo / "feat.txt").write_text("feat\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "feat.txt"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "feature change"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        _seed_named_brief(tmp_git_repo)

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre", "--base", "develop"])

        assert result.exit_code == 0, result.stdout
        contract = json.loads(result.stdout)
        assert contract["base_branch"] == "develop"
        assert "feat.txt" in contract["diff"]
        assert "dev.txt" not in contract["diff"]

    def test_review_pre_existing_report_warning(self, tmp_git_repo: Path) -> None:
        """UT-09: Contract includes report_exists: true when reports dir has files."""
        reports_dir = tmp_git_repo / ".deviate" / "review" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "review-report-20260615T120000.md").write_text(
            "# Old report\n", encoding="utf-8"
        )

        subprocess.run(
            ["git", "add", "-A"], cwd=tmp_git_repo, env=_git_env(), check=False
        )
        _seed_named_brief(tmp_git_repo)

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0, result.stdout
        contract = json.loads(result.stdout)
        assert contract["report_exists"] is True


_ISSUE_ID = "ISS-ADH-028"
_SIBLING_ISSUE_ID = "ISS-ADH-099"
_SLUG = "028-coverage"
_BRANCH = f"feat/adhoc/{_SLUG}"


def _seed_review_issue(
    repo: Path,
    *,
    plan_acs: tuple[str, ...] = ("AC-PLAN-001", "AC-PLAN-002"),
    task_rows: list[dict] | None = None,
    cards: dict[str, str] | None = None,
    sibling_rows: list[dict] | None = None,
) -> None:
    _git(repo, "checkout", "-b", _BRANCH)
    issues_dir = repo / "specs" / "adhoc" / "issues"
    issues_dir.mkdir(parents=True, exist_ok=True)
    (issues_dir / f"{_SLUG}.md").write_text(
        "# coverage issue\n\nAC-ADHOC-028-01 named check\n", encoding="utf-8"
    )
    issue_rows = [
        {
            "issue_id": _ISSUE_ID,
            "source_file": f"specs/adhoc/issues/{_SLUG}.md",
        }
    ]
    if sibling_rows is not None:
        issue_rows.append(
            {
                "issue_id": _SIBLING_ISSUE_ID,
                "source_file": "specs/adhoc/issues/099-sibling.md",
            }
        )
        sibling_dir = repo / "specs" / "adhoc" / "issues"
        (sibling_dir / "099-sibling.md").write_text("# sibling\n", encoding="utf-8")
    _write_jsonl(repo / "specs" / "issues.jsonl", issue_rows)

    work = repo / "specs" / "adhoc" / _SLUG
    work.mkdir(parents=True, exist_ok=True)
    if plan_acs:
        body = "\n".join(f"**Scenario {ac}: example**" for ac in plan_acs)
    else:
        body = "No AC-PLAN tokens.\n"
    (work / "plan.md").write_text(body + "\n", encoding="utf-8")

    card_lines = ["# Tasks\n"]
    for task_id, named in (cards or {}).items():
        card_lines.append(f"- {task_id}: card\n")
        if named:
            card_lines.append(f"  - **Acceptance Criteria**: {named}\n")
            card_lines.append(f"  - **Rationale**: owns {named}\n")
    (work / "tasks.md").write_text("".join(card_lines), encoding="utf-8")
    _write_jsonl(work / "tasks.jsonl", task_rows or [])

    if sibling_rows is not None:
        sibling_work = repo / "specs" / "adhoc" / "099-sibling"
        sibling_work.mkdir(parents=True, exist_ok=True)
        _write_jsonl(sibling_work / "tasks.jsonl", sibling_rows)


def _completed(
    task_id: str,
    *criterion_ids: str,
    issue_id: str = _ISSUE_ID,
    evidence: list[dict] | None = None,
    status: str = "COMPLETED",
) -> dict:
    row: dict = {
        "id": task_id,
        "issue_id": issue_id,
        "description": f"{task_id} {status}",
        "status": status,
        "execution_mode": "TDD",
    }
    if criterion_ids:
        row["acceptance_criteria"] = [
            {"criterion_id": token, "verification_mode": "manual"}
            for token in criterion_ids
        ]
    if evidence is not None:
        row["evidence"] = evidence
    return row


class TestReviewPlanAcCoverage:
    """Uncovered plan ACs are comment input, not a merge/apply gate."""

    def test_review_pre_named_brief_without_plan_is_ready(
        self, tmp_git_repo: Path
    ) -> None:
        _seed_named_brief(tmp_git_repo)
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0, result.stdout
        contract = json.loads(result.stdout)
        assert contract["status"] == "READY"
        assert contract.get("uncovered", []) == []

    def test_review_pre_lists_unclaimed_plan_ac_as_comment_input(
        self, tmp_git_repo: Path
    ) -> None:
        _seed_review_issue(
            tmp_git_repo,
            task_rows=[
                _completed("TSK-028-01", "AC-PLAN-001"),
            ],
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0, result.stdout
        contract = json.loads(result.stdout)
        assert contract["status"] == "READY"
        assert "AC-PLAN-002" in contract["uncovered"]
        assert contract["coverage_complete"] is False

    def test_review_post_persists_comments_when_plan_ac_unclaimed(
        self, tmp_git_repo: Path
    ) -> None:
        _seed_review_issue(
            tmp_git_repo,
            task_rows=[_completed("TSK-028-01", "AC-PLAN-001")],
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(
                cli, ["review", "post", "comments: AC-PLAN-002 uncovered"]
            )

        assert result.exit_code == 0, result.stdout
        reports_dir = tmp_git_repo / ".deviate" / "review" / "reports"
        files = list(reports_dir.iterdir())
        assert len(files) == 1
        assert "AC-PLAN-002" in files[0].read_text(encoding="utf-8")

    def test_review_pre_ready_when_completed_claims_cover_plan(
        self, tmp_git_repo: Path
    ) -> None:
        _seed_review_issue(
            tmp_git_repo,
            task_rows=[
                _completed("TSK-028-01", "AC-PLAN-001"),
                _completed("TSK-028-02", "AC-PLAN-002"),
            ],
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0
        contract = json.loads(result.stdout)
        assert contract["status"] == "READY"
        assert contract["uncovered"] == []
        assert contract["coverage_complete"] is True

    def test_review_pre_ready_when_persisted_evidence_claims_token(
        self, tmp_git_repo: Path
    ) -> None:
        _seed_review_issue(
            tmp_git_repo,
            task_rows=[
                _completed("TSK-028-01", "AC-PLAN-001"),
                _completed(
                    "TSK-028-02",
                    evidence=[{"ac": "AC-PLAN-002"}],
                ),
            ],
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0
        contract = json.loads(result.stdout)
        assert contract["status"] == "READY"
        assert contract["uncovered"] == []

    def test_pending_failed_and_sibling_rows_do_not_claim(
        self, tmp_git_repo: Path
    ) -> None:
        _seed_review_issue(
            tmp_git_repo,
            task_rows=[
                _completed("TSK-028-01", "AC-PLAN-001"),
                _completed("TSK-028-02", "AC-PLAN-002", status="PENDING"),
                _completed("TSK-028-03", "AC-PLAN-002", status="FAILED"),
            ],
            cards={
                "TSK-028-02": "AC-PLAN-002",
                "TSK-028-03": "AC-PLAN-002",
            },
            sibling_rows=[
                _completed(
                    "TSK-099-01",
                    "AC-PLAN-002",
                    issue_id=_SIBLING_ISSUE_ID,
                )
            ],
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0, result.stdout
        contract = json.loads(result.stdout)
        assert contract["status"] == "READY"
        assert "AC-PLAN-002" in contract["uncovered"]

    def test_criteria_win_does_not_union_later_card_tokens(
        self, tmp_git_repo: Path
    ) -> None:
        _seed_review_issue(
            tmp_git_repo,
            task_rows=[_completed("TSK-028-01", "AC-PLAN-001")],
            cards={"TSK-028-01": "AC-PLAN-001 AC-PLAN-002"},
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0, result.stdout
        contract = json.loads(result.stdout)
        assert "AC-PLAN-002" in contract["uncovered"]

    def test_card_tokens_claim_when_criteria_absent(self, tmp_git_repo: Path) -> None:
        _seed_review_issue(
            tmp_git_repo,
            task_rows=[
                _completed("TSK-028-01"),
                _completed("TSK-028-02"),
            ],
            cards={
                "TSK-028-01": "AC-PLAN-001",
                "TSK-028-02": "AC-PLAN-002",
            },
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0
        contract = json.loads(result.stdout)
        assert contract["status"] == "READY"
        assert contract["uncovered"] == []

    def test_plan_without_tokens_is_vacuously_complete(
        self, tmp_git_repo: Path
    ) -> None:
        _seed_review_issue(tmp_git_repo, plan_acs=())

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0
        contract = json.loads(result.stdout)
        assert contract["status"] == "READY"
        assert contract["uncovered"] == []
