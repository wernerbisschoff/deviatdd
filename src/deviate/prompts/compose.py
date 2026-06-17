"""Preview the composed content of skill SKILL.md files (dry-run only).

Composition is performed by ``install_skill()`` in ``deviate.core.skills``
at install time. This script is a dry-run preview tool only — it never
modifies files in-place.
"""

from __future__ import annotations

from pathlib import Path

from deviate.core.skills import _read_text, compose_skill_body

_HERE = Path(__file__).resolve().parent
_CORE_DIR = _HERE / "core"
_SKILLS_DIR = _HERE / "skills"


def preview_skill(skill_path: Path) -> bool:
    """Print the composed size of a skill file (preview only)."""
    raw = _read_text(skill_path)
    if raw is None:
        return False

    composed = compose_skill_body(raw, _CORE_DIR)
    if composed is None:
        return False

    old_size = len(raw)
    new_size = len(composed)
    print(
        f"  [DRY] {skill_path.parent.name}: {old_size} → {new_size} chars (+{new_size - old_size})"
    )
    return True


def main() -> None:
    count = 0
    for entry in sorted(_SKILLS_DIR.iterdir()):
        skill_file = entry / "SKILL.md"
        if not skill_file.is_file():
            continue
        changed = preview_skill(skill_file)
        if changed:
            count += 1

    print(f"\n{count} skill(s) — dry-run only, no files modified")


if __name__ == "__main__":
    main()
