#!/usr/bin/env bats
#
# Installed GREEN stall surfaces STALL_DETECTED on stderr-only noise
# (ISS-ADH-025 / GH-61). Constitution §3 E2E command: bats tests/e2e/.
#
# Happy path: installed constants stay 900s GREEN / 3600s EXECUTE, and
# `deviate micro --help` exits 0.
# Critical-failure path: mocked Popen pipes trip STALL_DETECTED at a
# sub-second budget when only stderr keeps arriving on a streaming
# backend (claude). Print-mode `pi -p` is excluded (GH-166). No live agent.
#
# Each test starts in a fresh tmpdir so `deviate` does not pick up the host
# repo's `.deviate/session.json` or `specs/` state.

setup() {
    BATS_TEST_TMPDIR="$(mktemp -d)"
    cd "$BATS_TEST_TMPDIR"
}

teardown() {
    if [[ -n "$BATS_TEST_TMPDIR" && "$BATS_TEST_TMPDIR" == /tmp/* ]]; then
        rm -rf "$BATS_TEST_TMPDIR"
    fi
}

# `uv tool install` and a local `.venv` put `deviate` on PATH, not always
# the matching `python`. Read the console-script shebang so `python -c`
# imports the installed package (AC-PLAN-004 / AC-PLAN-005).
_installed_python() {
    local script
    script="$(command -v deviate)"
    sed -n '1s/^#!//p' "$script"
}

@test "installed GREEN stall is 900s and EXECUTE stall is 3600s" {
    run "$(_installed_python)" -c '
from deviate.core.agent import STREAM_STALL_TIMEOUT_SECONDS
from deviate.cli.micro import EXECUTE_STALL_TIMEOUT_SECONDS
assert STREAM_STALL_TIMEOUT_SECONDS == 900, STREAM_STALL_TIMEOUT_SECONDS
assert EXECUTE_STALL_TIMEOUT_SECONDS == 3600, EXECUTE_STALL_TIMEOUT_SECONDS
print("STREAM_STALL_TIMEOUT_SECONDS", STREAM_STALL_TIMEOUT_SECONDS)
print("EXECUTE_STALL_TIMEOUT_SECONDS", EXECUTE_STALL_TIMEOUT_SECONDS)
'
    [ "$status" -eq 0 ]
    [[ "$output" == *"STREAM_STALL_TIMEOUT_SECONDS 900"* ]]
    [[ "$output" == *"EXECUTE_STALL_TIMEOUT_SECONDS 3600"* ]]
}

@test "deviate micro --help exits 0" {
    run deviate micro --help
    [ "$status" -eq 0 ]
}

@test "stderr-only noise raises STALL_DETECTED with diagnostic partial_stderr" {
    run "$(_installed_python)" -c '
import threading
from unittest.mock import MagicMock

from deviate.core.agent import AgentBackend, AgentTimeoutError

release = threading.Event()
diagnostic = "[zvec-grep] Background search failed"


class BlockingStdout:
    def __iter__(self):
        return self

    def __next__(self):
        release.wait()
        raise StopIteration


class PeriodicStderr:
    def __init__(self):
        self._emitted = False

    def __iter__(self):
        return self

    def __next__(self):
        if not self._emitted:
            self._emitted = True
            return f"{diagnostic}\n".encode()
        if release.wait(timeout=0.03):
            raise StopIteration
        return f"{diagnostic}\n".encode()


proc = MagicMock()
proc.stdin = MagicMock()
proc.stdout = BlockingStdout()
proc.stderr = PeriodicStderr()
proc.kill.side_effect = release.set

stall_budget = 0.15
raised = []


def run_stream():
    try:
        AgentBackend()._invoke_streaming(
            proc,
            ["claude", "-p", "--permission-mode", "auto"],
            "prompt",
            timeout_secs=10,
            backend_name="claude",
            output_callback=lambda _line: None,
            stall_timeout=stall_budget,
        )
    except BaseException as exc:
        raised.append(exc)


worker = threading.Thread(target=run_stream)
worker.start()
worker.join(timeout=1.0)
if worker.is_alive():
    release.set()
    worker.join(timeout=1.0)
    raise SystemExit("stderr-only noise kept the stall clock alive")

if not raised:
    raise SystemExit("streaming invoke returned without STALL_DETECTED")
exc = raised[0]
if not isinstance(exc, AgentTimeoutError):
    raise SystemExit(f"expected AgentTimeoutError, got {type(exc)}: {exc}")
if "STALL_DETECTED" not in str(exc):
    raise SystemExit(f"missing STALL_DETECTED: {exc}")
if diagnostic not in exc.partial_stderr:
    raise SystemExit(f"missing diagnostic on partial_stderr: {exc.partial_stderr!r}")
print("STALL_DETECTED")
print(exc.partial_stderr)
'
    [ "$status" -eq 0 ]
    [[ "$output" == *"STALL_DETECTED"* ]]
    [[ "$output" == *"[zvec-grep] Background search failed"* ]]
}
