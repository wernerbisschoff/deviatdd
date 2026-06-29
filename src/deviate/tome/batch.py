"""Fan-out orchestration for ``/tome-write-*`` invocations.

Given a ``/tome-classify`` markdown report, this module:

1. Parses the report into capability rows.
2. Filters to actionable rows (default: ``create`` / ``update``).
3. Pre-loads writer skill bodies (one per ``doc_type``).
4. Skips rows whose target file already exists (when ``resume=True``).
5. Dispatches the remaining rows in parallel against the configured
   agent backend (default 4 workers).
6. Returns a ``BatchSummary`` with per-row ``DispatchResult`` records.

The module is a library — the CLI layer (``src/deviate/cli/tome.py``)
wraps it with Typer argument parsing and Rich output.
"""

from __future__ import annotations

import concurrent.futures
import time
from dataclasses import dataclass, field
from pathlib import Path

from .dispatch import dispatch_writer, DispatchResult
from .parser import (
    CapabilityRow,
    filter_actionable_rows,
    parse_classification_report,
    writer_skill_for,
)


@dataclass
class BatchConfig:
    """Configuration for a batch write run.

    All paths are resolved relative to ``cwd`` (defaults to
    ``Path.cwd()``). ``actions`` defaults to ``{"create", "update"}``;
    the parser's ``setup-required``, ``human-review``, and
    ``no-change`` actions are skipped by default.
    """

    report_path: Path
    workers: int = 4
    timeout: int = 600
    backend: str = "opencode"
    actions: set[str] = field(default_factory=lambda: {"create", "update"})
    resume: bool = True
    log_path: Path | None = None
    cwd: Path = field(default_factory=Path.cwd)


@dataclass
class BatchSummary:
    """Summary of a completed batch run.

    ``exit_code`` returns 0 when no rows failed (status != DONE) and
    1 otherwise. CLI consumers typically use this to decide whether
    to raise ``typer.Exit(1)``.
    """

    total: int  # Total rows in the report.
    actionable: int  # Rows that matched the configured actions.
    done: int
    failed: int
    skipped: int  # Rows skipped because the target file already exists.
    duration_seconds: float
    results: list[DispatchResult] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return 0 if self.failed == 0 else 1


def build_writer_prompt(writer_skill_body: str, row: CapabilityRow) -> str:
    """Compose the prompt fed to the agent for one writer invocation.

    The prompt bundles:

    - The capability row (so the agent knows what to document)
    - The full writer skill body (so the agent can follow the register,
      frontmatter, and self-verify rules)
    - A completion signal protocol (``[DONE]`` / ``[FAIL]``)
    """
    target_display = row.target_file or "null (setup-required)"
    return f"""# Tome Writer Invocation

You are running the `{writer_skill_for(row.doc_type)}` writer from DeviaTDD's Tome subsystem.

## Capability to document

| capability | audience | doc_type | action | target_file | confidence |
|------------|----------|----------|--------|-------------|------------|
| {row.capability} | {row.audience} | {row.doc_type} | {row.action} | {target_display} | {row.confidence} |

Evidence — files you MUST read before writing (verbatim paths from the classifier):
{row.evidence}

## Writer skill body (inlined)

{writer_skill_body}

## Completion signal

After writing the file at `{row.target_file or "<see writer skill>"}` and self-verifying per the writer's rules, emit EXACTLY ONE final line:

- `[DONE] wrote {row.target_file}` on success
- `[FAIL] <one-line reason>` on failure

Do not emit any other text after this line.
"""


def load_writer_skill(skill_basename: str, cwd: Path) -> str:
    """Load a writer skill body from ``src/deviate/prompts/commands/<name>.md``.

    Strips the YAML frontmatter and returns the body. Raises
    ``FileNotFoundError`` if the skill file is missing — that signals a
    broken installation or a typo in the doc_type.
    """
    skill_path = (
        cwd / "src" / "deviate" / "prompts" / "commands" / f"{skill_basename}.md"
    )
    text = skill_path.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3 :].strip()
    return text


def should_skip_row(row: CapabilityRow, cwd: Path, resume: bool) -> bool:
    """Decide whether to skip a row under the resume policy.

    With ``resume=True`` (default), skip rows whose declared target file
    already exists on disk — the writer produced it in a prior run and
    we trust it. With ``resume=False``, never skip (re-run everything).

    Rows with no target file (typically ``setup-required`` actions) are
    never skipped on file-existence grounds — the agent gets to decide.
    """
    if not resume:
        return False
    if not row.target_file:
        return False
    return (cwd / row.target_file).exists()


def run_batch(config: BatchConfig) -> BatchSummary:
    """Run the batch write fan-out and return a summary.

    On a pre-flight error (e.g., a writer skill file is missing for
    one of the row's doc_types), raises ``RuntimeError`` so the CLI
    surfaces a clear failure rather than partial output.
    """
    start = time.monotonic()

    all_rows = parse_classification_report(config.report_path)
    actionable = filter_actionable_rows(all_rows, config.actions)

    # Pre-load writer skill bodies (one per doc_type present in actionable rows).
    skills: dict[str, str] = {}
    for row in actionable:
        if row.doc_type not in skills:
            try:
                skills[row.doc_type] = load_writer_skill(
                    writer_skill_for(row.doc_type), config.cwd
                )
            except FileNotFoundError as e:
                raise RuntimeError(
                    f"Writer skill not found for doc_type={row.doc_type!r}: {e}. "
                    f"Expected at: src/deviate/prompts/commands/{writer_skill_for(row.doc_type)}.md"
                ) from e
            except KeyError as e:
                raise RuntimeError(
                    f"Unknown doc_type {row.doc_type!r} in row {row.capability!r}; "
                    f"expected one of: tutorial, how-to, reference, explanation"
                ) from e

    # Build the work list, applying the resume skip.
    work: list[tuple[CapabilityRow, str]] = []
    skipped = 0
    for row in actionable:
        if should_skip_row(row, config.cwd, config.resume):
            skipped += 1
            continue
        work.append((row, build_writer_prompt(skills[row.doc_type], row)))

    if not work:
        return BatchSummary(
            total=len(all_rows),
            actionable=len(actionable),
            done=0,
            failed=0,
            skipped=skipped,
            duration_seconds=time.monotonic() - start,
            results=[],
        )

    # Dispatch in parallel. Each task is one subprocess; the pool is
    # bounded by config.workers so we don't overwhelm the backend.
    log = open(config.log_path, "w", encoding="utf-8") if config.log_path else None
    try:
        results: list[DispatchResult] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=config.workers) as ex:
            future_to_row = {
                ex.submit(
                    dispatch_writer,
                    config.backend,
                    prompt,
                    row.target_file,
                    config.cwd,
                    config.timeout,
                ): row
                for row, prompt in work
            }
            for future in concurrent.futures.as_completed(future_to_row):
                row = future_to_row[future]
                try:
                    result = future.result()
                except (
                    Exception
                ) as e:  # dispatch_writer should not raise, but be defensive.
                    result = DispatchResult(
                        returncode=-1,
                        file_exists=False,
                        target_file=row.target_file,
                        stdout_tail="",
                        stderr_tail=f"DISPATCH_ERROR: {type(e).__name__}: {e}",
                        duration_seconds=0.0,
                    )
                results.append(result)
                if log is not None:
                    log.write(
                        f"[{result.status:7s}] {row.action:5s} {row.doc_type:11s} "
                        f"{row.target_file} ({result.duration_seconds:.1f}s)\n"
                    )
                    if result.status != "DONE" and result.stderr_tail:
                        log.write(f"           stderr: {result.stderr_tail}\n")
                    log.flush()

        done = sum(1 for r in results if r.status == "DONE")
        failed = len(results) - done
        return BatchSummary(
            total=len(all_rows),
            actionable=len(actionable),
            done=done,
            failed=failed,
            skipped=skipped,
            duration_seconds=time.monotonic() - start,
            results=results,
        )
    finally:
        if log is not None:
            log.close()
