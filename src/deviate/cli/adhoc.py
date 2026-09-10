from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import typer

from deviate.cli._common import console
from deviate.core._shared import git_env as _git_env
from deviate.core.complexity import ClassificationResult, ComplexityGate
from deviate.core.convention import commit_scope, format_commit_message
from deviate.core.explore_routing import (
    ATTACH_EXISTING_EPIC,
    latest_explore_content,
    resolve_explore_routing,
)
from deviate.state.config import SessionState
from deviate.state.ledger import AdhocRecord

adhoc_app = typer.Typer(no_args_is_help=True)


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
    session_path = Path(".deviate") / "session.json"
    session = SessionState.load(session_path) if session_path.exists() else None
    routing = resolve_explore_routing(
        content=latest_explore_content(),
        session=session,
    )
    if routing.hitl_pending:
        _exit_with_error(
            "HITL_PENDING_ROUTING resolve attach vs new_epic vs adhoc "
            "in explore.md Status HITL_OVERRIDE or Pending HITL Decisions"
        )
    if routing.next_action == ATTACH_EXISTING_EPIC:
        epic_slug = routing.epic_slug
        if not epic_slug:
            _exit_with_error(
                "ATTACH_EPIC_MISSING NEXT_ACTION attach needs an epic slug"
            )
        epic_dir = Path("specs") / epic_slug
        if not epic_dir.is_dir():
            _exit_with_error(f"ATTACH_EPIC_NOT_FOUND {epic_slug}")
        _emit_contract(
            status="READY",
            execution_mode="ATTACH",
            description=description,
            attach_existing_epic=True,
            allocate_bucket=False,
            shared_prd=False,
            epic_slug=epic_slug,
            issue_dir=str(epic_dir / "issues"),
            prd_path=str(epic_dir / "prd.md"),
        )
        return

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

    # --- Resolve canonical issue path from record (created during /deviate-adhoc) ---
    ledger_path = _adhoc_ledger_path()
    records = _read_adhoc_ledger(ledger_path)
    found = records.get(issue_id)
    if found is None:
        _exit_with_error(f"MANIFEST_NOT_FOUND No record found with issue_id={issue_id}")

    source_file = str(found.get("source_file") or "").strip()
    if not source_file:
        candidate = root / "specs" / "adhoc" / "issues" / f"{issue_id}.md"
    else:
        candidate = Path(source_file)
        if not candidate.is_absolute():
            candidate = root / candidate
    _validate_no_gherkin_leak(candidate)

    # --- Commit step (skip if not a git repo) ---
    if (root / ".git").is_dir():
        subject = f"docs({commit_scope(issue_id)}): add issue"
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
    completed = found.copy()
    completed["status"] = "COMPLETED"
    completed["timestamp"] = datetime.now(timezone.utc).isoformat()
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(completed) + "\n")
    console.print(f"[green]COMPLETED[/] {issue_id}")

    _emit_contract(status="COMPLETED", issue_id=issue_id)


def _validate_no_gherkin_leak(issue_path: Path) -> None:
    if not issue_path.exists():
        return
    content = issue_path.read_text(encoding="utf-8")
    if not content.strip():
        return
    from deviate.core.validation import validate_acceptance_outline

    errors = validate_acceptance_outline(content)
    if errors:
        _exit_with_error(
            f"GHERKIN_LEAK_DETECTED {issue_path.name} invalid acceptance outline: "
            + "; ".join(errors)
        )
