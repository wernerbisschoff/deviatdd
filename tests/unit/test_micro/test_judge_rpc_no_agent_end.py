"""TSK-046-01 RED: no-agent_end RPC run surfaces pi-side response error.

AC-PLAN-001 (US-046-01, AO-046-01): RPC stdout holding a failed ``prompt``
response and no ``agent_end`` event with exit code 0 raises
``EmptyOutputError`` carrying the response error text plus stderr.
AC-PLAN-004 (US-046-02, AO-046-02): valid ``agent_end`` and nonzero-exit
paths behave as before.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from deviate.core.agent import (
    AgentBackend,
    AgentSubprocessError,
    EmptyOutputError,
)

PI_ERROR = "Cannot read properties of undefined (reading 'tools')"


def _proc(stdout: str, stderr: str = "", exit_code: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.communicate.return_value = (stdout.encode("utf-8"), stderr.encode("utf-8"))
    proc.returncode = exit_code
    return proc


def _invoke(proc: MagicMock) -> tuple[str, str]:
    return AgentBackend()._invoke_rpc_blocking(
        proc, ["pi", "--mode", "rpc"], "judge prompt", 60, "pi"
    )


@pytest.mark.behavioral
def test_no_agent_end_raises_empty_output_with_response_error() -> None:
    """AC-PLAN-001: failed prompt response plus stderr surfaces in EmptyOutputError."""
    stdout = (
        json.dumps({"type": "agent_start"})
        + "\n"
        + json.dumps({"type": "response", "success": False, "error": PI_ERROR})
        + "\n"
    )
    proc = _proc(stdout, stderr="rpc stderr line")
    with pytest.raises(EmptyOutputError) as exc_info:
        _invoke(proc)
    assert PI_ERROR in str(exc_info.value)
    assert "rpc stderr line" in str(exc_info.value)


@pytest.mark.behavioral
def test_no_agent_end_skips_malformed_lines() -> None:
    """AC-PLAN-001 edge: malformed JSON lines never crash the scanner."""
    stdout = (
        "not json at all\n"
        + json.dumps({"type": "response", "success": False, "error": PI_ERROR})
        + "\n"
    )
    proc = _proc(stdout)
    with pytest.raises(EmptyOutputError) as exc_info:
        _invoke(proc)
    assert PI_ERROR in str(exc_info.value)


@pytest.mark.behavioral
def test_no_agent_end_without_error_keys_falls_back_to_stderr() -> None:
    """AC-PLAN-001 edge: missing error/message keys fall back to stderr alone."""
    stdout = json.dumps({"type": "response", "success": False}) + "\n"
    proc = _proc(stdout, stderr="only stderr context")
    with pytest.raises(EmptyOutputError) as exc_info:
        _invoke(proc)
    assert "only stderr context" in str(exc_info.value)


@pytest.mark.behavioral
def test_nonzero_exit_still_raises_subprocess_error_first() -> None:
    """AC-PLAN-004 pin: nonzero exit keeps the AgentSubprocessError branch first."""
    stdout = (
        json.dumps({"type": "response", "success": False, "error": PI_ERROR}) + "\n"
    )
    proc = _proc(stdout, stderr="boom", exit_code=1)
    with pytest.raises(AgentSubprocessError):
        _invoke(proc)


@pytest.mark.behavioral
def test_valid_agent_end_flows_through_unchanged() -> None:
    """AC-PLAN-004: valid agent_end manifest flows through unchanged."""
    manifest = 'phase: JUDGE\nstatus: "PASS"\n'
    stdout = (
        json.dumps({"type": "agent_start"})
        + "\n"
        + json.dumps({"type": "agent_end", "message": {"content": manifest}})
        + "\n"
    )
    text, _stderr = _invoke(_proc(stdout))
    assert text == manifest


PI_SIDECAR_ERROR = "pi-side boom"


@pytest.mark.behavioral
def test_invoke_agent_writes_sidecar_on_empty_output_judge() -> None:
    """AC-PLAN-002: JUDGE empty-manifest path writes sidecar with pi-side text."""
    import unittest.mock as _mock

    import deviate.cli.micro as micro
    from deviate.core.agent import EmptyOutputError
    from rich.console import Console

    seen: dict[str, object] = {}
    events: list[str] = []

    def fake_sidecars(
        *, task_id: str, phase: str, stdout: str, prompt: str = ""
    ) -> None:
        seen["task_id"] = task_id
        seen["phase"] = phase
        seen["stdout"] = stdout

    def fake_log(event: str, **kwargs: object) -> None:
        events.append(event)

    backend = MagicMock()
    backend.invoke.side_effect = EmptyOutputError(PI_SIDECAR_ERROR)
    with (
        _mock.patch.object(micro, "AgentBackend", return_value=backend),
        _mock.patch.object(micro, "_write_invoke_sidecars", side_effect=fake_sidecars),
        _mock.patch.object(micro, "_log_run", side_effect=fake_log),
    ):
        manifest, _tail = micro._invoke_agent(
            "judge prompt",
            Console(),
            task_id="TSK-046-02",
            phase="JUDGE",
        )
    assert manifest is None
    assert PI_SIDECAR_ERROR in str(seen.get("stdout", ""))
    assert "JUDGE_AGENT_NO_AGENT_END" in events


@pytest.mark.spy
def test_invoke_agent_no_distinguishing_event_for_non_judge() -> None:
    """AC-PLAN-002: sidecar write stays generic, event is JUDGE-scoped."""
    import unittest.mock as _mock

    import deviate.cli.micro as micro
    from deviate.core.agent import EmptyOutputError
    from rich.console import Console

    events: list[str] = []

    def fake_log(event: str, **kwargs: object) -> None:
        events.append(event)

    backend = MagicMock()
    backend.invoke.side_effect = EmptyOutputError(PI_SIDECAR_ERROR)
    with (
        _mock.patch.object(micro, "AgentBackend", return_value=backend),
        _mock.patch.object(micro, "_write_invoke_sidecars"),
        _mock.patch.object(micro, "_log_run", side_effect=fake_log),
    ):
        micro._invoke_agent("red prompt", Console(), task_id="TSK-046-02", phase="RED")
    assert "JUDGE_AGENT_NO_AGENT_END" not in events


@pytest.mark.behavioral
def test_invoke_agent_empty_stderr_keeps_response_error_in_sidecar() -> None:
    """AC-PLAN-003: empty stderr still writes the response error text."""
    import unittest.mock as _mock

    import deviate.cli.micro as micro
    from deviate.core.agent import EmptyOutputError
    from rich.console import Console

    seen: dict[str, object] = {}

    def fake_sidecars(
        *, task_id: str, phase: str, stdout: str, prompt: str = ""
    ) -> None:
        seen["stdout"] = stdout

    backend = MagicMock()
    backend.invoke.side_effect = EmptyOutputError(PI_SIDECAR_ERROR)
    with (
        _mock.patch.object(micro, "AgentBackend", return_value=backend),
        _mock.patch.object(micro, "_write_invoke_sidecars", side_effect=fake_sidecars),
    ):
        micro._invoke_agent(
            "judge prompt",
            Console(),
            task_id="TSK-046-02",
            phase="JUDGE",
        )
    assert PI_SIDECAR_ERROR in str(seen.get("stdout", ""))


@pytest.mark.behavioral
def test_judge_phase_failed_error_carries_pi_side_text(tmp_path) -> None:
    """AC-PLAN-002: JUDGE PhaseFailedError message carries the pi-side text."""
    import subprocess
    import unittest.mock as _mock
    from pathlib import Path
    from rich.console import Console

    import deviate.cli.micro as micro
    from deviate.state.config import SessionState

    task = {
        "id": "TSK-046-02",
        "issue_id": "ISS-ADH-046",
        "description": "Write judge sidecar and distinguishing event",
        "status": "PENDING",
        "execution_mode": "TDD",
    }
    ledger_path = tmp_path / "tasks.jsonl"
    session = SessionState()
    session_path = tmp_path / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    with (
        _mock.patch.object(micro, "Path", wraps=Path),
        _mock.patch.object(
            micro, "_refresh_session_commit_anchors", return_value=False
        ),
        _mock.patch.object(
            micro, "_assemble_judge_injected_diff", return_value="diff text"
        ),
        _mock.patch.object(micro, "_build_auto_prompt", return_value="judge prompt"),
        _mock.patch.object(micro, "resolve_model_for_phase", return_value=None),
        _mock.patch.object(
            micro, "_invoke_agent", return_value=(None, PI_SIDECAR_ERROR)
        ),
        _mock.patch.object(
            micro,
            "_run_pytest",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            ),
        ),
    ):
        with pytest.raises(micro.PhaseFailedError) as exc_info:
            micro._run_judge_phase(task, ledger_path, session, session_path, Console())
    assert PI_SIDECAR_ERROR in str(exc_info.value)


@pytest.mark.behavioral
def test_valid_manifest_run_emits_no_distinguishing_event(tmp_path) -> None:
    """AC-PLAN-004: valid agent_end run keeps existing events only."""
    import subprocess
    import unittest.mock as _mock
    from pathlib import Path
    from rich.console import Console

    import deviate.cli.micro as micro
    from deviate.core.agent import HandoverManifest
    from deviate.state.config import SessionState

    manifest = HandoverManifest(phase="JUDGE", status="PASS", verdict="COMPLIANCE_PASS")
    events: list[str] = []
    real_log = micro._log_run

    def fake_log(event: str, **kwargs: object) -> None:
        events.append(event)
        if event != "JUDGE_AGENT_NO_AGENT_END":
            try:
                real_log(event, **kwargs)
            except Exception:
                pass

    task = {
        "id": "TSK-046-02",
        "issue_id": "ISS-ADH-046",
        "description": "Write judge sidecar and distinguishing event",
        "status": "PENDING",
        "execution_mode": "TDD",
    }
    ledger_path = tmp_path / "tasks.jsonl"
    session = SessionState()
    session_path = tmp_path / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    with (
        _mock.patch.object(micro, "Path", wraps=Path),
        _mock.patch.object(
            micro, "_refresh_session_commit_anchors", return_value=False
        ),
        _mock.patch.object(
            micro, "_assemble_judge_injected_diff", return_value="diff text"
        ),
        _mock.patch.object(micro, "_build_auto_prompt", return_value="judge prompt"),
        _mock.patch.object(micro, "resolve_model_for_phase", return_value=None),
        _mock.patch.object(micro, "_invoke_agent", return_value=(manifest, "")),
        _mock.patch.object(micro, "_log_run", side_effect=fake_log),
        _mock.patch.object(
            micro,
            "_run_pytest",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            ),
        ),
        _mock.patch.object(micro, "_apply_judge_verdict", return_value=session),
    ):
        micro._run_judge_phase(task, ledger_path, session, session_path, Console())
    assert "JUDGE_AGENT_NO_AGENT_END" not in events
