from __future__ import annotations

import json
import subprocess
from contextlib import chdir
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deviate.cli import cli
from tests.conftest import _git_env

runner = CliRunner()


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


def _seed_issue(
    repo: Path,
    *,
    with_plan: bool = True,
    name_constitution: bool = False,
) -> tuple[Path, Path | None]:
    _git(repo, "checkout", "-B", "feat/adhoc/035-gate3")
    issues_dir = repo / "specs" / "adhoc" / "issues"
    issues_dir.mkdir(parents=True, exist_ok=True)
    extra = "See specs/constitution.md\n" if name_constitution else ""
    brief = issues_dir / "035-gate3.md"
    brief.write_text(
        f"# gate3\n\nAC-ADHOC-035-01 named check\n{extra}",
        encoding="utf-8",
    )
    _write_jsonl(
        repo / "specs" / "issues.jsonl",
        [
            {
                "issue_id": "ISS-ADH-035",
                "source_file": "specs/adhoc/issues/035-gate3.md",
            }
        ],
    )
    plan: Path | None = None
    if with_plan:
        work = repo / "specs" / "adhoc" / "035-gate3"
        work.mkdir(parents=True, exist_ok=True)
        plan = work / "plan.md"
        plan.write_text("**Scenario AC-PLAN-001: map**\n", encoding="utf-8")
    return brief, plan


class TestWalkthroughPre:
    def test_pre_includes_brief_plan_and_classified_files(
        self, tmp_git_repo: Path
    ) -> None:
        subprocess.run(
            ["git", "branch", "-m", "main"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
        )
        (tmp_git_repo / "src").mkdir()
        (tmp_git_repo / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_git_repo / "tests").mkdir()
        (tmp_git_repo / "tests" / "test_mod.py").write_text(
            "def test_x():\n    assert True\n", encoding="utf-8"
        )
        _git(tmp_git_repo, "add", "-A")
        _git(tmp_git_repo, "commit", "-m", "base")
        brief, plan = _seed_issue(tmp_git_repo)
        (tmp_git_repo / "src" / "mod.py").write_text("x = 2\n", encoding="utf-8")
        (tmp_git_repo / "tests" / "test_mod.py").write_text(
            "def test_x():\n    assert 2 == 2\n", encoding="utf-8"
        )
        _git(tmp_git_repo, "add", "-A")
        _git(tmp_git_repo, "commit", "-m", "change")

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["walkthrough", "pre"])

        assert result.exit_code == 0, result.stdout
        contract = json.loads(result.stdout)
        assert contract["issue_brief_path"] == str(brief.resolve())
        assert plan is not None
        assert contract["plan_path"] == str(plan.resolve())
        assert "tests/test_mod.py" in contract["test_files"]
        assert "src/mod.py" in contract["production_files"]
        assert "constitution_path" not in contract
        assert "prd_path" not in contract

    def test_pre_omits_constitution_unless_brief_names_it(
        self, tmp_git_repo: Path
    ) -> None:
        specs = tmp_git_repo / "specs"
        specs.mkdir(parents=True, exist_ok=True)
        const = specs / "constitution.md"
        const.write_text("# Constitution\n", encoding="utf-8")
        _seed_issue(tmp_git_repo, with_plan=False, name_constitution=True)

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["walkthrough", "pre"])

        assert result.exit_code == 0, result.stdout
        contract = json.loads(result.stdout)
        assert contract["constitution_path"] == str(const.resolve())

    @pytest.mark.behavioral
    def test_pre_plan_path_null_when_absent(self, tmp_git_repo: Path) -> None:
        brief, plan = _seed_issue(tmp_git_repo, with_plan=False)
        assert plan is None
        # Committed change forces a non-empty diff so the JSON contract holds here,
        # unlike the empty-diff SKIP tree below (AO-035-01 vs AC-PLAN-001).
        (tmp_git_repo / "src_changed.py").write_text("x = 1\n", encoding="utf-8")
        _git(tmp_git_repo, "add", "-A")
        _git(tmp_git_repo, "commit", "-m", "change")

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["walkthrough", "pre"])

        assert result.exit_code == 0, result.stdout
        contract = json.loads(result.stdout)
        assert contract["issue_brief_path"] == str(brief.resolve())
        assert contract["plan_path"] is None
        assert "constitution_path" not in contract

    @pytest.mark.behavioral
    def test_pre_empty_diff_exits_with_skip(self, tmp_git_repo: Path) -> None:
        # No commits beyond main and no seeded brief: empty diff tree (AO-035-01
        # Error Category), distinct from the JSON plan-null tree above.
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["walkthrough", "pre"])

        assert result.exit_code == 0, result.stdout
        assert result.stdout.strip() == "SKIP: no changes since main"
