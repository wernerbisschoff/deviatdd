## [RECOMMENDED_ARCHITECTURE]

**[Summary]:** Extract reusable business logic from CLI modules into `core/` modules, keeping CLI routing thin. This follows the constitution's **Three-Layer Architecture** (`specs/constitution.md §[1_ARCHITECTURAL_PRINCIPLES]`) which mandates strict separation between layers. Currently, business logic like profile mapping, complexity gates, and context sync is inlined in CLI handlers (`cli/micro.py`, `cli/meso.py`). Relocating these to `core/` enables isolated unit testing without Typer fixtures, aligns with the constitution's `[3_1_FRAMEWORK]` (pytest) for testability, and keeps the `src/deviate/cli/` surface as thin command routing.

The 16 implementation gaps split into three structural categories: **(a) new domain logic** — ExecutionProfile, ComplexityGate, CacheDiscipline, ContextManifest → new `core/` module per concern; **(b) new CLI endpoints** — context|adhoc|constitution pre/post, inspect commands → new `cli/<name>.py` files registered in `__init__.py`; **(c) cross-cutting enhancements** — `--json/--quiet`, `--profile`, `pytest --json-report` → modify existing CLI modules and `_common.py`. Execution order from `specs/002-deviatdd-gap-analysis/explore.md` is preserved: Block 1 (independent foundations) → Block 2 (depends on `--json/--quiet`) → Block 3 (depends on Block 2) → Block 4.

Constitutional Tensions (identified by adversarial audit) are addressed via concrete mitigations rather than workflow halts:
- Gap #3 (Adhoc fast-path): Replace automatic Gate 1 bypass with explicit `--skip-gates` flag requiring human opt-in.
- Gap #8 (JUDGE rollback): Replace `git reset --hard HEAD~1` with `git revert` or tracked SHA reset to avoid destroying unrelated commits.
- Gap #13 (tasks.jsonl auto-generation): Generate proposal file requiring `--confirm` flag before appending to ledger.

**[Module_Surface]:**

| Action | Files | Gap |
|--------|-------|-----|
| **NEW** `core/profile.py` | `ExecutionProfile` enum + `resolve_profile()` mapping | #1 |
| **NEW** `core/context.py` | `ContextManifest`, `resolve_workspace_context()`, `sync_context_blocks()`, `enforce_symlink()` | #2, #11 |
| **NEW** `core/complexity.py` | `ComplexityGate.classify()` with file-scope heuristics | #3 |
| **NEW** `core/cache_discipline.py` | `CacheDiscipline.validate()` with 4 rules | #7 |
| **NEW** `core/tasks_ledger.py` | `generate_jsonl_from_md()`, `validate_tasks_jsonl()` | #13 |
| **MODIFY** `core/constitution.py` | Add `validate_placeholders()` for seed audit | #14 |
| **NEW** `cli/context.py` | Typer app: context pre, context post | #2 |
| **NEW** `cli/adhoc.py` | Typer app: adhoc pre, adhoc post | #3 |
| **NEW** `cli/constitution.py` | Typer app: constitution pre, constitution post | #5 |
| **NEW** `cli/inspect.py` | Commands: tasks list, issues list | #6 |
| **MODIFY** `cli/__init__.py` | Register new Typer apps; extend `_resolve_placeholder` to 6 vars; add `--json`/`--quiet` to init | #4, #10 |
| **MODIFY** `cli/_common.py` | Add `--json/--quiet` reusable callback/decorator | #9 |
| **MODIFY** `cli/micro.py` | `run_command`: swap booleans for `profile`; add `CacheDiscipline.validate()` hooks; train rollback in `_run_judge_phase`; `_run_pytest` → `--json-report` | #1, #7, #8, #16 |
| **MODIFY** `cli/macro.py` | Add `feature create`; wire context auto-trigger in explore/research/prd/shard post | #4, #2 |
| **MODIFY** `cli/meso.py` | tasks post: generate tasks.jsonl from tasks.md; wire context auto-trigger | #13, #2 |
| **MODIFY** `state/config.py` | Import `ExecutionProfile` re-export | #1 |
| **MODIFY** `AGENTS.md` | Remove stale `rgr run`, `manage-tasks.sh`, `sdd-parse-ast.sh`, `get-test-config.sh` refs | #11 |
| **MODIFY** 18× `SKILL.md` files | Replace `--no-judge`/`--no-refactor` with `--profile`; remove `.sh` refs; add `deviate <cmd> pre/post` | #12 |
| **MODIFY** `constitution_seed.md` | Add missing `${VARIABLE}` placeholders | #14 |
| **MODIFY** `pyproject.toml` | Add `pytest-json-report` dependency | #16 |

**[Rationale]:** Option B (Core Extraction) was chosen over alternatives because it directly satisfies the constitution's mandate that "no layer may be skipped" (`specs/constitution.md §[1_ARCHITECTURAL_PRINCIPLES]`). Currently business logic lives in CLI handlers — mixing concerns — this is a latent layer-violation that the 16-gap implementation must fix. The `specs/002-deviatdd-gap-analysis/explore.md` file registry shows `cli/micro.py:1082` lines mixing phase logic, pytest invocation, AST analysis, and git operations. Extracting profile, cache, and context logic to `core/` restores the three-layer contract. For P0 gaps (profile, context), this is mandatory — `cli/` should route, `core/` should compute. Each new `cli/<name>.py` module maps one-to-one to a new Typer subapp, keeping registration explicit in `src/deviate/cli/__init__.py:274-289` rather than relying on autodiscovery.

## [OPTIONS_MATRIX]

| Option | Complexity | Testability | Constitutional Alignment | Reversibility | Blast Radius | Verdict |
|--------|-----------|-------------|------------------------|---------------|-------------|---------|
| A: Monolithic CLI Extension | Low | Medium (CLI-tangled) | Low (layer violation) | High | Medium | Rejected for P0/P1 |
| **B: Core Extraction** | **Medium** | **High (pure-function core)** | **High (§Three-Layer Architecture)** | **Medium** | **Low** | **RECOMMENDED** |
| C: Layered Plugin | High | High | Low (no plugin model in constitution) | Low | High | Rejected |
| D: Full Domain Decomposition | Very High | High | Low (§Tech Stack: Typer) | Very Low | Very High | Rejected |

## [REJECTED_OPTIONS]

- **Option A (Monolithic CLI Extension):** Rejected for P0/P1 gaps because it perpetuates the existing layer violation that the 16-gap analysis (`specs/002-deviatdd-gap-analysis/explore.md`) identifies as the root cause. Acceptable only for trivially small P3 gaps (#15 docs, #14 seed audit).

- **Option C (Layered Plugin with autodiscovery):** Rejected because the constitution constrains tech stack to "Typer (CLI entry points)" (`specs/constitution.md §2_1_BACKEND`) — no plugin autodiscovery framework exists. Adding a registry would violate AGENTS.md simplicity discipline.

- **Option D (Full Domain Decomposition):** Rejected per AGENTS.md simplicity rule — "minimum code that solves the problem." Each gap maps to 1–2 functions in a small module; independent packages per gap add ceremony without benefit.

- **Separate ExecutionProfile in state/config.py vs core/profile.py:** Considered putting in `state/config.py`. Rejected because profile resolution is algorithmic mapping, not a persisted state schema — belongs in `core/` for unit-testability.

- **Inline context sync in macro/meso post handlers:** Considered to avoid extraction. Rejected because `deviate context post` must also work standalone per Gap #2 — extraction prevents duplication across 7 post handlers.

## [DESIGN_TRADEOFFS]

| Decision | Trade-off | Why This Side |
|----------|-----------|---------------|
| `ExecutionProfile` in `core/profile.py` vs `state/config.py` | Core purity vs config proximity | Core wins — profile mapping is algorithmic (3-way boolean resolution), not persisted state. Unit-testable without Pydantic. |
| New `cli/context.py` vs inline in `cli/__init__.py` | Module count vs file size | New file wins — context pre/post has ~200 lines of logic. `__init__.py` is already 289 lines. |
| `--json/--quiet` as decorator vs callback vs Typer mixin | Reusability vs Typer idiom | Decorator wins — `_common.py` exports `@with_json_quiet` that injects two options and wraps response. Keeps all 7×3 pre handlers consistent. |
| Train Rollback: `git reset --hard` vs `git revert` | Simplicity vs safety | **Modified per adversarial audit**: Use `git revert <green_sha>` instead of `--hard HEAD~1`. Never use `--hard` in automated pipeline. |
| Context auto-trigger: internal import vs subprocess | Coupling vs process boundary | Internal import wins — subprocess calls from within same process create CLI recursion issues. |
| tasks.jsonl generation in tasks_post vs specify_pre | When to generate | tasks_post wins — tasks.md is the human-authored artifact committed there; JSONL should derive from same command per Gap §13.1. |
| `pytest --json-report` mandatory vs optional toggle | Dep risk vs consistency | Optional toggle wins — string parsing kept as primary. Plugin may conflict with pytest-xdist or break on version upgrade (adversarial finding R10). |
| Feature create: standalone command vs function in macro.py | Discoverability vs file count | Function in `macro.py` wins — 30-line function doesn't justify a new file. |

## [CONTRARIAN_VIEWPOINTS]

- **Gap #1 (`--profile` enum):** The profile enum allows 3 of 4 possible boolean combinations. The missing combination (`no_judge=True, no_refactor=False`) is a plausible debugging workflow. Retain booleans as composable overrides to `--profile` per adversarial finding R01.

- **Gap #2 (Auto-Trigger Context Sync):** Coupling context sync to every post command creates a fragile dependency chain. If context sync fails (permission error, JSON parse failure, CLAUDE.md locked), the entire post operation fails after the artifact commit — leaving inconsistent state. Mitigate by making context sync best-effort with warning, not hard gate.

- **Gap #3 (Adhoc Complexity Gate):** File-scope heuristics measure file count, not semantic complexity. A "fix typo in 3 files" → MEDIUM (over-gated), "rename 50 variables in 1 file" → LOW (under-gated). Use LLM-based classification with confidence threshold instead.

- **Gap #7 (Cache Discipline):** Model switching in an opaque LLM session cannot be reliably detected from outside. The real enforcement is at phase-dispatch level (`_phase_map` in `micro.py`) where phase→model mapping is hard-coded. CacheDiscipline should audit at dispatch level, not session introspection.

- **Gap #8 (Train Rollback):** `git reset --hard` is weaponized against the wrong target. If YELLOW phase approved and committed amendments between RED and GREEN, `HEAD~1` may destroy legitimate work. Use precise SHA tracking (RED commit) and surgical checkout per adversarial finding R07.

- **Gap #9 (`--json`/`--quiet` decorator):** A uniform decorator imposes schema consistency across 15+ commands with structurally different contracts (specify pre has traceability fields, red pre has spec_dir). Use per-command serializers with a shared validation envelope, not a monolithic decorator.

- **Gap #12 (18 SKILL rewrites):** Simultaneous rewrites introduce copy-paste inconsistencies across all 18 files. Rewrite in dependency order (simplest skill first → complex skills) and verify each before proceeding, per adversarial finding R08.

- **Gap #13 (tasks.jsonl auto-generation):** Human-authored markdown is non-deterministic. Edge cases: code blocks that look like tasks, nested lists, mid-edit artifacts. Incorrect JSONL rows can never be removed under Append-Only Protocol. Generate proposal file (`.jsonl.proposal`), require `--confirm` flag to append, per adversarial finding R09.

## [RISK_REGISTER]

| Risk ID | Risk | Likelihood | Impact | Mitigation | Owner | Source Anchor |
|---------|------|------------|--------|------------|-------|---------------|
| R01 | `--profile` enum loses `no_judge=True, no_refactor=False` combo | M | L | Retain booleans as composable overrides to `--profile` | Architecture | Gap #1 |
| R02 | Context sync failure leaves inconsistent git/session state | H | M | Make context sync best-effort (warning only), not a hard gate | CLI Team | Gap #2 |
| R03 | Adhoc complexity heuristic misclassifies tasks | H | H | Use LLM-based classification with confidence threshold | CLI Team | Gap #3 |
| R04 | `specify pre` breaks when `feature create` internal API changes | M | H | Extract feature creation to `core/` library function | CLI Team | Gap #4 |
| R05 | `--json` decorator imposes uniform schema on variant contracts | M | M | Per-command serializers with shared validation envelope | CLI Team | Gap #9 |
| R06 | CacheDiscipline cannot detect model switching in opaque session | H | H | Enforce model at phase-dispatch level, not session introspection | Architecture | Gap #7 |
| R07 | `git reset --hard HEAD~1` destroys YELLOW-phase commits | M | H | Use `git revert` or tracked SHA reset; never `--hard` in automation | CLI Team | Gap #8 |
| R08 | 18 simultaneous SKILL.md rewrites introduce inconsistencies | H | M | Rewrite in dependency order (simplest→complex), verify each | Docs Team | Gap #12 |
| R09 | tasks.md auto-parser produces incorrect JSONL | M | H | Generate proposal file; require `--confirm` to append | CLI Team | Gap #13 |
| R10 | `pytest-json-report` breaks on version upgrade | L | H | Keep string parsing as primary; make `--json-report` optional | CLI Team | Gap #16 |
| R11 | Placeholder resolution falls out of sync with seed variables | M | L | Add `validate-placeholders` subcommand to `deviate init` | CLI Team | Gaps #10, #14 |
| R12 | Symlink enforcement fails on Windows | L | L | Add `os.name` guard; use copy fallback | CLI Team | Gap #11 |
| R13 | Ledger inspection parses corrupted JSONL mid-file | M | L | Per-line JSON validation with error reporting | CLI Team | Gap #6 |

## [CONSTITUTIONAL_ALIGNMENT_AUDIT]

| Constitutional Clause | Architectural Decision | Alignment | Notes |
|---|---|---|---|
| Three-Layer Architecture — no layer may be skipped | Gap #3: Adhoc fast-path compresses Macro layer | **Tension** | Adhoc fast-path compresses but doesn't eliminate Macro. HITL Gate 1 is programmatically bypassed — violates "No gate may be programmatically bypassed." Mitigate with `--skip-gates` flag requiring human opt-in. |
| Append-Only Ledger Protocol | Gap #13: Auto-generate tasks.jsonl from tasks.md | **Tension** | If implementation regenerates JSONL from scratch instead of appending, violates immutability. Gap text says "append corresponding PENDING rows" — aligned in intent. Mitigate with proposal file + `--confirm` flag. |
| Git Isolation Principle — clean branch, automatic commits | Gap #8: Train rollback via `git reset --hard` | **Tension** | `--hard` assumes linear clean history — breaks if YELLOW committed between RED and GREEN. Mitigate with `git revert` or tracked SHA reset per adversarial finding R07. |
| Tamper Guard & Micro-Sandboxing | Gap #8: JUDGE rollback re-routes to GREEN | **Aligned** | Re-entering GREEN reinforces Tamper Guard — baseline is RED commit post-reset. |
| HITL — three mandatory gates, no programmatic bypass | Gap #3: Complexity gate automates Gate 1 bypass | **Tension** | Low-complexity bypasses Design Approval without human interaction. Constitution forbids programmatic bypass. Mitigate with explicit opt-in. |
| Session Continuity — single LLM session across phases | Gap #7: CacheDiscipline enforces continuity | **Aligned** | Reinforces constitutional clause. Enforcement mechanism should be at phase-dispatch (hard-coded model routing) per R06. |
| Model Tiering — V4 Flash for high-frequency phases | Gap #7: CacheDiscipline validates model continuity | **Aligned** | CacheDiscipline reinforces tiering by detecting violations at dispatch layer. |
| Python 3.13, Typer + Rich | Gap #9: `--json`/`--quiet` flags | **Aligned** | Standard CLI flags compatible with Typer patterns. |
| TEST_COMMAND: pytest tests/ -v | Gap #16: Migrate to `--json-report` | **Tension** | Adding `--json-report` changes the test command. If plugin breaks, pipeline breaks. Mitigate: make optional, keep string parsing as primary. |
| RED phase: fail with AssertionError or NotImplementedError | Gap #16: `--json-report` outcome classification | **Aligned** | Structured JSON output still classifies PASS/ASSERTION_FAILURE/SYNTAX_ERROR — no semantic change. |
| REFACTOR runs regression gate | Gap #8: Rollback re-routes to GREEN | **Aligned** | Rollback preserves regression assumption: re-run GREEN from clean RED baseline. |
| DoD — Judge phase passed | Gap #8: Rollback causes re-entry to GREEN | **Aligned** | Rollback ensures violation addressed before task completes. DoD checkpoint enforced. |
| DoD — No governance violations | Gap #7: CacheDiscipline enforcement | **Aligned** | CacheDiscipline is itself a governance enforcement mechanism. |
| Quality gate: `mise run check` | All gaps #1–#16 | **Aligned** | All changes must pass `mise run check`. No gap relaxes this requirement. |

**Note on Tensions**: No row has `Alignment: Violation`. All Tensions have concrete mitigations documented in this design. The adversarial constitutional violation block raised by Subagent Gamma captured Tension findings with required actions — these are incorporated as risk mitigations (R01–R13) above. The workflow proceeds to HITL Gate 1.

## [SOURCE_REGISTRY]

| ID | Type | Source / Path | Relevance Note |
|----|------|---------------|----------------|
| SRC-001 | Explore_MD | `specs/002-deviatdd-gap-analysis/explore.md` | Primary source — 16 gaps, execution blocks, priority tags |
| SRC-002 | Constitution | `specs/constitution.md` | Governance rules for all architectural decisions |
| SRC-003 | Codebase_File | `src/deviate/cli/__init__.py` | CLI registration root — all Typer subapps and init command |
| SRC-004 | Codebase_File | `src/deviate/cli/micro.py` | TDD cycle execution, phase dispatch, `run_command` with booleans |
| SRC-005 | Codebase_File | `src/deviate/cli/macro.py` | Macro-layer pre/post commands (explore, research, prd, shard) |
| SRC-006 | Codebase_File | `src/deviate/cli/meso.py` | Meso-layer commands (specify, tasks, pr) |
| SRC-007 | Codebase_File | `src/deviate/state/config.py` | DeviateConfig, SessionState, phase transitions |
| SRC-008 | Codebase_File | `src/deviate/state/ledger.py` | IssueRecord, TaskRecord, append-only ledger models |
| SRC-009 | Codebase_File | `src/deviate/cli/_common.py` | Shared CLI utilities |
| SRC-010 | Codebase_File | `graphify-out/GRAPH_REPORT.md` | Graph-based architecture analysis of codebase |
| SRC-011 | Industry_Baseline | Python Pydantic v2 Field patterns | `Field(default_factory=...)`, `Literal` types for enum simulation |
| SRC-012 | Industry_Baseline | JSONL append-only ledger pattern | All state transitions immutable, canonical state from sequential parse |

## [STATUS_SUMMARY]

| Metric | Value |
|--------|-------|
| STATUS | AWAITING_HITL_GATE_1 |
| FEATURE_SLUG | 002-deviatdd-gap-analysis |
| EPIC_ID | 002 |
| GIT_BRANCH | main |
| SPEC_TARGET_DESIGN | specs/002-deviatdd-gap-analysis/design.md |
| SPEC_TARGET_DATAMODEL | specs/002-deviatdd-gap-analysis/data-model.md |
| NEXT_ACTION | Human reviews design.md + data-model.md, then invokes the `prd` skill |
