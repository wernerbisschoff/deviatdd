from __future__ import annotations

import contextvars
import json
from datetime import datetime, timezone
from pathlib import Path


class _LogSink:
    """A single writer sink — the shared per-run or per-task file.

    Multiple sinks can be active concurrently (one per task, plus the
    run-wide log). ``MultiSink`` dispatches to all of them; ``None``
    sinks are skipped, so callers can be wired up unconditionally.
    """

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Append so a re-run on the same task accumulates history
        # instead of overwriting the previous attempt's transcript.
        self._file = path.open("a", encoding="utf-8")

    def write(self, event: str, **kwargs: object) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        self._file.write(f"[{ts}] {event}\n")
        for k, v in kwargs.items():
            if isinstance(v, str) and "\n" in v:
                self._file.write(f"  {k}:\n")
                for line in v.split("\n"):
                    self._file.write(f"    {line}\n")
            else:
                self._file.write(f"  {k}: {v}\n")
        self._file.write("\n")
        self._file.flush()

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()


class RunLogger:
    """Per-run chronological log: ``.deviate/logs/run_<UTC>.log``.

    One file per ``deviate micro run`` invocation. Every task in the
    run appears in this file, in execution order — useful for a single
    end-to-end audit trail. For per-task transcripts, see
    :class:`TaskLogger`.
    """

    def __init__(self, root: Path) -> None:
        self.log_dir = root / ".deviate" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        self.log_file = self.log_dir / f"run_{timestamp}.log"
        self._sink = _LogSink(self.log_file)

    def log(self, event: str, **kwargs: object) -> None:
        self._sink.write(event, **kwargs)

    def close(self) -> None:
        self._sink.close()

    def __enter__(self) -> RunLogger:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class TaskLogger:
    """Per-task structured log: ``.deviate/logs/<issue_id>/<task_id>.log``.

    Append-mode: a re-run on the same task continues the file rather
    than overwriting the previous attempt, so a session spanning
    multiple ``micro run`` invocations accumulates a full transcript.
    """

    def __init__(self, root: Path, issue_id: str, task_id: str) -> None:
        if not issue_id or not task_id:
            raise ValueError(
                f"TaskLogger requires non-empty issue_id and task_id "
                f"(got issue_id={issue_id!r}, task_id={task_id!r})"
            )
        self.root = root
        self.issue_id = issue_id
        self.task_id = task_id
        self.log_dir = root / ".deviate" / "logs" / issue_id
        self.log_file = self.log_dir / f"{task_id}.log"
        self._sink = _LogSink(self.log_file)

    def log(self, event: str, **kwargs: object) -> None:
        self._sink.write(event, **kwargs)

    def close(self) -> None:
        self._sink.close()

    def __enter__(self) -> TaskLogger:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class _LogRegistry:
    """Holds the active run + task loggers and dispatches events to all.

    The micro layer sets one ``RunLogger`` per ``micro run`` invocation
    and one ``TaskLogger`` per task inside it. ``_log_run(event, ...)``
    dispatches to every active sink so a single ``INVOKE_AGENT`` call
    lands in both the chronological run log and the per-task transcript.
    """

    def __init__(self) -> None:
        self._run: RunLogger | None = None
        self._task: TaskLogger | None = None

    def set_run(self, logger: RunLogger | None) -> None:
        self._run = logger

    def set_task(self, logger: TaskLogger | None) -> None:
        self._task = logger

    def dispatch(self, event: str, **kwargs: object) -> None:
        if self._run is not None:
            self._run.log(event, **kwargs)
        if self._task is not None:
            self._task.log(event, **kwargs)


_current_log: contextvars.ContextVar[_LogRegistry] = contextvars.ContextVar(
    "_current_log", default=_LogRegistry()
)


def get_run_logger() -> RunLogger | None:
    """Return the active :class:`RunLogger`, or ``None`` if unset.

    Retained for back-compat with callers that touch the run log
    directly. New code should call :func:`log_event` so the dispatch
    reaches both run and task sinks.
    """
    return _current_log.get()._run


def set_run_logger(logger: RunLogger | None) -> None:
    """Register or clear the active :class:`RunLogger`.

    Equivalent to the prior single-logger behaviour — sets only the
    run sink, leaves the task sink untouched. Use :func:`set_task_logger`
    alongside this for the full registry.
    """
    _current_log.get().set_run(logger)


def set_task_logger(logger: TaskLogger | None) -> None:
    """Register or clear the active :class:`TaskLogger`."""
    _current_log.get().set_task(logger)


def get_task_logger() -> TaskLogger | None:
    """Return the active :class:`TaskLogger`, or ``None`` if unset."""
    return _current_log.get()._task


def log_event(event: str, **kwargs: object) -> None:
    """Dispatch an event to every active sink (run + task)."""
    _current_log.get().dispatch(event, **kwargs)


def verdicts_log_path(root: Path, issue_id: str, task_id: str) -> Path:
    """Per-task JUDGE postmortem file: ``.deviate/logs/<issue>/<task>.verdicts.jsonl``."""
    return root / ".deviate" / "logs" / issue_id / f"{task_id}.verdicts.jsonl"


def append_verdicts_record(
    root: Path,
    issue_id: str,
    task_id: str,
    record: dict[str, object],
) -> None:
    """Append one JSON object to the per-task verdicts JSONL.

    Skips the write when ``issue_id`` or ``task_id`` is missing so a
    half-resolved task never creates ``.deviate/logs//?.verdicts.jsonl``.
    Does not go through :class:`_LogSink` — this file is JSONL, not the
    ``[<ts>] EVENT`` transcript format. Never store prompts or
    ``AGENT_RAW_OUTPUT`` here.
    """
    if not issue_id or not task_id or task_id == "?":
        return
    path = verdicts_log_path(root, issue_id, task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def read_verdicts_records(
    root: Path, issue_id: str, task_id: str
) -> list[dict[str, object]]:
    """Parse the per-task verdicts JSONL, skipping blank lines."""
    path = verdicts_log_path(root, issue_id, task_id)
    if not path.exists():
        return []
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if isinstance(row, dict):
            records.append(row)
    return records


def raw_sidecar_dir(root: Path, issue_id: str, task_id: str) -> Path:
    """Directory for verbatim agent stdout: ``<task>.raw/``."""
    return root / ".deviate" / "logs" / issue_id / f"{task_id}.raw"


def next_raw_sidecar_path(root: Path, issue_id: str, task_id: str, phase: str) -> Path:
    """Return ``<task>.raw/<phase>-<n>.log`` for the next invoke of *phase*."""
    raw_dir = raw_sidecar_dir(root, issue_id, task_id)
    raw_dir.mkdir(parents=True, exist_ok=True)
    slug = (phase or "agent").strip().lower() or "agent"
    slug = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in slug)
    n = 1
    while (raw_dir / f"{slug}-{n}.log").exists():
        n += 1
    return raw_dir / f"{slug}-{n}.log"


def write_raw_sidecar(
    root: Path,
    issue_id: str,
    task_id: str,
    phase: str,
    *,
    stdout: str,
    prompt: str = "",
) -> Path | None:
    """Write verbatim agent stdout (and optional prompt) next to the transcript.

    Returns the stdout sidecar path, or ``None`` when ids are missing.
    Does not write into the run/task transcript.
    """
    if not issue_id or not task_id or task_id == "?":
        return None
    path = next_raw_sidecar_path(root, issue_id, task_id, phase)
    path.write_text(stdout, encoding="utf-8")
    if prompt:
        prompt_path = path.with_name(f"{path.stem}.prompt.log")
        prompt_path.write_text(prompt, encoding="utf-8")
    return path
