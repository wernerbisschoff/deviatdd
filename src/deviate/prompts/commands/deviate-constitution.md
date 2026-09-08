---
name: deviate-constitution
description: Initialize or update specs/constitution.md — the authoritative governance artifact defining tech stack, testing mandates, and DoD.
category: deviatdd-macro-layer
version: 1.0.0
aliases:
  - constitution
  - /deviate-constitution
  - spec:constitution
  - spec.constitution
---

<system_instructions>

This engine operates strictly as an isolated, context-bounded structural configuration and governance transpiler for software architecture specifications. Initialize or update `specs/constitution.md`.

CRITICAL INSTRUCTION INVARIANTS:
1. **Input Resolution Rule**: Resolve input per `<user_input>`; halt on empty. Run `deviate constitution pre` first and parse its JSON contract from stdout — do NOT re-derive paths. The contract carries `repo_root`, `git_branch`, `timestamp`, `constitution_path`, `test_command`, `lint_command`, `plan_target`, and `dry_run`.
2. **Output Format Constraint**: Emit Markdown per `<required_output_template>`.
3. **Zero-Tolerance Semantic Shift**: Preserve all user variable definitions, macro expressions (e.g., Jinja, Chezmoi wrappers), configuration paths, and environment shell variables (in `$NAME` form) byte-for-byte.
4. **Source Precedence Hierarchy**: Apply a deterministic sequence where higher-precedence sources completely override lower values:
   * Level 1: Active context resolved from the user input.
   * Level 2: Existing parsed properties from `specs/constitution.md`.
   * Level 3: Project state evidence discovered in standard configuration blueprints.
   * Level 4: Static systemic configuration defaults.
5. **Implementation Phase**: After parsing the contract, implement the constitution by writing to `constitution_path` from the contract. Then run `deviate constitution post` with the plan target path as argument.

</system_instructions>

<project_state_sources>
Consult exclusively the following evidence files when deriving environment standards:
- `package.json`
- `mix.exs`
- `pyproject.toml`
- `Dockerfile`
- `docker-compose.yml`
- `terraform/`
- CI configuration files
- Existing `specs/constitution.md` (if present)
</project_state_sources>

<few_shot_examples>
<example>
<example_user_input>Use Go, Gorilla Mux, and Postgres. Enforce 80% coverage.</example_user_input>
<output_payload>
# Project Constitution

**Version:** 0.1.0

---

## Architectural Principles
- Code must reflect strict domain-driven isolation.

## Tech Stack Standards
### Backend
- Go 1.21 / Gorilla Mux
### Database
- PostgreSQL

## Testing Protocols
### Framework
- `TEST_FRAMEWORK`: go test
- `TEST_COMMAND`: go test ./...

## Definition of Done
- [ ] Code implemented
- [ ] Tests passing

## Version History
- 0.1.0 — Initial constitution generation
</output_payload>
</example>
</few_shot_examples>

<required_output_template>
The generated output file must match the structural alignment defined below:

```markdown
# Project Constitution

**Version:** X.Y.Z

---

## Architectural Principles
- Immutable governance rules

## Tech Stack Standards
### Backend
### Frontend
### Database
### Infrastructure
### Tooling

## Testing Protocols
### Framework
- `TEST_FRAMEWORK`: <exunit|jest|pytest|...>
- `TEST_ROOT`: <test|tests>
- `TEST_EXT`: <_test.exs|.test.ts|...>
- `TEST_COMMAND`: <mix test|pytest|...>
- `LINT_COMMAND`: <mix credo|ruff check|...>

### Coverage
- Coverage thresholds

## Definition of Done
- [ ] Code implemented
- [ ] Tests passing
- [ ] Coverage requirements met
- [ ] Documentation updated
- [ ] No governance violations

## Version History
- X.Y.Z — Change description
```
</required_output_template>

<edge_case_handling>
- **EMPTY_USER_INPUT**: Read and parse existing constitution and alternative file states. If all targets are absent, fallback to minimum standard structural architecture templates.
- **MISSING_PROJECT_STATE**: Limit extraction exclusively to available definitions inside `<project_state_sources>`; maintain pre-existing parameters or defaults without failing execution.
- **MALFORMED_EXISTING_CONSTITUTION**: Extract valid structural components from surviving file text fragments, preserve the current version string, and execute a semantic patch increment.
</edge_case_handling>

<execution_sequence>

<step id="pre_script">
Run `deviate constitution pre` to emit the JSON contract:
```bash
deviate constitution pre
```

After parsing the contract:
- If `status` is `FAILURE` — surface the `reason` to the user and stop.
- If `status` is `READY` — proceed; for `dry_run: true`, write a preview constitution and skip post.
</step>

<step id="project_analysis">
Analyze the project state by consulting files listed in `<project_state_sources>`:
- `package.json` — detect Node.js, test frameworks (jest, mocha, vitest), linters (eslint, prettier)
- `mix.exs` — detect Elixir/Phoenix, exunit, credo
- `pyproject.toml` — detect Python, pytest, ruff, mypy
- `Dockerfile` / `docker-compose.yml` — detect container infrastructure
- `terraform/` — detect IaC
- CI config — detect GitHub Actions, CircleCI, etc.

Also read the existing `specs/constitution.md` (if present) from the `constitution_path` in the contract.
</step>

<step id="constitution_generation">
Generate or update the constitution markdown file at `constitution_path` (absolute path from the contract).

The constitution must contain all sections defined in `<required_output_template>`:
1. **Project Constitution** header with version
2. **Architectural Principles** — immutable governance rules
3. **Tech Stack Standards** — backend, frontend, database, infrastructure, tooling
4. **Testing Protocols** — framework, commands, coverage thresholds
5. **Definition of Done** — checklist
6. **Version History** — semantic versioning

Use `test_command` and `lint_command` from the contract to populate `TEST_COMMAND` and `LINT_COMMAND`.
</step>

<step id="manifest_writing">
Write an execution manifest JSON to `plan_target` (absolute path from the contract). The manifest must include:
```json
{
  "task_id": "constitution",
  "files_modified": [
    {
      "path": "specs/constitution.md",
      "action": "created|modified",
      "purpose": "Governance artifact defining architectural standards"
    }
  ],
  "commit_subject": "docs(constitution): add/update project constitution",
  "validation": {
    "lint": "SKIP",
    "typecheck": "SKIP",
    "tests": "SKIP",
    "summary": "Constitution document generated"
  }
}
```
</step>

<step id="post_script">
Run the post-script to validate the constitution, stage files, and commit:
```bash
deviate constitution post "$PLAN_TARGET"
```
**IMPORTANT**: The post-script runs precommit hooks which include the full test suite — allocate a timeout of at least 180s (3 minutes) when running this command.

The post-script:
1. Reads the manifest from `$PLAN_TARGET`
2. Validates that `specs/constitution.md` exists and is non-empty
3. Validates required sections are present
4. Stages and commits the constitution
5. Emits status JSON on stdout

If the post-script exits with `status: FAILURE`, surface the `reason` to the user and stop.
</step>

</execution_sequence>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>

