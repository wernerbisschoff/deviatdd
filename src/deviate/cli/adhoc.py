from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import typer

from deviate.cli._common import console
from deviate.core._shared import git_env as _git_env
from deviate.core.complexity import ClassificationResult, ComplexityGate
from deviate.core.convention import format_commit_message
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
    issue_id: str = typer.Argument(..., help="Issue/manifest ID"),
    title: str = typer.Option(
        "", "--title", "-t", help="Issue title for commit message"
    ),
) -> None:
    """Stage, commit ad-hoc issue artifacts, and mark record as completed."""
    root = Path.cwd()

    # --- Commit step (skip if not a git repo) ---
    if (root / ".git").is_dir():
        subject = f"docs(adhoc): add issue {issue_id}"
        if title:
            subject += f" - {title}"
        message = format_commit_message(subject, root)

        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=root, env=_git_env()
        )
        unstaged = subprocess.run(["git", "diff", "--quiet"], cwd=root, env=_git_env())
        untracked = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        )
        has_untracked = bool(untracked.stdout.strip())

        if staged.returncode != 0 or unstaged.returncode != 0 or has_untracked:
            subprocess.run(["git", "add", "-A"], cwd=root, env=_git_env(), check=False)
            result = subprocess.run(
                ["git", "commit", "-m", message, "--no-verify"],
                cwd=root,
                env=_git_env(),
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                console.print(f"[green]COMMITTED[/] adhoc issue {issue_id}")
            else:
                console.print(f"[red]COMMIT_FAILED[/] {result.stderr.strip()}")
                raise typer.Exit(code=1)
        else:
            console.print("[yellow]COMMIT_SKIP[/] no changes to commit")
    else:
        console.print("[dim]COMMIT_SKIP[/] not a git repository")

    # --- Mark adhoc record as COMPLETED ---
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
