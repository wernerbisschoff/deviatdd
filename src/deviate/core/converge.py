"""Issue-scoped Converge helpers: readiness, pack detect, append-only writes."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from deviate.cli._common import _extract_issue_num
from deviate.core.issues import resolve_issue_artifact_path
from deviate.core.review_coverage import (
    resolve_issue_brief_path,
    resolve_issue_plan_path,
    resolve_review_issue_id,
)
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord, append_task_record

TAXONOMY = frozenset({"missing", "partial", "contradicts", "unrequested"})
LEDGER_APPEND_FAILED = "LEDGER_APPEND_FAILED"
CONVERGE_NOT_READY = "CONVERGE_NOT_READY"

_PHASE_RE = re.compile(r"^## Phase (\d+)\b", re.MULTILINE)
_TASK_ID_RE = re.compile(r"TSK-(\d{3})-(\d{2})")
_PATH_RE = re.compile(r"(?:^|[\s`\"'(])((?:src|tests)/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)")
_UNFILLED_CONSTITUTION_RE = re.compile(r"(?m)^>\s*TBD\b|\$\{[A-Z_]+\}")
_MUST_RE = re.compile(r"\bMUST\b")

_PACK_COMMAND_REL = (
    Path(".opencode") / "commands" / "deviate-converge.md",
    Path(".claude") / "commands" / "deviate-converge.md",
    Path(".factory") / "commands" / "deviate-converge.md",
    Path(".omp") / "commands" / "deviate-converge.md",
    Path(".pi") / "skills" / "deviate-converge" / "SKILL.md",
    Path(".agents") / "skills" / "deviate-converge" / "SKILL.md",
)


@dataclass(frozen=True)
class ConvergenceFinding:
    taxonomy: str
    source_ref: str
    summary: str
    severity: str | None = None


@dataclass
class ConvergeApplyResult:
    status: Literal["CONVERGED", "APPENDED"]
    task_ids: list[str] = field(default_factory=list)
    phase: int | None = None
    error: str | None = None


def converge_pack_available(root: Path) -> bool:
    """True when the optional converge slash/skill file is installed."""
    return any((root / rel).is_file() for rel in _PACK_COMMAND_REL)


def resolve_converge_issue_id(root: Path) -> str | None:
    session_path = root / ".deviate" / "session.json"
    if session_path.is_file():
        try:
            issue_id = SessionState.load(session_path).active_issue_id
        except (OSError, ValueError, json.JSONDecodeError):
            issue_id = ""
        if issue_id:
            return issue_id
    from deviate.cli._common import _get_current_branch

    return resolve_review_issue_id(root, _get_current_branch(root))


def resolve_issue_tasks_path(root: Path, issue_id: str | None) -> Path | None:
    if not issue_id:
        return None
    brief = resolve_issue_brief_path(root, issue_id)
    if brief is None:
        return None
    source = _latest_source_file(root, issue_id)
    if not source:
        return None
    path = resolve_issue_artifact_path(root, source, "tasks.md")
    return path if path.is_file() else None


def _latest_source_file(root: Path, issue_id: str) -> str | None:
    from deviate.core.review_coverage import _latest_source_file as _latest

    return _latest(root, issue_id)


def constitution_is_filled(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    if _UNFILLED_CONSTITUTION_RE.search(text):
        return False
    return bool(_MUST_RE.search(text))


def extract_in_scope_paths(*texts: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for match in _PATH_RE.finditer(text):
            path = match.group(1)
            if path not in seen:
                seen.add(path)
                found.append(path)
    return found


def pending_task_ids(root: Path, issue_id: str | None) -> list[str]:
    from deviate.cli.micro import _find_all_pending_tasks

    pending = _find_all_pending_tasks(root, issue_id=issue_id)
    return [str(rec.get("id")) for rec, _ in pending if rec.get("id")]


def max_phase_number(tasks_text: str) -> int:
    numbers = [int(match.group(1)) for match in _PHASE_RE.finditer(tasks_text)]
    return max(numbers, default=0)


def next_task_ids(issue_id: str, tasks_text: str, count: int) -> list[str]:
    ordinal = _extract_issue_num(issue_id).zfill(3)
    used = [int(match.group(2)) for match in _TASK_ID_RE.finditer(tasks_text)]
    start = (max(used) + 1) if used else 1
    return [f"TSK-{ordinal}-{n:02d}" for n in range(start, start + count)]


def sort_findings(findings: list[ConvergenceFinding]) -> list[ConvergenceFinding]:
    return sorted(
        findings,
        key=lambda item: 0 if (item.severity or "").upper() == "CRITICAL" else 1,
    )


def parse_findings_payload(raw: str | None) -> list[ConvergenceFinding]:
    if raw is None or not raw.strip():
        return []
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("findings payload is not valid JSON") from exc
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("findings", [])
    else:
        raise ValueError("findings payload must be an object or list")
    if not isinstance(items, list):
        raise ValueError("findings must be a list")
    parsed: list[ConvergenceFinding] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("each finding must be an object")
        taxonomy = str(item.get("taxonomy", "")).strip()
        if taxonomy not in TAXONOMY:
            raise ValueError(
                f"invalid taxonomy {taxonomy!r}; expected one of {sorted(TAXONOMY)}"
            )
        source_ref = str(item.get("source_ref", "")).strip()
        summary = str(item.get("summary", "")).strip()
        if not source_ref or not summary:
            raise ValueError("each finding needs source_ref and summary")
        severity = item.get("severity")
        parsed.append(
            ConvergenceFinding(
                taxonomy=taxonomy,
                source_ref=source_ref,
                summary=summary,
                severity=str(severity) if severity else None,
            )
        )
    return sort_findings(parsed)


def build_pre_contract(root: Path) -> tuple[dict[str, Any], int]:
    """Return ``(contract_or_empty, exit_code)``.

    On NOT_READY the contract is empty and the caller prints a diagnostic.
    """
    issue_id = resolve_converge_issue_id(root)
    brief = resolve_issue_brief_path(root, issue_id)
    plan = resolve_issue_plan_path(root, issue_id)
    tasks = resolve_issue_tasks_path(root, issue_id)
    pending = pending_task_ids(root, issue_id)

    if brief is None:
        return (
            {
                "status": "NOT_READY",
                "readiness": "missing_brief",
                "message": f"{CONVERGE_NOT_READY} missing issue brief",
            },
            1,
        )
    if plan is None:
        return (
            {
                "status": "NOT_READY",
                "readiness": "missing_plan",
                "message": f"{CONVERGE_NOT_READY} missing plan.md",
            },
            1,
        )
    if tasks is None:
        return (
            {
                "status": "NOT_READY",
                "readiness": "missing_tasks",
                "message": f"{CONVERGE_NOT_READY} missing tasks.md",
            },
            1,
        )
    if pending:
        return (
            {
                "status": "NOT_READY",
                "readiness": "queue_not_drained",
                "issue_id": issue_id,
                "pending_task_ids": pending,
                "message": (
                    f"{CONVERGE_NOT_READY} issue queue not drained; "
                    f"pending {', '.join(pending)}"
                ),
            },
            1,
        )

    brief_text = brief.read_text(encoding="utf-8")
    plan_text = plan.read_text(encoding="utf-8")
    tasks_text = tasks.read_text(encoding="utf-8")
    contract: dict[str, Any] = {
        "status": "READY",
        "readiness": "ready",
        "issue_id": issue_id,
        "issue_brief_path": str(brief.resolve()),
        "plan_path": str(plan.resolve()),
        "tasks_path": str(tasks.resolve()),
        "in_scope_paths": extract_in_scope_paths(plan_text, tasks_text, brief_text),
        "pending_task_ids": [],
    }
    const_path = root / "specs" / "constitution.md"
    if constitution_is_filled(const_path):
        contract["constitution_path"] = str(const_path.resolve())
    from datetime import datetime, timezone

    contract["timestamp"] = datetime.now(timezone.utc).isoformat()
    return contract, 0


def _task_card(task_id: str, finding: ConvergenceFinding) -> str:
    justify = ""
    if finding.taxonomy == "unrequested":
        justify = " Review, justify, or remove — do not auto-delete code."
    return (
        f"- [ ] {task_id}: {finding.summary}\n"
        f"  - **Type**: Feature\n"
        f"  - **Mode**: TDD\n"
        f"  - **Test Strategy**: unit\n"
        f"  - **Rationale**: {finding.taxonomy} — {finding.source_ref}.{justify}\n"
    )


def apply_findings(
    root: Path,
    findings: list[ConvergenceFinding],
    *,
    append_record=append_task_record,
) -> ConvergeApplyResult:
    if not findings:
        return ConvergeApplyResult(status="CONVERGED")
    issue_id = resolve_converge_issue_id(root)
    tasks_path = resolve_issue_tasks_path(root, issue_id)
    if tasks_path is None or not issue_id:
        return ConvergeApplyResult(
            status="CONVERGED",
            error=f"{CONVERGE_NOT_READY} missing tasks.md",
        )
    original = tasks_path.read_bytes()
    text = original.decode("utf-8")
    phase = max_phase_number(text) + 1
    source = _latest_source_file(root, issue_id)
    if not source:
        return ConvergeApplyResult(
            status="CONVERGED",
            error=f"{CONVERGE_NOT_READY} missing issue source",
        )
    ledger_path = resolve_issue_artifact_path(root, source, "tasks.jsonl")
    ledger_text = (
        ledger_path.read_text(encoding="utf-8") if ledger_path.is_file() else ""
    )
    ids = next_task_ids(issue_id, f"{text}\n{ledger_text}", len(findings))
    records: list[TaskRecord] = []
    for task_id, finding in zip(ids, findings, strict=True):
        records.append(
            TaskRecord(
                id=task_id,
                issue_id=issue_id,
                description=f"{finding.taxonomy} {finding.source_ref}: {finding.summary}",
                status="PENDING",
                execution_mode="TDD",
                test_strategy="unit",
            )
        )
    try:
        for record in records:
            if not append_record(record, ledger_path):
                raise OSError(f"duplicate or rejected {record.id}")
    except OSError as exc:
        return ConvergeApplyResult(
            status="CONVERGED",
            error=f"{LEDGER_APPEND_FAILED} {exc}",
        )
    cards = "".join(
        _task_card(task_id, finding)
        for task_id, finding in zip(ids, findings, strict=True)
    )
    section = (
        f"\n## Phase {phase}: Convergence\n"
        f"**Goal**: Close present-state gaps against this issue brief, "
        f"plan AC-PLAN, and constitution MUST\n\n"
        f"### Tasks\n\n"
        f"{cards}"
    )
    tasks_path.write_text(text + section, encoding="utf-8")
    return ConvergeApplyResult(status="APPENDED", task_ids=ids, phase=phase)


def run_converge_pass(root: Path) -> str:
    """One converge assessment step for ``deviate run``.

    Default is a CONVERGE_READY handoff (slash/agent assesses, ``post`` applies).
    Tests patch this to return ``appended`` / ``converged``.
    """
    contract, code = build_pre_contract(root)
    if code != 0:
        return "not_ready"
    print("CONVERGE_READY")
    print(json.dumps(contract, indent=2))
    return "handoff"
