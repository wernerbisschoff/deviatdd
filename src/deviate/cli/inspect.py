from __future__ import annotations

import json
import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from deviate.cli.meso import _resolve_bucket_dir, _source_stem
from deviate.core._shared import git_env as _git_env
from deviate.core.worktree import detect_remote
from deviate.state.ledger import (
    IssueRecord,
    LedgerFilter,
    _read_ledger_strict,
    filter_tasks,
)

inspect_app = typer.Typer(no_args_is_help=True)
issues_app = typer.Typer(no_args_is_help=True)
tasks_app = typer.Typer(no_args_is_help=True)
inspect_app.add_typer(issues_app, name="issues")
inspect_app.add_typer(tasks_app, name="tasks")

console = Console()


def _derive_issue_branch(source_file: str) -> str:
    bucket = _resolve_bucket_dir(source_file)
    slug = _source_stem(source_file)
    return f"feat/{bucket}/{slug}"


def _check_orphan_claim(issue: IssueRecord, repo: Path) -> bool | None:
    if not issue.source_file:
        return None
    branch = _derive_issue_branch(issue.source_file)
    try:
        remote = detect_remote(repo)
    except RuntimeError:
        return None
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", remote, branch],
            cwd=repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    return not bool(result.stdout.strip())


def _deduplicate_issues(records: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for rec in records:
        issue_id = rec.get("issue_id")
        if issue_id:
            seen[issue_id] = rec
    return list(seen.values())


def _issues_list(
    type_filter: str | None = None,
    status_filter: str | None = None,
) -> list[dict]:
    ledger_path = Path.cwd() / "specs" / "issues.jsonl"
    records = _read_ledger_strict(ledger_path)
    issues = _deduplicate_issues(records)
    if type_filter:
        issues = [i for i in issues if i.get("type") == type_filter]
    if status_filter:
        issues = [i for i in issues if i.get("status") == status_filter]
    result: list[dict] = []
    for raw in issues:
        entry: dict = {
            "issue_id": raw.get("issue_id", ""),
            "type": raw.get("type", ""),
            "title": raw.get("title", ""),
            "status": raw.get("status", ""),
            "source_file": raw.get("source_file", ""),
            "blocked_by": raw.get("blocked_by", []),
            "coordinates_with": raw.get("coordinates_with", []),
        }
        if raw.get("status") == "SPECIFIED":
            try:
                issue_record = IssueRecord.model_validate(raw)
                orphan = _check_orphan_claim(issue_record, Path.cwd())
                entry["orphan_claim"] = orphan
            except Exception:
                entry["orphan_claim"] = None
        else:
            entry["orphan_claim"] = None
        result.append(entry)
    return result


@issues_app.command("list")
def issues_list_command(
    type_filter: str | None = typer.Option(None, "--type", help="Filter by issue type"),
    status_filter: str | None = typer.Option(
        None, "--status", help="Filter by issue status"
    ),
    json_flag: bool = typer.Option(False, "--json", help="Output as JSON array"),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress non-JSON output"),
) -> None:
    issues = _issues_list(
        type_filter=type_filter,
        status_filter=status_filter,
    )
    if json_flag:
        typer.echo(json.dumps(issues))
    elif quiet:
        pass
    else:
        table = Table(title="Issues")
        table.add_column("ID", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Title")
        table.add_column("Status", style="green")
        table.add_column("Orphan")
        for issue in issues:
            orphan_str = ""
            if issue.get("orphan_claim") is True:
                orphan_str = "\U0001f7e1 ORPHAN_CLAIM"
            elif issue.get("orphan_claim") is False:
                orphan_str = ""
            table.add_row(
                issue.get("issue_id", ""),
                issue.get("type", ""),
                issue.get("title", ""),
                issue.get("status", ""),
                orphan_str,
            )
        console.print(table)


def _tasks_list(
    status_filter: str | None = None,
) -> list[dict]:
    tasks_ledger = Path.cwd() / "tasks.jsonl"
    filter_obj = LedgerFilter(
        entity_type="task",
        status_filter=status_filter or None,
    )
    records = filter_tasks(tasks_ledger, filter_obj)
    return [
        {
            "id": t.id,
            "issue_id": t.issue_id,
            "description": t.description,
            "status": t.status,
            "execution_mode": t.execution_mode,
        }
        for t in records
    ]


@tasks_app.command("list")
def tasks_list_command(
    status_filter: str | None = typer.Option(
        None, "--status", help="Filter by task status"
    ),
    json_flag: bool = typer.Option(False, "--json", help="Output as JSON array"),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress non-JSON output"),
) -> None:
    tasks = _tasks_list(
        status_filter=status_filter,
    )
    if json_flag:
        typer.echo(json.dumps(tasks))
    elif quiet:
        pass
    else:
        table = Table(title="Tasks")
        table.add_column("ID", style="cyan")
        table.add_column("Issue ID")
        table.add_column("Description")
        table.add_column("Status", style="green")
        table.add_column("Mode", style="magenta")
        for task in tasks:
            table.add_row(
                task.get("id", ""),
                task.get("issue_id", ""),
                task.get("description", ""),
                task.get("status", ""),
                task.get("execution_mode", ""),
            )
        console.print(table)
