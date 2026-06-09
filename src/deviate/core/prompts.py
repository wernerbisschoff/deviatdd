from __future__ import annotations

import importlib.resources
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def _resolve_package_root() -> Path:
    return Path(importlib.resources.files("deviate.prompts"))  # type: ignore[arg-type]


def _resolve_file(name: str, override_dir: Path, fallback_dir: Path) -> str:
    override_path = override_dir / name
    fallback_path = fallback_dir / name

    if override_path.is_file():
        try:
            return override_path.read_text()
        except OSError:
            logger.warning("Unreadable override file: %s", override_path)

    if fallback_path.is_file():
        return fallback_path.read_text()

    raise FileNotFoundError(f"Prompt not found: {name}")


def resolve_prompt(
    name: str,
    overrides_root: Path | None = None,
    package_root: Path | None = None,
) -> str:
    if overrides_root is None:
        overrides_root = Path.cwd() / ".deviate" / "prompts"
    if package_root is None:
        package_root = _resolve_package_root()
    return _resolve_file(name, override_dir=overrides_root, fallback_dir=package_root)


def resolve_command(
    name: str,
    overrides_root: Path | None = None,
    package_root: Path | None = None,
) -> str:
    if overrides_root is None:
        overrides_root = Path.cwd() / ".deviate" / "prompts"
    if package_root is None:
        package_root = _resolve_package_root()
    return _resolve_file(
        f"commands/{name}.md",
        override_dir=overrides_root,
        fallback_dir=package_root,
    )


def interpolate(template: str, variables: dict[str, str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        return variables.get(match.group(1), match.group(0))

    return re.sub(r"\$\{(\w+)\}", _replace, template)


def list_overrides(overrides_root: Path, package_root: Path) -> list[str]:
    if not overrides_root.is_dir():
        return []
    result: list[str] = []
    for path in sorted(overrides_root.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(overrides_root))
        package_path = package_root / rel
        if not package_path.is_file() or path.read_text() != package_path.read_text():
            result.append(rel)
    return result


def list_defaults(overrides_root: Path, package_root: Path) -> list[str]:
    overridden = set(list_overrides(overrides_root, package_root))
    if not package_root.is_dir():
        return []
    result: list[str] = []
    for path in sorted(package_root.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(package_root))
        if rel not in overridden:
            result.append(rel)
    return result
