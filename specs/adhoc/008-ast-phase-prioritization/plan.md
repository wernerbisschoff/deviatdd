## Plan Summary
- **Issue**: ISS-ADH-008 — AST/Structural Analysis Integration — JUDGE + PLAN + REFACTOR (Pareto High-ROI)
- **Implementation Strategy**: Create a new `src/deviate/core/treesitter.py` module with tree-sitter parser factory and structure extraction functions, then wire it into three phases: JUDGE (structured diff summary before agent prompt), PLAN (pre-scan target workstation files, inject file structure appendix into prompt contract), and REFACTOR (replace stdlib `ast` in `_check_return_type_mismatch` with incremental tree-sitter + extended dead-code/duplication/complexity checks). Update prompt templates for JUDGE and PLAN to consume the new structured sections. Add `tree-sitter>=0.24` dependency.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 4-6 hours

## Workstation Mapping
- **`src/deviate/core/treesitter.py`**: New module — tree-sitter parser factory, query execution, diff structure extraction, and file structure extraction.
  - **Current State**: File does not exist. No tree-sitter usage anywhere in the codebase — only stdlib `ast` in `micro.py:2507`.
  - **Changes Required**: Create module with: `_load_python_grammar()` factory (load tree-sitter Python grammar via `tree_sitter_languages.get_language("python")`), `get_parser()` (return configured `tree_sitter.Parser`), `extract_changed_symbols(diff_text, repo_root)` that parses `git diff --unified=0` output and returns structured list of changed FunctionDef/ClassDef nodes with old/new signatures, `extract_file_structure(filepath)` that returns function/class signatures and import blocks from a target file, `incremental_parse(filepath, old_tree)` for re-parsing only changed ranges via `parser.parse(source_bytes, old_tree)` and `old_tree.changed_ranges(new_tree)`.
  - **Integration Surface**: Called by `_run_judge_phase()` (micro.py), `_meso_run()` (meso.py), and `_check_return_type_mismatch()` (micro.py). No external dependencies beyond `tree-sitter` and `tree-sitter-languages` packages.

- **`src/deviate/cli/micro.py`**: JUDGE phase integration (lines 1101-1159) and REFACTOR phase integration (lines 2507-2539).
  - **Current State**: `_run_judge_phase()` runs `git diff RED..HEAD` (line 1117-1123), appends raw diff to prompt (line 1126). `_check_return_type_mismatch()` uses stdlib `ast.parse()` to walk FunctionDef nodes and check return types against 7 builtin types (line 2507-2539).
  - **Changes Required**: In `_run_judge_phase()` after line 1123, call `extract_changed_symbols(diff, root)` from treesitter module, format output as `## Structured Diff Summary` markdown section, insert between the auto prompt and `\n\n<diff>\n{diff}\n</diff>\n`. Replace `_check_return_type_mismatch()` body: use `incremental_parse()` + `get_parser()` from treesitter module; extend checks to include dead code detection (functions with no call sites in the same file), duplicated code blocks (similar AST subtrees >= 5 lines via tree-sitter query comparison), and cyclomatic complexity warnings (>= 10 per function via counting branch nodes). Maintain the existing builtin return-type check behavior.
  - **Integration Surface**: `_run_judge_phase()` imports `extract_changed_symbols` from `deviate.core.treesitter`. `_check_return_type_mismatch()` imports `get_parser`, `incremental_parse` from `deviate.core.treesitter`. Both connect to the `_build_auto_prompt()` prompt assembly flow.

- **`src/deviate/cli/meso.py`**: PLAN phase — pre-scan workstation files before agent invocation.
  - **Current State**: `_meso_run()` (line 1161) builds contract, calls `_invoke_agent_phase("plan", contract)` (line 1276). `_invoke_agent_phase()` calls `_build_slim_prompt()` which uses `assemble_prompt()` with `${PLACEHOLDER}` substitution against the contract dict.
  - **Changes Required**: Before `_invoke_agent_phase("plan", contract)`, parse the issue file's `## System Topology Mapping` section to extract `Primary Architectural Workstations` file paths. For each file that exists, call `extract_file_structure(filepath)` from treesitter module. Format output as `## Target File Structure` markdown. Add `file_structure_appendix` key to the contract dict so it's available as `${file_structure_appendix}` placeholder in the plan prompt template. Handle missing files per edge cases (log warning, skip).
  - **Integration Surface**: Connects to `_build_slim_prompt()` → `assemble_prompt()` → `auto/plan.md` template. New import of `extract_file_structure` from `deviate.core.treesitter`.

- **`src/deviate/prompts/auto/judge.md`**: Update prompt template to consume structured diff format.
  - **Current State**: Template defines role, evaluation criteria, execution sequence. No structured diff section. Template is composed via `load_template()` (assembly.py:44) and receives `${spec_content}`, `${task_content}`, etc.
  - **Changes Required**: Add placeholder `${structured_diff_summary}` in the `<execution_sequence>` section between `STEP_1: INGEST_CONTEXT` and `STEP_2: ANALYZE_DIFF`. Add instruction to STEP_1: "4. Parse the `## Structured Diff Summary` section (pre-extracted by the orchestrator) for changed symbols — this is a pre-computed tree-sitter extraction." Update evaluation dimensions to reference structured diff when available.
  - **Integration Surface**: Receives `${structured_diff_summary}` injected by `_run_judge_phase()` in micro.py as part of the prompt assembly context dict.

- **`src/deviate/prompts/auto/plan.md`**: Update prompt template to consume file structure appendix.
  - **Current State**: Template defines role, execution sequence starting from contract_loaded → context_loading → codebase_scan. Uses `{spec_path}`, `{plan_path}`, `{worktree_full}` placeholders.
  - **Changes Required**: Add `${file_structure_appendix}` placeholder in the `<execution_sequence>` section after the `context_loading` step. Add instruction: "Before scanning files with git tools, read the `## Target File Structure` appendix (pre-extracted tree-sitter analysis of workstation files). This provides function/class signatures without requiring you to read full file contents — use it to identify insertion points."
  - **Integration Surface**: Receives `${file_structure_appendix}` from the contract dict built in `_meso_run()` (meso.py:1261-1270) with the new `file_structure_appendix` key.

- **`pyproject.toml`**: Add tree-sitter dependency.
  - **Current State**: Dependencies include `typer>=0.12`, `rich>=13.0`, `pydantic>=2.0`, `pyyaml>=6.0.3` (line 6-11).
  - **Changes Required**: Add `"tree-sitter>=0.24"` to the `dependencies` list. Optionally add `"tree-sitter-languages>=1.10"` for pre-built Python grammar (avoids manual grammar compilation per defensive exclusions).
  - **Integration Surface**: Declares the dependency that `src/deviate/core/treesitter.py` imports at module level.

## Implementation Strategy
- **Phase 1**: Create `src/deviate/core/treesitter.py` module with core tree-sitter API
  - **Files**: `src/deviate/core/treesitter.py`, `pyproject.toml`, `tests/core/test_treesitter.py`
  - **Approach**: Add tree-sitter dependency to pyproject.toml. Create treesitter.py with: `_load_python_grammar()` using `tree_sitter_languages.get_language("python")`, `get_parser()` returning configured Parser, `extract_changed_symbols(diff_text, repo_root)` parsing unified diff headers and running tree-sitter queries for FunctionDef/ClassDef nodes in changed files, `extract_file_structure(filepath)` running a query for function_definition/class_definition/import_statement nodes and returning signatures, `incremental_parse(filepath, old_tree)` wrapping `parser.parse(bytes, old_tree)`. Write unit tests for all four functions per verification targets.
  - **Verification**: `mise run test tests/core/test_treesitter.py -v` — all four unit tests pass.

- **Phase 2**: Integrate tree-sitter into JUDGE phase
  - **Files**: `src/deviate/cli/micro.py`, `src/deviate/prompts/auto/judge.md`, `tests/test_micro/test_judge.py`
  - **Approach**: In `_run_judge_phase()`, after capturing diff on line 1123, import and call `extract_changed_symbols(diff, root)`. Format output as a markdown section with bullet list of changed symbols. Add `structured_diff_summary` key to the prompt assembly context (or prepend to the diff block). Update `judge.md` template to reference `${structured_diff_summary}` in STEP_1. Update integration test to assert the structured section appears in the judge prompt.
  - **Verification**: `mise run test tests/test_micro/test_judge.py -v` — integration test passes.

- **Phase 3**: Integrate tree-sitter into PLAN phase
  - **Files**: `src/deviate/cli/meso.py`, `src/deviate/prompts/auto/plan.md`, `tests/test_meso/test_plan.py`
  - **Approach**: In `_meso_run()`, before the `_invoke_agent_phase("plan", contract)` call, read the issue file at `spec_path`, parse the `## System Topology Mapping` section to extract `Primary Architectural Workstations` bullet list. For each path that exists relative to worktree root, call `extract_file_structure()`. Format as `## Target File Structure` markdown with per-file sections. Add `file_structure_appendix` to contract dict. Add `${file_structure_appendix}` placeholder to `plan.md` template.
  - **Verification**: `mise run test tests/test_meso/test_plan.py -v` — integration test passes.

- **Phase 4**: Replace stdlib `ast` in REFACTOR with tree-sitter + extended checks
  - **Files**: `src/deviate/cli/micro.py`, `tests/test_micro/test_refactor.py`
  - **Approach**: Replace `_check_return_type_mismatch()` body (lines 2507-2539). Use `get_parser()` and `incremental_parse()` from treesitter module. Implement: (1) existing builtin return-type checks via tree-sitter queries instead of `ast.walk()`, (2) dead code detection — identify functions defined in file but never called (scan `call` expression nodes), (3) duplicated code detection — compare function body subtrees for similarity >= 5 lines, (4) cyclomatic complexity — count `if_statement`/`for_statement`/`while_statement`/`except_clause`/`match_case` nodes per function body, warn if >= 10. Update test to verify new checks.
  - **Verification**: `mise run test tests/test_micro/test_refactor.py -v` — integration test passes, including dead-code and complexity checks.

- **Phase 5**: Full regression and performance validation
  - **Files**: All of the above
  - **Approach**: Run full test suite, verify no regressions in RED/GREEN/YELLOW/TASKS/MACRO phases per AC-ADH-008-04. Measure performance of `extract_file_structure()` (target <=200ms), `extract_changed_symbols()` (target <=100ms), upgraded `_check_return_type_mismatch()` (target <=300ms).
  - **Verification**: `mise run test` — full suite passes. Manual timing via pytest `--durations` or dedicated perf tests.

## Data Flow Analysis
- **JUDGE Flow**: `_run_judge_phase()` → `git diff RED..HEAD` (raw diff text) → `extract_changed_symbols(diff, root)` → structured dict of changed symbols → formatted as `## Structured Diff Summary` markdown → injected into prompt assembly context (or prepended to `<diff>` block) → judge agent consumes both structured summary and raw diff → emits YAML verdict manifest.
- **PLAN Flow**: `_meso_run()` → parse issue file `## System Topology Mapping` → for each workstation file path → `extract_file_structure(filepath)` → structured dict of signatures per file → formatted as `## Target File Structure` markdown → added as `file_structure_appendix` key in contract dict → `${file_structure_appendix}` substitution in `assemble_prompt()` → plan agent receives pre-extracted file structure without reading full files → produces `plan.md`.
- **REFACTOR Flow**: `refactor_post()` → for each test file → `_check_return_type_mismatch(filepath)` → `get_parser()` + `incremental_parse(filepath, old_tree)` → tree-sitter queries for return types, dead code, duplication, complexity → returns list of issues → if issues found, `git restore .` and halt.
- **Grammar Loading Flow**: `treesitter.py` module import → `_load_python_grammar()` → `tree_sitter_languages.get_language("python")` → `tree_sitter.Language` object → cached in module-level variable → used by `get_parser()` for all subsequent operations.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `tree-sitter-languages` package not available or incompatible with Python 3.13 | High | Medium | Fall back to `tree-sitter` + manual grammar from `tree-sitter-python` PyPI package. Pre-verify with `uv run python -c "import tree_sitter_languages"` during setup. |
| Syntax errors in modified files break tree-sitter parse | Medium | Medium | Wrap parse in try/except; on `tree_sitter` parse failure, return empty structure and fall back to raw diff text — graceful degradation per edge case spec. |
| Incremental parse produces incorrect changed ranges on large files (>5000 lines) | Low | Low | Tree-sitter's `changed_ranges()` is well-tested in editor integrations (Neovim, Helix). Test with a large synthetic file during development. |
| Performance budget exceeded for `extract_file_structure()` (<=200ms) | Medium | Low | Initial parse is one-time cost — amortize across session. Test with largest files in codebase (micro.py ~2883 lines). If over budget, limit to top-level declarations only. |
| PLAN phase fails to find issue file's `## System Topology Mapping` section | Low | Low | Use regex with case-insensitive heading match. If section missing or unparseable, log warning and proceed without file structure appendix — same as current behavior. |
| Dead code detection marks fixtures or entry points as unused | Medium | Medium | Initial dead code check scans only within-file call sites. External references (test files, CLI entry points) are excluded from detection scope. |
| Duplicated code detection false positives on trivial patterns (< 5 lines) | Low | Low | Threshold of >= 5 lines per AC spec filters trivially similar patterns. Use tree-sitter subtree hash comparison, not text diff. |
| Merge conflicts with concurrent work on `_meso_run()` (ISS-001-008 recently completed) | Medium | Low | ISS-001-008 completed and merged. No other in-flight work touches `_meso_run()` or `_run_judge_phase()`. Plan integration is additive — new contract key, new function call before existing code. |

## Integration Points
- **`_build_auto_prompt()` → `assemble_prompt()`**: JUDGE phase uses `${PLACEHOLDER}` substitution for `spec_content`, `task_content`, etc. The structured diff summary can be added as a new placeholder key (`${structured_diff_summary}`) or prepended directly to the prompt string after `_build_auto_prompt()` returns (the current pattern at micro.py:1126 appends raw diff as `\n\n<diff>\n{diff}\n</diff>\n`).
- **`_build_slim_prompt()` → `assemble_prompt()`**: PLAN phase uses contract dict for `${PLACEHOLDER}` substitution. Adding `file_structure_appendix` key to the contract enables template access via `${file_structure_appendix}`. No changes needed to `_build_slim_prompt()` or `assemble_prompt()`.
- **`_check_return_type_mismatch()` → `refactor_post()`**: The return value is `list[str]` of issues. The calling code in `refactor_post()` (line ~2630) already handles a non-empty list as a failure condition and calls `_execute_rollback()`. No interface contract change — just an extended implementation.
- **`pyproject.toml` dependency list**: Adding `tree-sitter>=0.24` (and optionally `tree-sitter-languages>=1.10`) follows the existing pattern of explicitly declared runtime dependencies. No build system changes required.
- **`test/conftest.py` `tmp_git_repo` fixture**: All new tests must use `tmp_git_repo` for git isolation and `_git_env()` from `tests.conftest`. New tree-sitter tests can use `tmp_path` for file fixtures since they don't need git context.

## Constitutional Alignment
- **Architecture**: This issue operates within all three layers — MICRO (JUDGE + REFACTOR phase modifications in `micro.py`), MESO (PLAN phase modification in `meso.py`), and CORE (new `treesitter.py` module). No new phases, no bypass of existing phase gates. Follows the three-layer architecture's strict phase-gate discipline per `[1_ARCHITECTURAL_PRINCIPLES]`.
- **Testing**: All new code is test-driven. Unit tests in `tests/core/test_treesitter.py` per the `[MULTI_TIERED_VERIFICATION_TARGETS]` specification (4 new unit tests). Integration tests in existing test modules (`tests/test_micro/test_judge.py`, `tests/test_micro/test_refactor.py`, `tests/test_meso/test_plan.py`). Test framework: `pytest` per `[3_1_FRAMEWORK]`. Test isolation: git operations use `tmp_git_repo` fixture and `_git_env()` per AGENTS.md git isolation contract. `_run_pytest()` must be mocked in integration tests per AGENTS.md performance constraints.
- **Git Isolation**: New production code in `micro.py` and `meso.py` does not create branches or switch branch state — all work happens on the pre-configured worktree branch. The `treesitter.py` module is a pure library with no git operations. Tests use `tmp_git_repo` fixture.
