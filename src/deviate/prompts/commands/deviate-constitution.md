---
name: deviate-constitution
description: Governance artifact generation — initialize or update specs/constitution.md as an authoritative document defining architectural standards, tech stack constraints, testing mandates, and completion criteria
---

## [ROLE_DEFINITION]
This engine operates strictly as an isolated, context-bounded structural configuration and governance transpiler for software architecture specifications. Your objective is to initialize or update the `specs/constitution.md` file as an authoritative governance artifact defining architectural standards, tech stack constraints, testing mandates, and completion criteria.

## [GOVERNANCE]
${CONSTITUTION}

## [AGENT_RULES]
${CLAUDE_MD}

## [TASK]
- **ID**: ${TASK_ID}
- **Description**: ${TASK_DESCRIPTION}

## [CONSTRAINTS]
- Consult project state sources: package.json, pyproject.toml, Dockerfile, CI config, existing constitution
- Source precedence: user input > existing constitution > project state > system defaults
- Preserve all variable definitions, macro expressions, config paths byte-for-byte
- Write to `specs/constitution.md` and commit via post-script

## [OUTPUT]
Constitution document at `specs/constitution.md` following the standard template with Architectural Principles, Tech Stack Standards, Testing Protocols, Definition of Done, and Version History.
