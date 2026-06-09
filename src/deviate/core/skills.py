from __future__ import annotations

from pathlib import Path

from deviate.core.prompts import resolve_command


def install_command(
    name: str,
    target_dir: Path,
    repo_path: Path | None = None,
) -> bool:
    overrides_root: Path | None = None
    if repo_path is not None:
        overrides_root = repo_path / ".deviate" / "prompts"

    content = resolve_command(name, overrides_root=overrides_root)

    target_path = target_dir / "commands" / f"{name}.md"
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if target_path.exists() and target_path.read_text(encoding="utf-8") == content:
        return False

    target_path.write_text(content, encoding="utf-8")
    return True


def install_skill(
    name: str,
    target_dir: Path,
    repo_path: Path | None = None,
) -> bool:
    return install_command(name, target_dir, repo_path=repo_path)


def discover_commands(root: Path | None = None) -> list[str]:
    search_root = root or Path.cwd()
    for agent_dir in (".opencode", ".claude", ".factory"):
        commands_dir = search_root / agent_dir / "commands"
        if commands_dir.is_dir():
            return sorted(p.stem for p in commands_dir.glob("*.md"))
    return []


def discover_skills(root: Path | None = None) -> list[str]:
    return discover_commands(root=root)


def detect_agents(workdir: Path | None = None) -> list[str]:
    workdir = workdir or Path.cwd()
    agents: list[str] = []
    for name in ("claude", "opencode", "factory"):
        if (workdir / f".{name}").is_dir():
            agents.append(name)
    return sorted(agents)
