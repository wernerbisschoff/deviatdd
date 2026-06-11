---
title: Context Pipeline — Context Pre/Post Commands & AGENTS.md Alignment
labels: ["feature", "ISS-002", "P0"]
source_file: specs/002-deviatdd-gap-analysis/prd.md
blocked_by: ["ISS-002-001"]
coordinates_with: []
issue_id: ISS-002-002
epic_id: ISS-002
---

## [SYSTEM_TOPOLOGY_MAPPING]

- **Epic Domain**: 002 — DeviaTDD Docs-to-Code Gap Resolution
- **Local Issue File**: `specs/002-deviatdd-gap-analysis/issues/002-context-pipeline.md`
- **Workstation Paths**:
  - `src/deviate/cli/context.py` — NEW: Typer app with `context pre`, `context post`
  - `src/deviate/core/context.py` — NEW: `resolve_workspace_context()`, `sync_context_blocks()`, `enforce_symlink()`
  - `src/deviate/cli/__init__.py` — MODIFY: register `context_app`
  - `src/deviate/cli/macro.py` — MODIFY: add `--no-context-sync` flag, wire auto-trigger in explore/research/prd/shard post
  - `src/deviate/cli/meso.py` — MODIFY: add `--no-context-sync` flag, wire auto-trigger in specify/tasks post
  - `AGENTS.md` — MODIFY: remove stale references (`rgr run`, `manage-tasks.sh`, `sdd-parse-ast.sh`, `get-test-config.sh`, `.rgr/`)

## [THE_PROBLEM_CONTRACT]

**User Journey**: A developer finishes `deviate explore post` and expects CLAUDE.md to automatically get an updated `## Technical Execution Context` governance block and AGENTS.md to be a symlink to CLAUDE.md. They can also run `deviate context pre` standalone to emit a `ContextContract` JSON describing the current workspace state, then `deviate context post <manifest>` to apply changes.

**System Response**: `context pre` crawls the workspace, resolves paths (spec, constitution, AGENTS.md, CLAUDE.md, worktree, branch, issue), emits a `ContextContract` JSON to stdout. `context post` reads the agent's manifest, upserts governance blocks in CLAUDE.md and AGENTS.md, enforces `AGENTS.md → CLAUDE.md` symlink via `ln -sf`, and commits. Auto-triggered after every macro/meso post command unless `--no-context-sync` is passed. Stale references (`rgr run`, etc.) are cleaned from AGENTS.md.

## [SCOPE_BOUNDARIES]

### Hard Inclusions
- `cli/context.py` with `context pre` (no args → stdout JSON) and `context post <manifest>` (upsert → symlink → commit)
- `core/context.py` with `resolve_workspace_context()`, `sync_context_blocks()`, `enforce_symlink()`
- Register `context_app` in `cli/__init__.py`
- `--no-context-sync` flag on all macro/meso post commands
- Auto-trigger `context post` in explore/research/prd/shard/specify/tasks post
- Remove stale references from AGENTS.md
- Symlink enforcement with `os.name` guard (copy fallback on non-POSIX)
- Context sync best-effort with warning — not a hard gate
- Overwrite `## DeviaTDD Orchestration Rules` block in CLAUDE.md (idempotent)

### Defensive Exclusions
- NO changes to constitution validation
- NO changes to ledger management
- NO changes to profile execution
- NO changes to skill files
- NO changes to the session state machine
- NO web or UI components

## [UPSTREAM_REQUIREMENT_TRACING]

### Functional Requirements
| ID | Title | PRD Section |
|----|-------|-------------|
| FR-002 | Context Pre/Post with Auto-Trigger | FR-002-ContextSync |
| FR-011 | AGENTS.md/CLAUDE.md Symlink Enforcement | FR-011-AgentsClaudeAlign |

### Acceptance Criteria
| ID | Description |
|----|-------------|
| AC-002-01 | `deviate context pre` emits JSON contract with relative paths and status `READY` |
| AC-002-02 | `deviate context post <manifest>` updates CLAUDE.md, creates symlink, commits |
| AC-002-03 | Macro post command auto-triggers `context post` unless `--no-context-sync` |
| AC-011-01 | AGENTS.md becomes a symlink to CLAUDE.md after `context post` |
| AC-011-02 | Stale references (`rgr run`, `manage-tasks.sh`) removed from AGENTS.md |

### Data Model Entities
- `ContextContract` — `src/deviate/core/context.py`

## [MULTI_TIERED_VERIFICATION_TARGETS]

- `tests/test_cli/test_context.py` — `test_context_pre_emits_contract`, `test_context_pre_missing_dotdev`, `test_context_post`, `test_context_post_symlink`
- `tests/test_core/test_context.py` — `test_resolve_workspace_context`, `test_enforce_symlink_posix`, `test_enforce_symlink_non_posix`, `test_sync_context_blocks`
- `tests/test_cli/test_macro.py` — `test_explore_post_context_auto_trigger`, `test_explore_post_no_context_sync`
- `tests/test_cli/test_meso.py` — `test_specify_post_context_auto_trigger`

## [DEMONSTRATION_PATH]

```bash
# Verify context pre emits valid JSON contract
uv run deviate context pre 2>/dev/null | python -c "
import sys, json
c = json.load(sys.stdin)
assert c['status'] == 'READY'
assert c['phase'] == 'CONTEXT'
assert c['worktree_path']
print('Context contract valid:', c['status'])
"

# Verify symlink enforcement
uv run python -c "
import os
from deviate.core.context import enforce_symlink
enforce_symlink('AGENTS.md', 'CLAUDE.md')
assert os.path.islink('AGENTS.md') or os.name != 'posix'
print('Symlink enforcement OK')
"

# Run verification tests
pytest tests/test_cli/test_context.py tests/test_core/test_context.py -v --no-header -q
```
