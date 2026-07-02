from __future__ import annotations

import importlib.resources
import re
import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Prompt

from deviate.state.config import DeviateConfig, SessionState
from deviate.state.config import resolve_graphite_config as resolve_graphite_config  # noqa: F401
from deviate.cli.macro import explore_app, macro_app, research_app, prd_app, shard_app  # noqa: F401
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
)
from deviate.cli.adhoc import adhoc_app
from deviate.cli.constitution import constitution_app
from deviate.cli.feature import feature_app
from deviate.cli.inspect import inspect_app
from deviate.cli.init import init_app
from deviate.cli.review import review_app
from deviate.core.commands import discover_commands, install_command
from deviate.ui.render import is_interactive

cli = typer.Typer(no_args_is_help=True)
console = Console()

_GOVERNANCE_MODULE = "deviate.prompts.governance"

# User-facing agent platform choices (selectable via --agent and the
# interactive init prompt). Order is intentional: factory/droid (Droid
# ecosystem) come first, then the third-party CLIs.
AGENT_CHOICES: tuple[str, ...] = ("factory", "droid", "claude", "opencode", "pi", "omp")

# Map a user-facing agent name to the underlying backend that meso/micro
# layers invoke. ``factory`` is the Factory Droid IDE — the meso/micro
# commands still drive the ``droid`` binary under the hood. ``pi`` is
# the @earendil-works/pi-coding-agent CLI binary. ``omp`` uses the same
# backend as ``pi`` (Oh-My-Pi is a wrapper around the Pi executor).
AGENT_TO_BACKEND: dict[str, str] = {
    "factory": "droid",
    "droid": "droid",
    "claude": "claude",
    "opencode": "opencode",
    "pi": "pi",
    "omp": "pi",
}


def _version_callback(value: bool) -> None:
    if value:
        from importlib.metadata import version

        typer.echo(f"deviate {version('deviate')}")
        raise typer.Exit()


@cli.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit",
    ),
) -> None:
    """DeviaTDD CLI — agent orchestration framework"""


# TOML comment annotations for DeviateConfig fields — emitted as `#` lines
# before their corresponding key in .deviate/config.toml.  These are the
# primary documentation surface for end users editing config by hand.
_CONFIG_TOML_COMMENTS: dict[str, str] = {
    "profile": 'Preset config group: "default", "full", "fast", or "secure"',
    "timeout_seconds": "CLI inactivity timeout in seconds (must be > 0)",
    "agent_export_mode": 'Agent export mode: "local" (project) or "global" (~/.claude/)',
    "agent": "Agent backend configuration",
    "models": "Per-phase model overrides; key = phase name, value = model ID",
    "use_libref": "Enable the libref CLI for offline documentation lookups",
    "graphite": "Enable Graphite CLI integration for stacked changes",
}


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


def _dict_to_toml(data: dict, comments: dict[str, str] | None = None) -> str:
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
        if comments and key in comments:
            lines.append(f"# {comments[key]}")
        line = _serialize_value(key, value)
        if line:
            lines.append(line)

    for key, value in tables:
        if not value:
            continue
        if comments and key in comments:
            lines.append(f"\n# {comments[key]}")
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


def _split_governance_sections(content: str) -> list[str]:
    """Split multi-section governance content into individual ``##`` sections."""
    parts = re.split(r"^(?=## )", content, flags=re.MULTILINE)
    return [p.strip() for p in parts if p.strip() and p.startswith("## ")]


def _normalize_heading(text: str) -> str:
    """Lowercase heading text with emojis, punctuation, and parentheticals stripped."""
    h = re.sub(r"^##\s*", "", text)
    h = re.sub(r"\([^)]*\)", "", h)
    h = re.sub(r"[^\w\s-]", "", h)
    return " ".join(h.lower().split())


def _find_section_heading(content: str, seed_header: str) -> str | None:
    """Return the heading line in *content* that matches *seed_header*.

    Tries exact match first (line-boundary aware), then normalized
    (ignore emoji/parentheticals). Returns ``None`` when no match is found.
    """
    for line in content.split("\n"):
        if line.strip().startswith(seed_header):
            return seed_header

    seed_norm = _normalize_heading(seed_header)
    if not seed_norm:
        return None

    for heading in re.findall(r"^## .+$", content, re.MULTILINE):
        if _normalize_heading(heading) == seed_norm:
            return heading

    return None


def _upsert_section(target_path: Path, section_content: str) -> None:
    section_header = _extract_section_heading(section_content)
    if section_header is None:
        console.print("  [red]ERROR[/] Could not extract section heading from seed")
        return

    if not target_path.exists():
        target_path.write_text(section_content + "\n", encoding="utf-8")
        console.print(f"  [green]CREATE[/] {target_path.name}")
        return

    existing = target_path.read_text(encoding="utf-8")

    if not existing.strip():
        target_path.write_text(section_content + "\n", encoding="utf-8")
        console.print(f"  [green]CREATE[/] {target_path.name}")
        return

    target_heading = _find_section_heading(existing, section_header)
    if target_heading is None:
        target_path.write_text(
            existing.rstrip("\n") + "\n\n" + section_content + "\n", encoding="utf-8"
        )
        console.print(f"  [green]APPEND[/] {target_path.name}")
        return

    pattern = re.compile(
        rf"^{re.escape(target_heading)}.*?(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    existing = pattern.sub(lambda _: section_content.strip() + "\n", existing)
    target_path.write_text(existing, encoding="utf-8")
    console.print(f"  [green]UPDATE[/] {target_path.name} block replaced")


def _upsert_governance_block(target_path: Path, seed_content: str) -> None:
    sections = _split_governance_sections(seed_content)
    if not sections:
        console.print("  [red]ERROR[/] No valid governance sections found in seed")
        return
    for section in sections:
        _upsert_section(target_path, section)


def _detect_libref() -> bool:
    return shutil.which("libref") is not None


# ---------------------------------------------------------------------------
# Agent selection
# ---------------------------------------------------------------------------


def _read_agent_backend_from_config(config_path: Path) -> str | None:
    """Return the ``[agent].backend`` value stored in *config_path*.

    Used by both init (to detect a previously persisted choice) and the
    interactive prompt (to pre-select the current value as the default).
    """
    if not config_path.exists():
        return None
    try:
        import tomllib

        with open(config_path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return None
    backend = data.get("agent", {}).get("backend")
    return backend if isinstance(backend, str) and backend else None


def _resolve_agent_to_backend(agent: str) -> str:
    """Map a user-facing agent name to its underlying backend.

    Falls back to the input value when it is already a valid backend
    literal (``opencode``, ``claude``, ``droid``). Unknown values are
    returned unchanged so the caller can surface a validation error.
    """
    return AGENT_TO_BACKEND.get(agent, agent)


def _write_agent_block_to_config(config_path: Path, backend: str) -> bool:
    """Surgically upsert ``[agent]\nbackend = "<value>"`` in *config_path*.

    Preserves every other key/table in the file (similar in spirit to
    :func:`_merge_flag_keys` for the boolean ``graphite`` / ``use_libref``
    keys, but for the nested ``[agent]`` table).

    Returns ``True`` when the file was modified, ``False`` when the
    existing ``[agent].backend`` already matches the requested value.
    """
    content = config_path.read_text(encoding="utf-8")
    new_line = f'backend = "{backend}"'

    block_pattern = re.compile(
        r"^\[agent\]\s*\n(?:backend\s*=\s*.*\n?)+",
        re.MULTILINE,
    )
    match = block_pattern.search(content)
    if match:
        if f'backend = "{backend}"' in match.group(0):
            return False
        content = block_pattern.sub(f"[agent]\n{new_line}\n", content)
    else:
        table_match = re.search(r"^\[.*\]\s*$", content, re.MULTILINE)
        new_block = f"\n[agent]\n{new_line}\n"
        if table_match:
            idx = table_match.start()
            content = content[:idx] + new_block.lstrip("\n") + "\n" + content[idx:]
        else:
            if content and not content.endswith("\n"):
                content += "\n"
            content += new_block
    config_path.write_text(content, encoding="utf-8")
    return True


def _prompt_agent_selection(
    workdir: Path,
    config_path: Path,
) -> str | None:
    """Interactively prompt the user to pick an agent platform.

    Returns the selected agent name, or ``None`` when the session is not
    interactive (e.g. CI) — the caller is then expected to abort the
    command with a clear error message.
    """
    if not is_interactive():
        return None
    existing = _read_agent_backend_from_config(config_path)
    default = existing if existing in AGENT_CHOICES else None
    try:
        selected = Prompt.ask(
            "Select agent platform",
            choices=list(AGENT_CHOICES),
            default=default,
            console=console,
        )
    except (EOFError, KeyboardInterrupt):
        return None
    if not selected or selected not in AGENT_CHOICES:
        return None
    return selected


def _validate_agent_choice(value: str | None) -> str | None:
    """Typer callback: validate ``--agent`` value and emit Typer error.

    ``None`` is allowed — that means the user did not pass ``--agent`` and
    the init command should fall through to config lookup / interactive
    prompt.
    """
    if value is None:
        return None
    if value not in AGENT_CHOICES:
        raise typer.BadParameter(
            f"Invalid agent '{value}'. Must be one of: {', '.join(AGENT_CHOICES)}"
        )
    return value


def _merge_flag_keys(config_path: Path, *, graphite: bool, use_libref: bool) -> None:
    """Surgically update ``graphite`` and ``use_libref`` keys in an existing TOML.

    Preserves every other key/table (e.g. user-customised ``[models]``).
    Used when ``init --graphite`` or ``init --libref`` is re-run on a workspace
    whose ``.deviate/config.toml`` already exists — the idempotency guard in
    ``_write_if_missing`` would otherwise silently drop the new flag values.
    """
    content = config_path.read_text(encoding="utf-8")
    for key, value in (("graphite", graphite), ("use_libref", use_libref)):
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
    use_libref: bool = False,
    graphite: bool = False,
    force_update_flags: bool = False,
    agent_backend: str | None = None,
) -> None:
    dot_dir = workdir / ".deviate"
    _ensure_dir(dot_dir)
    _ensure_dir(dot_dir / "artifacts")

    config_path = dot_dir / "config.toml"
    if config_path.exists() and not force_update_flags and agent_backend is None:
        console.print(f"  [yellow]SKIP[/] {config_path.name} already exists")
    elif config_path.exists():
        # Existing config: only touch the keys the caller asked us to touch.
        # `use_libref` and `graphite` are only ever upserted when the
        # corresponding flag was passed (force_update_flags).  `agent_backend`
        # is always upserted when provided so `--agent factory` can overwrite
        # a previously persisted backend.
        changed = False
        if force_update_flags:
            _merge_flag_keys(config_path, graphite=graphite, use_libref=use_libref)
            changed = True
        if agent_backend is not None:
            changed = (
                _write_agent_block_to_config(config_path, agent_backend) or changed
            )
        if changed:
            console.print(f"  [green]UPDATE[/] {config_path.name} flags merged")
        else:
            console.print(f"  [yellow]SKIP[/] {config_path.name} already exists")
    else:
        config = DeviateConfig(
            agent_export_mode=agent_export_mode,
            use_libref=use_libref,
            graphite=graphite,
        )
        if agent_backend is not None:
            config = config.model_copy(
                update={
                    "agent": config.agent.model_copy(update={"backend": agent_backend})
                }
            )
        _write_if_missing(
            config_path,
            _dict_to_toml(config.model_dump(), comments=_CONFIG_TOML_COMMENTS),
        )

    session = SessionState()
    session_path = dot_dir / "session.json"
    _write_if_missing(session_path, session.model_dump_json(indent=2))


def _apply_governance(workdir: Path, graphite: bool = False) -> None:
    # NOTE: claudemd_seed.md and agents_seed.md are intentionally empty — the
    # former ``## 🛠 DeviaTDD Phase Architecture`` block was project-internal
    # guidance that did not help consuming projects. An empty seed (read
    # successfully but with no content) is skipped silently so the remaining
    # blocks below still run. A missing seed is treated as a packaging error.
    claude_path = workdir / "CLAUDE.md"
    claude_content = _read_seed(_GOVERNANCE_MODULE, "claudemd_seed.md")
    if claude_content is None:
        return
    if "## " in claude_content:
        _upsert_governance_block(claude_path, claude_content)

    agents_path = workdir / "AGENTS.md"
    agents_content = _read_seed(_GOVERNANCE_MODULE, "agents_seed.md")
    if agents_content is None:
        return
    if "## " in agents_content:
        _upsert_governance_block(agents_path, agents_content)
    libref_content = _read_seed(_GOVERNANCE_MODULE, "libref_seed.md")
    if libref_content:
        _upsert_governance_block(claude_path, libref_content)
        _upsert_governance_block(agents_path, libref_content)

    if graphite:
        content = _read_seed(_GOVERNANCE_MODULE, "graphite_seed.md")
        if content:
            _upsert_governance_block(claude_path, content)
            _upsert_governance_block(agents_path, content)


_CONSTITUTION_SEED_MODULE = "deviate.prompts"
_CONSTITUTION_SEED_FILE = "constitution_seed.md"


def _scaffold_constitution(workdir: Path) -> None:
    """Write a placeholder specs/constitution.md if it doesn't exist.

    The placeholder is populated by ``/research`` during the macro layer.
    """
    specs_dir = workdir / "specs"
    const_path = specs_dir / "constitution.md"

    if const_path.exists():
        console.print("  [yellow]SKIP[/] specs/constitution.md already exists")
        return

    seed = _read_seed(_CONSTITUTION_SEED_MODULE, _CONSTITUTION_SEED_FILE)
    if seed is None:
        return

    specs_dir.mkdir(parents=True, exist_ok=True)
    const_path.write_text(seed, encoding="utf-8")
    console.print("  [green]CREATE[/] specs/constitution.md")


def _get_agent_command_dir(agent_name: str, workdir: Path) -> Path | None:
    """Resolve the slash-command directory for a given agent platform.

    Factory, Claude, OpenCode discover slash commands from
    ``<workdir>/.{agent}/commands/`` (flat top-level only). Pi and OMP use
    ``<workdir>/.{agent}/prompts/`` per their platform conventions.
    """
    if agent_name in ("claude", "opencode", "factory"):
        return workdir / f".{agent_name}" / "commands"
    if agent_name == "pi":
        return workdir / ".pi" / "prompts"
    if agent_name == "omp":
        return workdir / ".omp" / "prompts"
    return None


def _install_commands_to_agents(workdir: Path, agents: list[str]) -> None:
    """Install the command library into every supported agent directory.

    Output is aggregated per-agent — one summary line per agent instead of
    one line per (command × agent) — to keep ``deviate setup`` output
    readable when 32 commands are written to four agent directories
    (128 lines per invocation under the legacy per-command format).
    """
    commands = discover_commands()
    if not commands:
        return
    for agent in agents:
        target_dir = _get_agent_command_dir(agent, workdir)
        if target_dir is None:
            console.print(f"  [yellow]SKIP[/] Unknown agent: {agent}")
            continue
        installed = 0
        skipped = 0
        for command_name in commands:
            if install_command(command_name, target_dir, workdir=workdir, agent=agent):
                installed += 1
            else:
                skipped += 1
        if installed and not skipped:
            console.print(f"  [green]INSTALL[/] {installed} commands → {agent}")
        elif skipped and not installed:
            console.print(f"  [yellow]SKIP[/] {skipped} commands → {agent}")
        else:
            console.print(
                f"  [green]INSTALL[/] {installed}, [yellow]SKIP[/] {skipped} → {agent}"
            )


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
        "logs/",
    ]
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        for entry in entries:
            if entry not in content:
                content = content.rstrip("\n") + f"\n{entry}\n"
        gitignore.write_text(content, encoding="utf-8")
    else:
        gitignore.write_text("\n".join(entries) + "\n", encoding="utf-8")


@cli.command(name="setup")
def setup(
    agent_export_mode: str = typer.Option(
        "local", "--agent-export-mode", help="Export mode for agent commands"
    ),
    graphite: bool = typer.Option(
        False, "--graphite", help="Enable Graphite CLI integration for stacked changes"
    ),
    libref: bool = typer.Option(
        False,
        "--libref",
        help="Force-enable offline libref CLI integration (overrides PATH detection)",
    ),
    agent: str | None = typer.Option(
        None,
        "--agent",
        help="Override auto-detected agent platform",
        callback=_validate_agent_choice,
    ),
) -> None:
    workdir = Path.cwd()
    config_path = workdir / ".deviate" / "config.toml"

    console.print("[bold]Initializing deviate workspace...[/bold]")

    selected_agent: str | None = agent
    if selected_agent is None:
        existing_backend = _read_agent_backend_from_config(config_path)
        if existing_backend is not None:
            selected_agent = existing_backend
        else:
            selected_agent = _prompt_agent_selection(workdir, config_path)
            if selected_agent is None:
                console.print(
                    "[red]NO_AGENT_SELECTED[/] No agent platform chosen."
                    " Re-run `deviate setup --agent <name>` with one of:"
                    f" {', '.join(AGENT_CHOICES)}."
                )
                raise typer.Exit(code=1)

    backend = _resolve_agent_to_backend(selected_agent)

    use_libref_val = True if libref else _detect_libref()
    _scaffold_dotfiles(
        workdir,
        agent_export_mode,
        use_libref=use_libref_val,
        graphite=graphite,
        force_update_flags=graphite or libref,
        agent_backend=backend,
    )

    _apply_governance(workdir, graphite=graphite)

    _scaffold_constitution(workdir)
    # DeviaTDD commands are installed into ALL agent directories regardless
    # of ``--agent``. ``--agent`` only drives the ``[agent].backend`` value
    # written to ``.deviate/config.toml`` — that value is consumed by the
    # meso/micro layers to dispatch agent invocations, never to gate which
    # agents receive commands. ``droid`` is normalised to ``factory`` —
    # both names map to the Factory Droid IDE commands directory
    # (``.factory/commands/``); ``droid`` is the underlying backend binary.
    # ``pi`` uses ``.pi/prompts/`` per the platform's documented convention;
    # ``omp`` uses ``.omp/prompts/`` per the OMP platform convention; the
    # other three use ``commands/``. No global ``~/.pi/agent/`` writes,
    # no ``settings.json`` generation — the operator's Pi config is out of
    # scope.
    active_agents = ("claude", "opencode", "factory", "pi", "omp")
    _install_commands_to_agents(workdir, list(active_agents))

    _ensure_gitignore(workdir)
    _ensure_root_gitignore(workdir)
    _ensure_root_gitattributes(workdir)


# Canonical ``.gitattributes`` content provisioned by ``deviate setup``.
# Marked as a module constant so the deviatdd repo's own ``.gitattributes``
# file and every downstream scaffolded project stay in sync — single source
# of truth for the union-merge rules over append-only JSONL ledgers.
DEVIATE_GITATTRIBUTES_SEED = (
    "# DeviaTDD append-only JSONL ledgers: union-merge so concurrent\n"
    "# appends never conflict at branch-merge time.\n"
    "# See specs/constitution.md §1 Append-Only Ledger Protocol.\n"
    "specs/issues.jsonl merge=union\n"
    "specs/**/tasks.jsonl merge=union\n"
)


def _ensure_root_gitattributes(workdir: Path) -> None:
    """Provision a project-root ``.gitattributes`` declaring
    ``merge=union`` for the append-only JSONL ledgers.

    Mirrors the idempotent-merge contract of :func:`_ensure_root_gitignore`:
    user-authored entries are preserved, and re-running setup never
    duplicates the union-merge rules.

    Without this, concurrent ``deviate shard`` runs on feature branches
    produce line-level conflicts in ``specs/issues.jsonl`` at merge time
    that require manual resolution. ``merge=union`` is git's built-in
    line-wise union driver — it keeps every unique line across all
    branches and emits no conflict markers.

    Rationale, semantic-dup behaviour, and diamond-merge verification
    are documented in ``specs/DeviaTDD-api.md`` under ``deviate init``
    and ``deviate setup``.
    """
    attr_path = workdir / ".gitattributes"
    if attr_path.exists():
        content = attr_path.read_text(encoding="utf-8")
        existing_lines = content.splitlines()
        union_lines = [
            line
            for line in DEVIATE_GITATTRIBUTES_SEED.splitlines()
            if line and not line.startswith("#")
        ]
        missing = [line for line in union_lines if line not in existing_lines]
        if not missing:
            return
        merged = list(existing_lines)
        if merged and merged[-1].strip():
            merged.append("")
        merged.extend(missing)
        attr_path.write_text("\n".join(merged) + "\n", encoding="utf-8")
        console.print(
            f"  [green]UPDATE[/] .gitattributes added {len(missing)} union-merge rules"
        )
    else:
        attr_path.write_text(DEVIATE_GITATTRIBUTES_SEED, encoding="utf-8")
        console.print("  [green]CREATE[/] .gitattributes with union-merge rules")


def _ensure_root_gitignore(workdir: Path) -> None:
    """Update the project-root ``.gitignore`` to exclude DeviaTDD-installed
    commands across all agent platforms.
    Two command families are installed and must not be committed:

    - ``deviate-*`` — the core DeviaTDD command library

    The patterns are scoped with ``*/commands/`` and ``*/prompts/`` so they
    only match a SINGLE directory level before the agent subdir — this is
    deliberately tight because the project itself stores command sources
    three levels deep at ``src/deviate/prompts/commands/deviate-*.md``
    (plus spec files like ``specs/plans/deviate-content.md``). A broader
    ``**/deviate-*.md`` pattern would silently ignore those source-of-truth
    files and break ``deviate setup`` in the deviatdd repo itself. The
    patterns cover every supported agent (``.claude/commands/``,
    ``.opencode/commands/``, ``.factory/commands/``, ``.pi/prompts/``,
    ``.omp/prompts/``) and any future agent that follows the same
    ``<dir>/commands/`` or ``<dir>/prompts/`` flat-file convention.
    """
    gitignore_path = workdir / ".gitignore"
    entries = (
        "*/commands/deviate-*.md",
        "*/prompts/deviate-*.md",
    )
    if gitignore_path.exists():
        content = gitignore_path.read_text(encoding="utf-8")
        existing_lines = content.splitlines()
        missing = [entry for entry in entries if entry not in existing_lines]
        if not missing:
            return
        merged = list(existing_lines)
        if merged and merged[-1].strip():
            merged.append("")
        merged.extend(missing)
        gitignore_path.write_text("\n".join(merged) + "\n", encoding="utf-8")
        console.print(
            f"  [green]UPDATE[/] .gitignore added {len(missing)} agent entries"
        )
    else:
        gitignore_path.write_text("\n".join(entries) + "\n", encoding="utf-8")
        console.print(
            f"  [green]CREATE[/] .gitignore with {len(entries)} agent entries"
        )


cli.add_typer(explore_app, name="explore")
cli.add_typer(research_app, name="research")
cli.add_typer(prd_app, name="prd")
cli.add_typer(shard_app, name="shard")

cli.add_typer(meso_app, name="meso")
cli.add_typer(macro_app, name="macro")
cli.add_typer(red_app, name="red")
cli.add_typer(green_app, name="green")
cli.add_typer(judge_app, name="judge")
cli.add_typer(refactor_app, name="refactor")
cli.add_typer(execute_app, name="execute")
cli.add_typer(e2e_app, name="e2e")
cli.add_typer(hotfix_app, name="hotfix")
cli.add_typer(adhoc_app, name="adhoc")
cli.add_typer(constitution_app, name="constitution")
cli.add_typer(init_app, name="init")
cli.add_typer(feature_app, name="feature")
cli.add_typer(inspect_app, name="inspect")
cli.command(name="specify")(specify)
cli.command(name="plan")(plan)
cli.add_typer(review_app, name="review")
cli.command(name="tasks")(tasks)
cli.command(name="pr")(pr)
cli.command(name="run")(run_command)
