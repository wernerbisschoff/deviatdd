from __future__ import annotations

import subprocess
from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState

runner = CliRunner()


def _git_env() -> dict[str, str]:
    import os

    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _setup_macro_workspace(
    tmp_git_repo: Path,
    target_slug: str = "my-feature",
    with_bucket_dir: bool = True,
) -> None:
    dot_dir = tmp_git_repo / ".deviate"
    dot_dir.mkdir(parents=True)
    session = SessionState(current_phase="IDLE")
    session.save(dot_dir / "session.json")

    spec_root = tmp_git_repo / "specs"
    spec_root.mkdir(parents=True)
    (spec_root / "constitution.md").write_text("# Constitution\n")
    (spec_root / "issues.jsonl").write_text("")

    if with_bucket_dir:
        feature_dir = spec_root / target_slug
        feature_dir.mkdir(parents=True)

    subprocess.run(
        ["git", "add", "."],
        cwd=tmp_git_repo,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "setup macro workspace"],
        cwd=tmp_git_repo,
        env=_git_env(),
        check=True,
    )


class TestMacroIntegration:
    def test_macro_integration_full_pipeline(self, tmp_git_repo: Path) -> None:
        _setup_macro_workspace(tmp_git_repo, target_slug="my-feature")

        with chdir(tmp_git_repo):
            result = runner.invoke(
                cli, ["macro", "run", "--target", "my-feature", "--dry-run"]
            )
            assert result.exit_code == 0, result.output
            assert "DRY_RUN" in result.output

            loaded = SessionState.load(tmp_git_repo / ".deviate" / "session.json")
            assert loaded.current_phase == "IDLE"

    def test_macro_integration_bucket_not_found(self, tmp_git_repo: Path) -> None:
        _setup_macro_workspace(
            tmp_git_repo, target_slug="my-feature", with_bucket_dir=False
        )

        with chdir(tmp_git_repo):
            result = runner.invoke(
                cli, ["macro", "run", "--target", "nonexistent-slug"]
            )
            assert result.exit_code != 0
            assert "BUCKET_NOT_FOUND" in result.output
