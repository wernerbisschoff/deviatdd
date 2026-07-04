"""Commit convention detection.

Detects whether a repository uses emoji-prefixed conventional commits
(by checking CONTRIBUTING.md / .commit-convention.md for emoji content,
then falling back to sampling recent git history) and provides a
formatter that prepends the correct emoji to commit messages.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from deviate.core._shared import git_env as _git_env

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


def _git_log_has_emojis(repo: Path, n: int = 10) -> bool:
    """Sample the last *n* commit subjects for emoji presence."""
    try:
        result = subprocess.run(
            ["git", "log", f"-{n}", "--pretty=format:%s"],
            cwd=repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return False
        return _file_has_emojis(result.stdout)
    except (subprocess.TimeoutExpired, OSError):
        return False


def detect_uses_emojis(repo: Path) -> bool:
    """Determine whether a repository uses emoji-prefixed commits.

    Detection order:
    1. CONTRIBUTING.md / .commit-convention.md — if the file contains
       Unicode emoji characters, the project uses them.
    2. Git history — sample the last 10 commit subjects.
    3. Default: False (no emoji prefix).
    """
    convention_content = _read_convention_file(repo)
    if convention_content is not None and _file_has_emojis(convention_content):
        return True
    return _git_log_has_emojis(repo)


def _extract_type(message: str) -> str | None:
    """Extract the conventional-commit type from a message string."""
    m = _TYPE_RE.match(message)
    return m.group(1) if m else None


def format_commit_message(message: str, repo: Path, phase: str | None = None) -> str:
    """Prepend the appropriate emoji to a conventional-commit message.

    If the repository uses emoji prefixes (detected via CONTRIBUTING.md
    or git history) and the message starts with a known type, the
    corresponding emoji is prepended.  Otherwise the message is returned
    unchanged.

    The optional ``phase`` argument selects a per-phase emoji override for
    ``test:`` commits during the red-green TDD cycle:

    - ``phase="red"``   → 🚨 (failing test, RED phase commit)
    - ``phase="green"`` → ✅ (passing test, GREEN phase commit)

    For any other commit type the ``phase`` argument is ignored, and the
    emoji falls back to ``TYPE_EMOJI_MAP``. An unknown ``phase`` value
    also falls back to the type's default emoji.
    """
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
