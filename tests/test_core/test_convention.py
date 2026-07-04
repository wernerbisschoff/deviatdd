"""Tests for deviate.core.convention — commit message emoji detection and formatting."""

from __future__ import annotations

import subprocess
from pathlib import Path


from tests.conftest import _git_env
from deviate.core.convention import (
    TYPE_EMOJI_MAP,
    _extract_type,
    _file_has_emojis,
    detect_uses_emojis,
    format_commit_message,
)


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

    def test_returns_true_when_git_history_has_emojis(self, tmp_git_repo: Path) -> None:
        """Recent commit subjects with emoji prefixes trigger detection."""
        file_path = tmp_git_repo / "file.txt"
        file_path.write_text("content", encoding="utf-8")
        subprocess.run(["git", "add", "file.txt"], cwd=tmp_git_repo, env=_git_env())
        subprocess.run(
            ["git", "commit", "-m", "✨ feat: initial feature"],
            cwd=tmp_git_repo,
            env=_git_env(),
        )
        assert detect_uses_emojis(tmp_git_repo) is True

    def test_returns_false_when_contributing_md_has_no_emojis(
        self, tmp_git_repo: Path
    ) -> None:
        """A CONTRIBUTING.md without emoji characters falls through to history."""
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
    def test_prepends_emoji_when_repo_uses_emojis(self, tmp_git_repo: Path) -> None:
        """When the repo uses emoji commits, the correct emoji is prepended."""
        # Seed git history with an emoji commit
        file_path = tmp_git_repo / "file.txt"
        file_path.write_text("content", encoding="utf-8")
        subprocess.run(["git", "add", "file.txt"], cwd=tmp_git_repo, env=_git_env())
        subprocess.run(
            ["git", "commit", "-m", "✨ feat: seed"],
            cwd=tmp_git_repo,
            env=_git_env(),
        )

        result = format_commit_message("feat(T001): add feature", tmp_git_repo)
        assert result == "✨ feat(T001): add feature"

    def test_returns_plain_message_when_repo_has_no_emojis(
        self, tmp_git_repo: Path
    ) -> None:
        """When the repo does not use emoji commits, message is unchanged."""
        result = format_commit_message("feat(T001): add feature", tmp_git_repo)
        assert result == "feat(T001): add feature"

    def test_maps_all_standard_types(self, tmp_git_repo: Path) -> None:
        """Every type in TYPE_EMOJI_MAP is correctly prepended when repo uses emojis."""
        # Seed with emoji commit
        file_path = tmp_git_repo / "file.txt"
        file_path.write_text("content", encoding="utf-8")
        subprocess.run(["git", "add", "file.txt"], cwd=tmp_git_repo, env=_git_env())
        subprocess.run(
            ["git", "commit", "-m", "✨ feat: seed"],
            cwd=tmp_git_repo,
            env=_git_env(),
        )

        for commit_type, emoji in TYPE_EMOJI_MAP.items():
            msg = f"{commit_type}: some work"
            result = format_commit_message(msg, tmp_git_repo)
            assert result == f"{emoji} {msg}", f"Failed for type '{commit_type}'"

    def test_unknown_type_returns_unchanged(self, tmp_git_repo: Path) -> None:
        """A message with an unknown type is returned as-is even with emoji detection."""
        file_path = tmp_git_repo / "file.txt"
        file_path.write_text("content", encoding="utf-8")
        subprocess.run(["git", "add", "file.txt"], cwd=tmp_git_repo, env=_git_env())
        subprocess.run(
            ["git", "commit", "-m", "✨ feat: seed"],
            cwd=tmp_git_repo,
            env=_git_env(),
        )

        result = format_commit_message("custom: some work", tmp_git_repo)
        assert result == "custom: some work"

    def test_red_phase_test_uses_siren_emoji(self, tmp_git_repo: Path) -> None:
        """`test:` commit during RED phase uses 🚨 to flag the failing test."""
        file_path = tmp_git_repo / "file.txt"
        file_path.write_text("content", encoding="utf-8")
        subprocess.run(["git", "add", "file.txt"], cwd=tmp_git_repo, env=_git_env())
        subprocess.run(
            ["git", "commit", "-m", "✨ feat: seed"],
            cwd=tmp_git_repo,
            env=_git_env(),
        )

        result = format_commit_message(
            "test(T001): RED phase - failing test", tmp_git_repo, phase="red"
        )
        assert result == "🚨 test(T001): RED phase - failing test"

    def test_green_phase_test_uses_check_emoji(self, tmp_git_repo: Path) -> None:
        """`test:` commit during GREEN phase uses ✅ to flag the passing test."""
        file_path = tmp_git_repo / "file.txt"
        file_path.write_text("content", encoding="utf-8")
        subprocess.run(["git", "add", "file.txt"], cwd=tmp_git_repo, env=_git_env())
        subprocess.run(
            ["git", "commit", "-m", "✨ feat: seed"],
            cwd=tmp_git_repo,
            env=_git_env(),
        )

        result = format_commit_message(
            "test(T001): GREEN phase - implementation", tmp_git_repo, phase="green"
        )
        assert result == "✅ test(T001): GREEN phase - implementation"

    def test_test_type_without_phase_keeps_default_check_emoji(
        self, tmp_git_repo: Path
    ) -> None:
        """`test:` commit without phase falls back to TYPE_EMOJI_MAP default (✅)."""
        file_path = tmp_git_repo / "file.txt"
        file_path.write_text("content", encoding="utf-8")
        subprocess.run(["git", "add", "file.txt"], cwd=tmp_git_repo, env=_git_env())
        subprocess.run(
            ["git", "commit", "-m", "✨ feat: seed"],
            cwd=tmp_git_repo,
            env=_git_env(),
        )

        result = format_commit_message("test(T001): add coverage", tmp_git_repo)
        assert result == "✅ test(T001): add coverage"

    def test_non_test_type_ignores_phase(self, tmp_git_repo: Path) -> None:
        """The phase parameter only affects `test:` commits; other types unchanged."""
        file_path = tmp_git_repo / "file.txt"
        file_path.write_text("content", encoding="utf-8")
        subprocess.run(["git", "add", "file.txt"], cwd=tmp_git_repo, env=_git_env())
        subprocess.run(
            ["git", "commit", "-m", "✨ feat: seed"],
            cwd=tmp_git_repo,
            env=_git_env(),
        )

        result = format_commit_message(
            "feat(T001): implementation", tmp_git_repo, phase="red"
        )
        assert result == "✨ feat(T001): implementation"

    def test_unknown_phase_falls_back_to_default(self, tmp_git_repo: Path) -> None:
        """An unknown phase value (e.g. 'refactor') falls back to TYPE_EMOJI_MAP."""
        file_path = tmp_git_repo / "file.txt"
        file_path.write_text("content", encoding="utf-8")
        subprocess.run(["git", "add", "file.txt"], cwd=tmp_git_repo, env=_git_env())
        subprocess.run(
            ["git", "commit", "-m", "✨ feat: seed"],
            cwd=tmp_git_repo,
            env=_git_env(),
        )

        result = format_commit_message(
            "test(T001): some work", tmp_git_repo, phase="refactor"
        )
        assert result == "✅ test(T001): some work"
