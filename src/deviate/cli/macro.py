from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import typer

from deviate.cli._common import (
    _handle_missing_dot_dir,
    _handle_transition_error,
    console,
)
from deviate.core.commit import commit_artifact
from deviate.core.constitution import resolve_constitution, validate_constitution
from deviate.core.epic import (
    allocate_feature_bucket,
    discover_epic,
    resolve_active_feature,
)
from deviate.core.prd import extract_prd_requirements
from deviate.state.config import SessionState, TransitionViolationError
from deviate.state.ledger import IssueRecord, append_issue_record


def _load_and_transition(phase: str) -> tuple[SessionState, Path]:
    dot_dir = Path(".deviate")
    if not dot_dir.exists():
        _handle_missing_dot_dir(phase)
    session_path = dot_dir / "session.json"
    session = SessionState.load(session_path)
    try:
        session = session.transition_to(phase)
    except TransitionViolationError as e:
        _handle_transition_error(phase, e)
    return session, session_path


def _load_session(phase: str) -> tuple[SessionState, Path]:
    dot_dir = Path(".deviate")
    if not dot_dir.exists():
        _handle_missing_dot_dir(phase)
    session_path = dot_dir / "session.json"
    session = SessionState.load(session_path)
    if session.current_phase != phase:
        console.print(
            f"[red]{phase}_HALTED: session is in '{session.current_phase}' not '{phase}'[/]"
        )
        raise typer.Exit(code=1)
    return session, session_path


def _save_session(session: SessionState, session_path: Path, phase: str) -> None:
    session.save(session_path)
    console.print(f"[green]{phase}[/] session advanced to {phase} phase")


def _resolve_specs_root() -> Path:
    return Path("specs")


# ---------------------------------------------------------------------------
# Explore
# ---------------------------------------------------------------------------

explore_app = typer.Typer(no_args_is_help=True, help="Explore phase commands")


@explore_app.command("pre")
def explore_pre(
    problem: str = typer.Argument(..., help="Problem description"),
    slug: str = typer.Option(..., "--slug", help="Feature bucket slug"),
) -> None:
    """Allocate feature bucket and register scratch entry"""
    try:
        const_path = resolve_constitution(Path.cwd())
        if not validate_constitution(const_path):
            console.print("[red]EXPLORE_HALTED: constitution validation failed[/]")
            raise typer.Exit(code=1)
    except FileNotFoundError:
        console.print("[red]EXPLORE_HALTED: constitution.md not found[/]")
        raise typer.Exit(code=1)

    session, session_path = _load_and_transition("EXPLORE")

    bucket = allocate_feature_bucket(slug)
    console.print(f"[green]BUCKET_CREATED[/] {bucket}")

    record = IssueRecord(
        issue_id=str(uuid.uuid4()),
        type="feature",
        title=problem,
        status="DRAFT",
        source_file=f"specs/{slug}/explore.md",
        timestamp=datetime.now(timezone.utc),
    )
    ledger_path = Path("specs") / "issues.jsonl"
    appended = append_issue_record(record, ledger_path)
    if appended:
        console.print(f"[green]LEDGER_APPENDED[/] {record.issue_id}")
    else:
        console.print(
            f"[yellow]LEDGER_IDEMPOTENT[/] record for {record.issue_id} already exists"
        )

    contract = {
        "problem": problem,
        "slug": slug,
        "bucket_path": str(bucket),
        "issue_id": record.issue_id,
        "phase": "EXPLORE",
    }
    console.print(json.dumps(contract, indent=2))

    _save_session(session, session_path, "EXPLORE")


@explore_app.command("post")
def explore_post() -> None:
    """Validate explore.md and commit"""
    session, session_path = _load_session("EXPLORE")

    explore_files = list(Path("specs").rglob("explore.md"))
    if not explore_files:
        console.print("[red]EXPLORE_HALTED: no explore.md found to commit[/]")
        raise typer.Exit(code=1)

    for f in explore_files:
        if f.read_text(encoding="utf-8").strip():
            commit_artifact(f, f"EXPLORE: {f.parent.name}", repo=Path.cwd())
            console.print(f"[green]COMMITTED[/] {f}")

    _save_session(session, session_path, "EXPLORE")


# ---------------------------------------------------------------------------
# Research
# ---------------------------------------------------------------------------

research_app = typer.Typer(no_args_is_help=True, help="Research phase commands")


@research_app.command("pre")
def research_pre(
    epic: str = typer.Argument("", help="Epic slug"),
) -> None:
    """Gate on explore.md, validate constitution"""
    specs_root = _resolve_specs_root()
    epic_slug = epic if epic else resolve_active_feature(specs_root)
    if not epic_slug:
        console.print("[red]RESEARCH_HALTED: no active feature bucket found[/]")
        raise typer.Exit(code=1)

    explore_path = specs_root / epic_slug / "explore.md"
    if not explore_path.exists():
        console.print("[red]RESEARCH_HALTED: explore.md not found in feature bucket[/]")
        raise typer.Exit(code=1)

    try:
        const_path = resolve_constitution(Path.cwd())
        if not validate_constitution(const_path):
            console.print("[red]RESEARCH_HALTED: constitution validation failed[/]")
            raise typer.Exit(code=1)
    except FileNotFoundError:
        console.print("[red]RESEARCH_HALTED: constitution.md not found[/]")
        raise typer.Exit(code=1)

    session, session_path = _load_and_transition("RESEARCH")

    contract = {
        "epic_slug": epic_slug,
        "explore_path": str(explore_path),
        "phase": "RESEARCH",
    }
    console.print(json.dumps(contract, indent=2))

    _save_session(session, session_path, "RESEARCH")


@research_app.command("post")
def research_post() -> None:
    """Scan for constitutional violations, commit artifacts"""
    session, session_path = _load_session("RESEARCH")

    specs_root = _resolve_specs_root()
    epic_slug = resolve_active_feature(specs_root)
    if epic_slug:
        for artifact in ("design.md", "data-model.md"):
            path = specs_root / epic_slug / artifact
            if path.exists() and path.read_text(encoding="utf-8").strip():
                commit_artifact(
                    path, f"RESEARCH: {artifact} for {epic_slug}", repo=Path.cwd()
                )
                console.print(f"[green]COMMITTED[/] {path}")

    _save_session(session, session_path, "RESEARCH")


# ---------------------------------------------------------------------------
# PRD
# ---------------------------------------------------------------------------

prd_app = typer.Typer(no_args_is_help=True, help="PRD phase commands")


@prd_app.command("pre")
def prd_pre() -> None:
    """Discover epic slug, resolve upstream artifacts"""
    specs_root = _resolve_specs_root()
    epic_slug = discover_epic(specs_root)
    if not epic_slug:
        console.print("[red]PRD_HALTED: no epic discovered[/]")
        raise typer.Exit(code=1)

    required = ["design.md", "data-model.md"]
    missing = [a for a in required if not (specs_root / epic_slug / a).exists()]
    if missing:
        paths = "\n  - ".join(str(specs_root / epic_slug / a) for a in missing)
        console.print(f"[red]PRD_HALTED: missing upstream artifacts\n  - {paths}[/]")
        raise typer.Exit(code=1)

    session, session_path = _load_and_transition("PRD")

    contract = {
        "epic_slug": epic_slug,
        "phase": "PRD",
    }
    console.print(json.dumps(contract, indent=2))

    _save_session(session, session_path, "PRD")


@prd_app.command("post")
def prd_post(
    manifest: Path = typer.Argument(..., help="Path to manifest JSON file"),
) -> None:
    """Read manifest, validate PRD, commit"""
    session, session_path = _load_session("PRD")

    try:
        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError) as e:
        console.print(f"[red]PRD_HALTED: invalid manifest - {e}[/]")
        raise typer.Exit(code=1)

    epic_slug = manifest_data.get("epic_slug", "")
    if not epic_slug:
        console.print("[red]PRD_HALTED: manifest missing 'epic_slug'[/]")
        raise typer.Exit(code=1)

    prd_path = _resolve_specs_root() / epic_slug / "prd.md"
    if not prd_path.exists():
        console.print(f"[red]PRD_HALTED: prd.md not found at {prd_path}[/]")
        raise typer.Exit(code=1)

    reqs = extract_prd_requirements(prd_path)
    manifest_reqs = manifest_data.get("prd_requirements", [])
    missing = [r for r in manifest_reqs if r not in reqs]
    if missing:
        console.print(
            f"[yellow]PRD_WARNING[/] missing requirements in prd.md: {missing}"
        )

    try:
        sha = commit_artifact(prd_path, f"PRD: {epic_slug}", repo=Path.cwd())
        console.print(f"[green]COMMITTED[/] prd.md at {sha[:8]}")
    except Exception as e:
        console.print(f"[red]PRD_HALTED: commit failed - {e}[/]")
        raise typer.Exit(code=1)

    _save_session(session, session_path, "PRD")


# ---------------------------------------------------------------------------
# Shard
# ---------------------------------------------------------------------------

shard_app = typer.Typer(no_args_is_help=True, help="Shard phase commands")


@shard_app.command("pre")
def shard_pre() -> None:
    """Discover epic, resolve PRD, compute next_issue_id"""
    specs_root = _resolve_specs_root()
    epic_slug = discover_epic(specs_root)
    if not epic_slug:
        console.print("[red]SHARD_HALTED: no epic discovered[/]")
        raise typer.Exit(code=1)

    prd_path = specs_root / epic_slug / "prd.md"
    if not prd_path.exists():
        console.print(f"[red]SHARD_HALTED: prd.md not found at {prd_path}[/]")
        raise typer.Exit(code=1)

    ledger_path = Path("specs") / "issues.jsonl"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    existing = (
        ledger_path.read_text(encoding="utf-8").strip() if ledger_path.exists() else ""
    )
    next_num = 1
    if existing:
        numbers = []
        for line in existing.splitlines():
            if line.strip():
                try:
                    data = json.loads(line)
                    iid = data.get("issue_id", "")
                    if iid.startswith("ISS-"):
                        numbers.append(int(iid.split("-")[1]))
                except (json.JSONDecodeError, ValueError):
                    continue
        next_num = (max(numbers) + 1) if numbers else 1
    next_issue_id = f"ISS-{next_num:03d}"

    session, session_path = _load_and_transition("SHARD")

    contract = {
        "epic_slug": epic_slug,
        "prd_path": str(prd_path),
        "next_issue_id": next_issue_id,
        "phase": "SHARD",
    }
    console.print(json.dumps(contract, indent=2))

    _save_session(session, session_path, "SHARD")


@shard_app.command("post")
def shard_post(
    manifest: Path = typer.Argument(..., help="Path to shard manifest JSON file"),
) -> None:
    """Validate shard output, register issues as BACKLOG, reset session to IDLE"""
    session, session_path = _load_session("SHARD")

    try:
        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError) as e:
        console.print(f"[red]SHARD_HALTED: invalid manifest - {e}[/]")
        raise typer.Exit(code=1)

    issues = manifest_data.get("issues", [])
    ledger_path = Path("specs") / "issues.jsonl"

    for issue_data in issues:
        record = IssueRecord(
            issue_id=issue_data.get("issue_id", str(uuid.uuid4())),
            type=issue_data.get("type", "feature"),
            title=issue_data.get("title", ""),
            status="BACKLOG",
            source_file=issue_data.get("source_file", ""),
            timestamp=datetime.now(timezone.utc),
        )
        appended = append_issue_record(record, ledger_path)
        if appended:
            console.print(
                f"[green]LEDGER_APPENDED[/] {record.issue_id} ({record.title})"
            )
        else:
            console.print(
                f"[yellow]LEDGER_IDEMPOTENT[/] {record.issue_id} already exists"
            )

    try:
        session = session.transition_to("IDLE")
    except TransitionViolationError as e:
        _handle_transition_error("SHARD", e)

    session.save(session_path)
    console.print("[green]SHARD_POST[/] session reset to IDLE")
