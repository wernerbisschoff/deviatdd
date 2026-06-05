from __future__ import annotations

import re
from pathlib import Path

import typer
from rich.console import Console

from deviate.state.config import DeviateConfig, SessionState

cli = typer.Typer(no_args_is_help=True)
console = Console()


@cli.callback()
def main() -> None:
    """DeviaTDD CLI — agent orchestration framework"""


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        console.print(f"  [yellow]SKIP[/] {path.name} already exists")
        return False
    path.write_text(content)
    console.print(f"  [green]CREATE[/] {path.name}")
    return True


def _dict_to_toml(data: dict) -> str:
    lines: list[str] = []
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, bool):
            lines.append(f'{key} = {"true" if value else "false"}')
        elif isinstance(value, int):
            lines.append(f"{key} = {value}")
        elif isinstance(value, float):
            lines.append(f"{key} = {value}")
        elif isinstance(value, str):
            lines.append(f'{key} = "{value}"')
        else:
            lines.append(f'{key} = "{value}"')
    lines.append("")
    return "\n".join(lines)


def _resolve_placeholder(match: re.Match[str]) -> str:
    var_name = match.group(1)
    cwd = Path.cwd()

    if var_name == "PROJECT_NAME":
        pyproject = cwd / "pyproject.toml"
        if pyproject.exists():
            try:
                import tomllib

                with open(pyproject, "rb") as f:
                    data = tomllib.load(f)
                return data.get("project", {}).get("name", cwd.name)
            except Exception:
                pass
        return cwd.name

    if var_name == "REPO_ROOT":
        return str(cwd.resolve())

    return match.group(0)


def _resolve_seed(content: str) -> str:
    return re.sub(r"\$\{(\w+)\}", _resolve_placeholder, content)


def _upsert_governance_block(target_path: Path, seed_content: str) -> None:
    if not target_path.exists() or target_path.read_text().strip() == "":
        target_path.write_text(seed_content)
        console.print(f"  [green]CREATE[/] {target_path.name}")
        return

    existing = target_path.read_text()
    section_header = "## DeviaTDD Orchestration Rules"

    if section_header in existing:
        pattern = re.compile(
            r"^## DeviaTDD Orchestration Rules.*?(?=^## |\Z)",
            re.MULTILINE | re.DOTALL,
        )
        if pattern.search(existing):
            existing = pattern.sub(seed_content.strip(), existing)
            target_path.write_text(existing)
            console.print(f"  [green]UPDATE[/] {target_path.name} block replaced")
        else:
            target_path.write_text(existing + "\n\n" + seed_content)
            console.print(f"  [green]APPEND[/] {target_path.name}")
    else:
        with open(target_path, "a") as f:
            f.write("\n\n" + seed_content)
        console.print(f"  [green]APPEND[/] {target_path.name}")


def _scaffold_dotfiles(workdir: Path) -> None:
    dot_dir = workdir / ".deviate"
    _ensure_dir(dot_dir)

    config = DeviateConfig()
    config_path = dot_dir / "config.toml"
    _write_if_missing(config_path, _dict_to_toml(config.model_dump()))

    session = SessionState()
    session_path = dot_dir / "session.json"
    _write_if_missing(session_path, session.model_dump_json(indent=2))


def _provision_constitution(workdir: Path) -> None:
    import importlib.resources

    spec_dir = workdir / "specs"
    _ensure_dir(spec_dir)

    constitution_path = spec_dir / "constitution.md"
    if constitution_path.exists():
        console.print("  [yellow]SKIP[/] specs/constitution.md already exists")
        return

    try:
        seed = importlib.resources.files("deviate.prompts").joinpath(
            "constitution_seed.md"
        )
        content = seed.read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError):
        console.print("  [red]ERROR[/] constitution seed not found in package")
        return

    resolved = _resolve_seed(content)
    constitution_path.write_text(resolved)
    console.print("  [green]CREATE[/] specs/constitution.md")


def _apply_governance(workdir: Path) -> None:
    import importlib.resources

    try:
        seed = importlib.resources.files(
            "deviate.prompts.governance"
        ).joinpath("claudemd_seed.md")
        content = seed.read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError):
        console.print("  [red]ERROR[/] governance seed not found in package")
        return

    claude_path = workdir / "CLAUDE.md"
    _upsert_governance_block(claude_path, content)


@cli.command()
def init(
    agent_export_mode: str = typer.Option(
        "local", "--agent-export-mode", help="Export mode for agent commands"
    ),
    generate_constitution: bool = typer.Option(
        False, "--generate-constitution", help="Generate constitution boilerplate"
    ),
) -> None:
    workdir = Path.cwd()

    console.print("[bold]Initializing deviate workspace...[/bold]")

    _scaffold_dotfiles(workdir)

    _apply_governance(workdir)

    if generate_constitution:
        _provision_constitution(workdir)
