from __future__ import annotations

import inspect
import json
import re
import subprocess
from contextlib import redirect_stdout
from functools import wraps
from io import StringIO
from pathlib import Path

import typer
from rich.console import Console

from deviate.core._shared import git_env as _git_env
from deviate.core.constitution import resolve_constitution, validate_constitution
from deviate.state.config import TransitionViolationError

console = Console()


def with_json_quiet(func):
    """Decorator that injects ``--json`` and ``--quiet`` options into a Typer command.

    ``--json``: capture stdout, serialize the command's return value as JSON,
    print only JSON to stdout.

    ``--quiet``: suppress stdout while preserving stderr output.

    Flags are orthogonal: ``--json --quiet`` emits JSON on stdout and errors
    on stderr.
    """
    sig = inspect.signature(func)
    orig_params = list(sig.parameters.values())

    new_params = list(orig_params)
    new_params.extend(
        [
            inspect.Parameter(
                "json",
                inspect.Parameter.KEYWORD_ONLY,
                default=typer.Option(
                    False, "--json", help="Output result as JSON contract"
                ),
                annotation=bool,
            ),
            inspect.Parameter(
                "quiet",
                inspect.Parameter.KEYWORD_ONLY,
                default=typer.Option(False, "--quiet", help="Suppress non-JSON output"),
                annotation=bool,
            ),
        ]
    )

    @wraps(func)
    def wrapper(**kwargs: object) -> object:
        json_flag = kwargs.pop("json", False)
        quiet_flag = kwargs.pop("quiet", False)

        def _captured() -> object:
            buf = StringIO()
            with redirect_stdout(buf):
                return func(**kwargs)

        if json_flag:
            result = _captured()
            typer.echo(json.dumps(result))
        elif quiet_flag:
            result = _captured()
        else:
            result = func(**kwargs)
        return result

    wrapper.__signature__ = sig.replace(parameters=new_params)
    return wrapper


def _extract_epic_num(slug: str) -> str:
    """Extract the leading numeric prefix from an epic slug.

    ``001-deviate-cli-bootstrapping`` → ``001``
    """
    m = re.match(r"(\d+)", slug)
    return m.group(1) if m else slug


def _extract_issue_num(issue_id: str) -> str:
    """Extract the numeric suffix from an issue ID.

    ``ISS-001-006`` → ``006``, ``TSK-042`` → ``042``
    """
    m = re.search(r"-(\d+)$", issue_id)
    return m.group(1) if m else issue_id


def _halt(phase: str, message: str) -> None:
    console.print(f"[red]{phase}_HALTED: {message}[/]")
    raise typer.Exit(code=1)


def _handle_missing_dot_dir(phase: str) -> None:
    _halt(phase, ".deviate/ not found, run 'deviate init' first")


def _handle_transition_error(phase: str, error: TransitionViolationError) -> None:
    _halt(phase, str(error))


def _validate_constitution(phase: str = "CONSTITUTION") -> Path:
    try:
        const_path = resolve_constitution(Path.cwd())
        if not validate_constitution(const_path):
            _halt(phase, "constitution validation failed")
        return const_path
    except FileNotFoundError:
        _halt(phase, "constitution.md not found")


def _load_manifest(path: Path, phase: str) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError) as e:
        _halt(phase, f"invalid manifest at {path} — {e}")


def _run_pre_commit_hooks(worktree_path: Path | None = None) -> None:
    """Ensure .githooks/ is configured as hooks path if the directory exists."""
    repo = worktree_path or Path.cwd()
    githooks_dir = repo / ".githooks"
    if not githooks_dir.is_dir():
        console.print("[dim]PRE_COMMIT_SKIP[/] no .githooks/ directory")
        return
    try:
        subprocess.run(
            ["git", "config", "core.hooksPath", str(githooks_dir)],
            cwd=repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        console.print("[green]PRE_COMMIT_HOOKS[/] hooks path set to .githooks/")
    except subprocess.CalledProcessError:
        console.print("[yellow]PRE_COMMIT_WARN[/] could not set hooks path")
