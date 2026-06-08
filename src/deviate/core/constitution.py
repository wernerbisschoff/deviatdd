from __future__ import annotations

from pathlib import Path


def resolve_constitution(repo_root: Path) -> Path:
    path = repo_root / "specs" / "constitution.md"
    if not path.exists():
        raise FileNotFoundError(f"constitution.md not found at {path}")
    return path


def validate_constitution(path: Path) -> bool:
    if not path.exists():
        return False
    content = path.read_text()
    return len(content.strip()) > 0


def extract_commands(path: Path) -> dict[str, str]:
    content = path.read_text()
    commands: dict[str, str] = {}
    for line in content.splitlines():
        stripped = line.strip()
        if "TEST_COMMAND" in stripped and ":" in stripped:
            value = stripped.split(":", 1)[1].strip().strip("`").strip()
            if value:
                commands["test_command"] = value
        elif "LINT_COMMAND" in stripped and ":" in stripped:
            value = stripped.split(":", 1)[1].strip().strip("`").strip()
            if value:
                commands["lint_command"] = value
    return commands
