from __future__ import annotations

import functools
import json
import os
import secrets
import socket
import sys
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
    """Report a run callback as working, then idle or blocked on termination.

    Herdr's daemon stores one lifecycle authority per ``(source, agent)``
    pair per terminal and clears that authority on child process-exit
    detection (see Herdr's ``process_exit_clears_matching_full_lifecycle_hook_authority``
    test). After clearing, repeated ``pane.report_agent`` envelopes from
    the same pair are suppressed until a fresh session identity
    (``agent_session_id``) is supplied. Practical consequence: if a child
    OMP process exits while DeviaTDD is still busy retrying, Herdr clears
    DeviaTDD's ``working`` state and DeviaTDD cannot re-assert it without
    starting a new ``agent_session_id`` (not yet implemented natively;
    ``pane.release_agent`` before each retry is the documented mitigation).

    Native lifecycle reporting therefore emits exactly one initial
    ``working`` and one terminal ``idle``/``blocked`` per DeviaTDD
    invocation. The terminal ``report_state`` call fires BEFORE
    ``pause_for_close`` so the socket send happens while Herdr's
    authority for ``(source, agent)`` is still live — emitting after
    the pause risks the operator pressing Enter / Ctrl-C / EOF at the
    moment Herdr is processing the exit, which would leave the pane
    stuck in ``working`` until the next session identity lands. The
    pause itself keeps the pane alive in Herdr's UI while the operator
    reads the final output and any failure detail before the process
    actually exits.
    """

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
                pause_for_close()
                raise
            report_state("idle", None)
            pause_for_close()
            return result

        return wrapped

    return decorate


def pause_for_close() -> None:
    """Block on stdin until the operator presses Enter.

    Skipped unless ``HERDR_ENV == "1"``, ``HERDR_DEVIATE_NO_PAUSE != "1"``,
    ``sys.stdin.isatty()``, and ``TERM != "dumb"``. EOF and Ctrl-D/Ctrl-C
    return silently without hanging. Writes the prompt to ``sys.stderr``
    (Herdr reads pane state, not stdout) and uses ``stdin.readline()``
    directly so it does not interact with zsh's ``zle`` line editor.

    The intent is to keep the Herdr-tracked pane alive while the final
    report (``idle`` or ``blocked``) and any failure output remain
    visible. Without this pause, the pane collapses to the shell prompt
    the instant the process exits, and any errors scroll off before the
    operator can react. ``wrapped`` calls this *after* the terminal
    emit so Herdr observes the ``idle``/``blocked`` transition on the
    wire while its authority is still valid; the prompt then gives the
    operator time to read whatever the terminal state points at.
    If the socket send during ``report_state`` failed silently
    (see :func:`report_state`'s bare ``except BaseException``), the
    pane may stay in ``working`` after the pause exits — that is the
    correct degraded behavior, not a bug to suppress.
    """
    try:
        if os.environ.get("HERDR_ENV") != "1":
            return
        if os.environ.get("HERDR_DEVIATE_NO_PAUSE") == "1":
            return
        if os.environ.get("TERM") == "dumb":
            return
        stdin = sys.stdin
        if stdin is None or not stdin.isatty():
            return
        sys.stderr.write("\nPress Enter to close this pane (Ctrl-D / EOF to skip)... ")
        sys.stderr.flush()
        try:
            stdin.readline()
        except (EOFError, KeyboardInterrupt):
            return
    except BaseException:
        # Pause is observational and must never alter command behavior.
        return


def _exit_code(exc: BaseException) -> int | None:
    value = getattr(exc, "exit_code", getattr(exc, "code", None))
    if value is None and isinstance(exc, SystemExit):
        return 0
    return value if isinstance(value, int) else None
