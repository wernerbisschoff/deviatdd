## Plan Summary
- **Issue**: ISS-ADH-008 — AST/Structural Analysis Integration — JUDGE + PLAN + REVIEW + REFACTOR (Multi-Language)
- **Implementation Strategy**: Create a language-agnostic tree-sitter core module (`src/deviate/core/treesitter.py`) with 21 per-language query files, then integrate structured diff/file-structure injection into JUDGE, PLAN, REFACTOR, and REVIEW phases — replacing Python-only `ast` stdlib usage with multi-language tree-sitter parsing across all 20 supported languages.
- **Estimated Complexity**: High
- **Estimated Effort**: 8-12 hours

## Workstation Mapping
- **`src/deviate/core/treesitter.py`**: New module — the core language-agnostic parser factory and analysis pipeline. All 6 analysis functions (`extract_changed_symbols`, `extract_file_structure`, `incremental_parse`, `extract_dead_code`, `detect_duplicate_blocks`, `estimate_cyclomatic_complexity`) live here. Dispatches via `EXTENSION_MAP` → grammar ID → tree-sitter `Parser`.
  - **Current State**: Does not exist. `src/deviate/core/__init__.py` is empty.
  - **Changes Required**: Create the file with `EXTENSION_MAP` (38 extensions → 21 grammar IDs), `get_parser()` with parser caching, `get_language_id()`, all 6 analysis functions, and graceful degradation for unknown extensions and missing `tree-sitter-languages`.
  - **Integration Surface**: Imported by `micro.py` (JUDGE + REFACTOR), `meso.py` (PLAN), and `review.py` (REVIEW). Depends on `tree-sitter-languages` for pre-compiled grammars and `tree-sitter` for parser/query APIs.

- **`src/deviate/core/treesitter/queries/*.scm`**: New directory — 21 per-language S-expression query files for function/class extraction, dead code detection, duplication heuristics, and cyclomatic complexity.
  - **Current State**: Does not exist.
  - **Changes Required**: Create `src/deviate/core/treesitter/queries/` directory with 21 files: `python.scm`, `javascript.scm`, `typescript.scm`, `tsx.scm`, `rust.scm`, `go.scm`, `cpp.scm`, `elixir.scm`, `c_sharp.scm`, `markdown.scm`, `bash.scm`, `json.scm`, `toml.scm`, `yaml.scm`, `html.scm`, `css.scm`, `sql.scm`, `dockerfile.scm`, `hcl.scm`, `kotlin.scm`, `swift.scm`.
  - **Integration Surface**: Loaded by `treesitter.py` via `tree_sitter.Query(language, query_text)`. Each file documents its capture names (`@function`, `@class`, `@call`, etc.).

- **`src/deviate/cli/micro.py`** (lines 1108-1137): `_run_judge_phase()` — inject structured diff summary from `extract_changed_symbols()` before the agent prompt.
  - **Current State**: Collects raw `git diff RED..HEAD` text and appends it verbatim in `<diff>` tags (lines 1116-1126). No structural parsing.
  - **Changes Required**: After collecting raw diff, call `extract_changed_symbols(diff_text, filepath)` per-file. Append a `## Structured Diff Summary` section with `| Language | Kind | Name | Change |` rows before the raw diff. Gracefully handle empty diffs and parse errors.
  - **Integration Surface**: Calls `from deviate.core.treesitter import extract_changed_symbols`. Output feeds into `judge.md` prompt template (updated to consume structured section).

- **`src/deviate/cli/micro.py`** (lines 2507-2538): `_check_return_type_mismatch()` — replace Python-only `ast` with incremental tree-sitter parse + extended checks.
  - **Current State**: Uses stdlib `ast` module to parse `.py` files only; checks return type annotations against actual return values for 8 builtin types. No dead code, duplication, or complexity checks.
  - **Changes Required**: Replace `ast.parse()` with `get_parser(filepath)` + `incremental_parse()`. Add `extract_dead_code()`, `detect_duplicate_blocks()`, and `estimate_cyclomatic_complexity()` calls. Skip non-supported languages gracefully. Maintain existing return-type mismatch logic as one of several checks.
  - **Integration Surface**: Calls `from deviate.core.treesitter import get_parser, incremental_parse, extract_dead_code, detect_duplicate_blocks, estimate_cyclomatic_complexity`. Called by `refactor_post()`.

- **`src/deviate/cli/meso.py`** (`_plan_pre()`, line 556): Pre-scan target workstation files from the issue's system topology mapping, inject file structure appendix.
  - **Current State**: Emits a JSON contract with `spec_path`, `plan_target`, `worktree_full`, etc. Does not pre-scan or inject file structure.
  - **Changes Required**: After resolving `spec_path`, parse the issue file's `## System Topology Mapping` section to extract primary architectural workstations file paths. For each workstation file that exists in the repo, call `extract_file_structure()`. Append a `file_structure` key to the JSON contract containing per-file language and signatures. Update downstream prompt assembly (where `_plan_pre` output feeds the plan agent) to inject this as `## Target File Structure` appendix. Alternatively, inject directly into the contract.
  - **Integration Surface**: Calls `from deviate.core.treesitter import extract_file_structure`. Contract output feeds into `plan.md` prompt template.

- **`src/deviate/cli/review.py`** (`pre` command): Compute merge-base structured diff via tree-sitter, inject into review contract.
  - **Current State**: Computes `git diff merge_base...HEAD` as raw text and includes it in the JSON contract under `diff` key. No structural analysis.
  - **Changes Required**: After computing the raw diff, parse each changed file at both the merge-base commit and HEAD. Call `extract_file_structure()` on each version (by checking out file content at each commit via `git show <sha>:<path>`). Diff the symbol sets to produce a per-file structured change summary with change types (`added`, `removed`, `modified`, `renamed`). Add a `structured_diff` key to the contract. Handle merge-base-not-found gracefully.
  - **Integration Surface**: Calls `from deviate.core.treesitter import extract_file_structure, get_parser`. Contract feeds into `deviate-review` SKILL.md.

- **`src/deviate/prompts/auto/judge.md`**: Update prompt template to consume `## Structured Diff Summary` section.
  - **Current State**: References raw `<diff>` content only. No structured diff consumption instructions.
  - **Changes Required**: Add a `## Structured Diff Summary` consumption instruction in `STEP_2: ANALYZE_DIFF` — parse the `| Language | Kind | Name | Change |` table, use it to classify changes by language and type before detailed raw diff analysis. Update the `diff_summary` YAML schema to optionally include structured diff fields.
  - **Integration Surface**: Consumed by `_run_judge_phase()` in `micro.py`.

- **`src/deviate/prompts/auto/plan.md`**: Update prompt template to consume `## Target File Structure` appendix.
  - **Current State**: Has placeholder `{spec_path}` / `{plan_path}` / `{issue_id}` variables. No file structure appendix consumption.
  - **Changes Required**: Add a `## Target File Structure` consumption instruction in `step id="codebase_scan"` — the appendix contains per-file language, function/class signatures, and import blocks extracted via tree-sitter. Agent uses this to plan insertion points without reading full files. Format: `file.md: Language | Kind | Name | Signature`.
  - **Integration Surface**: Consumed by plan agent via meso layer plan invocation.

- **`src/deviate/prompts/skills/deviate-review/SKILL.md`**: Update to consume `## Merge-Base Structured Diff` appendix and align with multi-domain output format.
  - **Current State**: Simple three-area scan (Ledger, Consistency, Security) with OK/FLAG output. Version 1.1.0.
  - **Changes Required**: Add structured diff consumption step — parse `| Language | Kind | Name | Change |` per file. Align review output with `tools-review` multi-domain format: Positive Patterns, Critical Issues, Suggestions, Opportunities, Compliance Matrix, Quick Fix Summary. Apply all six domains (Security, Clean Code, Pragmatism, Idiomacy, Constitution, PRD) to per-language symbol changes.
  - **Integration Surface**: Consumed by review agent via `deviate review pre` contract output.

- **`pyproject.toml`**: Add tree-sitter dependencies.
  - **Current State**: Currently has `typer`, `rich`, `pydantic`, `pyyaml`.
  - **Changes Required**: Add `tree-sitter>=0.24` and `tree-sitter-languages>=1.12` to `dependencies`.
  - **Integration Surface**: Required by `treesitter.py` for actual parsing. Package wheel must include `queries/` directory via `tool.hatch.build.targets.wheel`.

## Implementation Strategy
- **Phase 1**: Core tree-sitter module — parser factory, extension map, query file loading
  - **Files**: `src/deviate/core/treesitter.py`, `src/deviate/core/treesitter/queries/*.scm` (21 files)
  - **Approach**: Create `EXTENSION_MAP` with all 38 extension entries, implement `get_parser()` with per-grammar caching via dictionary, implement `get_language_id()` for public lookup. Implement `_load_query(language, query_name)` that reads `.scm` files and compiles `tree_sitter.Query`. Write all 21 query files with documented capture names. Implement all 6 analysis functions: `extract_changed_symbols()` (parse git diff hunks, dispatch per filename), `extract_file_structure()` (full parse + query run), `incremental_parse()` (wrap `parser.parse(src, old_tree)`), `extract_dead_code()` (collect `@call` captures, flag `@function/@class` not called), `detect_duplicate_blocks()` (AST subtree hash comparison, O(n²) pair check with min-lines filter), `estimate_cyclomatic_complexity()` (count decision nodes in subtree). Graceful degradation: `try: import tree_sitter_languages` — if missing, all functions return empty structures.
  - **Verification**: `pytest tests/core/test_treesitter.py -v` — all language dispatch tests, query file compilation, extraction accuracy and edge cases.

- **Phase 2**: JUDGE integration — structured diff injection
  - **Files**: `src/deviate/cli/micro.py` (lines 1108-1137), `src/deviate/prompts/auto/judge.md`
  - **Approach**: In `_run_judge_phase()`, after `diff = subprocess.run(["git", "diff", ...])`, call `extract_changed_symbols(diff, <filepath>)` for each changed file detected. Build `## Structured Diff Summary` table. Prepend to prompt before raw `<diff>` section. Update `judge.md` to instruct agent to consume the table for language-aware classification before raw diff analysis. Add `diff_summary.structured_changes` optional field to YAML schema.
  - **Verification**: `pytest tests/test_micro/test_judge.py -v` — verify structured diff section appears in judge prompt with language annotations.

- **Phase 3**: PLAN integration — file structure appendix injection
  - **Files**: `src/deviate/cli/meso.py` (`_plan_pre()`), `src/deviate/prompts/auto/plan.md`
  - **Approach**: In `_plan_pre()`, after resolving `spec_path`, parse the issue file's `## System Topology Mapping` → `## Primary Architectural Workstations` list. Extract file paths. For each existing file, call `extract_file_structure()`. Add `file_structure: {filepath: {language, symbols[...]}}` to contract JSON. Update `plan.md` to add `## Target File Structure` consumption step. On file-not-found: log warning, skip.
  - **Verification**: `pytest tests/test_meso/test_plan.py -v` — verify file structure appendix in plan prompt.

- **Phase 4**: REFACTOR integration — multi-language checks
  - **Files**: `src/deviate/cli/micro.py` (lines 2507-2538)
  - **Approach**: Replace `ast.parse()` with `get_parser(filepath)` + `incremental_parse()`. Keep existing return-type mismatch logic for Python (mapping tree-sitter node types to the known builtins). Add calls to `extract_dead_code()`, `detect_duplicate_blocks(min_lines=5)`, `estimate_cyclomatic_complexity()` with threshold=10. Aggregate all issues into return list. Unknown extensions → empty results (no crash).
  - **Verification**: `pytest tests/test_micro/test_refactor.py -v` — dead code in Python + JS + Rust detected.

- **Phase 5**: REVIEW integration — merge-base structured diff + multi-domain alignment
  - **Files**: `src/deviate/cli/review.py` (`pre` command), `src/deviate/prompts/skills/deviate-review/SKILL.md`
  - **Approach**: In `review pre`, after computing raw diff via `git diff merge_base...HEAD`, extract changed file paths from diff. For each file, run `git show merge_base:<path>` and `git show HEAD:<path>` to get both versions, call `extract_file_structure()` on each, compare symbol sets to derive change type (`added`, `removed`, `modified`, `renamed`). Build `structured_diff: {filepath: [{language, kind, name, change}]}` in contract. Update `deviate-review` SKILL.md: add Step 1.5 to parse structured diff, expand Step 2 scan to six domains, change Step 3 output to multi-domain format. Handle merge-base-not-found: omit structured diff key.
  - **Verification**: `pytest tests/test_cli/test_review.py -v` — structured merge-base diff appendix in review contract with per-file symbol changes.

- **Phase 6**: Dependencies + package config + full verification
  - **Files**: `pyproject.toml`, `src/deviate/core/__init__.py`
  - **Approach**: Add `tree-sitter>=0.24` and `tree-sitter-languages>=1.12` to `dependencies`. Add `queries/` to wheel package config via `tool.hatch.build.targets.wheel.force-include`. Run full test suite: `mise run test` and `mise run check`.
  - **Verification**: `mise run test` — full suite regression; `mise run check` — lint + format check.

## Data Flow Analysis
- **JUDGE Phase**: `git diff RED..HEAD` (raw text) → `extract_changed_symbols()` → per-file `Language | Kind | Name | Change` table → prepended to judge prompt before raw diff → agent consumes both structured summary and raw diff → emits verdict YAML.
- **PLAN Phase**: Issue file `## System Topology Mapping` → file paths → `extract_file_structure()` per file → `{language, symbols[...]}` → `file_structure` key in contract → plan prompt `## Target File Structure` appendix → agent uses for insertion point planning.
- **REFACTOR Phase**: Source file path → `get_parser()` → `incremental_parse()` → query execution for `@function`, `@class`, `@call`, decision nodes → `extract_dead_code()` + `detect_duplicate_blocks()` + `estimate_cyclomatic_complexity()` + return-type mismatch → issues list → console output.
- **REVIEW Phase**: `git diff merge_base...HEAD` → changed file paths → `git show <sha>:<path>` per version → `extract_file_structure()` per version → symbol diff → `added/removed/modified/renamed` per-symbol → `structured_diff` key in contract → review agent consumes → multi-domain output.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `tree-sitter-languages` not installed or missing grammars | High | Medium | Graceful degradation at import time: `try`/`except ImportError` — all functions return empty structures, phases proceed without AST injection. No crash. |
| Query file syntax errors cause tree-sitter to reject query | Medium | Low | Each `.scm` file tested with `tree_sitter.Query(language, query_text)` at module load; failures logged as warnings. |
| Performance exceeds constraints on large files (>5000 lines) | Medium | Medium | Incremental parse limits scope to changed ranges. First parse is one-time cost. Skip analysis for files >10000 lines (configurable threshold). |
| Syntax errors in modified files cause parse failure | Low | Medium | Fall back to raw diff text (graceful degradation). Same as current behavior when `ast.parse` raises `SyntaxError`. |
| `git merge-base` fails (no common ancestor) in REVIEW | Low | Low | Omit `structured_diff` key from contract. Review proceeds with raw text diff only. |
| Mixed-language diffs with unknown extensions | Low | Low | `EXTENSION_MAP` lookup returns `None` → skip that file in structured diff. Warning logged. |
| Phase implementation order creates merge conflicts | Medium | High | Phases 2-5 modify different functions in different files, minimizing overlap. `micro.py` JUDGE and REFACTOR changes are in separate functions. Commit each phase independently. |

## Integration Points
- **`src/deviate/core/treesitter.py` → `tree-sitter-languages`**: Depends on pre-compiled grammars from `tree_sitter_languages.get_parser(grammar_id)`. Import-time check: `try: from tree_sitter_languages import get_parser as ts_get_parser`. Falls back gracefully on `ImportError`.
- **`micro.py` → `treesitter.py`**: `extract_changed_symbols()` for JUDGE; `get_parser` + `incremental_parse` + `extract_dead_code` + `detect_duplicate_blocks` + `estimate_cyclomatic_complexity` for REFACTOR. Both called with `Path.cwd()` as root for file resolution.
- **`meso.py` → `treesitter.py`**: `extract_file_structure()` called per-workstation file. File paths from issue markdown mapping.
- **`review.py` → `treesitter.py`**: `extract_file_structure()` called per-version (merge-base + HEAD) per-changed file. Uses `git show <sha>:<path>` for file content retrieval.
- **`pyproject.toml` → wheel packaging**: Must include `src/deviate/core/treesitter/queries/` directory in wheel via `tool.hatch.build.targets.wheel.force-include` or `packages`.

## Constitutional Alignment
- **Architecture**: Aligns with three-layer architecture: core module (`treesitter.py`) is a stateless utility layer under `src/deviate/core/`. Integration points touch micro layer (JUDGE, REFACTOR in `micro.py`), meso layer (PLAN in `meso.py`), and review gate (REVIEW in `review.py`). No modifications to macro layer. Defensive exclusions (RED, GREEN, YELLOW, TASKS, MACRO, TamperGuard) preserve architectural boundaries.
- **Testing**: Unit tests under `tests/core/test_treesitter.py` for all 6 analysis functions + language dispatch + edge cases. Integration tests under `tests/test_micro/test_judge.py`, `tests/test_micro/test_refactor.py`, `tests/test_meso/test_plan.py`, `tests/test_cli/test_review.py`. All use pytest with appropriate mocking. Coverage target >= 80%.
- **Git Isolation**: All changes within worktree `008-ast-phase-prioritization`. Each phase commit is atomic. No branch switching within the worktree. Production code uses `_git_env()` for subprocess calls (already established pattern). Test fixtures use `tmp_git_repo` with isolated git state.
