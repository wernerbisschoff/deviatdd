"""Top-level ``flows`` Typer group — owner of flows.jsonl creation.

`deviate flows sync` seeds ``specs/_product/flows.jsonl`` from the canonical
``specs/_product/flows/index.md``. The slash command ``/deviate-flows`` invokes
this command in Phase B, between authoring the index row and the final
``git commit``, so the catalog row and the ledger events land in the same
commit (atomic across the append-only ledger protocol).
"""

from __future__ import annotations

from pathlib import Path

import typer

from deviate.state.ledger import FlowIndexEmptyError, seed_flow_ledger

flows_app = typer.Typer(no_args_is_help=True, help="Flow ledger commands")

SPECS_ROOT = Path("specs")
FLOWS_INDEX_REL = Path("_product") / "flows" / "index.md"
FLOWS_LEDGER_REL = Path("_product") / "flows.jsonl"


@flows_app.command("sync")
def flows_sync() -> None:
    """Seed ``specs/_product/flows.jsonl`` from the canonical flow index.

    Reads every row of ``specs/_product/flows/index.md`` and appends one
    ``FlowRecord`` identity row plus ``FLOW_DISCOVERED`` and
    ``FLOW_DOCUMENTED`` events per flow. Idempotent: re-running on a
    populated ledger produces zero net appends.
    """
    flows_index = SPECS_ROOT / FLOWS_INDEX_REL
    flows_ledger = SPECS_ROOT / FLOWS_LEDGER_REL

    if not flows_index.exists():
        typer.echo(
            f"FLOWS_INDEX_MISSING {flows_index} — cannot seed flows ledger "
            "without a canonical index. Run /deviate-flows to author the "
            "catalog first.",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        appended = seed_flow_ledger(flows_index, flows_ledger)
    except FlowIndexEmptyError as exc:
        typer.echo(f"FLOWS_INDEX_EMPTY {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if appended == 0:
        typer.echo(
            "FLOW_LEDGER_UP_TO_DATE flows.jsonl already in sync with "
            "flows/index.md (no new rows appended)"
        )
    else:
        typer.echo(f"FLOW_LEDGER_SEEDED {appended} flow identity row(s) appended")
