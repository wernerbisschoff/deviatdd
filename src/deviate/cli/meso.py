from __future__ import annotations

import json
import logging
import re

import shutil
import subprocess
import time
from contextlib import chdir, contextmanager, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path, PurePosixPath
from typing import Callable, Generator

import typer
from deviate.cli._common import (
    _build_slim_prompt,
    _extract_epic_num,
    _extract_issue_num,
    _handle_missing_dot_dir,
    console,
    resolve_issue_id_from_branch,
    with_json_quiet,
)

from deviate.core.agent import (
    AgentBackend,
    AgentSubprocessError,
    resolve_agent_to_backend,
)
from deviate.core._shared import git_env as _git_env
from deviate.core.epic import _ordinals_from_remote_feat_refs, _remote_adhoc_ordinals
from deviate.core.commit import commit_artifact, stage_and_commit
from deviate.core.convention import commit_scope, format_commit_message
from deviate.core.constitution import extract_commands
from deviate.core.issues import claim_issue
from deviate.core.repo import gather_git_state
from deviate.core.validation import (
    repair_missing_verification_mode,
    validate_acceptance_contract,
)
from deviate.core.worktree import (
    branch_exists_on_remote,
    create_worktree,
    find_worktree_for_branch,
    remove_worktree,
    resolve_start_point,
)
from deviate.state.config import (
    AgentConfig,
    SessionState,
    _load_deviate_config_toml,
    resolve_claim_remote,
    resolve_graphite_config,
    resolve_base_branch,
    resolve_model_for_phase,
)
from deviate.state.ledger import (
    FlowConfirmationResult,
    IssueRecord,
    TaskRecord,
    _confirm_implemented_flows,
    append_issue_transition,
    append_task_record,
    resolve_issue_record,
    select_next_unblocked_issue,
    select_unblocked_candidates,
)
from deviate.ui.pipeline import (
    PhaseCallout,
    PhaseMarker,
    PipelineBanner,
    PipelineSummary,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LOCAL_CLAIM_HELP = (
    "Claim locally only: create worktree, write ledger, commit; skip "
    "remote check and push. Distinct from --no-setup, which skips the "
    "worktree and ledger claim. Omitted flag honors claim_remote config."
)


def _effective_local(local: bool, root: Path | None = None) -> bool:
    """Resolve claim locality: ``--local`` OR ``claim_remote = false``.

    Explicit ``local=True`` always wins. When *root* is omitted, use
    ``Path.cwd()``.
    """
    if local:
        return True
    return not resolve_claim_remote(root if root is not None else Path.cwd())


def _origin_remote(repo: Path) -> str | None:
    """Return ``origin`` when that remote is configured, else ``None``."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo,
            capture_output=True,
            text=True,
            env=_git_env(),
        )
    except Exception:
        return None
    return "origin" if result.returncode == 0 else None


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


_ISSUE_SLUG_ORDINAL = re.compile(r"^(\d+)-(.*)$")
_CLAIM_NAME_COLLISION_RETRIES = 3


def _as_git_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _is_feat_name_collision(stderr: str | bytes) -> bool:
    return "already exists" in _as_git_text(stderr).lower()


def _next_claim_slug(epic_slug: str, issue_slug: str, repo_path: Path) -> str | None:
    match = _ISSUE_SLUG_ORDINAL.match(issue_slug)
    if match is None:
        return None
    current = int(match.group(1))
    rest = match.group(2)
    if epic_slug == "adhoc":
        remote_nums = _remote_adhoc_ordinals(repo_path)
    else:
        pattern = re.compile(rf"^(?:origin/)?feat/{re.escape(epic_slug)}/(\d+)-")
        remote_nums = _ordinals_from_remote_feat_refs(pattern, repo_path)
    next_n = max([current, *remote_nums], default=current) + 1
    return f"{next_n:03d}-{rest}"


def _print_push_stderr(stderr: str) -> None:
    if stderr:
        console.print(f"[yellow]PUSH_STDERR[/] {stderr}")


def _push_claim_with_collision_retry(
    *,
    remote: str | None,
    branch: str,
    worktree_path: str,
    repo_root: Path,
    epic_slug: str,
    issue_slug: str,
    spec_target_rel: str,
    force: bool,
) -> tuple[str, str, str] | None:
    """Push the claim branch; increment NNN and retry on name collision.

    Returns ``(branch, issue_slug, spec_target_rel)`` after a successful
    push or a ``--force`` continue. Returns ``None`` when a remote race
    already claimed the name or when a non-collision failure rolls back
    the worktree. Does not set ``local=True``.
    """
    collision_retries = 0
    while True:
        push_result = subprocess.run(
            ["git", "push", "--no-verify", "-u", remote, branch],
            cwd=worktree_path,
            env=_git_env(),
            check=False,
            capture_output=True,
            text=True,
        )
        if push_result.returncode == 0:
            console.print(f"[green]PUSHED[/] {branch} pushed to {remote}")
            return branch, issue_slug, spec_target_rel
        push_stderr = _as_git_text(push_result.stderr).strip()
        # Re-check the remote: a winning race looks like a push failure
        # (e.g. non-fast-forward) but the branch now exists on origin
        # because another agent won the race. Keep the local branch +
        # worktree; rolling back would destroy state the operator may
        # want to push elsewhere.
        if branch_exists_on_remote(branch, repo=repo_root, remote=remote):
            console.print(
                f"[yellow]BRANCH_ON_REMOTE[/] {branch} — "
                f"race won elsewhere; keeping local worktree"
            )
            _print_push_stderr(push_stderr)
            return None
        next_slug = (
            _next_claim_slug(epic_slug, issue_slug, repo_root)
            if (
                collision_retries < _CLAIM_NAME_COLLISION_RETRIES
                and _is_feat_name_collision(push_stderr)
            )
            else None
        )
        if next_slug is not None:
            new_branch = f"feat/{epic_slug}/{next_slug}"
            renamed = subprocess.run(
                ["git", "branch", "-m", new_branch],
                cwd=worktree_path,
                env=_git_env(),
                check=False,
                capture_output=True,
            )
            if renamed.returncode == 0:
                collision_retries += 1
                issue_slug = next_slug
                branch = new_branch
                spec_target_rel = f"specs/{epic_slug}/{issue_slug}/spec.md"
                console.print(
                    f"[yellow]CLAIM_RETRY[/] name collision; retrying {branch}"
                )
                continue
        if force:
            console.print(f"[yellow]PUSH_FAILED[/] {branch} — continuing (--force)")
            _print_push_stderr(push_stderr)
            return branch, issue_slug, spec_target_rel
        console.print(f"[yellow]PUSH_FAILED[/] {branch} — race or remote error")
        _print_push_stderr(push_stderr)
        remove_worktree(branch, Path(worktree_path), repo=repo_root)
        return None


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


def _read_spec_content(spec_path: str) -> str | None:
    try:
        pp = Path(spec_path)
        if pp.is_file():
            return pp.read_text(encoding="utf-8")
    except OSError:
        pass
    return None


def _parse_workstation_paths(spec_content: str) -> list[str]:
    """Extract workstation file paths from an issue spec's System Topology Mapping section.

    Looks for ``## System Topology Mapping`` → ``- **Primary Architectural Workstations**:``
    and extracts backtick-quoted paths from the subsequent bullet list.
    """
    paths: list[str] = []
    in_topology = False
    in_workstations = False

    for line in spec_content.splitlines():
        if (
            line.startswith("## ")
            and in_topology
            and "System Topology Mapping" not in line
        ):
            break
        if "## System Topology Mapping" in line:
            in_topology = True
            continue
        if not in_topology:
            continue
        stripped = line.strip()
        if stripped.startswith("- **Primary Architectural Workstations**"):
            in_workstations = True
            continue
        if in_workstations:
            if stripped.startswith("- ") and "`" in stripped:
                m = re.search(r"`([^`]+)`", stripped)
                if m:
                    paths.append(m.group(1))
            elif not stripped.startswith("- ") and not stripped.startswith("  "):
                in_workstations = False
    return paths


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
    return f"{commit_type}({commit_scope(issue_id)}): {desc}"


def _derive_pr_metadata(
    branch_name: str,
    issue_id: str,
    record_title: str,
    record_type: str = "feature",
    repo: Path | None = None,
) -> tuple[str, str, str]:
    pr_title = _pr_title(issue_id, record_title, record_type)
    pr_body = ""
    base_branch = resolve_base_branch(repo or Path.cwd())
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


_AGENT_DIRS = (".claude", ".opencode", ".factory", ".pi", ".omp")

_WORKTREE_SYNC_FILES = (".env",)


def _sync_worktree_assets(repo_root: Path, worktree_path: Path) -> None:
    """Copy agent skill directories and config files from repo root to worktree.

    This ensures worktrees have the same skills (.claude/, .opencode/,
    .factory/, .pi/, .omp/) and environment files (.env) as the main
    repository so deviate commands work inside the worktree without
    re-running ``deviate setup`` or losing local configuration.
    """
    for agent_dir in _AGENT_DIRS:
        src = repo_root / agent_dir
        dst = worktree_path / agent_dir
        if src.exists():
            shutil.copytree(src, dst, dirs_exist_ok=True)
            console.print(f"[green]SYNC[/] {agent_dir}/ → worktree")

    for filename in _WORKTREE_SYNC_FILES:
        src = repo_root / filename
        dst = worktree_path / filename
        if src.is_file():
            shutil.copy2(src, dst)
            console.print(f"[green]SYNC[/] {filename} → worktree")


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
    local: bool = False,
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

    # ── Remote branch check (non-dry-run, non-local only) ──────────────
    if local:
        console.print("[yellow]LOCAL_ONLY[/] skipping remote check")
    elif not dry_run and remote is not None:
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
        # --local short-circuit: a pre-existing local branch is the user's
        # chosen "already claimed" signal. NOTE: this can false-positive on a
        # manual `git checkout -b` that pre-dated any claim; the user picked
        # this semantic explicitly for the no-remote workflow.
        if local:
            existing_path = find_worktree_for_branch(branch, repo=repo_root)
            if existing_path is not None:
                console.print(
                    f"[yellow]ALREADY_CLAIMED_LOCAL[/] {branch} → reusing {existing_path}"
                )
                return {
                    "resolved_id": resolved_id,
                    "issue": issue,
                    "epic_slug": epic_slug,
                    "issue_slug": issue_slug,
                    "branch": branch,
                    "spec_target_rel": spec_target_rel,
                    "worktree_path": str(existing_path),
                }
        wt_path = repo_root / ".worktrees" / branch
        try:
            created = create_worktree(
                branch,
                wt_path,
                repo=repo_root,
                start_point=resolve_start_point(
                    resolve_base_branch(repo_root), repo=repo_root
                ),
            )
            console.print(
                f"[green]WORKTREE[/] "
                f"{'detected at' if created != wt_path else 'created at'} "
                f"{created}"
            )
            worktree_path = str(created)
        except RuntimeError as e:
            console.print(f"[yellow]WORKTREE_ERROR[/] {e}")
            return None

        # ── Sync agent skill directories and config to worktree ────────
        _sync_worktree_assets(repo_root, Path(worktree_path))

        # ── Mise setup (after asset sync so .env is available) ─────────
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
            remote = _origin_remote(repo_root)

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
                commit_msg = format_commit_message(
                    f"chore({epic_num}-{issue_num}): claim {resolved_id}",
                    Path(worktree_path),
                )
                # --no-verify: claim only touches specs/issues.jsonl (not .py),
                # so hooks are no-ops; bypass avoids worktree hook config issues.
                subprocess.run(
                    [
                        "git",
                        "commit",
                        "--no-verify",
                        "-m",
                        commit_msg,
                    ],
                    cwd=worktree_path,
                    env=_git_env(),
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError:
                console.print("[yellow]COMMIT_CLAIM_SKIP[/] could not commit claim")

            if local:
                console.print("[yellow]LOCAL_ONLY[/] skipping push")
            else:
                pushed = _push_claim_with_collision_retry(
                    remote=remote,
                    branch=branch,
                    worktree_path=worktree_path,
                    repo_root=repo_root,
                    epic_slug=epic_slug,
                    issue_slug=issue_slug,
                    spec_target_rel=spec_target_rel,
                    force=force,
                )
                if pushed is None:
                    return None
                branch, issue_slug, spec_target_rel = pushed

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
    local: bool = False,
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
        local=_effective_local(local),
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
        _key_worktree_session_to_issue(wt_path, issue_id)

        console.print(f"[green]WORKTREE[/] setup at {wt_path}")
        console.print("[green]SESSION[/] advanced to PLAN")

    return Path(setup_result["worktree_path"])


@with_json_quiet
def _plan_pre(
    issue_id: str | None = None,
    force: bool = False,
    dry_run: bool = False,
    skip_auto_claim: bool = False,
) -> None:
    """Emit a plan-pre contract.

    *Not in a linked worktree* — auto-claim + setup:
      - ``issue_id`` given → claim that specific issue.
      - No ``issue_id`` → discover next unblocked BACKLOG issue.

    *Inside a linked worktree* — emit the JSON contract for the agent.
    """
    # ── Auto-claim + setup (not in linked worktree) ────────────────────
    if not skip_auto_claim and not _is_linked_worktree():
        rid = issue_id if issue_id is not None else _discover_unclaimed()
        _claim_and_setup(rid, force, dry_run)
        raise typer.Exit(code=0)

    # ── Contract mode (inside worktree or from _meso_run) ──────────────
    session, _ = _load_session_accept("SPECIFY", "PLAN", force=force)
    resolved_issue_id = (
        issue_id
        or session.active_issue_id
        or resolve_issue_id_from_branch(Path.cwd())
        or ""
    )
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
    contract: dict[str, object] = {
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


def _validate_or_repair_plan(content: str) -> tuple[list[str], str]:
    """Validate a plan contract; auto-fill a missing Verification Mode.

    When the contract fails *only* because scenarios lack a ``**Verification
    Mode**:`` line, inject the default ``automated`` value and return the
    repaired body with empty errors. Any other failure (invalid or duplicated
    mode, missing clauses, bad AO traceability) is returned unchanged so the
    caller rejects it.
    """
    errors = validate_acceptance_contract(content)
    if not errors:
        return [], content
    if not all(e.endswith("missing Verification Mode") for e in errors):
        return errors, content
    repaired, count = repair_missing_verification_mode(content)
    if count == 0:
        return errors, content
    console.print(
        f"[yellow]PLAN_MODE_REPAIR[/] auto-filled {count} missing "
        "**Verification Mode** line(s) as `automated`"
    )
    return validate_acceptance_contract(repaired), repaired


def _plan_post(force: bool = False, issue_id: str | None = None) -> None:
    """Validate plan.md, commit it, and advance session to TASKS."""
    session, session_path = _load_session_accept("PLAN", force=force)
    resolved_issue_id = (
        issue_id or session.active_issue_id or resolve_issue_id_from_branch(Path.cwd())
    )
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
    acceptance_errors, plan_content = _validate_or_repair_plan(content)
    if acceptance_errors:
        status = (
            "PLAN_ACCEPTANCE_CONTRACT_MISSING"
            if acceptance_errors == ["PLAN_ACCEPTANCE_CONTRACT_MISSING"]
            else "PLAN_ACCEPTANCE_CONTRACT_INVALID"
        )
        console.print(f"[red]{status}[/] {'; '.join(acceptance_errors)}")
        raise typer.Exit(code=1)
    if plan_content != content:
        plan_md.write_text(plan_content, encoding="utf-8")

    epic_num = _extract_epic_num(bucket)
    issue_num = _extract_issue_num(resolved_issue_id)
    try:
        sha = stage_and_commit(
            message=format_commit_message(
                f"docs({epic_num}-{issue_num}): create plan.md", Path.cwd()
            ),
            files=[plan_md],
            repo=Path.cwd(),
            no_verify=True,
        )
        if sha is None:
            console.print("[yellow]COMMIT_SKIP[/] plan.md — no changes to stage")
        else:
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

    issue_id = session.active_issue_id or resolve_issue_id_from_branch(Path.cwd()) or ""

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

    # Resolve tasks_target and plan_path (per-issue, not per-epic)
    tasks_target: str = ""
    plan_path: str = ""
    if issue_id:
        ledger_path = _resolve_specs_root() / "issues.jsonl"
        record = resolve_issue_record(issue_id, ledger_path)
        if record is not None:
            bucket = _resolve_bucket_dir(record.source_file)
            slug = _source_stem(record.source_file)
            tasks_target = str(_resolve_specs_root() / bucket / slug / "tasks.md")
            plan_path = str(_resolve_specs_root() / bucket / slug / "plan.md")

    # ── Enforce plan.md + acceptance-contract prerequisite ─────────
    if plan_path and not Path(plan_path).exists() and not force:
        status = "PLAN_NOT_FOUND"
        console.print(
            f"[red]PLAN_NOT_FOUND[/] {plan_path} — run deviate plan first "
            "(use --force to bypass)"
        )
    elif plan_path and Path(plan_path).exists():
        plan_text = Path(plan_path).read_text(encoding="utf-8")
        acceptance_errors, plan_text = _validate_or_repair_plan(plan_text)
        if plan_text != Path(plan_path).read_text(encoding="utf-8"):
            Path(plan_path).write_text(plan_text, encoding="utf-8")
        if acceptance_errors:
            missing = acceptance_errors == ["PLAN_ACCEPTANCE_CONTRACT_MISSING"]
            status = (
                "PLAN_ACCEPTANCE_CONTRACT_MISSING"
                if missing
                else "PLAN_ACCEPTANCE_CONTRACT_INVALID"
            )
            console.print(
                f"[red]{status}[/] {plan_path}: {'; '.join(acceptance_errors)}"
            )
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
        "plan_path": plan_path,
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
) -> None:
    session, session_path = _load_session_accept("TASKS", force=force)
    resolved_issue_id = (
        issue_id or session.active_issue_id or resolve_issue_id_from_branch(Path.cwd())
    )
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

    epic_num = _extract_epic_num(bucket)
    issue_num = _extract_issue_num(resolved_issue_id)
    try:
        sha = commit_artifact(
            tasks_md,
            format_commit_message(
                f"docs({epic_num}-{issue_num}): create tasks.md", Path.cwd()
            ),
            repo=Path.cwd(),
            no_verify=True,
        )
        if sha is None:
            console.print("[yellow]COMMIT_SKIP[/] tasks.md — no changes to stage")
        else:
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
    issue_id = session.active_issue_id or resolve_issue_id_from_branch(repo_root)
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

    # Gather metadata for PR body generation
    commit_titles = ""
    changed_files = ""
    diff_summary = ""
    try:
        log_result = subprocess.run(
            ["git", "log", f"{base_branch}..HEAD", "--oneline"],
            cwd=repo_root,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        )
        commit_titles = "|".join(
            line.split(" ", 1)[1] if " " in line else line
            for line in log_result.stdout.strip().splitlines()
            if line.strip()
        )
    except Exception:
        pass

    try:
        stat_result = subprocess.run(
            ["git", "diff", f"{base_branch}...HEAD", "--stat"],
            cwd=repo_root,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        )
        diff_summary = stat_result.stdout.strip()
        files_result = subprocess.run(
            ["git", "diff", f"{base_branch}...HEAD", "--name-only"],
            cwd=repo_root,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        )
        changed_files = ",".join(
            f for f in files_result.stdout.strip().splitlines() if f.strip()
        )
    except Exception:
        pass

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    contract = {
        "branch_name": branch_name,
        "base_branch": base_branch,
        "pr_title": pr_title,
        "pr_body": pr_body,
        "git_state": git_state,
        "issue_title": record.title,
        "commit_titles": commit_titles,
        "changed_files": changed_files,
        "diff_summary": diff_summary,
        "timestamp": timestamp,
        "status": "READY",
        "phase": "pr_pre",
    }
    print(json.dumps(contract, indent=2))


def _run_gt_submit(repo_root: Path, title: str, body_file: Path) -> None:
    try:
        result = subprocess.run(
            ["gt", "submit", "--stack", "--no-edit"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            env=_git_env(),
        )
    except FileNotFoundError:
        console.print(
            "[red]GT_SUBMIT_FAILED[/] Graphite CLI (gt) not found on PATH.\n"
            "See https://graphite.dev/docs/cli for installation instructions."
        )
        raise typer.Exit(code=1)
    if result.returncode != 0:
        console.print(
            f"[red]GT_SUBMIT_FAILED[/] {result.stderr.strip()}\n"
            "See https://graphite.dev/docs/cli for installation instructions."
        )
        raise typer.Exit(code=1)
    console.print(f"[green]GT_SUBMIT[/] {result.stdout.strip()}")
    _update_gt_prs(result.stdout, title, body_file, repo_root)


def _update_gt_prs(output: str, title: str, body_file: Path, repo_root: Path) -> None:
    for line in output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        pr_url_match = re.search(r"(https://github\.com/\S+/pull/\d+)", line)
        if not pr_url_match:
            continue
        pr_url = pr_url_match.group(1)
        pr_num_match = re.search(r"/(\d+)$", pr_url)
        if not pr_num_match:
            continue
        pr_number = pr_num_match.group(1)
        try:
            subprocess.run(
                [
                    "gh",
                    "pr",
                    "edit",
                    pr_number,
                    "--title",
                    title,
                    "--body-file",
                    str(body_file),
                ],
                capture_output=True,
                text=True,
                cwd=repo_root,
                env=_git_env(),
                check=True,
            )
            console.print(f"[green]PR_UPDATED[/] #{pr_number}")
        except subprocess.CalledProcessError as e:
            console.print(f"[yellow]PR_EDIT_WARN[/] #{pr_number}: {e.stderr.strip()}")


def _run_gh_pr_create(
    title: str,
    body_file: Path,
    merge: bool = False,
    auto_merge: bool = False,
    cwd: Path | None = None,
) -> None:
    cmd = ["gh", "pr", "create", "--title", title, "--body-file", str(body_file)]
    if merge:
        cmd.append("--merge")
    elif auto_merge:
        cmd.append("--auto-merge")
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=cwd, env=_git_env()
    )
    if result.returncode != 0:
        console.print(f"[red]PR_CREATE_FAILED[/] {result.stderr.strip()}")
        raise typer.Exit(code=1)
    pr_url = result.stdout.strip()
    console.print(f"[green]PR_CREATED[/] {pr_url}")


def _pr_run(
    body_file: Path,
    merge: bool = False,
    auto_merge: bool = False,
) -> None:
    session, session_path = _load_session_accept("TASKS", "IDLE")
    issue_id = session.active_issue_id or resolve_issue_id_from_branch(Path.cwd())
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
    title = _pr_title(issue_id, record.title, record.type)

    # 1. Record COMPLETED in the ledger before PR creation
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

    # 2. Stage the ledger and PR body file, then commit together
    staged = False
    for path in (str(ledger_path), str(body_file)):
        try:
            subprocess.run(
                ["git", "add", path],
                cwd=repo_root,
                env=_git_env(),
                check=True,
                capture_output=True,
                text=True,
            )
            staged = True
        except subprocess.CalledProcessError:
            pass
    if staged:
        try:
            subprocess.run(
                [
                    "git",
                    "commit",
                    "--no-verify",
                    "-m",
                    f"chore({commit_scope(issue_id)}): mark COMPLETED in ledger",
                ],
                cwd=repo_root,
                env=_git_env(),
                check=True,
                capture_output=True,
                text=True,
            )
            console.print("[green]LEDGER_COMMITTED[/]")
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip()
            if "nothing to commit" in stderr:
                console.print("[yellow]LEDGER_UNCHANGED[/] no ledger changes to commit")
            else:
                console.print(f"[yellow]COMMIT_LEDGER_WARN[/] {stderr}")
    else:
        console.print("[yellow]LEDGER_UNCHANGED[/] no files staged for commit")

    try:
        subprocess.run(
            ["git", "push", "-u", "origin", "HEAD"],
            cwd=repo_root,
            env=_git_env(),
            check=True,
            capture_output=True,
            text=True,
        )
        console.print("[green]BRANCH_PUSHED[/]")
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        if "does not exist" in stderr or "not found" in stderr:
            console.print(
                "[yellow]BRANCH_DELETED[/] remote branch gone after merge (expected)"
            )
        else:
            console.print(f"[yellow]PUSH_WARN[/] {stderr}")

    # 3. Create (and optionally merge) the PR
    if resolve_graphite_config(repo_root):
        if merge or auto_merge:
            console.print(
                "[yellow]GRAPHITE_MERGE_FLAGS_IGNORED[/] "
                "Graphite handles merge flow internally via `gt submit --stack`."
            )
        _run_gt_submit(repo_root, title, body_file)
    else:
        _run_gh_pr_create(title, body_file, merge, auto_merge, cwd=repo_root)

    _save_session(session, session_path, "TASKS")


# ---------------------------------------------------------------------------
# Meso automated pipeline
# ---------------------------------------------------------------------------


PLAN_DIGEST_MAX_BYTES = 16 * 1024


def _build_plan_digest(plan_path: Path) -> str:
    """Return bounded PLAN context while keeping both strategy and conclusions."""
    if not plan_path.exists():
        return ""

    content = plan_path.read_text(encoding="utf-8")
    encoded = content.encode("utf-8")
    if len(encoded) <= PLAN_DIGEST_MAX_BYTES:
        return content

    marker = (
        f"\n\n<!-- PLAN_DIGEST_TRUNCATED: read the full plan at {plan_path} -->\n\n"
    )
    marker_bytes = marker.encode("utf-8")
    remaining = PLAN_DIGEST_MAX_BYTES - len(marker_bytes)
    head_size = remaining // 2
    tail_size = remaining - head_size
    head = encoded[:head_size].decode("utf-8", errors="ignore")
    tail = encoded[-tail_size:].decode("utf-8", errors="ignore")
    return f"{head}{marker}{tail}"


def _invoke_agent_phase(
    phase: str,
    contract: dict[str, str],
    cwd: str | None = None,
) -> None:
    """Build a slim prompt, invoke the agent, and abort on failure."""
    prompt = _build_slim_prompt(phase, contract)
    try:
        root = Path(cwd) if cwd else Path.cwd()
        model = resolve_model_for_phase(phase, root)
        data = _load_deviate_config_toml(root)
        backend_name = "pi"
        if data:
            agent_data = data.get("agent", {})
            if isinstance(agent_data, dict) and isinstance(
                agent_data.get("backend"), str
            ):
                # Normalise user-facing aliases (``factory``, ``omp``) to
                # canonical backends before constructing AgentConfig —
                # the Pydantic ``backend`` Literal only accepts canonical
                # names (``opencode`` / ``claude`` / ``droid`` / ``pi``).
                backend_name = resolve_agent_to_backend(agent_data["backend"])
        agent_cfg = AgentConfig(
            backend=backend_name,
            timeout=(data.get("agent", {}).get("timeout", 600) if data else 600),
        )
        backend = AgentBackend(config=agent_cfg)
        model_str = f" --model {model}" if model else ""
        console.print(
            f"[green]INVOKE_AGENT[/] running '{backend_name}{model_str}'"
            f" for [{phase}] phase"
        )
        manifest = backend.invoke(prompt, cwd=cwd, model=model)
    except AgentSubprocessError as e:
        console.print(f"[red]{phase.upper()}_FAILED[/] {e}")
        raise SystemExit(1) from e
    if manifest.status != "PASS":
        console.print(
            f"[red]{phase.upper()}_FAILED[/] agent returned status: {manifest.status}"
        )
        raise SystemExit(1)


def _enforce_phase_artifact(phase: str, artifact_path: Path) -> None:
    """Fail-fast guard: agent returned PASS but the phase artifact is missing.

    Closes the false-success validation gap where ``_invoke_agent_phase``
    trusts ``manifest.status == "PASS"`` without verifying the agent
    actually wrote its deliverable. Distinct diagnostic code so logs
    distinguish "agent didn't do the work" from "agent wrote something
    invalid" (the latter is still caught by ``_plan_post`` / ``_tasks_post``).
    """
    if not artifact_path.exists() or artifact_path.stat().st_size == 0:
        console.print(
            f"[red]{phase.upper()}_NOT_WRITTEN[/] agent returned PASS but "
            f"{artifact_path} is missing or empty"
        )
        raise SystemExit(1)


def _meso_discover_and_sequence() -> str | None:
    ledger_path = _resolve_specs_root() / "issues.jsonl"
    issue = select_next_unblocked_issue(ledger_path)
    if issue is None:
        return None
    return issue.issue_id


def _origin_holds_claim_branch(
    candidate: IssueRecord, repo_root: Path, remote: str
) -> bool:
    """True when ``feat/{epic}/{issue}`` already exists on *remote*."""
    branch = (
        f"feat/{_resolve_bucket_dir(candidate.source_file)}"
        f"/{_source_stem(candidate.source_file)}"
    )
    return branch_exists_on_remote(branch, repo=repo_root, remote=remote)


def _discover_claimable_issue(local: bool = False) -> str | None:
    """Return the next unblocked BACKLOG issue this operator can claim.

    Default mode skips candidates whose ``feat/{epic}/{issue}`` branch already
    exists on origin (claimed elsewhere). Local mode skips that origin filter
    so leftover personal branches stay claimable, and does not call
    ``branch_exists_on_remote``.

    Returns the first claimable ``issue_id``, or ``None`` if none available.
    """
    ledger_path = _resolve_specs_root() / "issues.jsonl"
    repo_root = Path.cwd()
    candidates = select_unblocked_candidates(ledger_path)
    if not candidates:
        return None

    remote = None if local else _origin_remote(repo_root)
    for candidate in candidates:
        if _is_issue_completed(candidate.issue_id, ledger_path):
            continue
        if remote and _origin_holds_claim_branch(candidate, repo_root, remote):
            console.print(
                f"[yellow]SKIP[/] {candidate.issue_id} — "
                f"branch already on remote (claimed elsewhere)"
            )
            continue
        return candidate.issue_id
    return None


def _resolve_meso_resume_state(plan_path: Path, tasks_path: Path) -> str:
    """Return PLAN, TASKS, or COMPLETE; auto-repair a missing Verification Mode."""
    if plan_path.exists():
        plan_content = plan_path.read_text(encoding="utf-8")
        plan_errors, plan_content = _validate_or_repair_plan(plan_content)
        if plan_content != plan_path.read_text(encoding="utf-8"):
            plan_path.write_text(plan_content, encoding="utf-8")
        if plan_errors:
            console.print(
                f"[red]MESO_PLAN_INVALID[/] {plan_path}: {'; '.join(plan_errors)}"
            )
            raise typer.Exit(code=1)
        plan_ready = True
    else:
        plan_ready = False

    if tasks_path.exists():
        if not tasks_path.read_text(encoding="utf-8").strip():
            console.print(f"[red]MESO_TASKS_INVALID[/] {tasks_path}: empty file")
            raise typer.Exit(code=1)
        if not plan_ready:
            console.print(
                f"[red]MESO_TASKS_WITHOUT_PLAN[/] {tasks_path}: "
                "tasks.md requires a valid plan.md"
            )
            raise typer.Exit(code=1)
        return "COMPLETE"

    return "TASKS" if plan_ready else "PLAN"


def _silence_stdout(
    func: Callable[..., object], *args: object, **kwargs: object
) -> None:
    """Invoke ``func`` with stdout redirected to a discarded buffer.

    Used by ``_meso_run`` when calling ``_plan_pre`` / ``_tasks_pre``:
    those pre subcommands ``print()`` their JSON contract to stdout for the
    agent-subprocess CLI workflow, but ``_meso_run`` has already built its
    own contract and only needs the pre's logging side effects. Without
    this suppression the JSON dump would land on the user's terminal.
    """
    with redirect_stdout(StringIO()):
        func(*args, **kwargs)


@contextmanager
def _phase_callout(
    phase: str,
    task_id: str,
    task_description: str = "",
) -> Generator[None, None, None]:
    """Context manager that renders PhaseCallout IN_PROGRESS on enter,
    and COMPLETED or FAILED on exit depending on whether an exception
    (including SystemExit) was raised."""
    start = time.monotonic()
    console.print(
        PhaseCallout(
            phase=phase,
            task_id=task_id,
            task_description=task_description,
        ).render(status=PhaseMarker.IN_PROGRESS)
    )
    try:
        yield
    except BaseException:
        console.print(
            PhaseCallout(
                phase=phase,
                task_id=task_id,
                task_description=task_description,
            ).render(
                status=PhaseMarker.FAILED,
                duration_seconds=time.monotonic() - start,
            )
        )
        raise
    console.print(
        PhaseCallout(
            phase=phase,
            task_id=task_id,
            task_description=task_description,
        ).render(
            status=PhaseMarker.COMPLETED,
            duration_seconds=time.monotonic() - start,
        )
    )


def _key_worktree_session_to_issue(worktree_path: Path, issue_id: str) -> None:
    """Write claimed ``issue_id`` into ``worktree_path/.deviate/session.json``.

    Meso claim (AC-PLAN-006) and ``MESO_ALREADY_COMPLETE`` (AC-PLAN-005)
    both persist ``SessionState.active_issue_id`` so a leftover main-repo
    id cannot stick in the worktree session (constitution §2).
    """
    session_path = worktree_path / ".deviate" / "session.json"
    session = SessionState.load(session_path)
    if session.active_issue_id == issue_id:
        return
    session.active_issue_id = issue_id
    session.save(session_path)


def _resolve_meso_worktree(
    issue_id: str | None,
    force: bool,
    no_setup: bool,
    local: bool,
) -> Path:
    """Return the directory PLAN and TASKS run in.

    ``no_setup`` keeps PLAN plus TASKS in ``$CWD`` and skips ``_specify_pre``.
    Otherwise SPECIFY claims the issue and returns the new worktree path.
    ``local`` does not select the ``no_setup`` skip.
    """
    if no_setup:
        return Path.cwd().resolve()
    setup_result = _specify_pre(
        issue_id=issue_id, force=force, dry_run=False, local=local
    )
    return Path(setup_result["worktree_path"])


@with_json_quiet
def _meso_run(
    issue_id: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    no_setup: bool = False,
    local: bool = False,
) -> str | None:
    dot_dir = _resolve_dot_deviate()
    if not dot_dir.exists():
        _handle_missing_dot_dir("MESO")

    session_path = dot_dir / "session.json"
    ledger_path = _resolve_specs_root() / "issues.jsonl"
    effective_local = _effective_local(local)

    # ── Auto-detect: already inside a linked worktree? ──────────────────
    # When the operator is already inside the worktree that ``_specify_pre``
    # would have created, treat the run as a PLAN + TASKS continuation.
    # Auto-claim + a second worktree would clobber the existing branch and
    # violate the Git Isolation Principle. Skip the SPECIFY step and resolve
    # the active issue from the branch slug when no explicit ``--issue`` was
    # given. Operators can still force a fresh SPECIFY cycle by passing
    # ``--issue <other-id>`` (handled by the ``else`` branch below) or by
    # invoking ``deviate meso run`` from outside any worktree.
    if _is_linked_worktree() and issue_id is None and not no_setup:
        no_setup = True
        issue_id = resolve_issue_id_from_branch(Path.cwd())
        if issue_id:
            console.print(
                f"[green]WORKTREE_DETECTED[/] continuing PLAN + TASKS for "
                f"{issue_id} in current worktree (SPECIFY skipped)"
            )

    # ── Discover issue if not specified ──────────────────────────────
    if issue_id is None:
        discovered = _discover_claimable_issue(local=effective_local)
        if discovered is None:
            console.print(
                "[red]NO_CLAIMABLE_ISSUES[/] no unblocked BACKLOG issue "
                "available to claim"
            )
            raise SystemExit(1)
        issue_id = discovered

    # ── Check COMPLETED ──────────────────────────────────────────────
    if _is_issue_completed(issue_id, ledger_path):
        console.print(f"[red]ISSUE_COMPLETED[/] {issue_id} is already COMPLETED")
        raise SystemExit(1)

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

    epic_slug = _resolve_bucket_dir(record.source_file)
    issue_slug = _source_stem(record.source_file)
    issue_title = record.title

    _pipeline_start = time.monotonic()
    if no_setup:
        console.print(
            "[bold][yellow]WARN[/] --no-setup: skipping SPECIFY (no worktree, "
            "no ledger claim).\n"
            "PLAN + TASKS will run in [bold]$CWD[/]; post-hook commits will "
            "land plan.md / tasks.md on the\n"
            "branch currently checked out. This bypasses the project's Git "
            "Isolation Principle (every task loop runs on a clean branch/worktree)."
        )

    # ── Dry-run mode ─────────────────────────────────────────────────
    if dry_run:
        contract: dict[str, str] = {
            "issue_id": issue_id,
            "issue_title": issue_title,
            "epic_slug": epic_slug,
            "issue_slug": issue_slug,
        }
        console.print("[bold][yellow]DRY_RUN[/] — no state will be mutated[/]")
        prompt = _build_slim_prompt("tasks", contract)
        print(prompt)
        return None  # dry-run: no worktree to drain

    # ── Setup step: create worktree and claim issue ──────────────────
    worktree_path = _resolve_meso_worktree(
        issue_id=issue_id,
        force=force,
        no_setup=no_setup,
        local=effective_local,
    )

    dot_dir = _resolve_dot_deviate()
    session_path = (dot_dir / "session.json").resolve()

    # Sync .deviate/ to worktree so downstream functions find the session.
    # Write-then-copy keys the source session first; rewrite after copy
    # when the copied file still names a previous issue (AC-PLAN-006).
    if dot_dir.exists() and not no_setup:
        _key_worktree_session_to_issue(dot_dir.parent, issue_id)
        shutil.copytree(
            str(dot_dir), str(worktree_path / ".deviate"), dirs_exist_ok=True
        )
        _key_worktree_session_to_issue(worktree_path, issue_id)

    # Build contract with absolute worktree paths so agent writes files
    # to the exact worktree location regardless of tool re-rooting.
    src_file = record.source_file if record else ""
    spec_path = src_file if src_file.startswith("/") else str(worktree_path / src_file)
    plan_dir = worktree_path / "specs" / epic_slug / issue_slug
    tasks_dir = worktree_path / "specs" / epic_slug / issue_slug
    plan_dir.mkdir(parents=True, exist_ok=True)
    tasks_dir.mkdir(parents=True, exist_ok=True)
    contract: dict[str, object] = {
        "issue_id": issue_id,
        "issue_title": issue_title,
        "epic_slug": epic_slug,
        "issue_slug": issue_slug,
        "worktree_full": str(worktree_path),
        "spec_path": spec_path,
        "plan_path": str(plan_dir / "plan.md"),
        "tasks_target": str(tasks_dir / "tasks.md"),
    }

    plan_path = plan_dir / "plan.md"
    tasks_path = tasks_dir / "tasks.md"
    resume_state = (
        _resolve_meso_resume_state(plan_path, tasks_path) if no_setup else "PLAN"
    )

    if resume_state == "COMPLETE":
        _key_worktree_session_to_issue(worktree_path, issue_id)
        console.print(
            f"[green]MESO_ALREADY_COMPLETE[/] {issue_id}: valid plan.md and "
            "tasks.md already exist"
        )
        return str(worktree_path)

    if resume_state == "TASKS":
        steps = ("TASKS",)
    elif no_setup:
        steps = ("PLAN", "TASKS")
    else:
        steps = ("SPECIFY", "PLAN", "TASKS")
    console.print(
        PipelineBanner(
            issue_id=issue_id,
            issue_title=issue_title,
            epic_slug=epic_slug,
            issue_slug=issue_slug,
            steps=steps,
        ).render()
    )
    if resume_state == "TASKS":
        console.print(
            f"[green]MESO_RESUME[/] {issue_id}: valid plan.md found; resuming at TASKS"
        )

    if record.status not in ("BACKLOG", "DRAFT") and resume_state == "PLAN":
        console.print(
            f"[yellow]PROGRESS_RESET[/] {issue_id} ({record.status})"
            " — resetting to BACKLOG"
        )
        reset = record.model_copy(update={"status": "BACKLOG"})
        append_issue_transition(reset, ledger_path)

    initial_phase = "TASKS" if resume_state == "TASKS" else "PLAN"
    session = SessionState.load(session_path)
    if session.current_phase != initial_phase:
        session = session.force_transition_to(initial_phase)
    session.active_issue_id = issue_id
    session.save(session_path)

    ctx = chdir(worktree_path)
    with ctx:
        if resume_state == "PLAN":
            with _phase_callout("PLAN", issue_id, issue_title):
                _silence_stdout(
                    _plan_pre, force=force, dry_run=False, skip_auto_claim=no_setup
                )
                _invoke_agent_phase("plan", contract, cwd=str(worktree_path))
                _enforce_phase_artifact("plan", plan_path)
                _plan_post(force=force, issue_id=issue_id)

        contract["plan_digest"] = _build_plan_digest(plan_path)

        with _phase_callout("TASKS", issue_id, issue_title):
            _silence_stdout(_tasks_pre, force=force, dry_run=False)
            _invoke_agent_phase("tasks", contract, cwd=str(worktree_path))
            _enforce_phase_artifact("tasks", tasks_path)
            _tasks_post(force=force, issue_id=issue_id)

        session = SessionState.load(session_path)
        if session.current_phase != "IDLE":
            session = session.force_transition_to("IDLE")
            session.save(session_path)
    console.print(
        PipelineSummary.render(
            total=1,
            completed=1,
            failed=0,
            duration_seconds=time.monotonic() - _pipeline_start,
            pipeline_status="completed",
            include_meso_footer=True,
        )
    )
    # Return the worktree path so the top-level `deviate run` orchestrator
    # can ``chdir`` into it and dispatch `deviate micro run --all` without
    # having to re-derive the path from the session/ledger. ``meso_app run``
    # discards this return value — JSON mode serializes a plain string.
    return str(worktree_path)


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
    quiet: bool = typer.Option(
        False,
        "--quiet/--verbose",
        help="Suppress non-essential output (default: verbose)",
    ),
    no_setup: bool = typer.Option(
        False,
        "--no-setup",
        help=(
            "Skip the SPECIFY step (worktree + ledger claim). PLAN and TASKS run "
            "in the current directory; _plan_post / _tasks_post will commit to "
            "the currently checked-out branch. Bypasses Git Isolation Principle."
        ),
    ),
    local: bool = typer.Option(
        False,
        "--local",
        help=_LOCAL_CLAIM_HELP,
    ),
) -> None:
    """Run the meso automated pipeline (setup → plan → tasks)"""
    _meso_run(
        issue_id=issue,
        dry_run=dry_run,
        force=force,
        quiet=quiet,
        no_setup=no_setup,
        local=local,
    )


# ---------------------------------------------------------------------------
# CLI command entry points
# ---------------------------------------------------------------------------


def specify(
    issue_id: str | None = typer.Argument(
        None,
        help=(
            "Issue ID to claim. Omit to auto-discover the next unblocked BACKLOG "
            "issue via select_next_unblocked_issue(). Also accepts 'pre' / 'post' "
            "as agent-internal dispatch sentinels."
        ),
    ),
    force: bool = typer.Option(
        False, "--force", help="Force operation (bypass push failure)"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Resolve issue and emit contract without creating worktree or claiming",
    ),
    local: bool = typer.Option(
        False,
        "--local",
        help="Claim locally only: create worktree, write ledger, commit; skip remote check and push. If the local branch already exists, treat as already claimed.",
    ),
    issue: str | None = typer.Option(
        None, "--issue", help="Issue ID for pre subcommand"
    ),
) -> None:
    """Claim an issue and create its worktree.

    With no argument, auto-discovers the next unblocked BACKLOG issue and
    claims it. With an explicit issue ID, claims that specific issue. Stops
    after the worktree is created and the claim is committed — does NOT
    advance session state and does NOT run plan or tasks. To advance from
    the claim, run ``deviate plan pre`` or invoke the ``/deviate-plan`` slash
    command inside the new worktree.
    """
    if issue_id == "pre":
        _specify_pre(issue_id=issue, force=force, dry_run=dry_run, local=local)
    elif issue_id == "post":
        _specify_post(force=force)
    elif issue_id is None:
        discovered = _discover_claimable_issue(local=_effective_local(local))
        if discovered is None:
            console.print(
                "[red]NO_CLAIMABLE_ISSUES[/] no unblocked BACKLOG issue ",
                "available to claim",
            )
            raise typer.Exit(code=1)
        _specify_pre(
            issue_id=discovered,
            force=force,
            dry_run=dry_run,
            local=local,
        )
    else:
        _specify_pre(issue_id=issue_id, force=force, dry_run=dry_run, local=local)


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
) -> None:
    """Tasks phase: pre (detect worktree) or post (validate, commit)"""
    if issue_id == "pre":
        _tasks_pre(force=force, dry_run=dry_run)
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


# ---------------------------------------------------------------------------
# Merge — mark issue COMPLETED after external merge (e.g. squash-merge skill)
# ---------------------------------------------------------------------------


def _merge_run(
    issue_id: str | None = None,
    delete_branch: bool = False,
    delete_worktree: bool = False,
    stage_only: bool = False,
    message: list[str] | None = None,
) -> None:
    """Mark an issue COMPLETED in the ledger with a full IssueRecord.

    Intended for use after an external merge (e.g. the /squash-merge skill)
    that does not write DeviaTDD-compatible ledger entries.  Unlike the bare
    ``{issue_id, status, timestamp}`` format, this writes a full record that
    ``resolve_issue_record`` can always validate.

    When *stage_only* is True, the ledger is written and ``git add``-ed but
    NOT committed — the caller is expected to fold it into a squash-merge
    commit.  Cleanup and session-reset are also skipped so a subsequent
    ``--delete-branch`` pass can handle them.

    When *message* is provided, ``git add -A`` includes pre-staged feature
    changes, and the first element is routed through ``format_commit_message``
    (applying the project's emoji convention) with the rest passed verbatim
    as body paragraphs.
    """
    session, session_path = _load_session_accept("TASKS", "IDLE", force=True)
    if issue_id is None:
        issue_id = session.active_issue_id or resolve_issue_id_from_branch(Path.cwd())
    if not issue_id:
        console.print("[red]NO_ACTIVE_ISSUE[/] session has no active_issue_id")
        raise typer.Exit(code=1)

    ledger_path = _resolve_specs_root() / "issues.jsonl"
    record = resolve_issue_record(issue_id, ledger_path)
    if record is None:
        console.print(f"[red]ISSUE_NOT_FOUND[/] {issue_id}")
        raise typer.Exit(code=1)

    # Ensure the ledger has the COMPLETED transition (idempotent — handles
    # both the first --stage-only call and the subsequent --message call
    # which sees the already-COMPLETED record).
    if record.status != "COMPLETED":
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

    # ── Flow confirmation: append FLOW_CONFIRMED_IMPLEMENTED events
    # for every flow_ref on the issue, then stage the flows ledger
    # alongside the issues ledger.  The helper is a pure ledger op
    # (no git) and is idempotent on
    # (flow_id, event_type, event_issue_id, evidence_path=None), so
    # re-running merge (or --stage-only followed by --message)
    # produces no duplicate events.  Skip-banner policy:
    #   * No flow_refs on the issue: emit NO_FLOW_REFS, no ledger write.
    #   * Skipped_refs (malformed tokens): ORPHANED_FLOW_REF_SKIPPED.
    #   * Idempotent re-runs: emit per-flow CONFIRMED banner on the
    #     first call and LEDGER_IDEMPOTENT on subsequent calls.
    flows_ledger_path = _resolve_specs_root() / "_product" / "flows.jsonl"
    flows_ledger_existed_before = flows_ledger_path.exists()
    confirmation: FlowConfirmationResult = _confirm_implemented_flows(
        issue_id=issue_id,
        issues_ledger=ledger_path,
        flows_ledger=flows_ledger_path,
    )
    if not confirmation.flow_ids:
        if record.flow_refs:
            # Issue carried flow_refs but the helper skipped all of
            # them (e.g. malformed tokens).  Surface so the operator
            # can correct the issue frontmatter.
            for ref in confirmation.skipped_refs:
                console.print(f"[yellow]ORPHANED_FLOW_REF_SKIPPED[/] {ref}")
        else:
            console.print(
                f"[yellow]NO_FLOW_REFS[/] {issue_id} — no flow confirmations emitted"
            )
    else:
        for ref in confirmation.flow_ids:
            console.print(f"[green]CONFIRMED[/] {ref}")
        if confirmation.appended_count < len(confirmation.flow_ids):
            console.print(
                f"[yellow]LEDGER_IDEMPOTENT[/] "
                f"{len(confirmation.flow_ids) - confirmation.appended_count} "
                f"flow event(s) already recorded for {issue_id}"
            )

    # Stage the issues ledger.
    repo_root = Path.cwd()
    try:
        subprocess.run(
            ["git", "add", str(ledger_path)],
            cwd=repo_root,
            env=_git_env(),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        if "nothing to commit" in stderr:
            console.print("[yellow]LEDGER_UNCHANGED[/]")
        else:
            console.print(f"[yellow]STAGE_WARN[/] {stderr}")
        raise typer.Exit(code=1)

    # Stage the flows ledger if the helper created or appended to it.
    if flows_ledger_path.exists() and (
        not flows_ledger_existed_before or confirmation.appended_count > 0
    ):
        try:
            subprocess.run(
                ["git", "add", str(flows_ledger_path)],
                cwd=repo_root,
                env=_git_env(),
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip()
            if "nothing to commit" in stderr:
                console.print("[yellow]FLOWS_LEDGER_UNCHANGED[/]")
            else:
                console.print(f"[yellow]FLOWS_STAGE_WARN[/] {stderr}")
            # Non-fatal: the issues ledger already staged.  Continue
            # so the operator can fix the flows ledger path on a
            # follow-up commit.

    # Commit (only when not --stage-only). Pulled out of the COMPLETED
    # branch above so --stage-only followed by --message produces a single
    # combined commit regardless of the ALREADY_COMPLETED state.
    if not stage_only:
        try:
            if message:
                # Custom message: combined commit (feature + ledger).
                subprocess.run(
                    ["git", "add", "-A"],
                    cwd=repo_root,
                    env=_git_env(),
                    check=True,
                    capture_output=True,
                    text=True,
                )
                subject = format_commit_message(message[0], repo_root)
                cmd: list[str] = ["git", "commit", "-m", subject]
                for body in message[1:]:
                    cmd.extend(["-m", body])
            else:
                subject = format_commit_message(
                    f"chore({commit_scope(issue_id)}): mark COMPLETED in ledger",
                    repo_root,
                )
                cmd = ["git", "commit", "-m", subject]
            subprocess.run(
                cmd,
                cwd=repo_root,
                env=_git_env(),
                check=True,
                capture_output=True,
                text=True,
            )
            console.print("[green]COMMITTED[/]")
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip()
            if "nothing to commit" in stderr:
                console.print("[yellow]LEDGER_UNCHANGED[/]")
            else:
                console.print(f"[yellow]COMMIT_WARN[/] {stderr}")
    else:
        console.print("[green]LEDGER_STAGED[/]")
    if not stage_only:
        if delete_worktree:
            worktree_path = Path.cwd()
            if _is_linked_worktree(worktree_path):
                remove_worktree(worktree_path)
                console.print(f"[green]WORKTREE_REMOVED[/] {worktree_path}")
            else:
                console.print("[yellow]SKIP_WORKTREE[/] not in a linked worktree")

        if delete_branch:
            branch_name = (
                f"feat/{_resolve_bucket_dir(record.source_file)}"
                f"/{_source_stem(record.source_file)}"
            )
            archive_tag = (
                f"archive/{issue_id}/{datetime.now(timezone.utc).date().isoformat()}"
            )
            # If the branch is checked out in a worktree, remove that
            # worktree first so ``git branch -D`` does not fail with
            # "branch ... used by worktree".
            try:
                wt_list = subprocess.run(
                    ["git", "worktree", "list", "--porcelain"],
                    cwd=Path.cwd(),
                    env=_git_env(),
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout
                wt_path_str: str | None = None
                for block in wt_list.split("\n\n"):
                    if f"branch refs/heads/{branch_name}" in block:
                        for line in block.splitlines():
                            if line.startswith("worktree "):
                                wt_path_str = line.split(" ", 1)[1]
                                break
                        break
                if wt_path_str and Path(wt_path_str).exists():
                    subprocess.run(
                        ["git", "worktree", "remove", "--force", wt_path_str],
                        cwd=Path.cwd(),
                        env=_git_env(),
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    console.print(f"[green]WORKTREE_REMOVED[/] {wt_path_str}")
            except subprocess.CalledProcessError:
                # ``git worktree list`` failed — fall through and try to
                # delete the branch anyway.
                pass
            # Tag the pre-squash branch tip before deletion so the full
            # commit history stays recoverable. ``git merge --squash``
            # collapses every feature commit into one main commit — the
            # archive tag is the only link back to the per-commit graph.
            try:
                subprocess.run(
                    ["git", "tag", archive_tag, branch_name],
                    cwd=Path.cwd(),
                    env=_git_env(),
                    check=True,
                    capture_output=True,
                    text=True,
                )
                console.print(f"[green]ARCHIVE_TAG[/] {archive_tag}")
            except subprocess.CalledProcessError as e:
                console.print(
                    f"[yellow]ARCHIVE_TAG_SKIP[/] {branch_name}: "
                    f"{(e.stderr or '').strip()}"
                )
            # Best-effort: push the tag and delete the remote branch.
            # Skip silently when ``origin`` is not configured; surface
            # ``PUSH_WARN`` and continue when the remote is unreachable
            # or returns an error so local cleanup still proceeds.
            try:
                remote_check = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    cwd=Path.cwd(),
                    env=_git_env(),
                    capture_output=True,
                    text=True,
                )
                if remote_check.returncode == 0:
                    try:
                        subprocess.run(
                            ["git", "push", "origin", archive_tag],
                            cwd=Path.cwd(),
                            env=_git_env(),
                            check=True,
                            capture_output=True,
                            text=True,
                        )
                        console.print(
                            f"[green]ARCHIVE_PUSHED[/] {archive_tag} -> origin"
                        )
                    except subprocess.CalledProcessError as e:
                        console.print(
                            f"[yellow]PUSH_WARN[/] tag push failed: "
                            f"{(e.stderr or '').strip()}"
                        )
                    try:
                        subprocess.run(
                            [
                                "git",
                                "push",
                                "origin",
                                "--delete",
                                branch_name,
                            ],
                            cwd=Path.cwd(),
                            env=_git_env(),
                            check=True,
                            capture_output=True,
                            text=True,
                        )
                        console.print(
                            f"[green]REMOTE_BRANCH_DELETED[/] origin/{branch_name}"
                        )
                    except subprocess.CalledProcessError as e:
                        stderr = (e.stderr or "").strip()
                        # "remote ref does not exist" / "could not find" on an
                        # already-gone branch is the expected post-merge state
                        # — not a warning.
                        if (
                            "not found" in stderr
                            or "does not exist" in stderr
                            or "could not find" in stderr
                        ):
                            console.print(
                                f"[yellow]REMOTE_BRANCH_SKIP[/] "
                                f"origin/{branch_name} already gone"
                            )
                        else:
                            console.print(
                                f"[yellow]PUSH_WARN[/] remote branch delete "
                                f"failed: {stderr}"
                            )
            except Exception:
                # ``git remote get-url`` itself failed — skip remote ops.
                pass
            try:
                subprocess.run(
                    ["git", "branch", "-D", branch_name],
                    cwd=Path.cwd(),
                    env=_git_env(),
                    check=True,
                    capture_output=True,
                    text=True,
                )
                console.print(f"[green]BRANCH_DELETED[/] {branch_name}")
            except subprocess.CalledProcessError:
                console.print(f"[yellow]BRANCH_SKIP[/] {branch_name} not found locally")
        session.active_issue_id = None
        session.current_phase = "IDLE"
        _save_session(session, session_path, "IDLE")


def merge(
    issue: str | None = typer.Option(
        None, "--issue", help="Issue ID to mark completed"
    ),
    delete_branch: bool = typer.Option(
        False, "--delete-branch", help="Delete the feature branch"
    ),
    delete_worktree: bool = typer.Option(
        False, "--delete-worktree", help="Remove the worktree"
    ),
    stage_only: bool = typer.Option(
        False,
        "--stage-only",
        help="Append to ledger and stage, but do not commit (for folding into squash-merge commit)",
    ),
    message: list[str] = typer.Option(
        [],
        "-m",
        "--message",
        help="Commit message. The first -m is the subject (formatted via "
        "the project's emoji convention); remaining -m values are passed "
        "verbatim as body paragraphs. Repeat the flag for each paragraph.",
    ),
) -> None:
    """Mark an issue COMPLETED after an external merge (e.g. squash-merge)."""
    _merge_run(
        issue_id=issue,
        delete_branch=delete_branch,
        delete_worktree=delete_worktree,
        stage_only=stage_only,
        message=message,
    )
