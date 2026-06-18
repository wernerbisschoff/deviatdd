from __future__ import annotations

import importlib.resources
import re
import shutil
import warnings
from pathlib import Path

import typer
from rich.console import Console

from deviate.state.config import DeviateConfig, SessionState
from deviate.state.config import resolve_graphite_config as resolve_graphite_config  # noqa: F401
from deviate.cli.macro import explore_app, macro_app, research_app, prd_app, shard_app
from deviate.cli.meso import meso_app, plan, pr, specify, tasks
from deviate.cli.micro import (
    e2e_app,
    execute_app,
    green_app,
    hotfix_app,
    judge_app,
    red_app,
    refactor_app,
    run_command,
    yellow_app,
)
from deviate.cli.adhoc import adhoc_app
from deviate.cli.constitution import constitution_app
from deviate.cli.feature import feature_app
from deviate.cli.inspect import inspect_app
from deviate.cli.review import review_app
from deviate.core.skills import detect_agents, discover_skills, install_skill

cli = typer.Typer(no_args_is_help=True)
console = Console()

_GOVERNANCE_MODULE = "deviate.prompts.governance"


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


def _serialize_value(key: str, value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return f"{key} = {'true' if value else 'false'}"
    if isinstance(value, (int, float)):
        return f"{key} = {value}"
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'{key} = "{escaped}"'


def _dict_to_toml(data: dict) -> str:
    lines: list[str] = []
    # Emit all scalar top-level keys FIRST, then all tables. TOML has no
    # "back to root" syntax — once a [table] header is written, any subsequent
    # bare keys are absorbed into that table. By ordering scalars before
    # dicts, top-level scalars stay at root scope.
    scalars: list[tuple[str, object]] = []
    tables: list[tuple[str, dict]] = []
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, dict):
            tables.append((key, value))
        else:
            scalars.append((key, value))

    for key, value in scalars:
        line = _serialize_value(key, value)
        if line:
            lines.append(line)

    for key, value in tables:
        if not value:
            # Skip empty tables — emitting `[key]` would still consume the
            # section header even with no entries, and any later bare keys
            # would nest under it.
            continue
        lines.append(f"\n[{key}]")
        for k, v in value.items():
            line = _serialize_value(k, v)
            if line:
                lines.append(line)
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


def _warn_if_unresolved(var_name: str, value: str) -> None:
    if value == "UNKNOWN":
        warnings.warn(
            f"{var_name} could not be resolved from pyproject.toml", stacklevel=2
        )


def _resolve_project_name(data: dict) -> str:
    name = data.get("project", {}).get("name")
    return "UNKNOWN" if not name else name


def _resolve_backend_framework(data: dict) -> str:
    deps = data.get("project", {}).get("dependencies", [])
    if not deps:
        return "UNKNOWN"
    pkg = re.split(r"[><=~!]", deps[0])[0].strip()
    return pkg if pkg else "UNKNOWN"


def _resolve_package_manager(data: dict) -> str:
    tool = data.get("tool", {})
    if "uv" in tool:
        return "uv"
    if "poetry" in tool:
        return "poetry"
    if "hatch" in tool:
        return "hatch"
    if "pdm" in tool:
        return "pdm"
    return "UNKNOWN"


def _resolve_test_runner(data: dict) -> str:
    tool = data.get("tool", {})
    if "pytest" in tool:
        return "pytest"
    if "unittest" in tool:
        return "unittest"
    return "UNKNOWN"


def _load_pyproject(root: Path) -> dict:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return {}
    try:
        import tomllib

        with open(pyproject, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def _resolve_placeholder(repo_root: Path | None = None) -> dict[str, str]:
    root = repo_root.resolve() if repo_root else Path.cwd().resolve()
    data = _load_pyproject(root)

    result: dict[str, str] = {
        "REPO_ROOT": str(root),
        "TARGET_COVERAGE_MINIMUM": "80",
    }

    pairs: list[tuple[str, str]] = [
        ("PROJECT_NAME", _resolve_project_name(data)),
        (
            "TARGET_BACKEND_FRAMEWORK",
            _resolve_backend_framework(data),
        ),
        (
            "TARGET_PACKAGE_MANAGER",
            _resolve_package_manager(data),
        ),
        ("TARGET_TEST_RUNNER", _resolve_test_runner(data)),
    ]
    for var_name, value in pairs:
        _warn_if_unresolved(var_name, value)
        result[var_name] = value

    return result


def _resolve_placeholder_match(match: re.Match[str]) -> str:
    var_name = match.group(1)
    resolved = _resolve_placeholder()
    return resolved.get(var_name, f"${{{var_name}}}")


def _resolve_seed(content: str) -> str:
    return re.sub(r"\$\{(\w+)\}", _resolve_placeholder_match, content)


def _extract_section_heading(content: str) -> str | None:
    match = re.search(r"^## (.+)$", content, re.MULTILINE)
    if match:
        return f"## {match.group(1)}"
    return None


def _read_seed(module: str, filename: str) -> str | None:
    try:
        seed = importlib.resources.files(module).joinpath(filename)
        return seed.read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError):
        console.print(f"  [red]ERROR[/] {filename} not found in package")
        return None


def _upsert_governance_block(target_path: Path, seed_content: str) -> None:
    section_header = _extract_section_heading(seed_content)
    if section_header is None:
        console.print("  [red]ERROR[/] Could not extract section heading from seed")
        return

    if not target_path.exists():
        target_path.write_text(seed_content, encoding="utf-8")
        console.print(f"  [green]CREATE[/] {target_path.name}")
        return

    existing = target_path.read_text(encoding="utf-8")

    if not existing.strip():
        target_path.write_text(seed_content, encoding="utf-8")
        console.print(f"  [green]CREATE[/] {target_path.name}")
        return

    if section_header not in existing:
        target_path.write_text(existing + "\n\n" + seed_content, encoding="utf-8")
        console.print(f"  [green]APPEND[/] {target_path.name}")
        return

    pattern = re.compile(
        rf"^{re.escape(section_header)}.*?(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    existing = pattern.sub(lambda _: seed_content.strip(), existing)
    target_path.write_text(existing, encoding="utf-8")
    console.print(f"  [green]UPDATE[/] {target_path.name} block replaced")


def _detect_context() -> bool:
    return shutil.which("context") is not None


def _merge_flag_keys(config_path: Path, *, graphite: bool, use_context: bool) -> None:
    """Surgically update ``graphite`` and ``use_context`` keys in an existing TOML.

    Preserves every other key/table (e.g. user-customised ``[models]``).
    Used when ``init --graphite`` or ``init --context`` is re-run on a workspace
    whose ``.deviate/config.toml`` already exists — the idempotency guard in
    ``_write_if_missing`` would otherwise silently drop the new flag values.
    """
    content = config_path.read_text(encoding="utf-8")
    for key, value in (("graphite", graphite), ("use_context", use_context)):
        new_line = f"{key} = {'true' if value else 'false'}"
        pattern = re.compile(rf"^{re.escape(key)}\s*=\s*.*$", re.MULTILINE)
        if pattern.search(content):
            content = pattern.sub(new_line, content)
        else:
            # Insert before the first [table] header if any, else append.
            table_match = re.search(r"^\[.*\]\s*$", content, re.MULTILINE)
            if table_match:
                idx = table_match.start()
                content = content[:idx] + f"{new_line}\n" + content[idx:]
            else:
                if content and not content.endswith("\n"):
                    content += "\n"
                content += f"{new_line}\n"
    config_path.write_text(content, encoding="utf-8")


def _scaffold_dotfiles(
    workdir: Path,
    agent_export_mode: str,
    use_context: bool = False,
    graphite: bool = False,
    force_update_flags: bool = False,
) -> None:
    dot_dir = workdir / ".deviate"
    _ensure_dir(dot_dir)
    _ensure_dir(dot_dir / "artifacts")

    config_path = dot_dir / "config.toml"
    if config_path.exists() and not force_update_flags:
        console.print(f"  [yellow]SKIP[/] {config_path.name} already exists")
    elif config_path.exists():
        _merge_flag_keys(config_path, graphite=graphite, use_context=use_context)
        console.print(f"  [green]UPDATE[/] {config_path.name} flags merged")
    else:
        config = DeviateConfig(
            agent_export_mode=agent_export_mode,
            use_context=use_context,
            graphite=graphite,
        )
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


def _apply_governance(workdir: Path, graphite: bool = False) -> None:
    claude_path = workdir / "CLAUDE.md"
    claude_content = _read_seed(_GOVERNANCE_MODULE, "claudemd_seed.md")
    if claude_content is None:
        return
    _upsert_governance_block(claude_path, claude_content)

    agents_path = workdir / "AGENTS.md"
    agents_content = _read_seed(_GOVERNANCE_MODULE, "agents_seed.md")
    if agents_content is None:
        return
    _upsert_governance_block(agents_path, agents_content)

    if graphite:
        content = _read_seed(_GOVERNANCE_MODULE, "graphite_seed.md")
        if content:
            _upsert_governance_block(claude_path, content)
            _upsert_governance_block(agents_path, content)


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
            if install_skill(skill_name, target_dir, workdir=workdir):
                console.print(f"  [green]INSTALL[/] {skill_name} → {agent}")
            else:
                console.print(f"  [yellow]SKIP[/] {skill_name} → {agent}")


def _ensure_gitignore(workdir: Path) -> None:
    dot_dir = workdir / ".deviate"
    dot_dir.mkdir(parents=True, exist_ok=True)
    gitignore = dot_dir / ".gitignore"
    entries = [
        "session.json",
        "artifacts/",
        "prompts.log",
        "reports/",
        "rollback.jsonl",
    ]
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        for entry in entries:
            if entry not in content:
                content = content.rstrip("\n") + f"\n{entry}\n"
        gitignore.write_text(content, encoding="utf-8")
    else:
        gitignore.write_text("\n".join(entries) + "\n", encoding="utf-8")


@cli.command()
def init(
    agent_export_mode: str = typer.Option(
        "local", "--agent-export-mode", help="Export mode for agent commands"
    ),
    generate_constitution: bool = typer.Option(
        False, "--generate-constitution", help="Generate constitution boilerplate"
    ),
    graphite: bool = typer.Option(
        False, "--graphite", help="Enable Graphite CLI integration for stacked changes"
    ),
    context: bool = typer.Option(
        False,
        "--context",
        help="Force-enable offline context CLI integration (overrides PATH detection)",
    ),
    agent: str | None = typer.Option(
        None, "--agent", help="Override auto-detected agent platform"
    ),
) -> None:
    workdir = Path.cwd()

    console.print("[bold]Initializing deviate workspace...[/bold]")

    use_context = True if context else _detect_context()
    _scaffold_dotfiles(
        workdir,
        agent_export_mode,
        use_context=use_context,
        graphite=graphite,
        force_update_flags=graphite or context,
    )

    _apply_governance(workdir, graphite=graphite)

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
cli.command(name="plan")(plan)
cli.command(name="tasks")(tasks)
cli.command(name="pr")(pr)
cli.add_typer(meso_app, name="meso")
cli.add_typer(macro_app, name="macro")
cli.add_typer(red_app, name="red")
cli.add_typer(green_app, name="green")
cli.add_typer(yellow_app, name="yellow")
cli.add_typer(judge_app, name="judge")
cli.add_typer(refactor_app, name="refactor")
cli.add_typer(execute_app, name="execute")
cli.add_typer(e2e_app, name="e2e")
cli.add_typer(hotfix_app, name="hotfix")
cli.add_typer(adhoc_app, name="adhoc")
cli.add_typer(constitution_app, name="constitution")
cli.add_typer(feature_app, name="feature")
cli.add_typer(inspect_app, name="inspect")
cli.add_typer(review_app, name="review")
cli.command(name="run")(run_command)
