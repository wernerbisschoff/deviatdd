from __future__ import annotations

from pathlib import Path

from deviate.state.ledger import IssueRecord


def resolve_issue(issue_id: str, ledger_path: Path | None = None) -> IssueRecord | None:
    raise NotImplementedError


def claim_issue(issue_id: str, ledger_path: Path | None = None) -> bool:
    raise NotImplementedError


def read_issue_body(issue_id: str, ledger_path: Path | None = None) -> str:
    raise NotImplementedError


def is_issue_completed(issue_id: str, ledger_path: Path | None = None) -> bool:
    raise NotImplementedError
