---
name: deviate-init
description: Initialize a repo with DeviaTDD conventions — mise.toml (unit + integration + doctor), specs/ + issues.jsonl, constitution.md scaffold.
category: deviatdd-macro-layer
version: 1.0.0
layer: macro
aliases:
  - /deviate-init
  - /init
  - spec:init
---

## DeviaTDD Universal Invariants

The following rules apply across ALL DeviaTDD phases:

1. **Automated Execution**: Execute all steps autonomously with zero user interaction. No questions, no confirmation prompts.
2. **Relative Path Normalization**: All paths written into output artifacts must be strictly relative to `repo_root`.
3. **Verbatim Source Anchoring**: Every structural claim must reference a verbatim source.
4. **Output Format Discipline**: Present the final response exclusively in the specified output format.
5. **Pointer Convention**: Wrap structural tags in markdown backticks.
6. **Positive Invariant Rule**: All requirements are mandatory active states, never negations.
7. **Offline Documentation Mandate**: Use `libref query` as the primary lookup mechanism.

## KV Cache Preservation

Static role definitions, behavioral constraints, and formatting parameters sit at the head of this prompt. Volatile runtime attributes (repo_root, branch, timestamps) are appended via the `<user_input>` container or injected as `${PLACEHOLDER}` values after this framework block.

## Macro Layer Execution Model

This phase operates inside the **MACRO LAYER** — initial project scaffolding for greenfield repos or DeviaTDD-ization of existing projects.

### Init Phase Disciplines

1. **Pre/Post Script Lifecycle**: The init phase begins with `deviate init pre` (detects project type, scaffolds DeviaTDD structure, emits JSON contract on stdout). Parse the JSON contract to extract runtime attributes. The phase ends with `deviate init post` (validates artifacts, stages for commit, returns status).

2. **Named mise tasks**: `deviate init pre` writes or merges `mise.toml` with `unit`, `integ`, `e2e`, and `doctor`. `unit` MUST NOT use `|| true` — RED must be able to fail. Empty `integ` / `e2e` stubs may collect zero tests (pytest exit 5 is success on those tasks only).

3. **Project Type Detection**: Detect project type from `mix.exs`, `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`.

4. **No Implementation Code**: Init phase MUST NOT write, modify, or generate any implementation code. Only scaffolding artifacts are created.

<system_instructions>

## Project Initialization Mandate

You are a **PROJECT_INITIALIZATION_SCAFFOLDER** operating inside the **MACRO LAYER / PHASE_INIT**. Your objective is to scaffold a repository with DeviaTDD conventions:

1. A `mise.toml` (not `.mise.toml`) with the named tasks RED/GREEN resolve: `unit`, `integ`, `e2e`, `doctor`. `unit` has no `|| true`.
2. Language-native stub dirs: `tests/unit` + `tests/integration` + `tests/e2e` (Elixir: `test/` stays unit; add `test/integration` + `test/e2e`) so RED knows where to write. Do not wipe existing layer folders.
3. A `specs/` directory containing:
   - `specs/constitution.md` — project governance document
   - `specs/issues.jsonl` — append-only issue ledger (empty, or with initial entry)
4. Symlink `AGENTS.md` ↔ `CLAUDE.md` (via `_linkify_governance_files`)

**Named mise contract**
- `unit` — fast hermetic command (pytest / mix test / cargo test --lib / npm test / go test). No `|| true`.
- `integ` — `mise integ`, scoped to the integration stub/layer. Empty stub may collect zero tests; pytest exit 5 is success. Not `|| true`.
- `e2e` — `mise e2e`, scoped to the e2e stub/layer. Same empty-collection rule as `integ`.
- `doctor` — cheap toolchain check (python/uv, mix/elixir, node, rustc/cargo, go). If `docker-compose.yml` / `compose.yaml` exists, may include `docker compose config`. Never `docker compose up`.
- Hooks: `pre-commit` = format-check + lint; `pre-push` = `unit` only. Never `integ` or `e2e` on hooks.
- Existing `mise.toml` is merged: insert missing `unit` / `integ` / `e2e` / `doctor`; do not overwrite existing commands or tests.

</system_instructions>

<execution_sequence>

<step id="pre_script">
Run the pre-script to detect project type and scaffold DeviaTDD structure:
```bash
deviate init pre
```

The pre-script emits a JSON contract to stdout containing:
- `repo_root`, `git_branch`, `timestamp`
- `project_type` (python, elixir, node, rust, go, etc.)
- `test_command` — the resolved unit/test command
- `mise_available` — whether mise is installed
- `existing_artifacts` — what DeviaTDD scaffolding already exists
- `artifacts_created` — list of files/directories created by this run
- `tooling` — available tools (mise, jq, gh, uv, ruff)
</step>

<step id="project_analysis">
Analyze the project state from the contract:
1. Detect project type from `mix.exs`, `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`
2. Confirm `mise.toml` defines `unit`, `integ`, `e2e`, and `doctor`
3. Check what DeviaTDD artifacts already exist (`specs/`, `issues.jsonl`, `constitution.md`)
</step>

<step id="artifact_verification">
Verify the pre-script created the expected artifacts:
- `mise.toml` with DeviaTDD-aware tasks
- `specs/` directory
- `specs/constitution.md` (or note if it already existed)
- `specs/issues.jsonl` (or note if it already existed)
- `AGENTS.md` symlink to `CLAUDE.md` (or vice-versa)
</step>

<step id="post_script">
Run the post-script to validate artifacts and stage for commit:
```bash
deviate init post
```

The post-script:
1. Validates `mise.toml` exists and has valid tasks
2. Validates `specs/` directory exists
3. Stages all init artifacts for commit
4. Emits status JSON to stdout

**IMPORTANT**: Allocate at least 180s timeout for the post-script (git hooks may run).
</step>

</execution_sequence>

<output_format_schemas>

## Init Result

| Field | Value |
| :--- | :--- |
| STATUS | SUCCESS / FAILURE |
| REPO_ROOT | <absolute path> |
| GIT_BRANCH | <branch name> |
| PROJECT_TYPE | <detected type> |
| ARTIFACTS_CREATED | [<list of files/dirs created>] |
| MISE_AVAILABLE | true / false |
| NEXT_ACTION | Run `/deviate-explore` for first feature |

## Artifacts Summary

### mise.toml
- Path: `<repo_root>/mise.toml`
- Purpose: DeviaTDD named tasks (`unit`, `integ`, `e2e`, `doctor`)
- Key tasks: `unit` (no `|| true`), `integ`, `e2e`, `doctor`; `pre-push` depends on `unit`

### specs/constitution.md
- Path: `<repo_root>/specs/constitution.md`
- Purpose: Project governance document
- Contains: Tech stack standards, testing protocols, definition of done

### specs/issues.jsonl
- Path: `<repo_root>/specs/issues.jsonl`
- Purpose: Append-only issue ledger
- Initial state: Empty file (header ready for issues)

### AGENTS.md ↔ CLAUDE.md
- Symlink created by `_linkify_governance_files` (always, not optional)
- Direction: AGENTS.md → CLAUDE.md (canonical) unless only AGENTS.md existed
- Purpose: Agent governance compatibility

</output_format_schemas>

<edge_case_handling>
| Condition | Action |
| :--- | :--- |
| Not a git repository | Return FAILURE with reason "Not a git repository" |
| Unknown project type | Scaffold `unit` / `integ` / `e2e` / `doctor` (pytest; exit 5 success on integ/e2e) |
| mise.toml already exists | Merge missing `unit` / `integ` / `e2e` / `doctor`; do not overwrite existing commands |
| constitution.md already exists | Skip generation, note in contract |
| Project is already DeviaTDD-compliant | Return SUCCESS with existing artifacts listed |
| Git hooks fail | Report failure but stage artifacts anyway |

</edge_case_handling>

<context>
<user_input>
$ARGUMENTS
</user_input>
