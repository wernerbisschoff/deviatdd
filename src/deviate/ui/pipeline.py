"""Pipeline UI components for `deviate meso run` and `deviate micro run --all`.

Aesthetic: "Editorial / Refined Engineering" — restrained palette, Unicode
box-drawing, monospace tabular layout. Designed for senior engineers who
live in the CLI; no playful/decorative elements, no gradient colour noise.

Components
----------

* :class:`PipelineBanner` — opening banner for the meso pipeline.
* :class:`PhaseCallout`   — per-phase single-task output (RED/GREEN/JUDGE/REFACTOR/EXECUTE).
* :class:`RunBoard`       — live-updating multi-row task table for `run --all`.
* :class:`TrainIndicator` — visual train-retry counter (1/3 -> 2/3 -> 3/3).
* :class:`PipelineSummary` — closing summary panel.

Token-preservation contract: every literal token the existing test suite
asserts against (``RED``, ``GREEN``, ``COMPLETED``, ``JUDGE_REJECTED``,
``TRAIN``, ``DISCOVERED``, ``MESO``, ``INVOKE_AGENT``, ``IDLE``, etc.)
must remain in the rendered string output. Wrapping in `Panel`/`Rule` is
fine; dropping or rewriting the tokens is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from rich.console import Group, RenderableType
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# (style, glyph) per TDD phase. Used by PhaseCallout, RunBoard, banner.
PHASE_STYLES: dict[str, tuple[str, str]] = {
    "RED": ("bold blue", "R"),
    "GREEN": ("bold green", "G"),
    "JUDGE": ("bold magenta", "J"),
    "REFACTOR": ("bold cyan", "F"),
    "EXECUTE": ("bold green", "E"),
    "SPECIFY": ("bold yellow", "S"),
    "PLAN": ("bold cyan", "P"),
    "TASKS": ("bold blue", "T"),
}
G_PENDING = "\u25cb"  # ○
G_IN_PROGRESS = "\u25d0"  # ◐
G_COMPLETED = "\u25cf"  # ●
G_FAILED = "\u2717"  # ✗
G_SKIPPED = "\u2298"  # ⊘
G_ARROW = "\u25b6"  # ▶
G_DASH = "\u2500"  # ─


# ---------------------------------------------------------------------------
# PhaseMarker
# ---------------------------------------------------------------------------


class PhaseMarker(str, Enum):
    """Visual marker for a single phase / task progress slot."""

    PENDING = G_PENDING
    IN_PROGRESS = G_IN_PROGRESS
    COMPLETED = G_COMPLETED
    FAILED = G_FAILED
    SKIPPED = G_SKIPPED


# ---------------------------------------------------------------------------
# format_duration
# ---------------------------------------------------------------------------


def format_duration(seconds: float) -> str:
    """Render *seconds* as a human-readable duration string.

    Examples
    --------
    >>> format_duration(0.0)
    '0.0s'
    >>> format_duration(12.345)
    '12.3s'
    >>> format_duration(83.0)
    '1m 23s'
    >>> format_duration(3725.0)
    '1h 2m 5s'
    """
    if seconds < 0:
        seconds = 0.0
    total = int(seconds)
    hundredths = int(round((seconds - total) * 10))
    if hundredths == 10:
        total += 1
        hundredths = 0
    if total < 60:
        return f"{total}.{hundredths}s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}m {secs}s"


# ---------------------------------------------------------------------------
# PipelineBanner
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PipelineBanner:
    """Framed opening banner for the meso pipeline.

    Renders the issue context (id, title, slug) and a horizontal step
    indicator (SPECIFY -> PLAN -> TASKS) inside a single panel.
    """

    issue_id: str
    issue_title: str
    epic_slug: str
    issue_slug: str
    steps: tuple[str, ...] = ("SPECIFY", "PLAN", "TASKS")
    pipeline_label: str = "MESO"

    def render(self) -> RenderableType:
        header = Text()
        header.append(self.pipeline_label, style="bold blue")
        header.append("  ", style="dim")
        header.append(self.issue_id, style="bold")
        header.append("  ", style="dim")
        header.append(self.issue_title, style="default")

        meta = Text()
        meta.append(f"epic: {self.epic_slug}", style="dim")
        meta.append("    ", style="dim")
        meta.append(f"issue: {self.issue_slug}", style="dim")

        steps = Text()
        for i, step in enumerate(self.steps):
            if i:
                steps.append("  " + G_ARROW + "  ", style="dim")
            steps.append(step, style="bold cyan")

        body = Group(
            header,
            meta,
            Text(""),
            steps,
        )
        return Panel(
            body,
            border_style="blue",
            padding=(0, 2),
        )


# ---------------------------------------------------------------------------
# PhaseCallout
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PhaseCallout:
    """Per-phase single-task output (RED / GREEN / JUDGE / REFACTOR / EXECUTE).

    Renders as a tight panel with a phase-tag header, the task id and
    description, an optional duration footer, and a marker indicating the
    outcome (pending / in progress / completed / failed / skipped).
    """

    phase: str
    task_id: str
    task_description: str = ""

    def render(
        self,
        status: PhaseMarker = PhaseMarker.IN_PROGRESS,
        duration_seconds: float | None = None,
        note: str = "",
    ) -> RenderableType:
        style, glyph = PHASE_STYLES.get(self.phase, ("bold", "?"))

        marker = Text(status.value)
        marker.style = {
            PhaseMarker.PENDING: "dim",
            PhaseMarker.IN_PROGRESS: "bold yellow",
            PhaseMarker.COMPLETED: "bold green",
            PhaseMarker.FAILED: "bold red",
            PhaseMarker.SKIPPED: "dim",
        }[status]

        header = Text()
        header.append("  ")
        header.append(marker)
        header.append("  ")
        header.append(self.phase, style=style)
        header.append(f"  {G_DASH}  ", style="dim")
        header.append(glyph, style=style)
        header.append(f"  {G_DASH}  ", style="dim")
        header.append(self.task_id, style="bold")

        body = Text()
        if self.task_description:
            body.append(self.task_description)
        if note:
            if body.plain:
                body.append("\n")
            body.append(note, style="dim")

        footer: Text | None = None
        if duration_seconds is not None:
            footer = Text()
            footer.append("elapsed: ", style="dim")
            footer.append(format_duration(duration_seconds))

        if footer is not None:
            content: list[RenderableType] = [header, body, Text(""), footer]
        else:
            content = [header, body]

        return Panel(
            Group(*content),
            border_style={
                PhaseMarker.PENDING: "dim",
                PhaseMarker.IN_PROGRESS: "yellow",
                PhaseMarker.COMPLETED: "green",
                PhaseMarker.FAILED: "red",
                PhaseMarker.SKIPPED: "dim",
            }[status],
            padding=(0, 1),
        )


# ---------------------------------------------------------------------------
# RunBoard
# ---------------------------------------------------------------------------


@dataclass
class RunBoard:
    """Live, multi-row task table for `deviate micro run --all`.

    Each row corresponds to a PENDING task. The board is updated in place
    by ``mark_phase`` / ``mark_completed`` / ``mark_failed``; the same
    instance can be wrapped in a ``rich.live.Live`` to get a refreshing
    display.
    """

    pending: list[dict]
    title: str = "Pipeline"

    _rows: dict[str, PhaseMarker] = field(default_factory=dict)
    _phases: dict[str, str] = field(default_factory=dict)
    _errors: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for task in self.pending:
            tid = task.get("id", "")
            if tid:
                self._rows[tid] = PhaseMarker.PENDING

    def mark_phase(self, task_id: str, phase: str) -> None:
        """Update a task's marker to IN_PROGRESS and remember the current phase."""
        if task_id not in self._rows:
            return
        # Don't downgrade a failed task.
        if self._rows[task_id] is PhaseMarker.FAILED:
            return
        self._rows[task_id] = PhaseMarker.IN_PROGRESS
        self._phases[task_id] = phase

    def mark_completed(self, task_id: str) -> None:
        if task_id not in self._rows:
            return
        self._rows[task_id] = PhaseMarker.COMPLETED
        self._phases[task_id] = "COMPLETED"

    def mark_failed(self, task_id: str, reason: str = "") -> None:
        if task_id not in self._rows:
            return
        self._rows[task_id] = PhaseMarker.FAILED
        self._errors[task_id] = reason

    @property
    def completed_count(self) -> int:
        return sum(1 for m in self._rows.values() if m is PhaseMarker.COMPLETED)

    @property
    def failed_count(self) -> int:
        return sum(1 for m in self._rows.values() if m is PhaseMarker.FAILED)

    def render(self) -> RenderableType:
        table = Table(
            title=Text(self.title, style="bold blue"),
            show_header=True,
            header_style="bold",
            border_style="blue",
            expand=True,
        )
        table.add_column("", width=2, no_wrap=True)
        table.add_column("TASK", style="bold cyan", no_wrap=True)
        table.add_column("DESCRIPTION", ratio=1)
        table.add_column("PHASE", style="magenta", width=10)
        table.add_column("STATUS", width=12)

        for task in self.pending:
            tid = task.get("id", "?")
            desc = task.get("description", "").strip()
            marker = self._rows.get(tid, PhaseMarker.PENDING)
            phase = self._phases.get(tid, "")
            error = self._errors.get(tid, "")

            marker_text = Text(marker.value)
            marker_text.style = {
                PhaseMarker.PENDING: "dim",
                PhaseMarker.IN_PROGRESS: "bold yellow",
                PhaseMarker.COMPLETED: "bold green",
                PhaseMarker.FAILED: "bold red",
                PhaseMarker.SKIPPED: "dim",
            }[marker]

            display_desc = desc
            if marker is PhaseMarker.FAILED and error:
                display_desc = f"{desc}  --  {error}"
            status_text = Text(marker.name.replace("_", " "))
            status_text.style = {
                PhaseMarker.PENDING: "dim",
                PhaseMarker.IN_PROGRESS: "yellow",
                PhaseMarker.COMPLETED: "green",
                PhaseMarker.FAILED: "red",
                PhaseMarker.SKIPPED: "dim",
            }[marker]

            table.add_row(
                marker_text,
                tid,
                display_desc,
                phase,
                status_text,
            )

        # Footer with running counts.
        total = len(self.pending)
        done = self.completed_count
        failed = self.failed_count
        in_progress = sum(
            1 for m in self._rows.values() if m is PhaseMarker.IN_PROGRESS
        )
        pending_count = total - done - failed - in_progress

        footer = Text()
        footer.append(f"{done}/{total} done", style="bold green")
        footer.append("  " + G_DASH + "  ", style="dim")
        footer.append(f"{in_progress} active", style="yellow")
        footer.append("  " + G_DASH + "  ", style="dim")
        footer.append(f"{pending_count} pending", style="dim")
        if failed:
            footer.append("  " + G_DASH + "  ", style="dim")
            footer.append(f"{failed} failed", style="bold red")

        return Group(table, Padding(footer, (0, 0, 0, 2)))


# ---------------------------------------------------------------------------
# TrainIndicator
# ---------------------------------------------------------------------------


class TrainIndicator:
    """Visual train-retry counter for the Green -> Judge -> Green loop.

    Renders a sequential progression bar with the current attempt
    highlighted. Always emits the literal token ``TRAIN`` so the existing
    test suite (``assert "TRAIN" in result.output``) keeps passing.
    """

    @staticmethod
    def render(attempt: int, maximum: int, phase: str = "GREEN") -> RenderableType:
        # Existing tests expect "1/3", "2/3", "3/3" to be present.
        cells: list[Text] = []
        for n in range(1, maximum + 1):
            cell = Text()
            if n < attempt:
                cell.append(f" {G_COMPLETED} {n}/{maximum} ", style="bold green")
            elif n == attempt:
                cell.append(f" {G_IN_PROGRESS} {n}/{maximum} ", style="bold yellow")
            else:
                cell.append(f" {G_PENDING} {n}/{maximum} ", style="dim")
            cells.append(cell)
            if n < maximum:
                cells.append(Text("  " + G_DASH + G_ARROW + G_DASH + "  ", style="dim"))

        header = Text()
        header.append("TRAIN", style="bold yellow")
        header.append(f"  {G_DASH}  re-running ", style="dim")
        header.append(phase, style="bold green")
        header.append(" with feedback", style="dim")

        return Group(header, Text(""), *cells)


# ---------------------------------------------------------------------------
# PipelineSummary
# ---------------------------------------------------------------------------


class PipelineSummary:
    """Closing summary panel for a run --all or meso run pipeline.

    Renders a small table of totals plus a footer line that defaults to
    the literal ``MESO pipeline complete - session at IDLE`` (preserved for
    the existing test suite).
    """

    @staticmethod
    def render(
        total: int,
        completed: int,
        failed: int,
        duration_seconds: float,
        pipeline_status: str,
        include_meso_footer: bool = False,
    ) -> RenderableType:
        table = Table(
            show_header=False,
            border_style="blue",
            expand=False,
            padding=(0, 2),
        )
        table.add_column("KEY", style="dim")
        table.add_column("VALUE", style="bold")

        status_style = {
            "completed": "bold green",
            "halted": "bold red",
            "interrupted": "bold yellow",
        }.get(pipeline_status, "bold")

        table.add_row("Total tasks", str(total))
        table.add_row("Completed", str(completed))
        table.add_row("Failed", str(failed))
        table.add_row("Duration", format_duration(duration_seconds))
        table.add_row(
            Text("Status", style="dim"),
            Text(pipeline_status, style=status_style),
        )

        body: list[RenderableType] = [table]
        if include_meso_footer:
            footer = Text()
            footer.append("MESO", style="bold green")
            footer.append(" pipeline complete - session at ", style="default")
            footer.append("IDLE", style="bold blue")
            body.append(Text(""))
            body.append(footer)

        return Group(*body)
