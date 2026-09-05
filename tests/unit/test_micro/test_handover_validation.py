"""AC-PLAN-001 + AC-PLAN-005: task-id consistency in parse_output (US-045-01)."""

from __future__ import annotations

import pytest

from deviate.core.agent import AgentBackend, MalformedHandoverManifestError


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
