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
        "Status Summary",
    ],
    "data_model": [
        "Entity Definitions",
        "Relationship Graph",
        "Schema Tables",
        "State Transitions",
        "Data Flow",
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


_ROW_CAP_WARNINGS: dict[str, int] = {"File Registry": 12, "Risk Register": 4}
_FR_OPTIONAL_SUBFIELDS = ("Preconditions", "State Transition", "Exception")
_DATA_FLOW_LOCAL_ONLY = re.compile(r"None\s*[—–\-]+\s*local-only", re.IGNORECASE)
_DATA_FLOW_OUTBOUND = re.compile(r"outbound integrations", re.IGNORECASE)


def _substance_errors(content: str, required: list[str]) -> list[str]:
    errors: list[str] = []
    for section in required:
        body = extract_section_body(content, section)
        if body is not None and not body.strip():
            errors.append(f"empty section: {section}")
    return errors


def _row_cap_warnings(content: str, required: list[str]) -> list[str]:
    warnings: list[str] = []
    for section, cap in _ROW_CAP_WARNINGS.items():
        if section not in required:
            continue
        body = extract_section_body(content, section)
        if body is None:
            continue
        rows = [ln for ln in body.splitlines() if ln.strip().startswith(("-", "*"))]
        if len(rows) > cap:
            warnings.append(f"{section} has {len(rows)} rows, over cap of {cap}")
    return warnings


def _has_fenced_sequence_diagram(body: str) -> bool:
    return "```" in body and "sequenceDiagram" in body


def _data_flow_runtime_errors(content: str) -> list[str]:
    """Mechanical floor for data-model ``## Data Flow`` request-flow substance.

    Empty or missing sections stay with the existing heading / empty-body
    checks. A non-empty body must show a fenced ``sequenceDiagram`` or an
    explicit local-only marker, and an Outbound integrations heading/table
    or the same marker. No provider-name matching.
    """
    body = extract_section_body(content, "Data Flow")
    if body is None or not body.strip():
        return []
    local_only = _DATA_FLOW_LOCAL_ONLY.search(body) is not None
    errors: list[str] = []
    if not local_only and not _has_fenced_sequence_diagram(body):
        errors.append("Data Flow: missing sequenceDiagram or None — local-only")
    if not local_only and _DATA_FLOW_OUTBOUND.search(body) is None:
        errors.append(
            "Data Flow: missing Outbound integrations or None — local-only"
        )
    return errors


def _fr_subfield_errors(content: str) -> list[str]:
    body = extract_section_body(content, "Functional Requirements and Epics")
    if body is None:
        return []
    errors: list[str] = []
    for field in _FR_OPTIONAL_SUBFIELDS:
        match = re.search(
            rf"^\s*[-*]?\s*\*\*{re.escape(field)}\*\*\s*:(.*)$", body, re.MULTILINE
        )
        if match is not None and not match.group(1).strip():
            errors.append(f"empty sub-field: {field}")
    return errors


def validate_artifact(content: str | None, artifact_type: str) -> ValidationResult:
    required = ARTIFACT_VALIDATORS.get(artifact_type)
    if required is None:
        return ValidationResult(
            passed=False,
            errors=[f"unknown artifact type: {artifact_type}"],
            warnings=[],
        )
    missing = validate_sections(content, required)
    if missing and (not content or not content.strip()):
        return ValidationResult(passed=False, errors=missing, warnings=[])
    errors = list(missing)
    warnings: list[str] = []
    if content and content.strip():
        errors.extend(
            _substance_errors(content, [s for s in required if s not in missing])
        )
        warnings.extend(_row_cap_warnings(content, required))
        if artifact_type == "data_model" and "Data Flow" not in missing:
            errors.extend(_data_flow_runtime_errors(content))
    return ValidationResult(passed=len(errors) == 0, errors=errors, warnings=warnings)


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


PRD_CONTRACT_SECTIONS = ARTIFACT_VALIDATORS["prd"] + [
    "Acceptance Outline",
    "Ambiguity Resolution and Stakeholder Decisions",
]
SHARD_CONTRACT_SECTIONS = [
    "System Topology Mapping",
    "The Problem Contract",
    "Scope Boundaries",
    "Upstream Requirement Tracing",
    "Multi-Tiered Verification Targets",
    "Demonstration Path",
    "Acceptance Outline",
]
_AO_PATTERN = re.compile(r"\bAO-\d{3}\b")


def validate_macro_contract(content: str, artifact: str) -> list[str]:
    """Validate the shared PRD/Shard contract before committing artifacts."""
    required = PRD_CONTRACT_SECTIONS if artifact == "prd" else SHARD_CONTRACT_SECTIONS
    errors = validate_sections(content, required)
    errors.extend(_substance_errors(content, [s for s in required if s not in errors]))
    if artifact == "prd":
        errors.extend(_fr_subfield_errors(content))
    outline = extract_section_body(content, "Acceptance Outline") or ""
    if not _AO_PATTERN.search(outline):
        errors.append(
            f"{artifact.upper()} Acceptance Outline must contain at least one AO-NNN token"
        )
    if outline and _GHERKIN_CLAUSE_PATTERN.search(outline):
        errors.append(
            "GHERKIN_LEAK_DETECTED: Acceptance Outline must not contain Given/When/Then clauses"
        )
    if artifact == "shard":
        verification = (
            extract_section_body(content, "Multi-Tiered Verification Targets") or ""
        )
        if not re.search(
            r"(?im)^\s*[-*]?\s*\*\*Verification Command\*\*\s*:", verification
        ):
            errors.append(
                "Multi-Tiered Verification Targets must contain a Verification Command"
            )
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
    for _, clause_pattern, missing_msg in _ACCEPTANCE_CLAUSES:
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


def repair_missing_verification_mode(content: str) -> tuple[str, int]:
    """Fail loud on missing Verification Mode; never insert a default."""
    return content, 0


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


ISSUE_TRACEABILITY_SECTIONS = [
    "User Stories Ledger",
    "Upstream Requirement Tracing",
    "Acceptance Outline",
]


def validate_issue_traceability(body: str | None) -> dict[str, object]:
    """Check issue stories, tracing, and outline plus AO tokens."""
    missing = validate_sections(body, ISSUE_TRACEABILITY_SECTIONS)
    outline = extract_section_body(body or "", "Acceptance Outline")
    if outline is not None and not _AO_PATTERN.search(outline):
        missing.append("Acceptance Outline must contain at least one AO-NNN token")
    if missing:
        return {
            "status": "NOT_READY",
            "missing_fields": missing,
            "repair_hint": f"repair the issue by adding the missing sections: {', '.join(missing)}",
        }
    return {"status": "READY", "missing_fields": [], "repair_hint": ""}
