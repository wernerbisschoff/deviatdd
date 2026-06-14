from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class MarkdownStatus(str, Enum):
    PENDING = "[ ]"
    IN_PROGRESS = "[/]"
    COMPLETED = "[X]"
    FAILED = "[✗]"


VALID_EVENT_TYPES = frozenset(
    {
        "task_started",
        "phase_change",
        "task_completed",
        "task_failed",
        "pipeline_complete",
        "agent_output",
    }
)


@dataclass
class TaskStatus:
    id: str
    description: str
    marker: MarkdownStatus = MarkdownStatus.PENDING
    phase: str = ""
    error_reason: str | None = None


class OrchestrationMonitor:
    def __init__(self, console: Any, *, json_mode: bool = False) -> None:
        self._console = console
        self._json_mode = json_mode
        self._tasks: dict[str, TaskStatus] = {}
        self._interrupted = False
        self._exited = False
        self.display_active = False
        self._dispatch: dict[str, Any] = {
            "task_started": self._on_task_started,
            "phase_change": self._on_phase_change,
            "task_completed": self._on_task_completed,
            "task_failed": self._on_task_failed,
            "pipeline_complete": self._on_pipeline_complete,
        }

    def __enter__(self) -> OrchestrationMonitor:
        self._exited = False
        self.display_active = True
        return self

    def __exit__(self, *args: Any) -> None:
        if self._exited:
            return
        self._exited = True
        self.display_active = False

    def _validate_event(self, event_type: str) -> None:
        if event_type not in VALID_EVENT_TYPES:
            raise ValueError(f"Unknown event type: {event_type}")

    @staticmethod
    def _resolve_task_id(data: dict[str, Any]) -> str:
        return data.get("id", data.get("task_id", ""))

    def push_event(self, event_type: str, **data: Any) -> None:
        self._validate_event(event_type)
        handler = self._dispatch.get(event_type)
        if handler is not None:
            handler(data)

    def _on_task_started(self, data: dict[str, Any]) -> None:
        task_id = self._resolve_task_id(data)
        if (
            task_id in self._tasks
            and self._tasks[task_id].marker is not MarkdownStatus.PENDING
        ):
            return
        self._tasks[task_id] = TaskStatus(
            id=task_id,
            description=data.get("description", ""),
            marker=MarkdownStatus.IN_PROGRESS,
            phase=data.get("phase", ""),
        )

    def _on_phase_change(self, data: dict[str, Any]) -> None:
        task_id = self._resolve_task_id(data)
        if task_id not in self._tasks:
            self._tasks[task_id] = TaskStatus(
                id=task_id,
                description=data.get("description", ""),
                marker=MarkdownStatus.PENDING,
                phase=data.get("phase", ""),
            )
            return
        self._tasks[task_id].phase = data.get("phase", "")
        if self._tasks[task_id].marker is MarkdownStatus.PENDING:
            self._tasks[task_id].marker = MarkdownStatus.IN_PROGRESS

    def _on_task_completed(self, data: dict[str, Any]) -> None:
        task_id = self._resolve_task_id(data)
        if task_id not in self._tasks:
            self._tasks[task_id] = TaskStatus(
                id=task_id,
                description=data.get("description", ""),
                marker=MarkdownStatus.COMPLETED,
                phase=data.get("phase", ""),
            )
            return
        self._tasks[task_id].marker = MarkdownStatus.COMPLETED
        self._tasks[task_id].phase = data.get("phase", self._tasks[task_id].phase)

    def _on_task_failed(self, data: dict[str, Any]) -> None:
        task_id = self._resolve_task_id(data)
        if task_id not in self._tasks:
            self._tasks[task_id] = TaskStatus(
                id=task_id,
                description=data.get("description", ""),
                marker=MarkdownStatus.FAILED,
                error_reason=data.get("error_reason", ""),
                phase=data.get("phase", ""),
            )
            return
        self._tasks[task_id].marker = MarkdownStatus.FAILED
        self._tasks[task_id].error_reason = data.get("error_reason", "")
        self._tasks[task_id].phase = data.get("phase", self._tasks[task_id].phase)

    def _on_pipeline_complete(self, data: dict[str, Any]) -> None:
        self.display_active = False

    def signal_keyboard_interrupt(self) -> None:
        self._interrupted = True
        for task in self._tasks.values():
            if task.marker is MarkdownStatus.IN_PROGRESS:
                task.marker = MarkdownStatus.FAILED

    @property
    def interrupted(self) -> bool:
        return self._interrupted

    def render(self) -> None:
        """Delegate to render functions. Stub for Phase 2 integration."""
