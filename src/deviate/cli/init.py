from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path
from typing import NoReturn

import typer
from rich.console import Console

init_app = typer.Typer(no_args_is_help=True)
console = Console()

_E2E_DIR_CANDIDATES = (Path("tests/e2e"), Path("e2e"), Path("test/e2e"))
_COMPOSE_FILE_CANDIDATES = (Path("docker-compose.yml"), Path("compose.yaml"))


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


def _node_pkg_manager(repo_root: Path) -> str:
    if (repo_root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (repo_root / "yarn.lock").exists():
        return "yarn"
    return "npm"


_INTEG_DIR_CANDIDATES = (
    Path("tests/integration"),
    Path("test/integration"),
    Path("tests/integ"),
)


def _discover_existing_dir(
    repo_root: Path, candidates: tuple[Path, ...]
) -> Path | None:
    for rel in candidates:
        if (repo_root / rel).is_dir():
            return rel
    return None


def _unit_stub_path(project_type: str) -> Path:
    if project_type == "elixir_phoenix":
        return Path("test")
    return Path("tests/unit")


def _integ_stub_path(project_type: str, repo_root: Path) -> Path:
    existing = _discover_existing_dir(repo_root, _INTEG_DIR_CANDIDATES)
    if existing is not None:
        return existing
    if project_type == "elixir_phoenix":
        return Path("test/integration")
    return Path("tests/integration")


def _existing_e2e_dir(repo_root: Path) -> Path | None:
    return _discover_existing_dir(repo_root, _E2E_DIR_CANDIDATES)


def _layer_paths(project_type: str, repo_root: Path) -> tuple[Path, Path]:
    return (
        _unit_stub_path(project_type),
        _integ_stub_path(project_type, repo_root),
    )


def _has_compose_file(repo_root: Path) -> bool:
    return any((repo_root / rel).is_file() for rel in _COMPOSE_FILE_CANDIDATES)


def _toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _allow_empty_pytest(command: str) -> str:
    """Treat pytest exit 5 (no tests collected) as success for an empty stub.

    Assertion failures (exit 1) still fail. This is not ``|| true``.
    """
    return f"{command} || {{ [ $? -eq 5 ]; }}"


def _unit_run(project_type: str, repo_root: Path) -> str:
    unit, _ = _layer_paths(project_type, repo_root)
    unit_s = unit.as_posix()
    if project_type == "elixir_phoenix":
        return "mix test"
    if project_type == "python":
        return f"uv run pytest {unit_s}"
    if project_type == "node":
        return f"{_node_pkg_manager(repo_root)} test -- {unit_s}"
    if project_type == "rust":
        return "cargo test --lib"
    if project_type == "go":
        return f"go test ./{unit_s}/..."
    return f"pytest {unit_s}"


def _integ_run(project_type: str, repo_root: Path) -> str:
    _, integ = _layer_paths(project_type, repo_root)
    integ_s = integ.as_posix()
    if project_type == "elixir_phoenix":
        return f"mix test {integ_s}"
    if project_type == "python":
        return _allow_empty_pytest(f"uv run pytest {integ_s}")
    if project_type == "node":
        return f"{_node_pkg_manager(repo_root)} test -- --passWithNoTests {integ_s}"
    if project_type == "rust":
        return "cargo test --tests"
    if project_type == "go":
        return f"go test ./{integ_s}/..."
    return _allow_empty_pytest(f"pytest {integ_s}")


def _e2e_run(project_type: str, repo_root: Path) -> str:
    e2e = _existing_e2e_dir(repo_root)
    e2e_s = (e2e or Path("tests/e2e")).as_posix()
    if project_type == "elixir_phoenix":
        return f"mix test {e2e_s}"
    if project_type == "python":
        return _allow_empty_pytest(f"uv run pytest {e2e_s}")
    if project_type == "node":
        return f"{_node_pkg_manager(repo_root)} test -- --passWithNoTests {e2e_s}"
    if project_type == "rust":
        return "cargo test --tests"
    if project_type == "go":
        return f"go test ./{e2e_s}/..."
    return _allow_empty_pytest(f"pytest {e2e_s}")


def _doctor_run(project_type: str, repo_root: Path) -> str:
    if project_type == "elixir_phoenix":
        command = "elixir --version && mix --version"
    elif project_type == "python":
        command = "python3 --version && uv --version"
    elif project_type == "node":
        pkg = _node_pkg_manager(repo_root)
        command = f"node --version && {pkg} --version"
    elif project_type == "rust":
        command = "rustc --version && cargo --version"
    elif project_type == "go":
        command = "go version"
    else:
        command = "python3 --version"
    if _has_compose_file(repo_root):
        command += " && docker compose config"
    return command


def _named_mise_tasks(project_type: str, repo_root: Path) -> dict[str, str]:
    # Write ``integration`` so ``mise integration`` works. The runner
    # (_resolve_verification_command) also accepts ``integ`` as an alias
    # when a repo already defines that name; init does not emit ``integ``.
    tasks = {
        "unit": _unit_run(project_type, repo_root),
        "integration": _integ_run(project_type, repo_root),
        "doctor": _doctor_run(project_type, repo_root),
    }
    if _existing_e2e_dir(repo_root) is not None:
        tasks["e2e"] = _e2e_run(project_type, repo_root)
    return tasks


def _ensure_stub_dirs(project_type: str, repo_root: Path) -> list[str]:
    created: list[str] = []
    for rel in _layer_paths(project_type, repo_root):
        # unit + integration stubs only; e2e is never created here
        path = repo_root / rel
        path.mkdir(parents=True, exist_ok=True)
        has_real_entries = any(entry.name != ".gitkeep" for entry in path.iterdir())
        if has_real_entries:
            continue
        gitkeep = path / ".gitkeep"
        if gitkeep.exists():
            continue
        gitkeep.write_text("", encoding="utf-8")
        created.append(str(rel / ".gitkeep"))
    return created


def _mise_task_names(content: str) -> set[str]:
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return set()
    tasks = data.get("tasks")
    if isinstance(tasks, dict):
        return {str(key) for key in tasks}
    return set()


def _render_named_task(name: str, run: str) -> str:
    return f"[tasks.{name}]\nrun = {_toml_string(run)}\n"


def _merge_mise_toml(content: str, named: dict[str, str]) -> str:
    try:
        tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return content
    existing = _mise_task_names(content)
    additions = [
        _render_named_task(name, run)
        for name, run in named.items()
        if name not in existing
    ]
    if not additions:
        return content
    if content and not content.endswith("\n"):
        content += "\n"
    if content and not content.endswith("\n\n"):
        content += "\n"
    return content + "\n".join(additions)


def _apply_mise_toml(project_type: str, repo_root: Path) -> bool:
    path = repo_root / "mise.toml"
    named = _named_mise_tasks(project_type, repo_root)
    if not path.exists():
        path.write_text(_generate_mise_toml(project_type, repo_root), encoding="utf-8")
        return True
    original = path.read_text(encoding="utf-8")
    merged = _merge_mise_toml(original, named)
    if merged == original:
        return False
    path.write_text(merged, encoding="utf-8")
    return True


def _generate_mise_toml(project_type: str, repo_root: Path) -> str:
    named = _named_mise_tasks(project_type, repo_root)
    unit = _toml_string(named["unit"])
    integration = _toml_string(named["integration"])
    doctor = _toml_string(named["doctor"])
    e2e_line = ""
    if "e2e" in named:
        e2e_line = f"e2e = {_toml_string(named['e2e'])}\n"
    if project_type == "elixir_phoenix":
        return f"""# Mise configuration for Elixir/Phoenix project
# Scaffolded by /deviate-init — DeviaTDD scaffolding

[tools]
elixir = "latest"
erlang = "latest"

[tasks]
unit = {unit}
integration = {integration}
{e2e_line}test = {{ depends = ["unit"] }}
setup = {{ depends = ["hooks"], run = "mix deps.get && mix deps.compile" }}
lint = "mix credo --strict"
format = "mix format"
format-check = "mix format --check-formatted"
fix = {{ depends = ["format", "lint"] }}
check = {{ depends = ["format-check", "lint", "unit"] }}
pre-commit = {{ depends = ["format-check", "lint"] }}
pre-push = {{ depends = ["unit"] }}
doctor = {doctor}
hooks = "mise generate git-pre-commit --write && mise generate git-pre-commit --hook pre-push --write"
dev = "mix phx.server"
clean = "mix clean && rm -rf _build deps .fetch"
"""
    if project_type == "python":
        dev_cmd = _get_dev_command(project_type, repo_root)
        return f"""# Mise configuration for Python project
# Scaffolded by /deviate-init — DeviaTDD scaffolding

[tools]
python = "3.12"
uv = "latest"

[tasks]
# Runner also accepts `integ` as an alias (_resolve_verification_command).
# Init writes `integration` so `mise integration` works.
# Empty integration: pytest exit 5 (no tests collected) is success. Not || true.
unit = {unit}
integration = {integration}
{e2e_line}test = {{ depends = ["unit"] }}
setup = {{ depends = ["hooks"], run = "uv sync --extra dev" }}
lint = "uv run ruff check"
format = "uv run ruff format"
format-check = "uv run ruff format --check"
fix = {{ depends = ["format", "lint"] }}
check = {{ depends = ["format-check", "lint", "unit"] }}
pre-commit = {{ depends = ["format-check", "lint"] }}
pre-push = {{ depends = ["unit"] }}
doctor = {doctor}
hooks = "mise generate git-pre-commit --write && mise generate git-pre-commit --hook pre-push --write"
dev = "{dev_cmd}"
clean = "rm -rf .venv dist build __pycache__"
"""
    if project_type == "node":
        pkg_manager = _node_pkg_manager(repo_root)
        return f"""# Mise configuration for Node.js project
# Scaffolded by /deviate-init — DeviaTDD scaffolding

[tools]
node = "lts"
{pkg_manager} = "latest"

[tasks]
unit = {unit}
integration = {integration}
{e2e_line}test = {{ depends = ["unit"] }}
setup = {{ depends = ["hooks"], run = "{pkg_manager} install" }}
lint = "{pkg_manager} run lint 2>/dev/null || echo 'No lint configured'"
format = "{pkg_manager} run format 2>/dev/null || echo 'No formatter configured'"
format-check = "{pkg_manager} run format:check 2>/dev/null || echo 'No format check configured'"
fix = {{ depends = ["format", "lint"] }}
check = {{ depends = ["format-check", "lint", "unit"] }}
pre-commit = {{ depends = ["format-check", "lint"] }}
pre-push = {{ depends = ["unit"] }}
doctor = {doctor}
hooks = "mise generate git-pre-commit --write && mise generate git-pre-commit --hook pre-push --write"
dev = "{pkg_manager} run dev 2>/dev/null || {pkg_manager} run start"
clean = "rm -rf node_modules dist build"
"""
    if project_type == "rust":
        return f"""# Mise configuration for Rust project
# Scaffolded by /deviate-init — DeviaTDD scaffolding

[tools]
rust = "stable"

[tasks]
unit = {unit}
integration = {integration}
{e2e_line}test = {{ depends = ["unit"] }}
setup = {{ depends = ["hooks"], run = "cargo fetch" }}
lint = "cargo clippy -- -D warnings"
format = "cargo fmt"
format-check = "cargo fmt --check"
fix = {{ depends = ["format", "lint"] }}
check = {{ depends = ["format-check", "lint", "unit"] }}
pre-commit = {{ depends = ["format-check", "lint"] }}
pre-push = {{ depends = ["unit"] }}
doctor = {doctor}
hooks = "mise generate git-pre-commit --write && mise generate git-pre-commit --hook pre-push --write"
dev = "cargo run"
clean = "cargo clean"
"""
    if project_type == "go":
        return f"""# Mise configuration for Go project
# Scaffolded by /deviate-init — DeviaTDD scaffolding

[tools]
go = "latest"

[tasks]
unit = {unit}
integration = {integration}
{e2e_line}test = {{ depends = ["unit"] }}
setup = {{ depends = ["hooks"], run = "go mod download" }}
lint = "golangci-lint run 2>/dev/null || echo 'No linter configured'"
format = "gofmt -w ."
format-check = "gofmt -l ."
fix = {{ depends = ["format", "lint"] }}
check = {{ depends = ["format-check", "lint", "unit"] }}
pre-commit = {{ depends = ["format-check", "lint"] }}
pre-push = {{ depends = ["unit"] }}
doctor = {doctor}
hooks = "mise generate git-pre-commit --write && mise generate git-pre-commit --hook pre-push --write"
dev = "go run ."
clean = "go clean"
"""
    if project_type == "unknown":
        e2e_block = ""
        if "e2e" in named:
            e2e_block = (
                f"\n[tasks.e2e]\n"
                f"run = {_toml_string(named['e2e'])}\n"
                f'description = "End-to-end tests. Empty stub: pytest exit 5 is success."\n'
            )
        return f"""# Mise configuration for an unclassified project
# Scaffolded by /deviate-init — DeviaTDD scaffolding

[tasks.unit]
run = {unit}
description = "Fast hermetic unit tests"

[tasks.integration]
run = {integration}
description = "Integration tests. Empty stub: pytest exit 5 is success. Runner also accepts integ as an alias."
{e2e_block}
[tasks.test]
depends = ["unit"]
description = "Back-compat alias of unit"

[tasks.doctor]
run = {doctor}
description = "Cheap toolchain check"

[tasks.lint]
run = "ruff check && ruff format --check"
description = "Run the default Python lint checks"

[tasks.format]
run = "ruff format"
description = "Format Python sources"

[tasks.format-check]
run = "ruff format --check"
description = "Check Python formatting"

[tasks.pre-commit]
depends = ["format-check", "lint"]
description = "Commit hook: format-check + lint"

[tasks.pre-push]
depends = ["unit"]
description = "Push hook: unit tests only"
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

    artifacts_created.extend(_ensure_stub_dirs(project_type, repo_root))

    if _apply_mise_toml(project_type, repo_root):
        has_mise_toml = True
        artifacts_created.append("mise.toml")
    else:
        has_mise_toml = (repo_root / "mise.toml").exists()

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
    for rel in (
        Path("tests/unit") / ".gitkeep",
        Path("tests/integration") / ".gitkeep",
        Path("tests/e2e") / ".gitkeep",
        Path("test") / ".gitkeep",
        Path("test/integration") / ".gitkeep",
        Path("test/e2e") / ".gitkeep",
        Path("e2e") / ".gitkeep",
    ):
        if (repo_root / rel).is_file():
            artifacts.append(str(rel))
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
