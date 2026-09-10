from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.core.explore_routing import ATTACH_EXISTING_EPIC, ADHOC
from deviate.state.config import SessionState

from tests.explore_artifact import render_explore_md

runner = CliRunner()


class TestExploreCommand:
    def test_explore_help(self):
        result = runner.invoke(cli, ["explore", "--help"])
        assert result.exit_code == 0, result.output
        assert "explore" in result.output.lower()

    def test_explore_pre_transitions_from_idle(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")
            Path("specs").mkdir(parents=True)
            (Path("specs") / "constitution.md").write_text("# Constitution\n")

            result = runner.invoke(
                cli, ["explore", "pre", "test problem", "--slug", "test-slug"]
            )
            assert result.exit_code == 0, result.output

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "EXPLORE"
            assert (Path("specs") / "explore").is_dir()

    def test_explore_pre_accepts_greenfield_and_transitions_from_any_phase(
        self, tmp_path: Path
    ) -> None:
        """Greenfield explore (no ``specs/constitution.md``) proceeds.

        explore pre no longer halts on a missing constitution — it derives
        ``is_greenfield=true`` from constitution absence. The orchestrator
        does NOT enforce phase transitions via ``_load_and_transition``;
        a non-IDLE starting phase is silently overwritten (see
        ``SessionState.transition_to``). The ``is_greenfield`` flag is the
        greenfield-detection signal downstream phases rely on.
        """
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="RESEARCH")
            session.save(dot_dir / "session.json")
            # No constitution file — greenfield.

            result = runner.invoke(
                cli, ["explore", "pre", "test", "--slug", "test-slug"]
            )
            assert result.exit_code == 0, result.output
            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "EXPLORE"

    def test_explore_pre_missing_session_file_defaults_idle(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            assert not (dot_dir / "session.json").exists()
            Path("specs").mkdir(parents=True)
            (Path("specs") / "constitution.md").write_text("# Constitution\n")

            result = runner.invoke(
                cli, ["explore", "pre", "test", "--slug", "test-slug"]
            )
            assert result.exit_code == 0, result.output

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "EXPLORE"

    def test_explore_pre_missing_dotdeviate_dir_error(self, tmp_path: Path):
        with chdir(tmp_path):
            assert not Path(".deviate").exists()

            result = runner.invoke(
                cli, ["explore", "pre", "test", "--slug", "test-slug"]
            )
            assert result.exit_code != 0
            assert "EXPLORE_HALTED" in result.output


class TestExplorePreFileSlug:
    def test_explore_pre_derives_slug_from_file_contents(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")
            Path("specs").mkdir(parents=True)
            (Path("specs") / "constitution.md").write_text("# Constitution\n")
            Path("next-release.md").write_text(
                "# Offline Context Docs\n\nSearch local docs offline.\n"
            )

            result = runner.invoke(cli, ["explore", "pre", "next-release.md"])

            assert result.exit_code == 0, result.output
            assert "specs/explore/offline-context-docs.md" in result.output
            assert "next-release" not in result.output


def _seed_explore_session(root: Path, *, slug: str, body: str) -> None:
    dot_dir = root / ".deviate"
    dot_dir.mkdir(parents=True, exist_ok=True)
    SessionState(current_phase="EXPLORE").save(dot_dir / "session.json")
    explore_dir = root / "specs" / "explore"
    explore_dir.mkdir(parents=True, exist_ok=True)
    (explore_dir / f"{slug}.md").write_text(body, encoding="utf-8")
    (root / "specs" / "constitution.md").write_text("# Constitution\n")


class TestExplorePostAttachRouting:
    def test_post_persists_attach_next_action(self, tmp_git_repo: Path) -> None:
        slug = "follow-on-config"
        body = render_explore_md(
            next_action="attach_existing_epic `006-setup-interactive-config`",
            attach_epic="006-setup-interactive-config",
            candidates=(
                "| Path | Title | Evidence |\n"
                "| :--- | :--- | :--- |\n"
                "| specs/006-setup-interactive-config/ | setup | "
                '"interactive config" |\n'
            ),
        )
        _seed_explore_session(tmp_git_repo, slug=slug, body=body)

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["explore", "post", "--slug", slug])

        assert result.exit_code == 0, result.output
        assert "ATTACH_EXISTING_EPIC" in result.output
        assert "006-setup-interactive-config" in result.output
        loaded = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
        assert loaded.explore_next_action == ATTACH_EXISTING_EPIC
        assert loaded.attach_epic_slug == "006-setup-interactive-config"
        assert loaded.explore_hitl_pending is False

    def test_post_persists_adhoc_next_action(self, tmp_git_repo: Path) -> None:
        slug = "typo-fix"
        _seed_explore_session(
            tmp_git_repo,
            slug=slug,
            body=render_explore_md(next_action="adhoc"),
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["explore", "post", "--slug", slug])

        assert result.exit_code == 0, result.output
        loaded = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
        assert loaded.explore_next_action == ADHOC
        assert "adhoc pre" in result.output

    def test_post_pending_hitl_does_not_allocate(self, tmp_git_repo: Path) -> None:
        slug = "needs-hitl"
        _seed_explore_session(
            tmp_git_repo,
            slug=slug,
            body=render_explore_md(
                next_action="attach_existing_epic 006-foo",
                hitl_override="pending",
            ),
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(cli, ["explore", "post", "--slug", slug])

        assert result.exit_code == 0, result.output
        assert "HITL" in result.output
        loaded = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
        assert loaded.explore_hitl_pending is True
