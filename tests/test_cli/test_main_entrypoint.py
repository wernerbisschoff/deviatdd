"""Regression coverage for ``deviate.main.app``.

The console-script entry point must dispatch the Typer ``cli()``
callback directly. When the entry point is reached from an agent or
nested pane that has inherited the legacy pane-tracker environment
keys, the entry point must NOT prompt the operator to press Enter or
block on stdin.
"""

from __future__ import annotations

import io
import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _inherited_pane_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deterministic inherited-env setup so a re-introduced branch fails this test."""
    monkeypatch.delenv("HERDR_DEVIATE_NO_PAUSE", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setenv("HERDR_SOCKET_PATH", "/tmp/legacy-pane.sock")
    monkeypatch.setenv("HERDR_PANE_ID", "pane-42")


@pytest.fixture
def stdin_mock() -> MagicMock:
    stdin = MagicMock()
    stdin.isatty.return_value = True
    return stdin


@pytest.mark.parametrize(
    "argv",
    [
        ["micro", "run", "--all"],
        ["meso", "run"],
        ["run"],
    ],
)
def test_app_dispatches_cli_without_blocking_on_stdin(
    argv: list[str], stdin_mock: MagicMock
) -> None:
    stderr_capture = io.StringIO()
    with (
        patch("deviate.main.cli") as mock_cli,
        patch.object(sys, "stdin", stdin_mock),
        patch.object(sys, "stderr", stderr_capture),
        patch.object(sys, "argv", ["deviate", *argv]),
    ):
        from deviate.main import app

        app()

    mock_cli.assert_called_once()
    stdin_mock.readline.assert_not_called()
    assert "Press Enter to close this pane" not in stderr_capture.getvalue(), (
        f"app() must not emit the 'Press Enter to close this pane' prompt "
        f"under inherited pane env; got stderr={stderr_capture.getvalue()!r}"
    )
