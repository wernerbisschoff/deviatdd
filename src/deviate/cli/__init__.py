from __future__ import annotations

import importlib.resources
import re
from pathlib import Path

import typer
from rich.console import Console

from deviate.state.config import DeviateConfig, SessionState
from deviate.cli.macro import explore_app, research_app, prd_app, shard_app
from deviate.cli.meso import pr, specify, tasks
from deviate.cli.micro import run_command
from deviate.core.skills import detect_agents, discover_skills, install_skill

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
    path.write_text(content, encoding="utf-8")
    console.print(f"  [green]CREATE[/] {path.name}")
    return True


def _dict_to_toml(data: dict) -> str:
    lines: list[str] = []
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, bool):
            lines.append(f"{key} = {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key} = {value}")
        else:
            escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
    lines.append("")
    toml_str = "\n".join(lines)
    try:
        import tomllib

        try:
            tomllib.loads(toml_str)
        except tomllib.TOMLDecodeError:
            console.print("  [red]ERROR[/] Generated TOML failed round-trip validation")
    except ImportError:
        pass
    return toml_str


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


def _read_seed(module: str, filename: str) -> str | None:
    try:
        seed = importlib.resources.files(module).joinpath(filename)
        return seed.read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError):
        console.print(f"  [red]ERROR[/] {filename} not found in package")
        return None


def _upsert_governance_block(target_path: Path, seed_content: str) -> None:
    if not target_path.exists():
        target_path.write_text(seed_content, encoding="utf-8")
        console.print(f"  [green]CREATE[/] {target_path.name}")
        return

    existing = target_path.read_text(encoding="utf-8")

    if not existing.strip():
        target_path.write_text(seed_content, encoding="utf-8")
        console.print(f"  [green]CREATE[/] {target_path.name}")
        return

    section_header = "## DeviaTDD Orchestration Rules"

    if section_header not in existing:
        target_path.write_text(existing + "\n\n" + seed_content, encoding="utf-8")
        console.print(f"  [green]APPEND[/] {target_path.name}")
        return

    pattern = re.compile(
        r"^## DeviaTDD Orchestration Rules.*?(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    existing = pattern.sub(lambda _: seed_content.strip(), existing)
    target_path.write_text(existing, encoding="utf-8")
    console.print(f"  [green]UPDATE[/] {target_path.name} block replaced")


def _scaffold_dotfiles(workdir: Path, agent_export_mode: str) -> None:
    dot_dir = workdir / ".deviate"
    _ensure_dir(dot_dir)

    config = DeviateConfig(agent_export_mode=agent_export_mode)
    config_path = dot_dir / "config.toml"
    _write_if_missing(config_path, _dict_to_toml(config.model_dump()))

    session = SessionState()
    session_path = dot_dir / "session.json"
    _write_if_missing(session_path, session.model_dump_json(indent=2))


def _provision_constitution(workdir: Path) -> None:
    spec_dir = workdir / "specs"
    _ensure_dir(spec_dir)

    constitution_path = spec_dir / "constitution.md"
    if constitution_path.exists():
        console.print("  [yellow]SKIP[/] specs/constitution.md already exists")
        return

    content = _read_seed("deviate.prompts", "constitution_seed.md")
    if content is None:
        return

    resolved = _resolve_seed(content)
    constitution_path.write_text(resolved, encoding="utf-8")
    console.print("  [green]CREATE[/] specs/constitution.md")


def _apply_governance(workdir: Path) -> None:
    content = _read_seed("deviate.prompts.governance", "claudemd_seed.md")
    if content is None:
        return

    claude_path = workdir / "CLAUDE.md"
    _upsert_governance_block(claude_path, content)

    agents_content = _read_seed("deviate.prompts.governance", "agents_seed.md")
    if agents_content is None:
        return

    agents_path = workdir / "AGENTS.md"
    _upsert_governance_block(agents_path, agents_content)


def _get_agent_skill_dir(agent_name: str, workdir: Path) -> Path | None:
    if agent_name == "claude":
        return workdir / ".claude" / "skills"
    if agent_name == "opencode":
        return workdir / ".opencode" / "skills"
    if agent_name == "factory":
        return workdir / ".factory" / "skills"
    return None


def _install_skills_to_agents(workdir: Path, agents: list[str]) -> None:
    skills = discover_skills()
    if not skills:
        return
    for agent in agents:
        target_dir = _get_agent_skill_dir(agent, workdir)
        if target_dir is None:
            console.print(f"  [yellow]SKIP[/] Unknown agent: {agent}")
            continue
        for skill_name in skills:
            if install_skill(skill_name, target_dir):
                console.print(f"  [green]INSTALL[/] {skill_name} → {agent}")
            else:
                console.print(f"  [yellow]SKIP[/] {skill_name} → {agent}")


def _ensure_gitignore(workdir: Path) -> None:
    gitignore = workdir / ".gitignore"
    entry = ".deviate/session.json"
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        if entry not in content:
            gitignore.write_text(
                content.rstrip("\n") + f"\n{entry}\n", encoding="utf-8"
            )
    else:
        gitignore.write_text(f"{entry}\n", encoding="utf-8")


@cli.command()
def init(
    agent_export_mode: str = typer.Option(
        "local", "--agent-export-mode", help="Export mode for agent commands"
    ),
    generate_constitution: bool = typer.Option(
        False, "--generate-constitution", help="Generate constitution boilerplate"
    ),
    agent: str | None = typer.Option(
        None, "--agent", help="Override auto-detected agent platform"
    ),
) -> None:
    workdir = Path.cwd()

    console.print("[bold]Initializing deviate workspace...[/bold]")

    _scaffold_dotfiles(workdir, agent_export_mode)

    _apply_governance(workdir)

    _provision_constitution(workdir)

    if agent:
        active_agents = [agent]
    else:
        active_agents = detect_agents(workdir)

    if active_agents:
        _install_skills_to_agents(workdir, active_agents)

    _ensure_gitignore(workdir)


cli.add_typer(explore_app, name="explore")
cli.add_typer(research_app, name="research")
cli.add_typer(prd_app, name="prd")
cli.add_typer(shard_app, name="shard")
cli.command(name="specify")(specify)
cli.command(name="tasks")(tasks)
cli.command(name="pr")(pr)
cli.command(name="run")(run_command)
