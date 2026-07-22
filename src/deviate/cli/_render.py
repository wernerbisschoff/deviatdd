"""``deviate render`` — manual HTML rendering for spec files.

The post-commit hooks (``_plan_post`` / ``prd_post``) render HTML automatically
when the corresponding ``.md`` changes. Flow files (``flows/index.md`` and
``flows-<domain>.md``) are authored through the ``/deviate-flows`` slash
command and committed externally — they have no post-hook. ``deviate render``
is the manual escape hatch for those files (and for re-rendering after a CSS
update).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from deviate.cli._common import console
from deviate.core.specs_html import (
    find_flow_files,
    render_html,
    render_spec_set,
)

render_app = typer.Typer(
    no_args_is_help=True,
    help=(
        "Render spec markdown files to standalone HTML. Use after editing "
        "flow files (flows/*.md) or to refresh HTML output after a CSS "
        "update. Plan and PRD files render automatically via their post "
        "hooks; this command is the manual escape hatch."
    ),
)


def _resolve_specs_root() -> Path:
    """Find the specs root — same logic as the rest of the CLI."""
    from deviate.cli.macro import _resolve_specs_root as _macro_resolve

    return _macro_resolve()


@render_app.command("plan")
def render_plan(
    issue_id: Annotated[
        str,
        typer.Option(
            "--issue",
            "-i",
            help="Issue ID (e.g. ISS-001-03). Defaults to the session's active issue.",
        ),
    ]
    | None = None,
) -> None:
    """Render plan.md for the active issue to plan.html (no commit)."""
    if issue_id is None:
        console.print("[red]NO_ISSUE[/] pass --issue ISS-NNN-NN")
        raise typer.Exit(code=1)
    specs_root = _resolve_specs_root()
    # Resolve to <bucket>/<slug>/plan.md via the issue ledger.
    from deviate.state.ledger import resolve_issue_record

    record = resolve_issue_record(issue_id, specs_root / "issues.jsonl")
    if record is None:
        console.print(f"[red]ISSUE_NOT_FOUND[/] {issue_id}")
        raise typer.Exit(code=1)
    bucket_dir = Path(record.source_file).parent.parent
    plan_md = bucket_dir / "plan.md"
    if not plan_md.exists():
        console.print(f"[red]PLAN_NOT_FOUND[/] {plan_md}")
        raise typer.Exit(code=1)
    html_path = render_html(plan_md, plan_md.with_suffix(".html"))
    console.print(f"[cyan]HTML_PREVIEW[/] {html_path}")


@render_app.command("prd")
def render_prd(
    epic: Annotated[
        str,
        typer.Option(
            "--epic",
            "-e",
            help="Epic slug (e.g. 001-deviate-cli-python).",
        ),
    ],
) -> None:
    """Render prd.md for an epic to prd.html (no commit)."""
    specs_root = _resolve_specs_root()
    prd_md = specs_root / epic / "prd.md"
    if not prd_md.exists():
        console.print(f"[red]PRD_NOT_FOUND[/] {prd_md}")
        raise typer.Exit(code=1)
    html_path = render_html(prd_md, prd_md.with_suffix(".html"))
    console.print(f"[cyan]HTML_PREVIEW[/] {html_path}")


@render_app.command("flows")
def render_flows() -> None:
    """Render every file under specs/_product/flows/ to sibling HTML (no commit)."""
    specs_root = _resolve_specs_root()
    flow_files = find_flow_files(specs_root)
    if not flow_files:
        console.print(
            f"[yellow]NO_FLOW_FILES[/] no markdown under {specs_root / '_product' / 'flows'}"
        )
        raise typer.Exit(code=1)
    written = render_spec_set(flow_files)
    for path in written:
        console.print(f"[cyan]HTML_PREVIEW[/] {path}")


@render_app.command("all")
def render_all() -> None:
    """Render plan + prd + flows for the current worktree (no commit).

    Convenience entry point: re-render every spec artifact that may have a
    corresponding HTML preview. Useful after a ``specs.css`` update.
    """
    specs_root = _resolve_specs_root()
    written: list[Path] = []

    # Flow files (always two-level: <specs_root>/_product/flows/<file>.md).
    flow_files = find_flow_files(specs_root)
    if flow_files:
        written.extend(render_spec_set(flow_files))

    # PRDs (one-level: <specs_root>/<epic_slug>/prd.md).
    for prd_md in sorted(specs_root.glob("*/prd.md")):
        written.append(render_html(prd_md, prd_md.with_suffix(".html")))

    # Plans (two-level: <specs_root>/<bucket>/<slug>/plan.md).
    for plan_md in sorted(specs_root.glob("*/*/plan.md")):
        written.append(render_html(plan_md, plan_md.with_suffix(".html")))

    if not written:
        console.print("[yellow]NO_SPECS[/] no plan.md, prd.md, or flows found")
        return
    for path in written:
        console.print(f"[cyan]HTML_PREVIEW[/] {path}")
