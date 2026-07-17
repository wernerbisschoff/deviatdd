from __future__ import annotations

import contextvars
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


def log_event(event: str, **kwargs: object) -> None:
    """Dispatch an event to every active sink (run + task)."""
    _current_log.get().dispatch(event, **kwargs)
