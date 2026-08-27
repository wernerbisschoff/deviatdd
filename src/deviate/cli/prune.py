"""Thin ``deviate prune pre`` / ``post`` contract for ``/deviate-prune``."""

from __future__ import annotations

from pathlib import Path

import typer

from deviate.core.prune import (
    apply_prune,
    build_prune_plan,
    dumps_contract,
    plan_to_contract,
)

prune_app = typer.Typer(
    no_args_is_help=True,
    help="Post-COMPLETED spec+test cleanup (one issue per invocation)",
)


def _intent_text(intent: list[str] | None) -> str:
    return " ".join(intent or [])


@prune_app.command()
def pre(
    issue: str | None = typer.Option(
        None, "--issue", "-i", help="Target issue ID (one issue per invocation)"
    ),
    intent: list[str] | None = typer.Argument(
        None, help="Optional operator intent (compact/squash/rewrite is rejected)"
    ),
) -> None:
    """Inventory drop-safe cycle markdown and honeycomb test tags."""
    root = Path.cwd()
    plan = build_prune_plan(root, issue, intent=_intent_text(intent))
    print(dumps_contract(plan_to_contract(root, plan)))
    if plan.status in {"READY", "IN_FLIGHT"}:
        raise typer.Exit(code=0)
    if plan.reason:
        typer.echo(plan.reason, err=True)
    raise typer.Exit(code=1)


@prune_app.command()
def post(
    issue: str | None = typer.Option(
        None, "--issue", "-i", help="Target issue ID (one issue per invocation)"
    ),
    intent: list[str] | None = typer.Argument(
        None, help="Optional operator intent (compact/squash/rewrite is rejected)"
    ),
) -> None:
    """Apply honeycomb thinning and, when READY, delete that issue's cycle markdown."""
    root = Path.cwd()
    plan = build_prune_plan(root, issue, intent=_intent_text(intent))
    print(dumps_contract(plan_to_contract(root, plan)))
    if plan.status in {"LEDGER_REWRITE_REJECTED", "NO_ISSUE", "ONE_ISSUE_ONLY"}:
        if plan.reason:
            typer.echo(plan.reason, err=True)
        raise typer.Exit(code=1)
    apply_prune(root, plan)
    if plan.status == "ACS_NOT_ENCODED":
        typer.echo(plan.reason, err=True)
        raise typer.Exit(code=1)
    if plan.status == "IN_FLIGHT":
        typer.echo(plan.reason, err=True)
        raise typer.Exit(code=0)
    raise typer.Exit(code=0)
