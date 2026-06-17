from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import typer

from deviate.cli._common import (
    _extract_epic_num,
    _halt,
    _handle_missing_dot_dir,
    _load_manifest,
    _run_pre_commit_hooks,
    _validate_constitution,
    console,
    with_json_quiet,
)
from deviate.core._shared import git_env as _git_env
from deviate.core.agent import AgentBackend, AgentSubprocessError
from deviate.core.commit import commit_artifact, stage_and_commit
from deviate.prompts.assembly import assemble_prompt
from deviate.core.constitution import extract_commands, resolve_constitution
from deviate.cli.feature import _derive_slug
from deviate.core.epic import (
    allocate_feature_bucket,
    discover_latest_epic,
    resolve_active_feature,
)
from deviate.core.prd import extract_prd_requirements
from deviate.core.repo import find_repo_root
from deviate.core.validation import (
    ARTIFACT_VALIDATORS,
    extract_section_body,
    validate_artifact,
    validate_sections,
    validate_yaml_frontmatter,
)
from deviate.state.config import SessionState, resolve_model_for_phase
from deviate.state.ledger import IssueRecord, _read_ledger, append_issue_record


def _load_or_create_session(phase: str) -> tuple[SessionState, Path]:
    dot_dir = Path(".deviate")
    if not dot_dir.exists():
        _handle_missing_dot_dir(phase)
    session_path = dot_dir / "session.json"
    if not session_path.exists():
        session = SessionState.reconstruct_from_worktree(Path.cwd())
        session.save(session_path)
    else:
        session = SessionState.load(session_path)
    return session, session_path


def _load_and_transition(phase: str) -> tuple[SessionState, Path]:
    session, session_path = _load_or_create_session(phase)
    session = session.transition_to(phase)
    return session, session_path


def _load_session_accept(
    *phases: str, force: bool = False
) -> tuple[SessionState, Path]:
    """Load session, accepting any phase — state is purely descriptive."""
    phase_tag = phases[0] if phases else "?"
    session, session_path = _load_or_create_session(phase_tag)
    return session, session_path


def _load_session(phase: str) -> tuple[SessionState, Path]:
    session, session_path = _load_or_create_session(phase)
    return session, session_path


def _save_session(session: SessionState, session_path: Path, phase: str) -> None:
    session.save(session_path)
    console.print(f"[green]{phase}[/] session advanced to {phase} phase")


def _load_session_for_phase(
    phase: str, dry_run: bool = False
) -> tuple[SessionState, Path]:
    if dry_run:
        console.print("[yellow]DRY_RUN[/] skipping phase transition")
        dot_dir = Path(".deviate")
        session_path = dot_dir / "session.json"
        session = SessionState.load(session_path)
        return session, session_path
    session, session_path = _load_or_create_session(phase)
    session = session.transition_to(phase)
    return session, session_path


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
    except subprocess.CalledProcessError:
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
        test_cmd = commands.get("test_command", "")
        lint_cmd = commands.get("lint_command", "")
        type_check_cmd = commands.get("type_check_command", "")
        const_path_str = str(const_path)
    except (FileNotFoundError, ValueError):
        const_path_str = ""
        test_cmd = ""
        lint_cmd = ""
        type_check_cmd = ""
    return {
        "constitution_path": const_path_str,
        "test_cmd": test_cmd,
        "lint_cmd": lint_cmd,
        "type_check_cmd": type_check_cmd,
        "test_command": test_cmd,
        "lint_command": lint_cmd,
        "type_check_command": type_check_cmd,
        "constitution_test_command": test_cmd,
        "constitution_lint_command": lint_cmd,
    }


def _emit_contract(
    phase: str,
    session: SessionState,
    session_path: Path,
    dry_run: bool = False,
    **extra: str | int | bool | None,
) -> None:
    repo_ctx = _resolve_repo_context()
    const_cmds = _resolve_constitution_commands()
    contract = {
        **repo_ctx,
        **const_cmds,
        "status": "DRY_RUN" if dry_run else "READY",
        "phase": phase,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        **extra,
    }
    print(json.dumps(contract, indent=2))
    if not dry_run:
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
@with_json_quiet
def explore_pre(
    problem: str = typer.Argument(..., help="Problem description"),
    slug: str | None = typer.Option(None, "--slug", help="Feature bucket slug"),
) -> None:
    """Allocate feature bucket and register scratch entry"""
    _validate_constitution("EXPLORE")

    session, session_path = _load_and_transition("EXPLORE")

    specs_root = _resolve_specs_root()
    final_slug = slug or _derive_slug(problem)
    bucket_path = specs_root / final_slug if final_slug else None
    is_greenfield = not (bucket_path and bucket_path.exists())

    bucket = allocate_feature_bucket(final_slug)
    console.print(f"[green]BUCKET_CREATED[/] {bucket}")

    spec_target_rel = str(bucket / "explore.md")
    spec_target_abs = str((bucket / "explore.md").resolve())

    _emit_contract(
        "EXPLORE",
        session,
        session_path,
        epic_id=final_slug or "",
        is_greenfield=is_greenfield,
        feature_slug=final_slug,
        feature_dir=str(bucket),
        specs_directory=str(specs_root),
        spec_target=spec_target_rel,
        spec_target_abs=spec_target_abs,
        feature_bucket=final_slug,
        explore_path=str(bucket / "explore.md"),
        problem=problem,
        slug=final_slug,
        bucket_path=str(bucket),
        issue_id="",
    )


@explore_app.command("post")
def explore_post(
    epic: str | None = typer.Option(
        None, "--epic", help="Epic slug (e.g. 003-prompt-optimization)"
    ),
    force: bool = typer.Option(False, "--force", help="Bypass phase validation"),
) -> None:
    """Validate explore.md and commit"""
    session, session_path = _load_session_accept("EXPLORE", force=force)

    specs_root = _resolve_specs_root()
    epic_slug = epic or discover_latest_epic(specs_root)
    if not epic_slug:
        _halt("EXPLORE", "no active feature bucket found")

    explore_path = specs_root / epic_slug / "explore.md"
    if not explore_path.exists():
        _halt("EXPLORE", f"explore.md not found at {explore_path}")

    content = explore_path.read_text(encoding="utf-8")
    if not content.strip():
        _halt("EXPLORE", "explore.md is empty")

    result = validate_artifact(content, "explore")
    if not result.passed:
        _halt("EXPLORE", f"missing required sections: {', '.join(result.errors)}")

    _run_pre_commit_hooks()

    epic_num = _extract_epic_num(explore_path.parent.name)
    commit_artifact(
        explore_path, f"docs({epic_num}): create explore.md", repo=Path.cwd()
    )
    console.print(f"[green]COMMITTED[/] {explore_path}")

    _save_session(session, session_path, "EXPLORE")


# ---------------------------------------------------------------------------
# Research
# ---------------------------------------------------------------------------

research_app = typer.Typer(no_args_is_help=True, help="Research phase commands")


@research_app.command("pre")
@with_json_quiet
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

    issues_ledger = str(specs_root / "issues.jsonl")
    explore_md_abs = str(explore_path.resolve())
    explore_md_rel = str(explore_path)
    design_target_abs = str((feature_dir / "design.md").resolve())
    data_model_target_abs = str((feature_dir / "data-model.md").resolve())

    _emit_contract(
        "RESEARCH",
        session,
        session_path,
        is_greenfield=is_greenfield,
        epic_id=epic_slug,
        feature_slug=epic_slug,
        feature_dir=str(feature_dir),
        specs_directory=str(specs_root),
        explore_md_path=explore_md_abs,
        explore_md_rel=explore_md_rel,
        design_target=str(feature_dir / "design.md"),
        design_target_abs=design_target_abs,
        data_model_target=str(feature_dir / "data-model.md"),
        data_model_target_abs=data_model_target_abs,
        issues_ledger=issues_ledger,
        issue_id="",
        feature_bucket=epic_slug,
        explore_path=str(explore_path),
        epic_slug=epic_slug,
    )


@research_app.command("post")
def research_post(
    epic: str | None = typer.Option(
        None, "--epic", help="Epic slug (e.g. 003-prompt-optimization)"
    ),
    force: bool = typer.Option(False, "--force", help="Bypass phase validation"),
) -> None:
    """Validate research artifacts and create a single commit for all"""
    session, session_path = _load_session_accept("RESEARCH", force=force)

    _validate_constitution("RESEARCH")

    specs_root = _resolve_specs_root()
    epic_slug = epic or resolve_active_feature(specs_root)
    if not epic_slug:
        _halt("RESEARCH", "no active feature bucket found")

    artifacts: list[Path] = []
    for artifact, atype in (
        ("design.md", "design"),
        ("data-model.md", "data_model"),
    ):
        path = specs_root / epic_slug / artifact
        if not path.exists():
            _halt("RESEARCH", f"{artifact} not found in {epic_slug}")
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            _halt("RESEARCH", f"{artifact} is empty")
        result = validate_artifact(content, atype)
        if not result.passed:
            _halt(
                "RESEARCH", f"{artifact} missing sections: {', '.join(result.errors)}"
            )
        artifacts.append(path)

    # Include constitution.md if it was created/modified (greenfield bootstrap)
    const_path = resolve_constitution(Path.cwd())
    if const_path and const_path.exists():
        artifacts.append(const_path)

    _run_pre_commit_hooks()

    epic_num = _extract_epic_num(epic_slug)
    message = f"docs({epic_num}): add research artifacts (design.md, data-model.md)"
    sha = stage_and_commit(message=message, files=artifacts, repo=Path.cwd())
    console.print(f"[green]COMMITTED[/] research artifacts at {sha[:8]}")

    _save_session(session, session_path, "RESEARCH")


# ---------------------------------------------------------------------------
# PRD
# ---------------------------------------------------------------------------


def _check_pending_hitl_decisions(design_path: Path) -> list[str]:
    """Check design.md for unresolved HITL decisions.

    Returns a list of pending decision descriptions. If empty, Gate 1 is clear.
    """
    if not design_path.exists():
        # Let the existence check above handle this
        return []

    content = design_path.read_text(encoding="utf-8")
    section_body = extract_section_body(content, "Pending HITL Decisions")
    if not section_body:
        # Section missing — the ARTIFACT_VALIDATORS check will catch this
        # during research_post; treat as clear for PRD to proceed
        return []

    import re

    pending_rows: list[str] = []
    for line in section_body.splitlines():
        line = line.strip()
        # Match table data rows: starts with | and ends with | PENDING |
        if line.startswith("|") and re.search(r"\|\s*PENDING\s*\|", line):
            # Extract the Decision ID column (first cell after opening pipe)
            parts = [p.strip() for p in line.split("|")]
            decision_id = parts[1] if len(parts) > 1 else "?"
            pending_rows.append(decision_id)
    return pending_rows


prd_app = typer.Typer(no_args_is_help=True, help="PRD phase commands")


@prd_app.command("pre")
@with_json_quiet
def prd_pre(
    epic: str | None = typer.Option(
        None, "--epic", help="Epic slug (e.g. 003-prompt-optimization)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview contract without side effects"
    ),
) -> None:
    """Discover epic slug, resolve upstream artifacts"""
    specs_root = _resolve_specs_root()
    epic_slug = epic or discover_latest_epic(specs_root)
    if not epic_slug:
        _halt("PRD", "no epic discovered")
    epic_dir = specs_root / epic_slug

    required = ["design.md", "data-model.md"]
    missing = [a for a in required if not (epic_dir / a).exists()]
    if missing:
        paths = "\n  - ".join(str(specs_root / epic_slug / a) for a in missing)
        _halt("PRD", f"missing upstream artifacts\n  - {paths}")

    design_path = epic_dir / "design.md"
    pending = _check_pending_hitl_decisions(design_path)
    if pending:
        console.print("[red]HITL GATE 1 — UNRESOLVED DECISIONS[/]")
        console.print(
            "The following items in `## Pending HITL Decisions` require human resolution:"
        )
        for item in pending:
            console.print(f"  [yellow]•[/] {item}")
        console.print()
        console.print(
            "Edit design.md to resolve each item (set Status to `RESOLVED`), then re-run."
        )
        _halt("PRD", "HITL Gate 1 not passed — pending decisions exist")

    session, session_path = _load_session_for_phase("PRD", dry_run=dry_run)

    artifacts_dir = Path(".deviate") / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    _emit_contract(
        "PRD",
        session,
        session_path,
        dry_run=dry_run,
        epic_slug=epic_slug,
        feature_bucket=epic_slug,
        design_path=str(epic_dir / "design.md"),
        data_model_path=str(epic_dir / "data-model.md"),
        plan_target=str(artifacts_dir / "manifest_prd.json"),
        issue_id=session.active_issue_id or "",
    )


@prd_app.command("post")
def prd_post(
    manifest: Path = typer.Argument(..., help="Path to manifest JSON file"),
    force: bool = typer.Option(False, "--force", help="Bypass phase validation"),
) -> None:
    """Read manifest, validate PRD, commit"""
    session, session_path = _load_session_accept("PRD", force=force)

    manifest_data = _load_manifest(manifest, "PRD")

    epic_slug = manifest_data.get("epic_slug", "")
    if not epic_slug:
        _halt("PRD", "manifest missing 'epic_slug'")

    prd_path = _resolve_specs_root() / epic_slug / "prd.md"
    if not prd_path.exists():
        _halt("PRD", f"prd.md not found at {prd_path}")

    prd_content = prd_path.read_text(encoding="utf-8")
    prd_required = ARTIFACT_VALIDATORS.get("prd", [])
    missing_sections = validate_sections(prd_content, prd_required)
    if missing_sections:
        console.print(
            f"[yellow]PRD_WARNING[/] missing required sections: {', '.join(missing_sections)}"
        )

    reqs = extract_prd_requirements(prd_path)
    manifest_reqs = manifest_data.get("prd_requirements", [])
    missing = [r for r in manifest_reqs if r not in reqs]
    if missing:
        console.print(
            f"[yellow]PRD_WARNING[/] missing requirements in prd.md: {missing}"
        )

    _run_pre_commit_hooks()

    try:
        epic_num = _extract_epic_num(epic_slug)
        sha = commit_artifact(
            prd_path, f"docs({epic_num}): create prd.md", repo=Path.cwd()
        )
        console.print(f"[green]COMMITTED[/] prd.md at {sha[:8]}")
    except Exception as e:
        _halt("PRD", f"commit failed - {e}")

    _save_session(session, session_path, "PRD")


# ---------------------------------------------------------------------------
# Shard
# ---------------------------------------------------------------------------

shard_app = typer.Typer(no_args_is_help=True, help="Shard phase commands")


@shard_app.command("pre")
@with_json_quiet
def shard_pre(
    epic: str | None = typer.Option(
        None, "--epic", help="Epic slug (e.g. 002-deviatdd-gap-analysis)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview contract without side effects"
    ),
) -> None:
    """Discover epic, resolve PRD, compute next_issue_id"""
    specs_root = _resolve_specs_root()
    epic_slug = epic or discover_latest_epic(specs_root)
    if not epic_slug:
        _halt("SHARD", "no epic discovered")

    prd_path = specs_root / epic_slug / "prd.md"
    if not prd_path.exists():
        _halt("SHARD", f"prd.md not found at {prd_path}")

    ledger_path = _resolve_specs_root() / "issues.jsonl"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    next_issue_id = _compute_next_issue_id(ledger_path)

    session, session_path = _load_session_for_phase("SHARD", dry_run=dry_run)

    epic_path = specs_root / epic_slug
    issues_dir = epic_path / "issues"
    shard_count = len(list(issues_dir.glob("*.md"))) if issues_dir.exists() else 0

    artifacts_dir = Path(".deviate") / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    _emit_contract(
        "SHARD",
        session,
        session_path,
        dry_run=dry_run,
        epic_slug=epic_slug,
        prd_path=str(prd_path),
        next_issue_id=next_issue_id,
        issues_dir=str(issues_dir),
        plan_target=str(artifacts_dir / "manifest_shard.json"),
        issue_id=session.active_issue_id or "",
        shard_count=shard_count,
    )


@shard_app.command("post")
def shard_post(
    manifest: Path = typer.Argument(..., help="Path to shard manifest JSON file"),
    epic: str | None = typer.Option(
        None, "--epic", help="Override epic slug from manifest"
    ),
    force: bool = typer.Option(False, "--force", help="Bypass phase validation"),
) -> None:
    """Validate shard output, register issues as BACKLOG, reset session to IDLE"""
    session, session_path = _load_session_accept("SHARD", force=force)

    manifest_data = _load_manifest(manifest, "SHARD")

    issues = manifest_data.get("issues", [])
    ledger_path = _resolve_specs_root() / "issues.jsonl"

    epic_slug = epic or manifest_data.get("epic_slug", "")
    if epic_slug:
        issues_dir = _resolve_specs_root() / epic_slug / "issues"
        if issues_dir.exists():
            for shard_file in sorted(issues_dir.glob("*-*.md")):
                shard_content = shard_file.read_text(encoding="utf-8")
                if not shard_content.strip():
                    console.print(
                        f"[yellow]SHARD_WARNING[/] {shard_file.name} is empty"
                    )
                elif not validate_yaml_frontmatter(shard_content):
                    console.print(
                        f"[yellow]SHARD_WARNING[/] invalid YAML frontmatter in {shard_file.name}"
                    )

    for issue_data in issues:
        record = IssueRecord(
            issue_id=issue_data.get("issue_id", str(uuid.uuid4())),
            type=issue_data.get("type", "feature"),
            title=issue_data.get("title", ""),
            status="BACKLOG",
            source_file=issue_data.get("source_file", ""),
            blocked_by=issue_data.get("blocked_by", []),
            coordinates_with=issue_data.get("coordinates_with", []),
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

    _run_pre_commit_hooks()

    session = session.transition_to("IDLE")
    session.save(session_path)
    console.print("[green]SHARD_POST[/] session reset to IDLE")


# ---------------------------------------------------------------------------
# Macro automated pipeline helpers
# ---------------------------------------------------------------------------


def _build_slim_prompt(phase: str, contract: dict[str, str]) -> str:
    repo_root = Path.cwd()
    constitution_path = repo_root / "specs" / "constitution.md"
    return assemble_prompt(
        template_name=phase,
        context=contract,
        constitution_path=constitution_path,
    )


def _invoke_agent_phase(phase: str, contract: dict[str, str]) -> None:
    prompt = _build_slim_prompt(phase, contract)
    backend = AgentBackend()
    try:
        root = Path.cwd()
        model = resolve_model_for_phase(phase, root)
        manifest = backend.invoke(prompt, model=model)
    except AgentSubprocessError as e:
        _halt(phase.upper(), str(e))
    if manifest.status != "PASS":
        _halt(phase.upper(), f"agent returned status: {manifest.status}")


_PHASE_ORDER = ["explore", "research", "prd", "shard"]


def _macro_discover_bucket(target: str | None) -> str:
    specs_root = _resolve_specs_root()
    if target:
        bucket_path = specs_root / target
        if not bucket_path.exists():
            _halt("MACRO", f"BUCKET_NOT_FOUND: '{target}' not found in specs/")
        return target
    return discover_latest_epic(specs_root) or ""


def _dry_run_phases(phases: list[str], resolved: str) -> None:
    """Emit contracts and prompts for each phase without side effects."""
    console.print("[bold][yellow]DRY_RUN[/] — no state will be mutated[/]")
    for phase in phases:
        contract: dict[str, str] = {"phase": phase, "target": resolved}
        print(json.dumps(contract, indent=2))
        prompt = _build_slim_prompt(phase, contract)
        print(prompt)


def _cycle_phase(
    phase: str, resolved: str, specs_root: Path, force: bool = False
) -> None:
    """Execute a single macro phase: upstream check, pre, agent, post."""
    if phase == "research" and not (specs_root / resolved / "explore.md").exists():
        _halt("RESEARCH", "UPSTREAM_MISSING: explore.md not found")

    if phase == "explore":
        _explore_pre(problem=f"Automated explore for {resolved}", slug=resolved)
    elif phase == "research":
        _research_pre(epic=resolved)
    elif phase == "prd":
        _prd_pre()
    elif phase == "shard":
        _shard_pre(epic=resolved)

    agent_contract: dict[str, str] = {"phase": phase, "target": resolved}
    _invoke_agent_phase(phase, agent_contract)

    if phase == "explore":
        _explore_post(force=force)
    elif phase == "research":
        _research_post(force=force)
    elif phase == "prd":
        manifest_path = Path(".deviate") / "artifacts" / "manifest_prd.json"
        if not manifest_path.exists():
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps({"epic_slug": resolved, "phase": "prd", "status": "PASS"}),
            )
        _prd_post(manifest=manifest_path, force=force)
    elif phase == "shard":
        manifest_path = Path(".deviate") / "artifacts" / "manifest_shard.json"
        if not manifest_path.exists():
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "epic_slug": resolved,
                        "phase": "shard",
                        "status": "PASS",
                        "issues": [],
                    },
                ),
            )
        _shard_post(manifest=manifest_path, epic=resolved, force=force)


def _macro_run(
    target: str | None = None,
    from_phase: str | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    if from_phase and from_phase not in _PHASE_ORDER:
        valid = ", ".join(_PHASE_ORDER)
        _halt("MACRO", f"INVALID_PHASE: '{from_phase}'. Valid phases: {valid}")

    resolved = _macro_discover_bucket(target)
    if not resolved:
        _halt("MACRO", "no epic discovered")

    start_idx = _PHASE_ORDER.index(from_phase) if from_phase else 0
    phases = _PHASE_ORDER[start_idx:]

    if from_phase:
        session_path = Path(".deviate") / "session.json"
        session = SessionState.load(session_path)
        preceding_states = {
            "explore": "IDLE",
            "research": "EXPLORE",
            "prd": "RESEARCH",
            "shard": "PRD",
        }
        required_preceding = preceding_states[from_phase]
        if session.current_phase != required_preceding:
            session = session.force_transition_to(required_preceding)
            session.save(session_path)

    if dry_run:
        _dry_run_phases(phases, resolved)
        return

    specs_root = _resolve_specs_root()
    for phase in phases:
        _cycle_phase(phase, resolved, specs_root, force=force)

    session_path = Path(".deviate") / "session.json"
    session = SessionState.load(session_path)
    if session.current_phase != "IDLE":
        session = session.force_transition_to("IDLE")
        session.save(session_path)
    console.print("[green]MACRO[/] pipeline complete — session at IDLE")


# ---------------------------------------------------------------------------
# Macro pre/post wrappers (called by _macro_run)
# ---------------------------------------------------------------------------


def _explore_pre(problem: str, slug: str | None = None) -> None:
    explore_pre(problem=problem, slug=slug)


def _explore_post(force: bool = False) -> None:
    explore_post(epic=None, force=force)


def _research_pre(epic: str = "") -> None:
    research_pre(epic=epic)


def _research_post(force: bool = False) -> None:
    research_post(epic=None, force=force)


def _prd_pre() -> None:
    prd_pre()


def _prd_post(manifest: Path, force: bool = False) -> None:
    prd_post(manifest, force=force)


def _shard_pre(epic: str | None = None) -> None:
    shard_pre(epic=epic, dry_run=False)


def _shard_post(manifest: Path, epic: str | None = None, force: bool = False) -> None:
    shard_post(manifest, epic=epic, force=force)


# ---------------------------------------------------------------------------
# Macro CLI command
# ---------------------------------------------------------------------------


macro_app = typer.Typer(no_args_is_help=True)


@macro_app.command("run")
def macro_run_command(
    target: str | None = typer.Option(
        None, "--target", help="Target feature bucket slug"
    ),
    from_phase: str | None = typer.Option(
        None,
        "--from",
        help="Resume from a specific phase (explore|research|prd|shard)",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Emit prompts and contracts without side effects"
    ),
    force: bool = typer.Option(False, "--force", help="Bypass pre-flight guards"),
) -> None:
    """Run the macro automated pipeline (explore→research→prd→shard)"""
    _macro_run(target=target, from_phase=from_phase, dry_run=dry_run, force=force)
