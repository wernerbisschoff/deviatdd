"""``deviate html`` — write a per-phase HTML starter scaffold for the agent.

The CLI does NOT render markdown to HTML. It writes a hand-authored
HTML5 skeleton with empty ``<section>`` placeholders for every expected
phase section. The agent running the phase reads the corresponding
``.md`` file and fills the body in itself — that is the whole point of
moving HTML authorship out of the auto-renderer.

Phases supported: ``architecture``, ``prd``, ``plan``, ``flows``,
``domain-model``. ``deviate html all`` emits the scaffold for every
phase whose ``.html`` sibling is missing.

Usage examples::

    deviate html architecture
    deviate html prd
    deviate html plan                # autodetect issue from current git branch
    deviate html plan --issue ISS-001-03
    deviate html flows --force       # overwrite existing HTML
    deviate html all
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from deviate.cli._common import console, resolve_issue_id_from_branch
from deviate.html_templates import render_starter

html_app = typer.Typer(
    no_args_is_help=True,
    help=(
        "Write a per-phase HTML starter scaffold for the agent to author. "
        "Reads the corresponding .md file's path into the scaffold's "
        "source-of-truth header; the agent fills in the body from the "
        "markdown content. NEVER auto-translates markdown to HTML."
    ),
)


def _specs_root() -> Path:
    """Find the specs root — same convention as the rest of the CLI."""
    return Path("specs")


def _bucket_dir(source_file: str) -> str:
    """Extract the epic bucket slug from a source_file path."""
    from pathlib import PurePosixPath

    return PurePosixPath(source_file).parent.parent.name


def _source_stem(source_file: str) -> str:
    """Extract the issue slug (filename stem) from a source_file path."""
    from pathlib import PurePosixPath

    return PurePosixPath(source_file).stem


def _resolve_plan_md(issue_id: str | None) -> Path:
    """Resolve the ``plan.md`` path for ``issue_id``.

    Resolution order:
    1. ``--issue ISS-NNN-NN`` (explicit)
    2. Active git branch via ``resolve_issue_id_from_branch``
    3. ``.deviate/session.json`` ``active_issue_id``
    4. Hard fail with ``HTML_NO_ISSUE``
    """
    root = Path.cwd()
    resolved_id = issue_id

    if resolved_id is None:
        resolved_id = resolve_issue_id_from_branch(root)

    if resolved_id is None:
        from deviate.state.config import SessionState

        session_path = root / ".deviate" / "session.json"
        if session_path.exists():
            session = SessionState.load(session_path)
            resolved_id = session.active_issue_id or None

    if resolved_id is None:
        console.print(
            "[red]HTML_NO_ISSUE[/] pass --issue ISS-NNN-NN or run from a "
            "feat/<bucket>/<slug> branch with an active session"
        )
        raise typer.Exit(code=1)

    from deviate.state.ledger import resolve_issue_record

    specs_root = _specs_root()
    ledger_path = specs_root / "issues.jsonl"
    record = resolve_issue_record(resolved_id, ledger_path)
    if record is None:
        console.print(f"[red]ISSUE_NOT_FOUND[/] {resolved_id}")
        raise typer.Exit(code=1)

    bucket = _bucket_dir(record.source_file)
    slug = _source_stem(record.source_file)
    plan_md = specs_root / bucket / slug / "plan.md"
    if not plan_md.exists():
        console.print(f"[red]PLAN_NOT_FOUND[/] {plan_md}")
        raise typer.Exit(code=1)
    return plan_md


def _resolve_product_md(filename: str) -> Path:
    """Resolve a product-layer markdown file under ``specs/_product/``."""
    md = _specs_root() / "_product" / filename
    if not md.exists():
        console.print(f"[red]HTML_NO_SOURCE[/] {md} — write the markdown first")
        raise typer.Exit(code=1)
    return md


def _resolve_prd_md() -> Path:
    """Resolve the unique ``prd.md`` under the specs root (single-epic)."""
    # Only numbered epic dirs (e.g. ``001-deviate-cli-python``) own a
    # ``prd.md``. Other top-level dirs under ``specs/`` carry unrelated
    # artifacts (``adhoc/`` is the shared adhoc ledger,
    # ``_product/`` is the product layer, ``explore/`` is the
    # pre-numbered discovery scratchpad).
    candidates = sorted(
        p for p in _specs_root().glob("*/prd.md") if p.parent.name[:3].isdigit()
    )
    if not candidates:
        console.print("[red]HTML_NO_PRD[/] no */prd.md under specs/")
        raise typer.Exit(code=1)
    if len(candidates) > 1:
        names = ", ".join(p.parent.name for p in candidates)
        console.print(
            f"[red]HTML_AMBIGUOUS_PRD[/] multiple prd.md candidates: {names}. "
            "Disambiguate by removing extras or running from the epic dir."
        )
        raise typer.Exit(code=1)
    return candidates[0]


def _write_html(md_path: Path, phase: str, *, force: bool) -> Path:
    """Write the starter scaffold next to ``md_path``."""
    html_path = md_path.with_suffix(".html")
    if html_path.exists() and not force:
        console.print(f"[red]HTML_EXISTS[/] {html_path} — pass --force to overwrite")
        raise typer.Exit(code=1)
    html_path.write_text(render_starter(phase, md_path), encoding="utf-8")
    console.print(f"[green]WROTE[/] {html_path}")
    return html_path


@html_app.command("architecture")
def html_architecture(
    force: Annotated[bool, typer.Option(help="Overwrite existing HTML")] = False,
) -> None:
    """Write ``specs/_product/architecture.html`` starter scaffold."""
    _write_html(_resolve_product_md("architecture.md"), "architecture", force=force)


@html_app.command("prd")
def html_prd(
    force: Annotated[bool, typer.Option(help="Overwrite existing HTML")] = False,
) -> None:
    """Write the active epic's ``prd.html`` starter scaffold."""
    _write_html(_resolve_prd_md(), "prd", force=force)


@html_app.command("plan")
def html_plan(
    issue_id: Annotated[
        str | None,
        typer.Option(
            "--issue",
            "-i",
            help="Issue ID (e.g. ISS-001-03). Autodetects from the active git branch.",
        ),
    ] = None,
    force: Annotated[bool, typer.Option(help="Overwrite existing HTML")] = False,
) -> None:
    """Write the plan's ``plan.html`` starter scaffold."""
    _write_html(_resolve_plan_md(issue_id), "plan", force=force)


@html_app.command("flows")
def html_flows(
    force: Annotated[bool, typer.Option(help="Overwrite existing HTML")] = False,
) -> None:
    """Write ``specs/_product/flows/index.html`` starter scaffold."""
    flows_md = _specs_root() / "_product" / "flows" / "index.md"
    if not flows_md.exists():
        console.print(f"[red]HTML_NO_SOURCE[/] {flows_md} — write the index first")
        raise typer.Exit(code=1)
    _write_html(flows_md, "flows", force=force)


@html_app.command("domain-model")
def html_domain_model(
    force: Annotated[bool, typer.Option(help="Overwrite existing HTML")] = False,
) -> None:
    """Write ``specs/_product/domain-model.html`` starter scaffold."""
    _write_html(_resolve_product_md("domain-model.md"), "domain-model", force=force)


@html_app.command("all")
def html_all(
    force: Annotated[bool, typer.Option(help="Overwrite existing HTML")] = False,
) -> None:
    """Emit the starter scaffold for every phase whose HTML is missing."""
    written: list[Path] = []
    skipped: list[Path] = []

    def _try_write(md: Path, phase: str) -> None:
        if not md.exists():
            return
        html = md.with_suffix(".html")
        if html.exists() and not force:
            skipped.append(html)
            return
        html.write_text(render_starter(phase, md), encoding="utf-8")
        written.append(html)
        console.print(f"[green]WROTE[/] {html}")

    specs_root = _specs_root()
    product = specs_root / "_product"
    _try_write(product / "architecture.md", "architecture")
    _try_write(product / "domain-model.md", "domain-model")
    _try_write(product / "flows" / "index.md", "flows")
    for prd_md in sorted(specs_root.glob("*/prd.md")):
        if prd_md.parent.name == "_product":
            continue
        _try_write(prd_md, "prd")
    plan_md = None
    try:
        plan_md = _resolve_plan_md(None)
    except (SystemExit, typer.Exit):
        # ``typer.Exit`` does not inherit ``SystemExit`` on Typer 0.12+;
        # either signals "no plan.md to scaffold", which we treat as
        # best-effort skip in the ``all`` aggregator.
        plan_md = None
    if plan_md is not None:
        _try_write(plan_md, "plan")

    if not written and not skipped:
        console.print("[yellow]HTML_NO_TARGETS[/] no source markdown to scaffold")
        return
    if skipped:
        names = ", ".join(str(p) for p in skipped)
        console.print(
            f"[yellow]HTML_SKIPPED[/] existing HTML (pass --force to overwrite): {names}"
        )


__all__ = ["html_app"]
