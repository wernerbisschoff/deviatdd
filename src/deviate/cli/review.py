from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

from deviate.cli._common import console
from deviate.core._shared import git_env as _git_env
from deviate.core.treesitter import ast_diff_files, get_file_at_revision

review_app = typer.Typer(no_args_is_help=True)

_EXCLUDED_RE = re.compile(
    r"\.(min\.(js|css)|lock|png|jpg|gif|woff|ttf|ico|svg|eot|woff2|pyc|pyo)$"
    r"|^(dist/|build/|node_modules/|vendor/|third_party/|\.worktrees/|\.opencode/|\.git/)"
)


def _git_run(
    args: list[str], repo: Path, check: bool = True
) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=_git_env(),
        capture_output=True,
        text=True,
        check=check,
    )


def _get_current_branch(repo: Path) -> str:
    try:
        return _git_run(["rev-parse", "--abbrev-ref", "HEAD"], repo).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _compute_merge_base(commit_a: str, commit_b: str, repo: Path) -> str:
    try:
        return _git_run(["merge-base", commit_a, commit_b], repo).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _gather_git_state(repo: Path) -> dict[str, Any]:
    """Return staged, unstaged, untracked file info as JSON-serializable dict."""
    staged = _git_run(["diff", "--cached", "--name-only"], repo).stdout.splitlines()
    unstaged = _git_run(["diff", "--name-only"], repo).stdout.splitlines()
    untracked = _git_run(
        ["ls-files", "--others", "--exclude-standard"], repo
    ).stdout.splitlines()

    def to_json(lines: list[str]) -> list[str]:
        return [line for line in lines if line]

    return {
        "staged": to_json(staged),
        "unstaged": to_json(unstaged),
        "untracked": to_json(untracked),
    }


def _build_filtered_file_list(files: list[str]) -> list[str]:
    """Filter out generated, binary, vendor files."""
    result: list[str] = []
    for f in files:
        if not _EXCLUDED_RE.search(f):
            result.append(f)
    return sorted(set(result))


def _categorize_files(files: list[str]) -> dict[str, int]:
    categories: dict[str, int] = {
        "core": 0,
        "tests": 0,
        "specs": 0,
        "config": 0,
        "prompts": 0,
        "other": 0,
    }
    for f in files:
        if f.startswith("src/"):
            categories["core"] += 1
        elif f.startswith("tests/"):
            categories["tests"] += 1
        elif f.startswith("specs/"):
            categories["specs"] += 1
        elif re.match(r"^\.(gitignore|editorconfig|env|mise|deviate)", f):
            categories["config"] += 1
        elif "prompts/" in f:
            categories["prompts"] += 1
        else:
            categories["other"] += 1
    return categories


def _resolve_constitution_path(repo: Path) -> str | None:
    path = repo / "specs" / "constitution.md"
    return str(path.resolve()) if path.exists() else None


def _resolve_prd(branch_name: str, repo: Path) -> tuple[str | None, bool]:
    epic_slug = None
    parts = branch_name.split("/")
    if len(parts) > 1:
        epic_slug = parts[1]

    if epic_slug:
        epic_prd = repo / "specs" / epic_slug / "prd.md"
        if epic_prd.exists():
            return str(epic_prd.resolve()), False

    adhoc_prd = repo / "specs" / "adhoc" / "prd.md"
    if adhoc_prd.exists():
        return str(adhoc_prd.resolve()), False

    return None, True


def _resolve_branch_artifacts(branch_name: str, repo: Path) -> dict[str, str | None]:
    """Resolve spec/tasks/prd/design/data-model from branch name."""
    artifacts: dict[str, str | None] = {
        "spec_path": None,
        "tasks_path": None,
        "prd_path": None,
        "design_path": None,
        "data_model_path": None,
    }
    branch_stripped = (
        branch_name.split("/", 1)[-1] if "/" in branch_name else branch_name
    )

    parts = branch_stripped.split("/")
    if len(parts) >= 2:
        epic, issue = parts[0], parts[1]
        base = repo / "specs" / epic
        spec = base / issue / "spec.md"
        tasks = base / issue / "tasks.md"
        prd = base / "prd.md"
        design = base / "design.md"
        data_model = base / "data-model.md"
        if spec.exists():
            artifacts["spec_path"] = str(spec.resolve())
        if tasks.exists():
            artifacts["tasks_path"] = str(tasks.resolve())
        if prd.exists():
            artifacts["prd_path"] = str(prd.resolve())
        if design.exists():
            artifacts["design_path"] = str(design.resolve())
        if data_model.exists():
            artifacts["data_model_path"] = str(data_model.resolve())
    elif len(parts) == 1 and parts[0]:
        epic = parts[0]
        base = repo / "specs" / epic
        prd = base / "prd.md"
        design = base / "design.md"
        data_model = base / "data-model.md"
        spec = base / "spec.md"
        if prd.exists():
            artifacts["prd_path"] = str(prd.resolve())
        if design.exists():
            artifacts["design_path"] = str(design.resolve())
        if data_model.exists():
            artifacts["data_model_path"] = str(data_model.resolve())
        if spec.exists():
            artifacts["spec_path"] = str(spec.resolve())

    return artifacts


def _compute_review_strategy(filtered_count: int, total_diff_size: int) -> str:
    if filtered_count > 15 or total_diff_size > 20000:
        return "targeted"
    elif filtered_count > 5 or total_diff_size > 5000:
        return "diff_first"
    return "full"


def _compute_ast_diff(
    repo: Path, merge_base: str, base: str, target: str
) -> dict[str, Any]:
    """Compute AST structural diff between merge_base and target for changed .py files."""
    diff_output = _git_run(
        ["diff", "--name-only", f"{merge_base}..{target}"], repo
    ).stdout
    changed_files = [f for f in diff_output.splitlines() if f.endswith(".py")]

    file_diffs: list[dict[str, Any]] = []
    summary: dict[str, int] = {
        "functions_added": 0,
        "functions_removed": 0,
        "signatures_changed": 0,
        "classes_added": 0,
        "complexity_warnings": 0,
        "dead_functions": 0,
        "total_files_analyzed": 0,
    }

    for filepath in changed_files:
        old_source = get_file_at_revision(repo, merge_base, filepath) or ""
        try:
            new_source = (repo / filepath).read_text(encoding="utf-8")
        except FileNotFoundError:
            new_source = ""

        if not old_source and not new_source:
            continue

        diff = ast_diff_files(old_source, new_source, filepath=filepath)
        file_diffs.append(diff)
        summary["functions_added"] += len(diff.get("functions_added", []))
        summary["functions_removed"] += len(diff.get("functions_removed", []))
        summary["signatures_changed"] += len(diff.get("functions_modified", []))
        summary["classes_added"] += len(diff.get("classes_added", []))
        summary["complexity_warnings"] += len(diff.get("complexity_warnings", []))
        summary["dead_functions"] += len(diff.get("dead_functions", []))
        summary["total_files_analyzed"] += 1

    return {"files": file_diffs, "summary": summary}


def _format_ast_diff_markdown(ast_diff: dict[str, Any]) -> str:
    """Format AST diff as compact markdown for the review agent."""
    lines = ["## Structural Diff\n"]
    summary = ast_diff.get("summary", {})
    total = summary.get("total_files_analyzed", 0)
    if total == 0:
        lines.append("No Python files changed — no structural diff available.\n")
        return "\n".join(lines)

    lines.append(f"**{total} Python file(s)** analyzed via tree-sitter AST parsing.\n")

    s = summary
    parts = []
    if s.get("functions_added"):
        parts.append(f"+{s['functions_added']} functions")
    if s.get("functions_removed"):
        parts.append(f"-{s['functions_removed']} functions")
    if s.get("signatures_changed"):
        parts.append(f"~{s['signatures_changed']} signatures")
    if s.get("classes_added"):
        parts.append(f"+{s['classes_added']} classes")
    if s.get("complexity_warnings"):
        parts.append(f"⚠ {s['complexity_warnings']} complexity warnings")
    if s.get("dead_functions"):
        parts.append(f"✗ {s['dead_functions']} potentially dead functions")
    if parts:
        lines.append(f"**Delta:** {' | '.join(parts)}\n")

    for fd in ast_diff.get("files", []):
        fp = fd.get("file", "?")
        ct = fd.get("change_type", "modified")
        lines.append(f"### `{fp}` ({ct})")

        added = fd.get("functions_added", [])
        removed = fd.get("functions_removed", [])
        modified = fd.get("functions_modified", [])
        classes_added = fd.get("classes_added", [])
        classes_removed = fd.get("classes_removed", [])
        classes_modified = fd.get("classes_modified", [])
        imports_added = fd.get("imports_added", [])
        imports_removed = fd.get("imports_removed", [])
        warnings = fd.get("complexity_warnings", [])
        dead = fd.get("dead_functions", [])

        if added:
            lines.append(
                f"- **Added functions:** {', '.join(a['name'] for a in added)}"
            )
        if removed:
            lines.append(
                f"- **Removed functions:** {', '.join(r['name'] for r in removed)}"
            )
        if modified:
            lines.append(
                f"- **Modified functions:** {' | '.join(m['name'] for m in modified)}"
            )
            for m in modified:
                lines.append(f"  - `{m['old_signature']}` → `{m['new_signature']}`")
        if classes_added:
            lines.append(
                f"- **Added classes:** {', '.join(c['name'] for c in classes_added)}"
            )
        if classes_removed:
            lines.append(
                f"- **Removed classes:** {', '.join(c['name'] for c in classes_removed)}"
            )
        if classes_modified:
            for cm in classes_modified:
                ma = cm.get("methods_added", [])
                mr = cm.get("methods_removed", [])
                desc = f"{cm['name']}"
                if ma:
                    desc += f" (+{', '.join(ma)})"
                if mr:
                    desc += f" (-{', '.join(mr)})"
                lines.append(f"- **Modified class:** {desc}")
        if imports_added:
            lines.append(f"- **Imports added:** {len(imports_added)}")
        if imports_removed:
            lines.append(f"- **Imports removed:** {len(imports_removed)}")
        if warnings:
            for w in warnings:
                fn = w.get("function", "?")
                cc = w.get("complexity", 0)
                ln = w.get("lines", 0)
                reason = w.get("reason", "warning")
                lines.append(f"- ⚠ `{fn}` — {reason} (CC={cc}, lines={ln})")
        if dead:
            lines.append(f"- ✗ **Potentially dead:** {', '.join(dead)}")
        if not any(
            [
                added,
                removed,
                modified,
                classes_added,
                classes_removed,
                classes_modified,
                imports_added,
                imports_removed,
                warnings,
                dead,
            ]
        ):
            lines.append("- No structural changes detected.\n")
        lines.append("")

    return "\n".join(lines)


@review_app.command()
def pre(
    base: str = typer.Option(
        "main", "--base", help="Base branch for merge-base computation"
    ),
    branch: str | None = typer.Option(
        None, "--branch", help="Target branch for self-contained review"
    ),
) -> None:
    """Gather git state, governance context, and AST structural diff for review."""
    repo = Path.cwd()

    target = branch or "HEAD"
    branch_name = branch or _get_current_branch(repo)

    # Gather git state
    git_state = _gather_git_state(repo)
    merge_base = _compute_merge_base(base, target, repo)

    staged_files = git_state["staged"]
    unstaged_files = git_state["unstaged"]
    untracked_files = git_state["untracked"]
    wt_changes = len(staged_files) + len(unstaged_files) + len(untracked_files)

    # Determine if ahead of base
    ahead_of_main = bool(merge_base)
    if ahead_of_main:
        try:
            _git_run(["diff", "--quiet", f"{merge_base}..{target}"], repo, check=True)
            ahead_of_main = False
        except subprocess.CalledProcessError:
            ahead_of_main = True

    # Commits ahead of merge-base
    branch_commit_count = 0
    branch_files: list[str] = []
    if ahead_of_main and merge_base:
        branch_commit_count_str = _git_run(
            ["rev-list", "--count", f"{merge_base}..{target}"], repo
        ).stdout.strip()
        branch_commit_count = (
            int(branch_commit_count_str) if branch_commit_count_str else 0
        )
        branch_files_raw = _git_run(
            ["diff", "--name-only", f"{merge_base}..{target}"], repo
        ).stdout
        branch_files = [f for f in branch_files_raw.splitlines() if f]

    # Build combined filtered file list
    all_raw = list(set(staged_files + unstaged_files + untracked_files + branch_files))
    filtered = _build_filtered_file_list(all_raw)
    categories = _categorize_files(filtered)

    # Review strategy
    total_diff_size = 0
    branch_diff_raw = ""
    if ahead_of_main and merge_base:
        branch_diff_raw = _git_run(
            ["diff", f"{merge_base}..{target}"], repo, check=False
        ).stdout
        total_diff_size = len(branch_diff_raw.splitlines())
    staged_diff_raw = _git_run(["diff", "--cached"], repo, check=False).stdout
    unstaged_diff_raw = _git_run(["diff"], repo, check=False).stdout
    total_diff_size += len(staged_diff_raw.splitlines())
    total_diff_size += len(unstaged_diff_raw.splitlines())

    review_strategy = _compute_review_strategy(len(filtered), total_diff_size)

    # Governance file resolution
    constitution_path = _resolve_constitution_path(repo)
    prd_path, prd_warning = _resolve_prd(branch_name, repo)
    branch_artifacts = _resolve_branch_artifacts(branch_name, repo)

    # Create temp dir for artifacts
    temp_dir = Path(tempfile.mkdtemp(prefix="deviate-review-"))
    metadata_path = temp_dir / ".review-metadata"
    metadata_path.write_text(f"TEMP_DIR={temp_dir}\n", encoding="utf-8")

    diff_path = temp_dir / "DIFF"
    staged_diff_path = temp_dir / "STAGED_DIFF"
    unstaged_diff_path = temp_dir / "UNSTAGED_DIFF"
    branch_diff_path = temp_dir / "BRANCH_DIFF"
    stat_path = temp_dir / "STAT"
    recent_commits_path = temp_dir / "RECENT_COMMITS"
    changed_files_path = temp_dir / "CHANGED_FILES"
    ast_diff_path = temp_dir / "AST_DIFF.md"

    # Write diff files
    staged_diff_path.write_text(staged_diff_raw, encoding="utf-8")
    unstaged_diff_path.write_text(unstaged_diff_raw, encoding="utf-8")
    if branch_diff_raw:
        branch_diff_path.write_text(branch_diff_raw, encoding="utf-8")
    combined_diff = f"{branch_diff_raw}\n{staged_diff_raw}\n{unstaged_diff_raw}"
    diff_path.write_text(combined_diff, encoding="utf-8")

    # Write stat
    stat_parts: list[str] = []
    if ahead_of_main and merge_base:
        stat_parts.append(
            _git_run(
                ["diff", f"{merge_base}..{target}", "--stat"], repo, check=False
            ).stdout
        )
    stat_parts.append(
        _git_run(["diff", "--cached", "--stat"], repo, check=False).stdout
    )
    stat_parts.append(_git_run(["diff", "--stat"], repo, check=False).stdout)
    stat_path.write_text("\n".join(stat_parts), encoding="utf-8")

    # Write recent commits
    if ahead_of_main and merge_base:
        commits = _git_run(
            ["--no-pager", "log", "--oneline", "--decorate", f"{merge_base}..{target}"],
            repo,
            check=False,
        ).stdout
    else:
        commits = _git_run(
            ["--no-pager", "log", "--oneline", "--decorate", "-10"],
            repo,
            check=False,
        ).stdout
    recent_commits_path.write_text(commits, encoding="utf-8")

    # Write changed files list
    all_changed = sorted(set(branch_files + staged_files + unstaged_files))
    changed_files_path.write_text("\n".join(all_changed) + "\n", encoding="utf-8")

    # AST structural diff
    ast_diff_result: dict[str, Any] = {"files": [], "summary": {}}
    if merge_base and ahead_of_main:
        ast_diff_result = _compute_ast_diff(repo, merge_base, base, target)
    ast_diff_markdown = _format_ast_diff_markdown(ast_diff_result)
    ast_diff_path.write_text(ast_diff_markdown, encoding="utf-8")

    # Existing reports check
    reports_dir = repo / ".deviate" / "review" / "reports"
    report_exists = reports_dir.is_dir() and any(reports_dir.iterdir())

    contract: dict[str, Any] = {
        "status": "READY",
        "phase": "review",
        "branch": branch_name,
        "repo_root": str(repo.resolve()),
        "has_changes": wt_changes > 0 or ahead_of_main,
        "files": {
            "staged": staged_files,
            "staged_count": len(staged_files),
            "unstaged": unstaged_files,
            "unstaged_count": len(unstaged_files),
            "untracked": untracked_files,
            "untracked_count": len(untracked_files),
            "wt_changes": wt_changes,
            "ahead_files": branch_files,
            "ahead_count": len(branch_files),
            "branch_commit_count": branch_commit_count,
            "filtered": filtered,
            "filtered_count": len(filtered),
            "review_strategy": review_strategy,
            "categories": categories,
        },
        "scope": {
            "is_feature_branch": branch_name
            not in ("main", "master", "HEAD", "unknown"),
            "ahead_of_main": ahead_of_main,
            "merge_base": merge_base,
        },
        "governance": {
            "constitution_found": constitution_path is not None,
            "constitution_path": constitution_path,
            "prd_found": prd_path is not None,
            "prd_path": prd_path,
            "prd_warning": prd_warning,
            "spec_found": branch_artifacts.get("spec_path") is not None,
            "spec_path": branch_artifacts.get("spec_path"),
            "tasks_path": branch_artifacts.get("tasks_path"),
            "design_found": branch_artifacts.get("design_path") is not None,
            "design_path": branch_artifacts.get("design_path"),
            "data_model_found": branch_artifacts.get("data_model_path") is not None,
            "data_model_path": branch_artifacts.get("data_model_path"),
        },
        "diff_path": str(diff_path.resolve()),
        "staged_diff_path": str(staged_diff_path.resolve()),
        "unstaged_diff_path": str(unstaged_diff_path.resolve()),
        "branch_diff_path": str(branch_diff_path.resolve())
        if branch_diff_raw
        else None,
        "changed_files_path": str(changed_files_path.resolve()),
        "staged_diff_size": len(staged_diff_raw.splitlines()),
        "unstaged_diff_size": len(unstaged_diff_raw.splitlines()),
        "branch_diff_size": len(branch_diff_raw.splitlines()) if branch_diff_raw else 0,
        "total_diff_size": total_diff_size,
        "stat_path": str(stat_path.resolve()),
        "recent_commits_path": str(recent_commits_path.resolve()),
        "metadata_path": str(metadata_path.resolve()),
        "ast_diff_path": str(ast_diff_path.resolve()),
        "ast_diff_summary": ast_diff_result.get("summary", {}),
        "report_exists": report_exists,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print(json.dumps(contract, indent=2, default=str))


def _reports_dir(repo: Path) -> Path:
    return repo / ".deviate" / "review" / "reports"


@review_app.command()
def post(
    content: str | None = typer.Argument(
        None, help="Report markdown content. If not provided, reads from stdin."
    ),
) -> None:
    """Persist review report and mark review complete."""
    if not content:
        if not sys.stdin.isatty():
            content = sys.stdin.read()

    if not content:
        console.print("[yellow]SKIP[/] no report content provided")
        raise typer.Exit(code=0)

    repo = Path.cwd()
    reports_dir = _reports_dir(repo)
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    report_file = reports_dir / f"review-report-{timestamp}.md"
    report_file.write_text(content, encoding="utf-8")
    console.print(f"[green]OK[/] report written to {report_file}")
