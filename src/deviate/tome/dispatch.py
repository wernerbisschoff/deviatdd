"""Dispatch a single writer prompt to the configured agent backend.

Unlike ``deviate.core.agent.AgentBackend.invoke`` — which expects the
agent to emit a ``<handover_manifest>`` YAML block describing TDD-cycle
work — the Tome writers produce a markdown file on disk. This module
runs the backend subprocess, waits for it to exit, and reports success
by checking whether the declared target file was created.

The backend prompt is fed via stdin. Per the existing
``AgentBackend`` contract, ``opencode`` / ``droid`` / ``claude`` /
``pi`` all accept stdin prompts in their headless ``-p`` / ``run`` /
``exec`` modes. See ``src/deviate/core/agent.py::BACKEND_COMMANDS``.
"""

from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


# Track every running subprocess.Popen so a SIGINT handler in batch.py can
# kill them all on Ctrl+C without waiting for the per-row 600s timeout.
# The set is guarded by a lock because dispatch_writer may be called from
# multiple worker threads concurrently (ThreadPoolExecutor fan-out).
_RUNNING_PROCS: set[subprocess.Popen[str]] = set()
_RUNNING_PROCS_LOCK = threading.Lock()

BackendName = Literal["opencode", "claude", "droid", "pi", "stub"]


# Per-backend command tokens. The prompt is fed via stdin (matches the
# existing AgentBackend._invoke_blocking pattern in core/agent.py).
BACKEND_COMMANDS: dict[str, list[str]] = {
    "opencode": ["opencode", "run"],
    "claude": ["claude", "-p", "--permission-mode", "auto"],
    "droid": ["droid", "exec"],
    "pi": ["pi", "-p"],
    "stub": ["echo"],  # Test fallback — emits the prompt to stdout, writes nothing.
}


# Tail sizes captured in DispatchResult (kept small to bound memory at scale).
_STDOUT_TAIL_CHARS = 1000
_STDERR_TAIL_CHARS = 1000


@dataclass
class DispatchResult:
    """Outcome of a single writer dispatch attempt.

    ``status`` is the coarse label used for logging and exit-code
    computation; the raw fields are preserved for debugging.
    """

    returncode: int
    file_exists: bool
    target_file: str
    stdout_tail: str
    stderr_tail: str
    duration_seconds: float
    timed_out: bool = False

    @property
    def status(self) -> str:
        """Coarse status: ``DONE`` / ``FAIL`` / ``TIMEOUT`` / ``MISSING``."""
        if self.timed_out:
            return "TIMEOUT"
        if self.returncode != 0:
            return "FAIL"
        if not self.file_exists:
            return "MISSING"  # Returned 0 but never wrote the file.
        return "DONE"


def dispatch_writer(
    backend: str,
    prompt: str,
    target_file: str,
    cwd: Path,
    timeout: int = 600,
) -> DispatchResult:
    """Dispatch one writer invocation; report whether ``target_file`` exists after.

    Raises ``ValueError`` for an unknown backend (caller's bug, not a
    runtime condition). On timeout, the subprocess is killed and the
    result is marked ``timed_out=True`` with whatever partial output
    was captured.
    """
    cmd = BACKEND_COMMANDS.get(backend)
    if cmd is None:
        raise ValueError(
            f"Unknown backend: {backend!r}; expected one of {sorted(BACKEND_COMMANDS)}"
        )

    start = time.monotonic()
    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
        )
        with _RUNNING_PROCS_LOCK:
            _RUNNING_PROCS.add(proc)
        try:
            stdout, stderr = proc.communicate(input=prompt, timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            duration = time.monotonic() - start
            return DispatchResult(
                returncode=-1,
                file_exists=(cwd / target_file).exists() if target_file else False,
                target_file=target_file,
                stdout_tail=_tail(stdout, _STDOUT_TAIL_CHARS),
                stderr_tail=_tail(stderr, _STDERR_TAIL_CHARS),
                duration_seconds=duration,
                timed_out=True,
            )
        duration = time.monotonic() - start
        file_exists = (cwd / target_file).exists() if target_file else False
        return DispatchResult(
            returncode=proc.returncode if proc.returncode is not None else -1,
            file_exists=file_exists,
            target_file=target_file,
            stdout_tail=_tail(stdout, _STDOUT_TAIL_CHARS),
            stderr_tail=_tail(stderr, _STDERR_TAIL_CHARS),
            duration_seconds=duration,
        )
    except FileNotFoundError as e:
        # The backend binary isn't on PATH — surface as a FAIL with a
        # readable error rather than letting the exception bubble.
        duration = time.monotonic() - start
        return DispatchResult(
            returncode=-1,
            file_exists=False,
            target_file=target_file,
            stdout_tail="",
            stderr_tail=f"BINARY_NOT_FOUND: {e}",
            duration_seconds=duration,
        )
    finally:
        if proc is not None:
            with _RUNNING_PROCS_LOCK:
                _RUNNING_PROCS.discard(proc)


def kill_all_running_procs() -> int:
    """SIGINT helper: kill every tracked subprocess and return how many were killed.

    Idempotent — safe to call multiple times. Called from the SIGINT handler
    installed by ``run_batch`` so Ctrl+C aborts the fan-out immediately
    instead of waiting for the per-row timeout to elapse.
    """
    with _RUNNING_PROCS_LOCK:
        procs = list(_RUNNING_PROCS)
    for p in procs:
        try:
            p.kill()
        except ProcessLookupError:
            pass
    return len(procs)


def _tail(text: str | None, n: int) -> str:
    """Return the last ``n`` characters of ``text`` (or empty string)."""
    if not text:
        return ""
    return text[-n:]
