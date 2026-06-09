from __future__ import annotations

import json
import re
import subprocess
import uuid as uuid_mod
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import typer

from deviate.cli._common import (
    _extract_epic_num,
    _extract_issue_num,
    _handle_missing_dot_dir,
    _handle_transition_error,
    _run_pre_commit_hooks,
    console,
)
from deviate.core._shared import git_env as _git_env
from deviate.core.commit import commit_artifact
from deviate.core.constitution import extract_commands
from deviate.core.issues import claim_issue
from deviate.core.repo import gather_git_state
from deviate.core.validation import (
    validate_gherkin_syntax,
    validate_task_id,
)
from deviate.core.worktree import (
    branch_exists_on_remote,
    create_worktree,
    detect_remote,
    detect_worktree,
)
from deviate.state.config import SessionState, TransitionViolationError
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
    if session.current_phase != phase:
        console.print(
            f"[red]PHASE_MISMATCH[/] session is in '{session.current_phase}', "
            f"expected '{phase}'"
        )
        raise typer.Exit(code=1)
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


def _find_spec_md(issue_id: str) -> Path | None:
    ledger_path = _resolve_specs_root() / "issues.jsonl"
    record = resolve_issue_record(issue_id, ledger_path)
    if record is None:
        return None
    bucket = _resolve_bucket_dir(record.source_file)
    slug = _source_stem(record.source_file)
    spec_path = _resolve_specs_root() / bucket / slug / "spec.md"
    if spec_path.exists():
        return spec_path
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


def _derive_pr_metadata(
    branch_name: str, issue_id: str, record_title: str
) -> tuple[str, str, str]:
    pr_title = f"[{issue_id}] {record_title}"
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
    record = _resolve_and_validate_issue(issue_id, "SPECIFY")
    session_path = _resolve_dot_deviate() / "session.json"
    session = SessionState.load(session_path)
    issue_slug = _resolve_bucket_dir(record.source_file)
    spec_dir = _resolve_specs_root() / issue_slug
    if spec_dir.exists():
        console.print(f"[yellow]SKIP[/] specs/{issue_slug}/ already exists")
    else:
        spec_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]CREATE[/] specs/{issue_slug}/")
    spec_md = spec_dir / "spec.md"
    if not spec_md.exists():
        spec_md.write_text("")
        console.print(f"[green]CREATE[/] specs/{issue_slug}/spec.md")
    session = session.force_transition_to("SPECIFY")
    session.active_issue_id = issue_id
    session.save(session_path)
    console.print("[green]SPECIFY[/] session advanced to SPECIFY phase")


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
# Specify — new pre/post subcommand behavior
# ---------------------------------------------------------------------------


def _specify_pre(
    issue_id: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> None:
    dot_dir = _resolve_dot_deviate()
    if not dot_dir.exists():
        _handle_missing_dot_dir("SPECIFY")
    session_path = dot_dir / "session.json"
    session = SessionState.load(session_path)
    repo_root = Path.cwd()
    ledger_path = _resolve_specs_root() / "issues.jsonl"

    # ── Resolve issue ──────────────────────────────────────────────────
    if issue_id is None:
        issue = select_next_unblocked_issue(ledger_path)
        if issue is None:
            console.print(
                "[red]NO_UNBLOCKED_BACKLOG[/] no unblocked BACKLOG issues found"
            )
            raise typer.Exit(code=1)
        resolved_id: str = issue.issue_id
        console.print(f"[green]SELECTED[/] {resolved_id} — {issue.title}")
    else:
        issue = resolve_issue_record(issue_id, ledger_path)
        if issue is None:
            console.print(f"[red]INVALID_ISSUE_ID[/] {issue_id}")
            raise typer.Exit(code=1)
        resolved_id = issue_id

    # ── Reject if already completed ────────────────────────────────────
    if _is_issue_completed(resolved_id, ledger_path):
        console.print(f"[red]COMPLETED[/] issue {resolved_id} is already COMPLETED")
        raise typer.Exit(code=1)

    # ── Parse source_file → epic slug + issue slug ─────────────────────
    epic_slug = _resolve_bucket_dir(issue.source_file)
    issue_slug = _source_stem(issue.source_file)
    branch = f"feat/{epic_slug}/{issue_slug}"
    spec_target_rel = f"specs/{epic_slug}/{issue_slug}/spec.md"

    console.print(f"[green]EPIC[/] {epic_slug}")
    console.print(f"[green]SLUG[/] {issue_slug}")
    console.print(f"[green]BRANCH[/] {branch}")

    # ── Issue body ─────────────────────────────────────────────────────
    issue_body = _read_issue_body(issue.source_file, repo_root)
    body_len = len(issue_body)
    console.print(f"[green]BODY[/] read {body_len} chars from {issue.source_file}")

    # ── PRD traceability ───────────────────────────────────────────────
    prd_path = repo_root / "specs" / epic_slug / "prd.md"
    prd_reqs: list[str] = []
    if prd_path.exists():
        prd_text = prd_path.read_text(encoding="utf-8")
        prd_reqs = sorted(set(re.findall(r"FR-\d+(?:[_-]\d+)?", prd_text)))
        traceability_status, traceability_details = _validate_prd_traceability(
            issue_body, prd_path
        )
    else:
        traceability_status = "FAIL"
        traceability_details = f"PRD not found at {prd_path}"

    console.print(f"[green]TRACEABILITY[/] {traceability_status}")

    # ── Constitution ───────────────────────────────────────────────────
    constitution_path, constitution_test_command, constitution_lint_command = (
        _resolve_constitution_commands(repo_root)
    )

    # ── Dry-run / create worktree ──────────────────────────────────────
    worktree_path: str
    if dry_run:
        console.print("[yellow]DRY_RUN[/] skipping worktree creation and claim")
        worktree_path = str(repo_root)
    else:
        try:
            remote = detect_remote(repo_root)
        except RuntimeError:
            console.print(
                "[red]NO_REMOTE[/] no git remotes configured — cannot push claim"
            )
            raise typer.Exit(code=1)
        # Check remote first
        if branch_exists_on_remote(branch, repo=repo_root, remote=remote):
            console.print(
                f"[red]BRANCH_EXISTS_REMOTE[/] {branch} already on {remote} — "
                f"issue likely already claimed elsewhere"
            )
            raise typer.Exit(code=1)

        wt_path = repo_root / ".worktrees" / branch
        try:
            created = create_worktree(branch, wt_path, repo=repo_root)
            console.print(
                f"[green]WORKTREE[/] {'detected at' if created != wt_path else 'created at'} {created}"
            )
            worktree_path = str(created)
        except RuntimeError as e:
            console.print(f"[red]WORKTREE_ERROR[/] {e}")
            raise typer.Exit(code=1)

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
                        "[red]PUSH_FAILED[/] push-to-claim failed. "
                        "Retry with --force to bypass."
                    )
                    raise typer.Exit(code=1)

    # ── Resolve git branch name ────────────────────────────────────────
    git_branch = branch
    if not dry_run:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=worktree_path,
                env=_git_env(),
                capture_output=True,
                text=True,
                check=True,
            )
            git_branch = result.stdout.strip()
        except Exception:
            pass

    # ── Session ────────────────────────────────────────────────────────
    session = session.force_transition_to("SPECIFY")
    session.active_issue_id = resolved_id
    session.save(session_path)
    if not dry_run:
        wt_dot_dir = Path(worktree_path) / ".deviate"
        wt_dot_dir.mkdir(parents=True, exist_ok=True)
        session.save(wt_dot_dir / "session.json")
        console.print(f"[green]SESSION_SYNC[/] session written to {wt_dot_dir}")
    console.print(
        f"[green]SPECIFY_PRE[/] session advanced to SPECIFY with {resolved_id}"
    )

    # ── Emit JSON contract ─────────────────────────────────────────────
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    contract = _emit_contract(
        status="READY" if not dry_run else "DRY_RUN",
        phase="specify",
        issue_id=resolved_id,
        issue_title=issue.title,
        issue_body=issue_body,
        epic_slug=epic_slug,
        issue_slug=issue_slug,
        branch_name=branch,
        worktree_path=worktree_path,
        spec_target=spec_target_rel,
        spec_target_abs=str(repo_root / spec_target_rel),
        prd_requirements=prd_reqs,
        traceability_status=traceability_status,
        traceability_details=traceability_details,
        constitution_path=constitution_path,
        constitution_test_command=constitution_test_command,
        constitution_lint_command=constitution_lint_command,
        repo_root=str(repo_root),
        git_branch=git_branch,
        timestamp=timestamp,
    )
    console.print(contract)


def _specify_post(force: bool = False) -> None:
    session, session_path = _load_session("SPECIFY")
    issue_id = session.active_issue_id
    if not issue_id:
        console.print("[red]NO_ACTIVE_ISSUE[/] session has no active_issue_id")
        raise typer.Exit(code=1)
    spec_path = _find_spec_md(issue_id)
    if spec_path is None:
        console.print("[red]SPEC_NOT_FOUND[/] could not find spec.md for issue")
        raise typer.Exit(code=1)
    content = spec_path.read_text(encoding="utf-8")
    errors = validate_gherkin_syntax(content)
    if errors:
        if force:
            for err in errors:
                console.print(f"[yellow]WARNING[/] {err}")
        else:
            for err in errors:
                console.print(f"[red]GHERKIN_ERROR[/] {err}")
            raise typer.Exit(code=1)
    epic_slug = spec_path.parent.parent.name
    epic_num = _extract_epic_num(epic_slug)
    issue_num = _extract_issue_num(issue_id)
    try:
        sha = commit_artifact(
            spec_path, f"docs({epic_num}-{issue_num}): create spec.md", repo=Path.cwd()
        )
        console.print(f"[green]COMMITTED[/] spec.md at {sha[:8]}")
    except Exception as e:
        console.print(f"[red]COMMIT_FAILED[/] {e}")
        raise typer.Exit(code=1)
    try:
        session = session.transition_to("TASKS")
    except TransitionViolationError as e:
        _handle_transition_error("SPECIFY", e)
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
    try:
        session = session.transition_to("TASKS")
    except TransitionViolationError as e:
        _handle_transition_error("TASKS", e)
    session.active_issue_id = issue_id
    session.save(session_path)

    task = TaskRecord(
        id=str(uuid_mod.uuid4()),
        issue_id=issue_id,
        description=f"Implement {record.title}",
        status="PENDING",
        execution_mode="TDD",
    )
    if not append_task_record(task, tasks_jsonl):
        console.print(f"[red]ERROR[/] Failed to append task record {task.id}")
        raise typer.Exit(code=1)

    try:
        session = session.transition_to("IDLE")
    except TransitionViolationError as e:
        _handle_transition_error("TASKS", e)
    session.save(session_path)
    console.print(f"[green]TASKS[/] 1 task(s) provisioned for {issue_slug}")


# ---------------------------------------------------------------------------
# Tasks — new pre/post subcommand behavior
# ---------------------------------------------------------------------------


def _tasks_pre(dry_run: bool = False) -> None:
    session, _ = _load_session("SPECIFY")
    repo_root = Path.cwd()

    issue_id = session.active_issue_id or ""

    spec_mds = list(_resolve_specs_root().rglob("spec.md"))
    if not spec_mds:
        spec_path = ""
        status = "SPEC_NOT_FOUND"
        console.print("[red]SPEC_NOT_FOUND[/] no spec.md found under specs/")
    else:
        spec_path = str(spec_mds[0])
        status = "READY"
        console.print(f"[green]SPEC_DISCOVERED[/] {spec_path}")

    wts = detect_worktree(repo=repo_root)
    worktree_full = str(next(iter(wts.values()))).strip() if wts else str(repo_root)
    console.print(f"[green]WORKTREES[/] {len(wts)} worktree(s) detected")

    constitution_path, constitution_test_command, constitution_lint_command = (
        _resolve_constitution_commands(repo_root)
    )

    if dry_run:
        console.print("[yellow]DRY_RUN[/] skipping side effects")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    contract = {
        "issue_id": issue_id,
        "spec_path": spec_path,
        "worktree_full": worktree_full,
        "constitution_path": constitution_path,
        "constitution_test_command": constitution_test_command,
        "constitution_lint_command": constitution_lint_command,
        "timestamp": timestamp,
        "status": status,
        "phase": "tasks_pre",
        "dry_run": dry_run,
    }
    print(json.dumps(contract, indent=2))


def _tasks_post(force: bool = False, issue_id: str | None = None) -> None:
    session, session_path = _load_session("TASKS")
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
    tasks_md = _resolve_specs_root() / bucket / "tasks.md"
    if not tasks_md.exists():
        console.print(f"[red]TASKS_NOT_FOUND[/] {tasks_md}")
        raise typer.Exit(code=1)
    content = tasks_md.read_text(encoding="utf-8").strip()
    if not content and not force:
        console.print("[red]TASKS_EMPTY[/] tasks.md is empty")
        raise typer.Exit(code=1)

    task_id_pattern = re.findall(r"(?m)^- \[[ x]\]\s+([\w-]+)", content)
    for tid in task_id_pattern:
        if not validate_task_id(tid):
            console.print(f"[red]INVALID_TASK_ID[/] {tid}")
            raise typer.Exit(code=1)

    task_lines = re.findall(r"(?m)^- \[[ x]\]\s+\S+.*", content)
    for line in task_lines:
        if "[ ]" in line:
            console.print(f"[yellow]UNCHECKED_TASK[/] {line.strip()}")
            if not force:
                console.print(
                    "[red]UNCHECKED_TASKS[/] some tasks are not marked complete"
                )
                raise typer.Exit(code=1)

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
    try:
        session = session.transition_to("IDLE")
    except TransitionViolationError as e:
        _handle_transition_error("TASKS", e)
    _save_session(session, session_path, "IDLE")


# ---------------------------------------------------------------------------
# PR — new pre/run subcommand behavior
# ---------------------------------------------------------------------------


def _pr_pre() -> None:
    session, _ = _load_session("TASKS")
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
        branch_name, issue_id, record.title
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
    session, session_path = _load_session("TASKS")
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
    title = f"[{issue_id}] {record.title}"
    cmd = ["gh", "pr", "create", "--title", title, "--body-file", str(body_file)]
    if merge:
        cmd.append("--merge")
    if auto_merge:
        cmd.append("--auto-merge")
    result = subprocess.run(cmd, capture_output=True, text=True, env=_git_env())
    if result.returncode != 0:
        console.print(f"[red]PR_CREATE_FAILED[/] {result.stderr.strip()}")
        raise typer.Exit(code=1)
    pr_url = result.stdout.strip()
    console.print(f"[green]PR_CREATED[/] {pr_url}")

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
    _save_session(session, session_path, "TASKS")


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
    """Specify phase: pre (select issue, create worktree) or post (validate, commit)"""
    if issue_id == "pre":
        _specify_pre(issue_id=issue, force=force, dry_run=dry_run)
    elif issue_id == "post":
        _specify_post(force=force)
    else:
        _specify_legacy(issue_id)


def tasks(
    issue_id: str = typer.Argument(..., help="Issue ID (or 'pre' / 'post')"),
    force: bool = typer.Option(False, "--force", help="Force operation"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview without side effects"
    ),
    issue: str | None = typer.Option(
        None, "--issue-id", help="Issue ID for post subcommand"
    ),
) -> None:
    """Tasks phase: pre (detect worktree) or post (validate, commit)"""
    if issue_id == "pre":
        _tasks_pre(dry_run=dry_run)
    elif issue_id == "post":
        _tasks_post(force=force, issue_id=issue)
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
