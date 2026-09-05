from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError

from deviate.state.config import AgentConfig, DeviateConfig

OutputCallback = Callable[[str], None]


MAX_PROMPT_CHARS = 80_000
STREAM_STALL_TIMEOUT_SECONDS = 900
# Smart-stall detector: when stdout byte-rate over the last minute drops
# below this floor, the agent is treated as stalled (waiting on a hung
# subprocess, infinite tool loop, etc.) even if it trickles out a few
# bytes per minute. Empirically tuned for `mix precommit` on this repo,
# which emits ~100 B/s during compile + test runs but drops to ~0 B/s when
# the agent subprocess is genuinely stuck. See diagnosis F2.
STREAM_STALL_MIN_BYTES_PER_SECOND = 50
STREAM_STALL_WINDOW_SECONDS = 60
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


BackendName = Literal["opencode", "claude", "droid", "pi", "omp", "codex", "stub"]


class EvidenceItem(BaseModel):
    """Per-AC citation the TDD JUDGE evidence gate can read."""

    ac: str
    test_path: str
    test_quote: str
    impl_path: str = Field(default="")
    impl_quote: str = Field(default="")

    model_config = {"extra": "ignore"}


class HandoverManifest(BaseModel):
    phase: str = "UNKNOWN"
    status: str = "UNKNOWN"
    task_id: str | None = None
    test_file: str | None = None
    verification_command: str | None = None
    expected_failure_node: str | None = None
    rationale: str | None = None
    failure_kind: Literal["mechanical", "test_defect", "already_satisfied"] | None = (
        None
    )
    next_phase: str | None = None
    next_action: Optional[
        Literal[
            "revert_red",
            "revert_green",
            "continue_refactor",
            "skip_refactor",
            "proceed_to_refactor_no_diff",
        ]
    ] = None
    files: list[str] | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
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
        self,
        message: str,
        partial_stdout: str = "",
        partial_stderr: str = "",
        *,
        retryable: bool = True,
    ):
        self.partial_stdout = partial_stdout
        self.partial_stderr = partial_stderr
        # Streaming stall / wall-clock already killed the child.
        # Blocking ``TimeoutExpired`` stays retryable (default True).
        self.retryable = retryable
        super().__init__(message)


_STREAMING_STALL_TOKENS = ("STALL_DETECTED", "SMART_STALL_DETECTED")
# Print-mode CLIs that buffer all stdout until process exit. A stdout-silence
# stall cannot distinguish working from hung on these transports (GH-166).
_BUFFERED_PRINT_BACKENDS: frozenset[str] = frozenset({"pi", "omp"})


def _is_buffered_print_cli(backend_name: str, cmd: list[str]) -> bool:
    """Return True when *cmd* is a print-mode CLI that buffers stdout until exit.

    ``pi -p`` and ``omp -p`` emit the full answer only at process exit.
    RPC (``pi --mode rpc``) and streaming backends are not buffered this way.
    """
    if backend_name not in _BUFFERED_PRINT_BACKENDS:
        return False
    return "-p" in cmd


def _backend_timeout_message(backend_name: str, timeout_secs: int) -> str:
    return f"Agent backend '{backend_name}' timed out after {timeout_secs}s"


def _is_streaming_stall(error: BaseException) -> bool:
    """Return True for a hard or smart streaming stall.

    Those paths already killed the child. Blocking ``TimeoutExpired``
    stays on the single 30s retry so AGENT_TIMEOUT can surface inside
    the interactive budget (ISS-ADH-025 / GH-61).
    """
    return str(error).startswith(_STREAMING_STALL_TOKENS)


def _skip_timeout_retry(error: BaseException) -> bool:
    """Return True when invoke must not sleep 30s or start a second child.

    Stall tokens and ``retryable=False`` (streaming wall-clock) already
    killed the child. Blocking ``TimeoutExpired`` stays on the 30s retry
    (ISS-ADH-027).
    """
    return _is_streaming_stall(error) or (
        isinstance(error, AgentTimeoutError) and not error.retryable
    )


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
    # ChatGPT Codex CLI (non-interactive). Official ``codex exec`` reads
    # the prompt from stdin when no positional prompt is given — omit the
    # ``-`` sentinel so ``MODEL_FLAGS`` can append ``--model`` at the end
    # without it being swallowed as prompt text. Default ``codex exec``
    # sandbox is read-only; ``--sandbox workspace-write`` plus
    # ``--approve-for-me`` provides unattended approval without bypassing the
    # sandbox. Do not use ``--dangerously-bypass-approvals-and-sandbox``.
    "codex": "codex exec --sandbox workspace-write --approve-for-me",
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
    "codex": "codex",
}


def resolve_agent_to_backend(agent: str) -> str:
    """Return the canonical backend for *agent*.

    User-facing aliases (``factory``) are mapped to their underlying
    backend binary.     Already-canonical names (``opencode``, ``claude``,
    ``droid``, ``pi``, ``omp``, ``codex``) pass through unchanged. Unknown values
    are returned unchanged so the caller can surface a validation error
    against :class:`~deviate.state.config.AgentConfig`'s ``backend``
    Literal.
    """
    return AGENT_TO_BACKEND.get(agent, agent)


PI_RPC_COMMAND: list[str] = ["pi", "--mode", "rpc", "--no-session"]
PI_CODING_TOOLS: tuple[str, ...] = ("read", "bash", "edit", "write")
PI_DEVIATDD_SKILL = Path(".pi") / "skills" / "deviatdd" / "SKILL.md"
PI_SHARED_DEVIATDD_SKILL = Path(".agents") / "skills" / "deviatdd" / "SKILL.md"
SCHEMA_REJECTION_TOKENS: tuple[str, ...] = (
    "tool_count_limit",
    "unsupported_tool_schema",
)


def _pi_lean_flags(cwd: str | None) -> list[str]:
    """Return the default lean Pi tool policy after the transport prefix."""
    # No --no-extensions: extension-registered providers (e.g. commandcode)
    # must load, otherwise pi cannot resolve a saved default model from that
    # provider and silently falls back to whatever env keys authenticate.
    flags = [
        "--tools",
        ",".join(PI_CODING_TOOLS),
        "--no-skills",
    ]
    skill_root = Path(cwd) if cwd is not None else Path.cwd()
    if (skill_root / PI_SHARED_DEVIATDD_SKILL).is_file():
        flags.extend(["--skill", str(PI_SHARED_DEVIATDD_SKILL)])
    elif (skill_root / PI_DEVIATDD_SKILL).is_file():
        flags.extend(["--skill", str(PI_DEVIATDD_SKILL)])
    return flags


def _schema_rejection_token(text: str) -> str | None:
    """Return the first schema-rejection token found in *text*."""
    for token in SCHEMA_REJECTION_TOKENS:
        if token in text:
            return token
    return None


def is_schema_rejection(text: str) -> bool:
    """Return whether *text* carries a provider schema-limit token."""
    return _schema_rejection_token(text) is not None


def _schema_rejection_message(text: str) -> str | None:
    """Return the first line that carries a schema-rejection token."""
    token = _schema_rejection_token(text)
    if token is None:
        return None
    for line in text.splitlines():
        if token in line:
            return line
    return text.strip()


def _raise_schema_rejection(proc: subprocess.Popen[bytes], message: str) -> None:
    """Kill *proc* and raise a token-bearing ``AgentSubprocessError``."""
    proc.kill()
    exit_code = proc.returncode if proc.returncode not in (None, 0) else 1
    raise AgentSubprocessError(message=message, exit_code=exit_code)


def _abort_on_schema_rejection(proc: subprocess.Popen[bytes], text: str) -> None:
    """Kill *proc* and raise when *text* carries a schema-rejection token."""
    message = _schema_rejection_message(text)
    if message is None:
        return
    _raise_schema_rejection(proc, message)


def _decode_stdio(
    stdout_bytes: bytes | None, stderr_bytes: bytes | None
) -> tuple[str, str]:
    stdout = stdout_bytes.decode("utf-8") if stdout_bytes else ""
    stderr = stderr_bytes.decode("utf-8") if stderr_bytes else ""
    return stdout, stderr


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
    "codex": ["--model"],
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


_QUOTE_FIELD_LINE_RE = re.compile(r"^(\s*)(quote|test_quote|impl_quote):\s+(.*)$")


def _unwrap_double_quoted_value(raw: str) -> str:
    """Strip a surrounding pair of double quotes, or a leading opener."""
    if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    if raw.startswith('"'):
        return raw[1:]
    return raw


def _is_broken_double_quoted_scalar(key: str, raw: str) -> bool:
    """Return True when *raw* is a double-quoted scalar ``yaml.safe_load`` rejects."""
    if not raw.startswith('"'):
        return False
    try:
        parsed = yaml.safe_load(f"{key}: {raw}\n")
    except yaml.YAMLError:
        return True
    return not isinstance(parsed, dict) or key not in parsed


def _repair_unescaped_quote_scalars(text: str) -> str:
    """Rewrite broken evidence-quote double-quoted scalars as ``|`` block scalars.

    Models emit citations such as ``test_quote: "assert "YAGNI" in text"``
    without escaping the inner quotes. Convert those lines so
    ``yaml.safe_load`` can recover the intended text. Well-formed values
    are left unchanged (GH-116).
    """
    if not text:
        return text
    repaired: list[str] = []
    for line in text.splitlines(keepends=True):
        ending = ""
        body = line
        if body.endswith("\r\n"):
            ending = "\r\n"
            body = body[:-2]
        elif body.endswith("\n"):
            ending = "\n"
            body = body[:-1]
        match = _QUOTE_FIELD_LINE_RE.match(body)
        if match is None:
            repaired.append(line)
            continue
        indent, key, raw = match.groups()
        if not _is_broken_double_quoted_scalar(key, raw):
            repaired.append(line)
            continue
        content = _unwrap_double_quoted_value(raw)
        block_ending = ending or "\n"
        repaired.append(f"{indent}{key}: |-{block_ending}")
        repaired.append(f"{indent}  {content}{ending}")
    return "".join(repaired)


def _safe_load_handover_yaml(text: str) -> object:
    """Load handover YAML, recovering unescaped quotes in evidence fields."""
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        repaired = _repair_unescaped_quote_scalars(text)
        if repaired == text:
            raise
        return yaml.safe_load(repaired)


def _looks_like_manifest(yaml_text: str) -> bool:
    """Return True iff *yaml_text* parses to a dict with at least 2 keys.

    Used by `_extract_yaml_block` to reject prose-with-stray-mapping output
    that would otherwise be silently recovered into an UNKNOWN manifest by
    the schema-recovery path. Single-key dicts (``Status: complete``) look
    like prose, not manifests; multi-key dicts may be partial manifests
    that should flow through schema recovery.
    """
    try:
        parsed = _safe_load_handover_yaml(yaml_text)
    except yaml.YAMLError:
        return False
    return isinstance(parsed, dict) and len(parsed) >= 2


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
            candidate = text[m.start() :].strip()
            if _looks_like_manifest(candidate):
                return candidate
        cleaned = _strip_md_for_yaml(text)
        if cleaned and _looks_like_manifest(cleaned):
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
            data = _safe_load_handover_yaml(yaml_text)
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
            errors = e.errors()
            parse_errors = [
                f"{'.'.join(str(p) for p in err.get('loc', ()))}: {err.get('msg', '')}"
                for err in errors
            ]
            recovered = dict(data)
            # Drop every top-level field that failed validation so the
            # reconstruction below succeeds. Without this the offending
            # value (e.g. an out-of-enum ``failure_kind`` / ``next_action``)
            # re-raises the same ValidationError unguarded, the recovery
            # degrades into an AGENT_SKIP, and the phase aborts with a
            # misleading "agent returned no manifest" (GH-52, GH-55).
            for err in errors:
                loc = err.get("loc", ())
                if loc:
                    key = loc[0]
                    if key in recovered and key != "parse_errors":
                        del recovered[key]
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
        stdout, stderr = _decode_stdio(stdout_bytes, stderr_bytes)
        _abort_on_schema_rejection(proc, f"{stdout}\n{stderr}")
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
        stall_timeout: int | None = None,
    ) -> tuple[str, str]:
        # GH-53: the stall deadline defaults to the module constant but can
        # be raised per invocation. DIRECT EXECUTE phases run deterministic
        # long pipelines (clean-checkout ``mise run check`` / cargo release
        # builds) that legitimately emit nothing for >15 min; the interactive
        # 900s TDD budget would kill a healthy run.
        stall_timeout_secs = stall_timeout or STREAM_STALL_TIMEOUT_SECONDS
        # ``pi -p`` / ``omp -p`` buffer every stdout byte until exit. Watching
        # stdout silence (or 0 B/s) would kill a healthy GREEN that thinks for
        # longer than the 900s default. Wall-clock ``timeout_secs`` still
        # applies. Streaming backends keep the silence stall (GH-166).
        watch_stdout_silence = not _is_buffered_print_cli(backend_name, cmd)
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
        poll_abort_reason: str | None = None
        poll_abort_partial: tuple[str, str] | None = None
        schema_rejection_line: str | None = None

        # Two-track stall detector (see diagnosis F2 in the README).
        # ``stall_lock`` + ``stall_deadline`` reset on stdout only and trip
        # after STREAM_STALL_TIMEOUT_SECONDS of stdout silence — but only
        # when the child is a streaming backend. ``pi -p`` / ``omp -p``
        # buffer stdout until exit, so silence is not a hang (GH-166).
        # Stderr is diagnostic capture (partial_stderr) and must not refresh
        # the hard clock or feed ``record_bytes``. The ``byte_samples``
        # window tracks stdout emit rate over STREAM_STALL_WINDOW_SECONDS
        # — a stuck streaming agent that trickles a few stdout bytes per
        # minute resets the line-timer on every emit but the byte-rate
        # stays well below the floor for a real working invocation like
        # ``mix precommit`` (~100 B/s).
        stall_lock = threading.Lock()
        invoke_started = time.monotonic()
        wall_deadline = invoke_started + timeout_secs
        stall_deadline = [invoke_started + stall_timeout_secs]
        byte_samples: list[tuple[float, int]] = []

        def captured_streams() -> tuple[str, str]:
            return "\n".join(stdout_lines), "\n".join(stderr_lines)

        def record_bytes(num_bytes: int) -> None:
            now = time.monotonic()
            with stall_lock:
                byte_samples.append((now, num_bytes))
                cutoff = now - STREAM_STALL_WINDOW_SECONDS
                while byte_samples and byte_samples[0][0] < cutoff:
                    byte_samples.pop(0)

        def byte_rate_below_floor() -> bool:
            with stall_lock:
                if len(byte_samples) < 3:
                    return False
                if not byte_samples:
                    return False
                window = byte_samples[-1][0] - byte_samples[0][0]
                if window <= 0:
                    return False
                total = sum(n for _, n in byte_samples)
                rate = total / window
                return rate < STREAM_STALL_MIN_BYTES_PER_SECOND

        def refresh_stall_deadline() -> None:
            with stall_lock:
                stall_deadline[0] = time.monotonic() + stall_timeout_secs

        def note_schema_rejection(line: str) -> bool:
            nonlocal schema_rejection_line
            message = _schema_rejection_message(line)
            if message is None:
                return False
            schema_rejection_line = message
            proc.kill()
            return True

        def read_stdout() -> None:
            nonlocal stdout_done
            try:
                for raw_line in proc.stdout:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
                    if note_schema_rejection(line):
                        return
                    stdout_lines.append(line)
                    output_callback(line)
                    record_bytes(len(raw_line))
                    refresh_stall_deadline()
            except (ValueError, OSError):
                pass
            finally:
                stdout_done = True

        def capture_stderr_diagnostics() -> None:
            try:
                for raw_line in proc.stderr:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
                    stderr_lines.append(line)
                    if note_schema_rejection(line):
                        return
            except (ValueError, OSError, RuntimeError):
                pass

        threads = [
            threading.Thread(target=read_stdout),
            threading.Thread(target=capture_stderr_diagnostics),
        ]
        for t in threads:
            t.start()

        def stall_deadline_remaining() -> float:
            with stall_lock:
                return stall_deadline[0] - time.monotonic()

        def wall_clock_remaining() -> float:
            return wall_deadline - time.monotonic()

        def capture_poll_abort(reason: str) -> None:
            nonlocal poll_abort_reason, poll_abort_partial
            poll_abort_reason = reason
            poll_abort_partial = captured_streams()

        def raise_nonretryable_timeout(
            reason: str, streams: tuple[str, str] | None = None
        ) -> None:
            proc.kill()
            for t in threads:
                t.join(timeout=5)
            partial_stdout, partial_stderr = streams or captured_streams()
            raise AgentTimeoutError(
                reason,
                partial_stdout=partial_stdout,
                partial_stderr=partial_stderr,
                retryable=False,
            )

        while True:
            if schema_rejection_line is not None:
                break
            if stdout_done and not any(t.is_alive() for t in threads):
                break
            # One wall-clock exit, independent of stall / schema exits.
            # Periodic stdout refreshes only stall_deadline.
            if wall_clock_remaining() <= 0:
                capture_poll_abort(_backend_timeout_message(backend_name, timeout_secs))
                break
            if watch_stdout_silence and stall_deadline_remaining() <= 0:
                capture_poll_abort(
                    f"STALL_DETECTED: no agent output for {stall_timeout_secs}s"
                )
                break
            # Smart-stall gate: only trips when the rolling byte-rate over
            # the last window drops below the floor AND we have enough
            # samples to trust the measurement. ``mix precommit`` emits
            # ~100 B/s; a stuck subprocess emits <10 B/s. Threshold chosen
            # at 50 B/s to leave room for compile output bursts.
            # Buffered print CLIs never emit mid-run, so 0 B/s is not hung.
            if (
                watch_stdout_silence
                and time.monotonic() - stall_deadline[0] + stall_timeout_secs
                > stall_timeout_secs / 2
                and byte_rate_below_floor()
            ):
                capture_poll_abort(
                    f"SMART_STALL_DETECTED: byte-rate dropped below "
                    f"{STREAM_STALL_MIN_BYTES_PER_SECOND} B/s for "
                    f"{STREAM_STALL_WINDOW_SECONDS}s while stdout was "
                    f"still emitting (likely hung subprocess)"
                )
                break
            time.sleep(0.05)
        if schema_rejection_line is not None:
            for t in threads:
                t.join(timeout=5)
            _abort_on_schema_rejection(proc, schema_rejection_line)
        if poll_abort_reason is not None:
            raise_nonretryable_timeout(poll_abort_reason, poll_abort_partial)

        for t in threads:
            t.join(timeout=timeout_secs)

        if not stdout_done or any(t.is_alive() for t in threads):
            raise_nonretryable_timeout(
                _backend_timeout_message(backend_name, timeout_secs)
            )

        proc.wait()
        stdout, stderr = captured_streams()
        _abort_on_schema_rejection(proc, f"{stdout}\n{stderr}")

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
                _backend_timeout_message(backend_name, timeout_secs),
                partial_stdout=partial_out,
                partial_stderr=partial_err,
            )
        stdout, stderr = _decode_stdio(stdout_bytes, stderr_bytes)
        _abort_on_schema_rejection(proc, f"{stdout}\n{stderr}")
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
        stall_timeout: int | None = None,
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
            if backend_name == "codex" and self.config.reasoning_effort:
                cmd.extend(
                    ["-c", f"model_reasoning_effort={self.config.reasoning_effort}"]
                )
            # Backends that expect the prompt as a positional CLI argument
            # (e.g. ``omp -p "prompt"``) get the prompt appended to the
            # command. The ``prompt`` variable is then cleared so the
            # subprocess dispatch does not send it via stdin.
            if backend_name in PROMPT_AS_ARG_BACKENDS:
                cmd.append(prompt)
                prompt = ""
        if backend_name == "pi":
            cmd.extend(_pi_lean_flags(cwd))
        # Consolidated deadline: the caller passes an explicit ``timeout``
        # (resolved from ``DeviateConfig.timeout_seconds``), else fall back
        # to the single config default (AC-PLAN-005).
        effective_timeout = timeout or DeviateConfig().timeout_seconds

        popen_kwargs: dict[str, Any] = dict(
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # Explicit ``env=None`` (Python default) — the agent subprocess
            # inherits the parent's ``os.environ`` verbatim, so keys set by
            # the operator's shell (PI_MODEL, PI_DEFAULT_MODEL,
            # OPENCODE_API_KEY, mise-injected vars, …) reach ``pi`` / ``omp``
            # without any deviation-side rewriting. Model selection is the
            # agent layer's responsibility; deviate only forwards ``--model``
            # when ``[models]`` config or ``--model`` CLI resolved a value.
            # operator relies on, so we leave it open.
            env=None,
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
                stall_timeout=stall_timeout,
            )
        except AgentTimeoutError as exc:
            if _skip_timeout_retry(exc):
                raise
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
                stall_timeout=stall_timeout,
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
                    stall_timeout=stall_timeout,
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
        stall_timeout: int | None = None,
    ) -> tuple[str, str]:
        if use_rpc:
            return self._invoke_rpc_blocking(
                proc, cmd, prompt, timeout_secs, backend_name
            )
        if output_callback is not None:
            return self._invoke_streaming(
                proc,
                cmd,
                prompt,
                timeout_secs,
                backend_name,
                output_callback,
                stall_timeout=stall_timeout,
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
        stall_timeout: int | None = None,
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
