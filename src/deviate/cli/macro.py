from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import typer

from deviate.cli._common import (
    _halt,
    _handle_missing_dot_dir,
    _handle_transition_error,
    _load_manifest,
    _validate_constitution,
    console,
)
from deviate.core._shared import git_env as _git_env
from deviate.core.commit import commit_artifact
from deviate.core.constitution import extract_commands, resolve_constitution
from deviate.core.epic import (
    allocate_feature_bucket,
    discover_epic,
    resolve_active_feature,
)
from deviate.core.prd import extract_prd_requirements
from deviate.core.repo import find_repo_root
from deviate.state.config import SessionState, TransitionViolationError
from deviate.state.ledger import IssueRecord, _read_ledger, append_issue_record


def _load_and_transition(phase: str) -> tuple[SessionState, Path]:
    dot_dir = Path(".deviate")
    if not dot_dir.exists():
        _handle_missing_dot_dir(phase)
    session_path = dot_dir / "session.json"
    if not session_path.exists():
        session = SessionState.reconstruct_from_worktree(Path.cwd())
        session.save(session_path)
    else:
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
    if not session_path.exists():
        session = SessionState.reconstruct_from_worktree(Path.cwd())
        session.save(session_path)
    else:
        session = SessionState.load(session_path)
    if session.current_phase != phase:
        _halt(phase, f"session is in '{session.current_phase}' not '{phase}'")
    return session, session_path


def _save_session(session: SessionState, session_path: Path, phase: str) -> None:
    session.save(session_path)
    console.print(f"[green]{phase}[/] session advanced to {phase} phase")


def _resolve_specs_root() -> Path:
    return Path("specs")


def _resolve_repo_context() -> dict:
    try:
        repo_root = find_repo_root()
    except ValueError:
        repo_root = Path.cwd()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()
    except Exception:
        branch = "detached"
    return {
        "repo_root": str(repo_root.resolve()),
        "git_branch": branch,
    }


def _resolve_constitution_commands() -> dict:
    try:
        repo_root = find_repo_root()
        const_path = resolve_constitution(repo_root)
        commands = extract_commands(const_path)
        return {
            "constitution_path": str(const_path),
            "test_cmd": commands.get("test_command", ""),
            "lint_cmd": commands.get("lint_command", ""),
            "type_check_cmd": commands.get("type_check_command", ""),
        }
    except (FileNotFoundError, ValueError):
        return {
            "constitution_path": "",
            "test_cmd": "",
            "lint_cmd": "",
            "type_check_cmd": "",
        }


def _emit_contract(
    phase: str,
    session: SessionState,
    session_path: Path,
    **extra: str | int | bool | None,
) -> None:
    repo_ctx = _resolve_repo_context()
    const_cmds = _resolve_constitution_commands()
    contract = {
        **repo_ctx,
        **const_cmds,
        "status": "READY",
        "phase": phase,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **extra,
    }
    print(json.dumps(contract, indent=2))
    _save_session(session, session_path, phase)


def _compute_next_issue_id(ledger_path: Path) -> str:
    records = _read_ledger(ledger_path)
    numbers: list[int] = []
    for data in records:
        iid = data.get("issue_id", "")
        if isinstance(iid, str) and iid.startswith("ISS-"):
            try:
                numbers.append(int(iid.split("-")[1]))
            except (ValueError, IndexError):
                continue
    next_num = (max(numbers) + 1) if numbers else 1
    return f"ISS-{next_num:03d}"


# ---------------------------------------------------------------------------
# Explore
# ---------------------------------------------------------------------------

explore_app = typer.Typer(no_args_is_help=True, help="Explore phase commands")


@explore_app.command("pre")
def explore_pre(
    problem: str = typer.Argument(..., help="Problem description"),
    slug: str | None = typer.Option(None, "--slug", help="Feature bucket slug"),
) -> None:
    """Allocate feature bucket and register scratch entry"""
    _validate_constitution("EXPLORE")

    session, session_path = _load_and_transition("EXPLORE")

    specs_root = _resolve_specs_root()
    bucket_path = specs_root / slug if slug else None
    is_greenfield = not (bucket_path and bucket_path.exists())

    bucket = allocate_feature_bucket(slug)
    console.print(f"[green]BUCKET_CREATED[/] {bucket}")

    record = IssueRecord(
        issue_id=str(uuid.uuid4()),
        type="feature",
        title=problem,
        status="DRAFT",
        source_file=str(bucket / "explore.md"),
        timestamp=datetime.now(timezone.utc),
    )
    ledger_path = specs_root / "issues.jsonl"
    appended = append_issue_record(record, ledger_path)
    if appended:
        console.print(f"[green]LEDGER_APPENDED[/] {record.issue_id}")
    else:
        console.print(
            f"[yellow]LEDGER_IDEMPOTENT[/] record for {record.issue_id} already exists"
        )

    _emit_contract(
        "EXPLORE",
        session,
        session_path,
        epic_id=slug or "",
        is_greenfield=is_greenfield,
        feature_bucket=slug,
        feature_dir=str(bucket),
        explore_path=str(bucket / "explore.md"),
        problem=problem,
        slug=slug,
        bucket_path=str(bucket),
        issue_id=record.issue_id,
    )


@explore_app.command("post")
def explore_post() -> None:
    """Validate explore.md and commit"""
    session, session_path = _load_session("EXPLORE")

    specs_root = _resolve_specs_root()
    epic_slug = resolve_active_feature(specs_root)
    if not epic_slug:
        _halt("EXPLORE", "no active feature bucket found")

    explore_path = specs_root / epic_slug / "explore.md"
    if not explore_path.exists():
        _halt("EXPLORE", f"explore.md not found at {explore_path}")

    content = explore_path.read_text(encoding="utf-8")
    if not content.strip():
        _halt("EXPLORE", "explore.md is empty")

    commit_artifact(
        explore_path, f"EXPLORE: {explore_path.parent.name}", repo=Path.cwd()
    )
    console.print(f"[green]COMMITTED[/] {explore_path}")

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
        _halt("RESEARCH", "no active feature bucket found")

    explore_path = specs_root / epic_slug / "explore.md"
    if not explore_path.exists():
        _halt("RESEARCH", "explore.md not found in feature bucket")

    _validate_constitution("RESEARCH")

    session, session_path = _load_and_transition("RESEARCH")

    feature_dir = specs_root / epic_slug
    is_greenfield = not feature_dir.exists()

    _emit_contract(
        "RESEARCH",
        session,
        session_path,
        is_greenfield=is_greenfield,
        issue_id="",
        feature_bucket=epic_slug,
        explore_path=str(explore_path),
        design_target=str(feature_dir / "design.md"),
        data_model_target=str(feature_dir / "data-model.md"),
        epic_slug=epic_slug,
    )


@research_app.command("post")
def research_post() -> None:
    """Scan for constitutional violations, commit artifacts"""
    session, session_path = _load_session("RESEARCH")

    _validate_constitution("RESEARCH")

    specs_root = _resolve_specs_root()
    epic_slug = resolve_active_feature(specs_root)
    if not epic_slug:
        _halt("RESEARCH", "no active feature bucket found")

    for artifact in ("design.md", "data-model.md"):
        path = specs_root / epic_slug / artifact
        if not path.exists():
            _halt("RESEARCH", f"{artifact} not found in {epic_slug}")
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            _halt("RESEARCH", f"{artifact} is empty")
        commit_artifact(path, f"RESEARCH: {artifact} for {epic_slug}", repo=Path.cwd())
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
        _halt("PRD", "no epic discovered")

    required = ["design.md", "data-model.md"]
    missing = [a for a in required if not (specs_root / epic_slug / a).exists()]
    if missing:
        paths = "\n  - ".join(str(specs_root / epic_slug / a) for a in missing)
        _halt("PRD", f"missing upstream artifacts\n  - {paths}")

    session, session_path = _load_and_transition("PRD")

    _emit_contract("PRD", session, session_path, epic_slug=epic_slug)


@prd_app.command("post")
def prd_post(
    manifest: Path = typer.Argument(..., help="Path to manifest JSON file"),
) -> None:
    """Read manifest, validate PRD, commit"""
    session, session_path = _load_session("PRD")

    manifest_data = _load_manifest(manifest, "PRD")

    epic_slug = manifest_data.get("epic_slug", "")
    if not epic_slug:
        _halt("PRD", "manifest missing 'epic_slug'")

    prd_path = _resolve_specs_root() / epic_slug / "prd.md"
    if not prd_path.exists():
        _halt("PRD", f"prd.md not found at {prd_path}")

    prd_content = prd_path.read_text(encoding="utf-8")
    _REQUIRED_PRD_SECTIONS = [
        "DOCUMENT_CONTROL_AND_METADATA",
        "SYSTEM_OBJECTIVES_AND_SCOPE_BOUNDARY",
        "ARCHITECTURAL_CONSTRAINTS_AND_PREREQUISITES",
        "FUNCTIONAL_FLOW_AND_SEQUENCE_ARCHITECTURE",
        "FUNCTIONAL_REQUIREMENTS_AND_EPICS",
        "GITHUB_ISSUE_SHARDING_STRATEGY",
    ]
    missing_sections = [s for s in _REQUIRED_PRD_SECTIONS if s not in prd_content]
    if missing_sections:
        sections_str = ", ".join(missing_sections)
        console.print(
            f"[yellow]PRD_WARNING[/] missing required sections: {sections_str}"
        )

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
        _halt("PRD", f"commit failed - {e}")

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
        _halt("SHARD", "no epic discovered")

    prd_path = specs_root / epic_slug / "prd.md"
    if not prd_path.exists():
        _halt("SHARD", f"prd.md not found at {prd_path}")

    ledger_path = _resolve_specs_root() / "issues.jsonl"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    next_issue_id = _compute_next_issue_id(ledger_path)

    session, session_path = _load_and_transition("SHARD")

    _emit_contract(
        "SHARD",
        session,
        session_path,
        epic_slug=epic_slug,
        prd_path=str(prd_path),
        next_issue_id=next_issue_id,
    )


@shard_app.command("post")
def shard_post(
    manifest: Path = typer.Argument(..., help="Path to shard manifest JSON file"),
) -> None:
    """Validate shard output, register issues as BACKLOG, reset session to IDLE"""
    session, session_path = _load_session("SHARD")

    manifest_data = _load_manifest(manifest, "SHARD")

    issues = manifest_data.get("issues", [])
    ledger_path = _resolve_specs_root() / "issues.jsonl"

    epic_slug = manifest_data.get("epic_slug", "")
    if epic_slug:
        bucket_root = _resolve_specs_root() / epic_slug
        for shard_artifact in ("spec.md", "tasks.md"):
            art_path = bucket_root / shard_artifact
            if art_path.exists():
                art_content = art_path.read_text(encoding="utf-8")
                if not art_content.strip():
                    console.print(f"[yellow]SHARD_WARNING[/] {shard_artifact} is empty")
                elif not art_content.startswith("---"):
                    console.print(
                        f"[yellow]SHARD_WARNING[/] missing YAML frontmatter in {shard_artifact}"
                    )
            else:
                console.print(
                    f"[yellow]SHARD_WARNING[/] {shard_artifact} not found in {epic_slug}"
                )

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
