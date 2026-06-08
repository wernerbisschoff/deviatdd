from __future__ import annotations

from pathlib import Path


def extract_prd_requirements(prd_path: Path) -> list[str]:
    raise NotImplementedError


def validate_traceability(issue_body: str, prd_reqs: list[str]) -> dict:
    raise NotImplementedError
