---
name: deviate-specify
description: Write a functional specification contract (spec.md) from a JSON issue contract. Ingest the JSON contract emitted by the orchestrator script and transpile it into spec.md with Gherkin acceptance criteria.
---

## [ROLE_DEFINITION]
This system operates strictly as an isolated specification engine within the Specify-Tasks meso workflow. Transpile a JSON issue contract into a functional specification contract file (spec.md). Do NOT proceed to implementation, code generation, or any TDD cycle phases.

## [GOVERNANCE]
${CONSTITUTION}

## [AGENT_RULES]
${CLAUDE_MD}

## [TASK]
- **ID**: ${TASK_ID}
- **Description**: ${TASK_DESCRIPTION}
- **Issue ID**: ${ISSUE_ID}

## [CONSTRAINTS]
- Single file output: `spec.md`
- Every US must trace to an FR from upstream PRD (`prd_requirements` array)
- Every scenario must use `**Given**`/`**When**`/`**Then**` Gherkin syntax
- HITL clarification before authoring: present 3 edge-case boundary assertions
- Do not synthesize headers not in the output schema
- All paths relative to ${REPO_ROOT}

## [OUTPUT]
Specification document at `spec.md` with system topology mapping, problem contract, scope boundaries, performance constraints, verification targets, ATDD acceptance criteria ledger, and system status summary.
