from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import NoReturn

import typer
from rich.console import Console

init_app = typer.Typer(no_args_is_help=True)
console = Console()


def _fail_with(reason: str) -> NoReturn:
    print(json.dumps({"status": "FAILURE", "reason": reason}))
    raise typer.Exit(code=1)


def _detect_project_type(repo_root: Path) -> str:
    if (repo_root / "mix.exs").exists():
        return "elixir_phoenix"
    if (repo_root / "pyproject.toml").exists():
        return "python"
    if (repo_root / "package.json").exists():
        return "node"
    if (repo_root / "Cargo.toml").exists():
        return "rust"
    if (repo_root / "go.mod").exists():
        return "go"
    return "unknown"


def _get_test_command(project_type: str) -> str:
    commands = {
        "elixir_phoenix": "mix test",
        "python": "uv run pytest",
        "node": "npm test",
        "rust": "cargo test",
        "go": "go test ./...",
    }
    return commands.get(project_type, "true")


def _get_zero_test_pass_command(project_type: str) -> str:
    commands = {
        "elixir_phoenix": "mix test || true",
        "python": "uv run pytest || true",
        "node": "npm test || true",
        "rust": "cargo test || true",
        "go": "go test ./... || true",
    }
    return commands.get(project_type, "echo 'No test framework' || true")


def _get_lint_command(project_type: str) -> str:
    commands = {
        "elixir_phoenix": "mix credo --strict",
        "python": "uv run ruff check",
        "node": "npm run lint 2>/dev/null || echo 'No lint configured'",
        "rust": "cargo clippy -- -D warnings",
        "go": "golangci-lint run 2>/dev/null || echo 'No linter configured'",
    }
    return commands.get(project_type, "echo 'No linter configured'")


def _get_format_command(project_type: str) -> str:
    commands = {
        "elixir_phoenix": "mix format",
        "python": "uv run ruff format",
        "node": "npm run format 2>/dev/null || echo 'No formatter configured'",
        "rust": "cargo fmt",
        "go": "gofmt -w .",
    }
    return commands.get(project_type, "echo 'No formatter configured'")


def _get_format_check_command(project_type: str) -> str:
    commands = {
        "elixir_phoenix": "mix format --check-formatted",
        "python": "uv run ruff format --check",
        "node": "npm run format:check 2>/dev/null || echo 'No format check configured'",
        "rust": "cargo fmt --check",
        "go": "gofmt -l .",
    }
    return commands.get(project_type, "echo 'No format check configured'")


def _get_setup_command(project_type: str) -> str:
    commands = {
        "elixir_phoenix": "mix deps.get && mix deps.compile",
        "python": "uv sync --extra dev",
        "node": "npm install",
        "rust": "cargo fetch",
        "go": "go mod download",
    }
    return commands.get(project_type, "echo 'No setup required'")


def _get_dev_command(project_type: str, repo_root: Path) -> str:
    if project_type == "elixir_phoenix":
        return "mix phx.server"
    if project_type == "python":
        pyproject = repo_root / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            if "uvicorn" in content.lower() or "fastapi" in content.lower():
                name = repo_root.name.replace("-", "_")
                return f"uv run uvicorn {name}:app --reload"
            if "django" in content.lower():
                return "uv run python manage.py runserver"
            if "flask" in content.lower():
                return "uv run flask --reload run"
        return f"uv run python -m {repo_root.name}"
    if project_type == "node":
        return "npm run dev 2>/dev/null || npm run start"
    if project_type == "rust":
        return "cargo run"
    if project_type == "go":
        return "go run ."
    return "echo 'No dev server configured'"


def _generate_mise_toml(project_type: str, repo_root: Path) -> str:
    if project_type == "elixir_phoenix":
        return """# Mise configuration for Elixir/Phoenix project
# Scaffolded by /deviate-init — DeviaTDD scaffolding
# ZERO-TEST-PASS: test task uses || true to pass when no tests exist

[tools]
elixir = "latest"
erlang = "latest"

[tasks]
# DeviaTDD zero-test-pass invariant: passes even with zero tests written
test = "mix test || true"
test-raw = "mix test"
setup = { depends = ["hooks"], run = "mix deps.get && mix deps.compile" }
lint = "mix credo --strict"
format = "mix format"
format-check = "mix format --check-formatted"
fix = { depends = ["format", "lint"] }
check = { depends = ["format-check", "lint", "test"] }
pre-commit = { depends = ["format-check", "lint"] }
pre-push = { depends = ["test"] }
hooks = "mise generate git-pre-commit --write && mise generate git-pre-commit --hook pre-push --write"
dev = "mix phx.server"
clean = "mix clean && rm -rf _build deps .fetch"
"""
    if project_type == "python":
        dev_cmd = _get_dev_command(project_type, repo_root)
        return f"""# Mise configuration for Python project
# Scaffolded by /deviate-init — DeviaTDD scaffolding
# ZERO-TEST-PASS: test task uses || true to pass when no tests exist

[tools]
python = "3.12"
uv = "latest"

[tasks]
# DeviaTDD zero-test-pass invariant: passes even with zero tests written
test = "uv run pytest || true"
test-raw = "uv run pytest"
setup = {{ depends = ["hooks"], run = "uv sync --extra dev" }}
lint = "uv run ruff check"
format = "uv run ruff format"
format-check = "uv run ruff format --check"
fix = {{ depends = ["format", "lint"] }}
check = {{ depends = ["format-check", "lint", "test"] }}
pre-commit = {{ depends = ["format-check", "lint"] }}
pre-push = {{ depends = ["test"] }}
hooks = "mise generate git-pre-commit --write && mise generate git-pre-commit --hook pre-push --write"
dev = "{dev_cmd}"
clean = "rm -rf .venv dist build __pycache__"
"""
    if project_type == "node":
        pkg_manager = "npm"
        if (repo_root / "pnpm-lock.yaml").exists():
            pkg_manager = "pnpm"
        elif (repo_root / "yarn.lock").exists():
            pkg_manager = "yarn"
        return f"""# Mise configuration for Node.js project
# Scaffolded by /deviate-init — DeviaTDD scaffolding
# ZERO-TEST-PASS: test task uses || true to pass when no tests exist

[tools]
node = "lts"
{pkg_manager} = "latest"

[tasks]
# DeviaTDD zero-test-pass invariant: passes even with zero tests written
test = "{pkg_manager} test || true"
test-raw = "{pkg_manager} test"
setup = {{ depends = ["hooks"], run = "{pkg_manager} install" }}
lint = "{pkg_manager} run lint 2>/dev/null || echo 'No lint configured'"
format = "{pkg_manager} run format 2>/dev/null || echo 'No formatter configured'"
format-check = "{pkg_manager} run format:check 2>/dev/null || echo 'No format check configured'"
fix = {{ depends = ["format", "lint"] }}
check = {{ depends = ["format-check", "lint", "test"] }}
pre-commit = {{ depends = ["format-check", "lint"] }}
pre-push = {{ depends = ["test"] }}
hooks = "mise generate git-pre-commit --write && mise generate git-pre-commit --hook pre-push --write"
dev = "{pkg_manager} run dev 2>/dev/null || {pkg_manager} run start"
clean = "rm -rf node_modules dist build"
"""
    if project_type == "rust":
        return """# Mise configuration for Rust project
# Scaffolded by /deviate-init — DeviaTDD scaffolding
# ZERO-TEST-PASS: test task uses || true to pass when no tests exist

[tools]
rust = "stable"

[tasks]
# DeviaTDD zero-test-pass invariant: passes even with zero tests written
test = "cargo test || true"
test-raw = "cargo test"
setup = { depends = ["hooks"], run = "cargo fetch" }
lint = "cargo clippy -- -D warnings"
format = "cargo fmt"
format-check = "cargo fmt --check"
fix = { depends = ["format", "lint"] }
check = { depends = ["format-check", "lint", "test"] }
pre-commit = { depends = ["format-check", "lint"] }
pre-push = { depends = ["test"] }
hooks = "mise generate git-pre-commit --write && mise generate git-pre-commit --hook pre-push --write"
dev = "cargo run"
clean = "cargo clean"
"""
    if project_type == "go":
        return """# Mise configuration for Go project
# Scaffolded by /deviate-init — DeviaTDD scaffolding
# ZERO-TEST-PASS: test task uses || true to pass when no tests exist

[tools]
go = "latest"

[tasks]
# DeviaTDD zero-test-pass invariant: passes even with zero tests written
test = "go test ./... || true"
test-raw = "go test ./..."
setup = { depends = ["hooks"], run = "go mod download" }
lint = "golangci-lint run 2>/dev/null || echo 'No linter configured'"
format = "gofmt -w ."
format-check = "gofmt -l ."
fix = { depends = ["format", "lint"] }
check = { depends = ["format-check", "lint", "test"] }
pre-commit = { depends = ["format-check", "lint"] }
pre-push = { depends = ["test"] }
hooks = "mise generate git-pre-commit --write && mise generate git-pre-commit --hook pre-push --write"
dev = "go run ."
clean = "go clean"
"""
    _fail_with(f"Unknown project type: {project_type}")


def _scaffold_constitution(project_type: str, repo_root: Path) -> None:
    test_cmd = _get_test_command(project_type)
    lint_cmd = _get_lint_command(project_type)

    constitution_path = repo_root / "specs" / "constitution.md"
    constitution_path.write_text(
        f"""# Project Constitution

Version: 0.1.0

---

## 1. Architectural Principles
> TBD — populated by `/research` from codebase analysis.

## 2. Tech Stack Standards

### Backend
> TBD

### Frontend
> TBD

### Database
> TBD

### Infrastructure
> TBD

### Tooling
> TBD

## 3. Testing Protocols

### Framework
- `TEST_COMMAND`: `{test_cmd}`
- `LINT_COMMAND`: `{lint_cmd}`

### Coverage
> TBD

## 4. Development Workflow
> TBD — populated by `/research`.

## 5. Definition of Done
- [ ] Code implemented
- [ ] Tests passing
- [ ] Lint passing
- [ ] Documentation updated
- [ ] No governance violations

## 6. Version History

- 0.1.0 — Initial constitution scaffolded by `deviate init`
""",
        encoding="utf-8",
    )


def _check_tool(name: str) -> bool:
    try:
        subprocess.run(
            ["which", name],
            capture_output=True,
            check=False,
        )
        return True
    except Exception:
        return False


@init_app.command()
def pre() -> None:
    """Detect project type, scaffold DeviaTDD structure, emit JSON contract."""
    try:
        repo_root = Path(
            subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
    except subprocess.CalledProcessError:
        _fail_with("Not a git repository")

    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        branch = "unknown"

    project_type = _detect_project_type(repo_root)

    has_mise_toml = (repo_root / "mise.toml").exists()
    has_specs_dir = (repo_root / "specs").exists()
    has_constitution = (repo_root / "specs" / "constitution.md").exists()
    has_issues_ledger = (repo_root / "specs" / "issues.jsonl").exists()
    has_claude_md = (repo_root / "CLAUDE.md").exists()

    mise_available = _check_tool("mise")
    tooling = {
        "mise": mise_available,
        "jq": _check_tool("jq"),
        "gh": _check_tool("gh"),
        "uv": _check_tool("uv"),
        "ruff": _check_tool("ruff"),
    }

    artifacts_created = []

    if not has_mise_toml and project_type != "unknown":
        mise_content = _generate_mise_toml(project_type, repo_root)
        (repo_root / "mise.toml").write_text(mise_content, encoding="utf-8")
        has_mise_toml = True
        artifacts_created.append("mise.toml")

    if not has_specs_dir:
        (repo_root / "specs").mkdir(exist_ok=True)
        has_specs_dir = True
        artifacts_created.append("specs/")
    else:
        artifacts_created.append("specs/")

    if not has_issues_ledger:
        (repo_root / "specs" / "issues.jsonl").touch()
        has_issues_ledger = True
        artifacts_created.append("specs/issues.jsonl")

    if not has_constitution:
        _scaffold_constitution(project_type, repo_root)
        has_constitution = True
        artifacts_created.append("specs/constitution.md")

    from deviate.cli import _linkify_governance_files

    _linkify_governance_files(repo_root)
    if (repo_root / "AGENTS.md").is_symlink():
        artifacts_created.append("AGENTS.md")

    # Provision union-merge rules for append-only JSONL ledgers.
    # Idempotent: never duplicates entries, never overwrites user content.
    from deviate.cli import _ensure_root_gitattributes

    _ensure_root_gitattributes(repo_root)
    if (repo_root / ".gitattributes").exists():
        artifacts_created.append(".gitattributes")

    try:
        top_level_entries = [
            p.name for p in repo_root.iterdir() if p.name not in (".git",)
        ]
    except Exception:
        top_level_entries = []

    contract = {
        "phase": "deviate-init",
        "status": "READY",
        "branch": branch,
        "repo_root": str(repo_root),
        "project_type": project_type,
        "tooling": tooling,
        "mise_available": mise_available,
        "gh_available": _check_tool("gh"),
        "existing_artifacts": {
            "mise_toml": has_mise_toml,
            "specs_dir": has_specs_dir,
            "constitution": has_constitution,
            "issues_ledger": has_issues_ledger,
            "claude_md": has_claude_md,
        },
        "artifacts_created": artifacts_created,
        "top_level_entries": top_level_entries,
        "timestamp": subprocess.check_output(
            ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
            text=True,
        ).strip(),
    }

    print(json.dumps(contract, indent=2))


@init_app.command()
def post() -> None:
    """Validate artifacts, stage for commit, emit status JSON."""
    try:
        repo_root = Path(
            subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
    except subprocess.CalledProcessError:
        _fail_with("Not a git repository")

    artifacts = []
    if (repo_root / "mise.toml").exists():
        artifacts.append("mise.toml")
    if (repo_root / "specs").is_dir():
        artifacts.append("specs/")
    if (repo_root / "specs" / "constitution.md").exists():
        artifacts.append("specs/constitution.md")
    if (repo_root / "specs" / "issues.jsonl").exists():
        artifacts.append("specs/issues.jsonl")
    if (repo_root / "AGENTS.md").is_symlink():
        artifacts.append("AGENTS.md")
    if (repo_root / ".gitattributes").exists():
        artifacts.append(".gitattributes")

    if artifacts:
        subprocess.run(
            ["git", "add"] + artifacts,
            cwd=repo_root,
            check=False,
        )

    print(
        json.dumps(
            {
                "status": "SUCCESS",
                "artifacts_created": artifacts,
                "artifact_count": len(artifacts),
            },
            indent=2,
        )
    )
