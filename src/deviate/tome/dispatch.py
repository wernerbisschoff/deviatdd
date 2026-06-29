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
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


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
    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        duration = time.monotonic() - start
        file_exists = (cwd / target_file).exists() if target_file else False
        return DispatchResult(
            returncode=proc.returncode,
            file_exists=file_exists,
            target_file=target_file,
            stdout_tail=_tail(proc.stdout, _STDOUT_TAIL_CHARS),
            stderr_tail=_tail(proc.stderr, _STDERR_TAIL_CHARS),
            duration_seconds=duration,
        )
    except subprocess.TimeoutExpired as e:
        duration = time.monotonic() - start
        return DispatchResult(
            returncode=-1,
            file_exists=(cwd / target_file).exists() if target_file else False,
            target_file=target_file,
            stdout_tail=_tail(_decode(e.output), _STDOUT_TAIL_CHARS),
            stderr_tail=_tail(_decode(e.stderr), _STDERR_TAIL_CHARS),
            duration_seconds=duration,
            timed_out=True,
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


def _tail(text: str | None, n: int) -> str:
    """Return the last ``n`` characters of ``text`` (or empty string)."""
    if not text:
        return ""
    return text[-n:]


def _decode(value: bytes | None) -> str:
    """Decode ``bytes | None`` from subprocess exception fields."""
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace")
