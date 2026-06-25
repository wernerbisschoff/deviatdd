from __future__ import annotations

import re
from collections import namedtuple

import yaml

ValidationResult = namedtuple("ValidationResult", ["passed", "errors", "warnings"])

ARTIFACT_VALIDATORS: dict[str, list[str]] = {
    "explore": [
        "Problem Definition",
        "Discovery Audit Results",
        "Constitution Quotes",
        "Architectural Baselines",
        "Ecosystem Research",
        "File Registry",
        "Status Summary",
    ],
    "design": [
        "Recommended Architecture",
        "Options Matrix",
        "Rejected Options",
        "Design Trade-Offs",
        "Contrarian Viewpoints",
        "Risk Register",
        "Constitutional Alignment Audit",
        "Pending HITL Decisions",
        "Source Registry",
        "Status Summary",
    ],
    "data_model": [
        "Entity Definitions",
        "Relationship Graph",
        "Schema Tables",
        "State Transitions",
        "Data Flow",
        "Source Registry",
    ],
    "prd": [
        "Document Control and Metadata",
        "System Objectives and Scope Boundary",
        "Architectural Constraints and Prerequisites",
        "Functional Flow and Sequence Architecture",
        "Functional Requirements and Epics",
        "Issue Sharding Strategy",
    ],
}


def validate_artifact(content: str | None, artifact_type: str) -> ValidationResult:
    required = ARTIFACT_VALIDATORS.get(artifact_type)
    if required is None:
        return ValidationResult(
            passed=False,
            errors=[f"unknown artifact type: {artifact_type}"],
            warnings=[],
        )
    missing = validate_sections(content, required)
    passed = len(missing) == 0
    return ValidationResult(passed=passed, errors=missing, warnings=[])


def extract_section_body(content: str, header: str) -> str | None:
    escaped_header = re.escape(header)
    pattern = rf"^## {escaped_header}\s*$(.*?)(?=^## |\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if match:
        return match.group(1)
    return None


def validate_gherkin_syntax(content: str) -> list[str]:
    errors: list[str] = []
    scenario_pattern = re.compile(r"\*\*(?P<label>(?:Scenario \d+|AC-\d+-\d+)):.*?\*\*")
    scenarios = list(scenario_pattern.finditer(content))
    if not scenarios:
        return errors
    for i, match in enumerate(scenarios):
        start = match.end()
        end = scenarios[i + 1].start() if i + 1 < len(scenarios) else len(content)
        body = content[start:end]
        label = match.group("label")
        if "**Given**" not in body:
            errors.append(f"{label}: missing 'Given'")
        if "**When**" not in body:
            errors.append(f"{label}: missing 'When'")
        if "**Then**" not in body:
            errors.append(f"{label}: missing 'Then'")
    return errors


def validate_sections(content: str | None, required: list[str]) -> list[str]:
    if not content or not content.strip():
        return list(required)
    missing: list[str] = []
    for section in required:
        pattern = rf"^##\s+\[?{re.escape(section)}\]?\s*$"
        if not re.search(pattern, content, re.MULTILINE):
            missing.append(section)
    return missing


def validate_yaml_frontmatter(content: str) -> bool:
    if not content.lstrip().startswith("---"):
        return False
    end_idx = content.find("---", 3)
    if end_idx == -1:
        return False
    frontmatter = content[3:end_idx].strip()
    try:
        yaml.safe_load(frontmatter)
        return True
    except yaml.YAMLError:
        return False


def validate_task_id(task_id: str) -> bool:
    if not task_id:
        return False
    return bool(re.match(r"^TSK-\d{3}-\d{2}$", task_id))


def validate_source_file(source_file: str, epic_slug: str) -> bool:
    """Validate a shard manifest's ``source_file`` against the issue registry pattern.

    The downstream ``deviate meso run`` command parses ``source_file`` via
    ``PurePosixPath(source_file).parent.parent.name`` to derive the epic bucket
    slug and ``PurePosixPath(source_file).stem`` to derive the issue slug used
    for branch naming. Both rely on the strict shape
    ``specs/<epic_slug>/issues/<file>.md``. Any deviation (e.g. a PRD or
    design reference) silently produces wrong branch names and downstream
    worktree failures.

    Returns ``True`` only when *source_file* matches the expected pattern for
    *epic_slug*; ``False`` otherwise.
    """
    if not source_file or not epic_slug:
        return False
    if source_file.startswith("/"):
        return False
    parts = source_file.split("/")
    if len(parts) != 4:
        return False
    if parts[0] != "specs":
        return False
    if parts[1] != epic_slug:
        return False
    if parts[2] != "issues":
        return False
    if not parts[3].endswith(".md"):
        return False
    return True
