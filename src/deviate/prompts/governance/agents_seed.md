## DeviaTDD Orchestration Rules

### Three-Layer Architecture
- **Macro Layer** — Feature scoping: `/explore` → `/research` → `/prd` → `/shard`. Each phase has a deterministic output artifact. HITL Gate 1 (Design Approval) gates transition to Meso.
- **Meso Layer** — Issue engineering: `/specify` → `/tasks`. Converts issue contracts into functional specs and granular tasks. HITL Gate 2 (Contract Sign-Off) gates transition to Micro.
- **Micro Layer** — TDD sandbox: RED → GREEN → YELLOW → JUDGE → REFACTOR. Each task executes as an isolated vertical slice across a complete R-G-R cycle.

### Append-Only Ledger Protocol
- All state transitions in `specs/issues.jsonl` and `specs/**/tasks.jsonl` are append-only.
- No existing line is ever modified or overwritten.
- Canonical state is derived by sequential ledger parsing.

### Git Isolation Principle
- Every task loop executes on a clean git branch or worktree.
- Commits are automatic at each phase boundary.
- NEVER delete a branch — whether by merging, closing, or any other means — unless the user has explicitly requested branch deletion.

### Tamper Guard & Micro-Sandboxing
- GREEN phase resets test directories to post-RED commit state before evaluation.
- Micro-layer LLM execution is strictly sandboxed: write access is granted **only** to files matching `src/**/*.py`.
- All `tests/`, `specs/`, and configuration files are strictly read-only during Micro-layer execution.
- Any mutation outside this allow-list triggers an immediate rollback.

### Human-in-the-Loop (HITL) Gates
- **Gate 1** (Design Approval): After `/research`, before `/prd` — human approves design and data model.
- **Gate 2** (Contract Sign-Off): After `/specify`, before `/tasks` — human approves functional contract.
- **Gate 3** (Final Merge Audit): After all tasks complete — human approves merge.
- No gate may be programmatically bypassed.

### Model Tiering
| Model | Phases |
|-------|--------|
| DeepSeek V4 Flash | `/explore`, RED, GREEN, REFACTOR |
| DeepSeek V4 Pro | JUDGE, YELLOW, `/specify`, `/tasks` |
| Qwen 3.7+ [Thinking] | `/research`, `/prd`, `/shard`, `/adhoc` |

### Session Continuity
- Micro-layer tasks reuse a single LLM session across RED → GREEN → REFACTOR phases.
- Model switching mid-task is prohibited.
- JUDGE phase runs in an isolated V4 Pro session for compliance verification.

### Task Execution Reference
Use `mise run <task>` for all execution:

| Task | Purpose |
|------|---------|
| `mise run test` | Run unit tests |
| `mise run test-e2e` | Run E2E tests via bats |
| `mise run lint` | Lint Python |
| `mise run lint-fix` | Apply lint fixes |
| `mise run format` | Format Python |
| `mise run format-check` | Check formatting |
| `mise run check-types` | Type check |
| `mise run fix` | Format + lint fix |
| `mise run check` | All validation checks |
| `mise run setup` | Install deps + hooks |
| `mise run clean` | Remove artifacts |
| `mise run help` | List tasks |

## Offline Documentation System

The `libref` CLI is a local-first documentation tool for AI agents. It provides offline-queryable API docs for all project dependencies. **Always prefer `libref query <library> <topic>` over web fetching** — results are local, instant, and token-cheap.

### Usage Rules
- **Discovery first**: Run `libref list` to see available documentation packages before querying a library.
- **Primary lookup**: Use `libref query <library@version> "<topic>"` as the first and primary documentation mechanism for all library/framework API questions.
- **Registration**: When a dependency is not yet indexed, use `libref add <source>` (git repo URL) to register its documentation.
- **Fallback hierarchy**: `libref query` → training data → web fetch (last resort). Web fetching is only acceptable when `libref` has no documentation for the required library.

### Quick-Start Workflow
1. Run `deviate explore` to scan the codebase
2. Run `deviate research` for architectural analysis
3. Run `deviate prd` to compile requirements
4. Run `deviate shard` to decompose into issues
5. Run `deviate specify` to write functional contracts
6. Run `deviate tasks` to decompose into TDD cycles
7. Execute each task via RED → GREEN → REFACTOR
8. Run `deviate e2e` for end-to-end verification
