from __future__ import annotations

import re
from pathlib import Path


def extract_prd_requirements(prd_path: Path) -> list[str]:
    if not prd_path.exists():
        return []
    content = prd_path.read_text(encoding="utf-8")
    return re.findall(r"FR-\d+", content)


def validate_traceability(issue_body: str, prd_reqs: list[str]) -> dict:
    result: dict[str, bool] = {}
    for req in prd_reqs:
        result[req] = req in issue_body
    return result
