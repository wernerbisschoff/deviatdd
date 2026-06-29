"""Tests for ``deviate.tome.batch``.

The batch module is the fan-out orchestrator. It loads writer skill
bodies, builds prompts, skips rows whose target file exists (when
``resume=True``), and dispatches the remainder in parallel.

These tests use the same fake-backend technique as ``test_dispatch.py``
to avoid actually shelling out to ``opencode`` / ``droid`` etc.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from deviate.tome import dispatch as dispatch_module
from deviate.tome.batch import (
    BatchConfig,
    build_writer_prompt,
    load_writer_skill,
    run_batch,
    should_skip_row,
)
from deviate.tome.parser import CapabilityRow


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


SAMPLE_REPORT = """# Classification Report — abc1234

**Status**: mixed

## Summary
Test report.

## Capabilities
| capability | evidence | audience | doc_type | action | target_file | confidence |
|------------|----------|----------|----------|--------|-------------|------------|
| Setup workspace | `pyproject.toml:34` | developer | how-to | create | apps/docs/src/content/docs/how-to/setup.md | 0.85 |
| CLI flags | `pyproject.toml:34` | developer | reference | create | apps/docs/src/content/docs/reference/flags.md | 0.80 |
| Architecture | `specs/arch.md` | developer | explanation | update | apps/docs/src/content/docs/explanation/arch.md | 0.75 |
| Setup required | — | developer | how-to | setup-required | null | 0.50 |
"""


def _write_fake_writer_skill(prompts_dir: Path) -> None:
    """Create minimal writer-skill files the loader can read."""
    prompts_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "tome-write-tutorial",
        "tome-write-how-to",
        "tome-write-reference",
        "tome-write-explanation",
    ):
        (prompts_dir / f"{name}.md").write_text(
            f"---\nname: {name}\ndescription: fake\n---\n\n# {name}\n\nBody content.\n"
        )


@pytest.fixture
def work_dir(tmp_path: Path) -> Path:
    cwd = tmp_path / "work"
    cwd.mkdir()
    _write_fake_writer_skill(cwd / "src" / "deviate" / "prompts" / "commands")
    return cwd


@pytest.fixture
def report_file(work_dir: Path) -> Path:
    p = work_dir / "report.md"
    p.write_text(SAMPLE_REPORT, encoding="utf-8")
    return p


@pytest.fixture
def restore_backend_commands():
    """Save and restore BACKEND_COMMANDS around each test."""
    original = dict(dispatch_module.BACKEND_COMMANDS)
    yield
    dispatch_module.BACKEND_COMMANDS.clear()
    dispatch_module.BACKEND_COMMANDS.update(original)


@pytest.fixture(autouse=True)
def clear_fake_target_env(monkeypatch):
    """Ensure TOME_FAKE_TARGET is unset unless a test sets it explicitly."""
    monkeypatch.delenv("TOME_FAKE_TARGET", raising=False)
    yield


def _register_oneshot_backend(name: str, marker: Path) -> None:
    """Register a fake backend that writes ``marker`` and exits 0.

    Ignores TOME_FAKE_TARGET so the test doesn't need to know each
    row's target_file. The marker is the test's signal that dispatch
    happened. Per-row target_file existence is not verified by this
    fake — see DispatchResult tests in test_dispatch.py for that.
    """
    dispatch_module.BACKEND_COMMANDS[name] = [
        sys.executable,
        "-c",
        f"import sys; sys.stdin.read(); open('{marker}', 'w').write('x'); sys.exit(0)",
    ]


# ---------------------------------------------------------------------------
# build_writer_prompt
# ---------------------------------------------------------------------------


def test_build_writer_prompt_includes_capability_and_target() -> None:
    row = CapabilityRow(
        capability="Setup workspace",
        evidence="pyproject.toml:34",
        audience="developer",
        doc_type="how-to",
        action="create",
        target_file="apps/docs/how-to/setup.md",
        confidence=0.85,
    )
    body = "# WRITER BODY\n"
    prompt = build_writer_prompt(body, row)
    assert "Setup workspace" in prompt
    assert "apps/docs/how-to/setup.md" in prompt
    assert "how-to" in prompt
    assert "0.85" in prompt
    assert "pyproject.toml:34" in prompt
    assert "tome-write-how-to" in prompt
    assert "# WRITER BODY" in prompt
    assert "[DONE] wrote apps/docs/how-to/setup.md" in prompt
    assert "[FAIL]" in prompt


def test_build_writer_prompt_handles_null_target() -> None:
    row = CapabilityRow(
        capability="X",
        evidence="y",
        audience="dev",
        doc_type="how-to",
        action="setup-required",
        target_file="",
        confidence=0.5,
    )
    prompt = build_writer_prompt("body", row)
    assert "null" in prompt.lower()


# ---------------------------------------------------------------------------
# load_writer_skill
# ---------------------------------------------------------------------------


def test_load_writer_skill_strips_frontmatter(work_dir: Path) -> None:
    body = load_writer_skill("tome-write-how-to", work_dir)
    assert not body.startswith("---")
    assert "Body content." in body


def test_load_writer_skill_missing_file_raises(work_dir: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_writer_skill("tome-write-nonexistent", work_dir)


# ---------------------------------------------------------------------------
# should_skip_row
# ---------------------------------------------------------------------------


def test_should_skip_row_skips_when_file_exists(work_dir: Path) -> None:
    target = "apps/docs/exists.md"
    (work_dir / target).parent.mkdir(parents=True, exist_ok=True)
    (work_dir / target).write_text("exists")
    row = CapabilityRow(
        capability="x",
        evidence="y",
        audience="dev",
        doc_type="how-to",
        action="update",
        target_file=target,
        confidence=0.5,
    )
    assert should_skip_row(row, work_dir, resume=True) is True


def test_should_skip_row_does_not_skip_when_file_missing(work_dir: Path) -> None:
    row = CapabilityRow(
        capability="x",
        evidence="y",
        audience="dev",
        doc_type="how-to",
        action="update",
        target_file="apps/docs/missing.md",
        confidence=0.5,
    )
    assert should_skip_row(row, work_dir, resume=True) is False


def test_should_skip_row_resume_off_never_skips(work_dir: Path) -> None:
    target = "apps/docs/exists.md"
    (work_dir / target).parent.mkdir(parents=True, exist_ok=True)
    (work_dir / target).write_text("exists")
    row = CapabilityRow(
        capability="x",
        evidence="y",
        audience="dev",
        doc_type="how-to",
        action="update",
        target_file=target,
        confidence=0.5,
    )
    assert should_skip_row(row, work_dir, resume=False) is False


def test_should_skip_row_no_target_file_never_skips(work_dir: Path) -> None:
    row = CapabilityRow(
        capability="x",
        evidence="y",
        audience="dev",
        doc_type="how-to",
        action="setup-required",
        target_file="",
        confidence=0.5,
    )
    assert should_skip_row(row, work_dir, resume=True) is False


# ---------------------------------------------------------------------------
# run_batch
# ---------------------------------------------------------------------------


def test_run_batch_empty_actionable_returns_zero(
    work_dir: Path, report_file: Path, restore_backend_commands
) -> None:
    config = BatchConfig(
        report_path=report_file,
        actions={"no-such-action"},
        cwd=work_dir,
    )
    summary = run_batch(config)
    assert summary.total == 4
    assert summary.actionable == 0
    assert summary.done == 0
    assert summary.failed == 0
    assert summary.skipped == 0
    assert summary.exit_code == 0


def test_run_batch_dispatches_each_actionable_row(
    work_dir: Path, report_file: Path, restore_backend_commands
) -> None:
    marker = work_dir / "MARKER"
    _register_oneshot_backend("fakewrite", marker)
    config = BatchConfig(
        report_path=report_file,
        actions={"create", "update"},
        backend="fakewrite",
        cwd=work_dir,
        resume=False,
        workers=1,
    )
    summary = run_batch(config)
    # 3 actionable rows (2 create + 1 update); 1 setup-required filtered.
    assert summary.actionable == 3
    assert len(summary.results) == 3
    # Marker proves dispatch happened for all 3 rows. Status is MISSING
    # because the fake backend writes the marker, not the target_file.
    assert marker.exists()


def test_run_batch_skips_existing_files_with_resume(
    work_dir: Path, report_file: Path, restore_backend_commands
) -> None:
    pre_existing = work_dir / "apps/docs/src/content/docs/how-to/setup.md"
    pre_existing.parent.mkdir(parents=True, exist_ok=True)
    pre_existing.write_text("pre-existing content")

    marker = work_dir / "DISPATCH_MARKER"
    _register_oneshot_backend("fakewrite", marker)

    config = BatchConfig(
        report_path=report_file,
        actions={"create", "update"},
        backend="fakewrite",
        cwd=work_dir,
        resume=True,
        workers=1,
    )
    summary = run_batch(config)
    assert summary.actionable == 3
    assert summary.skipped == 1
    assert len(summary.results) == 2  # only 2 dispatched (1 skipped)
    assert marker.exists()


def test_run_batch_no_resume_runs_everything(
    work_dir: Path, report_file: Path, restore_backend_commands
) -> None:
    pre_existing = work_dir / "apps/docs/src/content/docs/how-to/setup.md"
    pre_existing.parent.mkdir(parents=True, exist_ok=True)
    pre_existing.write_text("pre-existing")

    marker = work_dir / "DISPATCH_MARKER"
    _register_oneshot_backend("fakewrite", marker)

    config = BatchConfig(
        report_path=report_file,
        actions={"create", "update"},
        backend="fakewrite",
        cwd=work_dir,
        resume=False,
        workers=1,
    )
    summary = run_batch(config)
    assert summary.skipped == 0
    assert len(summary.results) == 3
    assert marker.exists()


def test_run_batch_failed_rows_set_exit_code(
    work_dir: Path, report_file: Path, restore_backend_commands
) -> None:
    dispatch_module.BACKEND_COMMANDS["fakefail"] = [
        sys.executable,
        "-c",
        "import sys; sys.stdin.read(); sys.stderr.write('boom'); sys.exit(1)",
    ]
    config = BatchConfig(
        report_path=report_file,
        actions={"create", "update"},
        backend="fakefail",
        cwd=work_dir,
        resume=False,
        workers=1,
    )
    summary = run_batch(config)
    assert summary.done == 0
    assert summary.failed == 3
    assert summary.exit_code == 1
    assert len(summary.results) == 3
    for r in summary.results:
        assert r.status == "FAIL"


def test_run_batch_raises_on_missing_skill_file(
    work_dir: Path, report_file: Path, restore_backend_commands
) -> None:
    # Remove the how-to skill so load_writer_skill raises.
    (
        work_dir / "src" / "deviate" / "prompts" / "commands" / "tome-write-how-to.md"
    ).unlink()

    dispatch_module.BACKEND_COMMANDS["fakewrite"] = ["echo"]
    config = BatchConfig(
        report_path=report_file,
        actions={"create", "update"},
        backend="fakewrite",
        cwd=work_dir,
        resume=False,
        workers=1,
    )
    with pytest.raises(RuntimeError, match="Writer skill not found"):
        run_batch(config)


def test_run_batch_writes_log_when_log_path_set(
    work_dir: Path, report_file: Path, restore_backend_commands
) -> None:
    log_path = work_dir / "batch.log"
    dispatch_module.BACKEND_COMMANDS["fakewrite"] = [
        sys.executable,
        "-c",
        "import sys; sys.stdin.read(); sys.exit(0)",
    ]
    config = BatchConfig(
        report_path=report_file,
        actions={"create", "update"},
        backend="fakewrite",
        cwd=work_dir,
        resume=False,
        workers=1,
        log_path=log_path,
    )
    run_batch(config)
    log_text = log_path.read_text()
    assert "setup.md" in log_text
