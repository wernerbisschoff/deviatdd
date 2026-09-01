from __future__ import annotations

import json
import subprocess
import warnings
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from deviate.cli.meso import _resolve_bucket_dir, _source_stem
from deviate.core._shared import git_env as _git_env
from deviate.core.worktree import detect_remote
from deviate.state.ledger import (
    IssueRecord,
    _read_ledger_strict,
)

inspect_app = typer.Typer(no_args_is_help=True)
issues_app = typer.Typer(no_args_is_help=True)
tasks_app = typer.Typer(no_args_is_help=True)
inspect_app.add_typer(issues_app, name="issues")
inspect_app.add_typer(tasks_app, name="tasks")


@issues_app.command("show")
def issues_show_command(
    target_id: str = typer.Argument(..., help="Issue ID to inspect"),
    json_flag: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    issue = next(
        (item for item in _issues_list() if item.get("issue_id") == target_id), None
    )
    if issue is None:
        raise typer.BadParameter(f"Unknown issue ID: {target_id}")
    typer.echo(json.dumps(issue) if json_flag else str(issue))


@tasks_app.command("show")
def tasks_show_command(
    target_id: str = typer.Argument(..., help="Task ID to inspect"),
    json_flag: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    task = next((item for item in _tasks_list() if item.get("id") == target_id), None)
    if task is None:
        raise typer.BadParameter(f"Unknown task ID: {target_id}")
    typer.echo(json.dumps(task) if json_flag else str(task))


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
    """Deduplicate issue records by ``issue_id``.

    ``COMPLETED`` is a terminal status and always takes precedence: once any
    ``COMPLETED`` entry is captured for an issue, subsequent non-``COMPLETED``
    transitions (e.g. a ``SPECIFIED`` entry appended after the ``COMPLETED``
    write during a merge flow) do not override it. Among non-``COMPLETED``
    entries, the last entry by file position wins (the prior behaviour).
    """
    seen: dict[str, dict] = {}
    for rec in records:
        issue_id = rec.get("issue_id")
        if not issue_id:
            continue
        current = seen.get(issue_id)
        # Preserve any COMPLETED entry already captured — COMPLETED is terminal.
        if current is not None and current.get("status") == "COMPLETED":
            continue
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


def _tasks_dir_from_source(source_file: str) -> Path | None:
    """Map a ``source_file`` path to its per-issue tasks ledger directory.

    ``source_file`` follows ``specs/<bucket>/issues/<slug>.md`` (where
    ``<bucket>`` is e.g. ``001-…``, ``002-…``, or ``adhoc``). Tasks live under
    ``specs/<bucket>/<slug>/tasks.jsonl`` — the ``issues/`` segment is dropped
    because the tasks ledger is sibling to the bucket root, not nested under
    ``issues/``.

    Returns ``None`` if the path doesn't match the expected shape so callers
    can skip malformed entries instead of crashing on unrelated source files.
    """
    parts = Path(source_file).parts
    # Expect ['specs', '<bucket>', 'issues', '<slug>.md'].
    if len(parts) != 4 or parts[0] != "specs" or parts[2] != "issues":
        return None
    bucket, slug_md = parts[1], parts[3]
    if not slug_md.endswith(".md"):
        return None
    return Path("specs") / bucket / slug_md[:-3]


def _latest_completed_wins(records: list[dict]) -> dict:
    """Reduce a task's sequential ledger entries to one record.

    Mirrors ``_deduplicate_issues``: ``COMPLETED`` is terminal — once captured,
    no later non-``COMPLETED`` transition may override it. Among non-terminal
    entries, the last by file position wins. ``None``-valued status is ignored
    so that legacy entries with missing fields don't poison the precedence
    chain.
    """
    last: dict | None = None
    for rec in records:
        status = rec.get("status")
        if last is not None and last.get("status") == "COMPLETED":
            if status != "COMPLETED":
                continue
        last = rec
    return last if last is not None else {}


def _tasks_list(
    status_filter: str | None = None,
) -> list[dict]:
    repo = Path.cwd()
    issues_ledger = repo / "specs" / "issues.jsonl"
    issue_records = _read_ledger_strict(issues_ledger) if issues_ledger.exists() else []
    issues = _deduplicate_issues(issue_records)

    by_task: dict[str, dict] = {}
    for issue in issues:
        source_file = issue.get("source_file") or ""
        tasks_dir = _tasks_dir_from_source(source_file)
        if tasks_dir is None:
            continue
        tasks_ledger = repo / tasks_dir / "tasks.jsonl"
        if not tasks_ledger.exists():
            continue
        try:
            raw_records = _read_ledger_strict(tasks_ledger)
        except ValueError:
            # Malformed per-issue ledger: surface to the caller via stderr but
            # don't abort the whole aggregation. Existing strict semantics
            # for ``specs/issues.jsonl`` are preserved by re-raising there.
            warnings.warn(
                f"Skipping malformed tasks ledger: {tasks_ledger}", stacklevel=2
            )
            continue
        # Group this issue's records by task id (sequential-ledger parsed in
        # file order), then reduce to one record per task.
        per_task: dict[str, list[dict]] = {}
        order: list[str] = []
        for rec in raw_records:
            tid = rec.get("id")
            if not tid:
                continue
            if tid not in per_task:
                order.append(tid)
                per_task[tid] = []
            per_task[tid].append(rec)
        for tid in order:
            current = by_task.get(tid)
            latest = _latest_completed_wins(per_task[tid])
            # If we already aggregate a record for this task across another
            # issue (rare — task ids are normally issue-scoped — but the
            # append-only protocol does not forbid cross-issue collisions),
            # merge via the same COMPLETED-sticky rule.
            if current is None:
                by_task[tid] = latest
                continue
            merged_status = current.get("status")
            if merged_status == "COMPLETED":
                # Sticky: keep current.
                continue
            if latest.get("status") == "COMPLETED":
                by_task[tid] = latest
                continue
            # Both non-terminal: last by file position wins. The newer ledger
            # (this issue) was appended after the prior issue, so it wins.
            by_task[tid] = latest

    rows = []
    for t in by_task.values():
        row = {
            "id": t["id"],
            "issue_id": t.get("issue_id", ""),
            "description": t.get("description", ""),
            "status": t.get("status", ""),
            "execution_mode": t.get("execution_mode", ""),
        }
        if t.get("evidence"):
            row["evidence"] = t["evidence"]
        rows.append(row)
    if status_filter:
        rows = [r for r in rows if r.get("status") == status_filter]
    rows.sort(key=lambda r: r.get("id") or "")
    return rows


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
