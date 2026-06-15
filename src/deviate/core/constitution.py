from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


_REQUIRED_PLACEHOLDERS: frozenset[str] = frozenset(
    {
        "PROJECT_NAME",
        "REPO_ROOT",
        "TARGET_BACKEND_FRAMEWORK",
        "TARGET_PACKAGE_MANAGER",
        "TARGET_TEST_RUNNER",
        "TARGET_COVERAGE_MINIMUM",
    }
)


@dataclass
class PlaceholderAuditResult:
    all_present: bool
    variables: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def validate_placeholders(seed_path: Path) -> PlaceholderAuditResult:
    raise NotImplementedError


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
        elif "TYPE_CHECK_COMMAND" in stripped and ":" in stripped:
            value = stripped.split(":", 1)[1].strip().strip("`").strip()
            if value:
                commands["type_check_command"] = value
    return commands
