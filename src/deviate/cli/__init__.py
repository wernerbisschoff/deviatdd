from __future__ import annotations

import importlib.resources
import re
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt

from deviate.state.config import (
    CODEX_DEFAULT_MODEL,
    CODEX_DEFAULT_REASONING_EFFORT,
    SessionState,
    resolve_claim_remote,
)
from deviate.state.config import resolve_base_branch as resolve_base_branch  # noqa: F401
from deviate.cli.macro import explore_app, macro_app, research_app, prd_app, shard_app  # noqa: F401
from deviate.cli.flow_commands import flows_app as flows_app  # noqa: F401
from deviate.cli.meso import (
    _LOCAL_CLAIM_HELP,
    _meso_run,
    merge,
    meso_app,
    plan,
    pr,
    specify,
    tasks,
)
from deviate.cli.micro import (
    _run_all as _run_all,  # noqa: F401  (referenced by tests/test_cli/test_top_level_run.py)
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
from deviate.cli.prune import prune_app
from deviate.cli.walkthrough import walkthrough_app
from deviate.cli._html import html_app
from deviate.core.agent import AGENT_TO_BACKEND as AGENT_TO_BACKEND  # noqa: F401

from deviate.core.agent import resolve_agent_to_backend as _resolve_agent_to_backend  # noqa: F401
from deviate.core.commands import (
    OPTIONAL_PACK_NAMES,
    UnknownPackError,
    commands_for_packs,
    install_command,
    parse_optional_packs,
)
from deviate.ui.checkbox import checkbox_select
from deviate.ui.render import is_interactive

cli = typer.Typer(no_args_is_help=True)
console = Console()

_GOVERNANCE_MODULE = "deviate.prompts.governance"

# User-facing agent platform choices (selectable via --agent and the
# interactive init prompt). Order is intentional: factory/droid (Droid
# ecosystem) come first, then the third-party CLIs. ``codex`` is the
# ChatGPT Codex CLI — a first-class meso/micro backend that installs
# skills under ``.agents/skills/`` rather than ``.codex/prompts``.
AGENT_CHOICES: tuple[str, ...] = (
    "factory",
    "droid",
    "claude",
    "opencode",
    "pi",
    "omp",
    "codex",
)

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


# TOML comment annotations for generated `.deviate/config.toml` — emitted
# inline at the end of the same line as the key.
_CONFIG_TOML_COMMENTS: dict[str, str] = {
    "profile": "micro-run default when --profile is omitted: full or fast",
    "timeout_seconds": "agent spawn + test wall clock (seconds)",
    "base_branch": "worktrees, PR base, review diffs",
    "claim_remote": "push the claim branch as a lock",
    "use_libref": "enable the libref CLI for offline documentation lookups",
    "transport": "pi/omp only; omit on other backends",
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
        line = _serialize_value(key, value)
        if line and comments and key in comments:
            line = f"{line}  # {comments[key]}"
        if line:
            lines.append(line)

    for key, value in tables:
        if not value:
            continue
        lines.append(f"\n[{key}]")
        for k, v in value.items():
            line = _serialize_value(k, v)
            if line and comments and k in comments:
                line = f"{line}  # {comments[k]}"
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


def _toml_table_string(content: str, table: str, key: str) -> str | None:
    """Return the string value of ``[table].key``, or ``None`` if absent."""
    try:
        import tomllib

        data = tomllib.loads(content)
    except Exception:
        return None
    section = data.get(table)
    if not isinstance(section, dict):
        return None
    raw = section.get(key)
    return raw if isinstance(raw, str) else None


def _next_toml_table_index(content: str, start: int) -> int:
    """Return the index of the next ``[table]`` header after *start*, or EOF."""
    match = re.search(r"^\[", content[start:], re.MULTILINE)
    return start + match.start() if match else len(content)


def _upsert_toml_table_string_if_empty(
    content: str, table: str, key: str, value: str
) -> tuple[str, bool]:
    """Insert or fill ``[table].key = "value"`` when the key is missing/empty.

    A non-empty existing string is left untouched. Returns
    ``(new_content, changed)``.
    """
    current = _toml_table_string(content, table, key)
    if current is not None and current.strip():
        return content, False

    new_line = f'{key} = "{value}"'
    header_re = re.compile(rf"^\[{re.escape(table)}\]\s*$", re.MULTILINE)
    header = header_re.search(content)
    if header is None:
        if content and not content.endswith("\n"):
            content += "\n"
        content += f"\n[{table}]\n{new_line}\n"
        return content, True

    table_end = _next_toml_table_index(content, header.end())
    table_body = content[header.end() : table_end]
    key_re = re.compile(rf"^{re.escape(key)}\s*=\s*.*$", re.MULTILINE)
    if key_re.search(table_body):
        table_body = key_re.sub(new_line, table_body, count=1)
    else:
        if table_body and not table_body.endswith("\n"):
            table_body += "\n"
        table_body = f"{table_body}{new_line}\n"
    return content[: header.end()] + table_body + content[table_end:], True


def _apply_codex_setup_defaults(config_path: Path) -> bool:
    """Seed Codex Luna + high thinking when those keys are missing/empty."""
    content = config_path.read_text(encoding="utf-8")
    content, changed_model = _upsert_toml_table_string_if_empty(
        content, "models", "default", CODEX_DEFAULT_MODEL
    )
    content, changed_effort = _upsert_toml_table_string_if_empty(
        content, "agent", "reasoning_effort", CODEX_DEFAULT_REASONING_EFFORT
    )
    if not (changed_model or changed_effort):
        return False
    config_path.write_text(content, encoding="utf-8")
    return True


def _write_agent_block_to_config(config_path: Path, backend: str) -> bool:
    """Rewrite ``[agent]`` to persist *backend* with backend-correct keys.

    Non-pi/omp backends drop ``pi_rpc`` and ``transport``. Pi/OMP keep
    ``transport`` (default ``rpc``) and never write ``pi_rpc``. Other
    tables in the file are preserved.
    """
    content = config_path.read_text(encoding="utf-8")
    new_content, changed = _rewrite_agent_table(content, backend)
    if not changed:
        return False
    config_path.write_text(new_content, encoding="utf-8")
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


def _parse_yes_no(raw: str | None) -> bool | None:
    """Map ``y``/``yes`` → True, ``n``/``no`` → False (strip, case-insensitive)."""
    if raw is None:
        return None
    token = raw.strip().lower()
    if token in {"y", "yes"}:
        return True
    if token in {"n", "no"}:
        return False
    return None


def _parse_local_global(raw: str | None) -> str | None:
    """Map ``l``/``local`` → local, ``g``/``global`` → global (strip, case-insensitive)."""
    if raw is None:
        return None
    token = raw.strip().lower()
    if token in {"l", "local"}:
        return "local"
    if token in {"g", "global"}:
        return "global"
    return None


def _prompt_export_mode(default: str = "local") -> str | None:
    """Ask whether to install prompts/skills locally or under the user tree.

    Default highlight is always ``l`` (this choice is not persisted).
    Accepts ``l``/``g``/``local``/``global``. Returns ``None`` when the
    session is not interactive so the caller keeps local for this run.
    """
    if not is_interactive():
        return None
    default_label = "g" if default == "global" else "l"
    try:
        while True:
            selected = Prompt.ask(
                f"Prompt/skill install {escape('[l]ocal/[g]lobal')}",
                default=default_label,
                console=console,
            )
            parsed = _parse_local_global(selected)
            if parsed is not None:
                return parsed
    except (EOFError, KeyboardInterrupt):
        return None


def _prompt_base_branch(default: str = "main") -> str | None:
    """Ask for the trunk branch used as PR/worktree base.

    Returns the typed name, ``default`` on empty input, and ``None``
    when the session is not interactive.
    """
    if not is_interactive():
        return None
    try:
        selected = Prompt.ask(
            "Base branch",
            default=default,
            console=console,
        )
    except (EOFError, KeyboardInterrupt):
        return None
    if selected is None:
        return None
    stripped = str(selected).strip()
    return stripped or default


def _prompt_claim_remote(default: bool = False) -> bool | None:
    """Ask whether to push claim branches as a remote lock.

    Returns ``False`` when the operator disables push-as-lock,
    ``True`` when they enable it, and ``None`` when the session is not
    interactive so the caller keeps the existing or false default.
    ``default`` is the highlight: ``y`` when the file already has
    ``claim_remote = true``, otherwise ``n``. Accepts ``y``/``n``/``yes``/``no``.
    """
    if not is_interactive():
        return None
    default_label = "y" if default else "n"
    try:
        while True:
            selected = Prompt.ask(
                f"Push claim branches to the remote as a lock {escape('[y]es/[n]o')}",
                default=default_label,
                console=console,
            )
            parsed = _parse_yes_no(selected)
            if parsed is not None:
                return parsed
    except (EOFError, KeyboardInterrupt):
        return None


def _optional_pack_rows() -> tuple[str, ...]:
    """One TTY checkbox row per optional pack (product first)."""
    return OPTIONAL_PACK_NAMES


def _packs_from_selector_picks(picks: list[str]) -> tuple[str, ...]:
    """Interpret TTY checkbox picks into optional pack names."""
    if not picks:
        return ()
    if "all-optional" in picks:
        return OPTIONAL_PACK_NAMES
    return tuple(name for name in picks if name in OPTIONAL_PACK_NAMES)


def _ask_optional_pack_picks() -> list[str]:
    """TTY multi-select: one pack per row; Space toggles; Enter confirms."""
    picks = checkbox_select(
        _optional_pack_rows(),
        title="Optional command packs",
        console=console,
    )
    if picks:
        console.print(f"Optional packs: {', '.join(picks)}")
    else:
        console.print("Optional packs: none (default layers only)")
    return picks


def _prompt_pack_selection() -> tuple[str, ...] | None:
    """Ask which optional command packs to install.

    Returns ``()`` for the default-only set (nothing checked), a tuple
    of optional pack names when the operator toggles some, and ``None``
    when the session is not interactive so the caller keeps default-only.
    """
    if not is_interactive():
        return None
    try:
        return _packs_from_selector_picks(_ask_optional_pack_picks())
    except (EOFError, KeyboardInterrupt):
        return None


def _resolve_setup_optional_packs(packs: str | None) -> tuple[str, ...]:
    """Resolve optional packs from ``--packs`` or a TTY prompt."""
    if packs is not None:
        try:
            return parse_optional_packs(packs)
        except UnknownPackError as exc:
            raise typer.BadParameter(str(exc)) from exc
    prompted = _prompt_pack_selection()
    return prompted if prompted is not None else ()


def _agent_table_for_backend(
    backend: str,
    *,
    reasoning_effort: str | None = None,
    transport: str | None = None,
) -> dict[str, object]:
    """Return the persistable ``[agent]`` keys for *backend*.

    Does not write ``timeout`` — agent spawn and test deadlines both
    read top-level ``timeout_seconds`` (AC-PLAN-005).
    """
    table: dict[str, object] = {"backend": backend}
    if backend in ("pi", "omp"):
        table["transport"] = transport or "rpc"
    if backend == "codex" and reasoning_effort:
        table["reasoning_effort"] = reasoning_effort
    return table


def _parse_existing_agent_table(content: str) -> dict[str, object]:
    try:
        import tomllib

        data = tomllib.loads(content)
    except Exception:
        return {}
    agent = data.get("agent")
    return dict(agent) if isinstance(agent, dict) else {}


def _replace_toml_table(content: str, table: str, body_lines: list[str]) -> str:
    """Replace or append a ``[table]`` section with *body_lines*."""
    header_re = re.compile(rf"^\[{re.escape(table)}\]\s*$", re.MULTILINE)
    header = header_re.search(content)
    block = f"[{table}]\n" + "\n".join(body_lines)
    if not block.endswith("\n"):
        block += "\n"
    if header is None:
        if content and not content.endswith("\n"):
            content += "\n"
        if content and not content.endswith("\n\n"):
            content += "\n"
        return content + block
    table_end = _next_toml_table_index(content, header.end())
    prefix = content[: header.start()]
    suffix = content[table_end:]
    return prefix + block + suffix


def _rewrite_agent_table(content: str, backend: str) -> tuple[str, bool]:
    """Rewrite ``[agent]`` to the backend allowlist; strip dead Pi keys.

    A matching backend with no disallowed keys is left byte-identical so
    re-running setup does not invent ``timeout`` on a hand-edited file.
    """
    existing = _parse_existing_agent_table(content)
    dead = {"pi_rpc", "timeout"}
    if backend not in ("pi", "omp"):
        dead.add("transport")
    extras = {key for key in existing if key in dead}
    if existing.get("backend") == backend and not extras:
        return content, False
    reasoning = existing.get("reasoning_effort")
    if not isinstance(reasoning, str) or not reasoning.strip():
        reasoning = None
    transport = existing.get("transport")
    if not isinstance(transport, str):
        transport = None
    table = _agent_table_for_backend(
        backend,
        reasoning_effort=reasoning,
        transport=transport,
    )
    body = []
    for key, value in table.items():
        line = _serialize_value(key, value)
        if line:
            body.append(line)
    new_content = _replace_toml_table(content, "agent", body)
    return new_content, new_content != content


def _config_dump_dict(
    *,
    claim_remote: bool,
    use_libref: bool,
    agent_backend: str | None,
    base_branch: str = "main",
) -> dict[str, object]:
    """Allowlist payload for a fresh ``config.toml``.

    Setup-only choices (prompt/skill install local vs global) are not
    persisted. ``[agent].timeout`` is dead and is never written.
    """
    backend = agent_backend or "pi"
    agent_update: dict[str, object] = {"backend": backend}
    extra: dict[str, object] = {}
    if backend == "codex":
        agent_update["reasoning_effort"] = CODEX_DEFAULT_REASONING_EFFORT
        extra["models"] = {"default": CODEX_DEFAULT_MODEL}
    agent = _agent_table_for_backend(
        backend,
        reasoning_effort=str(agent_update["reasoning_effort"])
        if "reasoning_effort" in agent_update
        else None,
    )
    payload: dict[str, object] = {
        "profile": "full",
        "timeout_seconds": 1800,
        "base_branch": base_branch,
        "claim_remote": claim_remote,
        "agent": agent,
    }
    if use_libref:
        payload["use_libref"] = True
    payload.update(extra)
    return payload


def _resolve_setup_export_mode(*, agent_export_mode: str | None) -> str:
    """This-run prompt/skill install location. Never persisted.

    An explicit ``--agent-export-mode`` skips the prompt and applies
    to this install only. On a TTY with the flag omitted, always
    prompt (default ``l``). Non-TTY omitted is ``local``.
    """
    if agent_export_mode is not None:
        return agent_export_mode
    if is_interactive():
        prompted = _prompt_export_mode(default="local")
        return prompted or "local"
    return "local"


def _resolve_setup_base_branch(
    *,
    base_branch: str | None,
    config_exists: bool,
    workdir: Path | None = None,
) -> str | None:
    """Decide the ``base_branch`` value written by ``deviate setup``.

    An explicit ``--base-branch`` always writes and skips the prompt.
    On a TTY with the flag omitted, always prompt (even when
    ``config.toml`` exists); default is the current file value or
    ``main``. Non-TTY: no prompt; fresh config writes ``main``;
    existing config is left alone (``None``).
    """
    if base_branch is not None:
        return base_branch
    existing = "main"
    if config_exists and workdir is not None:
        existing = resolve_base_branch(workdir)
    if is_interactive():
        prompted = _prompt_base_branch(default=existing)
        return existing if prompted is None else prompted
    if config_exists:
        return None
    return "main"


def _resolve_setup_claim_remote(
    *,
    claim_remote: bool,
    no_claim_remote: bool,
    config_exists: bool,
    workdir: Path | None = None,
) -> bool | None:
    """Decide the ``claim_remote`` value written by ``deviate setup``.

    ``--claim-remote`` always writes true. ``--no-claim-remote`` always
    writes false. On a TTY with neither flag, always prompt (even when
    ``config.toml`` exists); default is the current file value (``yes``
    if true, ``no`` if false or missing). Non-TTY: no prompt; fresh
    config writes false; existing config is left alone (``None``).
    """
    if no_claim_remote:
        return False
    if claim_remote:
        return True
    existing = False
    if config_exists and workdir is not None:
        existing = resolve_claim_remote(workdir)
    if is_interactive():
        prompted = _prompt_claim_remote(default=existing)
        return existing if prompted is None else prompted
    if config_exists:
        return None
    return False


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


def _resolve_setup_selected_agent(
    agent: str | None,
    workdir: Path,
    config_path: Path,
) -> str:
    """Pick exactly one agent: ``--agent``, TTY selector, or existing backend.

    A TTY always shows the agent menu (existing ``[agent].backend`` is the
    default highlight, not an auto-skip). Non-TTY sessions reuse a
    persisted backend or fail closed with ``NO_AGENT_SELECTED``. Leftover
    agent directories are never consulted.
    """
    if agent is not None:
        return agent
    prompted = _prompt_agent_selection(workdir, config_path)
    if prompted is not None:
        return prompted
    existing = _read_agent_backend_from_config(config_path)
    if existing is not None:
        return existing
    console.print(
        "[red]NO_AGENT_SELECTED[/] No agent platform chosen."
        " Re-run `deviate setup --agent <name>` with one of:"
        f" {', '.join(AGENT_CHOICES)}."
    )
    raise typer.Exit(code=1)


def _resolve_install_agents(selected_agent: str) -> list[str]:
    """Return exactly one install target.

    Never consults ``detect_agents`` or leftover agent directories.
    An empty on-disk agent set is not a reason to install nothing —
    setup creates the selected agent's tree. ``--agent`` and the TTY
    picker resolve a single name first; this helper only wraps that
    name as the install list.
    """
    return [selected_agent]


def _insert_toml_root_line(content: str, line: str) -> str:
    """Insert a root-scope TOML assignment before the first ``[table]`` header."""
    if not line.endswith("\n"):
        line += "\n"
    table_match = re.search(r"^\[.*\]\s*$", content, re.MULTILINE)
    if table_match:
        idx = table_match.start()
        return content[:idx] + line + content[idx:]
    if content and not content.endswith("\n"):
        content += "\n"
    return content + line


def _upsert_toml_bool(content: str, key: str, value: bool) -> str:
    """Replace or insert a top-level boolean assignment in TOML text."""
    new_line = f"{key} = {'true' if value else 'false'}"
    pattern = re.compile(rf"^{re.escape(key)}\s*=\s*.*$", re.MULTILINE)
    if pattern.search(content):
        return pattern.sub(new_line, content)
    return _insert_toml_root_line(content, new_line)


def _upsert_toml_string(content: str, key: str, value: str) -> str:
    """Replace or insert a top-level string assignment in TOML text."""
    new_line = _serialize_value(key, value)
    pattern = re.compile(rf"^{re.escape(key)}\s*=\s*.*$", re.MULTILINE)
    if pattern.search(content):
        return pattern.sub(new_line, content)
    return _insert_toml_root_line(content, new_line)


def _strip_toml_root_key(content: str, key: str) -> str:
    """Remove a top-level assignment (and its trailing newline) if present."""
    pattern = re.compile(rf"^{re.escape(key)}\s*=\s*.*\n?", re.MULTILINE)
    return pattern.sub("", content)


def _merge_flag_keys(
    config_path: Path,
    *,
    use_libref: bool,
    claim_remote: bool | None = None,
    base_branch: str | None = None,
    strip_export_mode: bool = False,
) -> None:
    """Surgically update flag keys in an existing TOML.

    Upserts ``use_libref`` when opted in. Upserts ``claim_remote`` and
    ``base_branch`` only when the caller passed a value (flags or a TTY
    answer). Strips leftover ``agent_export_mode`` when asked — that
    key is setup-only and is never written. Preserves every other
    key/table (e.g. user-customised ``[models]``).
    """
    content = config_path.read_text(encoding="utf-8")
    original = content
    if strip_export_mode:
        content = _strip_toml_root_key(content, "agent_export_mode")
    if claim_remote is not None:
        content = _upsert_toml_bool(content, "claim_remote", claim_remote)
    if base_branch is not None:
        content = _upsert_toml_string(content, "base_branch", base_branch)
    if use_libref:
        content = _upsert_toml_bool(content, "use_libref", True)
    if content != original:
        config_path.write_text(content, encoding="utf-8")


def _scaffold_dotfiles(
    workdir: Path,
    use_libref: bool = False,
    claim_remote: bool = False,
    force_update_flags: bool = False,
    agent_backend: str | None = None,
    update_claim_remote: bool = False,
    update_base_branch: bool = False,
    base_branch: str = "main",
    strip_stale_keys: bool = False,
) -> None:
    dot_dir = workdir / ".deviate"
    _ensure_dir(dot_dir)
    _ensure_dir(dot_dir / "artifacts")

    config_path = dot_dir / "config.toml"
    if (
        config_path.exists()
        and not force_update_flags
        and agent_backend is None
        and not update_claim_remote
        and not update_base_branch
        and not strip_stale_keys
    ):
        console.print(f"  [yellow]SKIP[/] {config_path.name} already exists")
    elif config_path.exists():
        # Existing config: only touch the keys the caller asked us to touch.
        # `use_libref` is upserted when `--libref` was passed.
        # `claim_remote` and `base_branch` are upserted on flags or a TTY
        # answer. Leftover `agent_export_mode` is stripped — setup-only.
        # `agent_backend` is always upserted when provided so `--agent factory`
        # can overwrite a previously persisted backend.
        changed = False
        should_merge = (
            force_update_flags
            or update_claim_remote
            or update_base_branch
            or strip_stale_keys
        )
        if should_merge:
            _merge_flag_keys(
                config_path,
                use_libref=use_libref,
                claim_remote=claim_remote if update_claim_remote else None,
                base_branch=base_branch if update_base_branch else None,
                strip_export_mode=strip_stale_keys,
            )
            changed = True
        if agent_backend is not None:
            changed = (
                _write_agent_block_to_config(config_path, agent_backend) or changed
            )
            if agent_backend == "codex":
                changed = _apply_codex_setup_defaults(config_path) or changed
        if changed:
            console.print(f"  [green]UPDATE[/] {config_path.name} flags merged")
        else:
            console.print(f"  [yellow]SKIP[/] {config_path.name} already exists")
    else:
        payload = _config_dump_dict(
            claim_remote=claim_remote,
            use_libref=use_libref,
            agent_backend=agent_backend,
            base_branch=base_branch,
        )
        _write_if_missing(
            config_path,
            _dict_to_toml(payload, comments=_CONFIG_TOML_COMMENTS),
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


def _apply_governance(workdir: Path, use_libref: bool = False) -> None:
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

    if use_libref:
        libref_content = _read_seed(_GOVERNANCE_MODULE, "libref_seed.md")
        if libref_content:
            for t in targets:
                _upsert_governance_block(t, libref_content)


def _user_home() -> Path:
    """Return the operator home directory (monkeypatch seam for tests)."""
    return Path.home()


def _agent_install_root(workdir: Path, export_mode: str) -> Path:
    """Project workdir for local installs; user home for global."""
    return _user_home() if export_mode == "global" else workdir


def _display_install_path(target: Path, workdir: Path) -> str:
    """Prefer a workdir-relative path; fall back to the absolute path.

    Global installs live under the user home tree, so
    ``target.relative_to(workdir)`` raises ``ValueError``.
    """
    try:
        return str(target.relative_to(workdir))
    except ValueError:
        return str(target)


def _get_agent_command_dir(agent_name: str, workdir: Path) -> Path | None:
    """Resolve the slash-command directory for a given agent platform.

    Factory, Claude, OpenCode discover slash commands from
    ``<workdir>/.{agent}/commands/`` (flat top-level only). Pi and OMP use
    ``<workdir>/.{agent}/prompts/`` per their platform conventions.
    Codex CLI 0.117+ dropped custom prompts — return ``None`` so setup
    never writes ``.codex/prompts`` or ``.codex/commands``.
    """
    if agent_name in ("claude", "opencode", "factory"):
        return workdir / f".{agent_name}" / "commands"
    if agent_name == "pi":
        return workdir / ".pi" / "prompts"
    if agent_name == "omp":
        return workdir / ".omp" / "prompts"
    return None


def _skip_unknown_agent(agent: str, target_dir: Path | None) -> bool:
    """Report and skip agents with no install directory."""
    if target_dir is not None:
        return False
    console.print(f"  [yellow]SKIP[/] Unknown agent: {agent}")
    return True


def _install_commands_to_agents(
    workdir: Path,
    agents: list[str],
    command_names: list[str] | None = None,
    use_libref: bool = False,
    export_mode: str = "local",
) -> None:
    """Install the selected command packs into the selected agent directories.

    Output is aggregated per-agent — one summary line per agent instead of
    one line per (command × agent) — to keep ``deviate setup`` output
    readable when many commands are written to a single selected agent.
    ``export_mode="global"`` writes under the user-level agent tree;
    ``workdir`` stays the project root for constitution composition.
    """
    commands = command_names if command_names is not None else commands_for_packs()
    if not commands:
        return
    install_root = _agent_install_root(workdir, export_mode)
    for agent in agents:
        if agent == "codex":
            _install_codex_command_skills(
                workdir,
                command_names=commands,
                use_libref=use_libref,
                export_mode=export_mode,
            )
            continue
        target_dir = _get_agent_command_dir(agent, install_root)
        if _skip_unknown_agent(agent, target_dir):
            continue
        installed = 0
        skipped = 0
        for command_name in commands:
            if install_command(
                command_name,
                target_dir,
                workdir=workdir,
                agent=agent,
                use_libref=use_libref,
            ):
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


def _install_codex_command_skills(
    workdir: Path,
    command_names: list[str] | None = None,
    use_libref: bool = False,
    export_mode: str = "local",
) -> None:
    """Install selected packaged slash commands as Codex project skills.

    Codex CLI 0.117+ dropped ``~/.codex/prompts`` and ``/prompts:``.
    Official project-local discovery is ``.agents/skills/<name>/SKILL.md``
    (scanned from CWD up to the repo root). Global mode writes the same
    layout under ``~/.agents/skills``. Reuse the composed command
    bodies via :func:`install_command` — do not invent new prompt text.
    """
    commands = command_names if command_names is not None else commands_for_packs()
    if not commands:
        return
    installed = 0
    skipped = 0
    install_root = _agent_install_root(workdir, export_mode)
    skills_root = install_root / ".agents" / "skills"
    for command_name in commands:
        if install_command(
            command_name,
            skills_root / command_name,
            workdir=workdir,
            agent="codex",
            target_filename="SKILL.md",
            use_libref=use_libref,
        ):
            installed += 1
        else:
            skipped += 1
    if installed and not skipped:
        console.print(f"  [green]INSTALL[/] {installed} commands → codex")
    elif skipped and not installed:
        console.print(f"  [yellow]SKIP[/] {skipped} commands → codex")
    else:
        console.print(
            f"  [green]INSTALL[/] {installed}, [yellow]SKIP[/] {skipped} → codex"
        )


def _resolve_skill_source() -> str | None:
    """Load the deviatdd SKILL.md body from package resources."""
    try:
        path = importlib.resources.files("deviate.prompts.skills.deviatdd").joinpath(
            "SKILL.md"
        )
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, TypeError):
        fallback = Path("src/deviate/prompts/skills/deviatdd") / "SKILL.md"
        if fallback.exists():
            return fallback.read_text(encoding="utf-8")
        return None


def _get_agent_skill_dir(workdir: Path, agent: str) -> Path | None:
    """Return the project-local skills directory for *agent*.

    Setup installs the ``deviatdd`` skill only for the selected agent
    (``droid`` is normalized to ``factory`` before this helper runs).
    The skill body is identical across platforms — only the destination
    directory differs.

    Auto-discovery status per platform:

    - ``claude`` — verified. Same form as user-level
      ``~/.claude/skills/<name>/SKILL.md`` per the Agent Skills spec.
    - ``pi`` — verified. ``pi@latest`` docs at
      ``packages/coding-agent/docs/skills.md`` list ``.pi/skills/`` as
      a project-local skill discovery path.
    - ``opencode`` / ``factory`` — no documented project-local skills
      convention; the file is still written so the skill is on disk if
      those platforms add support. Operators using these backends can
      invoke ``/deviatdd`` via the slash-command path
      ``<workdir>/.opencode/commands/deviatdd.md`` (symlink not
      provided; copy manually if your platform doesn't pick up
      ``skills/``).
    - ``omp`` — libref (``oh-my-pi@latest``) documents skills at
      user-level ``~/.omp/agent/managed-skills/<name>/SKILL.md`` and
      via a settings-driven ``skills`` array, with no project-local
      auto-discovery. The file is still written to
      ``<workdir>/.omp/skills/deviatdd/SKILL.md`` so operators can
      register it via OMP's ``skills`` array in settings or copy it
      to the user-level path.
    - ``codex`` — official project-local discovery is
      ``<workdir>/.agents/skills/<name>/SKILL.md``. Codex CLI 0.117+
      dropped ``.codex/prompts`` / ``/prompts:``.
    - ``droid`` — normalized to ``factory`` at the command-install
      layer; not iterated separately here.

    Returns ``None`` for unknown agent names.
    """
    if agent == "codex":
        return workdir / ".agents" / "skills"
    if agent in ("claude", "opencode", "factory", "pi", "omp"):
        return workdir / f".{agent}" / "skills"
    return None


def _install_deviatdd_skill(
    workdir: Path, agents: list[str], export_mode: str = "local"
) -> None:
    """Provision the packaged deviatdd skill for every active agent."""
    body = _resolve_skill_source()
    if body is None:
        console.print("  [yellow]SKIP[/] deviatdd skill source missing")
        return
    install_root = _agent_install_root(workdir, export_mode)
    for agent in agents:
        target_dir = _get_agent_skill_dir(install_root, agent)
        if _skip_unknown_agent(agent, target_dir):
            continue
        target = target_dir / "deviatdd" / "SKILL.md"
        if target.exists() and target.read_text(encoding="utf-8") == body:
            console.print(f"  [yellow]SKIP[/] {_display_install_path(target, workdir)}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        console.print(f"  [green]INSTALL[/] {_display_install_path(target, workdir)}")


def _ensure_gitignore(workdir: Path) -> None:
    dot_dir = workdir / ".deviate"
    dot_dir.mkdir(parents=True, exist_ok=True)
    gitignore = dot_dir / ".gitignore"
    entries = [
        "session.json",
        "artifacts/",
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


def _validate_export_mode(value: str | None) -> str | None:
    """Typer callback: ``--agent-export-mode`` is local, global, or omitted."""
    if value is None:
        return None
    if value not in ("local", "global"):
        raise typer.BadParameter(
            f"Invalid agent export mode '{value}'. Must be one of: local, global"
        )
    return value


def _validate_base_branch(value: str | None) -> str | None:
    """Typer callback: ``--base-branch`` must be a non-empty name when passed."""
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        raise typer.BadParameter("Base branch must be a non-empty name")
    return stripped


@cli.command(name="setup", rich_help_panel="Run by you (start here)")
def setup(
    agent_export_mode: str | None = typer.Option(
        None,
        "--agent-export-mode",
        help="Export mode for agent commands (local or global). Omitted on a TTY prompts.",
        callback=_validate_export_mode,
    ),
    base_branch: str | None = typer.Option(
        None,
        "--base-branch",
        help="Trunk branch for worktrees and PRs. Omitted on a TTY prompts.",
        callback=_validate_base_branch,
    ),
    libref: bool = typer.Option(
        False,
        "--libref",
        help="Enable offline libref CLI integration in generated config, prompts, and skills",
    ),
    agent: str | None = typer.Option(
        None,
        "--agent",
        help="Agent platform to install and persist as [agent].backend",
        callback=_validate_agent_choice,
    ),
    claim_remote: bool = typer.Option(
        False,
        "--claim-remote",
        help="Enable push-as-lock; write claim_remote = true",
    ),
    no_claim_remote: bool = typer.Option(
        False,
        "--no-claim-remote",
        help="Disable push-as-lock; write claim_remote = false",
    ),
    packs: str | None = typer.Option(
        None,
        "--packs",
        help=(
            "Optional packs on top of default macro+meso+micro "
            "(product, merge, pr, review, walkthrough, html, hotfix, "
            "triage, prune, e2e). 'none', 'all-optional', or "
            "comma-separated names. Unknown names fail closed. "
            "Setup does not commit."
        ),
    ),
) -> None:
    """Bootstrap a new project with DeviaTDD (start here).

    Writes ``.deviate/`` and installs default packs (macro+meso+micro)
    plus the shared ``deviatdd`` skill. Does not commit.
    Non-TTY without ``--agent`` fails closed with ``NO_AGENT_SELECTED``;
    unknown ``--packs`` fails closed. ``claim_remote`` defaults to false.
    """
    workdir = Path.cwd()
    config_path = workdir / ".deviate" / "config.toml"

    console.print("[bold]Initializing deviate workspace...[/bold]")

    selected_agent = _resolve_setup_selected_agent(agent, workdir, config_path)
    install_agents = _resolve_install_agents(selected_agent)

    backend = _resolve_agent_to_backend(selected_agent)
    if claim_remote and no_claim_remote:
        console.print(
            "[red]CONFLICT[/] --claim-remote and --no-claim-remote are "
            "mutually exclusive."
        )
        raise typer.Exit(code=1)
    config_exists = config_path.exists()
    install_mode = _resolve_setup_export_mode(agent_export_mode=agent_export_mode)
    base_branch_val = _resolve_setup_base_branch(
        base_branch=base_branch,
        config_exists=config_exists,
        workdir=workdir,
    )
    claim_remote_val = _resolve_setup_claim_remote(
        claim_remote=claim_remote,
        no_claim_remote=no_claim_remote,
        config_exists=config_exists,
        workdir=workdir,
    )
    update_base = base_branch_val is not None
    update_claim = claim_remote_val is not None
    strip_stale = is_interactive() or agent_export_mode is not None

    use_libref_val = bool(libref)
    _scaffold_dotfiles(
        workdir,
        use_libref=use_libref_val,
        claim_remote=bool(claim_remote_val),
        force_update_flags=libref or update_claim or update_base or strip_stale,
        agent_backend=backend,
        update_claim_remote=update_claim,
        update_base_branch=update_base,
        base_branch=base_branch_val or "main",
        strip_stale_keys=strip_stale,
    )

    _apply_governance(workdir, use_libref=use_libref_val)

    # Install commands + the packaged skill only for the one selected agent.
    # ``--agent`` pins the target without prompting. On a TTY, omitted
    # ``--agent`` always shows the agent selector. Pack selection via
    # ``--packs`` or the TTY pack selector governs which command files
    # are written.
    # ``droid`` is normalised to ``factory`` so both names write
    # ``.factory/``. Codex is a first-class backend that writes skills
    # under ``.agents/skills/`` (Codex CLI 0.117+ dropped custom prompts).
    # ``pi`` uses ``.pi/prompts/``; ``omp`` uses ``.omp/prompts/``; the
    # remaining CLIs use ``commands/``. No global ``~/.pi/agent/`` writes,
    # no ``settings.json`` generation — the operator's Pi config is out of
    # scope.
    optional_packs = _resolve_setup_optional_packs(packs)
    command_names = commands_for_packs(optional_packs)
    _install_commands_to_agents(
        workdir,
        install_agents,
        command_names=command_names,
        use_libref=use_libref_val,
        export_mode=install_mode,
    )
    _install_deviatdd_skill(workdir, install_agents, export_mode=install_mode)

    _ensure_gitignore(workdir)
    _ensure_root_gitignore(workdir)
    _ensure_root_gitattributes(workdir)

    console.print(
        "\nNext: run [bold]/deviate-init[/bold] as the first prompt in your "
        "agent (Codex: the [bold]deviate-init[/bold] skill). "
        "It is a no-op if the repo is already scaffolded."
    )


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
    "specs/_product/flows.jsonl merge=union\n"
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
    artifacts and workspace state on all agent platforms.
    Six entry groups must not be committed:
    - ``deviate-*`` commands under ``<agent>/commands/`` and
      ``<agent>/prompts/`` — the core DeviaTDD command library.
    - The ``deviatdd`` skill under ``<agent>/skills/deviatdd/``.
    - Codex per-command skills under ``.agents/skills/deviate-*/``.
    - ``.worktrees/`` — isolated task worktrees managed by DeviaTDD.
    - ``.deviate/`` — per-project runtime state and local config.
    """
    entries = (
        "*/commands/deviate-*.md",
        "*/prompts/deviate-*.md",
        "*/skills/deviatdd/",
        "*/skills/deviate-*/",
        ".worktrees/",
        ".deviate/",
    )
    gitignore_path = workdir / ".gitignore"
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
        console.print(f"  [green]UPDATE[/] .gitignore added {len(missing)} entries")
    else:
        gitignore_path.write_text("\n".join(entries) + "\n", encoding="utf-8")
        console.print(f"  [green]CREATE[/] .gitignore with {len(entries)} entries")


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
cli.add_typer(
    flows_app,
    name="flows",
    rich_help_panel=_USER_PANEL,
    help="Flow ledger commands (sync the canonical flow index into flows.jsonl)",
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
    help="Macro: shard feature into issues",
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
    help="Macro: low/medium-complexity shortcut (post commits artifacts; stays BACKLOG)",
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
    help="Gate 3 comments-only PR scan; --apply is CRITICAL-only (not a merge gate)",
)
cli.add_typer(
    prune_app,
    name="prune",
    rich_help_panel=_AGENT_PANEL,
    help="Manual honeycomb test thinning",
)
cli.add_typer(
    walkthrough_app,
    name="walkthrough",
    rich_help_panel=_AGENT_PANEL,
    help="Four-look map: brief, tests, production vs checks, command (optional pack)",
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
#   - `micro run`        — drains the task queue.
#   - `run` (this)       — chains meso into micro end-to-end (no Gate 2).
# `micro run` itself is surfaced as the `micro` Typer group so future
# micro-layer helpers (e.g. `micro run --task <id>`) can ride along.
cli.add_typer(
    meso_app,
    name="meso",
    rich_help_panel=_USER_PANEL,
    help="Use `deviate meso run` to run the automated setup → plan → tasks pipeline (spawns agent; post commits)",
)
cli.add_typer(
    micro_app,
    name="micro",
    rich_help_panel=_USER_PANEL,
    help="Drain the task queue (single or --all) inside a worktree — `deviate micro run --all` is the user-facing micro drain (each phase commits; spawns agent)",
)
cli.add_typer(
    html_app,
    name="html",
    rich_help_panel=_AGENT_PANEL,
    help="Write per-phase HTML starter scaffolds (plan, prd, flows, architecture, domain-model). Agent-internal — invoked from the /deviate-html slash command, not by hand.",
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
    model: str | None = typer.Option(
        None,
        "--model",
        help="Override default model for RED/GREEN/REFACTOR/EXECUTE phases",
    ),
    local: bool = typer.Option(
        False,
        "--local",
        help=_LOCAL_CLAIM_HELP,
    ),
) -> None:
    """Prepare the next issue end-to-end and run it.

    Runs the meso pipeline (SPECIFY setup → PLAN → TASKS) inside the created
    worktree, then immediately chains into ``deviate micro run --all`` to drain
    the task queue. There is no human-approval step between meso and micro —
    the system auto-advances. Nested spawn + phase commits (same as
    ``meso run`` then ``micro run --all``). ``claim_remote`` defaults false;
    ``--local`` skips the remote lock.

    The per-task / ``--all`` dispatcher can also be invoked directly via
    ``deviate micro run`` if you only want to drain pending tasks without
    re-running meso.
    """
    worktree_path_str = _meso_run(issue_id=issue, force=force, local=local)
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

    # Chain into micro: drain the task queue in the worktree the meso step just
    # prepared. There is no approval step between meso and micro.
    _run_all(worktree_path, console, model=model)
