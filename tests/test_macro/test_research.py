from __future__ import annotations

import subprocess

from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState

from tests.conftest import _git_env

runner = CliRunner()


# Minimal design.md / data-model.md bodies that satisfy `validate_artifact` —
# all required section headers per `src/deviate/core/validation.py::ARTIFACT_VALIDATORS`,
# each carrying a one-line placeholder body. The bodies do not need to be
# meaningful for the explore-move commit boundary; they only need to pass the
# section validator so `deviate research post` reaches the stage_and_commit
# step where the bug lives.
_DESIGN_SECTIONS = [
    "Recommended Architecture",
    "Options Matrix",
    "Rejected Options",
    "Design Trade-Offs",
    "Contrarian Viewpoints",
    "Risk Register",
    "Constitutional Alignment Audit",
    "Pending HITL Decisions",
    "Source Registry",
    "Status Summary",
]
_DATA_MODEL_SECTIONS = [
    "Entity Definitions",
    "Relationship Graph",
    "Schema Tables",
    "State Transitions",
    "Data Flow",
    "Source Registry",
]


def _render_artifact(sections: list[str]) -> str:
    return "\n\n".join(f"## {name}\n\nplaceholder" for name in sections) + "\n"


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=_git_env(),
        capture_output=True,
        text=True,
        check=check,
    )


class TestResearchCommand:
    def test_research_help(self):
        result = runner.invoke(cli, ["research", "--help"])
        assert result.exit_code == 0, result.output
        assert "research" in result.output.lower()

    def test_research_pre_transitions_from_explore(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="EXPLORE")
            session.save(dot_dir / "session.json")

            explore_dir = Path("specs") / "explore"
            explore_dir.mkdir(parents=True)
            (explore_dir / "deviate-cli-python.md").write_text("# Explore results\n")
            (Path("specs") / "constitution.md").write_text("# Constitution\n")

            result = runner.invoke(
                cli, ["research", "pre", "--slug", "deviate-cli-python"]
            )
            assert result.exit_code == 0, result.output

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "RESEARCH"
            # Verify numbered epic bucket was created
            epic_dirs = [
                d for d in Path("specs").iterdir() if d.is_dir() and d.name != "explore"
            ]
            assert len(epic_dirs) >= 1

    def test_research_pre_rejects_if_not_explore(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="PRD")
            session.save(dot_dir / "session.json")

            result = runner.invoke(
                cli, ["research", "pre", "--slug", "001-deviate-cli-python"]
            )
            assert result.exit_code != 0
            assert "RESEARCH_HALTED" in result.output

    def test_research_pre_missing_explore_artifact(self, tmp_path: Path):
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="EXPLORE")
            session.save(dot_dir / "session.json")

            result = runner.invoke(cli, ["research", "pre", "--slug", "missing-slug"])
            assert result.exit_code != 0
            assert "RESEARCH_HALTED" in result.output
            assert "explore.md" in result.output


class TestResearchExploreMove:
    """Verify `deviate research pre` moves explore.md into the numbered
    epic directory and updates the contract field accordingly.
    """

    def test_research_pre_moves_explore_into_epic_dir(self, tmp_path: Path) -> None:
        import json

        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="EXPLORE")
            session.save(dot_dir / "session.json")

            explore_dir = Path("specs") / "explore"
            explore_dir.mkdir(parents=True)
            content = (
                "# Explore: my-feature\n\n## Problem Definition\n\n"
                "Factual context.\n## File Registry\n| Path | Type |\n"
            )
            source = explore_dir / "my-feature.md"
            source.write_text(content)
            (Path("specs") / "constitution.md").write_text("# Constitution\n")

            result = runner.invoke(cli, ["research", "pre", "--slug", "my-feature"])
            assert result.exit_code == 0, result.output

            # The source must no longer exist (clean cutover, no orphan).
            assert not source.exists(), (
                f"source explore.md still present at {source} after research pre"
            )

            # The numbered epic bucket was created.
            epic_dir = Path("specs") / "001-my-feature"
            assert epic_dir.is_dir(), f"expected epic dir at {epic_dir}"

            # explore.md now lives inside the epic dir, with byte-identical
            # content (no corruption from the move).
            moved = epic_dir / "explore.md"
            assert moved.exists(), f"expected explore.md at {moved}"
            assert moved.read_text(encoding="utf-8") == content

            # The contract payload points explore_md_path at the new location.
            start = result.output.index("{")
            end = result.output.rindex("}") + 1
            contract = json.loads(result.output[start:end])
            assert contract["phase"] == "RESEARCH"
            assert contract["explore_md_path"] == str(moved.resolve())
            assert contract["explore_path"] == str(moved)
            assert contract["feature_dir"] == str(epic_dir)

    def test_research_pre_halts_when_source_explore_missing(
        self, tmp_path: Path
    ) -> None:
        with chdir(tmp_path):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="EXPLORE")
            session.save(dot_dir / "session.json")

            (Path("specs") / "explore").mkdir(parents=True)
            (Path("specs") / "constitution.md").write_text("# Constitution\n")

            # No specs/explore/ghost.md exists; the command should halt
            # before allocating a numbered bucket.
            result = runner.invoke(cli, ["research", "pre", "--slug", "ghost"])
            assert result.exit_code != 0
            assert "RESEARCH_HALTED" in result.output
            assert "explore.md" in result.output
            assert not (Path("specs") / "001-ghost").exists()


class TestResearchPostCommitsExploreMove:
    """Verify ``deviate research post`` commits the ``specs/explore/<slug>.md``
    → ``specs/<epic>/explore.md`` move performed by ``deviate research pre``
    in the same atomic commit as ``design.md`` and ``data-model.md``.

    Regression for the bug where ``research_pre`` did ``shutil.move()``
    but ``research_post`` only staged design/data-model — leaving
    ``specs/explore/<slug>.md`` tracked-but-deleted and
    ``specs/<epic>/explore.md`` untracked. Spec invariant:
    "no orphan staging copy" (DeviaTDD-api.md § research pre).
    """

    def _seed_repo(self, tmp_git_repo: Path, slug: str) -> tuple[Path, str]:
        """Seed a committed explore.md + constitution and return
        ``(epic_slug, source_relative_path)``. The source must be committed
        to HEAD before ``research pre`` runs so the move actually changes
        git's index.
        """
        specs = tmp_git_repo / "specs"
        (specs / "explore").mkdir(parents=True)
        (specs / "constitution.md").write_text("# Constitution\n")
        source = specs / "explore" / f"{slug}.md"
        source.write_text(
            f"# Explore: {slug}\n\n## Problem Definition\n\nfactual\n",
            encoding="utf-8",
        )

        _git(tmp_git_repo, "add", ".")
        _git(tmp_git_repo, "commit", "-m", f"seed explore/{slug}")

        (tmp_git_repo / ".deviate").mkdir(exist_ok=True)
        SessionState(current_phase="EXPLORE").save(
            tmp_git_repo / ".deviate" / "session.json"
        )

        epic_slug = f"001-{slug}"
        return tmp_git_repo, epic_slug

    def test_research_post_stages_explore_move_atomically(
        self, tmp_git_repo: Path
    ) -> None:
        """End-to-end: research pre moves explore.md, then research post
        creates ONE commit containing the new explore.md (added), the old
        specs/explore/<slug>.md (deleted), design.md (added), and
        data-model.md (added). Working tree must be clean after.
        """
        slug = "explore-commit-boundary"
        repo, epic_slug = self._seed_repo(tmp_git_repo, slug)
        source_rel = f"specs/explore/{slug}.md"
        moved_rel = f"specs/{epic_slug}/explore.md"

        # research pre: moves the explore.md into the numbered epic dir.
        with chdir(repo):
            pre = runner.invoke(cli, ["research", "pre", "--slug", slug])
        assert pre.exit_code == 0, pre.output

        # Sanity: research pre removed the old path from disk.
        assert not (repo / source_rel).exists(), (
            "research pre should have moved the explore.md"
        )
        assert (repo / moved_rel).exists(), (
            "research pre should have placed explore.md inside the epic dir"
        )

        # Working tree is dirty BEFORE research post: the old path is
        # tracked-but-deleted (``D <path>``), and the new epic dir is
        # entirely untracked (``?? specs/<epic>/``) until research post
        # stages the move. This is the broken state the fix must collapse.
        pre_status = _git(repo, "status", "--porcelain").stdout
        # Old explore staging path: tracked, deleted in worktree, not
        # yet staged. ``git status --porcelain`` uses two-character XY
        # codes — the index column is empty (`` ``) and the worktree
        # column is ``D`` (so the prefix is `` D <path>``).
        assert any(
            line.startswith(f" D {source_rel}") for line in pre_status.splitlines()
        ), (
            f"expected tracked-deletion of {source_rel} in git status — "
            f"got:\n{pre_status}"
        )
        # New epic dir: untracked (``?? specs/<epic>/`` — git reports
        # the directory itself, not each contained file).
        assert any(
            line.startswith("?? ") and line.endswith(f"{epic_slug}/")
            for line in pre_status.splitlines()
        ), f"expected untracked epic dir {epic_slug} in git status — got:\n{pre_status}"

        # Author the two research artifacts so research post passes its
        # section validator and reaches the stage_and_commit step.
        epic_dir = repo / "specs" / epic_slug
        (epic_dir / "design.md").write_text(
            _render_artifact(_DESIGN_SECTIONS), encoding="utf-8"
        )
        (epic_dir / "data-model.md").write_text(
            _render_artifact(_DATA_MODEL_SECTIONS), encoding="utf-8"
        )

        # research post must stage the move (git add new + git rm old)
        # AND the two new artifacts in a single commit.
        with chdir(repo):
            post = runner.invoke(cli, ["research", "post"])
        assert post.exit_code == 0, post.output

        # HEAD's stat must show the move atomically with the artifacts.
        # Git may report the move as a single rename line (``R100``)
        # instead of separate add+delete lines, depending on similarity
        # detection — both encodings are correct.
        show = _git(repo, "show", "--name-status", "--format=", "HEAD").stdout
        added = {
            line.split("\t", 1)[1]
            for line in show.splitlines()
            if line.startswith("A\t")
        }
        renamed_to = {
            parts[2]
            for parts in (
                line.split("\t") for line in show.splitlines() if line.startswith("R")
            )
            if len(parts) == 3
        }
        deleted = {
            line.split("\t", 1)[1]
            for line in show.splitlines()
            if line.startswith("D\t")
        }
        moved_in_added = moved_rel in added or moved_rel in renamed_to

        assert moved_in_added, (
            f"research post did not stage {moved_rel} — HEAD additions: {added}, "
            f"renames→to: {renamed_to}\nfull show:\n{show}"
        )
        assert source_rel in deleted or any(
            line.startswith("R") and source_rel in line for line in show.splitlines()
        ), (
            f"research post did not stage deletion of {source_rel} — "
            f"HEAD deletions: {deleted}\nfull show:\n{show}"
        )
        assert f"specs/{epic_slug}/design.md" in added
        assert f"specs/{epic_slug}/data-model.md" in added
        # Working tree must be clean for the explore-move paths — no
        # leftover tracked-but-deleted or untracked entries from the
        # move. Other untracked dirs (``.deviate/`` and the like) are
        # unrelated to the move and are expected noise; we filter them
        # out rather than pretend the repo has zero untracked state.
        post_status = _git(repo, "status", "--porcelain").stdout
        move_residue = [
            line
            for line in post_status.splitlines()
            if source_rel in line or moved_rel in line
        ]
        assert not move_residue, (
            f"working tree still has explore-move residue: {move_residue}\n"
            f"full status:\n{post_status}"
        )

    def test_research_post_does_not_touch_explore_when_pre_was_skipped(
        self, tmp_git_repo: Path
    ) -> None:
        """If research pre never ran (no source move happened), research
        post must NOT ``git rm`` a path that was never tracked from the
        explore staging dir. Regression guard against the fix running
        ``git rm specs/explore/<slug>.md`` unconditionally.
        """
        slug = "no-pre-run"
        specs = tmp_git_repo / "specs"
        (specs / "explore").mkdir(parents=True)
        (specs / "constitution.md").write_text("# Constitution\n")
        (tmp_git_repo / ".deviate").mkdir(exist_ok=True)
        SessionState(current_phase="RESEARCH").save(
            tmp_git_repo / ".deviate" / "session.json"
        )

        # Author design.md + data-model.md directly into the epic dir
        # WITHOUT invoking research pre — simulates the manual escape
        # hatch where the operator authored artifacts by hand.
        epic_slug = f"001-{slug}"
        (specs / epic_slug).mkdir(parents=True)
        (specs / epic_slug / "design.md").write_text(
            _render_artifact(_DESIGN_SECTIONS), encoding="utf-8"
        )
        (specs / epic_slug / "data-model.md").write_text(
            _render_artifact(_DATA_MODEL_SECTIONS), encoding="utf-8"
        )

        with chdir(tmp_git_repo):
            post = runner.invoke(cli, ["research", "post", "--epic", epic_slug])
        assert post.exit_code == 0, post.output

        # HEAD must NOT contain a deletion of specs/explore/<slug>.md —
        # it was never tracked, so ``git rm`` would have failed or
        # produced a phantom delete in the commit stat.
        show = _git(tmp_git_repo, "show", "--name-status", "--format=", "HEAD").stdout
        assert f"specs/explore/{slug}.md" not in show, (
            f"research post staged a deletion that never happened:\n{show}"
        )
