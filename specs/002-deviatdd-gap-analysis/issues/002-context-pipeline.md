---
title: Context Pipeline — Context Pre/Post with Auto-Trigger and AGENTS.md Alignment
labels: ["feature", "ISS-002", "P1"]
source_file: specs/002-deviatdd-gap-analysis/prd.md
blocked_by: ["ISS-002-001"]
coordinates_with: []
issue_id: ISS-002-002
epic_id: ISS-002
type: feature
---

## [SYSTEM_TOPOLOGY_MAPPING]

- **Epic Domain**: 002 — DeviaTDD Docs-to-Code Gap Resolution
- **Local Issue File**: `specs/002-deviatdd-gap-analysis/issues/002-context-pipeline.md`
- **Workstation Paths**:
  - `src/deviate/cli/context.py` — NEW: `context pre` and `context post` CLI commands
  - `src/deviate/core/context.py` — NEW: `resolve_workspace_context()`, `ContextContract` model
  - `src/deviate/core/worktree.py` — MODIFY: governance block upsert helpers
  - `src/deviate/cli/macro.py` — MODIFY: auto-trigger `context post` via `--no-context-sync` flag
  - `src/deviate/cli/meso.py` — MODIFY: auto-trigger `context post` via `--no-context-sync` flag
  - `CLAUDE.md` — MODIFY: governance block upsert (`## Technical Execution Context`)
  - `AGENTS.md` — MODIFY: symlink enforcement, stale reference removal (`rgr run`, `manage-tasks.sh`, `sdd-parse-ast.sh`, `get-test-config.sh`, `.rgr/`)

## [THE_PROBLEM_CONTRACT]

**User Journey**: After running `deviate explore post`, the governance blocks in `CLAUDE.md` are stale — the `## Technical Execution Context` section references outdated paths. The developer runs `deviate context pre` which crawls the workspace directory, resolves all paths relative to `repo_root`, and emits a `ContextContract` JSON. Then `deviate context post <manifest>` upserts the governance blocks, enforces `AGENTS.md → CLAUDE.md` symlink, cleans stale references, and commits. All macro/meso post commands auto-trigger this flow unless `--no-context-sync` is passed.

**System Response**: `context pre` discovers `.deviate/config.toml` and `specs/` directory, resolves all paths to relative strings, emits `ContextContract{status: READY}`. `context post` reads the manifest, upserts `## Technical Execution Context`, creates `AGENTS.md → CLAUDE.md` symlink (or copy fallback on Windows), audits AGENTS.md for stale reference patterns and removes them, commits. Missing `.deviate/` emits `FAILURE` status. Missing/locked CLAUDE.md warns but does not block.

## [SCOPE_BOUNDARIES]

### Hard Inclusions
- `deviate context pre` — directory crawl, path resolution, `ContextContract` JSON emission
- `deviate context post <manifest>` — manifest read, governance block upsert, symlink enforcement
- `ContextContract` model with relative path strings and `status` field
- Auto-trigger in all macro/meso post commands via `--no-context-sync` flag
- Symlink enforcement: `AGENTS.md → CLAUDE.md` via `ln -sf` (POSIX) or copy fallback (Windows)
- `os.name` guard for symlink operations
- Stale reference audit: remove `rgr run`, `manage-tasks.sh`, `sdd-parse-ast.sh`, `get-test-config.sh`, `.rgr/` patterns
- Governance block upsert in `CLAUDE.md`: `## Technical Execution Context` section
- Context sync is best-effort with warning — never a hard gate that blocks post-command commit

### Defensive Exclusions
- NO changes to micro-layer TDD cycle, profiles, or cache discipline
- NO changes to session state machine beyond auto-trigger wiring
- NO removal of existing governance block content — only upsert/replace
- NO changes to `deviate init` or constitution provisioning
- Symlink on Windows uses copy fallback — no `mklink` or admin elevation

## [UPSTREAM_REQUIREMENT_TRACING]

### Functional Requirements
| ID | Title | PRD Section |
|----|-------|-------------|
| FR-002 | Context Pre/Post with Auto-Trigger | FR-002-ContextSync |
| FR-011 | AGENTS.md/CLAUDE.md Symlink Enforcement | FR-011-AgentsClaudeAlign |

### Acceptance Criteria
| ID | Description |
|----|-------------|
| AC-002-01 | `context pre` with valid `.deviate/` and `specs/` emits JSON contract with `status: READY`, all paths relative |
| AC-002-02 | `context post <manifest>` updates `## Technical Execution Context`, creates AGENTS.md→CLAUDE.md symlink, commits |
| AC-002-03 | Macro post command auto-triggers `context post` unless `--no-context-sync` passed |
| AC-011-01 | `context post` converts AGENTS.md to symlink → CLAUDE.md |
| AC-011-02 | `context post` removes stale `rgr run`, `manage-tasks.sh`, `.rgr/` references from AGENTS.md |

### Data Model Entities
- `ContextContract` — `src/deviate/core/context.py`

## [MULTI_TIERED_VERIFICATION_TARGETS]

- `tests/test_cli/test_context.py` — `test_context_pre_emits_contract`, `test_context_pre_missing_deviate`, `test_context_post_updates_governance`, `test_context_post_symlink_enforcement`
- `tests/test_cli/test_macro.py` — `test_explore_post_auto_triggers_context`, `test_explore_post_no_context_sync`
- `tests/test_cli/test_meso.py` — `test_specify_post_auto_triggers_context`
- `tests/test_core/test_context.py` — `test_resolve_workspace_context`, `test_context_contract_paths_relative`

## [DEMONSTRATION_PATH]

```bash
# Verify context pre emits contract
deviate context pre 2>/dev/null | uv run python -c "
import sys, json
contract = json.load(sys.stdin)
assert contract['status'] == 'READY'
assert 'repo_root' in contract
print(f'Context OK: status={contract[\"status\"]}')
"

# Verify context post updates governance
deviate context pre > /tmp/ctx_contract.json
deviate context post /tmp/ctx_contract.json 2>&1 && echo 'Context post OK'

# Verify AGENTS.md symlink
ls -la AGENTS.md | grep -q 'CLAUDE.md' && echo 'Symlink OK' || echo 'WARNING: not a symlink'

# Run tests
pytest tests/test_cli/test_context.py tests/test_core/test_context.py -v --no-header -q
```
