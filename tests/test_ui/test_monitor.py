from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from deviate.ui.monitor import MarkdownStatus, OrchestrationMonitor


@pytest.fixture
def console():
    return MagicMock()


@pytest.fixture
def monitor(console):
    return OrchestrationMonitor(console)


class TestDisplayLifecycle:
    def test_monitor_display_starts_stopped(
        self, monitor: OrchestrationMonitor
    ) -> None:
        assert not monitor.display_active

    def test_monitor_enter_activates_display(
        self, monitor: OrchestrationMonitor
    ) -> None:
        with monitor as m:
            assert m.display_active

    def test_monitor_pipeline_complete_clears(
        self, monitor: OrchestrationMonitor
    ) -> None:
        with monitor:
            monitor.push_event("pipeline_complete")
        assert not monitor.display_active

    def test_monitor_double_exit_does_not_raise(
        self, monitor: OrchestrationMonitor
    ) -> None:
        with monitor:
            pass
        with monitor:
            pass
        assert not monitor.display_active


class TestTaskMarkers:
    def test_monitor_task_started_creates_row(
        self, monitor: OrchestrationMonitor
    ) -> None:
        with monitor:
            monitor.push_event(
                "task_started",
                id="TSK-001",
                description="Implement auth",
                phase="RED",
            )
            task = monitor._tasks["TSK-001"]
            assert task.id == "TSK-001"
            assert task.description == "Implement auth"
            assert task.marker == MarkdownStatus.IN_PROGRESS
            assert task.phase == "RED"

    def test_monitor_updates_task_marker(self, monitor: OrchestrationMonitor) -> None:
        with monitor:
            monitor.push_event(
                "task_started",
                id="TSK-001",
                description="Implement auth",
                phase="RED",
            )
            assert monitor._tasks["TSK-001"].marker == MarkdownStatus.IN_PROGRESS

            monitor.push_event("phase_change", task_id="TSK-001", phase="GREEN")
            assert monitor._tasks["TSK-001"].phase == "GREEN"

            monitor.push_event("task_completed", task_id="TSK-001", phase="GREEN")
            assert monitor._tasks["TSK-001"].marker == MarkdownStatus.COMPLETED

    def test_monitor_task_failure_marker(self, monitor: OrchestrationMonitor) -> None:
        with monitor:
            monitor.push_event(
                "task_started",
                id="TSK-001",
                description="Implement auth",
                phase="RED",
            )
            monitor.push_event(
                "task_failed",
                task_id="TSK-001",
                error_reason="Agent returned non-zero exit code 1",
            )
            task = monitor._tasks["TSK-001"]
            assert task.marker == MarkdownStatus.FAILED
            assert task.error_reason == "Agent returned non-zero exit code 1"

    def test_monitor_task_completed_without_started(
        self, monitor: OrchestrationMonitor
    ) -> None:
        with monitor:
            monitor.push_event(
                "task_completed",
                task_id="TSK-002",
                phase="GREEN",
                description="Fix bug",
            )
            task = monitor._tasks["TSK-002"]
            assert task.id == "TSK-002"
            assert task.description == "Fix bug"
            assert task.marker == MarkdownStatus.COMPLETED
            assert task.phase == "GREEN"

    def test_monitor_completed_and_failed_counts(
        self, monitor: OrchestrationMonitor
    ) -> None:
        with monitor:
            assert monitor.completed_count == 0
            assert monitor.failed_count == 0

            monitor.push_event("task_started", id="TSK-001", phase="RED")
            assert monitor.completed_count == 0
            assert monitor.failed_count == 0

            monitor.push_event("task_completed", task_id="TSK-001")
            assert monitor.completed_count == 1
            assert monitor.failed_count == 0

            monitor.push_event("task_started", id="TSK-002", phase="RED")
            monitor.push_event("task_failed", task_id="TSK-002", error_reason="x")
            assert monitor.completed_count == 1
            assert monitor.failed_count == 1

            # Tasks that were never started are not in _tasks at all
            # so completed_count and failed_count are unaffected.
            assert "TSK-003" not in monitor._tasks
            assert monitor.completed_count == 1
            assert monitor.failed_count == 1


class TestKeyboardInterrupt:
    def test_monitor_keyboard_interrupt(self, monitor: OrchestrationMonitor) -> None:
        with monitor:
            monitor.push_event(
                "task_started",
                id="TSK-001",
                description="Implement auth",
                phase="RED",
            )
            monitor.signal_keyboard_interrupt()
            assert monitor.interrupted
            assert monitor._tasks["TSK-001"].marker == MarkdownStatus.FAILED


class TestValidation:
    def test_monitor_unknown_event_type(self, monitor: OrchestrationMonitor) -> None:
        with monitor:
            with pytest.raises(ValueError, match="Unknown event type"):
                monitor.push_event("unknown_event")


class TestRender:
    def test_monitor_render_stub(self, monitor: OrchestrationMonitor) -> None:
        with monitor:
            monitor.render()
