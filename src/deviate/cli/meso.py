from __future__ import annotations

import json
import re
import shutil
import subprocess
from contextlib import chdir
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import typer

from deviate.cli._common import (
    _extract_epic_num,
    _extract_issue_num,
    _handle_missing_dot_dir,
    _run_pre_commit_hooks,
    console,
    with_json_quiet,
)

from pydantic import ValidationError

from deviate.core.agent import AgentBackend, AgentSubprocessError
from deviate.core._shared import git_env as _git_env
from deviate.core.commit import commit_artifact
from deviate.core.constitution import extract_commands
from deviate.core.tasks_ledger import generate_jsonl_from_md
from deviate.core.issues import claim_issue
from deviate.core.repo import gather_git_state
from deviate.core.worktree import (
    branch_exists_on_remote,
    create_worktree,
    remove_worktree,
)
from deviate.prompts.assembly import assemble_prompt
from deviate.state.config import SessionState
from deviate.state.ledger import (
    IssueRecord,
    TaskRecord,
    append_issue_transition,
    append_task_record,
    resolve_issue_record,
    select_next_unblocked_issue,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_dot_deviate() -> Path:
    return Path(".deviate")


def _resolve_specs_root() -> Path:
    return Path("specs")


def _load_session(phase: str) -> tuple[SessionState, Path]:
    dot_dir = _resolve_dot_deviate()
    if not dot_dir.exists():
        _handle_missing_dot_dir(phase)
    session_path = dot_dir / "session.json"
    session = SessionState.load(session_path)
    return session, session_path


def _load_session_accept(
    *phases: str, force: bool = False
) -> tuple[SessionState, Path]:
    """Load session — state is purely descriptive, no phase gating."""
    dot_dir = _resolve_dot_deviate()
    if not dot_dir.exists():
        _handle_missing_dot_dir(phases[0] if phases else "?")
    session_path = dot_dir / "session.json"
    session = SessionState.load(session_path)
    return session, session_path


def _save_session(session: SessionState, session_path: Path, phase: str) -> None:
    session.save(session_path)
    console.print(f"[green]{phase}[/] session advanced to {phase} phase")


def _resolve_bucket_dir(source_file: str) -> str:
    """Extract the epic bucket slug from a source_file path.

    Expects ``source_file`` to follow the pattern ``specs/<epic>/issues/<file>.md``.
    Returns the second-to-last path component (the epic directory name).
    """
    return PurePosixPath(source_file).parent.parent.name


def _source_stem(source_file: str) -> str:
    """Extract the issue slug (filename stem) from a source_file path."""
    return PurePosixPath(source_file).stem


def _is_issue_completed(issue_id: str, ledger_path: Path) -> bool:
    record = resolve_issue_record(issue_id, ledger_path)
    if record is None:
        return False
    return record.status == "COMPLETED"


def _find_issue_file(issue_id: str) -> Path | None:
    """Resolve the spec-enriched issue file for *issue_id*.

    The issue file IS the spec — it contains ``[USER_STORIES_LEDGER]``,
    ``[ATDD_ACCEPTANCE_CRITERIA]``, and all other spec sections embedded
    as markdown sections.  No separate ``spec.md`` exists.
    """
    ledger_path = _resolve_specs_root() / "issues.jsonl"
    record = resolve_issue_record(issue_id, ledger_path)
    if record is None or not record.source_file:
        return None
    issue_path = Path(record.source_file)
    if issue_path.exists():
        return issue_path
    return None


def _resolve_constitution_commands(
    repo_root: Path,
) -> tuple[str, str, str]:
    const_path = repo_root / "specs" / "constitution.md"
    constitution_path = str(const_path) if const_path.exists() else ""
    test_command = ""
    lint_command = ""
    if const_path.exists():
        cmds = extract_commands(const_path)
        test_command = cmds.get("test_command", "")
        lint_command = cmds.get("lint_command", "")
    return constitution_path, test_command, lint_command


TYPE_MAP: dict[str, str] = {
    "feature": "feat",
    "bug": "fix",
    "chore": "chore",
    "refactor": "refactor",
    "docs": "docs",
    "test": "test",
    "perf": "perf",
    "style": "style",
}


def _pr_title(issue_id: str, record_title: str, record_type: str = "feature") -> str:
    """Build a conventional-commit PR title suitable for squash-merge.

    Takes the raw issue title (e.g. \"[FR-001] CLI Initialization\") and strips
    any bracketed prefix like [FR-NNN] so the final title reads as a clean
    conventional commit subject.
    """
    commit_type = TYPE_MAP.get(record_type, "feat")
    desc = re.sub(r"^\[[A-Z]+-\d+\]\s*", "", record_title).strip()
    return f"{commit_type}({issue_id}): {desc}"


def _derive_pr_metadata(
    branch_name: str, issue_id: str, record_title: str, record_type: str = "feature"
) -> tuple[str, str, str]:
    pr_title = _pr_title(issue_id, record_title, record_type)
    pr_body = ""
    base_branch = "main"
    return pr_title, pr_body, base_branch


def _resolve_and_validate_issue(issue_id: str, phase: str) -> IssueRecord:
    dot_dir = _resolve_dot_deviate()
    if not dot_dir.exists():
        _handle_missing_dot_dir(phase)
    ledger_path = _resolve_specs_root() / "issues.jsonl"
    record = resolve_issue_record(issue_id, ledger_path)
    if record is None:
        console.print(f"[red]INVALID_ISSUE_ID[/] {issue_id}")
        raise typer.Exit(code=1)
    return record


def _setup_mise(worktree_path: Path | None = None) -> None:
    """Run mise trust && install && setup if mise is on PATH."""
    repo = worktree_path or Path.cwd()
    try:
        subprocess.run(["mise", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        console.print("[yellow]MISE_WARN[/] mise not found on PATH, skipping setup")
        return
    try:
        subprocess.run(["mise", "trust"], cwd=repo, check=True, capture_output=True)
        console.print("[green]MISE[/] trust applied")
        subprocess.run(["mise", "install"], cwd=repo, check=True, capture_output=True)
        console.print("[green]MISE[/] install complete")
        subprocess.run(
            ["mise", "run", "setup"], cwd=repo, check=True, capture_output=True
        )
        console.print("[green]MISE[/] setup complete")
    except subprocess.CalledProcessError as e:
        console.print(f"[yellow]MISE_WARN[/] setup step failed — {e}")


# ---------------------------------------------------------------------------
# Specify — legacy positional-argument API
# ---------------------------------------------------------------------------


def _specify_legacy(issue_id: str) -> None:
    console.print(
        "[yellow]DEPRECATED[/] 'deviate specify' is deprecated. "
        "The SPECIFY phase has been merged into 'deviate shard'. "
        "Use 'deviate shard' instead — shard now produces spec-enriched "
        "issue files directly."
    )
    raise typer.Exit(code=0)


# ---------------------------------------------------------------------------
# Pre-flight helpers for _specify_pre
# ---------------------------------------------------------------------------


def _read_issue_body(source_file: str, repo_root: Path) -> str:
    path = repo_root / source_file
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _validate_prd_traceability(issue_body: str, prd_path: Path) -> tuple[str, str]:
    """Validate that FR references in issue_body exist in the PRD.
    Returns (status, details)."""
    if not prd_path.exists():
        return ("FAIL", "PRD not found — traceability cannot be validated")
    prd_frs = set()
    try:
        prd_text = prd_path.read_text(encoding="utf-8")
        for m in re.finditer(r"FR-\d+(?:[_-]\d+)?", prd_text):
            prd_frs.add(m.group(0))
    except Exception:
        return ("FAIL", "PRD unreadable")
    issue_frs = set()
    for m in re.finditer(r"FR-\d+(?:[_-]\d+)?", issue_body):
        issue_frs.add(m.group(0))
    if not issue_frs:
        return ("WARN", "No FR references found in issue body")
    missing = issue_frs - prd_frs
    if missing:
        return ("FAIL", f"Missing in PRD: {', '.join(sorted(missing))}")
    return ("PASS", "All FRs present in PRD")


def _emit_contract(
    status: str,
    phase: str,
    issue_id: str,
    issue_title: str,
    issue_body: str,
    epic_slug: str,
    issue_slug: str,
    branch_name: str,
    worktree_path: str,
    spec_target: str,
    spec_target_abs: str,
    prd_requirements: list[str],
    traceability_status: str,
    traceability_details: str,
    constitution_path: str,
    constitution_test_command: str,
    constitution_lint_command: str,
    repo_root: str,
    git_branch: str,
    timestamp: str,
) -> str:
    contract = {
        "status": status,
        "phase": phase,
        "issue_id": issue_id,
        "issue_title": issue_title,
        "issue_body": issue_body,
        "epic_slug": epic_slug,
        "issue_slug": issue_slug,
        "branch_name": branch_name,
        "worktree_full": worktree_path,
        "spec_target": spec_target,
        "spec_target_abs": spec_target_abs,
        "prd_requirements": prd_requirements,
        "traceability_status": traceability_status,
        "traceability_details": traceability_details,
        "constitution_path": constitution_path,
        "constitution_test_command": constitution_test_command,
        "constitution_lint_command": constitution_lint_command,
        "repo_root": repo_root,
        "git_branch": git_branch,
        "timestamp": timestamp,
    }
    return json.dumps(contract, indent=2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_linked_worktree(cwd: Path | None = None) -> bool:
    """True if *cwd* is inside a linked (non-main) git worktree.

    Distinguishes linked worktrees (``.git`` is a file containing
    ``/worktrees/``) from git submodules (``.git`` is a file containing
    ``/modules/``) and main repos (``.git`` is a directory).
    """
    cwd = cwd or Path.cwd()
    git_path = cwd / ".git"
    if not git_path.exists():
        return False
    if git_path.is_dir():
        return False  # Main worktree — .git is a directory
    try:
        content = git_path.read_text(encoding="utf-8").strip()
        return "/worktrees/" in content
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Specify — new pre/post subcommand behavior
# ---------------------------------------------------------------------------


def _try_claim_issue(
    issue: IssueRecord,
    repo_root: Path,
    ledger_path: Path,
    remote: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> dict | None:
    """Attempt to claim a single issue end-to-end.

    Returns a metadata dict on success, ``None`` if the issue cannot be
    claimed (branch on remote, worktree error, or push race).
    """
    resolved_id = issue.issue_id
    epic_slug = _resolve_bucket_dir(issue.source_file)
    issue_slug = _source_stem(issue.source_file)
    branch = f"feat/{epic_slug}/{issue_slug}"
    spec_target_rel = f"specs/{epic_slug}/{issue_slug}/spec.md"

    console.print(f"[green]EPIC[/] {epic_slug}")
    console.print(f"[green]SLUG[/] {issue_slug}")
    console.print(f"[green]BRANCH[/] {branch}")

    # ── Remote branch check (non-dry-run only) ──────────────────────────
    if not dry_run and remote is not None:
        if branch_exists_on_remote(branch, repo=repo_root, remote=remote):
            console.print(
                f"[yellow]BRANCH_ON_REMOTE[/] {branch} — issue likely "
                f"already claimed elsewhere"
            )
            return None

    # ── Dry-run / create worktree ──────────────────────────────────────
    worktree_path: str
    if dry_run:
        console.print("[yellow]DRY_RUN[/] skipping worktree creation and claim")
        worktree_path = str(repo_root)
    else:
        wt_path = repo_root / ".worktrees" / branch
        try:
            created = create_worktree(branch, wt_path, repo=repo_root)
            console.print(
                f"[green]WORKTREE[/] "
                f"{'detected at' if created != wt_path else 'created at'} "
                f"{created}"
            )
            worktree_path = str(created)
        except RuntimeError as e:
            console.print(f"[yellow]WORKTREE_ERROR[/] {e}")
            return None

        # ── Mise setup ─────────────────────────────────────────────────
        _setup_mise(Path(worktree_path))

        # ── Claim issue (write directly to worktree ledger) ────────────
        wt_ledger_path = Path(worktree_path) / "specs" / "issues.jsonl"
        claimed = claim_issue(resolved_id, wt_ledger_path)
        if claimed:
            console.print(f"[green]CLAIMED[/] {resolved_id} → SPECIFIED")
        else:
            console.print(
                f"[yellow]CLAIM_SKIP[/] {resolved_id} already claimed or skipped"
            )

        # ── Create spec target directory in worktree ───────────────────
        wt_spec_dir = Path(worktree_path) / Path(spec_target_rel).parent
        wt_spec_dir.mkdir(parents=True, exist_ok=True)

        # ── Detect remote if not specified ────────────────────────────
        if remote is None:
            try:
                r = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    env=_git_env(),
                )
                if r.returncode == 0:
                    remote = "origin"
            except Exception:
                pass

        # ── Commit and push claim ──────────────────────────────────────
        if claimed:
            try:
                subprocess.run(
                    ["git", "add", "specs/issues.jsonl"],
                    cwd=worktree_path,
                    env=_git_env(),
                    check=True,
                    capture_output=True,
                )
                epic_num = _extract_epic_num(epic_slug)
                issue_num = _extract_issue_num(resolved_id)
                subprocess.run(
                    [
                        "git",
                        "commit",
                        "--no-verify",
                        "-m",
                        f"chore({epic_num}-{issue_num}): claim {resolved_id}",
                    ],
                    cwd=worktree_path,
                    env=_git_env(),
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError:
                console.print("[yellow]COMMIT_CLAIM_SKIP[/] could not commit claim")

            try:
                subprocess.run(
                    ["git", "push", "-u", remote, branch],
                    cwd=worktree_path,
                    env=_git_env(),
                    check=True,
                    capture_output=True,
                )
                console.print(f"[green]PUSHED[/] {branch} pushed to {remote}")
            except subprocess.CalledProcessError:
                if force:
                    console.print("[yellow]PUSH_FAILED[/] continuing (--force)")
                else:
                    console.print(
                        f"[yellow]PUSH_FAILED[/] {branch} — race or remote error"
                    )
                    remove_worktree(branch, Path(worktree_path), repo=repo_root)
                    return None

    return {
        "resolved_id": resolved_id,
        "issue": issue,
        "epic_slug": epic_slug,
        "issue_slug": issue_slug,
        "branch": branch,
        "spec_target_rel": spec_target_rel,
        "worktree_path": worktree_path,
    }


@with_json_quiet
def _specify_pre(
    issue_id: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> dict | None:
    ledger_path = _resolve_specs_root() / "issues.jsonl"
    if issue_id is None:
        console.print("[red]ISSUE_ID_REQUIRED[/] specify pre requires --issue <id>")
        raise typer.Exit(code=1)
    record = resolve_issue_record(issue_id, ledger_path)
    if record is None:
        console.print(f"[red]ISSUE_NOT_FOUND[/] {issue_id}")
        raise typer.Exit(code=1)
    result = _try_claim_issue(
        record,
        repo_root=Path.cwd(),
        ledger_path=ledger_path,
        force=force,
        dry_run=dry_run,
    )
    if result is None:
        console.print(f"[red]CLAIM_FAILED[/] could not claim {issue_id}")
        raise typer.Exit(code=1)
    console.print(f"[green]WORKTREE[/] {result['worktree_path']}")
    return result


def _specify_post(force: bool = False) -> None:
    console.print(
        "[yellow]SETUP_NOOP[/] specify post is not needed — setup is a single pre step"
    )
    raise typer.Exit(code=0)


# ---------------------------------------------------------------------------
# Plan — pre / post subcommand behavior
# ---------------------------------------------------------------------------


def _discover_unclaimed() -> str:
    """Return the next unblocked BACKLOG issue ID, or halt."""
    ledger_path = _resolve_specs_root() / "issues.jsonl"
    if not ledger_path.exists():
        console.print("[red]NO_LEDGER[/] specs/issues.jsonl not found")
        raise typer.Exit(code=1)
    issue = select_next_unblocked_issue(ledger_path)
    if issue is None:
        console.print("[red]NO_UNBLOCKED_ISSUES[/] no BACKLOG issue available")
        raise typer.Exit(code=1)
    return issue.issue_id


def _claim_and_setup(issue_id: str, force: bool, dry_run: bool) -> Path:
    """Claim *issue_id* via ``_specify_pre``, advance session to PLAN,
    sync ``.deviate/`` to the new worktree.

    Returns the worktree path.
    """
    dot_dir = _resolve_dot_deviate()
    setup_result = _specify_pre(issue_id=issue_id, force=force, dry_run=dry_run)
    if setup_result is None:
        raise typer.Exit(code=1)

    if not dry_run:
        session_path = dot_dir / "session.json"
        session = SessionState.load(session_path)
        session = session.force_transition_to("PLAN")
        session.active_issue_id = issue_id
        session.save(session_path)

        wt_path = Path(setup_result["worktree_path"])
        if dot_dir.exists():
            shutil.copytree(str(dot_dir), str(wt_path / ".deviate"), dirs_exist_ok=True)

        console.print(f"[green]WORKTREE[/] setup at {wt_path}")
        console.print("[green]SESSION[/] advanced to PLAN")

    return Path(setup_result["worktree_path"])


@with_json_quiet
def _plan_pre(
    issue_id: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> None:
    """Emit a plan-pre contract.

    *Not in a linked worktree* — auto-claim + setup:
      - ``issue_id`` given → claim that specific issue.
      - No ``issue_id`` → discover next unblocked BACKLOG issue.

    *Inside a linked worktree* — emit the JSON contract for the agent.
    """
    # ── Auto-claim + setup (not in linked worktree) ────────────────────
    if not _is_linked_worktree():
        rid = issue_id if issue_id is not None else _discover_unclaimed()
        _claim_and_setup(rid, force, dry_run)
        raise typer.Exit(code=0)

    # ── Contract mode (inside worktree or from _meso_run) ──────────────
    session, _ = _load_session_accept("SPECIFY", "PLAN", force=force)
    resolved_issue_id = issue_id or session.active_issue_id or ""
    if not resolved_issue_id:
        console.print(
            "[red]NO_ACTIVE_ISSUE[/] provide --issue or run from a worktree "
            "with active_issue_id in session"
        )
        raise typer.Exit(code=1)

    repo_root = Path.cwd()
    worktree_full = str(repo_root)
    branch_name = ""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            env=_git_env(),
        )
        branch_name = r.stdout.strip()
    except Exception:
        pass
    console.print(f"[green]WORKTREE[/] {worktree_full} [{branch_name}]")

    spec_path: str = ""
    status: str = "READY"
    if resolved_issue_id:
        found = _find_issue_file(resolved_issue_id)
        if found is None:
            status = "ISSUE_NOT_FOUND"
            console.print(
                f"[red]ISSUE_NOT_FOUND[/] issue file not found for {resolved_issue_id}"
            )
        else:
            spec_path = str(found)
            console.print(
                f"[green]SPEC_DISCOVERED[/] {spec_path} (issue file IS the spec)"
            )
    else:
        status = "ISSUE_NOT_FOUND"
        console.print("[red]NO_ACTIVE_ISSUE[/]")

    plan_target: str = ""
    if resolved_issue_id:
        ledger_path = _resolve_specs_root() / "issues.jsonl"
        record = resolve_issue_record(resolved_issue_id, ledger_path)
        if record is not None:
            bucket = _resolve_bucket_dir(record.source_file)
            slug = _source_stem(record.source_file)
            plan_target = str(_resolve_specs_root() / bucket / slug / "plan.md")

    (
        constitution_path,
        constitution_test_command,
        constitution_lint_command,
    ) = _resolve_constitution_commands(repo_root)

    if dry_run:
        console.print("[yellow]DRY_RUN[/] skipping side effects")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    contract = {
        "issue_id": resolved_issue_id,
        "spec_path": spec_path,
        "plan_target": plan_target,
        "worktree_full": worktree_full,
        "branch_name": branch_name,
        "constitution_path": constitution_path,
        "constitution_test_command": constitution_test_command,
        "constitution_lint_command": constitution_lint_command,
        "timestamp": timestamp,
        "status": status,
        "phase": "plan_pre",
        "force": force,
        "dry_run": dry_run,
    }
    print(json.dumps(contract, indent=2))


def _plan_post(force: bool = False, issue_id: str | None = None) -> None:
    """Validate plan.md, commit it, and advance session to TASKS."""
    session, session_path = _load_session_accept("PLAN", force=force)
    resolved_issue_id = issue_id or session.active_issue_id
    if not resolved_issue_id:
        console.print("[red]NO_ACTIVE_ISSUE[/] session has no active_issue_id")
        raise typer.Exit(code=1)

    ledger_path = _resolve_specs_root() / "issues.jsonl"
    record = resolve_issue_record(resolved_issue_id, ledger_path)
    if record is None:
        console.print(f"[red]ISSUE_NOT_FOUND[/] {resolved_issue_id}")
        raise typer.Exit(code=1)

    bucket = _resolve_bucket_dir(record.source_file)
    slug = _source_stem(record.source_file)
    plan_md = _resolve_specs_root() / bucket / slug / "plan.md"
    if not plan_md.exists():
        console.print(f"[red]PLAN_NOT_FOUND[/] {plan_md}")
        raise typer.Exit(code=1)
    content = plan_md.read_text(encoding="utf-8").strip()
    if not content and not force:
        console.print("[red]PLAN_EMPTY[/] plan.md is empty")
        raise typer.Exit(code=1)

    _run_pre_commit_hooks()

    epic_num = _extract_epic_num(bucket)
    issue_num = _extract_issue_num(resolved_issue_id)
    try:
        sha = commit_artifact(
            plan_md,
            f"docs({epic_num}-{issue_num}): create plan.md",
            repo=Path.cwd(),
        )
        console.print(f"[green]COMMITTED[/] plan.md at {sha[:8]}")
    except Exception as e:
        console.print(f"[red]COMMIT_FAILED[/] {e}")
        raise typer.Exit(code=1)

    session = session.transition_to("TASKS")
    _save_session(session, session_path, "TASKS")


# ---------------------------------------------------------------------------
# Tasks — legacy positional-argument API
# ---------------------------------------------------------------------------


def _tasks_legacy(issue_id: str) -> None:
    record = _resolve_and_validate_issue(issue_id, "TASKS")
    session_path = _resolve_dot_deviate() / "session.json"
    session = SessionState.load(session_path)
    issue_slug = _resolve_bucket_dir(record.source_file)
    tasks_jsonl = _resolve_specs_root() / issue_slug / "tasks.jsonl"
    if tasks_jsonl.exists():
        console.print(f"[yellow]SKIP[/] tasks already provisioned for {issue_slug}")
        raise typer.Exit(code=0)
    session = session.transition_to("TASKS")
    session.active_issue_id = issue_id
    session.save(session_path)

    # Generate TSK-NNN-NN: extract issue number, count existing tasks, increment
    issue_num = _extract_issue_num(issue_id)
    existing_ids: list[dict] = []
    if tasks_jsonl.exists():
        for line in tasks_jsonl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    existing_ids.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    existing_tasks = [r for r in existing_ids if r.get("issue_id") == issue_id]
    existing_max = 0
    for t in existing_tasks:
        m = re.match(r"^TSK-\d{3}-(\d{2})$", t.get("id", ""))
        if m:
            idx = int(m.group(1))
            if idx > existing_max:
                existing_max = idx
    next_index = existing_max + 1
    task_id = f"TSK-{issue_num}-{next_index:02d}"

    task = TaskRecord(
        id=task_id,
        issue_id=issue_id,
        description=f"Implement {record.title}",
        status="PENDING",
        execution_mode="TDD",
    )
    if not append_task_record(task, tasks_jsonl):
        console.print(f"[red]ERROR[/] Failed to append task record {task.id}")
        raise typer.Exit(code=1)

    session = session.transition_to("IDLE")
    session.save(session_path)
    console.print(f"[green]TASKS[/] 1 task(s) provisioned for {issue_slug}")


# ---------------------------------------------------------------------------
# Tasks — new pre/post subcommand behavior
# ---------------------------------------------------------------------------


@with_json_quiet
def _tasks_pre(force: bool = False, dry_run: bool = False) -> None:
    session, _ = _load_session_accept("PLAN", "SPECIFY", "TASKS", force=force)

    issue_id = session.active_issue_id or ""

    # Resolve issue file (the spec-enriched issue IS the spec)
    spec_path: str = ""
    status: str = "READY"
    if issue_id:
        found = _find_issue_file(issue_id)
        if found is None:
            status = "ISSUE_NOT_FOUND"
            console.print(
                f"[red]ISSUE_NOT_FOUND[/] issue file not found for {issue_id}"
            )
        else:
            spec_path = str(found)
            console.print(f"[green]SPEC_DISCOVERED[/] {spec_path}")
    else:
        status = "SPEC_NOT_FOUND"
        console.print("[red]NO_ACTIVE_ISSUE[/] session has no active_issue_id")

    # Worktree: we are already inside the worktree when tasks pre runs,
    # so Path.cwd() is the correct answer. Fall back to branch lookup only
    # as a safety net.
    repo_root = Path.cwd()
    worktree_full = str(repo_root)
    branch_name = ""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        branch_name = result.stdout.strip()
    except Exception:
        pass
    console.print(f"[green]WORKTREE[/] {worktree_full} [{branch_name}]")

    constitution_path, constitution_test_command, constitution_lint_command = (
        _resolve_constitution_commands(repo_root)
    )

    # Resolve tasks_target (per-issue, not per-epic)
    tasks_target: str = ""
    if issue_id:
        ledger_path = _resolve_specs_root() / "issues.jsonl"
        record = resolve_issue_record(issue_id, ledger_path)
        if record is not None:
            bucket = _resolve_bucket_dir(record.source_file)
            slug = _source_stem(record.source_file)
            tasks_target = str(_resolve_specs_root() / bucket / slug / "tasks.md")

    if dry_run:
        console.print("[yellow]DRY_RUN[/] skipping side effects")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    contract = {
        "issue_id": issue_id,
        "spec_path": spec_path,
        "tasks_target": tasks_target,
        "worktree_full": worktree_full,
        "branch_name": branch_name,
        "constitution_path": constitution_path,
        "constitution_test_command": constitution_test_command,
        "constitution_lint_command": constitution_lint_command,
        "timestamp": timestamp,
        "status": status,
        "phase": "tasks_pre",
        "force": force,
        "dry_run": dry_run,
    }
    print(json.dumps(contract, indent=2))


def _tasks_post(
    force: bool = False,
    issue_id: str | None = None,
    confirm: bool = False,
) -> None:
    session, session_path = _load_session_accept("TASKS", force=force)
    resolved_issue_id = issue_id or session.active_issue_id
    if not resolved_issue_id:
        console.print("[red]NO_ACTIVE_ISSUE[/] session has no active_issue_id")
        raise typer.Exit(code=1)
    ledger_path = _resolve_specs_root() / "issues.jsonl"
    record = resolve_issue_record(resolved_issue_id, ledger_path)
    if record is None:
        console.print(f"[red]ISSUE_NOT_FOUND[/] {resolved_issue_id}")
        raise typer.Exit(code=1)
    bucket = _resolve_bucket_dir(record.source_file)
    slug = _source_stem(record.source_file)
    tasks_md = _resolve_specs_root() / bucket / slug / "tasks.md"
    if not tasks_md.exists():
        console.print(f"[red]TASKS_NOT_FOUND[/] {tasks_md}")
        raise typer.Exit(code=1)
    content = tasks_md.read_text(encoding="utf-8").strip()
    if not content and not force:
        console.print("[red]TASKS_EMPTY[/] tasks.md is empty")
        raise typer.Exit(code=1)

    tasks_jsonl = tasks_md.with_name("tasks.jsonl")
    proposal_path = tasks_md.with_name("tasks.jsonl.proposal")
    try:
        records = generate_jsonl_from_md(tasks_md, resolved_issue_id)
    except ValidationError as e:
        for err in e.errors():
            loc = ".".join(str(part) for part in err["loc"])
            console.print(f"[red]VALIDATION_ERROR[/] {loc}: {err['msg']}")
        raise typer.Exit(code=1)

    if confirm:
        for rec in records:
            append_task_record(rec, tasks_jsonl)
        if proposal_path.exists():
            proposal_path.unlink()
    else:
        proposal_path.parent.mkdir(parents=True, exist_ok=True)
        proposal_lines = "\n".join(rec.model_dump_json() for rec in records)
        proposal_path.write_text(proposal_lines + "\n", encoding="utf-8")

    _run_pre_commit_hooks()

    epic_num = _extract_epic_num(bucket)
    issue_num = _extract_issue_num(resolved_issue_id)
    try:
        sha = commit_artifact(
            tasks_md, f"docs({epic_num}-{issue_num}): create tasks.md", repo=Path.cwd()
        )
        console.print(f"[green]COMMITTED[/] tasks.md at {sha[:8]}")
    except Exception as e:
        console.print(f"[red]COMMIT_FAILED[/] {e}")
        raise typer.Exit(code=1)
    session = session.transition_to("IDLE")
    _save_session(session, session_path, "IDLE")


# ---------------------------------------------------------------------------
# PR — new pre/run subcommand behavior
# ---------------------------------------------------------------------------


def _pr_pre() -> None:
    session, _ = _load_session_accept("TASKS", "IDLE")
    repo_root = Path.cwd()
    issue_id = session.active_issue_id
    if not issue_id:
        console.print("[red]NO_ACTIVE_ISSUE[/] session has no active_issue_id")
        raise typer.Exit(code=1)
    ledger_path = _resolve_specs_root() / "issues.jsonl"
    record = resolve_issue_record(issue_id, ledger_path)
    if record is None:
        console.print(f"[red]ISSUE_NOT_FOUND[/] {issue_id}")
        raise typer.Exit(code=1)
    console.print(f"[green]ISSUE[/] {issue_id}: {record.title}")

    git_state = gather_git_state(repo=repo_root)

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        )
        branch_name = result.stdout.strip()
    except Exception:
        branch_name = "detached"

    pr_title, pr_body, base_branch = _derive_pr_metadata(
        branch_name, issue_id, record.title, record.type
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    contract = {
        "branch_name": branch_name,
        "base_branch": base_branch,
        "pr_title": pr_title,
        "pr_body": pr_body,
        "git_state": git_state,
        "timestamp": timestamp,
        "status": "READY",
        "phase": "pr_pre",
    }
    print(json.dumps(contract, indent=2))


def _pr_run(
    body_file: Path,
    merge: bool = False,
    auto_merge: bool = False,
) -> None:
    session, session_path = _load_session_accept("TASKS", "IDLE")
    issue_id = session.active_issue_id
    if not issue_id:
        console.print("[red]NO_ACTIVE_ISSUE[/] session has no active_issue_id")
        raise typer.Exit(code=1)
    ledger_path = _resolve_specs_root() / "issues.jsonl"
    record = resolve_issue_record(issue_id, ledger_path)
    if record is None:
        console.print(f"[red]ISSUE_NOT_FOUND[/] {issue_id}")
        raise typer.Exit(code=1)
    if not body_file.exists():
        console.print(f"[red]BODY_FILE_NOT_FOUND[/] {body_file}")
        raise typer.Exit(code=1)

    repo_root = Path.cwd()

    completed = record.model_copy(
        update={
            "status": "COMPLETED",
            "timestamp": datetime.now(timezone.utc),
        }
    )
    appended = append_issue_transition(completed, ledger_path)
    if appended:
        console.print(f"[green]COMPLETED[/] {issue_id} → COMPLETED")
    else:
        console.print(
            f"[yellow]LEDGER_IDEMPOTENT[/] COMPLETED for {issue_id} already recorded"
        )

    try:
        subprocess.run(
            ["git", "add", str(ledger_path)],
            cwd=repo_root,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "commit",
                "--no-verify",
                "-m",
                f"chore({issue_id}): mark COMPLETED in ledger",
            ],
            cwd=repo_root,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        console.print("[green]LEDGER_COMMITTED[/]")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip() if e.stderr else ""
        if "nothing to commit" in stderr:
            console.print("[yellow]LEDGER_UNCHANGED[/] no ledger changes to commit")
        else:
            console.print(f"[yellow]COMMIT_LEDGER_WARN[/] {stderr}")

    try:
        subprocess.run(
            ["git", "push", "-u", "origin", "HEAD"],
            cwd=repo_root,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        console.print("[green]BRANCH_PUSHED[/]")
    except subprocess.CalledProcessError as e:
        console.print(
            f"[yellow]PUSH_WARN[/] {e.stderr.strip() if e.stderr else 'push failed'}"
        )

    title = _pr_title(issue_id, record.title, record.type)
    cmd = ["gh", "pr", "create", "--title", title, "--body-file", str(body_file)]
    if merge:
        cmd.append("--merge")
    elif auto_merge:
        cmd.append("--auto-merge")
    result = subprocess.run(cmd, capture_output=True, text=True, env=_git_env())
    if result.returncode != 0:
        console.print(f"[red]PR_CREATE_FAILED[/] {result.stderr.strip()}")
        raise typer.Exit(code=1)
    pr_url = result.stdout.strip()
    console.print(f"[green]PR_CREATED[/] {pr_url}")

    _save_session(session, session_path, "TASKS")


# ---------------------------------------------------------------------------
# Meso automated pipeline
# ---------------------------------------------------------------------------


def _build_slim_prompt(phase: str, contract: dict[str, str]) -> str:
    repo_root = Path.cwd()
    constitution_path = repo_root / "specs" / "constitution.md"
    claude_path = repo_root / "CLAUDE.md"
    return assemble_prompt(
        template_name=phase,
        context=contract,
        constitution_path=constitution_path,
        claude_path=claude_path,
    )


def _invoke_agent_phase(phase: str, contract: dict[str, str]) -> None:
    """Build a slim prompt, invoke the agent, and abort on failure."""
    prompt = _build_slim_prompt(phase, contract)
    backend = AgentBackend()
    try:
        manifest = backend.invoke(prompt)
    except AgentSubprocessError as e:
        console.print(f"[red]{phase.upper()}_FAILED[/] {e}")
        raise SystemExit(1) from e
    if manifest.status != "PASS":
        console.print(
            f"[red]{phase.upper()}_FAILED[/] agent returned status: {manifest.status}"
        )
        raise SystemExit(1)


def _meso_discover_and_sequence() -> str | None:
    ledger_path = _resolve_specs_root() / "issues.jsonl"
    issue = select_next_unblocked_issue(ledger_path)
    if issue is None:
        return None
    return issue.issue_id


@with_json_quiet
def _meso_run(
    issue_id: str | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    dot_dir = _resolve_dot_deviate()
    if not dot_dir.exists():
        _handle_missing_dot_dir("MESO")

    session_path = dot_dir / "session.json"
    ledger_path = _resolve_specs_root() / "issues.jsonl"

    # ── Discover issue if not specified ──────────────────────────────
    if issue_id is None:
        discovered = _meso_discover_and_sequence()
        if discovered is None:
            console.print("[red]NO_UNBLOCKED_ISSUES[/] no unblocked BACKLOG issues")
            raise SystemExit(1)
        issue_id = discovered
        console.print(f"[green]DISCOVERED[/] {issue_id}")

    # ── Check COMPLETED ──────────────────────────────────────────────
    if _is_issue_completed(issue_id, ledger_path):
        console.print(f"[red]ISSUE_COMPLETED[/] {issue_id} is already COMPLETED")
        raise SystemExit(1)

    # ── Check progress → reset ──────────────────────────────────────
    record = resolve_issue_record(issue_id, ledger_path)
    if record and record.status not in ("BACKLOG", "DRAFT"):
        console.print(
            f"[yellow]PROGRESS_RESET[/] {issue_id} ({record.status})"
            " — resetting to BACKLOG"
        )
        reset = record.model_copy(update={"status": "BACKLOG"})
        append_issue_transition(reset, ledger_path)

    # Re-resolve after possible reset
    record = resolve_issue_record(issue_id, ledger_path)
    if record is None:
        console.print(f"[red]INVALID_ISSUE_ID[/] {issue_id} not found in ledger")
        raise SystemExit(1)

    # ── Blocking dependency check (explicit --issue) ─────────────────
    if record and record.blocked_by and not force:
        for dep_id in record.blocked_by:
            if not _is_issue_completed(dep_id, ledger_path):
                console.print(
                    f"[red]BLOCKED[/] {issue_id} is blocked by {dep_id} "
                    f"(use --force to bypass)"
                )
                raise SystemExit(1)

    epic_slug = _resolve_bucket_dir(record.source_file) if record else ""
    issue_slug = _source_stem(record.source_file) if record else ""
    issue_title = record.title if record else ""

    contract: dict[str, str] = {
        "issue_id": issue_id,
        "issue_title": issue_title,
        "epic_slug": epic_slug,
        "issue_slug": issue_slug,
    }

    # ── Dry-run mode ─────────────────────────────────────────────────
    if dry_run:
        console.print("[bold][yellow]DRY_RUN[/] — no state will be mutated[/]")
        prompt = _build_slim_prompt("tasks", contract)
        print(prompt)
        return

    # ── Setup step: create worktree and claim issue ──────────────────
    setup_result = _specify_pre(issue_id=issue_id, force=force, dry_run=False)
    worktree_path = Path(setup_result["worktree_path"])

    # ── PLAN phase — advance session (in original repo) ──────────────
    dot_dir = _resolve_dot_deviate()
    session_path = (dot_dir / "session.json").resolve()
    session = SessionState.load(session_path)
    if session.current_phase != "PLAN":
        session = session.force_transition_to("PLAN")
        session.active_issue_id = issue_id
        session.save(session_path)

    # Sync .deviate/ to worktree so downstream functions find the session
    if dot_dir.exists():
        shutil.copytree(
            str(dot_dir), str(worktree_path / ".deviate"), dirs_exist_ok=True
        )

    ctx = chdir(worktree_path)
    with ctx:
        _plan_pre(force=force, dry_run=False)

        _invoke_agent_phase("plan", contract)

        _plan_post(force=force, issue_id=issue_id)

        _tasks_pre(force=force, dry_run=False)

        _invoke_agent_phase("tasks", contract)

        _tasks_post(force=force, issue_id=issue_id)

        # ── Final IDLE guard ─────────────────────────────────────────
        session = SessionState.load(session_path)
        if session.current_phase != "IDLE":
            session = session.force_transition_to("IDLE")
            session.save(session_path)
    console.print("[green]MESO[/] pipeline complete — session at IDLE")


meso_app = typer.Typer(no_args_is_help=True)


@meso_app.command("run")
def meso_run_command(
    issue: str | None = typer.Option(
        None, "--issue", help="Target issue ID (default: next unblocked BACKLOG)"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Emit prompts and contracts without side effects",
    ),
    force: bool = typer.Option(False, "--force", help="Bypass pre-flight guards"),
) -> None:
    """Run the meso automated pipeline (setup → plan → tasks)"""
    _meso_run(issue_id=issue, dry_run=dry_run, force=force)


# ---------------------------------------------------------------------------
# CLI command entry points
# ---------------------------------------------------------------------------


def specify(
    issue_id: str = typer.Argument(..., help="Issue ID (or 'pre' / 'post')"),
    force: bool = typer.Option(
        False, "--force", help="Force operation (bypass push failure)"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Resolve issue and emit contract without creating worktree or claiming",
    ),
    issue: str | None = typer.Option(
        None, "--issue", help="Issue ID for pre subcommand"
    ),
) -> None:
    """Setup: create worktree and claim issue for the given issue ID"""
    if issue_id == "pre":
        _specify_pre(issue_id=issue, force=force, dry_run=dry_run)
    elif issue_id == "post":
        _specify_post(force=force)
    else:
        _specify_pre(issue_id=issue_id, force=force, dry_run=dry_run)


def plan(
    issue_id: str = typer.Argument(..., help="Issue ID (or 'pre' / 'post')"),
    force: bool = typer.Option(False, "--force", help="Force operation"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview without side effects"
    ),
    issue: str | None = typer.Option(
        None, "--issue", help="Issue ID for pre subcommand"
    ),
) -> None:
    """Plan phase: pre (research + emit) or post (validate, commit)"""
    if issue_id == "pre":
        _plan_pre(issue_id=issue, force=force, dry_run=dry_run)
    elif issue_id == "post":
        _plan_post(force=force, issue_id=issue)
    else:
        _plan_pre(issue_id=issue_id, force=force, dry_run=dry_run)


def tasks(
    issue_id: str = typer.Argument(..., help="Issue ID (or 'pre' / 'post')"),
    force: bool = typer.Option(False, "--force", help="Force operation"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview without side effects"
    ),
    issue: str | None = typer.Option(
        None, "--issue-id", help="Issue ID for post subcommand"
    ),
    confirm: bool = typer.Option(
        False, "--confirm", help="Confirm and write proposal to tasks.jsonl"
    ),
) -> None:
    """Tasks phase: pre (detect worktree) or post (validate, commit)"""
    if issue_id == "pre":
        _tasks_pre(force=force, dry_run=dry_run)
    elif issue_id == "post":
        _tasks_post(force=force, issue_id=issue, confirm=confirm)
    else:
        _tasks_legacy(issue_id)


def pr(
    action: str = typer.Argument(..., help="Action: pre (validate) or run (create PR)"),
    body_file: Path | None = typer.Option(
        None, "--body-file", help="Path to PR body file"
    ),
    merge: bool = typer.Option(False, "--merge", help="Merge after PR creation"),
    auto_merge: bool = typer.Option(False, "--auto-merge", help="Enable auto-merge"),
) -> None:
    """PR phase: pre (validate) or run (create PR)"""
    if action == "pre":
        _pr_pre()
    elif action == "run":
        if body_file is None:
            console.print("[red]MISSING_BODY_FILE[/] --body-file is required for 'run'")
            raise typer.Exit(code=1)
        _pr_run(body_file, merge=merge, auto_merge=auto_merge)
    else:
        console.print(f"[red]UNKNOWN_ACTION[/] '{action}'. Use 'pre' or 'run'")
        raise typer.Exit(code=1)
