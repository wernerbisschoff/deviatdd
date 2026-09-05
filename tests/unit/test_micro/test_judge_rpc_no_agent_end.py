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
