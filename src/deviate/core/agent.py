from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from collections.abc import Callable
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, ValidationError

from deviate.state.config import AgentConfig

OutputCallback = Callable[[str], None]


MAX_PROMPT_CHARS = 80_000
STREAM_STALL_TIMEOUT_SECONDS = 60
_PROMPT_TRUNCATED_MARKER = (
    "\n\n<!-- PROMPT_TRUNCATED: original was {original_chars} chars -->\n\n"
)


def _truncate_prompt(prompt: str) -> str:
    """Cap *prompt* to ``MAX_PROMPT_CHARS`` while preserving head and tail."""
    if len(prompt) <= MAX_PROMPT_CHARS:
        return prompt
    marker = _PROMPT_TRUNCATED_MARKER.format(original_chars=len(prompt))
    remaining = MAX_PROMPT_CHARS - len(marker)
    if remaining <= 0:
        return marker[:MAX_PROMPT_CHARS]
    head_size = remaining // 2
    tail_size = remaining - head_size
    return f"{prompt[:head_size]}{marker}{prompt[-tail_size:]}"


BackendName = Literal["opencode", "claude", "droid", "pi", "omp", "stub"]


class HandoverManifest(BaseModel):
    phase: str = "UNKNOWN"
    status: str = "UNKNOWN"
    task_id: str | None = None
    test_file: str | None = None
    verification_command: str | None = None
    expected_failure_node: str | None = None
    rationale: str | None = None
    next_phase: str | None = None
    next_action: Optional[
        Literal["revert_before", "revert_to_red", "continue_refactor", "skip_refactor"]
    ] = None
    files: list[str] | None = None
    parse_errors: list[str] = []

    model_config = {"extra": "allow"}

    @property
    def is_success(self) -> bool:
        return (
            self.status.upper() in {"PASS", "SUCCESS"}
            and self.phase.upper() != "UNKNOWN"
            and not self.parse_errors
        )


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

    @staticmethod
    def _yaml_error_hint(text: str) -> str:
        if '\\""' in text or '\\\\"' in text:
            return (
                " Avoid backslash-escaped quotes inside double-quoted YAML"
                " scalars — use single quotes or a YAML block scalar (|)"
                " instead."
            )
        if text.count('"') % 2 == 1:
            return (
                " Unbalanced double quotes detected. Ensure every value"
                ' wrapped in "..." has a matching closing quote.'
            )
        if re.search(r"^\s*\w+:\s*\|[^\n]*\n[^\s|]", text, re.MULTILINE):
            return (
                " Indent block scalar content (|) so every continuation"
                " line is indented at least one space deeper than its key."
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

        required_fields = ("phase", "status")
        missing = [name for name in required_fields if not data.get(name)]
        try:
            manifest = HandoverManifest(**data)
        except ValidationError as e:
            parse_errors = [
                f"{'.'.join(str(p) for p in err.get('loc', ()))}: {err.get('msg', '')}"
                for err in e.errors()
            ]
            recovered = dict(data)
            recovered["parse_errors"] = parse_errors
            recovered["phase"] = recovered.get("phase") or "UNKNOWN"
            recovered["status"] = recovered.get("status") or "UNKNOWN"
            return HandoverManifest(**recovered)
        if missing:
            manifest.parse_errors = [
                f"{name}: field missing or empty" for name in missing
            ]
            return manifest
        return manifest

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
        try:
            proc.stdin.write(prompt.encode("utf-8"))
            proc.stdin.close()
        except (BrokenPipeError, ValueError):
            # Subprocess died before the prompt drained; the for-loop below
            # will surface the return code.
            pass

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        stdout_done = False
        stall_reason: str | None = None
        stall_partial: tuple[str, str] | None = None

        def read_stdout() -> None:
            nonlocal stdout_done
            try:
                for raw_line in proc.stdout:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
                    stdout_lines.append(line)
                    output_callback(line)
            except (ValueError, OSError):
                pass
            finally:
                stdout_done = True

        def read_stderr() -> None:
            try:
                for raw_line in proc.stderr:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
                    stderr_lines.append(line)
            except (ValueError, OSError, RuntimeError):
                pass

        threads = [
            threading.Thread(target=read_stdout),
            threading.Thread(target=read_stderr),
        ]
        for t in threads:
            t.start()

        stall_deadline = time.monotonic() + STREAM_STALL_TIMEOUT_SECONDS
        while True:
            if stdout_done and not any(t.is_alive() for t in threads):
                break
            if time.monotonic() >= stall_deadline:
                stall_reason = (
                    f"STALL_DETECTED: no agent output for "
                    f"{STREAM_STALL_TIMEOUT_SECONDS}s"
                )
                stall_partial = (
                    "\n".join(stdout_lines),
                    "\n".join(stderr_lines),
                )
                break
            time.sleep(0.05)

        if stall_reason is not None:
            proc.kill()
            for t in threads:
                t.join(timeout=5)
            raise AgentTimeoutError(
                stall_reason,
                partial_stdout=(stall_partial or ("", ""))[0],
                partial_stderr=(stall_partial or ("", ""))[1],
            )

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
        prompt = _truncate_prompt(prompt)

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

        try:
            return self.parse_output(stdout, backend_name)
        except (MalformedHandoverManifestError, EmptyOutputError) as exc:
            strict_prompt = (
                prompt
                + "\n\n<!-- Previous attempt produced an unparseable manifest:\n"
                + str(exc)
                + "\nRe-emit a strict YAML block delimited by ```yaml ... ``` only. -->"
            )
            strict_prompt = _truncate_prompt(strict_prompt)
            retry_proc = subprocess.Popen(cmd, **popen_kwargs)
            try:
                stdout, stderr = self._dispatch_invocation(
                    retry_proc,
                    cmd,
                    strict_prompt,
                    effective_timeout,
                    backend_name,
                    output_callback,
                    use_rpc,
                )
            except AgentTimeoutError:
                proc.kill()
                raise
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
