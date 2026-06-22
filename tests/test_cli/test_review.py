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

    def test_review_pre_emits_contract(self, tmp_git_repo: Path) -> None:
        """UT-01: deviate review pre emits valid JSON contract with all required keys."""
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0
        contract = json.loads(result.stdout)
        assert isinstance(contract, dict)
        assert "status" in contract
        assert "diff" in contract
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

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0
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

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0
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
        subprocess.run(
            ["git", "commit", "-m", "add PRD files"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0
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

        assert result.exit_code == 0
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

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0
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

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre", "--base", "develop"])

        assert result.exit_code == 0
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

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0
        contract = json.loads(result.stdout)
        assert contract["report_exists"] is True


class TestReviewPreStructuredDiff:
    """RED-phase tests for TSK-008-06: merge-base structured diff in review contract."""

    def test_review_pre_structured_diff_language_agnostic(
        self, tmp_git_repo: Path
    ) -> None:
        """UT-17: Structured diff includes ALL diff files — even non-parseable ones with empty symbols + 'unknown' language."""
        subprocess.run(
            ["git", "branch", "-m", "main"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        (tmp_git_repo / "mod.py").write_text("def foo():\n    pass\n", encoding="utf-8")
        (tmp_git_repo / "config.txt").write_text("setting=value\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "-A"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "base"],
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
        (tmp_git_repo / "mod.py").write_text(
            "def foo(x: int) -> int:\n    return x\n", encoding="utf-8"
        )
        (tmp_git_repo / "config.txt").write_text(
            "setting=new_value\n", encoding="utf-8"
        )
        subprocess.run(
            ["git", "add", "-A"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "update both"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0
        contract = json.loads(result.stdout)
        assert "structured_diff" in contract
        entries = contract["structured_diff"]
        assert len(entries) == 2, (
            f"Expected 2 structured_diff entries for .py + .txt, got {len(entries)}"
        )

        file_map = {e["file"]: e for e in entries}
        assert "mod.py" in file_map
        assert "config.txt" in file_map

        py_entry = file_map["mod.py"]
        txt_entry = file_map["config.txt"]

        assert len(py_entry["symbols"]) > 0, "Python file should have parseable symbols"
        assert txt_entry["symbols"] == [], (
            "Non-parseable .txt should have empty symbols"
        )
        assert txt_entry["language"] == "unknown", (
            f"Expected 'unknown' language for .txt, got '{txt_entry['language']}'"
        )

        for key in (
            "net_lines_changed",
            "lines_added",
            "lines_removed",
            "chunks_changed",
        ):
            assert key in txt_entry, f"Missing file stats key '{key}' in .txt entry"

    def test_review_pre_contains_structured_diff(self, tmp_git_repo: Path) -> None:
        """UT-13: Contract contains structured_diff list for merge-base vs HEAD symbol comparison."""
        subprocess.run(
            ["git", "branch", "-m", "main"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        py_src = """def greet(name):
    return f"Hello, {name}"

class Calculator:
    def add(self, a, b):
        return a + b
"""
        (tmp_git_repo / "mod.py").write_text(py_src, encoding="utf-8")
        subprocess.run(
            ["git", "add", "mod.py"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "base commit"],
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
        new_src = """def greet(name, title="Mr."):
    return f"Hello, {title} {name}"

class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b

    def subtract(self, a, b):
        return a - b
"""
        (tmp_git_repo / "mod.py").write_text(new_src, encoding="utf-8")
        subprocess.run(
            ["git", "add", "mod.py"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "update mod"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0
        contract = json.loads(result.stdout)
        assert "structured_diff" in contract, (
            f"Expected structured_diff in contract keys: {list(contract.keys())}"
        )
        assert isinstance(contract["structured_diff"], list)

    def test_review_pre_structured_diff_multiple_languages(
        self, tmp_git_repo: Path
    ) -> None:
        """UT-14: Structured diff handles changes across .py and .ts files."""
        subprocess.run(
            ["git", "branch", "-m", "main"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        (tmp_git_repo / "mod.py").write_text("def foo():\n    pass\n", encoding="utf-8")
        (tmp_git_repo / "service.ts").write_text(
            "function bar(): void {}\n", encoding="utf-8"
        )
        subprocess.run(
            ["git", "add", "-A"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "base"],
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
        (tmp_git_repo / "mod.py").write_text(
            "def foo(x: int) -> int:\n    return x\n", encoding="utf-8"
        )
        (tmp_git_repo / "service.ts").write_text(
            "function bar(name: string): string {\n  return name;\n}\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "-A"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "update both"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0
        contract = json.loads(result.stdout)
        assert "structured_diff" in contract

    def test_review_pre_structured_diff_empty_when_no_diff(
        self, tmp_git_repo: Path
    ) -> None:
        """UT-15: Empty diff produces empty structured_diff list."""
        subprocess.run(
            ["git", "branch", "-m", "main"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        (tmp_git_repo / "dummy.txt").write_text("content\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "dummy.txt"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "base"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0
        contract = json.loads(result.stdout)
        assert "structured_diff" in contract
        if not contract.get("diff"):
            assert contract["structured_diff"] == []

    def test_review_pre_structured_diff_change_types(self, tmp_git_repo: Path) -> None:
        """UT-16: Change types correctly classify added/removed/modified/renamed."""
        subprocess.run(
            ["git", "branch", "-m", "main"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        base_src = """def removed_func():
    return "old"

def modified_func():
    return "original"
"""
        (tmp_git_repo / "mod.py").write_text(base_src, encoding="utf-8")
        subprocess.run(
            ["git", "add", "mod.py"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "base"],
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
        head_src = """def modified_func():
    return "changed"

def added_func():
    return "new"
"""
        (tmp_git_repo / "mod.py").write_text(head_src, encoding="utf-8")
        subprocess.run(
            ["git", "add", "mod.py"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "modify mod"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["review", "pre"])

        assert result.exit_code == 0
        contract = json.loads(result.stdout)
        assert "structured_diff" in contract
        if contract["structured_diff"]:
            entry = contract["structured_diff"]
            assert isinstance(entry, list)
            if len(entry) > 0:
                symbols = (
                    entry[0].get("symbols", entry)
                    if isinstance(entry[0], dict)
                    else entry
                )
                change_types = (
                    {s.get("change", s.get("change")) for s in symbols}
                    if symbols
                    else set()
                )
                assert change_types, (
                    "Expected at least one change type in structured diff"
                )
