from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from typing import Any

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from deviate.ui.monitor import TaskStatus


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate_line(line: str, width: int | None = None) -> str:
    if width is None:
        width = shutil.get_terminal_size().columns
    if width < 1:
        width = 80
    if len(line) <= width:
        return line
    return line[: width - 1] + "\u2026"


def build_task_table(tasks: list[TaskStatus]) -> Table:
    table = Table(show_header=True)
    table.add_column("Marker", no_wrap=True)
    table.add_column("ID", no_wrap=True)
    table.add_column("Description")
    for task in tasks:
        table.add_row(task.marker.value, task.id, task.description)
    return table


def render_agent_buffer(lines: list[str]) -> Panel:
    recent = lines[-5:]
    if not recent:
        return Panel(Text("(awaiting output)"))
    renderables = [Text(_truncate_line(line)) for line in recent]
    return Panel(Group(*renderables))


def render_status_bar(current: int, total: int, phase: str) -> str:
    return f"Task {current} of {total} \u2014 Phase: {phase}"


def emit_jsonl(event: str, **fields: Any) -> None:
    data = {"event": event, "timestamp": _now_iso(), **fields}
    sys.stdout.write(json.dumps(data) + "\n")
    sys.stdout.flush()


def is_interactive() -> bool:
    if os.environ.get("CI"):
        return False
    try:
        return os.isatty(sys.stdout.fileno())
    except (OSError, AttributeError):
        return False


def compose_display(
    tasks: list[TaskStatus],
    buffer_lines: list[str],
    current: int,
    total: int,
    phase: str,
) -> Group:
    return Group(
        build_task_table(tasks),
        render_agent_buffer(buffer_lines),
        Text(render_status_bar(current, total, phase)),
    )
