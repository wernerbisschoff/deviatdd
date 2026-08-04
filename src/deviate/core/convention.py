"""Commit convention detection.

Detects whether a repository uses emoji-prefixed conventional commits by
checking ``CONTRIBUTING.md`` / ``.commit-convention.md`` for emoji
content, and provides a formatter that prepends the correct emoji to
commit messages. The convention file is the source of truth; if it is
silent on emoji (or absent), ``detect_uses_emojis`` returns ``False``
and ``format_commit_message`` is a no-op. Git history is intentionally
NOT consulted: a self-perpetuating "look at the last emoji commit and
keep emitting emoji" loop is a bug, not a feature.
"""

from __future__ import annotations

import re
from pathlib import Path


# Default type → emoji mapping (gitmoji conventional-commit standard).
TYPE_EMOJI_MAP: dict[str, str] = {
    "feat": "✨",
    "fix": "🐛",
    "docs": "📚",
    "style": "🎨",
    "refactor": "♻️",
    "perf": "🚀",
    "test": "✅",
    "build": "📦",
    "ci": "👷",
    "chore": "🔧",
    "revert": "⏪",
}

# Per-phase emoji override for `test:` commits during the red-green TDD cycle.
# RED commits a failing test (🚨); GREEN commits a passing test (✅). All other
# types keep their `TYPE_EMOJI_MAP` entry. An unknown phase falls back to the
# default for the type.
PHASE_TEST_EMOJI: dict[str, str] = {
    "red": "\U0001f6a8",  # 🚨 — failing test
    "green": "\u2705",  # ✅ — passing test
}

# Conventional-commit type pattern at the start of a message.
_TYPE_RE = re.compile(r"^(\w+)")

_SCOPE_RE = re.compile(r"^(?P<prefix>\w+)\((?P<scope>[^)]+)\):")


def _read_convention_file(repo: Path) -> str | None:
    """Return the content of a project commit-convention file, or None."""
    for name in ("CONTRIBUTING.md", ".commit-convention.md"):
        path = repo / name
        if path.exists():
            return path.read_text(encoding="utf-8")
    return None


# Emoji Unicode ranges (covers the standard gitmoji set and common emoji).
_EMOJI_RANGE_RE = re.compile(
    "["
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f300-\U0001f5ff"  # symbols & pictographs
    "\U0001f680-\U0001f6ff"  # transport & map symbols
    "\U0001f1e0-\U0001f1ff"  # flags
    "\U0001f900-\U0001f9ff"  # supplemental symbols
    "\U0001fa00-\U0001fa6f"  # chess symbols
    "\U0001fa70-\U0001faff"  # symbols extended-A
    "\U00002702-\U000027b0"  # dingbats
    "\U00002600-\U000026ff"  # misc symbols
    "]+",
    re.UNICODE,
)


def _file_has_emojis(content: str) -> bool:
    """Check whether a text contains Unicode emoji characters."""
    return bool(_EMOJI_RANGE_RE.search(content))


def detect_uses_emojis(repo: Path) -> bool:
    """Determine whether a repository uses emoji-prefixed commits.

    Returns ``True`` only when ``CONTRIBUTING.md`` or
    ``.commit-convention.md`` exists in the repository root AND contains
    at least one Unicode emoji character. The file is the source of
    truth; if it is silent on the matter (or absent), the repository is
    treated as not using emoji prefixes. Git history is intentionally
    NOT consulted — a self-perpetuating emoji convention that drifts
    away from what the project actually documents is a bug.
    """
    convention_content = _read_convention_file(repo)
    if convention_content is None:
        return False
    return _file_has_emojis(convention_content)


def _extract_type(message: str) -> str | None:
    """Extract the conventional-commit type from a message string."""
    m = _TYPE_RE.match(message)
    return m.group(1) if m else None


def commit_scope(identifier: str) -> str:
    """Return the canonical commit scope for an issue or task identifier."""
    if identifier.startswith("ISS-"):
        return identifier[4:]
    return identifier


def _normalize_commit_scope(message: str) -> str:
    """Remove the legacy ``ISS-`` prefix from a conventional-commit scope."""
    match = _SCOPE_RE.match(message)
    if match is None:
        return message
    scope = commit_scope(match.group("scope"))
    if scope == match.group("scope"):
        return message
    return f"{match.group('prefix')}({scope}):{message[match.end() :]}"


def format_commit_message(message: str, repo: Path, phase: str | None = None) -> str:
    """Prepend the appropriate emoji to a conventional-commit message.

    If the repository declares an emoji convention in
    ``CONTRIBUTING.md`` / ``.commit-convention.md`` and the message
    starts with a known type, the corresponding emoji is prepended.

    The optional ``phase`` argument selects a per-phase emoji override for
    ``test:`` commits during the red-green TDD cycle:

    - ``phase="red"``   → 🚨 (failing test, RED phase commit)
    - ``phase="green"`` → ✅ (passing test, GREEN phase commit)

    For any other commit type the ``phase`` argument is ignored, and the
    emoji falls back to ``TYPE_EMOJI_MAP``. An unknown ``phase`` value
    also falls back to the type's default emoji.
    """
    message = _normalize_commit_scope(message)
    if not detect_uses_emojis(repo):
        return message

    commit_type = _extract_type(message)
    if commit_type is None:
        return message

    if commit_type == "test" and phase in PHASE_TEST_EMOJI:
        emoji = PHASE_TEST_EMOJI[phase]
    elif commit_type in TYPE_EMOJI_MAP:
        emoji = TYPE_EMOJI_MAP[commit_type]
    else:
        return message

    return f"{emoji} {message}"
