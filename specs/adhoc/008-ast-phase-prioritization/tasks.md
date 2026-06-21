# Implementation Tasks: feat/adhoc/008-ast-phase-prioritization

## Phase 1: Tree-sitter Foundation
**Goal**: Deliver `src/deviate/core/treesitter.py` module with parser factory, `extract_changed_symbols()`, `extract_file_structure()`, and `incremental_parse()` — the foundation consumed by JUDGE, PLAN, and REFACTOR integration tasks.

### Tasks

- TSK-008-01: Core treesitter module with parser factory and structure extraction functions
  - **Type**: Infra_Batch
  - **Mode**: TDD
  - **Test Strategy**: Solitary_Unit
  - **Verification**: `pytest tests/core/test_treesitter.py -v`
  - **Estimated Time**: 90 minutes
  - **Files**:
    - `src/deviate/core/treesitter.py`
    - `tests/core/test_treesitter.py`
    - `pyproject.toml`
  - **Rationale**: `src/deviate/core/treesitter.py` is the new module required by all three integration phases (JUDGE, PLAN, REFACTOR). Per the issue's `[SYSTEM_TOPOLOGY_MAPPING]` it MUST exist with parser factory + three public functions. `tests/core/test_treesitter.py` matches the issue's `[MULTI_TIERED_VERIFICATION_TARGETS]` unit test paths and follows the existing pattern in `tests/core/test_agent.py`. `pyproject.toml` adds the `tree-sitter>=0.24` runtime dependency required by the new module per AC-ADHOC-008-05.
  - **Details**:
    - **Red**: Write failing tests in `tests/core/test_treesitter.py::TestExtractChangedSymbols::test_single_function` (diff with one changed `FunctionDef` returns a structured dict with `name`, `old_signature`, `new_signature`), `::test_empty_diff` (empty diff returns empty list), `::TestExtractFileStructure::test_basic` (file with classes and functions returns `imports`, `functions`, `classes` lists), `::TestIncrementalParse::test_changed_ranges` (two consecutive parses — only `changed_ranges()` differ between calls).
    - **Green**: Implement `src/deviate/core/treesitter.py` with module-level `_PY_LANGUAGE` cache loaded via `tree_sitter_languages.get_language("python")` at import time, `get_parser() -> tree_sitter.Parser`, `extract_changed_symbols(diff_text: str, repo_root: Path) -> list[dict]`, `extract_file_structure(filepath: Path) -> dict`, and `incremental_parse(filepath: Path, old_tree: tree_sitter.Tree | None) -> tuple[tree_sitter.Tree, list[tuple[int,int,int,int]]]`. Use tree-sitter `(function_definition name: (identifier) parameters: (parameters) return_type: (type))` and `(class_definition name: (identifier) superclasses: (argument_list))` queries. Add `"tree-sitter>=0.24"` and `"tree-sitter-languages>=1.10"` to `pyproject.toml` `dependencies` list.
    - **Refactor**: Cache `_PY_LANGUAGE` at module level to avoid repeated grammar loads; raise `ImportError` with clear message if grammar cannot be loaded (no silent fallback per spec edge case); document performance budget per function in docstrings.
    - **Edge Cases**: Empty diff returns `[]`; syntax errors in target file return empty structure (graceful degradation); file not found raises `FileNotFoundError`; missing tree-sitter grammar raises `ImportError` at import time.
    - **Acceptance**: All 4 unit tests pass; `from deviate.core.treesitter import extract_changed_symbols, extract_file_structure, get_parser, incremental_parse` succeeds; `extract_file_structure()` completes in ≤200ms per AC-ADHOC-008 perf budget.

---

## Phase 2: JUDGE Phase Integration
**Goal**: Inject a `## Structured Diff Summary` section into the JUDGE prompt using `extract_changed_symbols()` so the V4 Pro agent parses changed `FunctionDef`/`ClassDef` nodes instead of raw diff text.

### Tasks

- TSK-008-02: Wire tree-sitter into `_run_judge_phase()` and update `judge.md` prompt template
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_micro/test_judge.py -v`
  - **Estimated Time**: 60 minutes
  - **Dependency**: TSK-008-01
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `src/deviate/prompts/auto/judge.md`
    - `tests/test_micro/test_judge.py`
  - **Rationale**: `src/deviate/cli/micro.py:1101-1159` (`_run_judge_phase`) currently appends raw `git diff RED..HEAD` text to the judge prompt per US-008-01 and AC-ADHOC-008-01. Per the issue's `[SYSTEM_TOPOLOGY_MAPPING]` this is the integration surface. `src/deviate/prompts/auto/judge.md` consumes the new `${structured_diff_summary}` placeholder per AC-ADHOC-008-01's Gherkin scenario. `tests/test_micro/test_judge.py` extends the existing integration test file with a new assertion that the structured diff section appears in the assembled judge prompt.
  - **Details**:
    - **Red**: Add `TestStructuredDiffInjection::test_structured_diff_in_prompt` to `tests/test_micro/test_judge.py`. Test creates a `tmp_git_repo` with a Python file containing one `FunctionDef`, makes a commit, then invokes `judge pre` with a GREEN-phase task record. Assert that the resulting prompt (via stdout JSON contract or mocked prompt assembly) contains the substring `## Structured Diff Summary` and references the changed function name. Mock `deviate.cli.micro._run_pytest` per AGENTS.md perf mandate.
    - **Green**: In `_run_judge_phase()` at `src/deviate/cli/micro.py:1123`, after capturing `diff` from `subprocess.run(...)`, call `from deviate.core.treesitter import extract_changed_symbols` then `structure = extract_changed_symbols(diff, root)`. If structure is non-empty, format as `## Structured Diff Summary\n\n{markdown}` and prepend to the prompt string. Update `prompt = _build_auto_prompt("judge", task, root) + structured_summary + f"\n\n<diff>\n{diff}\n</diff>\n"`. Update `src/deviate/prompts/auto/judge.md` STEP_1 to read the `${structured_diff_summary}` section in its execution sequence.
    - **Refactor**: Extract `_format_structured_diff(structure: list[dict]) -> str` helper inside `micro.py`; keep the raw diff appended after structured summary so the agent retains full context; add a single-line guard `if structure:` to skip injection when diff has no parseable symbols.
    - **Edge Cases**: Empty diff → no structured summary, prompt proceeds with raw diff only; syntax errors in changed Python file → `extract_changed_symbols` returns empty list → no injection (graceful degradation per AC spec); non-Python files in diff → ignored by tree-sitter query, only Python `FunctionDef`/`ClassDef` nodes appear.
    - **Acceptance**: Test passes; raw diff still appears in prompt after structured summary; structured summary is ≤500 tokens for typical diffs; `_run_judge_phase()` does not break existing tests.

---

## Phase 3: PLAN Phase Integration
**Goal**: Pre-scan target workstation files from an issue's `## System Topology Mapping` section and inject a `## Target File Structure` appendix into the PLAN agent prompt.

### Tasks

- TSK-008-03: Wire tree-sitter into `_meso_run()` and update `plan.md` prompt template
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_meso/test_plan.py -v`
  - **Estimated Time**: 75 minutes
  - **Dependency**: TSK-008-01
  - **Files**:
    - `src/deviate/cli/meso.py`
    - `src/deviate/prompts/auto/plan.md`
    - `tests/test_meso/test_plan.py`
  - **Rationale**: `src/deviate/cli/meso.py:_meso_run()` builds the plan phase contract at lines 1261-1270 and invokes the plan agent at line 1276 — this is the integration surface per the issue's `[SYSTEM_TOPOLOGY_MAPPING]` and US-008-02. Per AC-ADHOC-008-02 the appendix must be injected via the `${PLACEHOLDER}` mechanism used by `assemble_prompt()` in `src/deviate/prompts/assembly.py:112-119`. `src/deviate/prompts/auto/plan.md` consumes the new `${file_structure_appendix}` placeholder. `tests/test_meso/test_plan.py` is a new test file explicitly named in the issue's `[MULTI_TIERED_VERIFICATION_TARGETS]`.
  - **Details**:
    - **Red**: Create `tests/test_meso/test_plan.py::TestFileStructureInjection::test_appendix_in_prompt_contract`. Test creates a `tmp_git_repo`, writes an issue file with a `## System Topology Mapping` section listing 2 existing Python files, invokes `_meso_run` (or mocks `_invoke_agent_phase` to capture the contract dict), and asserts that `contract["file_structure_appendix"]` is non-empty and contains the substring `## Target File Structure`. Use `tmp_git_repo` fixture and `_git_env()` from `tests.conftest`.
    - **Green**: In `src/deviate/cli/meso.py:_meso_run()`, after building `contract` dict (line ~1270) and before `_invoke_agent_phase("plan", contract, ...)` (line 1276), add a helper `_build_file_structure_appendix(spec_path, worktree_path) -> str` that: (1) reads `spec_path` text, (2) extracts `## System Topology Mapping` section, (3) finds bullet points with `` `path/to/file.py` `` paths, (4) for each path that exists relative to `worktree_path`, calls `extract_file_structure(filepath)`, (5) formats as `## Target File Structure\n\n### {path}\n\n{structure_md}`. Add `contract["file_structure_appendix"] = appendix` to the contract dict. Update `src/deviate/prompts/auto/plan.md` to include `${file_structure_appendix}` placeholder in the `<execution_sequence>` section between `context_loading` and `codebase_scan` steps.
    - **Refactor**: Extract a private `_parse_topology_mapping(spec_text: str) -> list[str]` regex helper in `meso.py` that uses `r'`- `` `([^`]+)` `` regex to extract file paths from the bullet list; reuse the existing `_resolve_specs_root()` and `PurePosixPath` conventions for path normalization; log a warning via `console.print("[yellow]FILE_STRUCTURE_SKIP[/] ...")` for missing files per spec edge case.
    - **Edge Cases**: Issue file missing `## System Topology Mapping` section → return empty appendix string; workstation file listed but not present in worktree → log warning and skip; multiple files → append all per-file sections; non-Python file paths → `extract_file_structure` raises `NotImplementedError` → log warning, skip.
    - **Acceptance**: Test passes; contract dict has `file_structure_appendix` key; appendix contains all existing Python files; appendix is empty (not error) when no files exist; `_meso_run` does not break existing tests.

---

## Phase 4: REFACTOR Phase Integration
**Goal**: Replace stdlib `ast` in `_check_return_type_mismatch()` with tree-sitter incremental parse, and extend checks to include dead-code detection, duplication detection, and cyclomatic complexity warnings.

### Tasks

- TSK-008-04: Replace stdlib `ast` with tree-sitter incremental parse + extended checks
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_micro/test_refactor.py -v`
  - **Estimated Time**: 75 minutes
  - **Dependency**: TSK-008-01
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/test_micro/test_refactor.py`
  - **Rationale**: `src/deviate/cli/micro.py:2507-2539` (`_check_return_type_mismatch`) is the sole stdlib `ast` consumer per the explore.md discovery audit (`specs/explore/ast-tree-sitter.md:106-124`). The issue's `[SYSTEM_TOPOLOGY_MAPPING]` and AC-ADHOC-008-03 require this function to use tree-sitter incremental parse + extended checks. `tests/test_micro/test_refactor.py` is the existing integration test file referenced in the issue's `[MULTI_TIERED_VERIFICATION_TARGETS]`.
  - **Details**:
    - **Red**: Add `TestReturnTypeMismatchUpgraded::test_dead_code_detection`, `::test_duplicated_code_blocks`, `::test_cyclomatic_complexity_warning`, `::test_existing_builtin_check_preserved` to `tests/test_micro/test_refactor.py`. Tests create Python files with: (a) unused function with no call sites, (b) two similar function bodies >5 lines, (c) function with >10 branch nodes, (d) function annotated `-> int` returning `str`. Assert that `_check_return_type_mismatch(filepath)` returns a non-empty list with the expected issue strings.
    - **Green**: Replace `_check_return_type_mismatch()` body in `src/deviate/cli/micro.py:2507-2539`. Implement: (1) use `get_parser()` + `incremental_parse(filepath, old_tree)` from `deviate.core.treesitter`; (2) reuse tree-sitter `(function_definition return_type: ...) (return)` query to preserve existing builtin return-type checks (preserve `str`/`int`/`float`/`bool`/`list`/`dict`/`tuple`/`set` validation from lines 2519-2539); (3) add dead-code detection via `(function_definition name: (identifier) @name)` query + scan for `call` expression nodes referring to that name; (4) add duplicated code detection by hashing function body AST subtrees (excluding whitespace) and flagging subtrees with identical hashes and ≥5 lines; (5) add cyclomatic complexity by counting `(if_statement)`, `(for_statement)`, `(while_statement)`, `(except_clause)`, `(match_case)` nodes per function body and warning at ≥10.
    - **Refactor**: Maintain `_check_return_type_mismatch(filepath: str) -> list[str]` signature (string return, not dataclass) so callers in `refactor_post()` are unchanged; cache the parser and old_tree at module level (single `tree_sitter.Parser()` instance); document the new issue prefixes (`DEAD_CODE:`, `DUPLICATED_CODE:`, `COMPLEXITY:`) in docstring; preserve the existing `SyntaxError` → empty issues fallback by wrapping tree-sitter errors.
    - **Edge Cases**: File not parseable by tree-sitter → return empty issues (graceful degradation); function with no `return_type` annotation → skip builtin check, still apply dead-code and complexity checks; very large file (>5000 lines) → incremental parse returns only changed ranges; bare `except:` clause counts as one branch in complexity.
    - **Acceptance**: All new tests pass; existing `_check_return_type_mismatch` behavior preserved (builtin check still works); upgraded function completes in ≤300ms per AC perf budget; full test suite passes.

---

## Phase 5: SHARD Phase Integration
**Goal**: Inject a `## Codebase Structure` appendix into the SHARD contract using `extract_file_structure()` so the Qwen3.7-Plus agent produces issues with accurate `source_file` mappings and topology identification.

### Tasks

- TSK-008-05: Wire tree-sitter into `shard_pre()` and update `shard.md` prompt template
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_macro/test_shard.py -v`
  - **Estimated Time**: 75 minutes
  - **Dependency**: TSK-008-01
  - **Files**:
    - `src/deviate/cli/macro.py`
    - `src/deviate/prompts/auto/shard.md`
    - `tests/test_macro/test_shard.py`
  - **Rationale**: `src/deviate/cli/macro.py:544-588` (`shard_pre`) builds the contract dict at line ~576 and invokes the shard agent via `_cycle_phase()`. Per the issue's expanded scope, this is the integration surface for SHARD. `src/deviate/prompts/auto/shard.md` consumes the new `${codebase_structure_appendix}` placeholder. `tests/test_macro/test_shard.py` is a new test file for SHARD integration.
  - **Details**:
    - **Red**: Create `tests/test_macro/test_shard.py::TestCodebaseStructureInjection::test_appendix_in_contract`. Test creates a `tmp_git_repo`, writes a PRD file with referenced Python files, invokes `shard_pre()` (or mocks `_emit_contract` to capture the contract dict), and asserts that `contract["codebase_structure_appendix"]` is non-empty and contains the substring `## Codebase Structure`. Use `tmp_git_repo` fixture and `_git_env()` from `tests.conftest`.
    - **Green**: In `src/deviate/cli/macro.py:shard_pre()`, after building the contract dict (line ~576) and before `_emit_contract()`, add a helper `_build_codebase_structure_appendix(prd_path, worktree_path) -> str` that: (1) reads `prd_path` text, (2) extracts file paths from PRD references or scans `src/` directory for Python files, (3) for each path that exists relative to `worktree_path`, calls `extract_file_structure(filepath)`, (4) formats as `## Codebase Structure\n\n### {path}\n\n{structure_md}`. Add `codebase_structure_appendix=appendix` to the `_emit_contract()` call. Update `src/deviate/prompts/auto/shard.md` to include `${codebase_structure_appendix}` placeholder in the `<execution_sequence>` section between `prd_reading` and `vertical_slicing` steps. Add instruction: "Before scanning files with git tools, read the `## Codebase Structure` appendix (pre-extracted tree-sitter analysis of source files). This provides function/class signatures without requiring you to read full file contents — use it to identify insertion points and accurate `source_file` mappings."
    - **Refactor**: Extract a private `_scan_source_files(prd_text: str, worktree_path: Path) -> list[Path]` regex helper in `macro.py` that uses `r'`([^`]+\.py)` regex to extract Python file paths from PRD text, falling back to `src/` directory scan if no paths found; log a warning via `console.print("[yellow]CODEBASE_STRUCTURE_SKIP[/] ...")` for missing files per spec edge case.
    - **Edge Cases**: PRD missing file references → scan `src/` directory for Python files; source file listed but not present in worktree → log warning and skip; multiple files → append all per-file sections; non-Python file paths → `extract_file_structure` raises `NotImplementedError` → log warning, skip.
    - **Acceptance**: Test passes; contract dict has `codebase_structure_appendix` key; appendix contains all existing Python files; appendix is empty (not error) when no files exist; `shard_pre` does not break existing tests.

---

## Phase 6: ADHOC Flow Integration
**Goal**: Extend `adhoc pre` command to scan source files and write `specs/adhoc/codebase_structure.md` artifact, then update the adhoc skill prompt to consume it for accurate topology mapping.

### Tasks

- TSK-008-06: Extend `adhoc pre` with file structure extraction and update skill prompt
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_cli/test_adhoc.py -v`
  - **Estimated Time**: 60 minutes
  - **Dependency**: TSK-008-01
  - **Files**:
    - `src/deviate/cli/adhoc.py`
    - `src/deviate/prompts/skills/deviate-adhoc/SKILL.md`
    - `tests/test_cli/test_adhoc.py`
  - **Rationale**: `src/deviate/cli/adhoc.py:45-84` (`adhoc pre`) currently emits a contract JSON to stdout but provides no codebase context. Per the issue's expanded scope, this is the integration surface for ADHOC. `src/deviate/prompts/skills/deviate-adhoc/SKILL.md` step 3 ("Lightweight Discovery Pass") instructs the agent to use grep/glob — update it to read the pre-extracted artifact first. `tests/test_cli/test_adhoc.py` extends the existing test file.
  - **Details**:
    - **Red**: Add `TestAdhocCodebaseStructure::test_artifact_created` to `tests/test_cli/test_adhoc.py`. Test creates a `tmp_git_repo` with Python source files in `src/`, invokes `adhoc pre` with a description, and asserts that `specs/adhoc/codebase_structure.md` is created and contains `## Codebase Structure` with file signatures. Use `tmp_git_repo` fixture and `_git_env()` from `tests.conftest`.
    - **Green**: In `src/deviate/cli/adhoc.py:adhoc pre()`, after the complexity gate check (line ~55), add a helper `_build_codebase_structure_artifact(scan_dir: Path, output_path: Path) -> None` that: (1) scans `scan_dir` (default `src/`, configurable via `--scan-dir` option) for Python files, (2) for each file, calls `extract_file_structure(filepath)`, (3) formats as `## Codebase Structure\n\n### {path}\n\n{structure_md}`, (4) writes to `output_path` (default `specs/adhoc/codebase_structure.md`). Add `--scan-dir` option to the `adhoc pre` command signature. Emit the artifact path in the contract JSON: `codebase_structure_path=str(output_path)`. Update `src/deviate/prompts/skills/deviate-adhoc/SKILL.md` step 3 to add: "If `specs/adhoc/codebase_structure.md` exists (created by `adhoc pre`), read it first for pre-extracted file signatures — use it to identify target files and existing patterns before falling back to grep/glob. This avoids reading full file contents for structure discovery."
    - **Refactor**: Extract a private `_scan_directory_for_python_files(scan_dir: Path) -> list[Path]` helper in `adhoc.py` that uses `scan_dir.rglob("*.py")` to find all Python files; log a warning via `console.print("[yellow]CODEBASE_STRUCTURE_SKIP[/] ...")` for missing scan directory; ensure the artifact is idempotent (overwrite if exists).
    - **Edge Cases**: Scan directory does not exist → log warning, skip artifact creation; no Python files found → write empty artifact with header only; `extract_file_structure` raises `NotImplementedError` for non-Python files → log warning, skip; artifact write fails → log error, proceed without artifact (graceful degradation).
    - **Acceptance**: Test passes; `specs/adhoc/codebase_structure.md` is created by `adhoc pre`; artifact contains all existing Python files in `src/`; contract JSON includes `codebase_structure_path` key; skill prompt references the artifact; existing `adhoc pre` tests do not break.

---

## Phase 7: Spec Alignment and Regression Validation
**Goal**: Sync authoritative spec documents (`specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`) with the new tree-sitter integration across all five phases (JUDGE, PLAN, REFACTOR, SHARD, ADHOC) and verify full test suite passes with no regressions.

### Tasks

- TSK-008-07: Update API/architecture specs and run full regression
  - **Type**: Migration
  - **Mode**: IMMEDIATE
  - **Verification**: `mise run check`
  - **Estimated Time**: 45 minutes
  - **Dependency**: TSK-008-02, TSK-008-03, TSK-008-04, TSK-008-05, TSK-008-06
  - **Files**:
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
  - **Rationale**: `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` are authoritative source-of-truth documents per the project's AGENTS.md spec-alignment mandate. They must reflect the new `deviate.core.treesitter` module, JUDGE/PLAN/REFACTOR/SHARD/ADHOC integration points, and dependency on `tree-sitter>=0.24`. Migration-type task is appropriate since this is a documentation update with no behavior change. IMMEDIATE mode because doc edits are trivial (config/docs/constants per decision tree item 1) and the changes are mechanical reflections of already-verified code.
  - **Details**:
    - **Implementation**: Append a new section `## Tree-sitter Integration (ISS-ADH-008)` to `specs/DeviaTDD-architecture.md` documenting: (1) `src/deviate/core/treesitter.py` public API, (2) JUDGE phase structured diff injection, (3) PLAN phase file structure appendix, (4) REFACTOR phase extended checks, (5) SHARD phase codebase structure appendix, (6) ADHOC flow codebase structure artifact. Add a section to `specs/DeviaTDD-api.md` under `## Core Modules` listing `treesitter.get_parser`, `extract_changed_symbols`, `extract_file_structure`, `incremental_parse` signatures. Update the `[3_2_DATABASE]` or appropriate section in `architecture.md` if needed (no DB changes — skip if no relevant section).
    - **Refactor**: Verify both spec files reference `src/deviate/core/treesitter.py` by exact path; cross-link to the issue `ISS-ADH-008` in a "See also" footer; remove any stale references to stdlib `ast` as the sole AST implementation.
    - **Acceptance**: Both spec files contain updated sections referencing the new module and all five integration phases; no broken markdown links; `mise run check` passes (lint + full test suite per `[DEFINITION_OF_DONE]`).

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (TSK-008-01) → Phase 2 (TSK-008-02) + Phase 3 (TSK-008-03) + Phase 4 (TSK-008-04) + Phase 5 (TSK-008-05) + Phase 6 (TSK-008-06) → Phase 7 (TSK-008-07)

**Critical Dependency Chains**:
- TSK-008-01 (foundation module) must precede TSK-008-02, TSK-008-03, TSK-008-04, TSK-008-05, TSK-008-06 (all import from `deviate.core.treesitter`)
- TSK-008-02, TSK-008-03, TSK-008-04, TSK-008-05, TSK-008-06 must precede TSK-008-07 (spec docs reference the implemented modules)

**Risk Hotspots**:
- Tree-sitter grammar availability — `tree-sitter-languages` may need version pin to ensure Python grammar loads correctly on Python 3.13
- REFACTOR upgrade complexity — `_check_return_type_mismatch` runs on every REFACTOR cycle, so regression test coverage is critical
- PLAN phase pre-scan cost — must run in <200ms total per AC perf budget; if multiple workstation files exist, sum must stay under budget
- SHARD phase scan cost — scanning entire `src/` directory may exceed perf budget for large codebases; consider limiting to top-level declarations or caching results
- ADHOC artifact staleness — `specs/adhoc/codebase_structure.md` may become stale if source files change between `adhoc pre` and skill execution; document this limitation in the skill prompt

**Merge Conflict Boundaries**:
- `src/deviate/cli/micro.py` — touched by TSK-008-02 (JUDGE lines 1101-1159) and TSK-008-04 (REFACTOR lines 2507-2539). Different line ranges, no overlap.
- `src/deviate/cli/macro.py` — touched by TSK-008-05 (SHARD lines 544-588). No overlap with existing work.
- `src/deviate/cli/adhoc.py` — touched by TSK-008-06 (ADHOC lines 45-84). No overlap with existing work.
- `pyproject.toml` — touched by TSK-008-01 only.
- Test files `tests/test_micro/test_judge.py`, `tests/test_micro/test_refactor.py`, `tests/test_macro/test_shard.py`, `tests/test_cli/test_adhoc.py` — each task appends new test classes; sequential appends should not conflict.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations (init, add, commit, branch, worktree, checkout, log, status, push) MUST operate on a temporary directory initialized as a fresh git repo via `tmp_path` (pytest) or `tempfile.TemporaryDirectory`. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py` (which calls `git init` inside `tmp_path` and configures a test user). Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution. All tests are TDD and run repeatedly; accidental mutations corrupt the development workflow.
- **Pytest Mock Mandate**: Tests that invoke CLI commands which internally call `_run_pytest` (e.g., `refactor_post`, `judge_pre` with test runs) MUST mock `deviate.cli.micro._run_pytest` with an appropriate `subprocess.CompletedProcess` return value. Use `@patch("deviate.cli.micro._run_pytest")` decorator and `mock_pytest.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="1 passed", stderr="")`. This prevents the full test suite (~5s) from running as a subprocess for every CLI invocation in tests.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`. This is the **sole enabler** of test isolation — without it, tests must use fragile `chdir` tricks or operate on the real repo.

```python
# DO: accept repo_path, default to cwd
def find_repo_root(start_at: Path | None = None) -> Path:
    start_at = start_at or Path.cwd()

def stage_and_commit(message: str, files: list[Path], repo: Path | None = None) -> str:
    repo = repo or Path.cwd()
    subprocess.run(["git", "add", ...], cwd=repo, check=True)

# DON'T: hard-code Path.cwd() or rely on ambient working directory
def find_repo_root() -> Path:  # BAD — untestable
    ...
```

**Consequence**: Every per-task Git Isolation block below is a specific instance of this universal constraint. If a task's `Green` section says to implement a function that runs git commands, that function **must** accept `repo_path`.

## Performance Budgets (per AC-ADHOC-008 perf constraints)

- `extract_file_structure()`: ≤ 200ms per file (initial parse); ≤ 20ms incremental
- `extract_changed_symbols()`: ≤ 100ms per diff
- `_check_return_type_mismatch()` (upgraded): ≤ 300ms per file (initial); ≤ 50ms incremental
- Structured diff summary in JUDGE prompt: ≤ 500 tokens

Tests may include timing assertions using `time.perf_counter()` with generous bounds (1.5x budget) to avoid CI flakiness, but must verify budget compliance.

## Defensive Exclusions (per AC spec)

The following are EXPLICITLY excluded from this issue's scope and MUST NOT be touched:
- RED phase — no tree-sitter integration
- GREEN phase — no tree-sitter integration
- YELLOW phase — no tree-sitter integration
- TASKS phase — no tree-sitter integration
- MACRO layer (explore/research/prd) — no tree-sitter integration (shard and adhoc are included)
- TamperGuard — no tree-sitter integration
- JUDGE agent decision logic — only add structured context; agent still makes the call
- Type checking integration (mypy/pyre) — structural analysis only, no type system
- Grammar compilation — use pre-built Python grammar from `tree-sitter-languages` package
