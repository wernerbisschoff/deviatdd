from __future__ import annotations

import importlib.resources
import re
from contextlib import chdir
import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Prompt

from deviate.state.config import DeviateConfig, SessionState
from deviate.state.config import resolve_graphite_config as resolve_graphite_config  # noqa: F401
from deviate.cli.macro import explore_app, macro_app, research_app, prd_app, shard_app  # noqa: F401
from deviate.cli.meso import _meso_run, merge, meso_app, plan, pr, specify, tasks
from deviate.cli.micro import (
    _run_all,
    _validate_profile,
    e2e_app,
    execute_app,
    green_app,
    hotfix_app,
    judge_app,
    micro_app,
    red_app,
    refactor_app,
)
from deviate.cli.adhoc import adhoc_app
from deviate.cli.constitution import constitution_app
from deviate.cli.feature import feature_app
from deviate.cli.inspect import inspect_app
from deviate.cli.init import init_app
from deviate.cli.review import review_app
from deviate.cli.walkthrough import walkthrough_app
from deviate.core.agent import AGENT_TO_BACKEND as AGENT_TO_BACKEND  # noqa: F401
from deviate.core.agent import resolve_agent_to_backend as _resolve_agent_to_backend  # noqa: F401
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
# the @earendil-works/pi-coding-agent CLI binary. ``omp`` is the
# Oh-My-Pi CLI (``omp -p``) — a distinct backend from ``pi``, even
# though OMP internally wraps Pi. ``deviate`` spawns the ``omp`` binary
# directly, not ``pi``, when the user selects ``omp``.
# Canonical source is :data:`deviate.core.agent.AGENT_TO_BACKEND`; the
# top-of-module re-export keeps the existing
# ``from deviate.cli import AGENT_TO_BACKEND`` import path working and
# keeps the cli init flow reading the same values.


def _version_callback(value: bool) -> None:
    if value:
        from importlib.metadata import PackageNotFoundError, version

        try:
            ver = version("deviatdd")
        except PackageNotFoundError:
            ver = "0.0.0+unknown"
        typer.echo(f"deviate {ver}")
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


def _linkify_governance_files(workdir: Path) -> None:
    """Ensure CLAUDE.md ↔ AGENTS.md symlink relationship.

    If neither file exists, create an empty CLAUDE.md and symlink
    AGENTS.md → CLAUDE.md.  If exactly one exists, symlink the other
    to it.  If both exist (as regular files), leave them alone.
    Idempotent — an existing symlink is never replaced.
    """
    claude = workdir / "CLAUDE.md"
    agents = workdir / "AGENTS.md"
    claude_exists = claude.exists() or claude.is_symlink()
    agents_exists = agents.exists() or agents.is_symlink()

    if claude_exists and agents_exists:
        return

    if not claude_exists and not agents_exists:
        claude.write_text("", encoding="utf-8")
        agents.symlink_to("CLAUDE.md")
        console.print("  [green]CREATE[/] CLAUDE.md")
        console.print("  [green]LINK[/]  AGENTS.md -> CLAUDE.md")
        return

    if claude_exists and not agents_exists:
        agents.symlink_to("CLAUDE.md")
        console.print("  [green]LINK[/]  AGENTS.md -> CLAUDE.md")
        return

    # agents_exists and not claude_exists
    claude.symlink_to("AGENTS.md")
    console.print("  [green]LINK[/]  CLAUDE.md -> AGENTS.md")


def _apply_governance(workdir: Path, graphite: bool = False) -> None:
    # NOTE: claudemd_seed.md and agents_seed.md are intentionally empty — the
    # former ``## 🛠 DeviaTDD Phase Architecture`` block was project-internal
    # guidance that did not help consuming projects. An empty seed (read
    # successfully but with no content) is skipped silently so the remaining
    # blocks below still run. A missing seed is treated as a packaging error.

    # Ensure CLAUDE.md ↔ AGENTS.md symlink before any seed writes.
    # After linking, determine which paths are canonical (not symlinks)
    # so upserts only write to the real file — never double-write through
    # a symlink to the same target.
    _linkify_governance_files(workdir)

    claude_path = workdir / "CLAUDE.md"
    agents_path = workdir / "AGENTS.md"
    targets: list[Path] = [p for p in (claude_path, agents_path) if not p.is_symlink()]

    claude_content = _read_seed(_GOVERNANCE_MODULE, "claudemd_seed.md")
    if claude_content is None:
        return
    if "## " in claude_content:
        for t in targets:
            _upsert_governance_block(t, claude_content)

    agents_content = _read_seed(_GOVERNANCE_MODULE, "agents_seed.md")
    if agents_content is None:
        return
    if "## " in agents_content:
        for t in targets:
            _upsert_governance_block(t, agents_content)

    libref_content = _read_seed(_GOVERNANCE_MODULE, "libref_seed.md")
    if libref_content:
        for t in targets:
            _upsert_governance_block(t, libref_content)

    if graphite:
        content = _read_seed(_GOVERNANCE_MODULE, "graphite_seed.md")
        if content:
            for t in targets:
                _upsert_governance_block(t, content)


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


@cli.command(name="setup", rich_help_panel="Run by you (start here)")
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
    """Bootstrap a new project with DeviaTDD (start here)."""
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


# Command panels — keep "Run by you (start here)" at the top so first-timers
# see the human entry points first. The "Optional / manual utilities" panel
# sits right under it for the occasional manual entry points. The
# "Agent/internal (via /deviate-* slash commands)" panel is everything the
# agent drives; pre/post phase dispatchers are explicitly listed there so
# first-timers do not run them by hand.
_USER_PANEL = "Run by you (start here)"
_OPTIONAL_PANEL = "Optional / manual utilities"
_AGENT_PANEL = "Agent/internal (via /deviate-* slash commands)"

# `setup` is registered above (line ~627) with `rich_help_panel="Run by you
# (start here)"`; the literal string is used there because Typer evaluates
# the decorator at import time, before these constants are defined.
cli.add_typer(
    feature_app,
    name="feature",
    rich_help_panel=_OPTIONAL_PANEL,
    help="Create a new feature branch",
)
cli.add_typer(
    inspect_app,
    name="inspect",
    rich_help_panel=_OPTIONAL_PANEL,
    help="Inspect issue and task ledgers",
)

# Top-level macro-phase Typer groups (agent-internal).
cli.add_typer(
    explore_app,
    name="explore",
    rich_help_panel=_AGENT_PANEL,
    help="Macro: codebase exploration",
)
cli.add_typer(
    research_app,
    name="research",
    rich_help_panel=_AGENT_PANEL,
    help="Macro: design + data-model (Gate 1)",
)
cli.add_typer(
    prd_app,
    name="prd",
    rich_help_panel=_AGENT_PANEL,
    help="Macro: PRD synthesis",
)
cli.add_typer(
    shard_app,
    name="shard",
    rich_help_panel=_AGENT_PANEL,
    help="Macro: shard feature into issues (Gate 2)",
)
cli.add_typer(
    macro_app,
    name="macro",
    rich_help_panel=_AGENT_PANEL,
    help="Macro: explore → research → prd → shard",
)

# Micro-phase Typer groups (agent-internal).
cli.add_typer(
    red_app,
    name="red",
    rich_help_panel=_AGENT_PANEL,
    help="Micro: write a failing test",
)
cli.add_typer(
    green_app,
    name="green",
    rich_help_panel=_AGENT_PANEL,
    help="Micro: implement to pass the test",
)
cli.add_typer(
    judge_app,
    name="judge",
    rich_help_panel=_AGENT_PANEL,
    help="Micro: review GREEN diff against contract",
)
cli.add_typer(
    refactor_app,
    name="refactor",
    rich_help_panel=_AGENT_PANEL,
    help="Micro: behavior-preserving cleanup",
)
cli.add_typer(
    execute_app,
    name="execute",
    rich_help_panel=_AGENT_PANEL,
    help="Micro: direct execution for non-TDD tasks",
)
cli.add_typer(
    e2e_app,
    name="e2e",
    rich_help_panel=_AGENT_PANEL,
    help="Micro: end-to-end verification",
)
cli.add_typer(
    hotfix_app,
    name="hotfix",
    rich_help_panel=_AGENT_PANEL,
    help="Micro: bug fix (bypasses RED)",
)
cli.add_typer(
    adhoc_app,
    name="adhoc",
    rich_help_panel=_AGENT_PANEL,
    help="Macro: low/medium-complexity shortcut",
)
cli.add_typer(
    constitution_app,
    name="constitution",
    rich_help_panel=_AGENT_PANEL,
    help="Validate specs/constitution.md",
)
cli.add_typer(
    init_app,
    name="init",
    rich_help_panel=_AGENT_PANEL,
    help="Detect project type + scaffold structure",
)
cli.add_typer(
    review_app,
    name="review",
    rich_help_panel=_AGENT_PANEL,
    help="Final PR review (Gate 3)",
)
cli.add_typer(
    walkthrough_app,
    name="walkthrough",
    rich_help_panel=_AGENT_PANEL,
    help="Architectural code walkthrough (human-guided)",
)


# Meso-phase pre/post dispatchers (agent-internal). The `pre` / `post`
# subcommands are emitted by the agent, not run by hand.
cli.command(name="specify", rich_help_panel=_AGENT_PANEL)(specify)
cli.command(name="plan", rich_help_panel=_AGENT_PANEL)(plan)
cli.command(name="tasks", rich_help_panel=_AGENT_PANEL)(tasks)
cli.command(name="pr", rich_help_panel=_AGENT_PANEL)(pr)
cli.command(name="merge", rich_help_panel=_AGENT_PANEL)(merge)
# `meso run`, `micro run`, and `run` are three distinct entry points:
#   - `meso run`         — user-facing; SPECIFY → PLAN → TASKS pipeline.
#   - `micro run`        — agent-internal; drains the task queue (single or --all).
#   - `run` (this)       — user-facing; `meso run` + `micro run --all` in the
#                          created worktree, end-to-end.
# `micro run` itself is surfaced as the `micro` Typer group so future
# micro-layer helpers (e.g. `micro run --task <id>`) can ride along.
cli.add_typer(
    meso_app,
    name="meso",
    rich_help_panel=_USER_PANEL,
    help="Use `deviate meso run` to run the automated setup → plan → tasks pipeline",
)
cli.add_typer(
    micro_app,
    name="micro",
    rich_help_panel=_AGENT_PANEL,
    help="Micro: drain the task queue (single or --all) inside a worktree",
)


@cli.command(name="run", rich_help_panel=_USER_PANEL)
def run_command(
    issue: str | None = typer.Option(
        None,
        "--issue",
        help="Target issue ID (default: next unblocked BACKLOG)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Bypass pre-flight guards (e.g. blocked_by dependencies)",
    ),
    profile: str = typer.Option(
        "full",
        "--profile",
        callback=_validate_profile,
        help="Forwarded to `deviate micro run`: full, fast, or secure",
    ),
    no_judge: bool | None = typer.Option(
        None, "--no-judge", help="Skip JUDGE phase in `micro run`"
    ),
    no_refactor: bool | None = typer.Option(
        None, "--no-refactor", help="Skip REFACTOR phase in `micro run`"
    ),
    agent: str | None = typer.Option(
        None,
        "--agent",
        help="Override agent backend for the micro phase",
    ),
    json_mode: bool = typer.Option(
        False, "--json", help="Forward --json to `deviate micro run`"
    ),
) -> None:
    """Use `deviate run`; per-task drain is now `deviate micro run`.

    Full-pipeline orchestrator: chains ``deviate meso run`` with the
    micro drain (``deviate micro run --all``) inside the worktree the
    meso step just created. Discovers the next unblocked BACKLOG issue,
    claims it, runs SPECIFY → PLAN → TASKS, then iterates every
    PENDING task through the TDD cycle (or the direct-execute phase
    for IMMEDIATE-typed tasks).

    This is the canonical "go do the next thing" command — it replaces
    the old standalone ``deviate run`` task dispatcher. The old
    ``deviate run [task-id] --all`` invocation is now reachable as
    ``deviate micro run [task-id] --all`` for in-worktree drains.
    """
    worktree_path_str = _meso_run(issue_id=issue, force=force)
    if not worktree_path_str:
        # _meso_run has already raised SystemExit(1) on hard failures;
        # reaching here means a soft failure (e.g. dry-run consumed the
        # return). Treat as a no-op so we don't crash on a missing path.
        console.print(
            "[yellow]RUN_NO_WORKTREE[/] meso pipeline did not return a "
            "worktree; skipping micro drain"
        )
        raise typer.Exit(code=1)

    worktree_path = Path(worktree_path_str)
    if not worktree_path.exists():
        console.print(f"[red]RUN_WORKTREE_MISSING[/] {worktree_path} does not exist")
        raise typer.Exit(code=1)

    console.print(
        f"[green]MICRO_DRAIN[/] entering worktree {worktree_path} "
        f"to drain PENDING tasks"
    )

    # ``deviate micro run --all`` accepts ``profile`` + boolean overrides
    # + ``agent`` + ``--json``. The new ``deviate run`` carries the same
    # flags through; ``profile``/``no_judge``/``no_refactor`` are honored
    # exactly as if the user had typed ``deviate micro run --all ...``.
    # ``_run_all`` only takes boolean overrides (not the profile enum),
    # so we resolve the booleans via ``resolve_profile`` to stay aligned
    # with the micro layer's own profile semantics.
    from deviate.core.profile import resolve_profile  # local: avoids top-level cycle

    effective_no_judge, effective_no_refactor = resolve_profile(
        profile, no_judge, no_refactor
    )

    with chdir(worktree_path):
        root = worktree_path
        dot_dir = root / ".deviate"
        session_path = dot_dir / "session.json"
        if session_path.exists():
            session = SessionState.load(session_path)
            session = SessionState(
                current_phase=session.current_phase,
                active_issue_id=session.active_issue_id,
                last_command="run --all",
            )
            session.save(session_path)
        _run_all(
            root,
            console,
            no_judge=effective_no_judge,
            no_refactor=effective_no_refactor,
            agent=agent,
            json_mode=json_mode,
        )
