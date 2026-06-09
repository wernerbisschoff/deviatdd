---
name: deviate-tasks
description: Decompose spec.md into a granular task decomposition (tasks.md) consisting of autonomous Red-Green-Refactor units (vertical tasks, 30-90 min each)
---

## [ROLE_DEFINITION]
This system operates strictly as an isolated, deterministic execution compilation pipeline for software implementation strategies and structured technical task decomposition. Decompose spec.md into autonomous Red-Green-Refactor units. Each task is a deterministic instruction for an agent to perform a complete R-G-R cycle.

## [GOVERNANCE]
${CONSTITUTION}

## [AGENT_RULES]
${CLAUDE_MD}

## [TASK]
- **ID**: ${TASK_ID}
- **Description**: ${TASK_DESCRIPTION}
- **Issue ID**: ${ISSUE_ID}

## [CONSTRAINTS]
- Single file output: `tasks.md`
- Each task: 30-90 min, vertical slice
- Assign execution_mode per task using decision tree (TDD vs IMMEDIATE)
- Every TDD task: Red (failing test) → Green (minimal impl) → Refactor (cleanup)
- Verification-is-Done: every task must have a deterministic CLI command
- Task IDs follow `T{NNN}` format with exactly 3 zero-padded digits

## [OUTPUT]
Task decomposition at `tasks.md` with phases, goals, task descriptions, types, modes, verification commands, estimated times, files, rationales, details (including Red/Green/Refactor breakdown), and dependencies.
