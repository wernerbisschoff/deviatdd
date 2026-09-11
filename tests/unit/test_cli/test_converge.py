"""Tests for the opt-in Converge pack (ISS-ADH-058 / #219)."""

from __future__ import annotations

import json
import subprocess
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.core.commands import OPTIONAL_PACKS, commands_for_packs
from deviate.state.config import SessionState
from tests.conftest import _git_env

runner = CliRunner()

_ISSUE_ID = "ISS-ADH-058"
_SLUG = "058-converge-opt-in-pack"
_PROMPT = Path("src/deviate/prompts/commands/deviate-converge.md")
_SKILL = Path("src/deviate/prompts/skills/deviatdd/SKILL.md")


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
    with_tasks: bool = True,
    pending: bool = False,
    name_constitution: bool = False,
    name_explore: bool = False,
    filled_constitution: bool = False,
    extra_brief: str = "",
    checkout: bool = True,
) -> tuple[Path, Path | None, Path | None]:
    if checkout:
        _git(repo, "checkout", "-B", f"feat/adhoc/{_SLUG}")
    issues_dir = repo / "specs" / "adhoc" / "issues"
    issues_dir.mkdir(parents=True, exist_ok=True)
    extra = extra_brief
    if name_constitution:
        extra += "See specs/constitution.md\n"
    if name_explore:
        extra += "See specs/adhoc/explore.md\n"
    brief = issues_dir / f"{_SLUG}.md"
    brief.write_text(
        f"# converge\n\nAO-058-01 named check\nAC-ADHOC-058-01\n{extra}",
        encoding="utf-8",
    )
    _write_jsonl(
        repo / "specs" / "issues.jsonl",
        [
            {
                "issue_id": _ISSUE_ID,
                "source_file": f"specs/adhoc/issues/{_SLUG}.md",
            }
        ],
    )
    plan: Path | None = None
    tasks: Path | None = None
    work = repo / "specs" / "adhoc" / _SLUG
    if with_plan or with_tasks:
        work.mkdir(parents=True, exist_ok=True)
    if with_plan:
        plan = work / "plan.md"
        plan.write_text(
            "## Acceptance Contract\n"
            "**Scenario AC-PLAN-001: pack installs on opt-in**\n"
            "- **Current-Code Evidence**: src/deviate/core/commands.py\n"
            "**Scenario AC-PLAN-002: append-only gaps**\n"
            "- **Current-Code Evidence**: src/deviate/cli/converge.py\n",
            encoding="utf-8",
        )
    if with_tasks:
        tasks = work / "tasks.md"
        checkbox = "[ ] " if pending else "[x] "
        tasks.write_text(
            "# Tasks\n\n"
            "## Phase 1: Pack and CLI\n"
            f"- {checkbox}TSK-058-01: Register the converge pack\n"
            "  - **Type**: Feature\n"
            "  - **Mode**: TDD\n"
            "  - **Test Strategy**: unit\n"
            "  - **Files**:\n"
            "    - src/deviate/core/commands.py\n"
            "    - tests/unit/test_cli/test_converge.py\n",
            encoding="utf-8",
        )
        status = "PENDING" if pending else "COMPLETED"
        _write_jsonl(
            work / "tasks.jsonl",
            [
                {
                    "id": "TSK-058-01",
                    "issue_id": _ISSUE_ID,
                    "description": "Register the converge pack",
                    "status": status,
                    "execution_mode": "TDD",
                }
            ],
        )
    if filled_constitution:
        specs = repo / "specs"
        specs.mkdir(parents=True, exist_ok=True)
        (specs / "constitution.md").write_text(
            "# Constitution\n\n- Agents MUST NOT rewrite append-only ledgers.\n",
            encoding="utf-8",
        )
    return brief, plan, tasks


def _session(worktree: Path, issue_id: str = _ISSUE_ID) -> None:
    dot = worktree / ".deviate"
    dot.mkdir(parents=True, exist_ok=True)
    SessionState(current_phase="IDLE", active_issue_id=issue_id).save(
        dot / "session.json"
    )


class TestConvergePackOptIn:
    @pytest.mark.behavioral
    def test_converge_is_optional_pack_not_default(self) -> None:
        assert OPTIONAL_PACKS["converge"] == ("deviate-converge",)
        assert "deviate-converge" not in commands_for_packs()
        assert "deviate-converge" in commands_for_packs(("converge",))

    def test_default_setup_does_not_install_converge(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(cli, ["setup", "--agent", "opencode"])
        assert result.exit_code == 0, result.output
        commands = tmp_path / ".opencode" / "commands"
        assert (commands / "deviate-red.md").is_file()
        assert not (commands / "deviate-converge.md").exists()

    @pytest.mark.behavioral
    def test_setup_packs_converge_installs_slash_command(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(
                cli, ["setup", "--agent", "opencode", "--packs", "converge"]
            )
        assert result.exit_code == 0, result.output
        assert (tmp_path / ".opencode" / "commands" / "deviate-converge.md").is_file()

    @pytest.mark.behavioral
    def test_unknown_pack_still_fails_closed(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            result = runner.invoke(
                cli, ["setup", "--agent", "opencode", "--packs", "graphite"]
            )
        assert result.exit_code != 0


class TestConvergePre:
    @pytest.mark.behavioral
    def test_pre_emits_ready_contract_with_read_set(self, tmp_git_repo: Path) -> None:
        brief, plan, tasks = _seed_issue(tmp_git_repo, filled_constitution=True)
        assert plan is not None
        assert tasks is not None

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["converge", "pre"])

        assert result.exit_code == 0, result.stdout
        contract = json.loads(result.stdout)
        assert contract["status"] == "READY"
        assert contract["issue_id"] == _ISSUE_ID
        assert contract["issue_brief_path"] == str(brief.relative_to(tmp_git_repo))
        assert contract["plan_path"] == str(plan.relative_to(tmp_git_repo))
        assert contract["tasks_path"] == str(tasks.relative_to(tmp_git_repo))
        assert contract["constitution_path"] == "specs/constitution.md"
        assert "src/deviate/core/commands.py" in contract["in_scope_paths"]
        for key in ("issue_brief_path", "plan_path", "tasks_path", "constitution_path"):
            assert not contract[key].startswith("/")
        assert contract["pending_task_ids"] == []
        assert "diff" not in contract
        assert "prd_path" not in contract
        assert "explore_path" not in contract

    def test_pre_skips_unfilled_constitution_template(self, tmp_git_repo: Path) -> None:
        specs = tmp_git_repo / "specs"
        specs.mkdir(parents=True, exist_ok=True)
        (specs / "constitution.md").write_text(
            "# Project Constitution\n\n> TBD — populated by `/research`.\n",
            encoding="utf-8",
        )
        _seed_issue(tmp_git_repo)

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["converge", "pre"])

        assert result.exit_code == 0, result.stdout
        contract = json.loads(result.stdout)
        assert "constitution_path" not in contract

    def test_pre_omits_epic_explore_unless_brief_names_it(
        self, tmp_git_repo: Path
    ) -> None:
        explore = tmp_git_repo / "specs" / "adhoc" / "explore.md"
        explore.parent.mkdir(parents=True, exist_ok=True)
        explore.write_text("# leftover explore\n", encoding="utf-8")
        _seed_issue(tmp_git_repo)

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["converge", "pre"])

        assert result.exit_code == 0, result.stdout
        contract = json.loads(result.stdout)
        assert "explore_path" not in contract
        dumped = json.dumps(contract)
        assert "explore.md" not in dumped

    def test_pre_missing_brief_is_not_ready(self, tmp_git_repo: Path) -> None:
        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["converge", "pre"])

        assert result.exit_code != 0
        assert "brief" in result.stdout.lower()

    def test_pre_missing_plan_is_not_ready(self, tmp_git_repo: Path) -> None:
        _seed_issue(tmp_git_repo, with_plan=False)

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["converge", "pre"])

        assert result.exit_code != 0
        assert "plan" in result.stdout.lower()

    def test_pre_missing_tasks_is_not_ready(self, tmp_git_repo: Path) -> None:
        _seed_issue(tmp_git_repo, with_tasks=False)

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["converge", "pre"])

        assert result.exit_code != 0
        assert "tasks" in result.stdout.lower()

    def test_pre_pending_queue_is_not_ready(self, tmp_git_repo: Path) -> None:
        _seed_issue(tmp_git_repo, pending=True)

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["converge", "pre"])

        assert result.exit_code != 0
        assert "CONVERGE_NOT_READY" in result.stdout
        assert "drain" in result.stdout.lower() or "pending" in result.stdout.lower()


class TestConvergePost:
    def test_empty_findings_leaves_tasks_byte_unchanged(
        self, tmp_git_repo: Path
    ) -> None:
        _, _, tasks = _seed_issue(tmp_git_repo)
        assert tasks is not None
        before = tasks.read_bytes()

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["converge", "post", '{"findings":[]}'])

        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout)
        assert payload["status"] == "CONVERGED"
        assert tasks.read_bytes() == before
        assert "Phase" not in tasks.read_text(encoding="utf-8") or (
            "## Phase 2: Convergence" not in tasks.read_text(encoding="utf-8")
        )

    def test_omitted_findings_is_clean_no_op(self, tmp_git_repo: Path) -> None:
        _, _, tasks = _seed_issue(tmp_git_repo)
        assert tasks is not None
        before = tasks.read_bytes()

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["converge", "post"])

        assert result.exit_code == 0, result.stdout
        assert json.loads(result.stdout)["status"] == "CONVERGED"
        assert tasks.read_bytes() == before

    def test_missing_finding_appends_convergence_phase(
        self, tmp_git_repo: Path
    ) -> None:
        _, _, tasks = _seed_issue(tmp_git_repo)
        assert tasks is not None
        before = tasks.read_text(encoding="utf-8")
        findings = json.dumps(
            {
                "findings": [
                    {
                        "taxonomy": "missing",
                        "source_ref": "AC-PLAN-002",
                        "summary": "Append-only gap path is not implemented",
                    }
                ]
            }
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["converge", "post", findings])

        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout)
        assert payload["status"] == "APPENDED"
        assert payload["task_ids"] == ["TSK-058-02"]
        assert payload["phase"] == 2
        text = tasks.read_text(encoding="utf-8")
        assert text.startswith(before)
        assert "## Phase 2: Convergence" in text
        assert "TSK-058-02" in text
        assert "missing" in text
        assert "AC-PLAN-002" in text
        ledger_path = tmp_git_repo / "specs" / "adhoc" / _SLUG / "tasks.jsonl"
        rows = [
            json.loads(line)
            for line in ledger_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        appended = next(row for row in rows if row.get("id") == "TSK-058-02")
        assert appended["status"] == "PENDING"
        assert before in text

    def test_prior_convergence_phase_stays_and_next_is_numbered(
        self, tmp_git_repo: Path
    ) -> None:
        _, _, tasks = _seed_issue(tmp_git_repo)
        assert tasks is not None
        tasks.write_text(
            tasks.read_text(encoding="utf-8")
            + "\n## Phase 2: Convergence\n"
            + "- [x] TSK-058-02: prior gap\n",
            encoding="utf-8",
        )
        findings = json.dumps(
            {
                "findings": [
                    {
                        "taxonomy": "partial",
                        "source_ref": "AC-PLAN-001",
                        "summary": "Pack install path is incomplete",
                    }
                ]
            }
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["converge", "post", findings])

        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout)
        assert payload["phase"] == 3
        assert payload["task_ids"] == ["TSK-058-03"]
        text = tasks.read_text(encoding="utf-8")
        assert text.count("## Phase 2: Convergence") == 1
        assert "## Phase 3: Convergence" in text
        assert "- [x] TSK-058-02: prior gap" in text

    def test_critical_constitution_finding_is_ordered_first(
        self, tmp_git_repo: Path
    ) -> None:
        _seed_issue(tmp_git_repo, filled_constitution=True)
        findings = json.dumps(
            {
                "findings": [
                    {
                        "taxonomy": "partial",
                        "source_ref": "AC-PLAN-001",
                        "summary": "pack path incomplete",
                    },
                    {
                        "taxonomy": "contradicts",
                        "source_ref": "constitution MUST",
                        "summary": "rewrote an existing task",
                        "severity": "CRITICAL",
                    },
                ]
            }
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["converge", "post", findings])

        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout)
        assert payload["task_ids"] == ["TSK-058-02", "TSK-058-03"]
        tasks = tmp_git_repo / "specs" / "adhoc" / _SLUG / "tasks.md"
        text = tasks.read_text(encoding="utf-8")
        crit = text.index("contradicts")
        partial = text.index("partial")
        assert crit < partial

    def test_unrequested_does_not_delete_code(self, tmp_git_repo: Path) -> None:
        src = tmp_git_repo / "src" / "app.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("x = 1\n", encoding="utf-8")
        _seed_issue(tmp_git_repo)
        findings = json.dumps(
            {
                "findings": [
                    {
                        "taxonomy": "unrequested",
                        "source_ref": "AO-058-01",
                        "summary": "Review extra helper and justify or remove",
                    }
                ]
            }
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["converge", "post", findings])

        assert result.exit_code == 0, result.stdout
        assert src.read_text(encoding="utf-8") == "x = 1\n"
        tasks = (tmp_git_repo / "specs" / "adhoc" / _SLUG / "tasks.md").read_text(
            encoding="utf-8"
        )
        assert "unrequested" in tasks
        assert "justify" in tasks.lower() or "review" in tasks.lower()

    def test_invalid_taxonomy_does_not_write(self, tmp_git_repo: Path) -> None:
        _, _, tasks = _seed_issue(tmp_git_repo)
        assert tasks is not None
        before = tasks.read_bytes()
        findings = json.dumps(
            {
                "findings": [
                    {
                        "taxonomy": "style",
                        "source_ref": "AC-PLAN-001",
                        "summary": "nit",
                    }
                ]
            }
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["converge", "post", findings])

        assert result.exit_code != 0
        assert tasks.read_bytes() == before

    def test_ledger_failure_leaves_tasks_unchanged(self, tmp_git_repo: Path) -> None:
        _, _, tasks = _seed_issue(tmp_git_repo)
        assert tasks is not None
        before = tasks.read_bytes()
        findings = json.dumps(
            {
                "findings": [
                    {
                        "taxonomy": "missing",
                        "source_ref": "AC-PLAN-002",
                        "summary": "gap",
                    }
                ]
            }
        )

        with (
            chdir(tmp_git_repo),
            patch(
                "deviate.cli.converge.append_task_record",
                side_effect=OSError("disk full"),
            ),
        ):
            result = runner.invoke(cli, ["converge", "post", findings])

        assert result.exit_code != 0
        assert "LEDGER_APPEND_FAILED" in result.stdout
        assert tasks.read_bytes() == before


class TestConvergePrompt:
    @pytest.mark.behavioral
    def test_prompt_bounds_read_set_and_taxonomy(self) -> None:
        text = _PROMPT.read_text(encoding="utf-8")
        assert "MUST NOT read unless this brief names those paths" in text
        assert "epic explore" in text
        assert "missing" in text and "partial" in text
        assert "contradicts" in text and "unrequested" in text
        assert "deviate converge pre" in text
        assert "deviate converge post" in text
        assert "append-only" in text.lower() or "append_task_record" in text
        assert "byte-unchanged" in text or "CONVERGED" in text


class TestDeviatddSkillUntilHappy:
    @pytest.mark.behavioral
    def test_skill_drives_deviate_run_until_happy(self) -> None:
        text = _SKILL.read_text(encoding="utf-8")
        assert "deviate run" in text
        assert "converged" in text.lower() or "until happy" in text.lower()
        first = text.split("## Dispatch to slash commands", 1)[0]
        assert (
            "deviate meso run"
            not in first.split("## First action", 1)[-1].split(
                "## Code change policy", 1
            )[0]
        )
        assert "/deviate-walkthrough" not in first or "outside" in text.lower()
        assert "/deviate-converge" in text


class TestDeviateRunConvergeTail:
    def _worktree(self, tmp_git_repo: Path) -> Path:
        worktree = tmp_git_repo / ".worktrees" / "feat" / "adhoc" / _SLUG
        worktree.mkdir(parents=True, exist_ok=True)
        _session(worktree)
        return worktree

    def test_run_help_lists_converge_flag(self) -> None:
        result = runner.invoke(cli, ["run", "--help"])
        assert result.exit_code == 0, result.output
        ansi = __import__("re").compile(r"\x1b\[[0-9;]*m")
        output = ansi.sub("", result.output)
        assert "--converge" in output

    def test_run_without_pack_or_flag_does_not_converge(
        self, tmp_git_repo: Path
    ) -> None:
        worktree = self._worktree(tmp_git_repo)
        with chdir(tmp_git_repo):
            with (
                patch("deviate.cli._meso_run", return_value=str(worktree)),
                patch("deviate.cli._run_all") as mock_run_all,
                patch("deviate.cli._run_converge_pass") as mock_pass,
            ):
                result = runner.invoke(cli, ["run"])

        assert result.exit_code == 0, result.output
        mock_run_all.assert_called_once()
        mock_pass.assert_not_called()
        assert "CONVERGE_READY" not in result.output
        assert "CONVERGED" not in result.output

    def test_run_converge_flag_handoff_after_drain(self, tmp_git_repo: Path) -> None:
        worktree = self._worktree(tmp_git_repo)
        _seed_issue(worktree, checkout=False)
        with chdir(tmp_git_repo):
            with (
                patch("deviate.cli._meso_run", return_value=str(worktree)),
                patch("deviate.cli._run_all"),
            ):
                result = runner.invoke(cli, ["run", "--converge"])

        assert result.exit_code == 0, result.output
        assert "CONVERGE_READY" in result.output
        assert _ISSUE_ID in result.output

    def test_run_pack_available_enters_tail(self, tmp_git_repo: Path) -> None:
        worktree = self._worktree(tmp_git_repo)
        _seed_issue(worktree, checkout=False)
        cmd = worktree / ".opencode" / "commands"
        cmd.mkdir(parents=True, exist_ok=True)
        (cmd / "deviate-converge.md").write_text("# converge\n", encoding="utf-8")
        with chdir(tmp_git_repo):
            with (
                patch("deviate.cli._meso_run", return_value=str(worktree)),
                patch("deviate.cli._run_all"),
            ):
                result = runner.invoke(cli, ["run"])

        assert result.exit_code == 0, result.output
        assert "CONVERGE_READY" in result.output

    def test_run_converge_loops_when_pass_appends(self, tmp_git_repo: Path) -> None:
        worktree = self._worktree(tmp_git_repo)
        outcomes = iter(["appended", "converged"])

        def fake_pass(_root: Path) -> str:
            return next(outcomes)

        with chdir(tmp_git_repo):
            with (
                patch("deviate.cli._meso_run", return_value=str(worktree)),
                patch("deviate.cli._run_all") as mock_run_all,
                patch("deviate.cli._run_converge_pass", side_effect=fake_pass),
            ):
                result = runner.invoke(cli, ["run", "--converge"])

        assert result.exit_code == 0, result.output
        assert mock_run_all.call_count == 2
        assert "CONVERGED" in result.output

    def test_run_converge_not_ready_when_queue_remains(
        self, tmp_git_repo: Path
    ) -> None:
        worktree = self._worktree(tmp_git_repo)
        _seed_issue(worktree, pending=True, checkout=False)
        with chdir(tmp_git_repo):
            with (
                patch("deviate.cli._meso_run", return_value=str(worktree)),
                patch("deviate.cli._run_all"),
            ):
                result = runner.invoke(cli, ["run", "--converge"])

        assert result.exit_code != 0
        assert "CONVERGE_NOT_READY" in result.output
