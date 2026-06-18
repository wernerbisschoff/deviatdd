# Design: Graphite PR Stacks Integration

## Recommended Architecture

**Inline `gt` calls with config toggle.** The integration adds a `graphite: bool = False` field to `DeviateConfig`. When `true`, three insertion points in the existing code path call `gt` CLI via `subprocess.run` — no new modules, no new Pydantic models, no new JSONL ledgers, no state machines.

### Three insertion points

1. **Micro layer — before task execution** (`micro.py`, inside `_dispatch_task` or the phase entry points it calls):
   - If `graphite = true`: `gt create feat/{epic}/{task-slug} --onto {prior-task-branch}` (or `--onto main` for the first task in a stack)
   - Branch naming follows the existing `feat/{epic}/{issue-slug}` convention, extended with a task-specific suffix.

2. **Micro layer — after task COMPLETED** (`micro.py`, inside `_run_refactor_phase` and `_run_execute_phase`, after the COMPLETED ledger transition):
   - If `graphite = true`: `gt submit --no-edit-title --no-edit-description` to push the branch and create/update its PR.

3. **Meso layer — `deviate pr run`** (`meso.py::_pr_run()`):
   - If `graphite = true`: `gt submit --stack --no-edit-title --no-edit-description` instead of the current `gh pr create` path. This pushes all stacked PRs in one command.

### Module surface

| File | Change | Rationale |
| :--- | :--- | :--- |
| `src/deviate/state/config.py` | **Add** `graphite: bool = False` to `DeviateConfig` | The toggle. Read from `.deviate/config.toml` at runtime. |
| `src/deviate/cli/micro.py` | **Add** `gt create` before task dispatch, `gt submit` after task completion | Two calls. Guarded by `graphite` config check. |
| `src/deviate/cli/meso.py` | **Replace** `gh pr create` with `gt submit --stack` in `_pr_run()` when `graphite = true` | The stack-level submission. |

No changes to: `SessionState`, `_VALID_PHASES`, `micro.py::_phase_map`, the TDD cycle state machine, the ledger protocol, `deviate-pr/SKILL.md`, `deviate-review/SKILL.md`, or any test files (beyond new tests for the `gt` code paths).

## Options Matrix

| Option | Complexity | Scope | Verdict |
| :--- | :--- | :--- | :--- |
| **A: Full state model** — PRStackRecord, StackEntryRecord, PRReviewRecord models + ledgers | High | ~400 lines of models + persistence + tests | **REJECT** — over-engineered for a boolean toggle |
| **B: Inline `gt` calls** — config boolean, 3 insertion points, no new modules | Low | ~50 lines of code | **ACCEPT** |
| **C: GT MCP integration** — Graphite MCP server for agent-driven stack management | High | New MCP module, persistent process | **REJECT** — no constitutional precedent, complex test setup |

## Design Trade-Offs

| Decision | Trade-Off | Why This Side |
| :--- | :--- | :--- |
| **Inline `subprocess.run` over utility module** | Repeating `["gt", "create", ...]` vs. a `GraphiteClient` class | 3 call sites, each with different flags. A class adds abstraction for no reuse benefit. Contrarian viewpoint: if `gt` usage grows beyond 3 call sites, extraction is a trivial refactor. |
| **Config boolean over feature flag** | `graphite: bool` vs. `pr_stack_mode: Literal["gh", "gt"]` | Boolean is simpler. If a third PR tool emerges, promote to an enum. Not anticipated. |
| **Commit messages as PR titles** | `gt submit` uses commit messages for PR titles vs. custom `--title` flag (which doesn't exist in `gt`) | Existing commit messages (`feat(TSK-NNN-NN): GREEN phase - implementation`) make good PR titles. No need for a separate title-construction path. |
| **No per-task PR body** | `gt submit --no-edit-description` leaves PR body empty vs. generating body from task context | If PR body is needed, the skill layer can append it to the commit message body during the GREEN/EXECUTE commit. Deferred — no current requirement. |

## Contrarian Viewpoints

- **`gt` ghost dependency fragility**: Same risk as existing `gh` ghost dependency. Mitigation: runtime detection, clear error on absence, graceful fallback to `gh` for single-PR (non-stack) workflows when `gt` is absent but `graphite = true`.
- **TDD micro-tasks may not be independently reviewable**: A single TDD task is often <50 lines. Graphite best practices demand "each PR must be independently reviewable." If a task's diff is too small or context-dependent, the user can set `graphite = false` and use `gh pr create` for a single merge commit per issue instead. This is a user-driven choice, not an architectural constraint.
- **Per-task `gt create` modifies worktree branch state**: The TDD cycle assumes it's running on a stable branch. `gt create` creates a new branch from the previous task branch — the agent must commit all work before the branch switch. Mitigation: `gt create` runs BEFORE the RED phase starts, on a clean worktree after the prior task's REFACTOR commit. The AGENTS.md restriction ("Agents running TDD cycles MUST NOT execute CLI commands that mutate git branch state") applies only to agents inside the TDD sandbox — the `gt create` call is made by the `deviate run` host process, not by the agent.

## Risk Register

| Risk ID | Risk | Likelihood | Impact | Mitigation |
| :--- | :--- | :--- | :--- | :--- |
| GPR-001 | `gt` CLI not installed when `graphite = true` | High | High | Runtime detection before `gt create`. If absent: fall back to `gh` for single-PR, emit clear install hint. |
| GPR-002 | `gt submit` fails due to network/auth issues | Medium | High | Retry with backoff (3 attempts). Fail gracefully — task already committed locally, only PR creation failed. |
| GPR-003 | `gt create` branch name conflicts (branch exists from prior failed run) | Low | Medium | Check branch existence via `git rev-parse --verify` before `gt create`. If exists, use a retry suffix (`-2`, `-3`). |
| GPR-004 | `gt submit` opens web browser (interactive prompt) in agentic flow | High | Medium | Use `--no-edit-title --no-edit-description` to suppress prompts. Verify via `context query graphite.com@latest` that these flags suppress all interactivity. |

## Constitutional Alignment Audit

| Clause | Alignment | Notes |
| :--- | :--- | :--- |
| **Three-Layer Architecture** | **Aligned** | All changes stay within existing layers. Micro layer: task-level branch/create/submit. Meso layer: stack-level submit. No new phases. |
| **Append-Only Ledger Protocol** | **Aligned** | No new ledgers. No existing ledger fields modified. |
| **Git Isolation Principle** | **Tension — resolved** | `gt create` modifies branch state before RED phase. Mitigation: runs in the host `deviate run` process, not inside the agent sandbox. The host process owns git branch management; the agent operates only within the branch it's given. |
| **HITL Gates** | **Aligned** | No gates bypassed. PR creation is post-verification (after tests pass, after JUDGE compliance). |
| **Session Continuity** | **Aligned** | PR creation happens after the micro-cycle session ends. `gt submit` is a separate process call, not model switching mid-task. |
| **Ghost Dependencies** | **Aligned** | `gt` follows the existing `gh`/`aider` runtime-detection pattern. |
| **Testing Protocols** | **Aligned** | All `gt` calls mocked via `subprocess.run` mock — same pattern as existing `gh` test mocks. |

## Pending HITL Decisions

| Decision ID | Question | Context | Status |
| :--- | :--- | :--- | :--- |
| `HITL-001` | Should each TDD task get its own PR in the stack? | PR stack granularity: per-task vs. per-issue. Per-task increases review granularity but may produce non-reviewable diffs. | **Accepted.** Per-task. User controls via `graphite` toggle — if per-task diffs are too small, disable graphite. |
| `HITL-002` | Should `gt` be added to the project's documented ghost-dependency list? | `AGENTS.md` lists `gh` and `aider` as accepted ghost dependencies. `gt` should join them. | **Accepted.** Document `gt` alongside `gh` and `aider` in `AGENTS.md` and constitution ghost-dependency section. |
| `HITL-003` | Should `context query graphite.com@latest` be mandatory for implementation? | `gt` CLI flags evolve. The explore.md established this as authoritative source. | **Accepted.** Mandatory. All `gt` flag references in code must be verified against `context query graphite.com@latest`. |

## Source Registry

| ID | Type | Source / Path (Strictly Relative to Repo Root) | Relevance Note |
| :--- | :--- | :--- | :--- |
| SRC-01 | Codebase | `src/deviate/state/config.py` | `DeviateConfig` — add `graphite` field |
| SRC-02 | Codebase | `src/deviate/cli/micro.py` | Task dispatch — `gt create`/`gt submit` insertion points |
| SRC-03 | Codebase | `src/deviate/cli/meso.py` | `_pr_run()` — `gt submit --stack` branch |
| SRC-04 | Documentation | `context query graphite.com@latest` | Authoritative `gt` CLI reference — verify all flags |
| SRC-05 | Skill | `src/deviate/prompts/skills/deviate-pr/SKILL.md` | No changes — PR orchestration skill unchanged |

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | AWAITING_HITL_GATE_1 |
| FEATURE_SLUG | 004-graphite-pr-stacks |
| SPEC_TARGET_DESIGN | specs/004-graphite-pr-stacks/design.md |
| SPEC_TARGET_DATAMODEL | specs/004-graphite-pr-stacks/data-model.md |
| NEXT_ACTION | Human reviews design.md + data-model.md, resolves Pending HITL Decisions, then invokes the `prd` skill |
