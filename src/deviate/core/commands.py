from __future__ import annotations

import importlib.resources
import re
from pathlib import Path


def _resolve_commands_root(commands_root: Path | None = None) -> Path:
    if commands_root is not None:
        return commands_root
    try:
        return Path(importlib.resources.files("deviate.prompts").joinpath("commands"))
    except (ModuleNotFoundError, TypeError, FileNotFoundError):
        fallback = Path("src/deviate/prompts/commands")
        if fallback.exists():
            return fallback
        return Path() / "src" / "deviate" / "prompts" / "commands"


def discover_commands(commands_root: Path | None = None) -> list[str]:
    root = _resolve_commands_root(commands_root)
    if not root.exists():
        return []
    return sorted(p.stem for p in root.glob("*.md") if p.is_file())


def resolve_command(name: str, commands_root: Path | None = None) -> Path:
    root = _resolve_commands_root(commands_root)
    command_path = root / f"{name}.md"
    if not command_path.exists():
        raise FileNotFoundError(f"Command '{name}' not found at {command_path}")
    return command_path


# ---------------------------------------------------------------------------
# Layer prefix for cache-invariant command composition
# ---------------------------------------------------------------------------

_LAYER_RE = re.compile(r"^layer:\s*(.+)\s*$", re.MULTILINE)
_YAML_FM_RE = re.compile(r"^(---\n.*?\n---)\n", re.DOTALL)


def _read_text(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _resolve_core_dir() -> Path | None:
    try:
        return Path(importlib.resources.files("deviate.prompts").joinpath("core"))
    except (ModuleNotFoundError, TypeError):
        fallback = Path("src/deviate/prompts/core")
        return fallback if fallback.exists() else None


def compose_command_body(raw: str, core_dir: Path) -> str | None:
    """Compose a command body by prepending core.md and layer-command.md.

    Returns the full composed text (frontmatter + prefix + original body),
    or *None* if *raw* has no valid YAML frontmatter.

    The *core_dir* must contain ``core.md`` and ``{layer}-command.md`` files.
    """
    fm_match = _YAML_FM_RE.match(raw)
    if not fm_match:
        return None

    frontmatter = fm_match.group(1)
    body = raw[fm_match.end() :].lstrip()

    parts: list[str] = []
    core = _read_text(core_dir / "core.md")
    if core:
        parts.append(core)

    layer_match = _LAYER_RE.search(frontmatter)
    if layer_match:
        layer = layer_match.group(1).strip()
        layer_content = _read_text(core_dir / f"{layer}-command.md")
        if layer_content:
            parts.append(layer_content)

    prefix = "\n\n".join(parts) if parts else None
    if prefix:
        body = f"{prefix}\n\n{body}"

    return f"{frontmatter}\n\n{body}"


def _emit_platform_frontmatter(agent: str, name: str, description: str) -> str:
    """Build a minimal per-platform YAML frontmatter block.

    Emits only fields the platform actually recognizes — keeps the
    on-disk command free of DeviaTDD-internal keys (`category`,
    `version`, `aliases`, `layer`) that would clutter slash-command
    autocomplete across heterogeneous backends.
    """
    name_line = f"name: {name}\n" if name else ""
    description_line = f"description: {description}\n" if description else ""
    body = f"---\n{name_line}{description_line}---\n"
    return body


def _strip_deviate_frontmatter(frontmatter: str, name: str) -> tuple[str, str]:
    """Pull `description` out of the source frontmatter and drop internal keys.

    Returns ``(emitted_frontmatter_block, description)``. The emitted
    block is passed to :func:`_emit_platform_frontmatter` to assemble
    the on-disk frontmatter; the description drives ``description:`` in
    every platform's slash-command UI.
    """
    description = ""
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if stripped.startswith("description:"):
            description = stripped.split(":", 1)[1].strip().strip("'\"")
            break
    return "", description


def _read_graphite_routing() -> str | None:
    """Read the conditional `## Graphite Routing` block for deviate-pr."""
    try:
        path = Path(
            importlib.resources.files("deviate.prompts").joinpath(
                "extras/deviate-pr-graphite-routing.md"
            )
        )
        return path.read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError, OSError):
        return None


def _graphite_enabled(workdir: Path) -> bool:
    """Late-bound import to keep `core` free of `state` deps at module load."""
    from deviate.state.config import resolve_graphite_config

    try:
        return resolve_graphite_config(workdir)
    except Exception:
        return False


def install_command(
    name: str,
    target_dir: Path,
    commands_root: Path | None = None,
    workdir: Path | None = None,
    agent: str = "claude",
) -> bool:
    """Install a command as a flat .md file at ``target_dir/<name>.md``.

    Returns ``True`` when the file was created or rewritten, ``False``
    when the on-disk copy already matches the composed output.
    """
    command_path = resolve_command(name, commands_root)
    target_path = target_dir / f"{name}.md"

    raw = _read_text(command_path)
    if raw is None:
        return False

    core_dir = _resolve_core_dir()
    if core_dir is None:
        return False

    composed = compose_command_body(raw, core_dir)
    if composed is None:
        return False

    if name == "deviate-pr" and workdir is not None and _graphite_enabled(workdir):
        routing = _read_graphite_routing()
        if routing:
            composed = f"{composed}\n\n{routing.rstrip()}"

    fm_match = _YAML_FM_RE.match(composed)
    if fm_match:
        _, description = _strip_deviate_frontmatter(fm_match.group(1), name)
        emitted_fm = _emit_platform_frontmatter(agent, name, description)
        composed = f"{emitted_fm}\n{composed[fm_match.end() :]}"

    target_path.parent.mkdir(parents=True, exist_ok=True)

    if target_path.exists() and target_path.read_text(encoding="utf-8") == composed:
        return False

    target_path.write_text(composed, encoding="utf-8")
    return True


def detect_agents(workdir: Path | None = None) -> list[str]:
    """Detect agent platforms from cwd directories.

    Scans *workdir* for ``.claude/``, ``.opencode/``, ``.factory/``, and
    ``.pi/`` subdirectories and returns the matching agent names.
    """
    workdir = workdir or Path.cwd()
    agents: list[str] = []
    for name in ("claude", "opencode", "factory", "pi"):
        if (workdir / f".{name}").is_dir():
            agents.append(name)
    return sorted(agents)
