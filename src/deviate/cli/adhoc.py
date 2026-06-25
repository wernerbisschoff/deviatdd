from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import typer

from deviate.cli._common import console
from deviate.core.complexity import ClassificationResult, ComplexityGate
from deviate.state.ledger import AdhocRecord

adhoc_app = typer.Typer(no_args_is_help=True)

_FLOW_REF_PATTERN = re.compile(r"^FLOW-\d{2,}$")
_FLOW_REF_FORMAT_HINT = "expected format: FLOW-XX with at least two digits"


def _adhoc_ledger_path() -> Path:
    return Path.cwd() / "specs" / "adhoc.jsonl"


def _exit_with_error(message: str, code: int = 1) -> None:
    console.print(f"[red]{message}[/]")
    raise typer.Exit(code=code)


def _read_adhoc_ledger(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    records: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if isinstance(rec, dict):
                    issue_id = rec.get("issue_id")
                    if issue_id:
                        records[issue_id] = rec
            except json.JSONDecodeError:
                continue
    return records


def _emit_contract(status: str, **fields: object) -> None:
    contract: dict[str, object] = {"status": status, **fields}
    print(json.dumps(contract, indent=2))


def _parse_flow_refs(raw: str | None) -> list[str]:
    if raw is None:
        return []
    tokens = [token.strip() for token in raw.split(",") if token.strip()]
    for token in tokens:
        if not _FLOW_REF_PATTERN.match(token):
            _exit_with_error(
                f"INVALID_FLOW_REF {token!r} is not a valid flow ID "
                f"({_FLOW_REF_FORMAT_HINT})"
            )
    return tokens


@adhoc_app.command()
def pre(
    description: str = typer.Argument(..., help="Task description to classify"),
    skip_gates: bool = typer.Option(
        False,
        "--skip-gates",
        help="Skip complexity gate rejection for HIGH complexity tasks",
    ),
    flow_ref: str | None = typer.Option(
        None,
        "--flow-ref",
        help="Comma-separated FLOW-XX IDs (e.g. FLOW-01,FLOW-02)",
    ),
) -> None:
    """Classify an ad-hoc task description and record it for execution."""
    flow_refs = _parse_flow_refs(flow_ref)
    result: ClassificationResult = ComplexityGate.classify(description)

    if result.level == "HIGH" and not skip_gates:
        _exit_with_error(
            "COMPLEXITY_GATE_REJECTION HIGH complexity tasks require "
            "--skip-gates to proceed"
        )

    record = AdhocRecord(
        issue_id=f"adhoc-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        description=description,
        execution_mode=result.execution_mode,
        status="PENDING",
        flow_refs=flow_refs,
    )

    ledger_path = _adhoc_ledger_path()
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(record.model_dump_json() + "\n")

    console.print(
        f"[green]{result.execution_mode}[/] execution_mode={result.execution_mode}"
    )
    _emit_contract(
        status="READY",
        execution_mode=result.execution_mode,
        description=description,
        issue_id=record.issue_id,
        flow_refs=flow_refs,
    )


@adhoc_app.command()
def post(
    issue_id: str = typer.Argument(..., help="Issue/manifest ID to mark complete"),
) -> None:
    """Mark an ad-hoc record as completed."""
    ledger_path = _adhoc_ledger_path()
    records = _read_adhoc_ledger(ledger_path)

    found = records.get(issue_id)

    if found is None:
        _exit_with_error(f"MANIFEST_NOT_FOUND No record found with issue_id={issue_id}")

    completed = found.copy()
    completed["status"] = "COMPLETED"
    completed["timestamp"] = datetime.now(timezone.utc).isoformat()

    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(completed) + "\n")

    console.print(f"[green]COMPLETED[/] {issue_id}")
    _emit_contract(status="COMPLETED", issue_id=issue_id)
