from __future__ import annotations

import importlib.resources
import json
import re
from pathlib import Path
from typing import NoReturn

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt

from deviate.core.commit import commit_artifact
from deviate.core.constitution import (
    extract_commands,
    validate_constitution,
    validate_sections,
)
from deviate.ui.render import is_interactive

constitution_app = typer.Typer(no_args_is_help=True)
console = Console()


def _fail_with(reason: str) -> NoReturn:
    print(json.dumps({"status": "FAILURE", "reason": reason}))
    raise typer.Exit(code=1)


def _read_seed(filename: str) -> str | None:
    try:
        seed = importlib.resources.files("deviate.prompts").joinpath(filename)
        return seed.read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError):
        console.print(f"  [red]ERROR[/] {filename} not found in package")
        return None


def _detect_pyproject_value(keys: list[str]) -> str | None:
    pyproject = Path.cwd() / "pyproject.toml"
    if not pyproject.exists():
        return None
    try:
        import tomllib

        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        for key in keys:
            val: object = data
            for part in key.split("."):
                if isinstance(val, dict):
                    val = val.get(part)
                else:
                    return None
            if val is not None:
                return str(val)
    except Exception:
        pass
    return None


@constitution_app.command()
def generate(
    force: bool = typer.Option(
        False, "--force", help="Overwrite existing constitution.md"
    ),
    non_interactive: bool = typer.Option(
        False, "--non-interactive", help="Skip prompts, use detected defaults"
    ),
) -> None:
    """Generate or update specs/constitution.md interactively."""
    specs_dir = Path.cwd() / "specs"
    const_path = specs_dir / "constitution.md"

    if const_path.exists() and not force:
        console.print(
            "  [yellow]SKIP[/] specs/constitution.md already exists. Use --force to overwrite."
        )
        return

    seed = _read_seed("constitution_seed.md")
    if seed is None:
        raise typer.Exit(code=1)

    interactive = is_interactive() and not non_interactive

    if interactive:
        console.print("\n[bold]Detecting project settings...[/bold]")

    project_name = _detect_pyproject_value(["project.name"]) or "my-project"
    python_ver = (
        _detect_pyproject_value(["project.requires-python"])
        or _detect_pyproject_value(["tool.mypy.python_version"])
        or "3.13"
    )
    python_ver = re.sub(r"\D", "", python_ver) or "3.13"
    if len(python_ver) > 1 and python_ver[0] == "3":
        python_ver = f"3.{python_ver[1:]}" if len(python_ver) > 1 else "3.13"
    test_runner = (
        _detect_pyproject_value(["tool.pytest.ini_options"])
        and "pytest"
        or _detect_pyproject_value(["tool.unittest"])
        and "unittest"
        or "pytest"
    )
    linter = _detect_pyproject_value(["tool.ruff"]) and "ruff" or "flake8"
    pkg_manager = (
        _detect_pyproject_value(["tool.uv"])
        and "uv"
        or (_detect_pyproject_value(["tool.poetry"]) and "poetry" or "pip")
    )

    has_cli_entry = bool(_detect_pyproject_value(["project.scripts"]))
    target_type = "CLI application" if has_cli_entry else "Library"

    if interactive:
        console.print("\n[bold]Constitution Configuration[/bold]")
        target_type = Prompt.ask("Project target", default=target_type)
        project_name = Prompt.ask("Project name", default=project_name)
        python_ver = Prompt.ask("Python version", default=python_ver)
        test_runner = Prompt.ask("Test runner", default=test_runner)
        linter = Prompt.ask("Linter", default=linter)
        pkg_manager = Prompt.ask("Package manager", default=pkg_manager)

    content = seed
    content = content.replace("Python 3.13", f"Python {python_ver}")
    content = content.replace(
        "Target: CLI application (`deviate`)",
        f"Target: {target_type} (`{project_name}`)",
    )
    content = content.replace(
        "Package manager: `uv`", f"Package manager: `{pkg_manager}`"
    )
    content = content.replace("Test runner: `pytest`", f"Test runner: `{test_runner}`")
    content = content.replace("Linter: `ruff`", f"Linter: `{linter}`")
    content = content.replace(
        "- Test framework: pytest", f"- Test framework: {test_runner}"
    )
    content = content.replace(
        "- Test command: `pytest tests/ -v`",
        f"- Test command: `{test_runner} tests/ -v`",
    )

    now = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
    content += f"\n- 0.1.0 — Initial constitution generated on {now}\n"

    specs_dir.mkdir(parents=True, exist_ok=True)
    const_path.write_text(content, encoding="utf-8")
    console.print(f"  [green]CREATE[/] {const_path.relative_to(Path.cwd())}")

    if interactive and Confirm.ask("\nCommit constitution now?"):
        commit_artifact(path=const_path, message="Generate initial constitution")
        console.print("  [green]COMMIT[/] constitution.md committed")


@constitution_app.command()
def pre() -> None:
    """Validate constitution and extract commands."""
    repo_root = Path.cwd()
    const_path = repo_root / "specs" / "constitution.md"

    if not const_path.exists():
        _fail_with(f"constitution.md not found at {const_path}")

    if not validate_constitution(const_path):
        _fail_with("constitution validation failed")

    missing = validate_sections(const_path, ["## TESTING_PROTOCOLS"])
    if missing:
        _fail_with(f"Missing required section: {missing[0]}")

    commands = extract_commands(const_path)
    print(json.dumps(commands))


@constitution_app.command()
def post(
    manifest: str = typer.Argument(..., help="Path to manifest JSON"),
) -> None:
    """Validate constitution sections and commit."""
    manifest_path = Path(manifest)

    if not manifest_path.exists():
        _fail_with(f"manifest not found at {manifest_path}")

    manifest_data = json.loads(manifest_path.read_text())
    sections = manifest_data.get("sections", [])
    const_rel_path = manifest_data.get("constitution_path", "specs/constitution.md")

    const_path = Path.cwd() / const_rel_path

    missing = validate_sections(const_path, sections)
    if missing:
        _fail_with(f"Missing sections: {', '.join(missing)}")

    commit_artifact(path=const_path, message="Update constitution")
    print(json.dumps({"status": "SUCCESS"}))
