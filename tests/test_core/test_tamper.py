from __future__ import annotations

import subprocess
from pathlib import Path

from deviate.core.tamper import TamperContext, TamperGuard, TamperVerdict


def _git_env() -> dict[str, str]:
    import os

    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _init_and_commit(repo: Path, path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    subprocess.run(["git", "add", str(path)], cwd=repo, env=_git_env(), check=True)
    subprocess.run(
        ["git", "commit", "-m", f"add {path.name}"],
        cwd=repo,
        env=_git_env(),
        check=True,
    )


def _git_diff_names(repo: Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=repo,
        env=_git_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


class TestTamperDetectsTestModification:
    def test_detects_test_modification_and_restores(self, tmp_git_repo: Path) -> None:
        repo = tmp_git_repo
        test_file = repo / "tests" / "test_foo.py"
        original = "def test_foo(): pass\n"
        _init_and_commit(repo, test_file, original)

        test_file.write_text("def test_foo(): assert False\n")

        result = TamperGuard.evaluate(
            context=TamperContext.GREEN_IMPLEMENTATION, repo_path=repo
        )

        assert result == TamperVerdict.TAMPER_DETECTED
        assert test_file.read_text() == original


class TestTamperPassesSrcOnlyChanges:
    def test_passes_src_only_changes(self, tmp_git_repo: Path) -> None:
        repo = tmp_git_repo
        test_file = repo / "tests" / "test_foo.py"
        src_file = repo / "src" / "foo.py"
        _init_and_commit(repo, test_file, "def test_foo(): pass\n")
        _init_and_commit(repo, src_file, "def foo(): pass\n")

        src_file.write_text("def foo(): return 42\n")

        result = TamperGuard.evaluate(
            context=TamperContext.GREEN_IMPLEMENTATION, repo_path=repo
        )

        assert result == TamperVerdict.TAMPER_PASS
        assert src_file.read_text() == "def foo(): return 42\n"


class TestTamperDetectsSpecModification:
    def test_detects_spec_modification(self, tmp_git_repo: Path) -> None:
        repo = tmp_git_repo
        spec_file = repo / "specs" / "spec.md"
        _init_and_commit(repo, spec_file, "# Original spec\n")

        spec_file.write_text("# Modified spec\n")

        result = TamperGuard.evaluate(
            context=TamperContext.GREEN_IMPLEMENTATION, repo_path=repo
        )

        assert result == TamperVerdict.TAMPER_DETECTED


class TestTamperDetectsConfigModification:
    def test_detects_config_modification(self, tmp_git_repo: Path) -> None:
        repo = tmp_git_repo
        config_file = repo / ".deviate" / "config.toml"
        _init_and_commit(config_file.parent, config_file, 'profile = "default"\n')

        config_file.write_text('profile = "modified"\n')

        result = TamperGuard.evaluate(
            context=TamperContext.GREEN_IMPLEMENTATION, repo_path=repo
        )

        assert result == TamperVerdict.TAMPER_DETECTED


class TestTamperIgnoresRedTestCreation:
    def test_ignores_red_test_creation(self, tmp_git_repo: Path) -> None:
        repo = tmp_git_repo
        new_test = repo / "tests" / "test_new.py"
        new_test.parent.mkdir(parents=True, exist_ok=True)
        new_test.write_text("def test_new(): pass\n")

        result = TamperGuard.evaluate(
            context=TamperContext.RED_TEST_CREATION, repo_path=repo
        )

        assert result == TamperVerdict.TAMPER_PASS
        assert new_test.exists()


class TestTamperAcceptsYellowApprovedChanges:
    def test_accepts_yellow_approved_changes(self, tmp_git_repo: Path) -> None:
        repo = tmp_git_repo
        test_file = repo / "tests" / "test_foo.py"
        _init_and_commit(repo, test_file, "def test_foo(): pass\n")

        test_file.write_text("def test_foo(): assert True\n")

        result = TamperGuard.evaluate(
            context=TamperContext.GREEN_IMPLEMENTATION,
            repo_path=repo,
            approved_mods=["tests/test_foo.py"],
        )

        assert result == TamperVerdict.TAMPER_PASS
        assert test_file.read_text() == "def test_foo(): assert True\n"
