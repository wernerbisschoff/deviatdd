"""Pin SemVer bump rules and the on-demand Release workflow contract."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest
import yaml

from tests.conftest import _git_env

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "next_version.py"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "release.yml"


def _load_next_version():
    spec = importlib.util.spec_from_file_location("next_version", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


nv = _load_next_version()


def _git(*args: str, repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    )


def _seed_versioned_repo(repo: Path, version: str = "2.22.0") -> None:
    (repo / "pyproject.toml").write_text(
        f'[project]\nname = "deviatdd"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    (repo / "uv.lock").write_text(
        f'name = "other"\nversion = "0.1.0"\n\n'
        f'name = "deviatdd"\nversion = "{version}"\n'
        f'source = {{ editable = "." }}\n',
        encoding="utf-8",
    )
    _git("add", "pyproject.toml", "uv.lock", repo=repo)
    _git("commit", "-m", f"chore(release): version {version}", repo=repo)


def _commit_message(repo: Path, message: str) -> None:
    marker = repo / "history.txt"
    previous = marker.read_text(encoding="utf-8") if marker.exists() else ""
    marker.write_text(previous + message + "\n", encoding="utf-8")
    _git("add", "history.txt", repo=repo)
    _git("commit", "-m", message, repo=repo)


class TestBumpRules:
    def test_feat_bumps_minor(self, tmp_git_repo: Path) -> None:
        _seed_versioned_repo(tmp_git_repo, "2.22.0")
        _commit_message(tmp_git_repo, "feat(micro): add review pause")
        assert nv.compute_next_version(tmp_git_repo) == "2.23.0"

    def test_fix_bumps_patch(self, tmp_git_repo: Path) -> None:
        _seed_versioned_repo(tmp_git_repo, "2.22.0")
        _commit_message(tmp_git_repo, "fix(judge): persist feedback on the card")
        assert nv.compute_next_version(tmp_git_repo) == "2.22.1"

    def test_breaking_change_bumps_major(self, tmp_git_repo: Path) -> None:
        _seed_versioned_repo(tmp_git_repo, "2.22.0")
        _commit_message(
            tmp_git_repo,
            "feat(api): rename inspect output\n\nBREAKING CHANGE: JSON keys changed",
        )
        assert nv.compute_next_version(tmp_git_repo) == "3.0.0"

    def test_feat_bang_bumps_major(self, tmp_git_repo: Path) -> None:
        _seed_versioned_repo(tmp_git_repo, "2.22.0")
        _commit_message(tmp_git_repo, "feat!: drop legacy ISS- prefix")
        assert nv.compute_next_version(tmp_git_repo) == "3.0.0"

    def test_fix_bang_bumps_major(self, tmp_git_repo: Path) -> None:
        _seed_versioned_repo(tmp_git_repo, "2.22.0")
        _commit_message(tmp_git_repo, "fix(cli)!: change exit codes")
        assert nv.compute_next_version(tmp_git_repo) == "3.0.0"

    def test_chore_docs_only_still_bumps_patch(self, tmp_git_repo: Path) -> None:
        _seed_versioned_repo(tmp_git_repo, "2.22.0")
        _commit_message(tmp_git_repo, "docs: clarify contributing")
        _commit_message(tmp_git_repo, "chore: tidy scripts")
        _commit_message(tmp_git_repo, "test: pin bump rules")
        _commit_message(tmp_git_repo, "ci: add release workflow")
        _commit_message(tmp_git_repo, "style: ruff format")
        _commit_message(tmp_git_repo, "refactor: extract helper")
        assert nv.compute_next_version(tmp_git_repo) == "2.22.1"

    def test_highest_commit_wins(self, tmp_git_repo: Path) -> None:
        _seed_versioned_repo(tmp_git_repo, "2.22.0")
        _commit_message(tmp_git_repo, "fix: typo")
        _commit_message(tmp_git_repo, "feat: new command")
        _commit_message(tmp_git_repo, "docs: readme")
        assert nv.compute_next_version(tmp_git_repo) == "2.23.0"

    def test_empty_history_since_version_still_patches(
        self, tmp_git_repo: Path
    ) -> None:
        _seed_versioned_repo(tmp_git_repo, "2.22.0")
        assert nv.compute_next_version(tmp_git_repo) == "2.22.1"

    def test_explicit_bump_overrides_commits(self, tmp_git_repo: Path) -> None:
        _seed_versioned_repo(tmp_git_repo, "2.22.0")
        _commit_message(tmp_git_repo, "fix: small bug")
        assert nv.compute_next_version(tmp_git_repo, bump="minor") == "2.23.0"
        assert nv.compute_next_version(tmp_git_repo, bump="major") == "3.0.0"
        assert nv.compute_next_version(tmp_git_repo, bump="patch") == "2.22.1"


class TestBaselineFallback:
    def test_falls_back_to_latest_v_tag(self, tmp_git_repo: Path) -> None:
        (tmp_git_repo / "pyproject.toml").write_text(
            '[project]\nname = "deviatdd"\nversion = "1.0.0"\n',
            encoding="utf-8",
        )
        _git("add", "pyproject.toml", repo=tmp_git_repo)
        _git("commit", "-m", "chore: seed 1.0.0", repo=tmp_git_repo)
        _git("tag", "v1.0.0", repo=tmp_git_repo)
        _commit_message(tmp_git_repo, "feat: after the tag")
        (tmp_git_repo / "pyproject.toml").write_text(
            '[project]\nname = "deviatdd"\nversion = "9.9.9"\n',
            encoding="utf-8",
        )
        assert nv.compute_next_version(tmp_git_repo) == "9.10.0"

    def test_falls_back_to_previous_release_commit(self, tmp_git_repo: Path) -> None:
        (tmp_git_repo / "pyproject.toml").write_text(
            '[project]\nname = "deviatdd"\nversion = "1.0.0"\n',
            encoding="utf-8",
        )
        _git("add", "pyproject.toml", repo=tmp_git_repo)
        _git("commit", "-m", "chore(release): version 1.0.0", repo=tmp_git_repo)
        _commit_message(tmp_git_repo, "feat: after the release commit")
        (tmp_git_repo / "pyproject.toml").write_text(
            '[project]\nname = "deviatdd"\nversion = "9.9.9"\n',
            encoding="utf-8",
        )
        assert nv.compute_next_version(tmp_git_repo) == "9.10.0"


class TestPersistAndDryRun:
    def test_persist_writes_pyproject_and_deviatdd_lock_block(
        self, tmp_git_repo: Path
    ) -> None:
        _seed_versioned_repo(tmp_git_repo, "2.22.0")
        nv.persist_version(tmp_git_repo, "2.23.0")
        pyproject = (tmp_git_repo / "pyproject.toml").read_text(encoding="utf-8")
        lock = (tmp_git_repo / "uv.lock").read_text(encoding="utf-8")
        assert 'version = "2.23.0"' in pyproject
        assert 'name = "deviatdd"\nversion = "2.23.0"' in lock
        assert 'name = "other"\nversion = "0.1.0"' in lock

    def test_dry_run_prints_version_and_has_no_side_effects(
        self, tmp_git_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_versioned_repo(tmp_git_repo, "2.22.0")
        _commit_message(tmp_git_repo, "feat: something new")
        head_before = _git("rev-parse", "HEAD", repo=tmp_git_repo).stdout.strip()
        pyproject_before = (tmp_git_repo / "pyproject.toml").read_text(encoding="utf-8")
        lock_before = (tmp_git_repo / "uv.lock").read_text(encoding="utf-8")
        tags_before = _git("tag", repo=tmp_git_repo).stdout

        rc = nv.main(
            [
                "--repo",
                str(tmp_git_repo),
                "--dry-run",
                "--write",
                "--bump",
                "auto",
            ]
        )

        assert rc == 0
        assert capsys.readouterr().out.strip() == "2.23.0"
        assert (tmp_git_repo / "pyproject.toml").read_text(
            encoding="utf-8"
        ) == pyproject_before
        assert (tmp_git_repo / "uv.lock").read_text(encoding="utf-8") == lock_before
        assert (
            _git("rev-parse", "HEAD", repo=tmp_git_repo).stdout.strip() == head_before
        )
        assert _git("tag", repo=tmp_git_repo).stdout == tags_before


class TestReleaseWorkflowContract:
    def test_dispatch_only_with_expected_inputs_and_permissions(self) -> None:
        text = _WORKFLOW.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        # PyYAML 1.1 treats the unquoted key `on` as boolean True.
        on_block = data.get("on", data.get(True))
        assert set(on_block) == {"workflow_dispatch"}
        inputs = on_block["workflow_dispatch"]["inputs"]
        assert inputs["bump"]["default"] == "auto"
        assert set(inputs["bump"]["options"]) == {"auto", "patch", "minor", "major"}
        assert inputs["dry_run"]["type"] == "boolean"
        assert inputs["dry_run"]["default"] is False
        assert data["permissions"] == {"contents": "write"}
        assert "id-token" not in text
        assert "python-semantic-release" not in text
        assert "PYPI_API_TOKEN missing" in text
        assert "UV_PUBLISH_TOKEN" in text
        assert "secrets.PYPI_API_TOKEN" in text
        assert "default_branch" in text
        assert "chore(release): version" in text
        assert "uv build" in text
        assert "uv publish" in text
        assert "CHANGELOG" not in text
