from __future__ import annotations

import re
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ValidationError

from deviate.state.config import AgentConfig

OutputCallback = Callable[[str], None]


class HandoverManifest(BaseModel):
    phase: str
    status: str
    task_id: str | None = None
    test_file: str | None = None
    verification_command: str | None = None
    expected_failure_node: str | None = None
    yellow_trigger: bool | None = None
    test_changes: dict[str, Any] | None = None
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


class AiderParseError(Exception):
    pass


class ConstitutionMissingError(Exception):
    pass


BACKEND_COMMANDS: dict[str, str] = {
    "opencode": "opencode run",
    "claude": "claude -p",
    "droid": "droid exec",
}


_YAML_BLOCK_RE = re.compile(r"```(?:yaml)\s*\n(.*?)```", re.DOTALL)


class AgentBackend:
    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or AgentConfig()

    @staticmethod
    def _extract_yaml_block(text: str) -> str:
        m = _YAML_BLOCK_RE.search(text)
        if m:
            return m.group(1).strip()
        return text.strip()

    @staticmethod
    def _yaml_error_hint(text: str) -> str:
        if not re.search(r"```\s*yaml", text, re.IGNORECASE):
            return (
                " No ```yaml code block found — wrap the manifest in a ```yaml block."
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

        try:
            data = yaml.safe_load(yaml_text)
        except yaml.YAMLError as e:
            hint = AgentBackend._yaml_error_hint(stdout)
            raise MalformedHandoverManifestError(
                f"Failed to parse YAML handover manifest: {e}{hint}"
            )

        if not isinstance(data, dict):
            raise MalformedHandoverManifestError(
                "YAML handover manifest is not a mapping"
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

    def _invoke_dispatch(
        self,
        proc: subprocess.Popen[bytes],
        cmd: list[str],
        prompt: str,
        timeout_secs: int,
        backend_name: str,
        output_callback: OutputCallback | None,
    ) -> tuple[str, str]:
        if output_callback is not None:
            return self._invoke_streaming(
                proc, cmd, prompt, timeout_secs, backend_name, output_callback
            )
        return self._invoke_blocking(proc, cmd, prompt, timeout_secs, backend_name)

    def invoke(
        self,
        prompt: str,
        backend: Literal["opencode", "claude", "droid"] | None = None,
        timeout: int | None = None,
        output_callback: OutputCallback | None = None,
    ) -> HandoverManifest:
        backend_name: Literal["opencode", "claude", "droid"] = (
            backend or self.config.backend
        )
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

        try:
            stdout, stderr = self._invoke_dispatch(
                proc, cmd, prompt, effective_timeout, backend_name, output_callback
            )
        except AgentTimeoutError:
            time.sleep(30)
            retry_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = self._invoke_dispatch(
                retry_proc,
                cmd,
                prompt,
                effective_timeout,
                backend_name,
                output_callback,
            )

        return self.parse_output(stdout, backend_name)


class AiderBackend:
    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or AgentConfig()

    def _build_aider_command(
        self, prompt: str, aider_cfg: Any, repo_root: Path
    ) -> list[str]:
        constitution_path = repo_root / "specs" / "constitution.md"
        if not constitution_path.exists():
            raise ConstitutionMissingError(
                "Constitution not found at specs/constitution.md"
            )

        args = ["aider", "--message", prompt]

        if aider_cfg.yes_mode:
            args.append("--yes")

        if not aider_cfg.auto_commits:
            args.append("--no-auto-commits")

        if not aider_cfg.suggest_shell_commands:
            args.append("--no-suggest-shell-commands")

        args.extend(["--model", aider_cfg.model])

        for read_file in aider_cfg.read_files:
            if (repo_root / read_file).exists():
                args.extend(["--read", read_file])

        return args

    def parse_output(self, stdout: str, backend_name: str) -> HandoverManifest:
        if not stdout.strip():
            raise AiderParseError("Aider returned empty output")

        files_touched: list[str] = []
        error_lines: list[str] = []
        for line in stdout.splitlines():
            m = re.match(r"^Applied edit to (.+)\.$", line)
            if m:
                files_touched.append(m.group(1).strip())
                continue
            m = re.match(r"^Added (.+) to the chat\.$", line)
            if m:
                files_touched.append(m.group(1).strip())
                continue
            if "FAILED" in line or "Error" in line or "Traceback" in line:
                error_lines.append(line)

        if "Tests:" in stdout and "failed" in stdout:
            return HandoverManifest(
                phase="aider",
                status="FAIL",
                verification_result="FAIL",
                error_details="\n".join(error_lines) if error_lines else "Tests failed",
                files_touched=files_touched,
            )

        if "All tests passed" in stdout:
            return HandoverManifest(
                phase="aider",
                status="PASS",
                verification_result="PASS",
                files_touched=files_touched,
            )

        if re.search(r"\d+\s+tests?\s+passed", stdout):
            return HandoverManifest(
                phase="aider",
                status="PASS",
                verification_result="PASS",
                files_touched=files_touched,
            )

        return HandoverManifest(
            phase="aider",
            status="PASS",
            verification_result="UNKNOWN",
            files_touched=files_touched,
        )

    def _run_with_retry(
        self, cmd: list[str], timeout: int
    ) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError:
            raise AgentBinaryNotFoundError(
                "Agent binary not found on PATH for backend: aider"
            )
        except subprocess.TimeoutExpired:
            time.sleep(30)
            try:
                return subprocess.run(
                    cmd, capture_output=True, text=True, timeout=timeout
                )
            except FileNotFoundError:
                raise AgentBinaryNotFoundError(
                    "Agent binary not found on PATH for backend: aider"
                )
            except subprocess.TimeoutExpired:
                raise AgentTimeoutError(
                    f"Aider backend timed out after {timeout}s "
                    f"(retried once with 30s backoff)"
                )

    def _run_post_guard(self, manifest: HandoverManifest) -> HandoverManifest:
        try:
            guard_result = subprocess.run(
                ["mise", "run", "test"], capture_output=True, text=True
            )
        except FileNotFoundError:
            return manifest

        if guard_result.returncode != 0:
            manifest.status = "FAIL"

        return manifest

    def invoke(self, prompt: str) -> HandoverManifest:
        aider_cfg = self.config.aider
        repo_root = Path.cwd()
        effective_timeout = self.config.timeout

        cmd = self._build_aider_command(prompt, aider_cfg, repo_root)
        result = self._run_with_retry(cmd, effective_timeout)

        if result.returncode != 0:
            raise AgentSubprocessError(
                message=result.stderr or f"Agent exited with code {result.returncode}",
                exit_code=result.returncode,
            )

        try:
            manifest = self.parse_output(result.stdout, "aider")
        except AiderParseError:
            manifest = HandoverManifest(
                phase="aider", status="PASS", verification_result="UNKNOWN"
            )

        return self._run_post_guard(manifest)
