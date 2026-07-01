"""``deviate tome`` CLI subcommand — fan-out orchestration for Tome writers.

Mounted under ``cli.add_typer(tome_app, name="tome")`` from
``src/deviate/cli/__init__.py``. Ships two subcommands:

- ``deviate tome write --from-report <path>`` — fan out writer
  invocations across the rows of a ``/tome-classify`` markdown report.
- ``deviate tome list --from-report <path>`` — print the rows of a
  report as a table (or JSON with ``--json``).

The fan-out invokes the configured agent backend
(``opencode`` / ``droid`` / ``claude`` / ``pi``) per row, in parallel
up to ``--workers`` (default 4). The backend writes a markdown file
to ``target_file``; the command then checks file existence to
determine success.

This is the first deterministic-enforcement surface for Tome; the
underlying writer/verifier/setup skills remain prompt-only at
``src/deviate/prompts/commands/tome-*.md``.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from deviate.tome.batch import BatchConfig, run_batch
from deviate.tome.parser import (
    filter_actionable_rows,
    parse_classification_report,
)


tome_app = typer.Typer(
    no_args_is_help=True,
    help="Tome Subsystem — Starlight docs curation (fan-out orchestration).",
)

console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_backend(override: str | None) -> str:
    """Resolve the agent backend from CLI override or ``.deviate/config.toml``.

    Order of resolution:
    1. ``--backend`` flag (if provided).
    2. ``[agent].backend`` in ``.deviate/config.toml`` (if present and parseable).
    3. ``opencode`` (the documented default in ``AGENTS.md``).
    """
    if override:
        return override
    config_path = Path.cwd() / ".deviate" / "config.toml"
    if not config_path.exists():
        return "opencode"
    try:
        import tomllib

        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        agent_block = data.get("agent", {})
        if isinstance(agent_block, dict):
            backend = agent_block.get("backend")
            if isinstance(backend, str) and backend:
                return backend
    except Exception:
        # Malformed config — fall through to the default rather than
        # blocking the fan-out. Users can override with --backend.
        pass
    return "opencode"


def _format_capability(capability: str, width: int = 50) -> str:
    """Truncate a capability name for display in tables."""
    if len(capability) <= width:
        return capability
    return capability[: width - 1] + "…"


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


@tome_app.command("write")
def write_command(
    from_report: Path = typer.Option(
        ...,
        "--from-report",
        help="Path to a /tome-classify markdown report.",
        exists=True,
        readable=True,
    ),
    workers: int = typer.Option(
        4,
        "--workers",
        "-w",
        help="Parallel writer invocations (default 4).",
        min=1,
        max=32,
    ),
    timeout: int = typer.Option(
        600,
        "--timeout",
        "-t",
        help="Per-writer timeout in seconds (default 600).",
        min=10,
    ),
    backend: str | None = typer.Option(
        None,
        "--backend",
        help="Override agent backend (opencode|droid|claude|pi). Defaults to .deviate/config.toml [agent].backend.",
    ),
    actions: str = typer.Option(
        "create,update",
        "--actions",
        help="Comma-separated actions to process (default: create,update).",
    ),
    no_resume: bool = typer.Option(
        False,
        "--no-resume",
        help="Re-run rows whose target file already exists.",
    ),
    log: Path = typer.Option(
        Path(".deviate/tome-batch.log"),
        "--log",
        help="Per-row log file path (set to '' to disable).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print the plan and exit without dispatching.",
    ),
) -> None:
    """Fan out /tome-write-* invocations across the rows of a classification report.

    Each actionable row is dispatched as a subprocess against the
    configured agent backend. Rows run in parallel up to ``--workers``.
    With ``--resume`` (default), rows whose target file already exists
    are skipped — re-run the same command to pick up where you left
    off. Use ``--no-resume`` to force a full re-run.
    """
    backend_name = _resolve_backend(backend)
    log_path: Path | None = log if str(log) else None
    action_set = {a.strip() for a in actions.split(",") if a.strip()}

    all_rows = parse_classification_report(from_report)
    actionable = filter_actionable_rows(all_rows, action_set)

    console.print(
        f"[bold]Report:[/] {from_report}  "
        f"[bold]Rows:[/] {len(all_rows)} ({len(actionable)} actionable, actions={sorted(action_set)})"
    )
    console.print(
        f"[bold]Backend:[/] {backend_name}  "
        f"[bold]Workers:[/] {workers}  "
        f"[bold]Timeout:[/] {timeout}s  "
        f"[bold]Resume:[/] {'off (full re-run)' if no_resume else 'on (skip existing files)'}"
    )

    if dry_run:
        _print_dry_run_table(actionable)
        return

    config = BatchConfig(
        report_path=from_report,
        workers=workers,
        timeout=timeout,
        backend=backend_name,
        actions=action_set,
        resume=not no_resume,
        log_path=log_path,
        cwd=Path.cwd(),
    )

    summary = run_batch(config)

    if summary.interrupted:
        console.print(
            f"\n[bold yellow]INTERRUPTED[/] Ctrl+C received — killed in-flight "
            f"subprocesses and drained {summary.done + summary.failed} in-flight "
            f"results before exiting. {summary.actionable - summary.done - summary.failed - summary.skipped} "
            f"rows were not started."
        )

    console.print(
        f"\n[bold green]DONE[/] {summary.done}  "
        f"[bold red]FAIL[/] {summary.failed}  "
        f"[bold yellow]SKIP[/] {summary.skipped}  "
        f"({summary.actionable} actionable of {summary.total} total)  "
        f"[bold]in {summary.duration_seconds:.1f}s[/]"
    )

    if log_path is not None:
        console.print(f"[dim]Log: {log_path}[/]")

    if summary.interrupted:
        # 130 is the POSIX convention for SIGINT (Ctrl+C). Use it so shell
        # scripts and CI runners can detect an interrupted run distinctly
        # from a normal failure.
        raise typer.Exit(130)

    if summary.failed:
        console.print(f"\n[bold red]Failures ({summary.failed}):[/]")
        for r in summary.results:
            if r.status != "DONE":
                console.print(f"  [red]{r.status}[/] {r.target_file}")
                if r.stderr_tail:
                    console.print(f"    [dim]{r.stderr_tail[:300]}[/]")
        raise typer.Exit(1)


@tome_app.command("list")
def list_command(
    from_report: Path = typer.Option(
        ...,
        "--from-report",
        help="Path to a /tome-classify markdown report.",
        exists=True,
        readable=True,
    ),
    json_flag: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON instead of a table.",
    ),
) -> None:
    """List the rows of a /tome-classify report."""
    rows = parse_classification_report(from_report)

    if json_flag:
        typer.echo(
            json.dumps(
                [
                    {
                        "capability": r.capability,
                        "evidence": r.evidence,
                        "audience": r.audience,
                        "doc_type": r.doc_type,
                        "action": r.action,
                        "target_file": r.target_file,
                        "confidence": r.confidence,
                    }
                    for r in rows
                ],
                indent=2,
            )
        )
        return

    table = Table(
        title=f"Classification Report — {from_report.name} ({len(rows)} rows)"
    )
    table.add_column("Capability", style="cyan", no_wrap=False)
    table.add_column("DocType", style="magenta")
    table.add_column("Action", style="green")
    table.add_column("Confidence", justify="right")
    table.add_column("Target")
    for row in rows:
        action_style = {
            "create": "green",
            "update": "yellow",
            "no-change": "dim",
            "human-review": "red",
            "setup-required": "red",
        }.get(row.action, "white")
        table.add_row(
            _format_capability(row.capability, 60),
            row.doc_type,
            f"[{action_style}]{row.action}[/]",
            f"{row.confidence:.2f}",
            row.target_file or "—",
        )
    console.print(table)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _print_dry_run_table(rows) -> None:
    """Print the dispatch plan in dry-run mode."""
    table = Table(title=f"Dry run — {len(rows)} rows to dispatch")
    table.add_column("Action", style="cyan")
    table.add_column("DocType", style="magenta")
    table.add_column("Target")
    table.add_column("Capability")
    table.add_column("Conf", justify="right")
    for row in rows:
        table.add_row(
            row.action,
            row.doc_type,
            row.target_file or "—",
            _format_capability(row.capability, 40),
            f"{row.confidence:.2f}",
        )
    console.print(table)
