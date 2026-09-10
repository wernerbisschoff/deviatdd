"""Soft 12-point handover checklist at Meso Plan entry (ADH-059 / #220)."""

from __future__ import annotations

import json
import logging
from contextlib import chdir
from pathlib import Path

import pytest

from deviate.cli.meso import _plan_pre
from deviate.core.commands import compose_command_body, install_command
from deviate.prompts.assembly import load_template
from deviate.prompts.handover import (
    HANDOVER_CHECKLIST_BANNER,
    HANDOVER_CHECKLIST_QUESTIONS,
    HANDOVER_CHECKLIST_SKIPPED_LOG,
    emit_plan_handover_checklist,
    format_handover_checklist,
    should_emit_handover_checklist,
)

TRACEABLE_ISSUE_BODY = """
## User Stories Ledger

- **US-059-01**: As a planner, I want a handover checklist. *(Ref: FR-ADHOC-059)*

## Upstream Requirement Tracing

- **Requirements Tokens**: `FR-ADHOC-059`
- **Acceptance Criteria Tokens**: `AC-ADHOC-059-01`

## Acceptance Outline

- **AO-059-01** *(Ref: AC-ADHOC-059-01, US-059-01)*: TTY Plan entry surfaces checklist.
"""


def _setup_plan_env(path: Path, issue_id: str = "ISS-ADH-059") -> None:
    dot_dir = path / ".deviate"
    dot_dir.mkdir(parents=True, exist_ok=True)
    (dot_dir / "session.json").write_text(
        json.dumps({"current_phase": "PLAN", "active_issue_id": issue_id})
    )
    specs_dir = path / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    (specs_dir / "constitution.md").write_text("# Constitution\n")
    record = {
        "issue_id": issue_id,
        "type": "feature",
        "title": "Handover checklist",
        "status": "BACKLOG",
        "source_file": f"specs/adhoc/issues/{issue_id}.md",
        "timestamp": "2026-01-01T00:00:00Z",
    }
    (specs_dir / "issues.jsonl").write_text(json.dumps(record) + "\n")
    issue_dir = specs_dir / "adhoc" / "issues"
    issue_dir.mkdir(parents=True, exist_ok=True)
    (issue_dir / f"{issue_id}.md").write_text(TRACEABLE_ISSUE_BODY, encoding="utf-8")


def _extract_contract(output: str) -> dict:
    start = output.index("{")
    end = output.rindex("}") + 1
    return json.loads(output[start:end])


def _invoke_plan_pre(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> str:
    with chdir(tmp_path):
        _plan_pre(issue_id="ISS-ADH-059", skip_auto_claim=True)
        out, _ = capsys.readouterr()
    return out


class TestHandoverChecklistText:
    def test_shared_text_lists_all_twelve_questions(self) -> None:
        assert len(HANDOVER_CHECKLIST_QUESTIONS) == 12
        text = format_handover_checklist()
        assert HANDOVER_CHECKLIST_BANNER in text
        assert "Do not wait for answers" in text
        for question in HANDOVER_CHECKLIST_QUESTIONS:
            assert question in text

    def test_question_ten_allows_none_yet_on_first_plan(self) -> None:
        assert "none yet" in HANDOVER_CHECKLIST_QUESTIONS[9].lower()


class TestEmitHandoverChecklist:
    def test_tty_prints_checklist_without_prompting(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(
            "deviate.prompts.handover.should_emit_handover_checklist",
            lambda: True,
        )
        prompts: list[object] = []

        def _blocked_input(prompt: object = "") -> str:
            prompts.append(prompt)
            raise AssertionError("handover checklist must not block on input")

        monkeypatch.setattr("builtins.input", _blocked_input)
        emit_plan_handover_checklist()
        out, _ = capsys.readouterr()
        assert format_handover_checklist() in out
        assert prompts == []

    def test_non_tty_skips_checklist_and_logs_once(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setattr(
            "deviate.prompts.handover.should_emit_handover_checklist",
            lambda: False,
        )
        with caplog.at_level(logging.INFO, logger="deviate.prompts.handover"):
            emit_plan_handover_checklist()
        out, _ = capsys.readouterr()
        for question in HANDOVER_CHECKLIST_QUESTIONS:
            assert question not in out
        assert HANDOVER_CHECKLIST_SKIPPED_LOG in caplog.text

    def test_should_emit_follows_stdout_isatty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        assert should_emit_handover_checklist() is True
        monkeypatch.setattr("sys.stdout.isatty", lambda: False)
        assert should_emit_handover_checklist() is False


class TestPlanPreHandoverChecklist:
    @pytest.mark.behavioral
    def test_tty_plan_pre_surfaces_checklist_and_keeps_contract(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _setup_plan_env(tmp_path)
        monkeypatch.setattr(
            "deviate.prompts.handover.should_emit_handover_checklist",
            lambda: True,
        )
        out = _invoke_plan_pre(tmp_path, capsys)
        assert HANDOVER_CHECKLIST_BANNER in out
        for question in HANDOVER_CHECKLIST_QUESTIONS:
            assert question in out
        contract = _extract_contract(out)
        assert contract["status"] == "READY"
        assert contract["phase"] == "plan_pre"

    @pytest.mark.behavioral
    def test_non_tty_plan_pre_omits_checklist_and_emits_contract(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _setup_plan_env(tmp_path)
        monkeypatch.setattr(
            "deviate.prompts.handover.should_emit_handover_checklist",
            lambda: False,
        )
        out = _invoke_plan_pre(tmp_path, capsys)
        assert HANDOVER_CHECKLIST_BANNER not in out
        for question in HANDOVER_CHECKLIST_QUESTIONS:
            assert question not in out
        contract = _extract_contract(out)
        assert contract["status"] == "READY"
        assert contract["phase"] == "plan_pre"

    @pytest.mark.behavioral
    def test_json_flag_does_not_print_checklist(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _setup_plan_env(tmp_path)
        monkeypatch.setattr(
            "deviate.prompts.handover.should_emit_handover_checklist",
            lambda: True,
        )
        with chdir(tmp_path):
            _plan_pre(issue_id="ISS-ADH-059", skip_auto_claim=True, json=True)
            out, _ = capsys.readouterr()
        assert HANDOVER_CHECKLIST_BANNER not in out
        for question in HANDOVER_CHECKLIST_QUESTIONS:
            assert question not in out


class TestPlanOverlaySharesChecklist:
    def test_auto_plan_prompt_includes_shared_checklist(self) -> None:
        composed = load_template("plan")
        assert format_handover_checklist() in composed

    def test_auto_tasks_prompt_omits_handover_checklist(self) -> None:
        composed = load_template("tasks")
        assert format_handover_checklist() not in composed
        assert HANDOVER_CHECKLIST_BANNER not in composed

    def test_manual_plan_install_includes_shared_checklist(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "agent" / "commands"
        assert install_command("deviate-plan", target)
        installed = (target / "deviate-plan.md").read_text(encoding="utf-8")
        assert format_handover_checklist() in installed

    def test_compose_plan_body_includes_shared_checklist(self, tmp_path: Path) -> None:
        core_dir = (
            Path(__file__).resolve().parents[3] / "src" / "deviate" / "prompts" / "core"
        )
        raw = (
            "---\n"
            "name: deviate-plan\n"
            "layer: meso\n"
            "---\n\n"
            "<system_instructions>\nplan body\n</system_instructions>\n"
        )
        composed = compose_command_body(raw, core_dir)
        assert composed is not None
        assert format_handover_checklist() in composed
