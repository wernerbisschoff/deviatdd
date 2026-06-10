from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console

from deviate.core.tamper import TamperContext, TamperGuard, TamperVerdict
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord, append_task_transition

console = Console()

# Typer apps for manual phase commands
red_app = typer.Typer(no_args_is_help=True)
green_app = typer.Typer(no_args_is_help=True)
yellow_app = typer.Typer(no_args_is_help=True)
judge_app = typer.Typer(no_args_is_help=True)
refactor_app = typer.Typer(no_args_is_help=True)

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


# ---------------------------------------------------------------------------
# YELLOW commands
# ---------------------------------------------------------------------------


def _detect_phase_changes(root: Path) -> list[str]:
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    )
    files: list[str] = []
    for line in status.stdout.splitlines():
        raw = line.rstrip("\n")
        if not raw.strip():
            continue
        filename = raw[3:]
        files.append(filename)

    expanded: list[str] = []
    for f in files:
        if f.endswith("/"):
            full_dir = root / f
            if full_dir.is_dir():
                for py_file in sorted(full_dir.rglob("*.py")):
                    rel = py_file.relative_to(root)
                    expanded.append(str(rel))
            else:
                expanded.append(f)
        else:
            expanded.append(f)
    return expanded


@yellow_app.command(name="pre")
def yellow_pre(
    task: str | None = typer.Option(None, "--task", "-t", help="Task ID"),
) -> None:
    root = Path.cwd()
    _resolve_task_context(task, root)

    changed = _detect_phase_changes(root)
    test_files = [str(f) for f in _find_test_files(root)]

    contract = {
        "proposed_changes": changed,
        "rationale": "YELLOW phase — review proposed test amendments",
        "test_files": test_files,
    }
    print(json.dumps(contract, ensure_ascii=False))
    raise typer.Exit(code=0)


@yellow_app.command(name="post")
def yellow_post(
    approved: bool = typer.Option(False, "--approved", help="Approve amendments"),
    rejected: bool = typer.Option(False, "--rejected", help="Reject amendments"),
) -> None:
    root = Path.cwd()
    dot_dir = root / ".deviate"
    session_path = dot_dir / "session.json"
    session = SessionState.load(session_path)

    changed = _detect_phase_changes(root)

    if not changed:
        console.print("NO_CHANGES_PROPOSED")
        raise typer.Exit(code=0)

    if approved:
        _commit_phase("feat: YELLOW phase — approved amendments", root)
        session = session.force_transition_to("GREEN")
        session.save(session_path)
        console.print("[green]YELLOW_POST_OK[/]")

    if rejected:
        subprocess.run(["git", "restore", "."], cwd=root, env=_git_env(), check=False)
        session = session.force_transition_to("GREEN")
        session.save(session_path)
        console.print("[yellow]YELLOW_REVERTED[/]")

    raise typer.Exit(code=0)


# ---------------------------------------------------------------------------
# JUDGE commands
# ---------------------------------------------------------------------------


def _find_protected_modules(root: Path) -> list[str]:
    modules: list[str] = []
    for spec_file in sorted(root.glob("specs/**/spec.md")):
        content = spec_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("Module:"):
                module_path = stripped[len("Module:") :].strip()
                modules.append(module_path)
    return modules


@judge_app.command(name="pre")
def judge_pre() -> None:
    root = Path.cwd()
    changed = _detect_phase_changes(root)

    protected = _find_protected_modules(root)
    violations: list[dict[str, str]] = []
    for changed_file in changed:
        for protected_path in protected:
            changed_normalized = changed_file.rstrip("/")
            if changed_normalized == protected_path:
                violations.append(
                    {
                        "file": changed_file,
                        "protected_module": protected_path,
                    }
                )
            elif protected_path.startswith(changed_normalized + "/"):
                violations.append(
                    {
                        "file": changed_file,
                        "protected_module": protected_path,
                    }
                )

    if not changed and not violations:
        pass

    verdict = {
        "verdict": "COMPLIANCE_VIOLATION" if violations else "COMPLIANCE_PASS",
        "details": violations,
    }
    print(json.dumps(verdict, ensure_ascii=False))
    raise typer.Exit(code=0)


# ---------------------------------------------------------------------------
# REFACTOR commands
# ---------------------------------------------------------------------------


def _normalize_pytest_output(output: str) -> str:
    lines: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("==="):
            continue
        if "collected " in stripped and "item" in stripped:
            continue
        if stripped.startswith(".") and stripped.endswith("%]"):
            continue
        lines.append(stripped)
    return "\n".join(lines)


@refactor_app.command(name="pre")
def refactor_pre(
    task: str | None = typer.Option(None, "--task", "-t", help="Task ID"),
) -> None:
    root = Path.cwd()
    _resolve_task_context(task, root)

    src_files = [str(f) for f in _find_source_files(root)]

    contract = {"files_to_refactor": src_files}
    print(json.dumps(contract, ensure_ascii=False))
    raise typer.Exit(code=0)


_RETURN_TYPE_MAP = {
    "str": (ast.Constant, ast.JoinedStr),
    "int": (ast.Constant,),
    "float": (ast.Constant,),
    "bool": (ast.Constant,),
    "list": (ast.List,),
    "dict": (ast.Dict,),
    "tuple": (ast.Tuple,),
    "set": (ast.Set,),
}


def _check_return_type_mismatch(filepath: str) -> list[str]:
    issues: list[str] = []
    try:
        with open(filepath, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=filepath)
    except SyntaxError:
        return issues

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.returns is None:
            continue

        return_annotation: str | None = None
        if isinstance(node.returns, ast.Name):
            return_annotation = node.returns.id
        elif isinstance(node.returns, ast.Constant) and isinstance(
            node.returns.value, str
        ):
            return_annotation = node.returns.value

        if return_annotation is None:
            continue

        for child in ast.walk(node):
            if not isinstance(child, ast.Return) or child.value is None:
                continue
            if _is_return_type_mismatch(child.value, return_annotation):
                issues.append(
                    f"{node.name}: return value type mismatch (expected {return_annotation})"
                )
                break
    return issues


def _is_return_type_mismatch(
    value: ast.expr,
    expected: str,
) -> bool:
    if isinstance(value, ast.Constant):
        type_map = {"str": str, "int": int, "float": (int, float), "bool": bool}
        if expected in type_map:
            return not isinstance(value.value, type_map[expected])
        return True

    if expected == "str" and isinstance(value, ast.JoinedStr):
        return False
    if expected == "list" and isinstance(value, ast.List):
        return False
    if expected == "dict" and isinstance(value, ast.Dict):
        return False
    if expected == "tuple" and isinstance(value, ast.Tuple):
        return False
    if expected == "set" and isinstance(value, ast.Set):
        return False
    return False


@refactor_app.command(name="post")
def refactor_post() -> None:
    root = Path.cwd()
    dot_dir = root / ".deviate"
    session_path = dot_dir / "session.json"
    SessionState.load(session_path)

    test_files = _find_test_files(root)

    if not test_files:
        console.print("[yellow]NO_TESTS_TO_CHECK[/]")
        raise typer.Exit(code=0)

    proc_before = _run_pytest(root)
    before_returncode = proc_before.returncode
    before_output = _normalize_pytest_output(proc_before.stdout)

    changed = _detect_phase_changes(root)
    for changed_file in changed:
        full_path = root / changed_file
        if full_path.suffix == ".py" and full_path.exists():
            type_issues = _check_return_type_mismatch(str(full_path))
            if type_issues:
                subprocess.run(
                    ["git", "restore", "."], cwd=root, env=_git_env(), check=False
                )
                console.print(
                    "[red]RefactorRegressionError:[/] " + "; ".join(type_issues)
                )
                raise typer.Exit(code=1)

    proc_after = _run_pytest(root)
    after_returncode = proc_after.returncode
    after_output = _normalize_pytest_output(proc_after.stdout)

    if after_returncode != before_returncode or after_output != before_output:
        subprocess.run(["git", "restore", "."], cwd=root, env=_git_env(), check=False)
        console.print(
            "[red]RefactorRegressionError:[/] Test regression detected after refactor"
        )
        raise typer.Exit(code=1)

    committed = _commit_phase("feat: REFACTOR phase — code cleanup", root)

    if committed:
        console.print("[green]REFACTOR_POST_OK[/]")
    else:
        console.print("[yellow]NOTHING_CHANGED[/]")

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
