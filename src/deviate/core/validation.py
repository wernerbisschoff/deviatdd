from __future__ import annotations

import re
from collections import namedtuple

import yaml

ValidationResult = namedtuple("ValidationResult", ["passed", "errors", "warnings"])

ARTIFACT_VALIDATORS: dict[str, list[str]] = {
    "explore": [
        "PROBLEM_DEFINITION",
        "DISCOVERY_AUDIT_RESULTS",
        "CONSTITUTION_QUOTES",
        "FILE_REGISTRY",
        "STATUS_SUMMARY",
    ],
    "design": [
        "PROBLEM_DEFINITION",
        "SYSTEM_TOPOLOGY_MAPPING",
        "THE_PROBLEM_CONTRACT",
        "SCOPE_BOUNDARIES",
        "PERFORMANCE_CONSTRAINTS",
        "MULTI_TIERED_VERIFICATION_TARGETS",
        "ATDD_ACCEPTANCE_CRITERIA_LEDGER",
        "SYSTEM_STATUS_SUMMARY",
        "DESIGN_TRADE_OFF_MATRIX",
    ],
    "data_model": [
        "[ENTITY_DEFINITIONS]",
        "[RELATIONSHIP_GRAPH]",
        "[SCHEMA_TABLES]",
        "[STATE_TRANSITIONS]",
        "[DATA_FLOW]",
        "[SOURCE_REGISTRY]",
    ],
    "prd": [
        "DOCUMENT_CONTROL_AND_METADATA",
        "SYSTEM_OBJECTIVES_AND_SCOPE_BOUNDARY",
        "ARCHITECTURAL_CONSTRAINTS_AND_PREREQUISITES",
        "FUNCTIONAL_FLOW_AND_SEQUENCE_ARCHITECTURE",
        "FUNCTIONAL_REQUIREMENTS_AND_EPICS",
        "GITHUB_ISSUE_SHARDING_STRATEGY",
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
    scenario_pattern = re.compile(r"\*\*Scenario \d+:.*?\*\*")
    scenarios = list(scenario_pattern.finditer(content))
    if not scenarios:
        return errors
    for i, match in enumerate(scenarios):
        start = match.end()
        end = scenarios[i + 1].start() if i + 1 < len(scenarios) else len(content)
        body = content[start:end]
        if "**Given**" not in body:
            errors.append(f"Scenario {i + 1}: missing 'Given'")
        if "**When**" not in body:
            errors.append(f"Scenario {i + 1}: missing 'When'")
        if "**Then**" not in body:
            errors.append(f"Scenario {i + 1}: missing 'Then'")
    return errors


def validate_sections(content: str | None, required: list[str]) -> list[str]:
    if not content or not content.strip():
        return list(required)
    missing: list[str] = []
    for section in required:
        pattern = rf"^##\s+{re.escape(section)}\s*$"
        if not re.search(pattern, content, re.MULTILINE):
            missing.append(section)
    return missing


def validate_yaml_frontmatter(content: str) -> bool:
    if not content.startswith("---"):
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
    legacy = re.match(r"^T\d{3}$", task_id)
    new_format = re.match(r"^TSK-\d{3}-\d{2}$", task_id)
    return bool(legacy or new_format)
