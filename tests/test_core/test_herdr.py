from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import pytest
import typer

from deviate.core.herdr import report_state, with_herdr_status


def test_report_state_sends_wrapper_compatible_envelope(monkeypatch) -> None:
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setenv("HERDR_SOCKET_PATH", "/tmp/herdr.sock")
    monkeypatch.setenv("HERDR_PANE_ID", "pane-42")

    client = MagicMock()
    socket_context = MagicMock()
    socket_context.__enter__.return_value = client

    with (
        patch("deviate.core.herdr.socket.socket", return_value=socket_context),
        patch(
            "deviate.core.herdr.time.time_ns", return_value=1_750_000_000_123_456_789
        ),
        patch("deviate.core.herdr.secrets.token_hex", return_value="abcd1234"),
    ):
        report_state("working", "deviate micro run")

    payload = json.loads(client.sendall.call_args.args[0])
    assert payload == {
        "id": "herdr:deviate:1750000000123456789:abcd1234",
        "method": "pane.report_agent",
        "params": {
            "pane_id": "pane-42",
            "source": "herdr:deviate",
            "agent": "omp",
            "state": "working",
            "message": "deviate micro run",
            "seq": 1_750_000_000_123_456,
        },
    }
    client.settimeout.assert_called_once_with(1.0)
    client.connect.assert_called_once_with("/tmp/herdr.sock")
    client.shutdown.assert_called_once()
    client.recv.assert_called_once_with(1)


def test_report_state_is_disabled_without_complete_herdr_environment(
    monkeypatch,
) -> None:
    monkeypatch.delenv("HERDR_ENV", raising=False)
    monkeypatch.setenv("HERDR_SOCKET_PATH", "/tmp/herdr.sock")
    monkeypatch.setenv("HERDR_PANE_ID", "pane-42")

    with patch("deviate.core.herdr.socket.socket") as socket_factory:
        report_state("working", "deviate run")

    socket_factory.assert_not_called()


def test_report_state_swallows_socket_errors(monkeypatch) -> None:
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setenv("HERDR_SOCKET_PATH", "/tmp/missing-herdr.sock")
    monkeypatch.setenv("HERDR_PANE_ID", "pane-42")

    client = MagicMock()
    client.connect.side_effect = OSError("daemon unavailable")
    socket_context = MagicMock()
    socket_context.__enter__.return_value = client

    with patch("deviate.core.herdr.socket.socket", return_value=socket_context):
        report_state("working", "deviate run")


def test_report_state_swallows_base_exceptions(monkeypatch) -> None:
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setenv("HERDR_SOCKET_PATH", "/tmp/herdr.sock")
    monkeypatch.setenv("HERDR_PANE_ID", "pane-42")

    with patch("deviate.core.herdr.socket.socket", side_effect=KeyboardInterrupt):
        report_state("working", "deviate run")


def test_with_herdr_status_reports_working_then_idle_on_success() -> None:
    @with_herdr_status("micro run")
    def succeeds() -> int:
        return 42

    with patch("deviate.core.herdr.report_state") as report:
        assert succeeds() == 42

    assert report.call_args_list == [
        call("working", "deviate micro run"),
        call("idle", None),
    ]


def test_with_herdr_status_reports_blocked_for_nonzero_exit() -> None:
    @with_herdr_status("meso run")
    def fails() -> None:
        raise typer.Exit(code=7)

    with patch("deviate.core.herdr.report_state") as report:
        with pytest.raises(typer.Exit) as exc_info:
            fails()

    assert exc_info.value.exit_code == 7
    assert report.call_args_list == [
        call("working", "deviate meso run"),
        call("blocked", "deviate meso run: blocked (exit 7)"),
    ]


def test_with_herdr_status_reports_idle_for_explicit_zero_exit() -> None:
    @with_herdr_status("micro run")
    def exits_cleanly() -> None:
        raise typer.Exit(code=0)

    with patch("deviate.core.herdr.report_state") as report:
        with pytest.raises(typer.Exit):
            exits_cleanly()

    assert report.call_args_list == [
        call("working", "deviate micro run"),
        call("idle", None),
    ]


def test_with_herdr_status_reports_exception_type_without_error_details() -> None:
    @with_herdr_status("run")
    def crashes() -> None:
        raise ValueError("credential-like detail must not reach herdr")

    with patch("deviate.core.herdr.report_state") as report:
        with pytest.raises(ValueError):
            crashes()

    assert report.call_args_list == [
        call("working", "deviate run"),
        call("blocked", "deviate run: blocked (ValueError)"),
    ]
