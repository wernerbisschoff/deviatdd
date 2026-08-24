"""Runner-owned Gate 3 plan-AC coverage (no agent call)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deviate.core.issues import resolve_issue_artifact_path
from deviate.core.judge_evidence import _AC_TOKEN, resolve_task_ac_tokens
from deviate.state.ledger import _read_ledger

_BRANCH_SLUG_RE = re.compile(r"^feat/([^/]+)/([^/]+(?:/[^/]+)*)$")
_TASK_HEAD_RE = re.compile(r"^- (?:\[(?:x| )\]\s+)?(TSK-\d{3}-\d{2}):")
_COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class ReviewCoverage:
    """Plan-token coverage for one issue at Gate 3."""

    issue_id: str | None
    plan_tokens: list[str]
    claimed: list[str]
    uncovered: list[str]

    @property
    def complete(self) -> bool:
        return not self.uncovered


def resolve_review_issue_id(
    repo_path: Path | None = None,
    branch_name: str | None = None,
) -> str | None:
    """Map ``feat/<bucket>/<slug>`` to the matching ``issues.jsonl`` id."""
    if not branch_name:
        return None
    match = _BRANCH_SLUG_RE.match(branch_name)
    if match is None:
        return None
    root = repo_path or Path.cwd()
    target = f"{match.group(1)}/issues/{match.group(2)}.md"
    ledger = root / "specs" / "issues.jsonl"
    if not ledger.exists():
        return None
    for rec in _read_ledger(ledger):
        source = rec.get("source_file", "")
        if isinstance(source, str) and source.endswith(target):
            issue_id = rec.get("issue_id")
            if isinstance(issue_id, str) and issue_id:
                return issue_id
    return None


def evaluate_review_coverage(
    repo_path: Path | None = None,
    issue_id: str | None = None,
) -> ReviewCoverage:
    """Return uncovered ``AC-PLAN-NNN`` tokens for *issue_id*.

    Vacuous complete when *issue_id*, ``plan.md``, or plan tokens are absent.
    Only this-issue COMPLETED rows claim tokens.
    """
    if not issue_id:
        return ReviewCoverage(None, [], [], [])
    root = repo_path or Path.cwd()
    source_file = _latest_source_file(root, issue_id)
    if not source_file:
        return ReviewCoverage(issue_id, [], [], [])
    plan_path = resolve_issue_artifact_path(root, source_file, "plan.md")
    if not plan_path.is_file():
        return ReviewCoverage(issue_id, [], [], [])
    plan_tokens = _unique_tokens(plan_path.read_text(encoding="utf-8"))
    if not plan_tokens:
        return ReviewCoverage(issue_id, [], [], [])
    claimed = _claimed_tokens(root, issue_id, source_file)
    uncovered = [token for token in plan_tokens if token not in claimed]
    covered = [token for token in plan_tokens if token in claimed]
    return ReviewCoverage(issue_id, plan_tokens, covered, uncovered)


def _latest_source_file(root: Path, issue_id: str) -> str | None:
    ledger = root / "specs" / "issues.jsonl"
    source: str | None = None
    for rec in _read_ledger(ledger):
        if rec.get("issue_id") == issue_id:
            raw = rec.get("source_file")
            if isinstance(raw, str) and raw:
                source = raw
    return source


def _claimed_tokens(root: Path, issue_id: str, source_file: str) -> set[str]:
    ledger = resolve_issue_artifact_path(root, source_file, "tasks.jsonl")
    cards = _task_cards(resolve_issue_artifact_path(root, source_file, "tasks.md"))
    claimed: set[str] = set()
    for row in _latest_rows(ledger):
        if row.get("issue_id") != issue_id or row.get("status") != _COMPLETED:
            continue
        task_id = str(row.get("id") or "")
        claimed.update(resolve_task_ac_tokens(row, card_text=cards.get(task_id, "")))
        claimed.update(_persisted_evidence_tokens(row))
    return claimed


def _latest_rows(ledger: Path) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for rec in _read_ledger(ledger):
        task_id = rec.get("id")
        if isinstance(task_id, str) and task_id:
            latest[task_id] = rec
    return list(latest.values())


def _task_cards(tasks_md: Path) -> dict[str, str]:
    if not tasks_md.is_file():
        return {}
    lines = tasks_md.read_text(encoding="utf-8").splitlines()
    cards: dict[str, str] = {}
    start: int | None = None
    current = ""
    for index, line in enumerate(lines):
        head = _TASK_HEAD_RE.match(line)
        if head is None:
            continue
        if start is not None and current:
            cards[current] = "\n".join(lines[start:index]).strip()
        current = head.group(1)
        start = index
    if start is not None and current:
        cards[current] = "\n".join(lines[start:]).strip()
    return cards


def _persisted_evidence_tokens(row: Mapping[str, Any]) -> list[str]:
    evidence = row.get("evidence")
    if isinstance(evidence, Mapping):
        evidence = evidence.get("items") or []
    if not isinstance(evidence, list):
        return []
    found: list[str] = []
    for item in evidence:
        if isinstance(item, Mapping):
            raw = item.get("ac") or item.get("criterion_id")
            if isinstance(raw, str) and raw:
                found.append(raw)
        elif isinstance(item, str) and item:
            found.append(item)
    return _unique_tokens(" ".join(found))


def _unique_tokens(text: str) -> list[str]:
    return list(dict.fromkeys(_AC_TOKEN.findall(text)))
