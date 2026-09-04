from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import typer

from deviate.cli._common import (
    _compute_diff,
    _get_current_branch,
    _resolve_constitution_path,
    _resolve_prd,
    console,
)
from deviate.core.review_coverage import (
    BRIEF_INCOMPLETE,
    brief_has_named_checks,
    evaluate_review_coverage,
    resolve_issue_brief_path,
    resolve_issue_plan_path,
    resolve_review_issue_id,
)
from deviate.state.config import resolve_base_branch

logger = logging.getLogger(__name__)


review_app = typer.Typer(no_args_is_help=True)


@review_app.callback()
def _review_flags(
    ctx: typer.Context,
    apply: bool = typer.Option(
        False,
        "--apply",
        help=(
            "Opt-in: after comments, apply CRITICAL findings only "
            "(security / data loss / broken build / named-check fail with a "
            "concrete FIX). Default is comments only."
        ),
    ),
) -> None:
    """Gate 3 review: comments by default; ``--apply`` is CRITICAL-only."""
    ctx.ensure_object(dict)
    ctx.obj["apply"] = apply


def _apply_enabled(ctx: typer.Context, apply: bool) -> bool:
    return apply or bool((ctx.obj or {}).get("apply"))


def sort_review_comments(comments: list[dict]) -> list[dict]:
    """Sort review comments by token, path, then line (stable)."""
    return sorted(
        comments,
        key=lambda comment: (
            comment.get("token", ""),
            comment.get("path", ""),
            comment.get("line", 0),
        ),
    )


@review_app.command()
def pre(
    ctx: typer.Context,
    base: str | None = typer.Option(
        None, "--base", help="Base branch for merge-base computation"
    ),
    branch: str | None = typer.Option(
        None, "--branch", help="Target branch for self-contained review"
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help=(
            "Opt-in: apply CRITICAL findings only after comments. "
            "Without this flag, print/post comments and stop."
        ),
    ),
) -> None:
    """Gather this-issue brief + diff for Gate 3 review (comments by default)."""
    repo = Path.cwd()
    resolved_base = base or resolve_base_branch(repo)

    target = branch or "HEAD"
    branch_name = branch or _get_current_branch(repo)
    issue_id = resolve_review_issue_id(repo, branch_name)
    brief_path = resolve_issue_brief_path(repo, issue_id)
    plan_path = resolve_issue_plan_path(repo, issue_id)

    if not brief_has_named_checks(repo, issue_id):
        print(BRIEF_INCOMPLETE)
        raise typer.Exit(code=1)

    diff = _compute_diff(repo, resolved_base, target)
    constitution_path = _resolve_constitution_path(repo)
    prd_path, prd_warning = _resolve_prd(branch_name, repo)
    report_exists = _check_existing_reports(repo)
    coverage = evaluate_review_coverage(repo, issue_id)
    apply_on = _apply_enabled(ctx, apply)

    contract = {
        "status": "READY",
        "diff": diff,
        "issue_brief_path": str(brief_path.resolve()) if brief_path else None,
        "plan_path": str(plan_path.resolve()) if plan_path else None,
        "constitution_path": constitution_path,
        "constitution_warning": constitution_path is None,
        "prd_path": prd_path,
        "prd_warning": prd_warning,
        "base_branch": resolved_base,
        "report_exists": report_exists,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uncovered": coverage.uncovered,
        "coverage_complete": coverage.complete,
        "apply": apply_on,
        "apply_scope": "CRITICAL" if apply_on else None,
    }

    print(json.dumps(contract, indent=2))


def _reports_dir(repo: Path) -> Path:
    """Resolve the .deviate/review/reports/ directory path."""
    return repo / ".deviate" / "review" / "reports"


def _check_existing_reports(repo: Path) -> bool:
    """Check if review reports already exist under .deviate/review/reports/."""
    reports_dir = _reports_dir(repo)
    if not reports_dir.is_dir():
        return False
    return any(reports_dir.iterdir())


@review_app.command()
def post(
    content: str | None = typer.Argument(
        None, help="Report markdown content. If not provided, reads from stdin."
    ),
) -> None:
    """Persist comments-only review report. Never applies or commits."""
    if not content:
        if not sys.stdin.isatty():
            content = sys.stdin.read()

    if not content:
        console.print("[yellow]SKIP[/] no report content provided")
        raise typer.Exit(code=0)

    repo = Path.cwd()
    issue_id = resolve_review_issue_id(repo, _get_current_branch(repo))
    if not brief_has_named_checks(repo, issue_id):
        print(BRIEF_INCOMPLETE)
        raise typer.Exit(code=1)

    reports_dir = _reports_dir(repo)
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    report_file = reports_dir / f"review-report-{timestamp}.md"
    report_file.write_text(content, encoding="utf-8")
    console.print(f"[green]OK[/] report written to {report_file}")
