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


class TestReviewPost:
    """RED-phase tests for TSK-004-04: post command — report persistence with no-commit enforcement."""

    def test_review_post_persists_report(self, tmp_git_repo: Path) -> None:
        """UT-10: Post writes report to .deviate/review/reports/review-report-{timestamp}.md."""
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

    def _read_contract(self, tmp_git_repo: Path) -> dict:
        """Helper to invoke deviate review pre and parse the JSON contract."""
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])
        assert result.exit_code == 0
        return json.loads(result.stdout)

    def test_review_pre_emits_contract(self, tmp_git_repo: Path) -> None:
        """UT-01: deviate review pre emits valid JSON contract with all required top-level keys."""
        contract = self._read_contract(tmp_git_repo)
        assert isinstance(contract, dict)
        # Top-level keys from tools-review contract format
        assert contract["status"] == "READY"
        assert "phase" in contract
        assert "branch" in contract
        assert "repo_root" in contract
        assert "has_changes" in contract
        # Files block
        assert "files" in contract
        assert "staged" in contract["files"]
        assert "filtered" in contract["files"]
        assert "review_strategy" in contract["files"]
        assert "categories" in contract["files"]
        # Scope block
        assert "scope" in contract
        assert "merge_base" in contract["scope"]
        # Governance block
        assert "governance" in contract
        assert "constitution_path" in contract["governance"]
        assert "prd_path" in contract["governance"]
        # Paths
        assert "diff_path" in contract
        assert "ast_diff_path" in contract
        assert "ast_diff_summary" in contract
        assert "report_exists" in contract
        assert "timestamp" in contract

    def test_review_pre_finds_constitution(self, tmp_git_repo: Path) -> None:
        """UT-02: Contract constitution_path points to resolved absolute path of specs/constitution.md."""
        specs_dir = tmp_git_repo / "specs"
        specs_dir.mkdir(parents=True, exist_ok=True)
        const_path = specs_dir / "constitution.md"
        const_path.write_text("# Test Constitution\n", encoding="utf-8")

        contract = self._read_contract(tmp_git_repo)
        resolved = str(const_path.resolve())
        assert contract["governance"]["constitution_path"] == resolved
        assert contract["governance"]["constitution_found"] is True

    def test_review_pre_diff_against_main(self, tmp_git_repo: Path) -> None:
        """UT-06: Diff file at diff_path contains unified diff of changes against merge-base with main."""
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

        contract = self._read_contract(tmp_git_repo)

        # Diff should be non-empty
        diff_path = Path(contract["diff_path"])
        assert diff_path.exists()
        diff_content = diff_path.read_text(encoding="utf-8")
        assert diff_content, "Expected non-empty diff when branch has changes vs main"
        assert "new.txt" in diff_content

    def test_review_pre_empty_diff(self, tmp_git_repo: Path) -> None:
        """UT-07: Contract emitted with empty diff when no changes vs main."""
        subprocess.run(
            ["git", "branch", "-m", "main"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        contract = self._read_contract(tmp_git_repo)
        diff_path = Path(contract["diff_path"])
        assert not diff_path.read_text(encoding="utf-8").strip()

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
        subprocess.run(
            ["git", "commit", "-m", "add PRD files"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        contract = self._read_contract(tmp_git_repo)
        assert contract["governance"]["prd_path"] == str(epic_prd.resolve())
        assert contract["governance"]["prd_found"] is True

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

        contract = self._read_contract(tmp_git_repo)
        assert contract["governance"]["prd_path"] == str(adhoc_prd.resolve())
        assert contract["governance"]["prd_found"] is True

    def test_review_pre_no_prd_warning(self, tmp_git_repo: Path) -> None:
        """UT-05: When no PRD found, contract emits prd_found: false."""
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

        contract = self._read_contract(tmp_git_repo)
        assert contract["governance"]["prd_found"] is False
        assert contract["governance"]["prd_path"] is None

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

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre", "--base", "develop"])

        assert result.exit_code == 0
        contract = json.loads(result.stdout)
        diff_path = Path(contract["diff_path"])
        diff_content = diff_path.read_text(encoding="utf-8")
        assert "feat.txt" in diff_content
        assert "dev.txt" not in diff_content

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

        contract = self._read_contract(tmp_git_repo)
        assert contract["report_exists"] is True

    def test_review_pre_ast_diff_in_contract(self, tmp_git_repo: Path) -> None:
        """UT-13: Contract contains ast_diff_path and ast_diff_summary for changed Python files."""
        subprocess.run(
            ["git", "branch", "-m", "main"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        # Create a Python file on main
        py_file = tmp_git_repo / "src" / "example.py"
        py_file.parent.mkdir(parents=True, exist_ok=True)
        py_file.write_text("def existing():\n    return 1\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "-A"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "base python file"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        # Modify it on a feature branch
        subprocess.run(
            ["git", "checkout", "-b", "feature-branch"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        py_file.write_text(
            "def existing() -> int:\n    return 1\n\ndef new_func(x: int) -> int:\n"
            "    if x > 0:\n        return x\n    return 0\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "-A"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add new function"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        contract = self._read_contract(tmp_git_repo)

        # AST diff should exist
        ast_diff_path = Path(contract["ast_diff_path"])
        assert ast_diff_path.exists()
        ast_diff_md = ast_diff_path.read_text(encoding="utf-8")
        assert "## Structural Diff" in ast_diff_md
        assert "existing" in ast_diff_md or "new_func" in ast_diff_md

        # Summary should have non-zero values
        summary = contract["ast_diff_summary"]
        assert summary["total_files_analyzed"] == 1
        assert summary["functions_added"] == 1

    def test_review_pre_review_strategy(self, tmp_git_repo: Path) -> None:
        """UT-14: Contract includes review_strategy computed from filtered file count and diff size."""
        subprocess.run(
            ["git", "branch", "-m", "main"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        contract = self._read_contract(tmp_git_repo)
        assert contract["files"]["review_strategy"] in (
            "full",
            "diff_first",
            "targeted",
        )
        assert isinstance(contract["files"]["filtered"], list)
        assert isinstance(contract["files"]["filtered_count"], int)

    def test_review_pre_file_categories(self, tmp_git_repo: Path) -> None:
        """UT-15: Contract includes file categories (core, tests, specs, config, prompts, other)."""
        subprocess.run(
            ["git", "branch", "-m", "main"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        # Add some categorized files
        (tmp_git_repo / "src").mkdir(parents=True, exist_ok=True)
        (tmp_git_repo / "tests").mkdir(parents=True, exist_ok=True)
        (tmp_git_repo / "specs").mkdir(parents=True, exist_ok=True)
        (tmp_git_repo / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_git_repo / "tests" / "test_app.py").write_text(
            "def test_x(): pass\n", encoding="utf-8"
        )
        (tmp_git_repo / "specs" / "doc.md").write_text("# spec\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "-A"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add categorized files"],
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
        (tmp_git_repo / "src").mkdir(parents=True, exist_ok=True)
        (tmp_git_repo / "src" / "new.py").write_text("y = 2\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "src/new.py"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add new source file"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        contract = self._read_contract(tmp_git_repo)
        cats = contract["files"]["categories"]
        assert "core" in cats
        assert "tests" in cats
        assert "specs" in cats
        assert "config" in cats
        assert "prompts" in cats
        assert "other" in cats
        # The branch has changes to src/new.py (core), plus existing files
        assert cats["core"] >= 1

    def test_review_pre_governance_blocks(self, tmp_git_repo: Path) -> None:
        """UT-16: Contract governance block includes spec, design, data_model resolution from branch name."""
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

        # Create spec and design files
        issue_dir = tmp_git_repo / "specs" / "test-epic" / "test-issue"
        issue_dir.mkdir(parents=True, exist_ok=True)
        spec_file = issue_dir / "spec.md"
        spec_file.write_text("# Issue Spec\n", encoding="utf-8")
        tasks_file = issue_dir / "tasks.md"
        tasks_file.write_text("# Tasks\n", encoding="utf-8")

        epic_dir = tmp_git_repo / "specs" / "test-epic"
        design_file = epic_dir / "design.md"
        design_file.write_text("# Design\n", encoding="utf-8")
        data_model_file = epic_dir / "data-model.md"
        data_model_file.write_text("# Data Model\n", encoding="utf-8")

        (tmp_git_repo / "dummy.txt").write_text("work\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "-A"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add governance artifacts"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        contract = self._read_contract(tmp_git_repo)
        gov = contract["governance"]
        assert gov["spec_found"] is True
        assert gov["spec_path"] == str(spec_file.resolve())
        assert gov["tasks_path"] == str(tasks_file.resolve())
        assert gov["design_found"] is True
        assert gov["design_path"] == str(design_file.resolve())
        assert gov["data_model_found"] is True
        assert gov["data_model_path"] == str(data_model_file.resolve())
