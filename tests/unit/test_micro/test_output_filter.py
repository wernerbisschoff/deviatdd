from __future__ import annotations

from io import StringIO

from rich.console import Console


def _handler_output(verbose: bool, lines: list[str]) -> str:
    """Run lines through ``_make_output_handler`` and return captured stdout."""
    from deviate.cli.micro import _make_output_handler

    buf = StringIO()
    c = Console(file=buf, force_terminal=False, width=200)
    handler = _make_output_handler(c, verbose=verbose)
    for line in lines:
        handler(line)
    return buf.getvalue()


class TestMiseNoiseFilter:
    """Mise/Ruff shell noise between phases is suppressed in normal mode."""

    NOISE = [
        "[lint] $ uv run ruff check",
        "[lint] All checks passed!",
        "[lint] Finished in 39.8ms",
        "[format-check] $ uv run ruff format --check",
        "[format-check] 142 files already formatted",
        "[format-check] Finished in 30.6ms",
        "Finished in 46.5ms",
    ]

    def test_mise_task_prefix_filtered(self) -> None:
        out = _handler_output(verbose=False, lines=self.NOISE)
        for line in self.NOISE:
            assert line not in out, f"{line!r} should have been filtered"

    def test_mise_noise_visible_in_verbose_mode(self) -> None:
        # Verbose mode is the escape hatch for debugging agent output.
        out = _handler_output(verbose=True, lines=self.NOISE)
        for line in self.NOISE:
            assert line in out, f"{line!r} should be visible under --verbose"

    def test_prose_lines_kept(self) -> None:
        prose = [
            "I will run mise check now.",
            "Summary: 3 passing tests, 1 failing",
            "JUDGE_REFACTOR_NOTE: SPEC NAMING NOTE",
        ]
        out = _handler_output(verbose=False, lines=prose)
        for line in prose:
            assert line in out, f"{line!r} should have been kept"


class TestAgentStatusFilter:
    """Agent-declared phase states are internal; orchestration owns status UI."""

    def test_phase_status_lines_filtered_in_normal_mode(self) -> None:
        statuses = [
            "Status: GREEN_STATE_ACHIEVED",
            "Status: GREEN_STATE_ACHIEVED (mechanical boundary)",
            "Status: TASK_COMPLETE",
        ]

        out = _handler_output(verbose=False, lines=statuses)

        for line in statuses:
            assert line not in out

    def test_phase_status_lines_visible_in_verbose_mode(self) -> None:
        status = "Status: GREEN_STATE_ACHIEVED"

        assert status in _handler_output(verbose=True, lines=[status])


class TestMiseRegexPatterns:
    """Direct coverage of the noise regexes."""

    def test_task_prefix_matches(self) -> None:
        from deviate.cli.micro import _MISE_TASK_PREFIX_RE

        assert _MISE_TASK_PREFIX_RE.match("[lint] hello")
        assert _MISE_TASK_PREFIX_RE.match("[format-check] 142 files")
        assert _MISE_TASK_PREFIX_RE.match("[check-types] running")

    def test_task_prefix_skips_unrelated_brackets(self) -> None:
        from deviate.cli.micro import _MISE_TASK_PREFIX_RE

        assert not _MISE_TASK_PREFIX_RE.match("[HANDOVER_MANIFEST]")
        assert not _MISE_TASK_PREFIX_RE.match("[1] first item")
        assert not _MISE_TASK_PREFIX_RE.match("not bracketed")

    def test_timing_matches(self) -> None:
        from deviate.cli.micro import _MISE_TIMING_RE

        assert _MISE_TIMING_RE.match("Finished in 39.8ms")
        assert _MISE_TIMING_RE.match("Finished in 200ms")

    def test_timing_skips_unrelated_lines(self) -> None:
        from deviate.cli.micro import _MISE_TIMING_RE

        assert not _MISE_TIMING_RE.match("Finished successfully")
        assert not _MISE_TIMING_RE.match("Finished in 1.2s")
        assert not _MISE_TIMING_RE.match("Processing in 39ms")
