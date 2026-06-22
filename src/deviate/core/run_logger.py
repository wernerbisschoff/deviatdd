from __future__ import annotations

import contextvars
from datetime import datetime, timezone
from pathlib import Path


_current_run_log: contextvars.ContextVar[RunLogger | None] = contextvars.ContextVar(
    "_current_run_log", default=None
)


def get_run_logger() -> RunLogger | None:
    return _current_run_log.get()


def set_run_logger(logger: RunLogger | None) -> None:
    _current_run_log.set(logger)


class RunLogger:
    def __init__(self, root: Path) -> None:
        self.log_dir = root / ".deviate" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        self.log_file = self.log_dir / f"run_{timestamp}.log"
        self._file = self.log_file.open("w", encoding="utf-8")

    def log(self, event: str, **kwargs: object) -> None:
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

    def __enter__(self) -> RunLogger:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
