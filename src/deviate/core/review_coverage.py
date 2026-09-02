"""Runner-owned Gate 3 plan-AC coverage (no agent call)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deviate.core.issues import resolve_issue_artifact_path
from deviate.core.judge_evidence import _AC_TOKEN, resolve_task_ac_tokens

from deviate.core._shared import issue_slug_variants
from deviate.state.ledger import _read_ledger

_BRANCH_SLUG_RE = re.compile(r"^feat/([^/]+)/([^/]+(?:/[^/]+)*)$")
_TASK_HEAD_RE = re.compile(r"^- (?:\[(?:x| )\]\s+)?(TSK-\d{3}-\d{2}):")
_NAMED_CHECK_RE = re.compile(r"\bAC-(?:ADHOC-\d{3}-\d{2}|PLAN-\d{3}|\d{3}-\d{2})\b")
_TEST_FILE_RE = re.compile(
    r"(?:^|/)(?:tests?/|test_)|(?:^|/)conftest\.py$|"
    r"(?:_test|Test|_spec|\.test)\.[^/]+$|\.bats$",
    re.IGNORECASE,
)
_COMPLETED = "COMPLETED"
BRIEF_INCOMPLETE = "brief incomplete"
APPLY_CRITICAL_CATEGORIES = frozenset(
    {
        "security",
        "data_loss",
        "broken_build",
        "named_check_fail",
    }
)


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
    bucket = match.group(1)
    ledger = root / "specs" / "issues.jsonl"
    if not ledger.exists():
        return None
    records = _read_ledger(ledger)
    for slug in issue_slug_variants(match.group(2)):
        target = f"{bucket}/issues/{slug}.md"
        for rec in records:
            source = rec.get("source_file", "")
            if isinstance(source, str) and source.endswith(target):
                issue_id = rec.get("issue_id")
                if isinstance(issue_id, str) and issue_id:
                    return issue_id
    return None


def extract_named_checks(text: str) -> list[str]:
    """Return first-seen named-check tokens from *text* (stable order)."""
    return list(dict.fromkeys(_NAMED_CHECK_RE.findall(text)))


def resolve_issue_brief_path(
    repo_path: Path | None = None,
    issue_id: str | None = None,
) -> Path | None:
    """Return this issue's brief markdown path, or ``None``."""
    if not issue_id:
        return None
    root = repo_path or Path.cwd()
    source = _latest_source_file(root, issue_id)
    if not source:
        return None
    path = root / source
    return path if path.is_file() else None


def resolve_issue_plan_path(
    repo_path: Path | None = None,
    issue_id: str | None = None,
) -> Path | None:
    """Return this issue's ``plan.md`` path, or ``None``."""
    if not issue_id:
        return None
    root = repo_path or Path.cwd()
    source = _latest_source_file(root, issue_id)
    if not source:
        return None
    plan = resolve_issue_artifact_path(root, source, "plan.md")
    return plan if plan.is_file() else None


def brief_has_named_checks(
    repo_path: Path | None = None,
    issue_id: str | None = None,
) -> bool:
    """True when this issue's brief itself contains at least one named check.

    Plan AC-PLAN lines are extra inputs, not a substitute for a brief.
    """
    brief = resolve_issue_brief_path(repo_path, issue_id)
    if brief is None:
        return False
    return bool(extract_named_checks(brief.read_text(encoding="utf-8")))


def brief_names_path(brief_text: str, filename: str) -> bool:
    """True when *brief_text* names *filename* as a path to read."""
    return filename in brief_text


def is_test_path(path: str) -> bool:
    """Classify a changed-file path as test vs production."""
    posix = path.replace("\\", "/")
    return bool(_TEST_FILE_RE.search(posix))


def classify_changed_files(paths: list[str]) -> tuple[list[str], list[str]]:
    """Split *paths* into ``(test_files, production_files)`` preserving order."""
    test_files = [p for p in paths if is_test_path(p)]
    production_files = [p for p in paths if not is_test_path(p)]
    return test_files, production_files


def _normalize_apply_category(category: str) -> str:
    return category.strip().lower().replace("-", "_").replace(" ", "_")


def may_apply_finding(
    *,
    apply: bool,
    severity: str,
    category: str,
    has_concrete_fix: bool,
) -> bool:
    """True only for opt-in ``--apply`` + CRITICAL + allowed category + FIX.

    Default review (``apply=False``) never applies. SUGGESTION and
    OPPORTUNITY never apply. CRITICAL without a concrete FIX never applies.
    Allowed categories: security, data loss, broken build, named-check fail.
    """
    if not apply:
        return False
    if severity.strip().upper() != "CRITICAL":
        return False
    if not has_concrete_fix:
        return False
    return _normalize_apply_category(category) in APPLY_CRITICAL_CATEGORIES


def should_commit_review_fixes(*, apply: bool, applied_critical: int) -> bool:
    """Commit only when ``--apply`` actually landed a CRITICAL fix."""
    return bool(apply and applied_critical > 0)


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
