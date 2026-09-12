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


def test_green_train_is_one_plain_status_line() -> None:
    from deviate.cli.micro import _emit_green_train

    buf = StringIO()
    console = Console(file=buf, force_terminal=False, width=200)

    _emit_green_train(console, attempt=2, reason="judge requested another GREEN")

    assert buf.getvalue().strip() == "TRAIN (2/3) — judge requested another GREEN"


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


class TestStatusTokenRegression:
    """AC-PLAN-017/018: fixed status tokens hold on manual and auto surfaces."""

    TOKENS = ("RED_POST_OK", "GREEN_POST_OK", "REFACTOR_POST_OK", "JUDGE_POST_OK")

    def test_manual_prints_each_token_verbatim(self, capsys) -> None:
        from deviate.cli.micro import KernelOutcome, print_kernel_outcome

        for token in self.TOKENS:
            assert print_kernel_outcome(KernelOutcome(token=token)) == 0
            assert capsys.readouterr().out.strip() == token

    def test_auto_catches_each_token_per_step(self) -> None:
        from deviate.cli.micro import KernelError, handle_kernel_error

        for token in self.TOKENS:
            assert (
                handle_kernel_error(KernelError(token=token), surface="auto") == token
            )

    def test_manual_error_exits_1_with_token(self, capsys) -> None:
        from deviate.cli.micro import KernelError, handle_kernel_error

        for token in self.TOKENS:
            assert handle_kernel_error(KernelError(token=token), surface="manual") == 1
            assert token in capsys.readouterr().out

    def test_token_literals_stable_in_source(self) -> None:
        import inspect

        import deviate.cli.micro.surface as _surface_mod

        src = inspect.getsource(_surface_mod)
        for token in self.TOKENS:
            assert f'"{token}"' in src, f"status token drifted out of source: {token}"


class TestContractKeyRegression:
    """AC-PLAN-018: contract key sets stay additive on either surface."""

    RED_SHARED_KEYS = [
        "task_id",
        "test_strategy",
        "test_write_dir",
        "test_command",
        "lint_command",
    ]
    REFACTOR_REQUIRED_KEYS = [
        "status",
        "task_id",
        "task_title",
        "task_type",
        "test_strategy",
        "test_write_dir",
        "test_command",
        "lint_command",
    ]

    def _seed(self, tmp_path, task_id="TSK-001-08", status="PENDING") -> None:
        from deviate.state.config import SessionState
        from deviate.state.ledger import TaskRecord

        (tmp_path / ".deviate").mkdir(parents=True, exist_ok=True)
        SessionState(current_phase="IDLE").save(tmp_path / ".deviate" / "session.json")
        ledger = tmp_path / "specs" / "007-shared-phase-kernel" / "tasks.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text(
            TaskRecord(
                id=task_id,
                issue_id="007-001",
                description="status-token regression",
                status=status,
                execution_mode="TDD",
            ).model_dump_json()
            + "\n",
            encoding="utf-8",
        )

    def test_red_key_set_matches_manual_and_auto(self, tmp_path) -> None:
        import json
        from contextlib import chdir
        from pathlib import Path
        from typer.testing import CliRunner

        from deviate.cli import cli
        from deviate.cli.micro import _red_pre_kernel

        self._seed(tmp_path)
        with chdir(tmp_path):
            manual = json.loads(
                CliRunner().invoke(cli, ["red", "pre", "--task", "TSK-001-08"]).output
            )
            auto = _red_pre_kernel(task_id="TSK-001-08", root=Path.cwd())
        for key in self.RED_SHARED_KEYS:
            assert key in manual, f"manual RED contract dropped key: {key}"
            assert auto[key] == manual[key], f"key-set drift on shared key: {key}"

    def test_refactor_key_set_matches_manual_and_auto(self, tmp_path) -> None:
        import json
        from contextlib import chdir
        from pathlib import Path
        from typer.testing import CliRunner

        from deviate.cli import cli
        from deviate.cli.micro import _refactor_pre_kernel

        self._seed(tmp_path, status="GREEN")
        with chdir(tmp_path):
            manual = json.loads(
                CliRunner()
                .invoke(cli, ["refactor", "pre", "--task", "TSK-001-08"])
                .output
            )
            auto = _refactor_pre_kernel(task_id="TSK-001-08", root=Path.cwd())
        for key in self.REFACTOR_REQUIRED_KEYS:
            assert key in manual, f"manual REFACTOR contract dropped key: {key}"
            assert auto[key] == manual[key], f"key-set drift on shared key: {key}"


class TestCommitLiteralRegression:
    """AC-PLAN-018: verbatim commit literals stay unchanged."""

    LITERALS = {
        "_red_post_kernel": "test({scope}): RED phase - failing test",
        "_green_post_kernel": "feat({scope}): GREEN phase - implementation passes tests",
        "_refactor_post_kernel": r"refactor({scope}): REFACTOR phase \u2014 code cleanup",
    }

    def test_commit_literals_verbatim(self) -> None:
        import inspect

        import deviate.cli.micro as micro

        for kernel, literal in self.LITERALS.items():
            assert literal in inspect.getsource(getattr(micro, kernel)), (
                f"commit literal drifted in {kernel}: {literal!r}"
            )


class TestPromptRetryRegression:
    """AC-PLAN-017: prompt retry contracts hold on either surface."""

    def test_no_failing_test_forward_routes_frozen(self) -> None:
        from deviate.cli.micro import _NO_FAILING_TEST_FORWARD_ROUTES

        assert _NO_FAILING_TEST_FORWARD_ROUTES == frozenset(
            {
                "continue_refactor",
                "proceed_to_refactor_no_diff",
                "skip_refactor",
            }
        )

    def test_retry_budgets_frozen(self) -> None:
        import deviate.cli.micro as micro

        assert micro._MAX_GREEN_ATTEMPTS == 3
        assert micro._MAX_RED_ATTEMPTS == 3

    def test_train_feedback_placeholder_in_retry_prompts(self) -> None:
        from pathlib import Path

        for phase in ("red", "green"):
            body = (Path("src/deviate/prompts/auto") / f"{phase}.md").read_text(
                encoding="utf-8"
            )
            assert "{train_feedback}" in body, (
                f"retry placeholder dropped from {phase}.md"
            )

    def test_no_failing_test_path_exists_on_both_surfaces(self) -> None:
        import inspect

        import deviate.cli.micro as micro

        # Reconciled with 005-003: the auto surface reaches the shared helper
        # through its kernel (dry_run guard); the runner itself keeps the
        # non-blocking advisory checkpoint instead of a JUDGE route.
        assert "_adjudicate_red_no_failing_test" in inspect.getsource(
            micro._red_post_kernel
        )
        assert "_RedPhaseOutcome" in inspect.getsource(micro._run_red_phase)
        red_post_src = inspect.getsource(micro._red_post_kernel)
        assert "RedMustPassError" in red_post_src
        assert "failure_kind: already_satisfied" in red_post_src
