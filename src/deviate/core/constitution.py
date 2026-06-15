from __future__ import annotations

import re
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

_PLACEHOLDER_PATTERN = re.compile(r"\$\{(\w+)\}")


@dataclass
class PlaceholderAuditResult:
    all_present: bool
    variables: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def validate_placeholders(seed_path: Path) -> PlaceholderAuditResult:
    content = seed_path.read_text()
    found = set(_PLACEHOLDER_PATTERN.findall(content))
    variables = sorted(found & _REQUIRED_PLACEHOLDERS)
    missing = sorted(_REQUIRED_PLACEHOLDERS - found)
    return PlaceholderAuditResult(
        all_present=len(missing) == 0,
        variables=variables,
        missing=missing,
    )


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


_COMMAND_KEYS: dict[str, str] = {
    "TEST_COMMAND": "test_command",
    "LINT_COMMAND": "lint_command",
    "TYPE_CHECK_COMMAND": "type_check_command",
}


def _extract_value(line: str) -> str | None:
    _, _, tail = line.partition(":")
    value = tail.strip().strip("`").strip()
    return value or None


def validate_sections(path: Path, sections: list[str]) -> list[str]:
    headings = set(re.findall(r"^(#{1,6}\s+.+)$", path.read_text(), re.MULTILINE))
    return [s for s in sections if s not in headings]


def extract_commands(path: Path) -> dict[str, str]:
    content = path.read_text()
    commands: dict[str, str] = {}
    for line in content.splitlines():
        stripped = line.strip()
        if ":" not in stripped:
            continue
        for marker, key in _COMMAND_KEYS.items():
            if marker in stripped:
                value = _extract_value(stripped)
                if value:
                    commands[key] = value
    return commands
