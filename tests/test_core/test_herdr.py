from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import pytest
import typer

from deviate.core.herdr import (
    pause_for_close,
    report_state,
    with_herdr_status,
)


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
        with patch("deviate.core.herdr.pause_for_close") as pause:
            assert succeeds() == 42

    assert report.call_args_list == [
        call("working", "deviate micro run"),
        call("idle", None),
    ]
    assert pause.call_count == 1


def test_with_herdr_status_reports_blocked_for_nonzero_exit() -> None:
    @with_herdr_status("meso run")
    def fails() -> None:
        raise typer.Exit(code=7)

    with patch("deviate.core.herdr.report_state") as report:
        with patch("deviate.core.herdr.pause_for_close") as pause:
            with pytest.raises(typer.Exit) as exc_info:
                fails()

    assert exc_info.value.exit_code == 7
    assert report.call_args_list == [
        call("working", "deviate meso run"),
        call("blocked", "deviate meso run: blocked (exit 7)"),
        call("idle", None),
    ]
    assert pause.call_count == 1


def test_with_herdr_status_reports_idle_for_explicit_zero_exit() -> None:
    @with_herdr_status("micro run")
    def exits_cleanly() -> None:
        raise typer.Exit(code=0)

    with patch("deviate.core.herdr.report_state") as report:
        with patch("deviate.core.herdr.pause_for_close") as pause:
            with pytest.raises(typer.Exit):
                exits_cleanly()
    assert report.call_args_list == [
        call("working", "deviate micro run"),
        call("idle", None),
    ]
    assert pause.call_count == 1


def test_with_herdr_status_reports_exception_type_without_error_details() -> None:
    @with_herdr_status("run")
    def crashes() -> None:
        raise ValueError("credential-like detail must not reach herdr")

    with patch("deviate.core.herdr.report_state") as report:
        with patch("deviate.core.herdr.pause_for_close") as pause:
            with pytest.raises(ValueError):
                crashes()

    assert report.call_args_list == [
        call("working", "deviate run"),
        call("blocked", "deviate run: blocked (ValueError)"),
        call("idle", None),
    ]
    assert pause.call_count == 1


def test_with_herdr_status_emits_terminal_state_immediately_before_pause() -> None:
    """The only terminal report must be the event immediately before closing."""

    @with_herdr_status("micro run")
    def succeeds() -> int:
        return 42

    events: list[str] = []

    def record_state(state: str, message: str | None) -> None:
        events.append(f"report:{state}")

    def record_pause() -> None:
        events.append("pause")

    with (
        patch("deviate.core.herdr.report_state", side_effect=record_state),
        patch("deviate.core.herdr.pause_for_close", side_effect=record_pause),
    ):
        assert succeeds() == 42

    assert events == ["report:working", "report:idle", "pause"]


def test_with_herdr_status_blocked_emits_terminal_then_clears() -> None:
    """Blocked is sent before close, then idle clears it after acknowledgement."""

    @with_herdr_status("meso run")
    def fails() -> None:
        raise typer.Exit(code=3)

    events: list[str] = []

    def record_state(state: str, message: str | None) -> None:
        events.append(f"report:{state}")

    def record_pause() -> None:
        events.append("pause")

    with (
        patch("deviate.core.herdr.report_state", side_effect=record_state),
        patch("deviate.core.herdr.pause_for_close", side_effect=record_pause),
    ):
        with pytest.raises(typer.Exit):
            fails()

    assert events == ["report:working", "report:blocked", "pause", "report:idle"]


def test_pause_for_close_is_skipped_without_herdr_env(monkeypatch) -> None:
    monkeypatch.delenv("HERDR_ENV", raising=False)
    stdin = MagicMock()
    stdin.isatty.return_value = True

    with patch("deviate.core.herdr.sys.stdin", stdin):
        pause_for_close()

    stdin.readline.assert_not_called()


def test_pause_for_close_is_skipped_when_not_a_tty(monkeypatch) -> None:
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.delenv("HERDR_DEVIATE_NO_PAUSE", raising=False)
    monkeypatch.delenv("TERM", raising=False)
    stdin = MagicMock()
    stdin.isatty.return_value = False

    with patch("deviate.core.herdr.sys.stdin", stdin):
        pause_for_close()

    stdin.readline.assert_not_called()


def test_pause_for_close_is_skipped_when_term_is_dumb(monkeypatch) -> None:
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.delenv("HERDR_DEVIATE_NO_PAUSE", raising=False)
    monkeypatch.setenv("TERM", "dumb")
    stdin = MagicMock()
    stdin.isatty.return_value = True

    with patch("deviate.core.herdr.sys.stdin", stdin):
        pause_for_close()

    stdin.readline.assert_not_called()


def test_pause_for_close_is_skipped_when_explicit_opt_out(monkeypatch) -> None:
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setenv("HERDR_DEVIATE_NO_PAUSE", "1")
    monkeypatch.delenv("TERM", raising=False)
    stdin = MagicMock()
    stdin.isatty.return_value = True

    with patch("deviate.core.herdr.sys.stdin", stdin):
        pause_for_close()

    stdin.readline.assert_not_called()


def test_pause_for_close_writes_prompt_to_stderr_then_blocks(monkeypatch) -> None:
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.delenv("HERDR_DEVIATE_NO_PAUSE", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    stdin = MagicMock()
    stdin.isatty.return_value = True
    stdin.readline.return_value = "\n"
    stderr = MagicMock()

    with (
        patch("deviate.core.herdr.sys.stdin", stdin),
        patch("deviate.core.herdr.sys.stderr", stderr),
    ):
        pause_for_close()

    stderr.write.assert_called_once()
    prompt = stderr.write.call_args.args[0]
    assert prompt.startswith("\n")
    assert "Enter" in prompt
    stderr.flush.assert_called_once()
    stdin.readline.assert_called_once_with()


def test_pause_for_close_returns_silently_on_eof(monkeypatch) -> None:
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.delenv("HERDR_DEVIATE_NO_PAUSE", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    stdin = MagicMock()
    stdin.isatty.return_value = True
    stdin.readline.side_effect = EOFError
    stderr = MagicMock()

    with (
        patch("deviate.core.herdr.sys.stdin", stdin),
        patch("deviate.core.herdr.sys.stderr", stderr),
    ):
        pause_for_close()  # must not raise

    stderr.write.assert_called_once()


def test_pause_for_close_returns_silently_on_keyboard_interrupt(
    monkeypatch,
) -> None:
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.delenv("HERDR_DEVIATE_NO_PAUSE", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    stdin = MagicMock()
    stdin.isatty.return_value = True
    stdin.readline.side_effect = KeyboardInterrupt
    stderr = MagicMock()

    with (
        patch("deviate.core.herdr.sys.stdin", stdin),
        patch("deviate.core.herdr.sys.stderr", stderr),
    ):
        pause_for_close()  # must not raise


def test_pause_for_close_swallows_unexpected_exceptions(monkeypatch) -> None:
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.delenv("HERDR_DEVIATE_NO_PAUSE", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    stdin = MagicMock()
    stdin.isatty.return_value = True
    stdin.readline.side_effect = RuntimeError("unexpected")
    stderr = MagicMock()

    with (
        patch("deviate.core.herdr.sys.stdin", stdin),
        patch("deviate.core.herdr.sys.stderr", stderr),
    ):
        pause_for_close()  # must not raise
