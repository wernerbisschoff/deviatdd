---
title: "AST/Structural Analysis Integration — JUDGE + PLAN + REFACTOR (Pareto High-ROI)"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-008
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/008-ast-phase-prioritization.md`
- **Primary Architectural Workstations**:
  - `src/deviate/core/treesitter.py` — new module: tree-sitter parser factory, query execution, diff structure extraction
  - `src/deviate/cli/micro.py:1108-1137` — `_run_judge_phase()`: inject structured diff summary before agent prompt
  - `src/deviate/cli/micro.py:2507-2538` — `_check_return_type_mismatch()`: replace with incremental tree-sitter parse + extended checks
  - `src/deviate/cli/meso.py` — plan phase: pre-scan target workstation files, inject file structure appendix into plan prompt
  - `src/deviate/prompts/auto/judge.md` — update prompt template to consume structured diff format
  - `src/deviate/prompts/auto/plan.md` — update prompt template to consume file structure appendix
  - `pyproject.toml` — add `tree-sitter>=0.24` dependency
- **Upstream Evidence**: `specs/explore/ast-tree-sitter.md` (phase integration potential table, existing AST usage), `specs/constitution.md` (model cost tiers)

## The Problem Contract
The explore.md (`specs/explore/ast-tree-sitter.md:200-213`) maps 10+ phases to AST integration potential. Pareto analysis shows 80% of value comes from 3 phases: JUDGE (Pro-tier, diff validation against spec saves full-cycle redo), PLAN (Pro-tier, pre-scan target files prevents wrong insertion points from cascading into 3-5 wasted tasks), and REFACTOR (already has fragile `_check_return_type_mismatch` using stdlib `ast` — upgrade to tree-sitter incremental + dead-code/duplication checks). This issue implements AST across those 3 phases only — all other phases are explicitly excluded per token/cost analysis.

## Scope Boundaries
### Hard Inclusions
- Create `src/deviate/core/treesitter.py` with: tree-sitter parser factory (Python grammar), `extract_changed_symbols()` that parses `git diff` output and returns structured change data, `extract_file_structure()` that extracts function/class signatures from a target file, and `incremental_parse()` for re-parsing only changed ranges
- JUDGE: in `_run_judge_phase()`, after collecting `git diff` output, call `extract_changed_symbols()` to produce a structured change summary. Append it to the judge prompt as `## Structured Diff Summary` (below the raw diff). Update `judge.md` prompt template to consume this section.
- PLAN: in the plan agent invocation path (meso layer), pre-scan target workstation files from the issue's `## System Topology Mapping` section. Call `extract_file_structure()` on each file and inject a `## Target File Structure` appendix into the plan prompt. Update `plan.md` prompt template to consume this.
- REFACTOR: replace the stdlib `ast` in `_check_return_type_mismatch()` with tree-sitter incremental parse. Extend checks: detect dead code (unused functions with no call sites), duplicated code blocks (similar AST subtrees ≥ 5 lines), and cyclomatic complexity warnings (≥ 10). Use `incremental_parse()` so large file re-scans are cheap.
- Add `tree-sitter>=0.24` to `pyproject.toml` dependencies
- All existing tests under `tests/` must pass after integration

### Defensive Exclusions
- Do NOT integrate AST into RED, GREEN, YELLOW, TASKS, MACRO (explore/research/prd/shard), or TamperGuard — token/cost analysis shows low ROI for these phases
- Do NOT add tree-sitter grammar compilation — use pre-built Python grammar from `tree-sitter-languages` package or bundle
- Do NOT change the JUDGE agent's decision logic — only add structured context; the agent still makes the call
- Do NOT add mypy/pyre type checking integration — structural analysis only, no type system
- Do NOT modify test files beyond adding/updating unit tests for the new module

## Phase Prioritization Analysis (Reference)
Embedded from the adhoc conversation analysis. All phases ranked by token/cost ROI:

| Phase | Rank | Model Tier | AST Value | Rationale |
|-------|------|-----------|-----------|-----------|
| **JUDGE** | HIGH-ROI | V4 Pro (expensive) | Parse `git diff`, extract changed signatures, 15x token reduction on Pro tier. Prevents full-cycle redo. | Implemented in this issue |
| **PLAN** | HIGH-ROI | V4 Pro (expensive) | Pre-scan target files, inject structure. 50x token reduction. Prevents cascade failure across 3-5 tasks. | Implemented in this issue |
| **REFACTOR** | MEDIUM-ROI | V4 Flash (cheap) | Replace stdlib `ast` with incremental tree-sitter + extended checks. 10x faster on large files. | Implemented in this issue |
| GREEN | LOW-ROI | V4 Flash | Could enhance prompts with structural constraints. Speculative value — no evidence GREEN fails from missing context. | Excluded |
| YELLOW | LOW-ROI | V4 Pro | Fires rarely (only on tamper). Low aggregate ROI. | Excluded |
| RED | SKIP | V4 Flash | Produces test stubs. AST of `assert` adds nothing pytest doesn't already verify. | Excluded |
| TASKS | SKIP | V4 Pro | Text decomposition, no code to parse. | Excluded |
| MACRO | SKIP | V4 Flash | Operates on Markdown. Tree-sitter parses Python. | Excluded |
| TamperGuard | SKIP | V4 Flash | File hashing already catches unauthorized edits. | Excluded |

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-008`
- **Acceptance Criteria Tokens**: `AC-ADHOC-008-01`, `AC-ADHOC-008-02`, `AC-ADHOC-008-03`, `AC-ADHOC-008-04`, `AC-ADHOC-008-05`
- **Data Model Entities**: None (no new state entities; tree-sitter parser is stateless)

## User Stories Ledger
- **US-008-01**: As a DeviaTDD operator running `deviate run`, I want the JUDGE phase to receive a structured diff summary instead of raw diff text so that the expensive Pro-tier agent spends fewer tokens on diff syntax parsing and more on compliance evaluation. *(Ref: FR-ADHOC-008)*
- **US-008-02**: As a DeviaTDD architect running `/plan`, I want the plan agent to receive a pre-extracted file structure appendix for target workstation files so that the Pro-tier agent doesn't waste tokens reading large files and knows exact insertion points before task decomposition. *(Ref: FR-ADHOC-008)*
- **US-008-03**: As a DeviaTDD operator, I want REFACTOR phase dead-code and duplication detection so that `_check_return_type_mismatch` catches more than just 7 builtin return types without re-parsing the entire file every cycle. *(Ref: FR-ADHOC-008)*

## ATDD Acceptance Criteria
**Scenario 008-01**: Structured diff injected into JUDGE prompt
**Given** a GREEN-phase implementation produces a diff with changed function signatures
**When** `_run_judge_phase()` runs `git diff RED..HEAD`
**Then** the judge prompt contains a `## Structured Diff Summary` section listing only changed `FunctionDef`/`ClassDef` nodes with old/new signatures, and the raw diff follows below for full context.

**Scenario 008-02**: File structure injected into PLAN prompt
**Given** a PLAN phase is invoked for an issue with target workstation files listed
**When** the plan agent prompt is assembled
**Then** it contains a `## Target File Structure` appendix with function/class signatures and import blocks extracted from each target file via tree-sitter.

**Scenario 008-03**: Incremental REFACTOR checks
**Given** a file has been modified since the last parse
**When** `_check_return_type_mismatch()` runs in the REFACTOR phase
**Then** it uses tree-sitter incremental parse (re-parsing only changed ranges), detects dead code (unused functions), duplicated code blocks (similar AST subtrees ≥ 5 lines), and cyclomatic complexity ≥ 10 — in addition to existing builtin return-type checks.

**Scenario 008-04**: No regressions in excluded phases
**Given** AST integration targets only JUDGE, PLAN, and REFACTOR
**When** RED, GREEN, YELLOW, TASKS, or MACRO phases execute
**Then** no tree-sitter code is invoked — execution path is unchanged from pre-integration.

**Scenario 008-05**: Dependency is declared and importable
**Given** `pyproject.toml` declares `tree-sitter>=0.24`
**When** `from deviate.core.treesitter import extract_changed_symbols, extract_file_structure` is executed
**Then** the import succeeds and the function signatures match the module contract.

## Edge Cases and Boundaries
- **Empty diff**: JUDGE `git diff` produces no output → `extract_changed_symbols()` returns empty structure list; judge prompt proceeds with no structured section.
- **Syntax errors in modified file**: Tree-sitter parse fails on broken Python → fall back to raw diff text (graceful degradation, same as current behavior when `ast.parse` raises `SyntaxError`).
- **File not found in PLAN workstation list**: Target file listed in issue but missing from repo → log warning, skip that file in structure extraction, produce appendix with available files only.
- **Large files (>5000 lines)**: Tree-sitter incremental parse limits `changed_ranges()` scope. Full initial parse is one-time cost; subsequent uses only re-parse changed ranges.
- **No tree-sitter Python grammar available**: Grammar must be resolvable at import time. Use `tree-sitter-languages` package or bundle a compiled `.so` grammar. If grammar cannot be loaded, module raises `ImportError` with clear message — no silent fallback.

## Performance Constraints
- `extract_file_structure()`: ≤ 200ms per file (initial parse); ≤ 20ms incremental
- `extract_changed_symbols()`: ≤ 100ms per diff
- `_check_return_type_mismatch()` (upgraded): ≤ 300ms per file (initial); ≤ 50ms incremental
- Structured diff summary in JUDGE prompt: ≤ 500 tokens (vs raw diff which can be 3000+)

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**:
  - `tests/core/test_treesitter.py::test_extract_changed_symbols_single_function` — diff with one changed function → correct structure output
  - `tests/core/test_treesitter.py::test_extract_changed_symbols_empty_diff` — empty diff → empty structure list
  - `tests/core/test_treesitter.py::test_extract_file_structure_basic` — file with classes and functions → correct signature extraction
  - `tests/core/test_treesitter.py::test_incremental_parse_changed_ranges` — two consecutive parses of modified file → only changed ranges re-parsed
- **Integration Sandbox Targets**:
  - `tests/test_micro/test_judge.py` — verify structured diff section appears in judge prompt
  - `tests/test_micro/test_refactor.py` — verify upgraded `_check_return_type_mismatch` catches dead code
  - `tests/test_meso/test_plan.py` — verify file structure appendix appears in plan prompt

## Demonstration Path
```bash
# Unit tests for the new module
mise run test tests/core/test_treesitter.py -v

# Verify JUDGE prompt contains structured diff section
mise run test tests/test_micro/test_judge.py -v

# Verify REFACTOR dead-code detection
mise run test tests/test_micro/test_refactor.py -v

# Verify PLAN prompt contains file structure appendix
mise run test tests/test_meso/test_plan.py -v

# Full suite regression
mise run test
```
