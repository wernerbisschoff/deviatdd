from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import typer

from deviate.cli._common import console
from deviate.core.complexity import ClassificationResult, ComplexityGate
from deviate.state.ledger import AdhocRecord

adhoc_app = typer.Typer(no_args_is_help=True)


def _adhoc_ledger_path() -> Path:
    return Path.cwd() / "specs" / "adhoc.jsonl"


def _read_adhoc_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


@adhoc_app.command()
def pre(
    description: str = typer.Argument(..., help="Task description to classify"),
    skip_gates: bool = typer.Option(
        False,
        "--skip-gates",
        help="Skip complexity gate rejection for HIGH complexity tasks",
    ),
) -> None:
    """Classify an ad-hoc task description and record it for execution."""
    result: ClassificationResult = ComplexityGate.classify(description)

    if result.level == "HIGH" and not skip_gates:
        console.print(
            "[red]COMPLEXITY_GATE_REJECTION[/] HIGH complexity tasks require "
            "--skip-gates to proceed"
        )
        raise typer.Exit(code=1)

    record = AdhocRecord(
        issue_id=f"adhoc-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        description=description,
        execution_mode=result.execution_mode,
        status="PENDING",
    )

    ledger_path = _adhoc_ledger_path()
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(record.model_dump_json() + "\n")

    console.print(
        f"[green]{result.execution_mode}[/] execution_mode={result.execution_mode}"
    )
    contract = {
        "status": "READY",
        "execution_mode": result.execution_mode,
        "description": description,
        "issue_id": record.issue_id,
    }
    print(json.dumps(contract, indent=2))


@adhoc_app.command()
def post(
    issue_id: str = typer.Argument(..., help="Issue/manifest ID to mark complete"),
) -> None:
    """Mark an ad-hoc record as completed."""
    ledger_path = _adhoc_ledger_path()
    records = _read_adhoc_ledger(ledger_path)

    found_idx = -1
    for idx, rec in enumerate(records):
        if rec.get("issue_id") == issue_id:
            found_idx = idx

    if found_idx == -1:
        console.print(
            f"[red]MANIFEST_NOT_FOUND[/] No record found with issue_id={issue_id}"
        )
        raise typer.Exit(code=1)

    records[found_idx]["status"] = "COMPLETED"
    records[found_idx]["timestamp"] = datetime.now(timezone.utc).isoformat()

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

    console.print(f"[green]COMPLETED[/] {issue_id}")
    contract = {
        "status": "COMPLETED",
        "issue_id": issue_id,
    }
    print(json.dumps(contract, indent=2))
