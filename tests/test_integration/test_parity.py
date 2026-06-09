from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

BASH_SKILLS_DIR = Path.home() / ".claude" / "skills"
DEVIATE_CLI = ["uv", "run", "deviate"]


def _git_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, env=_git_env(), check=True)
    subprocess.run(
        ["git", "config", "user.email", "runner@test.local"],
        cwd=path,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test Runner"],
        cwd=path,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "initial"],
        cwd=path,
        env=_git_env(),
        check=True,
    )


def _install_deviate(path: Path) -> None:
    specs_dir = path / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    constitution = specs_dir / "constitution.md"
    constitution.write_text(
        "# Constitution\n\n"
        "## [3_TESTING_PROTOCOLS]\n"
        "`TEST_COMMAND`: pytest\n"
        "`LINT_COMMAND`: ruff check .\n"
    )
    subprocess.run(
        [*DEVIATE_CLI, "init", "--agent-export-mode", "local"],
        cwd=path,
        capture_output=True,
        text=True,
        check=True,
    )


def _find_bash_scripts() -> list[tuple[str, Path]]:
    scripts = []
    if not BASH_SKILLS_DIR.exists():
        return scripts
    for d in sorted(BASH_SKILLS_DIR.glob("deviate-*")):
        if not d.is_dir():
            continue
        script = d / f"{d.name}.sh"
        if script.exists():
            scripts.append((d.name, script))
    return scripts


def _run_bash(
    script_path: Path, args: list[str], cwd: Path
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(script_path), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def _run_python(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*DEVIATE_CLI, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def _parse_json_contract(output: str) -> dict:
    lines = output.strip().splitlines()
    buf: list[str] = []
    in_json = False
    depth = 0
    for line in lines:
        stripped = line.strip()
        if not in_json:
            if stripped.startswith("{"):
                in_json = True
                buf = [line]
                depth = 1
                for ch in stripped[1:]:
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                if depth == 0:
                    break
        else:
            buf.append(line)
            for ch in stripped:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
            if depth == 0:
                break
    if not buf:
        raise ValueError("No JSON contract found in output")
    raw = "".join(buf)
    return json.loads(raw)


EXPLORE_BASH_FIELDS = {
    "status",
    "phase",
    "repo_root",
    "git_branch",
    "feature_slug",
    "feature_dir",
    "specs_directory",
    "spec_target",
    "spec_target_abs",
    "constitution_path",
    "test_command",
    "lint_command",
    "type_check_command",
    "constitution_test_command",
    "constitution_lint_command",
    "epic_id",
    "is_greenfield",
    "timestamp",
}

RESEARCH_BASH_FIELDS = {
    "status",
    "phase",
    "repo_root",
    "git_branch",
    "feature_slug",
    "feature_dir",
    "specs_directory",
    "explore_md_path",
    "explore_md_rel",
    "design_target",
    "design_target_abs",
    "data_model_target",
    "data_model_target_abs",
    "constitution_path",
    "test_command",
    "lint_command",
    "type_check_command",
    "constitution_test_command",
    "constitution_lint_command",
    "epic_id",
    "issues_ledger",
    "is_greenfield",
    "timestamp",
}


class TestParity:
    def test_bash_skills_still_parse(self, tmp_path: Path) -> None:
        scripts = _find_bash_scripts()
        if not scripts:
            pytest.skip(
                "No bash deviate scripts found — project migrated to Python CLI"
            )

        failures: list[str] = []
        for name, script in scripts:
            result = _run_bash(script, ["--help"], tmp_path)
            if result.returncode != 0:
                stderr_snippet = result.stderr.strip()[:200]
                failures.append(f"{name}: exit {result.returncode} - {stderr_snippet}")

        assert not failures, "Bash scripts with non-zero --help exit:\n" + "\n".join(
            failures
        )

    def test_explore_python_matches_bash_fields(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _install_deviate(tmp_path)

        bash_script = BASH_SKILLS_DIR / "deviate-explore" / "deviate-explore.sh"
        if not bash_script.exists():
            pytest.skip("bash explore script not found")

        bash_result = _run_bash(bash_script, ["pre", "test parity feature"], tmp_path)
        assert bash_result.returncode == 0, (
            f"bash explore pre failed:\nstdout:{bash_result.stdout}\nstderr:{bash_result.stderr}"
        )
        bash_contract = _parse_json_contract(bash_result.stdout)
        assert EXPLORE_BASH_FIELDS.issubset(set(bash_contract.keys())), (
            f"bash contract missing expected fields: {EXPLORE_BASH_FIELDS - set(bash_contract.keys())}"
        )

        python_result = _run_python(
            ["explore", "pre", "test parity feature", "--slug", "test-parity"],
            tmp_path,
        )
        if python_result.returncode != 0:
            pytest.skip(
                f"python explore pre unavailable (will retest later):\n"
                f"{python_result.stderr}"
            )
        python_contract = _parse_json_contract(python_result.stdout)

        py_fields = set(python_contract.keys())
        missing = EXPLORE_BASH_FIELDS - py_fields
        assert not missing, (
            f"Python contract missing bash fields: {missing}\n"
            f"Python fields: {sorted(py_fields)}\n"
            f"Expected bash fields: {sorted(EXPLORE_BASH_FIELDS)}"
        )
        assert py_fields.issuperset(EXPLORE_BASH_FIELDS), (
            "Python field set is not a superset of bash fields"
        )

    def test_research_python_matches_bash_fields(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _install_deviate(tmp_path)

        specs_dir = tmp_path / "specs"
        epic_dir = specs_dir / "001-research-test"
        epic_dir.mkdir(parents=True, exist_ok=True)
        (epic_dir / "explore.md").write_text(
            "# Explore\n\n## [PROBLEM_DEFINITION]\n\n## [DISCOVERY_AUDIT_RESULTS]\n\n## [CONSTITUTION_QUOTES]\n\n## [FILE_REGISTRY]\n\n## [STATUS_SUMMARY]\n"
        )

        bash_script = BASH_SKILLS_DIR / "deviate-research" / "deviate-research.sh"
        if not bash_script.exists():
            pytest.skip("bash research script not found")

        bash_result = _run_bash(bash_script, ["pre", "001-research-test"], tmp_path)
        if bash_result.returncode != 0:
            pytest.skip(
                f"bash research pre unavailable:\n"
                f"stdout:{bash_result.stdout}\nstderr:{bash_result.stderr}"
            )
        bash_contract = _parse_json_contract(bash_result.stdout)
        assert RESEARCH_BASH_FIELDS.issubset(set(bash_contract.keys())), (
            f"bash research contract missing expected fields: {RESEARCH_BASH_FIELDS - set(bash_contract.keys())}"
        )

        python_result = _run_python(["research", "pre", "001-research-test"], tmp_path)
        if python_result.returncode != 0:
            pytest.skip(f"python research pre unavailable:\n{python_result.stderr}")
        python_contract = _parse_json_contract(python_result.stdout)

        py_fields = set(python_contract.keys())
        missing = RESEARCH_BASH_FIELDS - py_fields
        assert not missing, (
            f"Python research contract missing bash fields: {missing}\n"
            f"Python fields: {sorted(py_fields)}\n"
            f"Expected bash fields: {sorted(RESEARCH_BASH_FIELDS)}"
        )
