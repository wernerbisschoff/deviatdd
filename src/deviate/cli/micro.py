from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console

from deviate.core.tamper import TamperContext, TamperGuard, TamperVerdict
from deviate.state.ledger import TaskRecord, append_task_transition

console = Console()

# Typer apps for manual phase commands
red_app = typer.Typer(no_args_is_help=True)
green_app = typer.Typer(no_args_is_help=True)

_LEDGER_GLOB = "specs/**/tasks.jsonl"


def _git_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _read_ledger_records(ledger_file: Path) -> list[dict]:
    records: list[dict] = []
    try:
        with open(ledger_file, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    records.append(json.loads(stripped))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return records


def _resolve_issue_number(task_id: str) -> str | None:
    m = re.match(r"^T(\d{3})$", task_id)
    if m:
        return m.group(1)
    m = re.match(r"^TSK-(\d{3})-\d{2}$", task_id)
    if m:
        return m.group(1)
    return None


def _resolve_task_index(task_id: str) -> int | None:
    m = re.match(r"^T\d{3}$", task_id)
    if m:
        return 1
    m = re.match(r"^TSK-\d{3}-(\d{2})$", task_id)
    if m:
        return int(m.group(1))
    return None


def _find_task_record(
    root: Path, issue_number: str, task_index: int
) -> tuple[dict, Path] | None:
    count = 0
    for ledger_file in sorted(root.glob(_LEDGER_GLOB)):
        for record in _read_ledger_records(ledger_file):
            if record.get("issue_id") == f"ISS-{issue_number}":
                count += 1
                if count == task_index:
                    return record, ledger_file
    return None


def _find_all_pending_tasks(root: Path) -> list[tuple[dict, Path]]:
    results: list[tuple[dict, Path]] = []
    for ledger_file in sorted(root.glob(_LEDGER_GLOB)):
        for record in _read_ledger_records(ledger_file):
            if record.get("status") == "PENDING":
                results.append((record, ledger_file))
    return results


def _append_status_transition(
    task_data: dict, new_status: str, ledger_path: Path
) -> None:
    record = TaskRecord(
        id=task_data["id"],
        issue_id=task_data.get("issue_id", ""),
        description=task_data.get("description", ""),
        status=new_status,
        execution_mode=task_data.get("execution_mode", "TDD"),
    )
    append_task_transition(record, ledger_path)


def _resolve_task_context(task_id: str | None, root: Path) -> tuple[dict, Path] | None:
    if task_id is not None:
        issue_number = _resolve_issue_number(task_id)
        if issue_number is None:
            console.print(
                f"[red]TASK_NOT_FOUND[/] Unrecognised task ID format: {task_id}"
            )
            raise typer.Exit(code=1)
        task_index = _resolve_task_index(task_id)
        if task_index is None:
            console.print(
                f"[red]TASK_NOT_FOUND[/] Unrecognised task ID format: {task_id}"
            )
            raise typer.Exit(code=1)
        result = _find_task_record(root, issue_number, task_index)
        if result is None:
            console.print(f"[red]TASK_NOT_FOUND[/] No task matching {task_id}")
            raise typer.Exit(code=1)
        return result

    pending = _find_all_pending_tasks(root)
    if not pending:
        console.print("[red]NO_PENDING_TASKS[/]")
        raise typer.Exit(code=1)
    return pending[0]


def _run_tdd_cycle(task: dict, ledger_path: Path, c: Console) -> None:
    tid = task.get("id", "?")
    c.print(f"  [bold blue]RED →[/] {tid}")
    _append_status_transition(task, "RED", ledger_path)
    c.print(f"  [bold green]GREEN →[/] {tid}")
    _append_status_transition(task, "GREEN", ledger_path)
    c.print(f"  [bold yellow]REFACTOR →[/] {tid}")
    _append_status_transition(task, "REFACTOR", ledger_path)
    _append_status_transition(task, "COMPLETED", ledger_path)
    c.print(f"  [bold green]COMPLETED[/] {tid}")


def _run_execute_phase(task: dict, ledger_path: Path, c: Console) -> None:
    tid = task.get("id", "?")
    c.print(f"  [bold green]EXECUTE →[/] {tid}")
    _append_status_transition(task, "COMPLETED", ledger_path)
    c.print(f"  [bold green]COMPLETED[/] {tid}")


def _dispatch_task(task: dict, ledger_path: Path, c: Console) -> None:
    mode = task.get("execution_mode", "TDD")
    c.print(f"[cyan]Processing {task.get('id', '?')} ({mode})[/]")
    if mode == "TDD":
        _run_tdd_cycle(task, ledger_path, c)
    else:
        _run_execute_phase(task, ledger_path, c)


def _run_single(task_id: str, root: Path, c: Console) -> None:
    result = _resolve_task_context(task_id, root)
    task, ledger_file = result
    status = task.get("status", "PENDING")

    if status == "COMPLETED":
        c.print(f"[yellow]TASK_ALREADY_DONE[/] {task_id} is already completed")
        raise typer.Exit(code=0)

    _dispatch_task(task, ledger_file, c)


def _run_all(root: Path, c: Console) -> None:
    pending = _find_all_pending_tasks(root)
    if not pending:
        c.print("[yellow]No PENDING tasks found[/]")
        raise typer.Exit(code=0)
    for task, ledger_file in pending:
        _dispatch_task(task, ledger_file, c)


def _find_test_files(root: Path) -> list[Path]:
    return sorted(root.glob("tests/**/test_*.py"))


def _find_source_files(root: Path) -> list[Path]:
    return sorted(root.glob("src/**/*.py"))


def _run_pytest(root: Path) -> subprocess.CompletedProcess:
    test_files = _find_test_files(root)
    test_file_list = [str(f) for f in test_files]
    return subprocess.run(
        [sys.executable, "-m", "pytest", *test_file_list, "-v"],
        cwd=root,
        capture_output=True,
        text=True,
    )


def _commit_phase(message: str, root: Path) -> bool:
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=root, env=_git_env()
    )
    unstaged = subprocess.run(["git", "diff", "--quiet"], cwd=root, env=_git_env())
    if staged.returncode != 0 or unstaged.returncode != 0:
        subprocess.run(["git", "add", "-A"], cwd=root, env=_git_env(), check=False)
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=root,
            env=_git_env(),
            check=False,
        )
        return True
    return False


_SYNTAX_ERROR_MARKERS = frozenset(
    {
        "SyntaxError",
        "IndentationError",
        "TabError",
        "ImportError",
        "ModuleNotFoundError",
    }
)


def _classify_pytest_outcome(stdout: str, stderr: str, returncode: int) -> str | None:
    combined = stdout + "\n" + stderr
    if returncode == 0:
        return "PASS"
    for marker in _SYNTAX_ERROR_MARKERS:
        if marker in combined:
            return "SYNTAX_ERROR"
    if "AssertionError" in combined or "failed" in stdout:
        return "ASSERTION_FAILURE"
    return "UNKNOWN_FAILURE"


@red_app.command(name="pre")
def red_pre(
    task: str | None = typer.Option(None, "--task", "-t", help="Task ID"),
) -> None:
    root = Path.cwd()
    task_data, ledger_path = _resolve_task_context(task, root)

    spec_dir = str(ledger_path.parent)

    contract = {
        "task_id": task_data.get("id", ""),
        "test_command": "pytest tests/ -v",
        "lint_command": "ruff check .",
        "spec_dir": spec_dir,
    }
    print(json.dumps(contract, ensure_ascii=False))
    raise typer.Exit(code=0)


@red_app.command(name="post")
def red_post() -> None:
    root = Path.cwd()
    test_files = _find_test_files(root)

    if not test_files:
        console.print("[red]TEST_NOT_FOUND[/]")
        raise typer.Exit(code=1)

    proc = _run_pytest(root)
    outcome = _classify_pytest_outcome(proc.stdout, proc.stderr, proc.returncode)

    if outcome == "PASS":
        console.print("[red]RedMustPassError:[/] Test passed, expected a failing test")
        raise typer.Exit(code=1)

    if outcome == "SYNTAX_ERROR":
        console.print("[red]SyntaxCrashRejected:[/] Test file contains syntax errors")
        raise typer.Exit(code=1)

    _commit_phase("feat: RED phase - failing test", root)

    console.print("[green]RED_POST_OK[/]")
    raise typer.Exit(code=0)


@green_app.command(name="pre")
def green_pre(
    task: str | None = typer.Option(None, "--task", "-t", help="Task ID"),
) -> None:
    root = Path.cwd()
    task_data, ledger_path = _resolve_task_context(task, root)

    test_files = _find_test_files(root)
    src_files = _find_source_files(root)

    contract = {
        "test_file": str(test_files[0]) if test_files else "",
        "implementation_targets": [str(f) for f in src_files],
    }
    print(json.dumps(contract, ensure_ascii=False))
    raise typer.Exit(code=0)


@green_app.command(name="post")
def green_post() -> None:
    root = Path.cwd()
    test_files = _find_test_files(root)

    if not test_files:
        console.print("[red]TEST_NOT_FOUND[/]")
        raise typer.Exit(code=1)

    proc = _run_pytest(root)

    if proc.returncode != 0:
        console.print("[red]Tests failed:[/] Implementation does not pass tests")
        raise typer.Exit(code=1)

    tamper_verdict = TamperGuard.evaluate(
        context=TamperContext.GREEN_IMPLEMENTATION, repo_path=root
    )

    if tamper_verdict == TamperVerdict.TAMPER_DETECTED:
        console.print("[yellow]TAMPER_DETECTED[/]")

    committed = _commit_phase("feat: GREEN phase - implementation passes tests", root)

    if committed:
        console.print("[green]GREEN_POST_OK[/]")
    else:
        console.print("[yellow]YELLOW_TRIGGERED[/]")

    raise typer.Exit(code=0)


def run_command(
    task_id: str | None = typer.Argument(
        None, help="Task ID (TNNN or TSK-NNN-NN format)"
    ),
    all_tasks: bool = typer.Option(False, "--all", help="Run all PENDING tasks"),
) -> None:
    """Run dispatcher: route task by execution_mode to TDD cycle or execute phase."""
    if not task_id and not all_tasks:
        console.print("[red]ERROR[/] Provide a task ID or use --all")
        raise typer.Exit(code=1)

    root = Path.cwd()

    if all_tasks:
        _run_all(root, console)
        raise typer.Exit(code=0)

    assert task_id is not None
    _run_single(task_id, root, console)
