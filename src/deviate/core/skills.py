from __future__ import annotations

import importlib.resources
import re
from pathlib import Path


def _resolve_skills_root(skills_root: Path | None = None) -> Path:
    if skills_root is not None:
        return skills_root
    try:
        return Path(importlib.resources.files("deviate.prompts").joinpath("skills"))
    except (ModuleNotFoundError, TypeError, FileNotFoundError):
        fallback = Path("src/deviate/prompts/skills")
        if fallback.exists():
            return fallback
        return Path() / "src" / "deviate" / "prompts" / "skills"


def discover_skills(skills_root: Path | None = None) -> list[str]:
    root = _resolve_skills_root(skills_root)
    if not root.exists():
        return []
    return sorted(
        d.name for d in root.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
    )


def resolve_skill(name: str, skills_root: Path | None = None) -> Path:
    root = _resolve_skills_root(skills_root)
    skill_path = root / name / "SKILL.md"
    if not skill_path.exists():
        raise FileNotFoundError(f"Skill '{name}' not found at {skill_path}")
    return skill_path


# ---------------------------------------------------------------------------
# Layer prefix for cache-invariant skill composition
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


def compose_skill_body(raw: str, core_dir: Path) -> str | None:
    """Compose a skill body by prepending core.md and layer-skill.md.

    Returns the full composed text (frontmatter + prefix + original body),
    or *None* if *raw* has no valid YAML frontmatter.

    The *core_dir* must contain ``core.md`` and ``{layer}-skill.md`` files.
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
        layer_content = _read_text(core_dir / f"{layer}-skill.md")
        if layer_content:
            parts.append(layer_content)

    prefix = "\n\n".join(parts) if parts else None
    if prefix:
        body = f"{prefix}\n\n{body}"

    return f"{frontmatter}\n\n{body}"


def _read_graphite_routing() -> str | None:
    """Read the conditional `## Graphite Routing` block for deviate-pr."""
    try:
        path = Path(
            importlib.resources.files("deviate.prompts").joinpath(
                "skills/deviate-pr/graphite_routing.md"
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


def install_skill(
    name: str,
    target_dir: Path,
    skills_root: Path | None = None,
    workdir: Path | None = None,
) -> bool:
    skill_path = resolve_skill(name, skills_root)
    target_path = target_dir / name / "SKILL.md"

    raw = _read_text(skill_path)
    if raw is None:
        return False

    core_dir = _resolve_core_dir()
    if core_dir is None:
        return False

    composed = compose_skill_body(raw, core_dir)
    if composed is None:
        return False

    if name == "deviate-pr" and workdir is not None and _graphite_enabled(workdir):
        routing = _read_graphite_routing()
        if routing:
            composed = f"{composed}\n\n{routing.rstrip()}"

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
