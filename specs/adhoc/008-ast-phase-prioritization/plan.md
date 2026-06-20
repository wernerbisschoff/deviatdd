## Plan Summary
- **Issue**: ISS-ADH-008 — AST/Structural Analysis Integration — JUDGE + PLAN + REFACTOR + SHARD + ADHOC (Pareto High-ROI)
- **Implementation Strategy**: Create a new `src/deviate/core/treesitter.py` module with tree-sitter parser factory and structure extraction functions, then wire it into five phases: JUDGE (structured diff summary before agent prompt), PLAN (pre-scan target workstation files, inject file structure appendix into prompt contract), REFACTOR (replace stdlib `ast` in `_check_return_type_mismatch` with incremental tree-sitter + extended dead-code/duplication/complexity checks), SHARD (pre-scan source files, inject codebase structure appendix into shard contract for accurate topology mapping), and ADHOC (extend `adhoc pre` to scan source files and write `specs/adhoc/codebase_structure.md` artifact for skill prompt consumption). Update prompt templates for JUDGE, PLAN, SHARD, and ADHOC to consume the new structured sections. Add `tree-sitter>=0.24` dependency.
- **Estimated Complexity**: Medium-High
- **Estimated Effort**: 6-8 hours

## Workstation Mapping
- **`src/deviate/core/treesitter.py`**: New module — tree-sitter parser factory, query execution, diff structure extraction, and file structure extraction.
  - **Current State**: File does not exist. No tree-sitter usage anywhere in the codebase — only stdlib `ast` in `micro.py:2507`.
  - **Changes Required**: Create module with: `_load_python_grammar()` factory (load tree-sitter Python grammar via `tree_sitter_languages.get_language("python")`), `get_parser()` (return configured `tree_sitter.Parser`), `extract_changed_symbols(diff_text, repo_root)` that parses `git diff --unified=0` output and returns structured list of changed FunctionDef/ClassDef nodes with old/new signatures, `extract_file_structure(filepath)` that returns function/class signatures and import blocks from a target file, `incremental_parse(filepath, old_tree)` for re-parsing only changed ranges via `parser.parse(source_bytes, old_tree)` and `old_tree.changed_ranges(new_tree)`.
  - **Integration Surface**: Called by `_run_judge_phase()` (micro.py), `_meso_run()` (meso.py), `_check_return_type_mismatch()` (micro.py), `shard_pre()` (macro.py), and `adhoc pre()` (adhoc.py). No external dependencies beyond `tree-sitter` and `tree-sitter-languages` packages.

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

- **`src/deviate/cli/macro.py`**: SHARD phase — pre-scan source files before agent invocation.
  - **Current State**: `shard_pre()` (line 544-588) builds contract dict at line ~576 via `_emit_contract()`. Contract includes `epic_slug`, `prd_path`, `issues_dir`, `next_issue_id`, etc. No codebase structure context.
  - **Changes Required**: After building the contract dict, scan the PRD's referenced files and key source directories for Python files. For each file that exists, call `extract_file_structure(filepath)` from treesitter module. Format output as `## Codebase Structure` markdown. Add `codebase_structure_appendix` key to the contract dict so it's available as `${codebase_structure_appendix}` in the shard prompt template.
  - **Integration Surface**: Connects to `_emit_contract()` → `_invoke_agent_phase()` → `_build_slim_prompt()` → `assemble_prompt()` → `auto/shard.md` template. New import of `extract_file_structure` from `deviate.core.treesitter`.

- **`src/deviate/cli/adhoc.py`**: ADHOC flow — extend `adhoc pre` to scan source files and write artifact.
  - **Current State**: `adhoc pre()` (line 45-84) classifies task description via `ComplexityGate`, creates `AdhocRecord`, writes to `specs/adhoc.jsonl` ledger, emits contract JSON to stdout. No codebase structure context.
  - **Changes Required**: After the complexity gate check, scan `src/` (or configurable `--scan-dir`) for Python files. For each file, call `extract_file_structure(filepath)` from treesitter module. Format output as `## Codebase Structure` markdown. Write to `specs/adhoc/codebase_structure.md` artifact. Emit artifact path in contract JSON as `codebase_structure_path` key.
  - **Integration Surface**: The skill prompt (`deviate-adhoc/SKILL.md`) is loaded separately by the LLM agent. Integration is via artifact file: `adhoc pre` writes `specs/adhoc/codebase_structure.md`, and the skill prompt step 3 instructs the agent to read it. No placeholder substitution — the agent reads the file directly.

- **`src/deviate/prompts/auto/shard.md`**: Update prompt template to consume codebase structure appendix.
  - **Current State**: Template defines role, execution sequence starting from contract_loaded → constitutional_pre_flight → prd_reading → vertical_slicing. Uses `${epic_slug}`, `${prd_path}`, `${issues_dir}`, etc. placeholders.
  - **Changes Required**: Add `${codebase_structure_appendix}` placeholder in the `<execution_sequence>` section between `prd_reading` and `vertical_slicing` steps. Add instruction: "Before scanning files with git tools, read the `## Codebase Structure` appendix (pre-extracted tree-sitter analysis of source files). This provides function/class signatures without requiring you to read full file contents — use it to identify insertion points and accurate `source_file` mappings."
  - **Integration Surface**: Receives `${codebase_structure_appendix}` from the contract dict built in `shard_pre()` (macro.py:576) with the new `codebase_structure_appendix` key.

- **`src/deviate/prompts/skills/deviate-adhoc/SKILL.md`**: Update skill prompt to consume codebase structure artifact.
  - **Current State**: Skill prompt step 3 ("Lightweight Discovery Pass") instructs the agent to use grep/glob to find files and modules. No pre-extracted structure context.
  - **Changes Required**: Update step 3 to add: "If `specs/adhoc/codebase_structure.md` exists (created by `adhoc pre`), read it first for pre-extracted file signatures — use it to identify target files and existing patterns before falling back to grep/glob. This avoids reading full file contents for structure discovery."
  - **Integration Surface**: The agent reads the artifact file directly. No placeholder substitution. The artifact path is emitted in the contract JSON as `codebase_structure_path` key.

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

- **Phase 5**: Integrate tree-sitter into SHARD phase
  - **Files**: `src/deviate/cli/macro.py`, `src/deviate/prompts/auto/shard.md`, `tests/test_macro/test_shard.py`
  - **Approach**: In `shard_pre()`, after building the contract dict (line ~576), scan the PRD's referenced files and key source directories for Python files. For each file that exists, call `extract_file_structure(filepath)` from the treesitter module. Format as `## Codebase Structure` markdown. Add `codebase_structure_appendix` key to the contract dict so it's available as `${codebase_structure_appendix}` in the shard prompt template. Update `shard.md` to consume the appendix in the `vertical_slicing` step — instruct the agent to use pre-extracted signatures for `source_file` mapping and topology accuracy instead of raw file scanning.
  - **Verification**: `mise run test tests/test_macro/test_shard.py -v` — integration test passes.

- **Phase 6**: Integrate tree-sitter into ADHOC flow
  - **Files**: `src/deviate/cli/adhoc.py`, `src/deviate/prompts/skills/deviate-adhoc/SKILL.md`, `tests/test_cli/test_adhoc.py`
  - **Approach**: Extend `adhoc pre` command to scan `src/` (or configurable `--scan-dir`) for Python files, call `extract_file_structure()` on each, and write the result to `specs/adhoc/codebase_structure.md`. Emit the artifact path in the contract JSON. Update the adhoc SKILL.md step 3 ("Lightweight Discovery Pass") to instruct the agent: "If `specs/adhoc/codebase_structure.md` exists, read it first for pre-extracted file signatures — use it to identify target files and existing patterns before falling back to grep/glob." This avoids the agent reading full file contents for structure discovery.
  - **Verification**: `mise run test tests/test_cli/test_adhoc.py -v` — integration test passes; `specs/adhoc/codebase_structure.md` is created by `adhoc pre`.

- **Phase 7**: Full regression and performance validation
  - **Files**: All of the above
  - **Approach**: Run full test suite, verify no regressions in RED/GREEN/YELLOW/TASKS/MACRO phases per AC-ADH-008-04. Measure performance of `extract_file_structure()` (target <=200ms), `extract_changed_symbols()` (target <=100ms), upgraded `_check_return_type_mismatch()` (target <=300ms).
  - **Verification**: `mise run test` — full suite passes. Manual timing via pytest `--durations` or dedicated perf tests.

## Data Flow Analysis
- **JUDGE Flow**: `_run_judge_phase()` → `git diff RED..HEAD` (raw diff text) → `extract_changed_symbols(diff, root)` → structured dict of changed symbols → formatted as `## Structured Diff Summary` markdown → injected into prompt assembly context (or prepended to `<diff>` block) → judge agent consumes both structured summary and raw diff → emits YAML verdict manifest.
- **PLAN Flow**: `_meso_run()` → parse issue file `## System Topology Mapping` → for each workstation file path → `extract_file_structure(filepath)` → structured dict of signatures per file → formatted as `## Target File Structure` markdown → added as `file_structure_appendix` key in contract dict → `${file_structure_appendix}` substitution in `assemble_prompt()` → plan agent receives pre-extracted file structure without reading full files → produces `plan.md`.
- **REFACTOR Flow**: `refactor_post()` → for each test file → `_check_return_type_mismatch(filepath)` → `get_parser()` + `incremental_parse(filepath, old_tree)` → tree-sitter queries for return types, dead code, duplication, complexity → returns list of issues → if issues found, `git restore .` and halt.
- **SHARD Flow**: `shard_pre()` → read PRD → scan source directories for Python files → `extract_file_structure(filepath)` per file → formatted as `## Codebase Structure` markdown → added as `codebase_structure_appendix` key in contract dict → `${codebase_structure_appendix}` substitution in `shard.md` template → shard agent uses pre-extracted signatures for accurate `source_file` mapping and topology identification → emits issue files with precise workstation paths.
- **ADHOC Flow**: `adhoc pre` → scan `src/` (or `--scan-dir`) for Python files → `extract_file_structure(filepath)` per file → formatted as `## Codebase Structure` markdown → written to `specs/adhoc/codebase_structure.md` → artifact path emitted in contract JSON → adhoc skill prompt step 3 instructs agent to read artifact first for pre-extracted signatures before falling back to grep/glob → agent produces issue with accurate topology mapping.
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
| SHARD phase scan cost exceeds perf budget for large codebases | Medium | Medium | Scanning entire `src/` directory may exceed 200ms budget for large codebases. Mitigation: limit to top-level declarations only, or cache results across invocations. Consider `--scan-dir` option to scope scan. |
| ADHOC artifact staleness between `adhoc pre` and skill execution | Low | Medium | `specs/adhoc/codebase_structure.md` may become stale if source files change between `adhoc pre` and skill execution. Mitigation: document this limitation in the skill prompt; agent should verify critical files before relying on artifact. |

## Integration Points
- **`_build_auto_prompt()` → `assemble_prompt()`**: JUDGE phase uses `${PLACEHOLDER}` substitution for `spec_content`, `task_content`, etc. The structured diff summary can be added as a new placeholder key (`${structured_diff_summary}`) or prepended directly to the prompt string after `_build_auto_prompt()` returns (the current pattern at micro.py:1126 appends raw diff as `\n\n<diff>\n{diff}\n</diff>\n`).
- **`_build_slim_prompt()` → `assemble_prompt()`**: PLAN phase uses contract dict for `${PLACEHOLDER}` substitution. Adding `file_structure_appendix` key to the contract enables template access via `${file_structure_appendix}`. No changes needed to `_build_slim_prompt()` or `assemble_prompt()`.
- **`_emit_contract()` → `shard.md`**: SHARD phase uses `_emit_contract("SHARD", ...)` in `shard_pre()` (macro.py:576) to build the contract dict. Adding `codebase_structure_appendix` key enables `${codebase_structure_appendix}` substitution in `shard.md` template via the existing `_invoke_agent_phase()` → `_build_slim_prompt()` → `assemble_prompt()` pipeline.
- **`adhoc pre` → skill prompt**: ADHOC flow uses `adhoc pre` (adhoc.py:45-84) to emit a contract JSON to stdout. The skill prompt (`deviate-adhoc/SKILL.md`) is loaded separately by the LLM agent. Integration is via artifact file: `adhoc pre` writes `specs/adhoc/codebase_structure.md`, and the skill prompt step 3 instructs the agent to read it. No placeholder substitution — the agent reads the file directly.
- **`_check_return_type_mismatch()` → `refactor_post()`**: The return value is `list[str]` of issues. The calling code in `refactor_post()` (line ~2630) already handles a non-empty list as a failure condition and calls `_execute_rollback()`. No interface contract change — just an extended implementation.
- **`pyproject.toml` dependency list**: Adding `tree-sitter>=0.24` (and optionally `tree-sitter-languages>=1.10`) follows the existing pattern of explicitly declared runtime dependencies. No build system changes required.
- **`test/conftest.py` `tmp_git_repo` fixture**: All new tests must use `tmp_git_repo` for git isolation and `_git_env()` from `tests.conftest`. New tree-sitter tests can use `tmp_path` for file fixtures since they don't need git context.

## Constitutional Alignment
- **Architecture**: This issue operates within all three layers — MICRO (JUDGE + REFACTOR phase modifications in `micro.py`), MESO (PLAN phase modification in `meso.py`), MACRO (SHARD phase modification in `macro.py`, ADHOC flow modification in `adhoc.py`), and CORE (new `treesitter.py` module). No new phases, no bypass of existing phase gates. Follows the three-layer architecture's strict phase-gate discipline per `[1_ARCHITECTURAL_PRINCIPLES]`.
- **Testing**: All new code is test-driven. Unit tests in `tests/core/test_treesitter.py` per the `[MULTI_TIERED_VERIFICATION_TARGETS]` specification (4 new unit tests). Integration tests in existing test modules (`tests/test_micro/test_judge.py`, `tests/test_micro/test_refactor.py`, `tests/test_meso/test_plan.py`, `tests/test_macro/test_shard.py`, `tests/test_cli/test_adhoc.py`). Test framework: `pytest` per `[3_1_FRAMEWORK]`. Test isolation: git operations use `tmp_git_repo` fixture and `_git_env()` per AGENTS.md git isolation contract. `_run_pytest()` must be mocked in integration tests per AGENTS.md performance constraints.
- **Git Isolation**: New production code in `micro.py`, `meso.py`, `macro.py`, and `adhoc.py` does not create branches or switch branch state — all work happens on the pre-configured worktree branch. The `treesitter.py` module is a pure library with no git operations. Tests use `tmp_git_repo` fixture.
