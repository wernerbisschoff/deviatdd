from __future__ import annotations

import functools
import json
import os
import secrets
import socket
import time
from collections.abc import Callable
from typing import Literal, ParamSpec, TypeVar

AgentState = Literal["working", "blocked", "idle"]

_SOURCE = "herdr:deviate"
_AGENT = "omp"
_SOCKET_TIMEOUT_SECONDS = 1.0

P = ParamSpec("P")
R = TypeVar("R")


def report_state(state: AgentState, message: str | None = None) -> None:
    """Best-effort delivery of one herdr ``pane.report_agent`` envelope."""
    try:
        if os.environ.get("HERDR_ENV") != "1":
            return
        socket_path = os.environ.get("HERDR_SOCKET_PATH")
        pane_id = os.environ.get("HERDR_PANE_ID")
        if not socket_path or not pane_id:
            return

        timestamp_ns = time.time_ns()
        params: dict[str, str | int | None] = {
            "pane_id": pane_id,
            "source": _SOURCE,
            "agent": _AGENT,
            "state": state,
            "message": message,
            "seq": timestamp_ns // 1_000,
        }
        request = {
            "id": f"{_SOURCE}:{timestamp_ns}:{secrets.token_hex(4)}",
            "method": "pane.report_agent",
            "params": params,
        }
        payload = (json.dumps(request, separators=(",", ":")) + "\n").encode("utf-8")

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(_SOCKET_TIMEOUT_SECONDS)
            client.connect(socket_path)
            client.sendall(payload)
            client.shutdown(socket.SHUT_WR)
            client.recv(1)
    except BaseException:
        # Status reporting is observational and must never alter command behavior.
        return


def with_herdr_status(command: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Report a run callback as working, then idle or blocked on termination."""

    def decorate(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            label = f"deviate {command}"
            report_state("working", label)
            try:
                result = func(*args, **kwargs)
            except BaseException as exc:
                exit_code = _exit_code(exc)
                if exit_code == 0:
                    report_state("idle", None)
                else:
                    reason = (
                        f"exit {exit_code}"
                        if exit_code is not None
                        else type(exc).__name__
                    )
                    report_state("blocked", f"{label}: blocked ({reason})")
                raise
            report_state("idle", None)
            return result

        return wrapped

    return decorate


def _exit_code(exc: BaseException) -> int | None:
    value = getattr(exc, "exit_code", getattr(exc, "code", None))
    if value is None and isinstance(exc, SystemExit):
        return 0
    return value if isinstance(value, int) else None
