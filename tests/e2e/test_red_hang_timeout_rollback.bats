#!/usr/bin/env bats
#
# Installed RED hang surfaces AGENT_TIMEOUT before an outer bash kill
# (ISS-ADH-027). Constitution §3 E2E command: bats tests/e2e/.
#
# Happy path: installed AgentConfig.timeout stays 600s, GREEN/RED stall
# stays 900s, EXECUTE stall stays 3600s, and `deviate micro --help`
# exits 0 (AC-PLAN-005, AC-PLAN-006).
# Critical-failure path: mocked Popen pipes emit an early stdout chunk
# then trickle more chunks with no handover manifest. invoke raises
# AgentTimeoutError at a sub-second AgentConfig.timeout and does not
# sleep 30s (AC-PLAN-001, AC-PLAN-002). No live `pi -p`.
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
# imports the installed package (AC-PLAN-005 / AC-PLAN-006).
_installed_python() {
    local script
    script="$(command -v deviate)"
    sed -n '1s/^#!//p' "$script"
}

@test "installed RED hang budget is 600s wall-clock, 900s stall, 3600s EXECUTE" {
    run "$(_installed_python)" -c '
from deviate.core.agent import STREAM_STALL_TIMEOUT_SECONDS
from deviate.cli.micro import EXECUTE_STALL_TIMEOUT_SECONDS
from deviate.state.config import AgentConfig
assert AgentConfig().timeout == 600, AgentConfig().timeout
assert STREAM_STALL_TIMEOUT_SECONDS == 900, STREAM_STALL_TIMEOUT_SECONDS
assert EXECUTE_STALL_TIMEOUT_SECONDS == 3600, EXECUTE_STALL_TIMEOUT_SECONDS
print("AgentConfig.timeout", AgentConfig().timeout)
print("STREAM_STALL_TIMEOUT_SECONDS", STREAM_STALL_TIMEOUT_SECONDS)
print("EXECUTE_STALL_TIMEOUT_SECONDS", EXECUTE_STALL_TIMEOUT_SECONDS)
'
    [ "$status" -eq 0 ]
    [[ "$output" == *"AgentConfig.timeout 600"* ]]
    [[ "$output" == *"STREAM_STALL_TIMEOUT_SECONDS 900"* ]]
    [[ "$output" == *"EXECUTE_STALL_TIMEOUT_SECONDS 3600"* ]]
}

@test "deviate micro --help exits 0" {
    run deviate micro --help
    [ "$status" -eq 0 ]
}

@test "stdout trickle raises AgentTimeoutError before bash and skips the 30s retry" {
    run "$(_installed_python)" -c '
import threading
import time as time_mod
from unittest.mock import MagicMock, patch

from deviate.core.agent import AgentBackend, AgentTimeoutError

release = threading.Event()
early_chunk = "wrote tests/test_foo.py"
trickle_chunk = "still writing"


class TrickleStdout:
    def __init__(self):
        self._emitted = 0

    def __iter__(self):
        return self

    def __next__(self):
        self._emitted += 1
        if self._emitted == 1:
            return f"{early_chunk}\n".encode()
        if release.wait(timeout=0.03):
            raise StopIteration
        return f"{trickle_chunk}\n".encode()


proc = MagicMock()
proc.stdin = MagicMock()
proc.stdout = TrickleStdout()
proc.stderr = iter(())
proc.returncode = None
proc.kill.side_effect = release.set

wall_clock = 0.2
raised = []
sleep_30 = []
real_sleep = time_mod.sleep


def _sleep(seconds):
    if seconds == 30:
        sleep_30.append(seconds)
        return
    real_sleep(seconds)


def run_invoke():
    try:
        AgentBackend().invoke(
            "test prompt",
            backend="pi",
            timeout=wall_clock,
            output_callback=lambda _line: None,
        )
    except BaseException as exc:
        raised.append(exc)


started = time_mod.monotonic()
with (
    patch("subprocess.Popen", return_value=proc) as mock_popen,
    patch("time.sleep", side_effect=_sleep),
):
    worker = threading.Thread(target=run_invoke)
    worker.start()
    worker.join(timeout=1.5)
    elapsed = time_mod.monotonic() - started
    if worker.is_alive():
        release.set()
        worker.join(timeout=1.0)
        raise SystemExit(
            "stdout trickle kept the poll loop alive past AgentConfig.timeout"
        )

if not raised:
    raise SystemExit("streaming invoke returned without AgentTimeoutError")
exc = raised[0]
if not isinstance(exc, AgentTimeoutError):
    raise SystemExit(f"expected AgentTimeoutError, got {type(exc)}: {exc}")
if "STALL_DETECTED" in str(exc):
    raise SystemExit(f"stall token leaked onto wall-clock timeout: {exc}")
if "timeout" not in str(exc).lower() and "timed out" not in str(exc).lower():
    raise SystemExit(f"missing timeout wording: {exc}")
if early_chunk not in exc.partial_stdout:
    raise SystemExit(f"missing early stdout on partial_stdout: {exc.partial_stdout!r}")
if elapsed >= wall_clock + 1.0:
    raise SystemExit(f"elapsed {elapsed} reached an outer bash-scale wait")
if sleep_30:
    raise SystemExit("invoke slept 30s for a streaming wall-clock timeout")
if mock_popen.call_count != 1:
    raise SystemExit(f"expected one Popen, got {mock_popen.call_count}")
print("AGENT_TIMEOUT")
print(exc)
print(exc.partial_stdout)
'
    [ "$status" -eq 0 ]
    [[ "$output" == *"AGENT_TIMEOUT"* ]]
    [[ "$output" == *"timed out"* ]]
    [[ "$output" == *"wrote tests/test_foo.py"* ]]
}
