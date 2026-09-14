"""GH-150: auto micro injects this-task card only, plus train feedback."""

from __future__ import annotations

import json
from contextlib import chdir
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.cli.micro import _build_auto_prompt, _resolve_task_context
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord

runner = CliRunner()

_ISSUE_ID = "ISS-ADH-150"
_TSK_A = "TSK-150-01"
_TSK_B = "TSK-150-02"
_SLUG = "150-this-task-card"
_SOURCE_FILE = f"specs/adhoc/issues/{_SLUG}.md"

_TSK_A_BODY = "UNIQUE_TSK_A_CARD_BODY_GH150_ALPHA"
_TSK_A_FLOW = "FLOW-ALPHA-UNIQUE-GH150"
_TSK_A_TITLE = "Inject this-task card only"
_TSK_B_BODY = "UNIQUE_TSK_B_CARD_BODY_GH150_SIBLING"
_TSK_B_TITLE = "Sibling must not leak into the prompt"
_TRAIN_FEEDBACK = "UNIQUE_TRAIN_FEEDBACK_MARKER_GH150"

_AUTO_PHASES = ("red", "green", "judge", "refactor")


def _make_task_record(
    task_id: str,
    *,
    description: str,
    status: str = "PENDING",
) -> TaskRecord:
    return TaskRecord(
        id=task_id,
        issue_id=_ISSUE_ID,
        description=description,
        status=status,
        execution_mode="TDD",
    )


def _write_ledger(ledger_path: Path, *records: TaskRecord) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    for record in records:
        ledger_path.open("a", encoding="utf-8").write(record.model_dump_json() + "\n")


def _tsk_a_card() -> str:
    return (
        f"- {_TSK_A}: {_TSK_A_TITLE}\n"
        f"  - **Flow References**: {_TSK_A_FLOW}\n"
        "  - **Acceptance Criteria**: AC-PLAN-001\n"
        f"  - **Details**: {_TSK_A_BODY}\n"
    )


def _tsk_b_card() -> str:
    return f"- {_TSK_B}: {_TSK_B_TITLE}\n  - **Details**: {_TSK_B_BODY}\n"


def _seed_two_task_workspace(root: Path) -> tuple[dict, Path]:
    """Write issues.jsonl + two-task board + PENDING ledger rows.

    TSK-A is first in ``tasks.md`` so the pending queue pins it as active.
    Ledger descriptions stay generic so card-only strings prove injection.
    """
    issue_path = root / _SOURCE_FILE
    issue_path.parent.mkdir(parents=True, exist_ok=True)
    issue_path.write_text("# GH-150 this-task card\n", encoding="utf-8")
    (root / "specs" / "issues.jsonl").write_text(
        json.dumps({"issue_id": _ISSUE_ID, "source_file": _SOURCE_FILE}) + "\n",
        encoding="utf-8",
    )
    plan_dir = root / "specs" / "adhoc" / _SLUG
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan.md").write_text(
        "**Scenario AC-PLAN-001: this-task card injection**\n",
        encoding="utf-8",
    )
    (plan_dir / "tasks.md").write_text(
        "# Tasks\n\n" + _tsk_a_card() + "\n" + _tsk_b_card(),
        encoding="utf-8",
    )
    ledger_path = plan_dir / "tasks.jsonl"
    _write_ledger(
        ledger_path,
        _make_task_record(_TSK_A, description="Alpha ledger row only"),
        _make_task_record(_TSK_B, description="Beta ledger row only"),
    )
    session_path = root / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    SessionState(current_phase="IDLE", active_issue_id=_ISSUE_ID).save(session_path)
    return {
        "id": _TSK_A,
        "issue_id": _ISSUE_ID,
        "description": "Alpha ledger row only",
        "status": "PENDING",
        "execution_mode": "TDD",
    }, ledger_path


class TestAutoPromptThisTaskCardOnly:
    """Assemble the existing auto templates; this-task card, no sibling, train."""

    def test_auto_templates_inject_this_task_card_not_sibling_plus_train_feedback(
        self, tmp_path: Path
    ) -> None:
        task, _ledger = _seed_two_task_workspace(tmp_path)
        card_a = _tsk_a_card().strip()

        for phase in _AUTO_PHASES:
            prompt = _build_auto_prompt(
                phase, task, tmp_path, train_feedback=_TRAIN_FEEDBACK
            )
            assert card_a in prompt, (
                f"{phase}: assembled auto prompt must contain the full TSK-A "
                f"markdown card, not merely the ledger id/description"
            )
            assert _TSK_A_BODY in prompt, (
                f"{phase}: TSK-A distinctive card body must be in the prompt"
            )
            assert _TSK_A_FLOW in prompt, (
                f"{phase}: TSK-A Flow References must come from the injected card"
            )
            assert _TSK_B_BODY not in prompt, (
                f"{phase}: sibling TSK-B card body must not appear in the prompt"
            )
            assert _TSK_B_TITLE not in prompt, (
                f"{phase}: sibling TSK-B title must not appear in the prompt"
            )
            assert _TRAIN_FEEDBACK in prompt, (
                f"{phase}: train_feedback must be in the assembled prompt"
            )
            assert '"execution_mode": "TDD"' not in prompt, (
                f"{phase}: {{task_content}} must be the markdown card, not ledger JSON"
            )


class TestPreCliResolvesIntendedTask:
    """Manual pre CLI (or judge's selector) names TSK-A, not the sibling."""

    def _invoke_pre(self, root: Path, phase: str) -> object:
        with chdir(root):
            return runner.invoke(cli, [phase, "pre"])

    def test_red_green_refactor_pre_resolve_queued_task_a_not_sibling(
        self, tmp_git_repo: Path
    ) -> None:
        _seed_two_task_workspace(tmp_git_repo)
        for phase in ("red", "green", "refactor"):
            result = self._invoke_pre(tmp_git_repo, phase)
            assert result.exit_code == 0, (
                f"{phase} pre: expected exit 0, got {result.exit_code}: {result.output}"
            )
            data = json.loads(result.output)
            assert data.get("task_id") == _TSK_A, (
                f"{phase} pre must resolve the queued TSK-A, not sibling TSK-B; "
                f"got {data.get('task_id')!r}"
            )
            assert data.get("task_id") != _TSK_B

    def test_judge_task_selector_resolves_queued_task_a_not_sibling(
        self, tmp_git_repo: Path
    ) -> None:
        """``judge pre`` is a protected-module scan and does not emit ``task_id``.

        The function that selects the task for JUDGE (and the other micro
        pre commands) is ``_resolve_task_context``.
        """
        _seed_two_task_workspace(tmp_git_repo)
        with chdir(tmp_git_repo):
            resolved = _resolve_task_context(None, tmp_git_repo)
        assert resolved is not None
        rec, _ledger = resolved
        assert rec.get("id") == _TSK_A, (
            "JUDGE task selector must pin queued TSK-A, not sibling TSK-B; "
            f"got {rec.get('id')!r}"
        )
        assert rec.get("id") != _TSK_B


def _seed_acceptance_workspace(root: Path) -> tuple[dict, Path]:
    task, ledger = _seed_two_task_workspace(root)
    (root / _SOURCE_FILE).write_text(
        "# Issue scope\nKeep public behavior intact.\n\n"
        "## Acceptance Outline\n"
        "- **AO-001**: Selected outline.\n  - Boundary: preserve empty input.\n"
        "- **AO-150-02**: Shared outline.\n"
        "- **AO-003**: UNASSIGNED_OUTLINE\n\n"
        "## Scope Boundaries\nDo not change the API.\n",
        encoding="utf-8",
    )
    (ledger.parent / "plan.md").write_text(
        "# Plan\n## Acceptance Contract\n"
        "**Scenario AC-PLAN-001: Selected scenario**\n"
        "- **Source Outline**: `AO-001`, `AO-150-02`\n"
        "- **Given**: an empty input\n- **When**: the API runs\n"
        "- **Then**: preserve empty output\n"
        "- **Verification Mode**: automated\n\n"
        "**Scenario AC-PLAN-002: UNASSIGNED_SCENARIO**\n"
        "- **Source Outline**: `AO-003`\n\n"
        "## Implementation Approach\nReuse the existing API.\n",
        encoding="utf-8",
    )
    return task, ledger


@pytest.mark.behavioral
@pytest.mark.parametrize("phase", ["red", "green"])
def test_pre_and_auto_inject_matching_task_acceptance(
    tmp_git_repo: Path, phase: str
) -> None:
    task, ledger = _seed_acceptance_workspace(tmp_git_repo)
    card = ledger.parent / "tasks.md"
    card.write_text(
        card.read_text().replace(
            _TSK_A_BODY,
            _TSK_A_BODY + "\n  - **Judge Feedback**: See AC-PLAN-002",
        ),
        encoding="utf-8",
    )
    with chdir(tmp_git_repo):
        result = runner.invoke(cli, [phase, "pre", "--task", _TSK_A])
    assert result.exit_code == 0, result.output
    spec = json.loads(result.output)["spec_content"]
    prompt = _build_auto_prompt(phase, task, tmp_git_repo)
    assert spec in prompt
    for text in (
        "**Scenario AC-PLAN-001: Selected scenario**",
        "**Then**: preserve empty output",
        "**AO-001**: Selected outline.",
        "Boundary: preserve empty input.",
        "**AO-150-02**: Shared outline.",
        "Keep public behavior intact.",
        "Reuse the existing API.",
        "Do not change the API.",
    ):
        assert text in spec
    assert "UNASSIGNED_SCENARIO" not in spec
    assert "UNASSIGNED_OUTLINE" not in spec
    assert "UNASSIGNED_SCENARIO" not in prompt
    assert "UNASSIGNED_OUTLINE" not in prompt
    judge = _build_auto_prompt("judge", task, tmp_git_repo)
    assert "UNASSIGNED_SCENARIO" in judge


@pytest.mark.behavioral
@pytest.mark.parametrize("phase", ["red", "green"])
@pytest.mark.parametrize("missing", ["AC-PLAN-001", "AO-150-02"])
def test_pre_and_auto_reject_unresolved_acceptance(
    tmp_git_repo: Path, phase: str, missing: str
) -> None:
    from deviate.cli.micro import PhaseFailedError

    task, ledger = _seed_acceptance_workspace(tmp_git_repo)
    path = (
        ledger.parent / "plan.md"
        if missing.startswith("AC-")
        else tmp_git_repo / _SOURCE_FILE
    )
    path.write_text(path.read_text().replace(missing, "REMOVED"), encoding="utf-8")
    with chdir(tmp_git_repo):
        result = runner.invoke(cli, [phase, "pre", "--task", _TSK_A])
    assert result.exit_code == 1
    assert "TASK_ACCEPTANCE_UNRESOLVED" in result.output
    assert missing in result.output
    with pytest.raises(
        PhaseFailedError, match=f"TASK_ACCEPTANCE_UNRESOLVED.*{missing}"
    ):
        _build_auto_prompt(phase, task, tmp_git_repo)


@pytest.mark.behavioral
def test_acceptance_selection_uses_ledger_ids_and_deduplicates_outlines(
    tmp_path: Path,
) -> None:
    from deviate.cli.micro import _resolve_spec_md

    task, ledger = _seed_acceptance_workspace(tmp_path)
    plan_path = ledger.parent / "plan.md"
    plan_path.write_text(
        plan_path.read_text().replace("`AO-003`", "`AO-001`"), encoding="utf-8"
    )
    task["acceptance_criteria"] = [
        {"criterion_id": "AC-PLAN-002"},
        {"criterion_id": "AC-PLAN-001"},
    ]
    spec = _resolve_spec_md(tmp_path, task, task_scoped=True)
    assert "**Scenario AC-PLAN-002" in spec
    assert "**Scenario AC-PLAN-001" in spec
    assert spec.count("**AO-001**: Selected outline.") == 1
    assert "UNASSIGNED_OUTLINE" not in spec
    task["acceptance_criteria"] = [{"criterion_id": "AC-PLAN-002"}]
    spec = _resolve_spec_md(tmp_path, task, task_scoped=True)
    assert "**Scenario AC-PLAN-001" not in spec


@pytest.mark.behavioral
@pytest.mark.parametrize("token", ["AC-PLAN-001", "AO-001"])
def test_acceptance_selection_rejects_duplicate_definitions(
    tmp_path: Path, token: str
) -> None:
    from deviate.cli.micro import KernelError, _resolve_spec_md

    task, ledger = _seed_acceptance_workspace(tmp_path)
    path = (
        ledger.parent / "plan.md"
        if token.startswith("AC-")
        else tmp_path / _SOURCE_FILE
    )
    definition = (
        "**Scenario AC-PLAN-001: Duplicate**"
        if token.startswith("AC-")
        else "- **AO-001**: Duplicate"
    )
    header = (
        "## Acceptance Contract" if token.startswith("AC-") else "## Acceptance Outline"
    )
    path.write_text(
        path.read_text().replace(header, header + "\n" + definition),
        encoding="utf-8",
    )
    with pytest.raises(KernelError) as caught:
        _resolve_spec_md(tmp_path, task, task_scoped=True)
    assert caught.value.token == "TASK_ACCEPTANCE_UNRESOLVED"
    assert token in caught.value.detail


@pytest.mark.behavioral
def test_acceptance_selection_preserves_legacy_tasks_without_refs(
    tmp_path: Path,
) -> None:
    from deviate.cli.micro import _resolve_spec_md

    task, ledger = _seed_acceptance_workspace(tmp_path)
    (ledger.parent / "tasks.md").write_text(
        f"- {_TSK_A}: Legacy task\n", encoding="utf-8"
    )
    assert _resolve_spec_md(tmp_path, task, task_scoped=True) == _resolve_spec_md(
        tmp_path, task
    )
