"""Tests for the new pipeline UI components.

These components power the redesigned output of `deviate meso run` and
`deviate micro run --all`. The aesthetic is "Editorial / Refined Engineering":
restrained palette, Unicode box-drawing, monospace tabular layout.

The tests pin the visual contract:

* PipelineBanner      - framed opening for the meso run
* PhaseCallout        - per-phase single-task output (RED/GREEN/JUDGE/REFACTOR/EXECUTE)
* RunBoard            - live-updating task table for `run --all`
* TrainIndicator      - visual train-retry counter
* PipelineSummary     - closing summary panel

Token-preservation contract: every literal token the existing test suite
asserts against (RED, GREEN, COMPLETED, JUDGE_REJECTED, TRAIN, DISCOVERED,
MESO, INVOKE_AGENT, IDLE, etc.) must remain in the rendered string output.
"""

from __future__ import annotations

import io

import pytest
from rich.console import Console

from deviate.ui.pipeline import (
    PHASE_STYLES,
    G_ARROW,
    G_COMPLETED,
    G_DASH,
    G_FAILED,
    G_IN_PROGRESS,
    G_PENDING,
    G_SKIPPED,
    PhaseCallout,
    PhaseMarker,
    PipelineBanner,
    PipelineSummary,
    RunBoard,
    TrainIndicator,
    format_duration,
)


@pytest.fixture
def captured_console():
    buf = io.StringIO()
    return Console(file=buf, width=120, force_terminal=False, soft_wrap=False), buf


class TestFormatDuration:
    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            (0.0, "0.0s"),
            (0.4, "0.4s"),
            (12.345, "12.3s"),
            (59.4, "59.4s"),
            (60.0, "1m 0s"),
            (83.0, "1m 23s"),
            (3725.0, "1h 2m 5s"),
        ],
    )
    def test_format_duration(self, seconds, expected):
        assert format_duration(seconds) == expected


class TestPhaseMarker:
    def test_phase_marker_is_str_enum(self):
        for marker in PhaseMarker:
            assert isinstance(marker.value, str)

    @pytest.mark.parametrize(
        ("marker", "expected"),
        [
            (PhaseMarker.PENDING, G_PENDING),
            (PhaseMarker.IN_PROGRESS, G_IN_PROGRESS),
            (PhaseMarker.COMPLETED, G_COMPLETED),
            (PhaseMarker.FAILED, G_FAILED),
            (PhaseMarker.SKIPPED, G_SKIPPED),
        ],
    )
    def test_phase_marker_glyphs(self, marker, expected):
        assert marker.value == expected


class TestPhaseStyles:
    @pytest.mark.parametrize("phase", ["RED", "GREEN", "JUDGE", "REFACTOR", "EXECUTE"])
    def test_phase_styles_cover_all_phases(self, phase):
        assert phase in PHASE_STYLES
        style, _ = PHASE_STYLES[phase]
        assert isinstance(style, str)
        assert style


class TestPipelineBanner:
    def test_banner_contains_issue_id(self, captured_console):
        console, buf = captured_console
        banner = PipelineBanner(
            issue_id="ISS-001-007",
            issue_title="Add user authentication via OAuth2",
            epic_slug="007-auth",
            issue_slug="iss-001-007",
            steps=("SPECIFY", "PLAN", "TASKS"),
        )
        console.print(banner.render())
        text = buf.getvalue()
        assert "ISS-001-007" in text
        assert "Add user authentication via OAuth2" in text

    def test_banner_contains_all_step_labels(self, captured_console):
        console, buf = captured_console
        banner = PipelineBanner(
            issue_id="ISS-001-007",
            issue_title="Auth",
            epic_slug="auth",
            issue_slug="iss-007",
            steps=("SPECIFY", "PLAN", "TASKS"),
        )
        console.print(banner.render())
        text = buf.getvalue()
        for step in ("SPECIFY", "PLAN", "TASKS"):
            assert step in text, f"Step {step!r} missing from banner"

    def test_banner_uses_box_drawing(self, captured_console):
        console, buf = captured_console
        banner = PipelineBanner(
            issue_id="ISS-001-007",
            issue_title="Auth",
            epic_slug="auth",
            issue_slug="iss-007",
            steps=("SPECIFY", "PLAN", "TASKS"),
        )
        console.print(banner.render())
        text = buf.getvalue()
        for char in ("\u256d", "\u2570", "\u2502", "\u2500"):
            assert char in text, f"Box-drawing char {char!r} missing"

    def test_banner_uses_step_arrow(self, captured_console):
        console, buf = captured_console
        banner = PipelineBanner(
            issue_id="ISS-001-007",
            issue_title="Auth",
            epic_slug="auth",
            issue_slug="iss-007",
            steps=("SPECIFY", "PLAN", "TASKS"),
        )
        console.print(banner.render())
        assert G_ARROW in buf.getvalue()

    def test_banner_preserves_meso_token(self, captured_console):
        console, buf = captured_console
        banner = PipelineBanner(
            issue_id="ISS-001-007",
            issue_title="Auth",
            epic_slug="auth",
            issue_slug="iss-007",
            steps=("SPECIFY", "PLAN", "TASKS"),
        )
        console.print(banner.render())
        assert "MESO" in buf.getvalue()


class TestPhaseCallout:
    @pytest.mark.parametrize(
        "phase",
        [
            "RED",
            "GREEN",
            "JUDGE",
            "REFACTOR",
            "EXECUTE",
            "SPECIFY",
            "PLAN",
            "TASKS",
        ],
    )
    def test_callout_contains_phase_and_task(self, captured_console, phase):
        console, buf = captured_console
        callout = PhaseCallout(
            phase=phase,
            task_id="TSK-007-01",
            task_description="Write a failing test for token verification",
        )
        console.print(callout.render(status=PhaseMarker.IN_PROGRESS))
        text = buf.getvalue()
        assert phase in text
        assert "TSK-007-01" in text

    def test_callout_renders_in_progress_marker(self, captured_console):
        console, buf = captured_console
        callout = PhaseCallout(
            phase="RED", task_id="TSK-007-01", task_description="Token test"
        )
        console.print(callout.render(status=PhaseMarker.IN_PROGRESS))
        assert G_IN_PROGRESS in buf.getvalue()

    def test_callout_renders_completed_marker(self, captured_console):
        console, buf = captured_console
        callout = PhaseCallout(
            phase="GREEN", task_id="TSK-007-01", task_description="Implement"
        )
        console.print(callout.render(status=PhaseMarker.COMPLETED))
        assert G_COMPLETED in buf.getvalue()

    def test_callout_renders_failed_marker(self, captured_console):
        console, buf = captured_console
        callout = PhaseCallout(
            phase="JUDGE", task_id="TSK-007-01", task_description="Verify"
        )
        console.print(callout.render(status=PhaseMarker.FAILED))
        assert G_FAILED in buf.getvalue()

    def test_callout_includes_duration_when_provided(self, captured_console):
        console, buf = captured_console
        callout = PhaseCallout(
            phase="GREEN", task_id="TSK-007-01", task_description="Implement"
        )
        console.print(
            callout.render(status=PhaseMarker.COMPLETED, duration_seconds=12.3)
        )
        assert "12.3s" in buf.getvalue()

    def test_callout_preserves_red_green_tokens(self, captured_console):
        console, buf = captured_console
        callout = PhaseCallout(
            phase="RED", task_id="TSK-007-01", task_description="Write failing test"
        )
        console.print(callout.render(status=PhaseMarker.COMPLETED))
        assert "RED" in buf.getvalue()


class TestRunBoard:
    def _make_pending(self, tid, desc):
        return {
            "id": tid,
            "description": desc,
            "status": "PENDING",
            "execution_mode": "TDD",
        }

    def test_run_board_renders_all_pending_tasks(self, captured_console):
        board = RunBoard(
            pending=[
                self._make_pending("TSK-007-01", "Token verification"),
                self._make_pending("TSK-007-02", "Refresh flow"),
            ]
        )
        console, buf = captured_console
        console.print(board.render())
        text = buf.getvalue()
        assert "TSK-007-01" in text
        assert "TSK-007-02" in text
        assert "Token verification" in text
        assert "Refresh flow" in text

    def test_run_board_starts_with_pending_markers(self, captured_console):
        board = RunBoard(pending=[self._make_pending("TSK-007-01", "X")])
        console, buf = captured_console
        console.print(board.render())
        assert G_PENDING in buf.getvalue()

    def test_run_board_updates_after_phase_change(self, captured_console):
        board = RunBoard(pending=[self._make_pending("TSK-007-01", "X")])
        board.mark_phase("TSK-007-01", "RED")
        console, buf = captured_console
        console.print(board.render())
        text = buf.getvalue()
        assert G_IN_PROGRESS in text
        assert "RED" in text

    def test_run_board_marks_task_completed(self, captured_console):
        board = RunBoard(pending=[self._make_pending("TSK-007-01", "X")])
        board.mark_phase("TSK-007-01", "RED")
        board.mark_phase("TSK-007-01", "GREEN")
        board.mark_phase("TSK-007-01", "JUDGE")
        board.mark_completed("TSK-007-01")
        console, buf = captured_console
        console.print(board.render())
        assert G_COMPLETED in buf.getvalue()

    def test_run_board_marks_task_failed(self, captured_console):
        board = RunBoard(pending=[self._make_pending("TSK-007-01", "X")])
        board.mark_failed("TSK-007-01", reason="train exhausted")
        console, buf = captured_console
        console.print(board.render())
        text = buf.getvalue()
        assert G_FAILED in text
        assert "train exhausted" in text

    def test_run_board_tracks_progress_counts(self, captured_console):
        board = RunBoard(
            pending=[
                self._make_pending("TSK-007-01", "A"),
                self._make_pending("TSK-007-02", "B"),
            ]
        )
        assert board.completed_count == 0
        assert board.failed_count == 0
        board.mark_completed("TSK-007-01")
        assert board.completed_count == 1
        assert board.failed_count == 0
        board.mark_failed("TSK-007-02", reason="x")
        assert board.completed_count == 1
        assert board.failed_count == 1


class TestTrainIndicator:
    def test_train_indicator_renders_attempt_count(self, captured_console):
        console, buf = captured_console
        console.print(TrainIndicator.render(attempt=2, maximum=3, phase="GREEN"))
        text = buf.getvalue()
        assert "2" in text
        assert "3" in text
        assert "TRAIN" in text

    def test_train_indicator_renders_first_attempt(self, captured_console):
        console, buf = captured_console
        console.print(TrainIndicator.render(attempt=1, maximum=3, phase="GREEN"))
        assert "1/3" in buf.getvalue()

    def test_train_indicator_uses_box_drawing(self, captured_console):
        console, buf = captured_console
        console.print(TrainIndicator.render(attempt=1, maximum=3, phase="GREEN"))
        text = buf.getvalue()
        assert G_DASH in text
        assert G_ARROW in text

    def test_train_indicator_marks_past_attempts_completed(self, captured_console):
        console, buf = captured_console
        console.print(TrainIndicator.render(attempt=3, maximum=3, phase="GREEN"))
        text = buf.getvalue()
        # Attempt 1 and 2 should be visually completed
        assert text.count(G_COMPLETED) >= 2
        # Attempt 3 (current) should be in_progress
        assert G_IN_PROGRESS in text


class TestPipelineSummary:
    def test_summary_contains_total_completed_failed(self, captured_console):
        console, buf = captured_console
        console.print(
            PipelineSummary.render(
                total=4,
                completed=3,
                failed=1,
                duration_seconds=82.4,
                pipeline_status="halted",
            )
        )
        text = buf.getvalue()
        assert "4" in text
        assert "3" in text
        assert "1" in text
        assert "1m 22s" in text
        assert "halted" in text

    def test_summary_renders_completed_status(self, captured_console):
        console, buf = captured_console
        console.print(
            PipelineSummary.render(
                total=3,
                completed=3,
                failed=0,
                duration_seconds=10.0,
                pipeline_status="completed",
            )
        )
        assert "completed" in buf.getvalue()

    def test_summary_preserves_meso_token(self, captured_console):
        console, buf = captured_console
        console.print(
            PipelineSummary.render(
                total=1,
                completed=1,
                failed=0,
                duration_seconds=1.0,
                pipeline_status="completed",
                include_meso_footer=True,
            )
        )
        text = buf.getvalue()
        assert "MESO" in text
        assert "IDLE" in text
