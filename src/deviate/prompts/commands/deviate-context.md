---
name: deviate-context
description: Synchronize agent context files (CLAUDE.md, AGENTS.md) with spec.md, constitution.md, and workspace parameters — multi-lingual and mono-repo configuration mapping
---

## [ROLE_DEFINITION]
This engine operates strictly as an isolated operational runtime for multi-lingual and mono-repo software configuration mapping, context synchronization, and automated workspace orchestration. Your job is to perform context synchronization by merging spec and constitution parameters into CLAUDE.md and AGENTS.md.

## [GOVERNANCE]
${CONSTITUTION}

## [AGENT_RULES]
${CLAUDE_MD}

## [TASK]
- **ID**: ${TASK_ID}
- **Description**: ${TASK_DESCRIPTION}

## [CONSTRAINTS]
- Context merge hierarchy: spec.md values take precedence; constitution.md Constraints append with ", "
- Symlink atomicity: AGENTS.md → CLAUDE.md via `ln -sf`
- Multi-language mode detection: append per-language context blocks for 2+ primary languages
- Output contract: STATUS: SUCCESS or STATUS: INVALID_CONTEXT with DETAILS

## [OUTPUT]
Synchronized CLAUDE.md and AGENTS.md with `## Technical Execution Context` blocks populated from spec.md and constitution.md parameters.
