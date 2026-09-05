"""AC-PLAN-001 + AC-PLAN-005: task-id consistency in parse_output (US-045-01)."""

from __future__ import annotations

import pytest

import subprocess
from unittest.mock import patch

from rich.console import Console

from deviate.cli.micro import PhaseFailedError, _invoke_agent
from deviate.core.agent import (
    AgentBackend,
    HandoverManifest,
    MalformedHandoverManifestError,
)


def _manifest(task_id_line: str) -> str:
    return (
        "<handover_manifest>\n"
        "```yaml\n"
        'phase: "RED"\n'
        'status: "PASS"\n'
        f"{task_id_line}\n"
        'verdict: "pass"\n'
        'next_action: "continue_refactor"\n'
        'rationale: "done"\n'
        "```\n"
    )


@pytest.mark.behavioral
def test_mismatched_task_id_rejected_with_expected_vs_received() -> None:
    out = _manifest('task_id: "TSK-999-99"')
    with pytest.raises(MalformedHandoverManifestError) as exc:
        AgentBackend.parse_output(out, "stub", expected_task_id="TSK-045-01")
    msg = str(exc.value)
    assert "TSK-045-01" in msg
    assert "TSK-999-99" in msg


@pytest.mark.behavioral
def test_valid_manifest_passes_through_unchanged() -> None:
    out = _manifest('task_id: "TSK-045-01"')
    manifest = AgentBackend.parse_output(out, "stub", expected_task_id="TSK-045-01")
    assert manifest.task_id == "TSK-045-01"
    assert manifest.phase == "RED"
    assert manifest.status == "PASS"
    assert manifest.parse_errors == []


@pytest.mark.behavioral
def test_missing_task_id_treated_as_mismatch() -> None:
    out = _manifest("# no task id")
    with pytest.raises(MalformedHandoverManifestError) as exc:
        AgentBackend.parse_output(out, "stub", expected_task_id="TSK-045-01")
    assert "TSK-045-01" in str(exc.value)


@pytest.mark.behavioral
def test_unknown_extra_fields_still_pass() -> None:
    out = _manifest('task_id: "TSK-045-01"').replace(
        "```\n", 'legacy_note: "keep me"\n```\n'
    )
    manifest = AgentBackend.parse_output(out, "stub", expected_task_id="TSK-045-01")
    assert manifest.task_id == "TSK-045-01"
    assert manifest.parse_errors == []


# TSK-045-02 (AC-PLAN-002/003/004, US-045-01): contradiction rejection plus
# diagnostic-preserving failures in `deviate.cli.micro._invoke_agent`.


def _contradiction_manifest() -> HandoverManifest:
    return HandoverManifest(
        phase="JUDGE",
        status="PASS",
        task_id="TSK-045-02",
        verdict="COMPLIANCE_VIOLATION",
        next_action="revert_red",
        rationale="judge found a violation",
    )


def _run_invoke(manifest=None, *, output_lines=(), error=None):
    def _fake(prompt, *args, **kwargs):
        callback = kwargs.get("output_callback")
        for line in output_lines:
            if callback is not None:
                callback(line)
        if error is not None:
            raise error
        return manifest

    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with (
        patch.object(AgentBackend, "invoke", side_effect=_fake),
        patch("deviate.cli.micro._run_pytest", return_value=completed),
        patch("deviate.cli.micro._log_run"),
        patch("deviate.cli.micro._write_invoke_sidecars"),
    ):
        return _invoke_agent(
            "prompt",
            Console(quiet=True),
            backend_name="pi",
            task_id="TSK-045-02",
            phase="JUDGE",
        )


@pytest.mark.behavioral
def test_pass_with_violation_verdict_rejected_as_contradiction() -> None:
    with pytest.raises(PhaseFailedError) as exc:
        _run_invoke(_contradiction_manifest())
    msg = str(exc.value)
    assert "contradiction" in msg.lower()
    assert "COMPLIANCE_VIOLATION" in msg
    assert "revert_red" in msg


@pytest.mark.behavioral
def test_consistent_failure_violation_passes_through_unchanged() -> None:
    manifest = HandoverManifest(
        phase="JUDGE",
        status="FAILURE",
        task_id="TSK-045-02",
        verdict="COMPLIANCE_VIOLATION",
        next_action="revert_red",
        rationale="genuinely failed",
    )
    result = _run_invoke(manifest)
    assert result.manifest is manifest


@pytest.mark.behavioral
def test_consistent_clean_pass_passes_through_unchanged() -> None:
    manifest = HandoverManifest(
        phase="JUDGE",
        status="PASS",
        task_id="TSK-045-02",
        verdict="COMPLIANCE_PASS",
        next_action="skip_refactor",
        rationale="all green",
    )
    result = _run_invoke(manifest)
    assert result.manifest is manifest


@pytest.mark.behavioral
def test_error_without_rationale_carries_tail_and_specific_event() -> None:
    manifest = HandoverManifest(
        phase="GREEN",
        status="ERROR",
        task_id="TSK-045-02",
        rationale="",
    )
    lines = ("agent line one", "agent tail marker line")
    with pytest.raises(PhaseFailedError) as exc:
        _run_invoke(manifest, output_lines=lines)
    msg = str(exc.value)
    assert "HANDOVER_INVALID" in msg
    assert "agent tail marker line" in msg
    assert "unknown" not in msg.lower()


@pytest.mark.behavioral
def test_error_without_rationale_and_empty_output_names_defect() -> None:
    manifest = HandoverManifest(
        phase="GREEN",
        status="ERROR",
        task_id="TSK-045-02",
        rationale=None,
    )
    with pytest.raises(PhaseFailedError) as exc:
        _run_invoke(manifest, output_lines=())
    msg = str(exc.value)
    assert "HANDOVER_INVALID" in msg or "rationale" in msg.lower()
    assert "unknown" not in msg.lower()


@pytest.mark.behavioral
def test_missing_manifest_preserves_plain_test_defect_diagnosis() -> None:
    error = MalformedHandoverManifestError("No YAML handover manifest detected")
    lines = ("plain diagnosis: failure_kind: test_defect",)
    result = _run_invoke(None, output_lines=lines, error=error)
    manifest, tail = result
    assert manifest is None
    assert "test_defect" in tail


@pytest.mark.behavioral
def test_hostile_extra_keys_stay_inert_data() -> None:
    manifest = HandoverManifest(
        phase="JUDGE",
        status="PASS",
        task_id="TSK-045-02",
        verdict="COMPLIANCE_PASS",
        next_action="skip_refactor",
        rationale="all green",
        **{"__import__": "os", "eval": "1+1"},
    )
    result = _run_invoke(manifest)
    assert result.manifest is manifest
    assert result.manifest.model_extra["__import__"] == "os"


# TSK-045-03 (AC-PLAN-006/007, US-045-02): exactly one format-correction retry.


def _retry_manifest() -> HandoverManifest:
    return HandoverManifest(
        phase="RED",
        status="PASS",
        task_id="TSK-045-03",
        verdict="pass",
        next_action="continue_refactor",
        rationale="recovered",
    )


def _run_retry_case(side_effects: list, prompt_holder: list) -> object:
    def _fake(prompt, *args, **kwargs):
        prompt_holder.append(prompt)
        effect = side_effects[len(prompt_holder) - 1]
        if isinstance(effect, BaseException):
            raise effect
        return effect

    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with (
        patch.object(AgentBackend, "invoke", side_effect=_fake),
        patch("deviate.cli.micro._run_pytest", return_value=completed),
        patch("deviate.cli.micro._log_run"),
        patch("deviate.cli.micro._write_invoke_sidecars"),
    ):
        return _invoke_agent(
            "prompt",
            Console(quiet=True),
            backend_name="pi",
            task_id="TSK-045-03",
            phase="RED",
        )


@pytest.mark.behavioral
def test_unparseable_first_attempt_recovers_via_exactly_one_retry() -> None:
    prompts: list = []
    first = MalformedHandoverManifestError("No YAML handover manifest detected")
    result = _run_retry_case([first, _retry_manifest()], prompts)
    assert result.manifest is not None
    assert result.manifest.task_id == "TSK-045-03"
    assert len(prompts) == 2
    assert prompts[0] == "prompt"
    assert "format" in prompts[1].lower()


@pytest.mark.behavioral
def test_failed_correction_raises_specific_error_without_bare_unknown() -> None:
    prompts: list = []
    miss = MalformedHandoverManifestError("No YAML handover manifest detected")
    with pytest.raises(PhaseFailedError) as exc:
        _run_retry_case([miss, miss], prompts)
    msg = str(exc.value)
    assert len(prompts) == 2
    assert "unknown" not in msg.lower()
    assert "correction" in msg.lower() or "HANDOVER_INVALID" in msg


@pytest.mark.spy
def test_retry_path_never_issues_third_backend_call() -> None:
    prompts: list = []
    miss = MalformedHandoverManifestError("No YAML handover manifest detected")
    with pytest.raises(PhaseFailedError):
        _run_retry_case([miss, miss], prompts)
    assert len(prompts) == 2
