# Implementation Tasks: `ISS-ADH-008`

## Phase 1: Core Tree-Sitter Module — Parser Factory & Query Infrastructure
**Goal**: Language-agnostic parser factory with 38-extension dispatch map, parser caching, query file compilation for all 21 grammars. This is the foundation every other phase depends on.

### Tasks

- TSK-008-01: Create parser factory, EXTENSION_MAP, and all 21 query files
  - **Type**: Infra_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/core/test_treesitter.py -v -k "dispatch or parser or query_compile or unknown" `
  - **Estimated Time**: 90 minutes
  - **Files**:
    - `src/deviate/core/treesitter.py`
    - `src/deviate/core/treesitter/queries/python.scm`
    - `src/deviate/core/treesitter/queries/javascript.scm`
    - `src/deviate/core/treesitter/queries/typescript.scm`
    - `src/deviate/core/treesitter/queries/tsx.scm`
    - `src/deviate/core/treesitter/queries/rust.scm`
    - `src/deviate/core/treesitter/queries/go.scm`
    - `src/deviate/core/treesitter/queries/cpp.scm`
    - `src/deviate/core/treesitter/queries/elixir.scm`
    - `src/deviate/core/treesitter/queries/c_sharp.scm`
    - `src/deviate/core/treesitter/queries/markdown.scm`
    - `src/deviate/core/treesitter/queries/bash.scm`
    - `src/deviate/core/treesitter/queries/json.scm`
    - `src/deviate/core/treesitter/queries/toml.scm`
    - `src/deviate/core/treesitter/queries/yaml.scm`
    - `src/deviate/core/treesitter/queries/html.scm`
    - `src/deviate/core/treesitter/queries/css.scm`
    - `src/deviate/core/treesitter/queries/sql.scm`
    - `src/deviate/core/treesitter/queries/dockerfile.scm`
    - `src/deviate/core/treesitter/queries/hcl.scm`
    - `src/deviate/core/treesitter/queries/kotlin.scm`
    - `src/deviate/core/treesitter/queries/swift.scm`
    - `tests/core/test_treesitter.py`
  - **Rationale**: US-008-04 (language auto-detection from file extension), AC-ADHOC-008-04, AC-ADHOC-008-05, AC-ADHOC-008-07, AC-ADHOC-008-08. The EXTENSION_MAP is the single source of truth for all language dispatch. Parser caching keeps per-file overhead ≤10ms. Query files are the static data all analysis functions consume — they must be written first so analysis function TDD has patterns to test against. Graceful degradation for unknown extensions (.rb) and missing `tree-sitter-languages` is tested via ImportError fallback.
  - **Details**:
    - **Red**: Write `test_language_dispatch_*` tests (19 tests, one per grammar ID) asserting `get_parser(filepath)` returns correct grammar for each extension. Write `test_unknown_extension_logs_warning` for `.rb`. Write `test_parser_caching` verifying same grammar returns cached parser. Write `test_missing_tree_sitter_languages` (mock ImportError) asserting all public functions return empty structures. Write `test_query_file_coverage` asserting all 21 `.scm` files compile without error.
    - **Green**: Implement `EXTENSION_MAP` frozen dict with 38 extensions → 21 grammar IDs. Implement `get_parser(filepath: str) -> Parser` with per-grammar parser caching via dict, dispatching through `tree_sitter_languages.get_parser(grammar_id)`. Implement `get_language_id(filepath: str) -> str | None` for public lookup. Implement `_load_query(language, query_name)` reading `.scm` from `queries/` directory via `importlib.resources`, compiling with `tree_sitter.Query(language, query_text)`. Import-time try/except for `tree_sitter_languages` — on ImportError all public functions return empty structures.
    - **Refactor**: Extract query file path resolution into a single helper. Deduplicate the grammar-ID-to-language-name mapping (used by both EXTENSION_MAP values and query file naming).
    - **Edge Cases**: `.Dockerfile` (with dot prefix) → strip leading dot before lookup. `.rb` → `get_language_id` returns None, all analysis functions log warning and return empty structure. `tree-sitter-languages` missing → graceful degradation, no crash. Query file compilation failure → log warning, skip. Empty source file → parser returns empty tree.
    - **Acceptance**: All 21 query files compile with `tree_sitter.Query(language, query_text)` without error. All 38 extension entries dispatch to correct grammar. `get_parser()` returns cached parser on second call. Unknown extension returns None from `get_language_id` and logs warning.

- TSK-008-02: Implement all 6 language-agnostic analysis functions
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/core/test_treesitter.py -v -k "symbols or structure or incremental or dead_code or duplicate or complexity" `
  - **Estimated Time**: 90 minutes
  - **Files**:
    - `src/deviate/core/treesitter.py`
    - `tests/core/test_treesitter.py`
  - **Rationale**: US-008-01 (structured diff for JUDGE), US-008-02 (file structure for PLAN), US-008-03 (dead-code/duplication/complexity for REFACTOR), US-008-05 (merge-base structured diff for REVIEW). AC-ADHOC-008-01 through AC-ADHOC-008-03. All 6 analysis functions dispatch through the same pipeline (get_parser → Parser.parse → Query → matched nodes) and never reference a specific language by name. This task covers AC-ADHOC-008-04 (auto-detection) and AC-ADHOC-008-05 (graceful degradation) as all functions inherit language dispatch from TSK-008-01.
  - **Details**:
    - **Red**: Write `test_extract_changed_symbols_single_function` (Python diff with one changed function), `test_extract_changed_symbols_mixed_languages` (diff spanning `.py` + `.rs`), `test_extract_changed_symbols_empty_diff`. Write `test_extract_file_structure_python` (classes + functions + imports), `test_extract_file_structure_typescript` (interface + class), `test_extract_file_structure_rust` (struct + impl + trait). Write `test_incremental_parse_changed_ranges` (two parses, verify only changed ranges re-parsed). Write `test_dead_code_detection` (unused function flagged), `test_duplicate_block_detection` (similar AST subtrees ≥5 lines), `test_cyclomatic_complexity` (function with if/for/while ≥10). Write `test_analysis_graceful_degradation` (unknown extension returns empty).
    - **Green**: Implement `extract_changed_symbols(diff_text, filepath) -> list[SymbolChange]` — parse git diff hunks per-file, detect language via extension, extract changed function/class definitions with old/new signatures via query captures. Implement `extract_file_structure(filepath) -> FileStructure` — full parse + query execution for @function/@class/@import/@interface captures. Implement `incremental_parse(filepath, old_tree) -> Tree` — parser.parse(src, old_tree). Implement `extract_dead_code(filepath) -> list[str]` — collect @call captures, flag @function/@class not in call set. Implement `detect_duplicate_blocks(filepath, min_lines=5) -> list[DuplicateBlock]` — AST subtree hash comparison with O(n²) pair check for subtrees ≥ min_lines. Implement `estimate_cyclomatic_complexity(filepath, func_node) -> int` — count decision nodes (if/for/while/match/switch/case).
    - **Refactor**: Extract common parse-and-query pattern into `_run_query(filepath, query_name)` helper. Use `functools.lru_cache` for query compilation caching. Add type annotations for all return types.
    - **Edge Cases**: Empty diff → empty list. Syntax error in file → return empty structure (no crash). File >10000 lines → skip with warning. Mixed-language diff → per-hunk dispatch. Incremental parse with None old_tree → full parse. Dead code: function called in string/comment → false positive acceptable (per-file limitation).
    - **Acceptance**: `extract_changed_symbols` returns correct `SymbolChange` for Python, TS, Rust. `extract_file_structure` extracts functions and imports from Python. `extract_dead_code` flags unused functions. `detect_duplicate_blocks` finds similar subtrees. `estimate_cyclomatic_complexity` counts decision points correctly.

---

## Phase 2: JUDGE + PLAN Prompt Injection
**Goal**: Inject language-agnostic structured data into JUDGE and PLAN agent prompts — token reduction on Pro-tier phases.

### Tasks

- TSK-008-03: Inject structured diff summary into JUDGE prompt and update judge.md template
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_micro/test_judge.py -v -k "structured_diff" `
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `src/deviate/prompts/auto/judge.md`
    - `tests/test_micro/test_judge.py`
  - **Rationale**: US-008-01 (structured diff summary for JUDGE), AC-ADHOC-008-01. JUDGE is the HIGH-ROI phase on V4 Pro — structured diff reduces ~3000 token raw diffs to ~500 token tables. The agent still receives the raw diff for full context but parses the structured summary first for language-aware classification. Depends on TSK-008-02 (`extract_changed_symbols`).
  - **Details**:
    - **Red**: Write `test_judge_prompt_contains_structured_diff` — mock `extract_changed_symbols` to return a known `SymbolChange` list, invoke `_run_judge_phase`, assert the output judge prompt contains `## Structured Diff Summary` with `| Language | Kind | Name | Change |` rows. Write `test_judge_prompt_empty_diff` — empty diff produces no structured section. Write `test_judge_prompt_mixed_language_diff` — diff spanning `.py` + `.rs` produces rows with both languages. Write `test_judge_prompt_graceful_degradation` — `extract_changed_symbols` returns empty list, prompt proceeds without structured section.
    - **Green**: In `_run_judge_phase()` (micro.py lines 1116-1126), after collecting raw diff, detect changed file paths from diff hunks. For each changed file, call `extract_changed_symbols(diff, filepath)`. Build `## Structured Diff Summary` markdown table with `| Language | Kind | Name | Change |` rows. Prepend this table before the raw `<diff>` section in the prompt. In `judge.md`, add `## Structured Diff Summary` consumption instruction in STEP_2: parse the table, classify changes by language and type before raw diff analysis. Update YAML output schema to include optional `diff_summary.structured_changes` field.
    - **Refactor**: Extract table-building logic into `_build_structured_diff_table(symbols: list[SymbolChange]) -> str` helper. Handle edge case where a file appears in diff but `extract_changed_symbols` returns empty (syntactic changes, no symbol changes).
    - **Edge Cases**: Empty diff → no structured section appended. Single file diff → single-language table. Mixed-language diff → per-language rows. Parse failure in one file → skip that file, include others. Diff with binary files → skip binary, include text files.
    - **Acceptance**: Judge prompt for a Python-only diff contains `## Structured Diff Summary` table with correct language/kind/name/change rows. Judge prompt for empty diff omits the section. `judge.md` template updated with structured diff consumption instructions.

- TSK-008-04: Inject file structure appendix into PLAN contract and update plan.md template
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_meso/test_plan_structure_injection.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/meso.py`
    - `src/deviate/prompts/auto/plan.md`
    - `tests/test_meso/test_plan_structure_injection.py`
  - **Rationale**: US-008-02 (file structure appendix for PLAN), AC-ADHOC-008-02. PLAN is the HIGH-ROI phase on V4 Pro — pre-scanning target files reduces 50x token cost by providing structure instead of raw file content. Depends on TSK-008-02 (`extract_file_structure`).
  - **Details**:
    - **Red**: Write `test_plan_pre_injects_file_structure` — create a temp worktree with a Python file containing classes and functions, invoke `_plan_pre`, assert the emitted JSON contract contains a `file_structure` key with per-file `{language, symbols}` entries. Write `test_plan_pre_missing_workstation_file` — file in topology mapping doesn't exist → log warning, skip. Write `test_plan_pre_mixed_languages` — workstation files include `.py`, `.ts`, `.rs` → structure includes all three languages. Write `test_plan_pre_no_topology_section` — issue file missing `## System Topology Mapping` → no `file_structure` key.
    - **Green**: In `_plan_pre()` (meso.py lines 612-639), after resolving `spec_path`, read the issue file and parse `## System Topology Mapping` → `## Primary Architectural Workstations` list to extract file paths. For each file that exists in the repo, call `extract_file_structure(filepath)`. Add `file_structure: {filepath: {language: str, symbols: [...]}}` key to the contract JSON before output. In `plan.md`, add `## Target File Structure` consumption step in `step id="codebase_scan"` — agent uses file-structure appendix to plan insertion points without reading full files. Format specification: `Language | Kind | Name | Signature`.
    - **Refactor**: Extract workstation path parsing into `_parse_workstation_paths(spec_content: str) -> list[str]` helper. Handle both bullet-list (`- \`path\``) and inline code formats.
    - **Edge Cases**: Issue file not found → no `file_structure` key. Topology section missing → skip. Workstation file deleted after issue creation → log warning, skip. Binary file in workstation list → skip. File with syntax errors → return partial structure (what parsed successfully).
    - **Acceptance**: JSON contract from `_plan_pre` includes `file_structure` key with per-file language and symbol signatures. `plan.md` template updated with `## Target File Structure` consumption instructions. Missing files produce warning logs, not crashes.

---

## Phase 3: REFACTOR Integration — Multi-Language Checks
**Goal**: Replace Python-only stdlib `ast` with language-agnostic tree-sitter incremental parse. Add dead code detection, duplicate block detection, and cyclomatic complexity warnings across all 20 supported languages.

### Tasks

- TSK-008-05: Replace `ast` with tree-sitter in `_check_return_type_mismatch` and add extended checks
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_micro/test_refactor.py -v -k "check_return or dead_code or duplicate or complexity" `
  - **Estimated Time**: 75 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/test_micro/test_refactor.py`
  - **Rationale**: US-008-03 (multi-language dead-code/duplication/complexity for REFACTOR), AC-ADHOC-008-03. REFACTOR is MEDIUM-ROI — currently Python-only via `ast.parse`. Upgrading to tree-sitter extends checks to all 20 languages without per-language special casing. Depends on TSK-008-02 (all analysis functions).
  - **Details**:
    - **Red**: Write `test_check_return_type_mismatch_python_uses_treesitter` — verify `_check_return_type_mismatch` no longer imports `ast` and uses tree-sitter parser. Write `test_dead_code_detected_in_python` — Python file with unused function → issue reported. Write `test_dead_code_detected_in_javascript` — JS file with unused function → issue reported. Write `test_dead_code_detected_in_rust` — Rust file with unused function → issue reported. Write `test_duplicate_blocks_detected` — file with copy-pasted blocks → duplicate issues reported. Write `test_complexity_warning` — function with ≥10 decision points → complexity issue reported. Write `test_non_supported_language_graceful` — `.rb` file → empty issues list, no crash. Write `test_syntax_error_no_crash` — file with syntax errors → empty or partial results.
    - **Green**: In `_check_return_type_mismatch()` (micro.py lines 2507-2539), replace `ast.parse(f.read())` with `get_parser(filepath)` + `incremental_parse(filepath, None)`. Replace `ast.walk(tree)` iteration with tree-sitter query execution for `@function` captures. Preserve existing return-type mismatch logic by mapping tree-sitter node types to Python builtin names (e.g., `function_definition returns: (type (identifier) @return_type)` for Python). After return-type check, call `extract_dead_code(filepath)` → report unused definitions. Call `detect_duplicate_blocks(filepath, min_lines=5)` → report duplicate blocks. Call `estimate_cyclomatic_complexity(filepath, func_node)` for each function definition with threshold=10 → report complexity warnings. Skip non-`.py` files for return-type check (language-specific), but run dead-code/duplication/complexity for all supported languages. Unknown extensions → empty results list (no crash).
    - **Refactor**: Extract language-specific return-type check into `_check_python_return_types(filepath, tree) -> list[str]`. Generalize dead-code/duplication/complexity checks into `_run_refactor_checks(filepath) -> list[str]` called for all languages. Remove `_classify_expression_returns` if fully replaced by tree-sitter logic.
    - **Edge Cases**: Empty file → empty issues. File with only comments/whitespace → empty issues. File not found → empty issues (no exception). Large file (>10000 lines) → skip with log warning. Incremental parse with old tree from prior call → re-parse only changed ranges. Syntax error → graceful fallback, return empty.
    - **Acceptance**: `_check_return_type_mismatch` detects dead code in Python, JS, and Rust. Duplicate blocks in any supported language flagged. Cyclomatic complexity ≥10 flagged. Non-`.py` files get dead-code/duplication/complexity checks (not return-type). Unknown languages return empty without crash.

---

## Phase 4: REVIEW Integration + Finalization
**Goal**: Inject merge-base structured diff into REVIEW contract, update review SKILL.md for multi-domain consumption, add tree-sitter dependencies, and configure wheel packaging.

### Tasks

- TSK-008-06: Inject merge-base structured diff into REVIEW contract and update all prompt templates
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_cli/test_review.py -v -k "structured_diff" `
  - **Estimated Time**: 75 minutes
  - **Files**:
    - `src/deviate/cli/review.py`
    - `src/deviate/prompts/skills/deviate-review/SKILL.md`
    - `src/deviate/prompts/auto/judge.md`
    - `src/deviate/prompts/auto/plan.md`
    - `pyproject.toml`
    - `tests/test_cli/test_review.py`
  - **Rationale**: US-008-05 (merge-base structured diff for REVIEW), AC-ADHOC-008-09, AC-ADHOC-008-10. REVIEW is HIGH-ROI — structured merge-base diff catches renames, signature shifts, dead code, and duplicate blocks that raw text diffs hide. Updating SKILL.md aligns with tools-review's six-domain format. pyproject.toml adds `tree-sitter` and `tree-sitter-languages` dependencies required by all prior tasks. Depends on TSK-008-02 (`extract_file_structure`).
  - **Details**:
    - **Red**: Write `test_review_pre_contains_structured_diff` — in a temp git repo with Python, TS, and Rust files changed between merge-base and HEAD, invoke `review pre`, assert contract contains `structured_diff` key with per-file symbol changes annotated as `| Language | Kind | Name | Change |`. Write `test_review_pre_change_types` — verify change types: function added in HEAD returns `added`, function removed returns `removed`, function signature changed returns `modified`, function renamed returns `renamed`. Write `test_review_pre_merge_base_not_found` — no common ancestor → `structured_diff` absent, raw diff present. Write `test_review_pre_binary_files` — binary files in diff → marked as `| n/a | binary | <filename> | skipped |`.
    - **Green**: In `review pre` (review.py lines 97-100), after computing raw diff via `_compute_diff`, extract changed file paths. For each text file, run `git show merge_base:<path>` (via subprocess, capture stdout) and `git show HEAD:<path>` to get both versions. Call `extract_file_structure()` on each version's content (written to temp files or parsed from string). Diff the symbol sets: symbols in HEAD but not merge-base = `added`, in merge-base but not HEAD = `removed`, same name different signature = `modified`, same signature different name (heuristic) = `renamed`. Build `structured_diff: {filepath: [{language, kind, name, change}]}` in contract JSON. Update `deviate-review` SKILL.md: add Step 1.5 to parse `## Merge-Base Structured Diff` table, expand Step 2 scan to six domains (Security, Clean Code, Pragmatism, Idiomacy, Constitution, PRD), change Step 3 output to multi-domain format: Positive Patterns, Critical Issues, Suggestions, Opportunities, Compliance Matrix, Quick Fix Summary. Add `tree-sitter>=0.24` and `tree-sitter-languages>=1.12` to `pyproject.toml` dependencies. Add `"src/deviate/core/treesitter/queries"` to `tool.hatch.build.targets.wheel.force-include`.
    - **Refactor**: Extract merge-base per-file content retrieval into `_get_file_at_commit(commit: str, filepath: str) -> str | None` helper. Extract symbol-set diffing into `_diff_symbols(before: list, after: list) -> list[SymbolChange]` helper. Handle rename detection via Levenshtein distance on function names.
    - **Edge Cases**: Merge-base not reachable → omit `structured_diff` key (contract has raw diff only). File deleted in HEAD → `removed` for all its symbols, parse merge-base version only. File added in HEAD → `added` for all its symbols, parse HEAD version only. Binary file → skipped in structured diff, marked as skipped. File with syntax errors at merge-base → parse HEAD only, all symbols marked `added`. File with syntax errors at HEAD → parse merge-base only, all symbols marked `removed`.
    - **Acceptance**: Review contract contains `structured_diff` key with per-file symbol changes. Change types correctly classify added/removed/modified/renamed. SKILL.md updated with six-domain analysis instructions and tools-review output format. `pyproject.toml` declares tree-sitter dependencies. Wheel includes queries directory.

---

## Phase 5: End-to-End Verification
**Goal**: Verify the full integration across all modified phases with real multi-language test data. Catch cross-phase regressions and performance regressions.

### Tasks

- TSK-008-07: E2E verification of all AST-integrated phases
  - **Type**: Infra_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: Integration
  - **Verification**: `mise run test && mise run check`
  - **Estimated Time**: 45 minutes
  - **Files**:
    - `tests/core/test_treesitter.py`
    - `tests/test_micro/test_judge.py`
    - `tests/test_micro/test_refactor.py`
    - `tests/test_cli/test_review.py`
    - `tests/test_meso/test_plan_structure_injection.py`
    - `tests/e2e/test_ast_integration.bats`
  - **Rationale**: AC-ADHOC-008-06 (no regressions in excluded phases), AC-ADHOC-008-07 (dependencies importable), AC-ADHOC-008-10 (REVIEW multi-domain output). E2E bats test verifies the CLI integration paths work end-to-end: `deviate judge post` receives structured diff, `deviate plan pre` emits file structure, `deviate refactor post` runs multi-language checks, `deviate review pre` emits structured merge-base diff. Full suite regression ensures no breakage in RED, GREEN, YELLOW, TASKS, or MACRO phases.
  - **Details**:
    - **Implementation**: Create `tests/e2e/test_ast_integration.bats` with bats test cases: (1) `deviate review pre` emits `structured_diff` key in contract, (2) `deviate plan pre` emits `file_structure` key, (3) all tree-sitter imports succeed. Run `mise run test` (full pytest suite) to verify no regressions. Run `mise run check` (lint + format) to verify code quality. Verify performance: `get_parser()` ≤10ms, `extract_file_structure()` ≤200ms initial, `_check_return_type_mismatch()` ≤300ms. Document any performance regressions.
    - **Edge Cases**: `tree-sitter-languages` not installed in CI → tests skip gracefully. E2E bats tests use isolated temp directories. Performance benchmarks use `time.perf_counter()` with warm-up iterations.
    - **Acceptance**: `mise run test` exits 0. `mise run check` exits 0. No test regressions in excluded phases. All new tests pass. E2E bats tests pass.

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5

**Critical Dependency Chains**:
- TSK-008-01 must precede TSK-008-02 (analysis functions use parser + queries)
- TSK-008-02 must precede TSK-008-03, TSK-008-04, TSK-008-05, TSK-008-06 (all integrations depend on analysis functions)
- TSK-008-06 must include pyproject.toml dependency additions (required for all prior tasks to import `tree-sitter-languages` in tests)
- TSK-008-07 must follow all prior tasks (runs full suite)

**Risk Hotspots**:
- `tree-sitter-languages` binary wheel compatibility on macOS ARM64 (M-series) — test early in TSK-008-01
- Query file syntax errors in `.scm` files only surface at `tree_sitter.Query` compile time — covered by TSK-008-01 `test_query_file_coverage`
- Merge conflict between TSK-008-03 and TSK-008-05 both editing `micro.py` — both modify different functions (JUDGE: `_run_judge_phase`, REFACTOR: `_check_return_type_mismatch`), minimizing overlap
- Performance degradation on large files (>5000 lines) — TSK-008-02 and TSK-008-05 include size thresholds

**Merge Conflict Boundaries**:
- `src/deviate/cli/micro.py` — touched by TSK-008-03 (lines 1108-1137) and TSK-008-05 (lines 2507-2538)
- `tests/core/test_treesitter.py` — touched by TSK-008-01 and TSK-008-02
- `pyproject.toml` — touched by TSK-008-06

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.
- **_run_pytest Mocking**: Tests invoking CLI commands that internally call `_run_pytest` (red post, green post, refactor post) MUST mock `deviate.cli.micro._run_pytest` with an appropriate `subprocess.CompletedProcess` return value.
- **Production Code Git Isolation**: All `git` subprocess calls in production code MUST use `_git_env()` from `deviate.core._shared`.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
