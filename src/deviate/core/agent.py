from __future__ import annotations

import subprocess
import time
from typing import Any

import yaml
from pydantic import BaseModel

from deviate.state.config import AgentConfig


class HandoverManifest(BaseModel):
    phase: str
    status: str
    test_file: str | None = None
    verification_command: str | None = None
    yellow_trigger: bool | None = None
    test_changes: dict[str, Any] | None = None
    rationale: str | None = None

    model_config = {"extra": "forbid"}


class AgentTimeoutError(Exception):
    pass


class AgentSubprocessError(Exception):
    def __init__(self, message: str, exit_code: int = 1) -> None:
        self.exit_code = exit_code
        super().__init__(message)


class MalformedHandoverManifestError(Exception):
    pass


class AgentBinaryNotFoundError(Exception):
    pass


class EmptyOutputError(Exception):
    pass


BACKEND_COMMANDS: dict[str, str] = {
    "opencode": "opencode run",
    "claude": "claude -p",
    "droid": "droid exec",
}


class AgentBackend:
    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or AgentConfig()

    def invoke(
        self,
        prompt: str,
        backend: str | None = None,
        timeout: int | None = None,
    ) -> HandoverManifest:
        backend_name = backend or self.config.backend
        backend_cmd = BACKEND_COMMANDS.get(backend_name)
        if backend_cmd is None:
            raise AgentBinaryNotFoundError(f"Unknown backend: {backend_name}")

        cmd = backend_cmd.split()
        effective_timeout = timeout or self.config.timeout

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            raise AgentBinaryNotFoundError(
                f"Agent binary not found on PATH for backend: {backend_name}"
            )

        def _try_communicate() -> tuple[bytes, bytes]:
            try:
                stdout_bytes, stderr_bytes = proc.communicate(
                    input=prompt.encode("utf-8"),
                    timeout=effective_timeout,
                )
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                raise
            return stdout_bytes, stderr_bytes

        try:
            stdout_bytes, stderr_bytes = _try_communicate()
        except subprocess.TimeoutExpired:
            time.sleep(30)
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                stdout_bytes, stderr_bytes = _try_communicate()
            except subprocess.TimeoutExpired:
                raise AgentTimeoutError(
                    f"Agent backend '{backend_name}' timed out "
                    f"after {effective_timeout}s "
                    "(retried once with 30s backoff)"
                )

        stdout = stdout_bytes.decode("utf-8") if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8") if stderr_bytes else ""

        if proc.returncode != 0:
            raise AgentSubprocessError(
                message=stderr or f"Agent exited with code {proc.returncode}",
                exit_code=proc.returncode,
            )

        if not stdout.strip():
            raise EmptyOutputError(
                f"Agent backend '{backend_name}' returned empty output"
            )

        try:
            data = yaml.safe_load(stdout)
        except yaml.YAMLError as e:
            raise MalformedHandoverManifestError(
                f"Failed to parse YAML handover manifest: {e}"
            )

        if not isinstance(data, dict):
            raise MalformedHandoverManifestError(
                "YAML handover manifest is not a mapping"
            )

        return HandoverManifest(**data)
