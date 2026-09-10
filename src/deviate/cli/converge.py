"""Opt-in Converge pack: present-state assessment helpers (pre/post)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import typer

from deviate.core.converge import (
    LEDGER_APPEND_FAILED,
    apply_findings,
    build_pre_contract,
    parse_findings_payload,
    run_converge_pass as _run_converge_pass_impl,
)
from deviate.state.ledger import append_task_record

converge_app = typer.Typer(no_args_is_help=True)


def run_converge_pass(root: Path) -> str:
    """Seam for ``deviate run`` — default handoff; tests may patch."""
    return _run_converge_pass_impl(root)


@converge_app.command()
def pre() -> None:
    """Emit this-issue Converge JSON contract (paths, issue id, readiness)."""
    contract, code = build_pre_contract(Path.cwd())
    if code != 0:
        typer.echo(contract.get("message", "CONVERGE_NOT_READY"))
        raise typer.Exit(code=code)
    print(json.dumps(contract, indent=2))


@converge_app.command()
def post(
    findings: str | None = typer.Argument(
        None,
        help="JSON findings payload: {findings:[{taxonomy, source_ref, summary}]}",
    ),
) -> None:
    """Apply append-only Convergence tasks from a structured findings payload."""
    repo = Path.cwd()
    try:
        parsed = parse_findings_payload(findings)
    except ValueError as exc:
        typer.echo(f"CONVERGE_INVALID_FINDINGS {exc}")
        raise typer.Exit(code=1) from exc
    result = apply_findings(repo, parsed, append_record=append_task_record)
    if result.error:
        token = (
            LEDGER_APPEND_FAILED
            if result.error.startswith(LEDGER_APPEND_FAILED)
            else result.error
        )
        typer.echo(token)
        raise typer.Exit(code=1)
    payload: dict[str, object] = {
        "status": result.status,
        "phase": "converge",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if result.status == "APPENDED":
        payload["task_ids"] = result.task_ids
        payload["phase"] = result.phase
    print(json.dumps(payload, indent=2))
