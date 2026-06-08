from __future__ import annotations

import re


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
