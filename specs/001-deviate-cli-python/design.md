### [RESOLVED_CONSTITUTIONAL_VIOLATION]
[Trigger]: The following architectural decision initially violated the named constitutional clause but was resolved via constitutional amendment.
[Violating_Decision]: Integration of `aider` Python API as the Micro-layer execution substrate without explicit sandboxing controls.
[Violated_Clause]: "Git Isolation Principle" and "Tamper Guard" (pre-amendment).
[Resolution]: The constitution was amended to explicitly codify micro-layer sandboxing: "Micro-layer LLM execution (Aider) is strictly sandboxed: it is granted write access **only** to files matching `src/**/*.py`. All `tests/`, `specs/`, and configuration files are strictly read-only during Micro-layer execution. Any mutation outside this allow-list triggers an immediate rollback."
[Status]: RESOLVED. Workflow may proceed.

## [RECOMMENDED_ARCHITECTURE]
**Domain-Driven Sub-Application Architecture (Modular Typer)**  
The `deviate` CLI will be structured as a core Typer application that delegates to strictly isolated sub-applications using `app.add_typer()`. This directly enforces the "Three-Layer Architecture" constraint by mapping each layer to a distinct module boundary:
- `src/deviate/cli/macro.py`: Handles `/explore`, `/research`, `/prd`, `/shard` (and `/adhoc`).
- `src/deviate/cli/meso.py`: Handles `/specify`, `/tasks`, and HITL Gate orchestration.
- `src/deviate/cli/micro.py`: Handles the TDD sandbox (RED, GREEN, YELLOW, JUDGE, REFACTOR) with embedded Tamper Guard logic and automated `deviate micro` orchestration.
- `src/deviate/core/agent.py`: Agent backend abstraction — invokes agent subprocesses (opencode, claude, droid, aider) via heredoc pipe or `--message` flag, parses YAML handover manifests from output, handles timeouts.
- `src/deviate/prompts/auto/`: Slimmed prompt templates for automated pipelines — each template has a static KV-cacheable prefix (role, constraints, constitution/CLAUDE.md content) and a dynamic task-specific suffix.
- `src/deviate/state/ledger.py`: Centralized, append-only JSONL writer enforcing the "Append-Only Ledger Protocol" for `issues.jsonl` and `tasks.jsonl`.
- `src/deviate/core/git.py`: Isolated utility enforcing the "Git Isolation Principle" (branch/worktree creation and cleanup).

This approach satisfies the "Tech Stack" constraint (Python 3.13, Typer, Rich, Pydantic) while maintaining strict module boundaries, enabling independent unit testing of each layer via `CliRunner`, and preventing the "junk drawer" anti-pattern.

## [OPTIONS_MATRIX]
| Option | Complexity | Testability | Constitutional Alignment | Reversibility | Blast Radius | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Option A: Monolithic Command Tree | Low | Medium | Tension | Easy | Low | Rejected |
| Option B: Event-Driven Pipeline | High | Low | Tension | Hard | High | Rejected |
| Option C: Plugin-Based Micro-Commands | High | Medium | Tension | Medium | High | Rejected |
| Option D: Domain-Driven Sub-Applications | Medium | High | Aligned | Easy | Medium | Recommended |

## [REJECTED_OPTIONS]
- **Monolithic Command Tree (Option A)**: Rejected due to poor alignment with the "Three-Layer Architecture" constraint. A single module would inevitably lead to cross-layer imports, violating the principle of decoupled feature verticals.
- **Event-Driven Pipeline (Option B)**: Rejected under the "SIMPLICITY_FIRST" mandate ("No abstractions for single-use code"). An event bus introduces unnecessary concurrency complexity for a synchronous, HITL-gated CLI workflow.
- **Plugin-Based Micro-Commands (Option C)**: Rejected because the scope is bounded to consolidating 14 existing shell scripts. Dynamic plugin loading adds high complexity for a fixed, known set of commands, violating "No 'flexibility' or 'configurability' that wasn't requested."

## [DESIGN_TRADEOFFS]
| Decision | Trade-off | Why This Side |
| :--- | :--- | :--- |
| Boilerplate vs. Boundary Enforcement | Option D requires slightly more initial boilerplate (defining multiple `typer.Typer()` instances) compared to Option A. | Explicitly accepted to enforce the "Three-Layer Architecture" and prevent the "junk drawer" anti-pattern. |
| Synchronous Execution vs. Session Continuity | The "Session Continuity" constraint requires the `micro.py` sub-app to maintain state across RED/GREEN/REFACTOR loops. | Managed via `src/deviate/state/session.py` Pydantic model, trading minor in-memory state management complexity for strict compliance with "Model Tiering". |
| Append-Only Ledger Implementation | Using a dedicated `ledger.py` module centralizes the "Append-Only Ledger Protocol". | The trade-off is a single point of failure for state persistence, mitigated by strict Pydantic validation on every write and immediate `git commit` after verification loops. |

## [CONTRARIAN_VIEWPOINTS]
- **Consolidation into Python**: Shell scripts are natively optimized for orchestrating system-level tools (`git`, `mise`, `bats`) via process spawning. Consolidating them into Python introduces subprocess translation overhead and creates a monolithic single point of failure for what were previously decoupled, highly composable Unix utilities.
- **Rich for Terminal Output**: The constitution mandates strict performance constraints (`L_max <= 500ms` for init, `L_max <= 200ms` per agent export). `Rich` incurs non-trivial rendering overhead. For a high-frequency CLI tool, a lightweight alternative better guarantees compliance with sub-200ms latency bounds.
- **System-level `bats` for E2E**: System-level dependencies fracture cross-platform reproducibility. A macOS developer and a Linux CI runner may have different `bats` versions, leading to environmental divergence and false-negative test results.

## [RISK_REGISTER]
| Risk ID | Risk | Likelihood | Impact | Mitigation | Owner | Source Anchor |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| RSK-001 | Race Condition in Session State | Medium | High | Implement OS-level advisory file locking (e.g., `fcntl`) or transition to an append-only SQLite backend. | `state/session.py` | `specs/constitution.md:30` |
| RSK-002 | State Decay on Schema Evolution | Low | Medium | Enforce strict Pydantic versioning with explicit migration hooks or automatic invalidation of stale state files. | `state/config.py` | `specs/constitution.md:32` |
| RSK-003 | Unbounded Growth of Append-Only Ledgers | Medium | Medium | Implement log rotation or size-based truncation policies tied to the `DeviateConfig` model. | `state/ledger.py` | `specs/constitution.md:10` |
| RSK-004 | Security Hole via Ghost Dependency (`aider`) | High | High | Wrap `aider` in a strict, read-only sandbox with explicit allow-listed paths, or remove it entirely. | `cli/micro.py` | `explore.md:17` |
| RSK-005 | Environmental Divergence in E2E Tests | Medium | Medium | Containerize the E2E test environment or pin `bats` via `mise` to guarantee deterministic execution. | `tests/e2e/` | `explore.md:18` |

## [CONSTITUTIONAL_ALIGNMENT_AUDIT]
| Constitutional Clause | Architectural Decision | Alignment | Notes |
| :--- | :--- | :--- | :--- |
| "Three-Layer Architecture" | CLI (Typer), State (Pydantic), Prompts (Resources) | Aligned | Clear separation of concerns is enforced via module boundaries (`cli/`, `state/`, `prompts/`). |
| "Append-Only Ledger Protocol" | `prompts.log` and JSONL tracking | Aligned | Design dictates append-only mechanics, though unbounded growth remains a secondary operational risk. |
| "Git Isolation Principle" | Workspace mutation handling via sandboxed `aider` | Aligned | Constitution amended to explicitly restrict `aider` write access to `src/**/*.py`, enforcing the Git Isolation Principle and Tamper Guard. |
| "Tamper Guard" | Reverting unauthorized test edits | Tension | Python subprocess wrappers around `git` and `bats` may exhibit race conditions or fail to catch rapid, concurrent tampering compared to native, pre-commit git hooks. |
| "Human-in-the-Loop (HITL)" | Gates after research, specify, tasks | Aligned | Workflow explicitly defines blocking gates requiring human approval before proceeding to downstream phases. |
| "Session Continuity" | State survival across process death | Tension | JSON-based state lacks native concurrency controls. Without explicit file locking, concurrent invocations risk state corruption. |
| "Model Tiering" | Flash (RED/GREEN), Pro (JUDGE/PRD) | Aligned | Routing logic explicitly maps task complexity to the designated model tier as specified. |
| "Coverage target: >= 80%" | `pytest`, `ruff`, `bats` integration | Tension | Achieving 80% coverage on Python subprocess wrappers mocking shell behavior often leads to inflated, brittle tests. |
| "Performance Gate (L_max <= 200ms)" | Agent export mappings | Tension | The inclusion of `Rich` and Pydantic validation overhead on every invocation threatens the strict 200ms latency bound. |

## [SOURCE_REGISTRY]
| ID | Type | Source / Path (Strictly Relative to Repo Root) | Relevance Note |
| :--- | :--- | :--- | :--- |
| SRC-001 | Constitution | `specs/constitution.md` | Authoritative architectural rules: 3-layer arch, append-only ledgers, tamper guard, model tiering. |
| SRC-002 | Explore_MD | `specs/001-deviate-cli-python/explore.md` | Verified dependencies, ghost dependencies, and architectural baselines for the greenfield CLI. |
| SRC-003 | Codebase_File | `pyproject.toml` | Python project metadata, CLI entry point, deps (Typer, Rich, Pydantic), build config. |
| SRC-004 | Codebase_File | `mise.toml` | Task runner definitions (test, lint, format, check, setup, clean, help), tool versions. |

## [STATUS_SUMMARY]
| Metric | Value |
| :--- | :--- |
| STATUS | AWAITING_HITL_GATE_1 |
| FEATURE_SLUG | 001-deviate-cli-python |
| EPIC_ID | 001 |
| GIT_BRANCH | main |
| SPEC_TARGET_DESIGN | `specs/001-deviate-cli-python/design.md` |
| SPEC_TARGET_DATAMODEL | `specs/001-deviate-cli-python/data-model.md` |
| NEXT_ACTION | Human reviews design.md + data-model.md, then invokes the `prd` skill |