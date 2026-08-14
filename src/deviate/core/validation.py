from __future__ import annotations

import re
from collections import namedtuple
from collections.abc import Iterator

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


_SCENARIO_PATTERN = re.compile(
    r"\*\*(?P<label>(?:Scenario \d+|AC-\d+-\d+|Scenario AC-PLAN-\d+)):.*?\*\*"
)
_GHERKIN_CLAUSE_PATTERN = re.compile(r"\*\*(?:Given|When|Then)\*\*\s*:?")
_VERIFICATION_MODE_LITERALS = ("automated", "manual", "deferred")
_MODE_PATTERN = re.compile(r"\*\*Verification Mode\*\*:\s*([A-Za-z]+)")
_ACCEPTANCE_CLAUSES = (
    (
        "Source Outline",
        re.compile(r"\*\*Source Outline\*\*:\s*`?AO-\d{3}`?"),
        "missing Source Outline AO-NNN traceability",
    ),
    (
        "Upstream Traceability",
        re.compile(r"\*\*Upstream Traceability\*\*:\s*.+"),
        "missing Upstream Traceability",
    ),
    (
        "Current-Code Evidence",
        re.compile(r"\*\*Current-Code Evidence\*\*:\s*.+"),
        "missing Current-Code Evidence",
    ),
)


def _iter_scenario_bodies(
    content: str, pattern: re.Pattern[str]
) -> Iterator[tuple[re.Match[str], str]]:
    """Yield each scenario match paired with the body span until the next match."""
    scenarios = list(pattern.finditer(content))
    for i, match in enumerate(scenarios):
        start = match.end()
        end = scenarios[i + 1].start() if i + 1 < len(scenarios) else len(content)
        yield match, content[start:end]


def _validate_scenarios(bodies: list[tuple[re.Match[str], str]]) -> list[str]:
    errors: list[str] = []
    for match, body in bodies:
        label = match.group("label").removeprefix("Scenario ")
        for clause in ("Given", "When", "Then"):
            if f"**{clause}**" not in body:
                errors.append(f"{label}: missing '{clause}'")
    return errors


def validate_gherkin_syntax(content: str) -> list[str]:
    return _validate_scenarios(list(_iter_scenario_bodies(content, _SCENARIO_PATTERN)))


def validate_acceptance_outline(content: str) -> list[str]:
    body = extract_section_body(content, "Acceptance Outline")
    if body is None:
        return ["missing required section: Acceptance Outline"]
    errors: list[str] = []
    if _GHERKIN_CLAUSE_PATTERN.search(body):
        errors.append(
            "GHERKIN_LEAK_DETECTED: Acceptance Outline must not contain "
            "Given/When/Then clauses"
        )
    if not re.search(r"\bAO-\d{3}\b", body):
        errors.append("Acceptance Outline must contain at least one AO-NNN token")
    return errors


def _validate_verification_mode(scenario_id: str, scenario_body: str) -> list[str]:
    mode_matches = _MODE_PATTERN.findall(scenario_body)
    if not mode_matches:
        return [f"{scenario_id}: missing Verification Mode"]
    if len(mode_matches) > 1:
        return [f"{scenario_id}: duplicate Verification Mode lines"]
    literal = mode_matches[0]
    if literal.lower() not in _VERIFICATION_MODE_LITERALS:
        return [
            f"{scenario_id}: invalid Verification Mode '{literal}'; "
            "expected one of automated|manual|deferred",
        ]
    return []


def _validate_acceptance_clauses(scenario_id: str, scenario_body: str) -> list[str]:
    errors: list[str] = []
    for clause_name, clause_pattern, missing_msg in _ACCEPTANCE_CLAUSES:
        if not clause_pattern.search(scenario_body):
            errors.append(f"{scenario_id}: {missing_msg}")
    return errors


def validate_acceptance_contract(content: str) -> list[str]:
    body = extract_section_body(content, "Acceptance Contract")
    if body is None:
        return ["PLAN_ACCEPTANCE_CONTRACT_MISSING"]
    contract_pattern = re.compile(
        r"\*\*(?P<label>Scenario (?P<id>AC-PLAN-\d{3})):.*?\*\*"
    )
    bodies = list(_iter_scenario_bodies(body, contract_pattern))
    if not bodies:
        return ["Acceptance Contract must contain at least one AC-PLAN-NNN scenario"]
    errors = _validate_scenarios(bodies)
    for match, scenario_body in bodies:
        scenario_id = match.group("id")
        errors.extend(_validate_acceptance_clauses(scenario_id, scenario_body))
        errors.extend(_validate_verification_mode(scenario_id, scenario_body))
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
