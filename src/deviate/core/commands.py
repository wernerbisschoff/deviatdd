from __future__ import annotations

import importlib.resources
import re
from pathlib import Path


def _prompts_dir(subdir: str) -> Path:
    """Locate ``deviate.prompts/<subdir>`` in the package.

    Falls back to the source tree for runs outside an installed
    distribution (editable installs, worktrees).
    """
    try:
        return Path(importlib.resources.files("deviate.prompts").joinpath(subdir))
    except (ModuleNotFoundError, TypeError, FileNotFoundError):
        return Path("src/deviate/prompts") / subdir


def _resolve_commands_root(commands_root: Path | None = None) -> Path:
    if commands_root is not None:
        return commands_root
    return _prompts_dir("commands")


def discover_commands(commands_root: Path | None = None) -> list[str]:
    root = _resolve_commands_root(commands_root)
    if not root.exists():
        return []
    return sorted(p.stem for p in root.glob("*.md") if p.is_file())


DEFAULT_LAYER_PACKS: dict[str, tuple[str, ...]] = {
    "product": ("deviate-flows", "deviate-architecture", "deviate-release"),
    "macro": (
        "deviate-explore",
        "deviate-research",
        "deviate-prd",
        "deviate-shard",
        "deviate-adhoc",
        "deviate-constitution",
        "deviate-init",
    ),
    "meso": ("deviate-plan", "deviate-tasks"),
    "micro": (
        "deviate-red",
        "deviate-green",
        "deviate-judge",
        "deviate-refactor",
        "deviate-execute",
    ),
}
OPTIONAL_PACKS: dict[str, tuple[str, ...]] = {
    "merge": ("deviate-merge",),
    "pr": ("deviate-pr",),
    "review": ("deviate-review",),
    "walkthrough": ("deviate-walkthrough",),
    "html": ("deviate-html",),
    "hotfix": ("deviate-hotfix",),
    "triage": ("deviate-triage",),
    "prune": ("deviate-prune",),
    "e2e": ("deviate-e2e",),
}
DEFAULT_PACK_NAMES: tuple[str, ...] = ("product", "macro", "meso", "micro")
OPTIONAL_PACK_NAMES: tuple[str, ...] = tuple(OPTIONAL_PACKS)


class UnknownPackError(ValueError):
    """Raised when ``--packs`` names a pack that is not optional."""


def command_pack_index() -> dict[str, str]:
    """Map each command stem to ``default:<layer>`` or ``optional:<pack>``."""
    index: dict[str, str] = {}
    for name, commands in DEFAULT_LAYER_PACKS.items():
        for command in commands:
            index[command] = f"default:{name}"
    for name, commands in OPTIONAL_PACKS.items():
        for command in commands:
            index[command] = f"optional:{name}"
    return index


def classify_packaged_stems(commands_root: Path | None = None) -> list[str]:
    """Return unclassified packaged stems (empty when the map is complete)."""
    index = command_pack_index()
    return [stem for stem in discover_commands(commands_root) if stem not in index]


def parse_optional_packs(raw: str | None) -> tuple[str, ...]:
    """Parse a ``--packs`` value into optional pack names.

    ``None`` means the caller should prompt or use the default-only set.
    ``none`` / empty → no optional packs. ``all-optional`` → every optional pack.
    """
    if raw is None:
        return ()
    token = raw.strip().lower()
    if not token or token == "none":
        return ()
    if token in {"all-optional", "all"}:
        return OPTIONAL_PACK_NAMES
    names = tuple(part.strip().lower() for part in token.split(",") if part.strip())
    unknown = [name for name in names if name not in OPTIONAL_PACKS]
    if unknown:
        raise UnknownPackError(
            f"Unknown pack(s): {', '.join(unknown)}. "
            f"Optional packs: {', '.join(OPTIONAL_PACK_NAMES)}"
        )
    return names


def commands_for_packs(optional_packs: tuple[str, ...] = ()) -> list[str]:
    """Return command stems for default layer packs plus selected optional packs."""
    stems: list[str] = []
    for commands in DEFAULT_LAYER_PACKS.values():
        stems.extend(commands)
    for name in optional_packs:
        stems.extend(OPTIONAL_PACKS[name])
    return stems


def redact_libref(text: str) -> str:
    """Drop lines that mention libref so default installs stay clean."""
    lines = []
    for line in text.splitlines(keepends=True):
        if "libref" in line.lower():
            continue
        lines.append(line)
    return "".join(lines)


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
    core_dir = _prompts_dir("core")
    return core_dir if core_dir.exists() else None


# ---------------------------------------------------------------------------
# Canonical auto core for manual slash-command derivation
# ---------------------------------------------------------------------------

# The 11 phases with a canonical ``auto/{phase}.md`` core. The manual
# slash-command body is derived from this core plus a per-phase manual
# overlay at install time — there is no hand-maintained duplicate middle
# file to drift from the auto semantics. The 15 commands-only prompts
# (adhoc, architecture, constitution, e2e, flows, hotfix, html, init,
# merge, pr, prune, release, review, triage, walkthrough) have no auto
# counterpart and stay hand-maintained.
_OVERLAPPING_PHASES = frozenset(
    {
        "explore",
        "research",
        "prd",
        "shard",
        "plan",
        "tasks",
        "red",
        "green",
        "refactor",
        "judge",
        "execute",
    }
)


def _manual_phase(name: str) -> str | None:
    """Return the canonical auto phase for a manual command name.

    Returns ``None`` for the commands-only prompts (no auto counterpart) and
    for names outside the ``deviate-`` prefix namespace.
    """
    if not name.startswith("deviate-"):
        return None
    phase = name[len("deviate-") :]
    return phase if phase in _OVERLAPPING_PHASES else None


def _read_auto_body(phase: str) -> str | None:
    """Read the canonical ``auto/{phase}.md`` core body."""
    return _read_text(_prompts_dir("auto") / f"{phase}.md")


def _derive_manual_body(name: str, raw: str) -> str | None:
    """Derive the manual slash-command body from the canonical auto core.

    For the 11 overlapping phases the command source carries only the
    frontmatter and the per-phase manual overlay; the middle body comes from
    ``auto/{phase}.md`` and is spliced verbatim so the installed middle stays
    byte-identical to the auto core. Returns ``raw`` unchanged for the
    commands-only prompts (no auto counterpart) and ``None`` when the auto
    core is missing or the source has no YAML frontmatter.
    """
    phase = _manual_phase(name)
    if phase is None:
        return raw
    auto_body = _read_auto_body(phase)
    if auto_body is None:
        return None
    fm_match = _YAML_FM_RE.match(raw)
    if not fm_match:
        return None
    derived = f"{fm_match.group(1)}\n\n{auto_body}"
    overlay = raw[fm_match.end() :].strip()
    if overlay:
        derived = f"{derived}\n\n{overlay}"
    return derived


def compose_command_body(
    raw: str,
    core_dir: Path,
    constitution_path: Path | None = None,
    use_libref: bool = True,
) -> str | None:
    """Compose a command body by prepending core.md, layer-shared.md, and lifecycle-manual.md.

    Returns the full composed text (frontmatter + prefix + original body),
    or *None* if *raw* has no valid YAML frontmatter.

    The *core_dir* must contain ``core.md``, ``{layer}-shared.md`` (shared
    with auto-mode composition in :mod:`deviate.prompts.assembly`), and
    ``lifecycle-manual.md`` (the manual-mode counterpart to
    ``lifecycle-auto.md``).

    When ``constitution_path`` resolves to an existing ``constitution.md``,
    its content is prepended as the first tier of the composed body — the
    same position ``load_template()`` reserves on the auto path. This
    closes the manual/slash-command parity gap so agents running via
    ``/deviate-*`` slash commands see the constitution at the top of the
    prompt and cannot silently substitute a mandated tech-stack component
    (e.g., deferring Phoenix LiveView for a framework-free shell).
    """
    fm_match = _YAML_FM_RE.match(raw)
    if not fm_match:
        return None

    frontmatter = fm_match.group(1)
    body = raw[fm_match.end() :].lstrip()
    parts: list[str] = []

    # 0. Constitution (project governance) — manual-mode parity with
    # deviate.prompts.assembly.load_template. Missing file is non-fatal
    # to match the auto path's tolerance; the constitution is best-effort
    # because deviatdd may run before `deviate init` (greenfield case).
    if constitution_path is not None and constitution_path.is_file():
        try:
            parts.append(constitution_path.read_text(encoding="utf-8"))
        except OSError:
            pass

    # 1. Universal core
    core = _read_text(core_dir / "core.md")
    if core:
        parts.append(core)

    # 2. Layer-specific preamble (shared between auto and manual modes)
    layer_match = _LAYER_RE.search(frontmatter)
    layer = layer_match.group(1).strip() if layer_match else None
    if layer:
        layer_content = _read_text(core_dir / f"{layer}-shared.md")
        if layer_content:
            parts.append(layer_content)
    # 3. Lifecycle block — branch on layer.
    # Manual-mode (plan/specify/tasks/pr/merge) prepends ``lifecycle-manual.md``
    # which documents ``deviate <phase> pre`` / ``deviate <phase> post`` scripts.
    # Product-layer commands (release/architecture/flows) have no pre/post
    # scripts; they commit a single artifact via
    # ``deviate.core.commit.commit_artifact`` and the layer-shared block above
    # already documents that lifecycle. Skip the manual block here so the agent
    # does not attempt to run ``deviate release pre`` (no such subcommand).
    if layer != "product":
        lifecycle = _read_text(core_dir / "lifecycle-manual.md")
        if lifecycle:
            parts.append(lifecycle)

    # 4. ASD-STE100 writing-style directive (prose + structured discipline) —
    # sibling of lifecycle-manual.md; mirrors the auto-mode injection in
    # deviate.prompts.assembly.load_template.
    style = _read_text(core_dir / "style-ste.md")
    if style:
        parts.append(style)

    prefix = "\n\n".join(parts) if parts else None
    if prefix:
        body = f"{prefix}\n\n{body}"

    composed = f"{frontmatter}\n\n{body}"
    if not use_libref:
        composed = redact_libref(composed)
    return composed


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


def _extract_description(frontmatter: str) -> str:
    """Pull the ``description`` value out of a source frontmatter block."""
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if stripped.startswith("description:"):
            return stripped.split(":", 1)[1].strip().strip("'\"")
    return ""


def install_command(
    name: str,
    target_dir: Path,
    commands_root: Path | None = None,
    workdir: Path | None = None,
    agent: str = "claude",
    target_filename: str | None = None,
    use_libref: bool = True,
) -> bool:
    """Install a command as a flat file at ``target_dir/<name>.md``.

    Pass ``target_filename`` to override the basename (Codex skills use
    ``SKILL.md``). Returns ``True`` when the file was created or
    rewritten, ``False`` when the on-disk copy already matches the
    composed output.
    """
    command_path = resolve_command(name, commands_root)
    target_path = target_dir / (target_filename or f"{name}.md")

    raw = _read_text(command_path)
    if raw is None:
        return False

    # The auto core enters the manual verbatim: the derived middle stays
    # byte-identical to auto/{phase}.md (the drift-guard invariant).
    derived = _derive_manual_body(name, raw)
    if derived is None:
        return False
    raw = derived

    core_dir = _resolve_core_dir()
    if core_dir is None:
        return False

    # Resolve the project's constitution from <workdir>/specs/constitution.md
    # (when workdir is provided). The path is best-effort: a missing file is
    # non-fatal because `deviate setup` may run before `deviate research`
    # scaffolds the constitution in a greenfield repo.
    constitution_path: Path | None = None
    if workdir is not None:
        candidate = workdir / "specs" / "constitution.md"
        if candidate.is_file():
            constitution_path = candidate

    composed = compose_command_body(
        raw, core_dir, constitution_path=constitution_path, use_libref=use_libref
    )
    if composed is None:
        return False

    fm_match = _YAML_FM_RE.match(composed)
    if fm_match:
        description = _extract_description(fm_match.group(1))
        emitted_fm = _emit_platform_frontmatter(agent, name, description)
        composed = f"{emitted_fm}\n{composed[fm_match.end() :]}"

    target_path.parent.mkdir(parents=True, exist_ok=True)

    if target_path.exists() and target_path.read_text(encoding="utf-8") == composed:
        return False

    target_path.write_text(composed, encoding="utf-8")
    return True


def detect_agents(workdir: Path | None = None) -> list[str]:
    """Detect agent platforms from cwd directories.

    Scans *workdir* for ``.claude/``, ``.opencode/``, ``.factory/``,
    ``.pi/``, and ``.omp/`` subdirectories and returns the matching
    agent names.
    """
    workdir = workdir or Path.cwd()
    agents: list[str] = []
    for name in ("claude", "opencode", "factory", "pi", "omp"):
        if (workdir / f".{name}").is_dir():
            agents.append(name)
    return sorted(agents)
