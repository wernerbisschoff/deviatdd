from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from collections.abc import Callable
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ValidationError

from deviate.state.config import AgentConfig

OutputCallback = Callable[[str], None]

BackendName = Literal["opencode", "claude", "droid", "pi", "omp", "stub"]


class HandoverManifest(BaseModel):
    phase: str
    status: str
    task_id: str | None = None
    test_file: str | None = None
    verification_command: str | None = None
    expected_failure_node: str | None = None
    rationale: str | None = None
    next_phase: str | None = None

    model_config = {"extra": "allow"}


class AgentTimeoutError(Exception):
    def __init__(
        self, message: str, partial_stdout: str = "", partial_stderr: str = ""
    ):
        self.partial_stdout = partial_stdout
        self.partial_stderr = partial_stderr
        super().__init__(message)


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
    "claude": "claude -p --permission-mode auto",
    "droid": "droid exec",
    "pi": "pi -p",
    # Oh-My-Pi: a distinct CLI binary that wraps Pi internally but is
    # invoked directly (``omp -p``). The dispatch layer treats ``omp``
    # as a first-class backend, not an alias for ``pi`` — model flag,
    # timeout, and YAML manifest extraction all apply.
    "omp": "omp -p",
    "stub": "stub",
}

# Map a user-facing agent name (CLI ``--agent`` value, or ``[agent].backend``
# in ``.deviate/config.toml``) to the canonical backend that the dispatch
# layer invokes. Only ``factory`` remains as an alias — the Factory Droid
# IDE drives the ``droid`` binary under the hood. All other names are
# canonical: ``omp`` is its own backend (not an alias for ``pi``); the
# remaining names already match the dispatch-layer identifier.
AGENT_TO_BACKEND: dict[str, str] = {
    "factory": "droid",
    "droid": "droid",
    "claude": "claude",
    "opencode": "opencode",
    "pi": "pi",
    "omp": "omp",
}


def resolve_agent_to_backend(agent: str) -> str:
    """Return the canonical backend for *agent*.

    User-facing aliases (``factory``) are mapped to their underlying
    backend binary. Already-canonical names (``opencode``, ``claude``,
    ``droid``, ``pi``, ``omp``) pass through unchanged. Unknown values
    are returned unchanged so the caller can surface a validation error
    against :class:`~deviate.state.config.AgentConfig`'s ``backend``
    Literal.
    """
    return AGENT_TO_BACKEND.get(agent, agent)


PI_RPC_COMMAND: list[str] = ["pi", "--mode", "rpc", "--no-session"]


# Per-backend model-flag dispatch. ``None`` means the backend does not
# accept ``--model`` on the CLI (model routing is the operator's
# responsibility — claude ignores model config entirely).
# ``["--model"]`` means the backend accepts the ``--model <id>`` flag
# (``opencode``, ``droid``, ``pi``, and ``omp`` all do).
MODEL_FLAGS: dict[str, list[str] | None] = {
    "pi": ["--model"],
    "claude": None,
    "opencode": ["--model"],
    "droid": ["--model"],
    "omp": ["--model"],
}

# Backends whose CLI expects the prompt as a positional argument rather
# than via stdin. The prompt gets appended as the last element of the
# command list before spawning the subprocess.
PROMPT_AS_ARG_BACKENDS: frozenset[str] = frozenset({"omp"})


_YAML_BLOCK_RE = re.compile(r"```(?:yaml)?\s*\n(.*?)```", re.DOTALL)
_YAML_MAPPING_START_RE = re.compile(r"^[\w_]+:\s", re.MULTILINE)
_YAML_HANDOVER_MARKER_RE = re.compile(
    r"<handover_manifest>\s*(?:\n```(?:yaml)?\s*\n)?(.*?)(?:\n```\s*)?$",
    re.DOTALL,
)


def _strip_md_for_yaml(text: str) -> str:
    """Strip markdown artifacts that confuse YAML parsing in bare output."""
    text = re.sub(r"^<handover_manifest>\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    return text.strip()


class AgentBackend:
    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or AgentConfig()

    @staticmethod
    def _extract_yaml_block(text: str) -> str:
        m = _YAML_BLOCK_RE.search(text)
        if m:
            return m.group(1).strip()

        m = _YAML_HANDOVER_MARKER_RE.search(text)
        if m:
            candidate = m.group(1).strip()
            if candidate:
                return candidate

        m = _YAML_MAPPING_START_RE.search(text)
        if m:
            return text[m.start() :].strip()

        cleaned = _strip_md_for_yaml(text)
        if cleaned:
            try:
                yaml.safe_load(cleaned)
            except yaml.YAMLError:
                return ""
            return cleaned

        return ""

    @staticmethod
    def _yaml_error_hint(text: str) -> str:
        has_yaml_fence = bool(re.search(r"```\s*yaml", text, re.IGNORECASE))
        has_yaml_content = bool(_YAML_MAPPING_START_RE.search(text))
        has_handover_marker = bool(re.search(r"<handover_manifest>", text))
        if has_handover_marker and not has_yaml_fence:
            return (
                " Found <handover_manifest> tag but could not extract YAML —"
                " ensure the YAML content follows the tag,"
                " optionally inside a ```yaml block."
            )
        if not has_yaml_fence and has_yaml_content:
            return (
                " Expected ```yaml block, found inline YAML —"
                " wrap in ```yaml for reliability, or ensure"
                " no explanatory text precedes the YAML content."
            )
        if not has_yaml_fence:
            return (
                " No YAML handover manifest detected in agent output."
                " The agent must emit a YAML manifest (plain or in a ```yaml block)."
            )
        if re.search(r"(?<!\"):\s+\w", text):
            return " Check that all YAML string values are double-quoted."
        return ""

    @staticmethod
    def parse_output(
        stdout: str,
        backend_name: str,
    ) -> HandoverManifest:
        if not stdout.strip():
            raise EmptyOutputError(
                f"Agent backend '{backend_name}' returned empty output"
            )

        yaml_text = AgentBackend._extract_yaml_block(stdout)

        if not yaml_text:
            hint = AgentBackend._yaml_error_hint(stdout)
            raise MalformedHandoverManifestError(
                f"No YAML handover manifest detected in agent output.{hint}"
            )

        try:
            data = yaml.safe_load(yaml_text)
        except yaml.YAMLError as e:
            hint = AgentBackend._yaml_error_hint(stdout)
            raise MalformedHandoverManifestError(
                f"Failed to parse YAML handover manifest: {e}{hint}"
            )

        if not isinstance(data, dict):
            hint = AgentBackend._yaml_error_hint(stdout)
            raise MalformedHandoverManifestError(
                f"YAML handover manifest is not a mapping (got {type(data).__name__})."
                f" The manifest must be a key: value mapping.{hint}"
            )

        try:
            return HandoverManifest(**data)
        except ValidationError as e:
            raise MalformedHandoverManifestError(
                f"Handover manifest failed schema validation: {e}"
            )

    def _invoke_blocking(
        self,
        proc: subprocess.Popen[bytes],
        cmd: list[str],
        prompt: str,
        timeout_secs: int,
        backend_name: str,
    ) -> tuple[str, str]:
        try:
            stdout_bytes, stderr_bytes = proc.communicate(
                input=prompt.encode("utf-8"),
                timeout=timeout_secs,
            )
        except subprocess.TimeoutExpired as e:
            proc.kill()
            proc.wait()
            partial_out = e.output.decode("utf-8") if e.output else ""
            partial_err = e.stderr.decode("utf-8") if e.stderr else ""
            raise AgentTimeoutError(
                f"Agent backend '{backend_name}' timed out "
                f"after {timeout_secs}s"
                f" (retried once with 30s backoff)",
                partial_stdout=partial_out,
                partial_stderr=partial_err,
            )
        stdout = stdout_bytes.decode("utf-8") if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8") if stderr_bytes else ""
        if proc.returncode != 0:
            raise AgentSubprocessError(
                message=stderr or f"Agent exited with code {proc.returncode}",
                exit_code=proc.returncode,
            )
        return stdout, stderr

    def _invoke_streaming(
        self,
        proc: subprocess.Popen[bytes],
        cmd: list[str],
        prompt: str,
        timeout_secs: int,
        backend_name: str,
        output_callback: OutputCallback,
    ) -> tuple[str, str]:
        proc.stdin.write(prompt.encode("utf-8"))
        proc.stdin.close()

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        stdout_done = False

        def read_stdout() -> None:
            nonlocal stdout_done
            for raw_line in proc.stdout:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
                stdout_lines.append(line)
                output_callback(line)
            stdout_done = True

        def read_stderr() -> None:
            for raw_line in proc.stderr:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
                stderr_lines.append(line)

        threads = [
            threading.Thread(target=read_stdout),
            threading.Thread(target=read_stderr),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=timeout_secs)

        if not stdout_done or any(t.is_alive() for t in threads):
            proc.kill()
            for t in threads:
                t.join(timeout=5)
            raise AgentTimeoutError(
                f"Agent backend '{backend_name}' timed out after {timeout_secs}s",
                partial_stdout="\n".join(stdout_lines),
                partial_stderr="\n".join(stderr_lines),
            )

        proc.wait()
        stdout = "\n".join(stdout_lines)
        stderr = "\n".join(stderr_lines)

        if proc.returncode != 0:
            raise AgentSubprocessError(
                message=stderr or f"Agent exited with code {proc.returncode}",
                exit_code=proc.returncode,
            )
        return stdout, stderr

    def _invoke_rpc_blocking(
        self,
        proc: subprocess.Popen[bytes],
        cmd: list[str],
        prompt: str,
        timeout_secs: int,
        backend_name: str,
    ) -> tuple[str, str]:
        payload = (json.dumps({"type": "prompt", "content": prompt}) + "\n").encode(
            "utf-8"
        )
        try:
            stdout_bytes, stderr_bytes = proc.communicate(
                input=payload, timeout=timeout_secs
            )
        except subprocess.TimeoutExpired as e:
            proc.kill()
            proc.wait()
            partial_out = e.output.decode("utf-8") if e.output else ""
            partial_err = e.stderr.decode("utf-8") if e.stderr else ""
            raise AgentTimeoutError(
                f"Agent backend '{backend_name}' timed out after {timeout_secs}s",
                partial_stdout=partial_out,
                partial_stderr=partial_err,
            )
        stdout = stdout_bytes.decode("utf-8") if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8") if stderr_bytes else ""
        if proc.returncode != 0:
            raise AgentSubprocessError(
                message=stderr or f"Agent exited with code {proc.returncode}",
                exit_code=proc.returncode,
            )
        manifest_text = ""
        for raw_line in stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") != "agent_end":
                continue
            message = event.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content", "")
            if isinstance(content, str):
                manifest_text = content
                break
        return manifest_text, stderr

    def invoke(
        self,
        prompt: str,
        backend: BackendName | None = None,
        timeout: int | None = None,
        output_callback: OutputCallback | None = None,
        cwd: str | None = None,
        model: str | None = None,
    ) -> HandoverManifest:
        backend_name: BackendName = backend or self.config.backend
        use_rpc = backend_name == "pi" and self.config.pi_rpc

        if use_rpc:
            cmd = list(PI_RPC_COMMAND)
        else:
            backend_cmd = BACKEND_COMMANDS.get(backend_name)
            if backend_cmd is None:
                raise AgentBinaryNotFoundError(f"Unknown backend: {backend_name}")

            cmd = backend_cmd.split()
            model_flag = MODEL_FLAGS.get(backend_name, ["--model"])
            if model is not None and model_flag is not None:
                cmd.extend([model_flag[0], model])
            # Backends that expect the prompt as a positional CLI argument
            # (e.g. ``omp -p "prompt"``) get the prompt appended to the
            # command. The ``prompt`` variable is then cleared so the
            # subprocess dispatch does not send it via stdin.
            if backend_name in PROMPT_AS_ARG_BACKENDS:
                cmd.append(prompt)
                prompt = ""
        effective_timeout = timeout or self.config.timeout

        popen_kwargs: dict[str, Any] = dict(
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if cwd is not None:
            popen_kwargs["cwd"] = cwd

        try:
            proc = subprocess.Popen(cmd, **popen_kwargs)
        except FileNotFoundError:
            raise AgentBinaryNotFoundError(
                f"Agent binary not found on PATH for backend: {backend_name}"
            )

        try:
            stdout, stderr = self._dispatch_invocation(
                proc,
                cmd,
                prompt,
                effective_timeout,
                backend_name,
                output_callback,
                use_rpc,
            )
        except AgentTimeoutError:
            time.sleep(30)
            retry_proc = subprocess.Popen(cmd, **popen_kwargs)
            stdout, stderr = self._dispatch_invocation(
                retry_proc,
                cmd,
                prompt,
                effective_timeout,
                backend_name,
                output_callback,
                use_rpc,
            )

        return self.parse_output(stdout, backend_name)

    def _dispatch_invocation(
        self,
        proc: subprocess.Popen[bytes],
        cmd: list[str],
        prompt: str,
        timeout_secs: int,
        backend_name: str,
        output_callback: OutputCallback | None,
        use_rpc: bool,
    ) -> tuple[str, str]:
        if use_rpc:
            return self._invoke_rpc_blocking(
                proc, cmd, prompt, timeout_secs, backend_name
            )
        if output_callback is not None:
            return self._invoke_streaming(
                proc, cmd, prompt, timeout_secs, backend_name, output_callback
            )
        return self._invoke_blocking(proc, cmd, prompt, timeout_secs, backend_name)


class StubAgentBackend(AgentBackend):
    def __init__(self, config: AgentConfig | None = None) -> None:
        super().__init__(config)
        self._invoked = False

    def invoke(
        self,
        prompt: str,
        backend: BackendName | None = None,
        timeout: int | None = None,
        output_callback: OutputCallback | None = None,
        cwd: str | None = None,
        model: str | None = None,
    ) -> HandoverManifest:
        self._invoked = True
        if output_callback is not None:
            output_callback(prompt)
        return HandoverManifest(phase="RED", status="success")


class StubPiBackend(StubAgentBackend):
    """Pi-shaped stub backend for downstream test isolation.

    Marker subclass of :class:`StubAgentBackend` — shares the inherited
    ``invoke()``, ``_invoked`` flag, callable surface, and
    :class:`HandoverManifest` contract. Provides Pi-specific identity for
    downstream fixtures that need to distinguish Pi-stub from generic stub.
    """
