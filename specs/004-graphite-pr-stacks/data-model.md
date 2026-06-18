# Data Model: Graphite PR Stacks Integration

## Config Change

### DeviateConfig.graphite

- **Field**: `graphite: bool = False`
- **Location**: `src/deviate/state/config.py`, `DeviateConfig` class
- **Serialization**: `.deviate/config.toml` under `[deviate]` section (or top-level)
- **Scope**: Session-scoped. Read at runtime by `micro.py` and `meso.py` code paths.

```python
class DeviateConfig(BaseModel):
    profile: str = "default"
    llm_backend: str = "droid"
    timeout_seconds: int = Field(default=300, gt=0)
    agent_export_mode: Literal["local", "global"] = "local"
    agent: AgentConfig = Field(default_factory=AgentConfig)
    models: dict[str, str] = Field(default_factory=dict)
    graphite: bool = False  # NEW — enables Graphite PR stack workflow

    model_config = {"extra": "forbid"}
```

### Config Resolution

Config loaded from `.deviate/config.toml` at each call site. No caching — the TOML file is small, reads are <1ms.

```toml
graphite = true
```

### None

No new Pydantic models. No new JSONL ledgers. No new state machines.

## Data Flow

### Flow 1: Per-Task Graphite Stack (Micro Layer)

**Trigger**: `deviate run` dispatches a task via `_dispatch_task()`.

Context: `context query graphite.com@latest "gt create"` — `gt create <name> --onto <parent>` creates a Graphite-tracked branch.

```
  BEFORE TASK (graphite=true)
  │
  ├─ Read config: .deviate/config.toml → graphite=true
  │
  ├─ Resolve parent branch:
  │    First task in issue  → "main"
  │    Nth task             → branch name of prior COMPLETED task
  │
  ├─ gt create feat/{epic}/{task-slug} --onto {parent}
  │    Source: context query graphite.com@latest "gt create"
  │    - Creates new branch tracked by Graphite
  │    - Fails if branch already exists (rare — retry with -2 suffix)
  │    - --onto flag available since gt 1.8.6
  │
  └─ Task runs (RED → GREEN → JUDGE → REFACTOR, or EXECUTE)
       Commits happen on this branch
       └─ _commit_phase() uses existing commit messages:
            "test(TSK-NNN-NN): RED phase - failing test"
            "feat(TSK-NNN-NN): GREEN phase - implementation"
            "refactor(TSK-NNN-NN): REFACTOR phase - cleanup"
```

```
  AFTER TASK (COMPLETED, graphite=true)
  │
  ├─ gt submit --no-edit-title --no-edit-description
  │    Source: context query graphite.com@latest "gt submit"
  │    - Idempotently force-pushes branch
  │    - Creates/updates PR on GitHub
  │    - --no-edit-title / --no-edit-description: skip interactive prompts
  │    - PR title derived from commit messages (already correct format)
  │
  └─ console.print PR URL on success
```

### Flow 2: Stack Submission (Meso Layer)

**Trigger**: `deviate pr run` after all tasks for an issue are COMPLETED.

Context: `context query graphite.com@latest "gt submit --stack"`

```
  devaite pr run (graphite=true)
  │
  ├─ Same _pr_pre() contract emission (unchanged)
  │
  ├─ Instead of gh pr create:
  │    gt submit --stack --no-edit-title --no-edit-description
  │    - Pushes ALL branches in the stack (trunk → current branch)
  │    - Creates/updates PRs for each
  │
  ├─ On success: console.print PR URLs per entry
  │
  └─ On failure: surface error, task commits are safe locally
```

### Flow 3: Graceful Degradation (gt absent)

```
  graphite=true but gt not on PATH
  │
  ├─ Runtime detection fails (subprocess.run(["gt", "--version"]) exits non-zero)
  │
  ├─ If single task (micro layer): fall back to regular commit on existing branch
  │    - No stack created, but task completes normally
  │    - Warn: "GT_NOT_FOUND — install with: npm install -g @withgraphite/graphite-cli"
  │
  └─ If `deviate pr run` (meso layer): fall back to gh pr create
       - Single PR created from current branch
       - Warn: "GT_NOT_FOUND — falling back to gh pr create"
```

## Branch Naming Convention

Existing pattern: `feat/{epic_num}/{issue-slug}` (e.g., `feat/004/graphite-pr-stacks`)

Per-task extension: `feat/{epic_num}/{issue-slug}/{task-id}` (e.g., `feat/004/graphite-pr-stacks/TSK-004-01`)

- First task creates `feat/004/graphite-pr-stacks/TSK-004-01 --onto main`
- Second task creates `feat/004/graphite-pr-stacks/TSK-004-02 --onto feat/004/graphite-pr-stacks/TSK-004-01`

Graphite tracks the parent-child relationship. `gt log` shows the full stack.

## Context Query Mandate (Implementation)

All `gt` CLI flag references in code MUST be verified at implementation time against:

```
context query graphite.com@latest "<command>"
```

Specifically:

| Code Location | Required Verification |
| :--- | :--- |
| `gt create ... --onto ...` | `context query graphite.com@latest "gt create"` — confirm `--onto` flag signature |
| `gt submit --no-edit-title --no-edit-description` | `context query graphite.com@latest "gt submit"` — confirm no-interactive flags still work in current version |
| `gt submit --stack` | `context query graphite.com@latest "gt submit --stack"` — confirm stack flag behavior |

Do not hardcode `gt` flags from memory, blog posts, or web searches. The `context` CLI returns version-specific authoritative docs.

## Source Registry

| ID | Type | Source / Path (Strictly Relative to Repo Root) | Relevance Note |
| :--- | :--- | :--- | :--- |
| SRC-01 | Codebase | `src/deviate/state/config.py` | `DeviateConfig` — `graphite` field addition |
| SRC-02 | Codebase | `src/deviate/cli/micro.py` | Before-task `gt create`, after-task `gt submit` |
| SRC-03 | Codebase | `src/deviate/cli/meso.py` | Stack-level `gt submit --stack` in `_pr_run()` |
| SRC-04 | Documentation | `context query graphite.com@latest` | Authoritative source for all `gt` CLI flags |

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | AWAITING_HITL_GATE_1 |
| FEATURE_SLUG | 004-graphite-pr-stacks |
| SPEC_TARGET_DATAMODEL | specs/004-graphite-pr-stacks/data-model.md |
| NEXT_ACTION | Human reviews design.md + data-model.md, then invokes the `prd` skill |
