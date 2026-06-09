from __future__ import annotations

from typing import Any

from pydantic import BaseModel


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
    def __init__(self, config: Any = None) -> None:
        raise NotImplementedError

    def invoke(
        self,
        prompt: str,
        backend: str | None = None,
        timeout: int | None = None,
    ) -> HandoverManifest:
        raise NotImplementedError
