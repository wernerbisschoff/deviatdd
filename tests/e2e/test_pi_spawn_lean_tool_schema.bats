#!/usr/bin/env bats
#
# Installed Pi spawn is lean and schema tokens abort
# (ISS-ADH-026). Constitution §3 E2E command: bats tests/e2e/.
#
# Happy path: installed `AgentBackend.invoke` print-mode argv keeps
# `pi -p` plus `--no-skills` and `--tools` listing `read`, `bash`, `edit`,
# and `write`, with no `--no-extensions` (extension-registered providers
# must load so a saved default model from them resolves). `deviate micro --help` exits 0.
# Critical-failure path: mocked Popen pipes raise a token-bearing
# `AgentSubprocessError` on the first `tool_count_limit` /
# `unsupported_tool_schema` line. No live `pi --mode rpc`.
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
# imports the installed package (AC-PLAN-001 / AC-PLAN-003).
_installed_python() {
    local script
    script="$(command -v deviate)"
    sed -n '1s/^#!//p' "$script"
}

@test "installed print-mode Pi spawn is lean with four coding tools" {
    run "$(_installed_python)" -c '
from unittest.mock import MagicMock, patch

from deviate.core.agent import AgentBackend
from deviate.state.config import AgentConfig

yaml_output = "phase: RED\nstatus: TEST_WRITTEN_FAILING\n"
mock_proc = MagicMock()
mock_proc.communicate.return_value = (yaml_output.encode("utf-8"), b"")
mock_proc.returncode = 0

with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
    AgentBackend(config=AgentConfig(backend="pi")).invoke("test prompt")

cmd = mock_popen.call_args[0][0]
joined = " ".join(cmd)
assert cmd[0] == "pi", cmd
assert cmd[1] == "-p", cmd
assert "--no-extensions" not in cmd and "-ne" not in cmd, cmd
assert "--no-skills" in cmd or "-ns" in cmd, cmd
assert "--no-tools" not in cmd, cmd
assert "--no-builtin-tools" not in cmd, cmd
tools = ""
if "--tools" in cmd:
    tools = cmd[cmd.index("--tools") + 1]
elif "-t" in cmd:
    tools = cmd[cmd.index("-t") + 1]
for name in ("read", "bash", "edit", "write"):
    assert name in tools, (name, cmd)
print("LEAN_ARGV", joined)
'
    [ "$status" -eq 0 ]
    [[ "$output" == *"LEAN_ARGV"* ]]
    [[ "$output" == *"pi -p"* ]]
    [[ "$output" != *"--no-extensions"* && "$output" != *"-ne"* ]]
    [[ "$output" == *"--tools"* || "$output" == *"-t"* ]]
    [[ "$output" == *"read"* ]]
    [[ "$output" == *"bash"* ]]
    [[ "$output" == *"edit"* ]]
    [[ "$output" == *"write"* ]]
}

@test "deviate micro --help exits 0" {
    run deviate micro --help
    [ "$status" -eq 0 ]
}

@test "schema-rejection tokens abort invoke and call kill" {
    run "$(_installed_python)" -c '
import threading
from unittest.mock import MagicMock, patch

from deviate.core.agent import AgentBackend, AgentSubprocessError

release = threading.Event()
schema_line = "400 tool_count_limit unsupported_tool_schema"


class BlockingStdout:
    def __iter__(self):
        return self

    def __next__(self):
        release.wait()
        raise StopIteration


class SchemaStderr:
    def __iter__(self):
        return self

    def __next__(self):
        if not getattr(self, "_emitted", False):
            self._emitted = True
            return f"{schema_line}\n".encode()
        if release.wait(timeout=0.05):
            raise StopIteration
        return b""


proc = MagicMock()
proc.stdin = MagicMock()
proc.stdout = BlockingStdout()
proc.stderr = SchemaStderr()
proc.returncode = None
proc.kill.side_effect = release.set

raised = []


def run_invoke():
    try:
        with patch("subprocess.Popen", return_value=proc):
            AgentBackend().invoke(
                "test prompt",
                backend="pi",
                output_callback=lambda _line: None,
                stall_timeout=0.2,
            )
    except BaseException as exc:
        raised.append(exc)


worker = threading.Thread(target=run_invoke)
worker.start()
worker.join(timeout=2.0)
if worker.is_alive():
    release.set()
    worker.join(timeout=1.0)
    raise SystemExit("schema rejection waited instead of aborting")

if not raised:
    raise SystemExit("invoke returned without AgentSubprocessError")
exc = raised[0]
if not isinstance(exc, AgentSubprocessError):
    raise SystemExit(f"expected AgentSubprocessError, got {type(exc)}: {exc}")
text = str(exc)
if "tool_count_limit" not in text and "unsupported_tool_schema" not in text:
    raise SystemExit(f"missing schema tokens: {exc}")
if not proc.kill.called:
    raise SystemExit("kill was not called")
print("SCHEMA_ABORT")
print(text)
'
    [ "$status" -eq 0 ]
    [[ "$output" == *"SCHEMA_ABORT"* ]]
    [[ "$output" == *"tool_count_limit"* || "$output" == *"unsupported_tool_schema"* ]]
}
