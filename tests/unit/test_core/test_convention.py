"""Tests for deviate.core.convention — commit message emoji detection and formatting."""

from __future__ import annotations

import subprocess
from pathlib import Path


from tests.conftest import _git_env
from deviate.core.convention import (
    TYPE_EMOJI_MAP,
    _extract_type,
    _file_has_emojis,
    commit_scope,
    detect_uses_emojis,
    format_commit_message,
)


class TestCommitScope:
    def test_removes_legacy_prefix_from_numbered_issue(self) -> None:
        assert commit_scope("ISS-001-001") == "001-001"

    def test_removes_legacy_prefix_from_adhoc_issue(self) -> None:
        assert commit_scope("ISS-ADH-001") == "ADH-001"

    def test_keeps_canonical_scopes(self) -> None:
        assert commit_scope("001-001") == "001-001"
        assert commit_scope("ADH-001") == "ADH-001"

    def test_keeps_task_and_subsystem_scopes(self) -> None:
        assert commit_scope("TSK-001-01") == "TSK-001-01"
        assert commit_scope("review") == "review"

    def test_format_commit_message_normalizes_legacy_scope(
        self, tmp_git_repo: Path
    ) -> None:
        result = format_commit_message("chore(ISS-001-001): claim issue", tmp_git_repo)
        assert result == "chore(001-001): claim issue"

    def test_format_commit_message_normalizes_legacy_adhoc_scope(
        self, tmp_git_repo: Path
    ) -> None:
        result = format_commit_message("docs(ISS-ADH-001): add issue", tmp_git_repo)
        assert result == "docs(ADH-001): add issue"


# ---------------------------------------------------------------------------
# _file_has_emojis
# ---------------------------------------------------------------------------


class TestFileHasEmojis:
    def test_detects_emoji_in_text(self) -> None:
        assert _file_has_emojis("✨ feat: add feature") is True

    def test_detects_gitmoji_prefix(self) -> None:
        assert _file_has_emojis("🐛 fix: resolve crash") is True

    def test_plain_text_returns_false(self) -> None:
        assert _file_has_emojis("feat: add feature") is False

    def test_empty_string_returns_false(self) -> None:
        assert _file_has_emojis("") is False


# ---------------------------------------------------------------------------
# _extract_type
# ---------------------------------------------------------------------------


class TestExtractType:
    def test_extracts_feat(self) -> None:
        assert _extract_type("feat(scope): description") == "feat"

    def test_extracts_fix(self) -> None:
        assert _extract_type("fix: hotfix") == "fix"

    def test_extracts_test(self) -> None:
        assert _extract_type("test(T001): add test") == "test"

    def test_plain_text_returns_none(self) -> None:
        assert _extract_type("no type here") == "no"

    def test_empty_string_returns_none(self) -> None:
        assert _extract_type("") is None


# ---------------------------------------------------------------------------
# detect_uses_emojis
# ---------------------------------------------------------------------------


class TestDetectUsesEmojis:
    def test_returns_false_for_plain_repo(self, tmp_git_repo: Path) -> None:
        """A freshly initialized repo with no emoji commits returns False."""
        assert detect_uses_emojis(tmp_git_repo) is False

    def test_returns_true_when_contributing_md_has_emojis(
        self, tmp_git_repo: Path
    ) -> None:
        """A CONTRIBUTING.md containing emoji characters triggers detection."""
        contributing = tmp_git_repo / "CONTRIBUTING.md"
        contributing.write_text(
            "# Contributing\n\nUse ✨ for features and 🐛 for fixes.\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "CONTRIBUTING.md"], cwd=tmp_git_repo, env=_git_env()
        )
        subprocess.run(
            ["git", "commit", "-m", "docs: add contributing guide"],
            cwd=tmp_git_repo,
            env=_git_env(),
        )
        assert detect_uses_emojis(tmp_git_repo) is True

    def test_returns_false_when_only_git_history_has_emojis(
        self, tmp_git_repo: Path
    ) -> None:
        """Git history with emoji commits must NOT trigger detection.

        Regression pin: the prior implementation fell back to
        ``_git_log_has_emojis`` when ``CONTRIBUTING.md`` was silent on
        emoji, which made the convention self-perpetuating — any single
        accidental emoji commit locked in emoji forever, regardless of
        what the project actually documented. ``detect_uses_emojis`` is
        now strictly opt-in via the convention file; history is never
        consulted.
        """
        file_path = tmp_git_repo / "file.txt"
        file_path.write_text("content", encoding="utf-8")
        subprocess.run(["git", "add", "file.txt"], cwd=tmp_git_repo, env=_git_env())
        subprocess.run(
            ["git", "commit", "-m", "\u2728 feat: initial feature"],
            cwd=tmp_git_repo,
            env=_git_env(),
        )
        assert detect_uses_emojis(tmp_git_repo) is False

    def test_returns_false_when_contributing_md_has_no_emojis(
        self, tmp_git_repo: Path
    ) -> None:
        """A CONTRIBUTING.md without emoji characters means no convention.

        Without an emoji convention declared in CONTRIBUTING.md (or
        .commit-convention.md), ``detect_uses_emojis`` returns False
        regardless of what is in git history.
        """
        contributing = tmp_git_repo / "CONTRIBUTING.md"
        contributing.write_text(
            "# Contributing\n\nUse conventional commits.\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "CONTRIBUTING.md"], cwd=tmp_git_repo, env=_git_env()
        )
        subprocess.run(
            ["git", "commit", "-m", "docs: add contributing guide"],
            cwd=tmp_git_repo,
            env=_git_env(),
        )
        assert detect_uses_emojis(tmp_git_repo) is False


# ---------------------------------------------------------------------------
# format_commit_message
# ---------------------------------------------------------------------------


class TestFormatCommitMessage:
    @staticmethod
    def _seed_emoji_convention(tmp_git_repo: Path) -> None:
        """Write a CONTRIBUTING.md that declares an emoji convention.

        Replaces the prior pattern of seeding git history with a single
        emoji commit. The convention file is now the sole source of
        truth for ``detect_uses_emojis``; git history is not consulted.
        """
        contributing = tmp_git_repo / "CONTRIBUTING.md"
        contributing.write_text(
            "# Contributing\n\n"
            "Use gitmoji: \u2728 for features, \U0001f41b for fixes.\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "CONTRIBUTING.md"],
            cwd=tmp_git_repo,
            env=_git_env(),
        )
        subprocess.run(
            ["git", "commit", "-m", "docs: add contributing guide"],
            cwd=tmp_git_repo,
            env=_git_env(),
        )

    def test_prepends_emoji_when_repo_uses_emojis(self, tmp_git_repo: Path) -> None:
        """When CONTRIBUTING.md declares emoji, the correct emoji is prepended."""
        self._seed_emoji_convention(tmp_git_repo)

        result = format_commit_message("feat(T001): add feature", tmp_git_repo)
        assert result == "\u2728 feat(T001): add feature"

    def test_returns_plain_message_when_repo_has_no_emojis(
        self, tmp_git_repo: Path
    ) -> None:
        """Without an emoji convention declared, the message is unchanged."""
        result = format_commit_message("feat(T001): add feature", tmp_git_repo)
        assert result == "feat(T001): add feature"

    def test_maps_all_standard_types(self, tmp_git_repo: Path) -> None:
        """Every type in TYPE_EMOJI_MAP is correctly prepended when emoji convention is set."""
        self._seed_emoji_convention(tmp_git_repo)

        for commit_type, emoji in TYPE_EMOJI_MAP.items():
            msg = f"{commit_type}: some work"
            result = format_commit_message(msg, tmp_git_repo)
            assert result == f"{emoji} {msg}", f"Failed for type '{commit_type}'"

    def test_unknown_type_returns_unchanged(self, tmp_git_repo: Path) -> None:
        """A message with an unknown type is returned as-is even with emoji detection."""
        self._seed_emoji_convention(tmp_git_repo)

        result = format_commit_message("custom: some work", tmp_git_repo)
        assert result == "custom: some work"

    def test_red_phase_test_uses_siren_emoji(self, tmp_git_repo: Path) -> None:
        """`test:` commit during RED phase uses \U0001f6a8 to flag the failing test."""
        self._seed_emoji_convention(tmp_git_repo)

        result = format_commit_message(
            "test(T001): RED phase - failing test", tmp_git_repo, phase="red"
        )
        assert result == "\U0001f6a8 test(T001): RED phase - failing test"

    def test_green_phase_test_uses_check_emoji(self, tmp_git_repo: Path) -> None:
        """`test:` commit during GREEN phase uses \u2705 to flag the passing test."""
        self._seed_emoji_convention(tmp_git_repo)

        result = format_commit_message(
            "test(T001): GREEN phase - implementation", tmp_git_repo, phase="green"
        )
        assert result == "\u2705 test(T001): GREEN phase - implementation"

    def test_test_type_without_phase_keeps_default_check_emoji(
        self, tmp_git_repo: Path
    ) -> None:
        """`test:` commit without phase falls back to TYPE_EMOJI_MAP default (\u2705)."""
        self._seed_emoji_convention(tmp_git_repo)

        result = format_commit_message("test(T001): add coverage", tmp_git_repo)
        assert result == "\u2705 test(T001): add coverage"

    def test_non_test_type_ignores_phase(self, tmp_git_repo: Path) -> None:
        """The phase parameter only affects `test:` commits; other types unchanged."""
        self._seed_emoji_convention(tmp_git_repo)

        result = format_commit_message(
            "feat(T001): implementation", tmp_git_repo, phase="red"
        )
        assert result == "\u2728 feat(T001): implementation"

    def test_unknown_phase_falls_back_to_default(self, tmp_git_repo: Path) -> None:
        """An unknown phase value (e.g. 'refactor') falls back to TYPE_EMOJI_MAP."""
        self._seed_emoji_convention(tmp_git_repo)

        result = format_commit_message(
            "test(T001): some work", tmp_git_repo, phase="refactor"
        )
        assert result == "✅ test(T001): some work"
