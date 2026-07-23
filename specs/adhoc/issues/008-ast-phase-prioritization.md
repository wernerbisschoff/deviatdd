---
title: "REVOKED — ISS-ADH-008 (AST/Structural Analysis) was revoked on 2026-07-23. See CHANGELOG [Unreleased]."
labels: [enhancement, adhoc, vertical-slice, revoked]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-008
status: REVOKED
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/008-ast-phase-prioritization.md`
- **Primary Architectural Workstations**:
  - `src/deviate/core/treesitter.py` — new module: language-agnostic tree-sitter parser factory, grammar dispatch (20 languages), query execution, diff structure extraction, per-language `.scm` query files
  - `src/deviate/core/treesitter/queries/` — directory: per-language S-expression query files for function/class extraction, dead-code detection, duplication heuristics, cyclomatic complexity
  - `src/deviate/cli/micro.py:1108-1137` — `_run_judge_phase()`: inject structured diff summary (language-agnostic) before agent prompt
  - `src/deviate/cli/micro.py:2507-2538` — `_check_return_type_mismatch()`: replace with incremental tree-sitter parse + extended checks across all supported languages
  - `src/deviate/cli/meso.py` — plan phase: pre-scan target workstation files in any language, inject file structure appendix into plan prompt
  - `src/deviate/cli/review.py` — `deviate review pre`: compute merge-base vs branch structural diff via `extract_changed_symbols()`, inject structured diff appendix into review contract
  - `src/deviate/prompts/auto/judge.md` — update prompt template to consume structured diff format
  - `src/deviate/prompts/auto/plan.md` — update prompt template to consume file structure appendix
  - `src/deviate/prompts/skills/deviate-review/SKILL.md` — update review prompt to consume merge-base structured diff, align with tools-review's multi-domain approach (Security, Clean Code, Pragmatism, Idiomacy, Constitution, PRD)
  - `pyproject.toml` — add `tree-sitter>=0.24` + `tree-sitter-languages>=1.12` dependencies
- **Upstream Evidence**: `specs/explore/ast-tree-sitter.md` (language support matrix, phase integration potential table, existing AST usage), `specs/constitution.md` (model cost tiers)

## The Problem Contract
The current AST pipeline is Python-only — `_check_return_type_mismatch()` uses stdlib `ast` which cannot parse JS, TS, Rust, Go, C++, Elixir, C#, Markdown, Bash, JSON, TOML, YAML, HTML, CSS, SQL, Dockerfile, Terraform, Kotlin, or Swift files. As DeviaTDD targets multi-language codebases and manages its own operations in Markdown/Bash/TOML/JSON/YAML, JUDGE and PLAN phases need structural analysis that works across all 20 covered languages. Tree-sitter's unified API handles all of them with per-language grammar + query files. Pareto analysis shows 80% of value from 4 phases: JUDGE (Pro-tier, diff validation), PLAN (Pro-tier, pre-scan target files), REFACTOR (already has fragile Python-only `_check_return_type_mismatch`), and REVIEW (Flash-tier, merge-base structural diff for HITL Gate 3). This issue implements all 4 phases as language-agnostic and aligns /deviate-review with the tools-review multi-domain approach.

## Scope Boundaries
### Hard Inclusions
- Create `src/deviate/core/treesitter.py` with:
  - Language-agnostic parser factory: `get_parser(filepath: str) -> Parser` that detects language from file extension, loads the pre-compiled grammar from `tree-sitter-languages`, returns a configured tree-sitter `Parser`
  - `EXTENSION_MAP: dict[str, str]` — static mapping of file extensions to grammar IDs for: `.py`, `.js`, `.mjs`, `.cjs`, `.ts`, `.mts`, `.cts`, `.tsx`, `.rs`, `.go`, `.cpp`, `.cc`, `.cxx`, `.hpp`, `.h`, `.ex`, `.exs`, `.cs`, `.md`, `.mdx`, `.sh`, `.bash`, `.zsh`, `.json`, `.toml`, `.yaml`, `.yml`, `.html`, `.htm`, `.css`, `.scss`, `.less`, `.sql`, `Dockerfile`, `.dockerfile`, `.tf`, `.tfvars`, `.kt`, `.kts`, `.swift` (minimum)
  - `extract_changed_symbols(diff_text: str, filepath: str) -> list[SymbolChange]` — parses `git diff` output, splits by file, detects language per file, extracts changed function/class definitions with old/new signatures
  - `extract_file_structure(filepath: str) -> FileStructure` — parses a target file, extracts function/class/interface/enum signatures plus import/using/include blocks, returns structured data
  - `incremental_parse(filepath: str, old_tree: Tree | None) -> Tree` — runs `parser.parse(new_src, old_tree)` for incremental re-parse; only the initial call does a full parse
  - `extract_dead_code(filepath: str) -> list[str]` — detects functions/definitions with no call sites (across supported languages)
  - `detect_duplicate_blocks(filepath: str, min_lines: int = 5) -> list[DuplicateBlock]` — finds structurally similar AST subtrees ≥ min_lines
  - `estimate_cyclomatic_complexity(filepath: str, func_node: Node) -> int` — counts decision points (if/for/while/match/switch/case) within a function AST subtree
  - **Extensibility API** (adding a new language is 2 steps — no analysis function changes):
    - `EXTENSION_MAP: dict[str, str]` — the single source of truth for extension → grammar ID mapping. New language = 1 new key-value pair.
    - `get_language_id(filepath: str) -> str | None` — public lookup, returns grammar ID or None (unknown extension → graceful skip)
    - Future: `register_language(ext: str, grammar_id: str) -> None` — runtime registration for plugin-driven language additions without modifying `EXTENSION_MAP`
- Create `src/deviate/core/treesitter/queries/` with per-language `.scm` (S-expression query) files:
  - **Code languages** (functions, classes, dead-code, cyclomatic complexity):
    - `python.scm` — function_definition, class_definition, call_expression, import_statement, decorator
    - `javascript.scm` + `typescript.scm` + `tsx.scm` — function_declaration, class_declaration, arrow_function, interface_declaration, type_alias, export_statement, import_statement
    - `rust.scm` — function_item, struct_item, impl_item, trait_item, enum_item, use_declaration, call_expression
    - `go.scm` — function_declaration, method_declaration, type_spec, struct_type, interface_type, import_declaration, call_expression
    - `cpp.scm` — function_definition, class_specifier, template_declaration, using_declaration, call_expression
    - `elixir.scm` — def, defmodule, defstruct, defprotocol, defimpl, alias, import, call
    - `c_sharp.scm` — method_declaration, class_declaration, interface_declaration, struct_declaration, property_declaration, using_directive, invocation_expression
    - `bash.scm` — function_definition, command, variable_assignment, if_statement, for_statement, while_statement, case_statement
  - **Data/Markup languages** (structure extraction only — headings, keys, elements, selectors):
    - `markdown.scm` — section, fenced_code_block, list_item, link, image, emphasis, strong_emphasis
    - `json.scm` — object, array, pair, string_value, number_value, boolean_value, null_value
    - `toml.scm` — table, key_value, dotted_key, array_of_tables, inline_table
    - `yaml.scm` — document, block_mapping, block_sequence, flow_mapping, flow_sequence, block_scalar
    - `html.scm` — element, attribute, doctype, comment, script_element, style_element, self_closing_tag
    - `css.scm` — rule_set, declaration, selector, class_selector, id_selector, property_name, property_value, at_rule
  - **Infrastructure/Database languages** (structure extraction + dead-code for SQL functions):
    - `sql.scm` — create_table, create_function, create_procedure, select, insert, update, delete, column_definition
    - `dockerfile.scm` — from_instruction, run_instruction, cmd_instruction, env_instruction, expose_instruction, copy_instruction
    - `hcl.scm` — resource_block, variable_block, output_block, provider_block, module_block, locals_block, attribute
    - `kotlin.scm` — function_declaration, class_declaration, interface_declaration, object_declaration, property_declaration, lambda_expression
    - `swift.scm` — function_declaration, class_declaration, struct_declaration, protocol_declaration, enum_declaration, property_declaration
- JUDGE: in `_run_judge_phase()`, after collecting `git diff` output, call `extract_changed_symbols()` per-file to produce a language-agnostic structured change summary. Append to judge prompt as `## Structured Diff Summary`. Update `judge.md` to consume this section — format uses `Language: <lang> | Kind: <function|class|interface|...> | Name: <name> | Change: <modified|added|removed>`.
- PLAN: in `_plan_pre()` (meso layer), pre-scan target workstation files listed in the issue's `## System Topology Mapping`. Call `extract_file_structure()` per file (auto-detects language). Inject a `## Target File Structure` appendix into the plan prompt. Update `plan.md` to consume this section.
- REFACTOR: replace stdlib `ast` in `_check_return_type_mismatch()` with tree-sitter incremental parse across all supported languages. Extend checks: detect dead code (unused functions with no call sites), duplicated code blocks (similar AST subtrees ≥ 5 lines), and cyclomatic complexity warnings (≥ 10). Skip non-supported languages gracefully.
- REVIEW: In `deviate review pre`, after computing `git diff merge_base...HEAD`, parse each changed file at BOTH the merge-base commit AND the current HEAD via tree-sitter. Call `extract_file_structure()` on each version, diff the symbol sets to produce a structured merge-base vs branch change summary (per-file: `Language | Kind | Name | Change` with change types: `added`, `removed`, `modified`, `renamed`). Inject this as a `## Merge-Base Structured Diff` appendix into the review contract alongside the raw text diff. Update `deviate-review` SKILL.md to consume this structured appendix — the agent evaluates per-language symbol changes across all six domains: Security, Clean Code, Pragmatism, Idiomacy, Constitution, and PRD. Also update the SKILL.md to align with `tools-review`'s multi-domain output format: Positive Patterns, Critical Issues, Suggestions, Opportunities, Compliance Matrix, Quick Fix Summary.
- Add `tree-sitter>=0.24` and `tree-sitter-languages>=1.12` to `pyproject.toml` dependencies
- All existing tests under `tests/` must pass after integration

### Defensive Exclusions
- Do NOT integrate AST into RED, GREEN, YELLOW, TASKS, MACRO (explore/research/prd/shard), or TamperGuard — token/cost analysis shows low ROI regardless of language support
- Do NOT add tree-sitter grammar compilation — all grammars sourced pre-compiled from `tree-sitter-languages`
- Do NOT change the JUDGE agent's decision logic — only add structured context; the agent still makes the call
- Do NOT add mypy/pyre type checking integration — structural analysis only, no type system
- Do NOT modify test files beyond adding/updating unit tests for the new module
- Do NOT add custom query `.scm` files for languages beyond the 20-language minimum set — future languages are additive
- Do NOT attempt to detect relationships across files (cross-file call graphs) — per-file only

## Language Support Dispatch

| Extension(s) | Grammar | Query File | Key AST Nodes |
|:---|:---|:---|:---|
| `.py` | `python` | `python.scm` | function_definition, class_definition, call, import_statement |
| `.js`, `.mjs`, `.cjs` | `javascript` | `javascript.scm` | function_declaration, class_declaration, arrow_function, export_statement |
| `.ts`, `.mts`, `.cts` | `typescript` | `typescript.scm` | function_declaration, class_declaration, interface_declaration, type_alias |
| `.tsx` | `tsx` | `tsx.scm` | (TS nodes + jsx_element) |
| `.rs` | `rust` | `rust.scm` | function_item, struct_item, impl_item, trait_item, enum_item |
| `.go` | `go` | `go.scm` | function_declaration, method_declaration, type_spec |
| `.cpp`, `.cc`, `.cxx`, `.hpp`, `.h` | `cpp` | `cpp.scm` | function_definition, class_specifier, template_declaration |
| `.ex`, `.exs` | `elixir` | `elixir.scm` | def, defmodule, defstruct, defprotocol, defimpl |
| `.cs` | `c_sharp` | `c_sharp.scm` | method_declaration, class_declaration, interface_declaration |
| `.md`, `.mdx` | `markdown` | `markdown.scm` | section, fenced_code_block, list_item |
| `.sh`, `.bash`, `.zsh` | `bash` | `bash.scm` | function_definition, command, if_statement, for_statement |
| `.json` | `json` | `json.scm` | object, array, pair |
| `.toml` | `toml` | `toml.scm` | table, key_value |
| `.yaml`, `.yml` | `yaml` | `yaml.scm` | block_mapping, block_sequence |
| `.html`, `.htm` | `html` | `html.scm` | element, attribute, script_element, style_element |
| `.css`, `.scss`, `.less` | `css` | `css.scm` | rule_set, declaration, selector |
| `.sql` | `sql` | `sql.scm` | create_table, select, insert, function_definition |
| `Dockerfile`, `.dockerfile` | `dockerfile` | `dockerfile.scm` | from, run, cmd, env, copy |
| `.tf`, `.tfvars` | `hcl` | `hcl.scm` | resource, variable, output, provider, module |
| `.kt`, `.kts` | `kotlin` | `kotlin.scm` | function_declaration, class_declaration |
| `.swift` | `swift` | `swift.scm` | function_declaration, class_declaration, struct_declaration, protocol_declaration |

Unknown extensions → log warning + skip (graceful degradation).

### Extensibility Contract

Adding a new language requires exactly **2 changes** — no analysis function modifications:

1. **`EXTENSION_MAP` entry**: `{".nim": "nim", ".jsx": "javascript"}` in `treesitter.py`
2. **Query file**: `queries/nim.scm` with S-expression patterns for function/class/struct/call extraction

The core analysis pipeline is fully language-agnostic:
```
get_parser(path) ──EXTENSION_MAP──→ grammar ID ──tree-sitter-languages──→ configured Parser
                                              ↓
extract_*(path) ────→ Parser.parse(src) ──→ Tree ──→ Query(query_file)──→ matched nodes
```

All 6 analysis functions (`extract_changed_symbols`, `extract_file_structure`, `incremental_parse`, `extract_dead_code`, `detect_duplicate_blocks`, `estimate_cyclomatic_complexity`) dispatch through this same pipeline — they never reference a specific language by name. Adding Nim means writing `nim.scm` and adding the map entry; every function works immediately.

**Query file format** (`.scm`): Tree-sitter S-expression patterns with named captures. Each query file documents its capture names at the top:
```scheme
; CAPTURES: @function, @class, @call, @import, @comment
(function_definition name: (identifier) @function)
(class_definition name: (identifier) @class)
(call_expression function: (identifier) @call)
```

**Future**: A `register_language(ext, grammar_id)` runtime API could enable plugin-driven language additions without touching `EXTENSION_MAP` at all — but this is deferred to post-issue follow-up.

## Phase Prioritization Analysis (Reference)
Embedded from the adhoc conversation analysis. All phases ranked by token/cost ROI:

| Phase | Rank | Model Tier | AST Value | Rationale |
|-------|------|-----------|-----------|-----------|
| **JUDGE** | HIGH-ROI | V4 Pro (expensive) | Parse `git diff` across ANY supported language, extract changed signatures, 15x token reduction on Pro tier. Prevents full-cycle redo. | Implemented in this issue |
| **PLAN** | HIGH-ROI | V4 Pro (expensive) | Pre-scan target files in ANY supported language, inject structure. 50x token reduction. Prevents cascade failure across 3-5 tasks. | Implemented in this issue |
| **REVIEW** | HIGH-ROI | V4 Flash (cheap) | Compute merge-base vs branch structural diff across ANY language. Symbol-level comparison catches renames, signature shifts, dead code, and duplicate blocks that raw text diffs hide. Aligns output with tools-review multi-domain format (Security, Clean Code, Pragmatism, Idiomacy, Constitution, PRD). 20x token reduction on diff reading. | Implemented in this issue |
| **REFACTOR** | MEDIUM-ROI | V4 Flash (cheap) | Replace Python-only stdlib `ast` with language-agnostic incremental tree-sitter + extended checks. 10x faster on large files. | Implemented in this issue |
| GREEN | LOW-ROI | V4 Flash | Speculative value regardless of language support — no evidence GREEN fails from missing context. | Excluded |
| YELLOW | LOW-ROI | V4 Pro | Fires rarely (only on tamper). Low aggregate ROI. | Excluded |
| RED | SKIP | V4 Flash | Produces test stubs. AST of `assert` adds nothing pytest doesn't already verify. | Excluded |
| TASKS | SKIP | V4 Pro | Text decomposition, no code to parse. | Excluded |
| MACRO | SKIP | V4 Flash | Operates on Markdown. No code to parse. | Excluded |
| TamperGuard | SKIP | V4 Flash | File hashing already catches unauthorized edits. | Excluded |

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-008`
- **Acceptance Criteria Tokens**: `AC-ADHOC-008-01` through `AC-ADHOC-008-10`
- **Data Model Entities**: None (no new state entities; tree-sitter parser is stateless)

## User Stories Ledger
- **US-008-01**: As a DeviaTDD operator running `deviate run`, I want the JUDGE phase to receive a structured diff summary (in any language) instead of raw diff text so that the expensive Pro-tier agent spends fewer tokens on diff syntax parsing and more on compliance evaluation. *(Ref: FR-ADHOC-008)*
- **US-008-02**: As a DeviaTDD architect running `/plan`, I want the plan agent to receive a pre-extracted file structure appendix for target workstation files (in any language) so that the Pro-tier agent doesn't waste tokens reading large files and knows exact insertion points before task decomposition. *(Ref: FR-ADHOC-008)*
- **US-008-03**: As a DeviaTDD operator, I want REFACTOR phase dead-code and duplication detection across all supported languages so that `_check_return_type_mismatch` catches structural issues in Python, JS, TS, Rust, Go, C++, Elixir, and C# code without per-language special casing. *(Ref: FR-ADHOC-008)*
- **US-008-04**: As a DeviaTDD operator working on a multi-language codebase, I want the AST module to detect the correct language from file extension automatically so that I don't need to specify the language for each file. *(Ref: FR-ADHOC-008)*
- **US-008-05**: As a DeviaTDD operator running `/deviate-review` at HITL Gate 3, I want the review agent to receive a structured merge-base vs branch symbol diff (in any language) so that it catches per-language issues (renames, signature shifts, dead code, duplicate blocks, complexity spikes) that raw text diffs hide — and so the review matches the multi-domain rigor of `tools-review` (Security, Clean Code, Pragmatism, Idiomacy, Constitution, PRD). *(Ref: FR-ADHOC-008)*

## ATDD Acceptance Criteria

**Scenario 008-01**: Structured diff injected into JUDGE prompt (language-agnostic)
**Given** a GREEN-phase implementation produces a diff with changed function/class/interface signatures in any supported language
**When** `_run_judge_phase()` runs `git diff RED..HEAD`
**Then** the judge prompt contains a `## Structured Diff Summary` section with rows of `| Language | Kind | Name | Change |` — and the raw diff follows below for full context.

**Scenario 008-02**: File structure injected into PLAN prompt (language-agnostic)
**Given** a PLAN phase is invoked for an issue with target workstation files in Python, JS, Rust, or any other supported language
**When** the plan agent prompt is assembled
**Then** it contains a `## Target File Structure` appendix with function/class/interface/trait signatures and import/include/using blocks extracted from each target file via tree-sitter, annotated with the detected language.

**Scenario 008-03**: Incremental REFACTOR checks (multi-language)
**Given** a file in any supported language has been modified since the last parse
**When** `_check_return_type_mismatch()` runs in the REFACTOR phase
**Then** it uses tree-sitter incremental parse (re-parsing only changed ranges), detects dead code (unused definitions), duplicated code blocks (similar AST subtrees ≥ 5 lines), and cyclomatic complexity ≥ 10 — across all supported languages, not just Python.

**Scenario 008-04**: Language auto-detection from file extension
**Given** a file `src/app.ts` (TypeScript) and `src/main.rs` (Rust) are analyzed
**When** `get_parser()` is called for each file
**Then** the TypeScript grammar is used for `.ts` and the Rust grammar for `.rs` — correct grammar is dispatched without manual specification.

**Scenario 008-05**: Unknown language graceful degradation
**Given** a file with extension `.rb` (Ruby — not in the 8-language support set)
**When** `extract_file_structure()` or `extract_changed_symbols()` is called
**Then** the function logs a warning and returns an empty structure — no crash, no silent skip.

**Scenario 008-06**: No regressions in excluded phases
**Given** AST integration targets only JUDGE, PLAN, REVIEW, and REFACTOR
**When** RED, GREEN, YELLOW, TASKS, or MACRO phases execute
**Then** no tree-sitter code is invoked — execution path is unchanged from pre-integration.

**Scenario 008-07**: Dependencies are declared and importable
**Given** `pyproject.toml` declares `tree-sitter>=0.24` and `tree-sitter-languages>=1.12`
**When** `from deviate.core.treesitter import get_parser, extract_changed_symbols, extract_file_structure` is executed
**Then** the import succeeds and per-language `.scm` query files are loadable from the `queries/` subdirectory.

**Scenario 008-08**: Per-language query file coverage
**Given** the 20-language minimum set
**When** loading each `.scm` query file from `src/deviate/core/treesitter/queries/`
**Then** each file compiles with `tree_sitter.Query(language, query_text)` without error — files exist for all 20 languages: `python`, `javascript`, `typescript`, `tsx`, `rust`, `go`, `cpp`, `elixir`, `c_sharp`, `markdown`, `bash`, `json`, `toml`, `yaml`, `html`, `css`, `sql`, `dockerfile`, `hcl`, `kotlin`, `swift` (21 files covering 20 languages + TSX variant).

**Scenario 008-09**: Structured merge-base diff injected into REVIEW contract (language-agnostic)
**Given** a branch with N commits ahead of merge-base with `main`, containing changes in Python, TypeScript, and Rust files
**When** `deviate review pre` runs and computes `git diff merge_base...HEAD`
**Then** the contract contains a `## Merge-Base Structured Diff` appendix with per-file symbol changes annotated as `| Language | Kind | Name | Change |` — change types include `added`, `removed`, `modified`, `renamed` — and the raw text diff follows below for full context.

**Scenario 008-10**: REVIEW prompt consumes structured diff across multi-domains
**Given** the `deviate-review` SKILL.md prompt receives a contract with structured merge-base diff
**When** the review agent evaluates the diff
**Then** it analyzes per-language symbol changes across all six domains (Security, Clean Code, Pragmatism, Idiomacy, Constitution, PRD), detects renames/signature shifts/complexity spikes/dead code, and produces output sections aligned with tools-review: Positive Patterns, Critical Issues, Suggestions, Opportunities, Compliance Matrix, Quick Fix Summary.

## Edge Cases and Boundaries
- **Empty diff**: JUDGE `git diff` produces no output → `extract_changed_symbols()` returns empty structure list; judge prompt proceeds with no structured section.
- **Syntax errors in modified file**: Tree-sitter parse fails on broken source → fall back to raw diff text (graceful degradation, same as current behavior when `ast.parse` raises `SyntaxError`).
- **File not found in PLAN workstation list**: Target file listed in issue but missing from repo → log warning, skip that file in structure extraction, produce appendix with available files only.
- **Large files (>5000 lines)**: Tree-sitter incremental parse limits `changed_ranges()` scope. Full initial parse is one-time cost; subsequent uses only re-parse changed ranges.
- **Unknown language**: File extension not in `EXTENSION_MAP` → log warning, return empty structure — no exception raised.
- **Missing grammar for known extension**: `tree-sitter-languages` doesn't ship a grammar for an extension listed in `EXTENSION_MAP` → module raises `ImportError` at parser-construction time with clear message listing which grammar failed.
- **Mixed-language diffs**: A `git diff` spanning `.py` and `.rs` files → `extract_changed_symbols()` processes each hunk separately per file, dispatching to the correct grammar per extension.
- **No tree-sitter-languages installed**: At module import time, `try: from tree_sitter_languages import get_parser` — if `ImportError`, the module degrades gracefully: all public functions return empty structures, phases proceed without AST injection. No crash.
- **Merge-base not reachable** (review): `git merge-base main HEAD` fails (no common ancestor) → `extract_changed_symbols()` cannot be invoked; contract omits the structured diff appendix, review proceeds with raw text diff only.
- **Binary files in merge-base diff** (review): Binary file paths in diff → skipped by `extract_changed_symbols()`; structured diff appendix lists them as `| n/a | binary | <filename> | skipped |`.

## Performance Constraints
- `get_parser()`: ≤ 10ms cache lookup (parsers cached after first load per grammar)
- `extract_file_structure()`: ≤ 200ms per file (initial parse); ≤ 20ms incremental
- `extract_changed_symbols()`: ≤ 100ms per diff (regardless of language mix)
- `_check_return_type_mismatch()` (upgraded): ≤ 300ms per file (initial); ≤ 50ms incremental
- `extract_dead_code()`: ≤ 300ms per file (initial); ≤ 50ms incremental
- `detect_duplicate_blocks()`: ≤ 500ms per file (≤2000 lines); scales O(n²) in AST node count for similarity comparison
- `estimate_cyclomatic_complexity()`: ≤ 100ms per function
- Structured diff summary in JUDGE prompt: ≤ 500 tokens (vs raw diff which can be 3000+)
- Per-language `.scm` query file loading: ≤ 5ms per file (compiled once, cached per grammar ID)
- `EXTENSION_MAP` lookup: ≤ 1μs (frozen dict, O(1))
- Adding a new language: 0 changes to analysis logic — only EXTENSION_MAP entry + `.scm` file
- Review merge-base structured diff: ≤ 500ms for ≤20 changed files (two parses per file: merge-base version + HEAD version)
- Review structured diff appendix in contract: ≤ 800 tokens (vs full raw diff which can be 8000+)

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets (new module)** — `tests/core/test_treesitter.py`:
  - `test_language_dispatch_python` — `.py` → python grammar
  - `test_language_dispatch_typescript` — `.ts` → typescript grammar
  - `test_language_dispatch_rust` — `.rs` → rust grammar
  - `test_language_dispatch_go` — `.go` → go grammar
  - `test_language_dispatch_cpp` — `.cpp` → cpp grammar
  - `test_language_dispatch_elixir` — `.ex` → elixir grammar
  - `test_language_dispatch_csharp` — `.cs` → c_sharp grammar
  - `test_language_dispatch_markdown` — `.md` → markdown grammar
  - `test_language_dispatch_bash` — `.sh` → bash grammar
  - `test_language_dispatch_json` — `.json` → json grammar
  - `test_language_dispatch_toml` — `.toml` → toml grammar
  - `test_language_dispatch_yaml` — `.yaml` → yaml grammar
  - `test_language_dispatch_html` — `.html` → html grammar
  - `test_language_dispatch_css` — `.css` → css grammar
  - `test_language_dispatch_sql` — `.sql` → sql grammar
  - `test_language_dispatch_dockerfile` — `Dockerfile` → dockerfile grammar
  - `test_language_dispatch_terraform` — `.tf` → hcl grammar
  - `test_language_dispatch_kotlin` — `.kt` → kotlin grammar
  - `test_language_dispatch_swift` — `.swift` → swift grammar
  - `test_unknown_extension_logs_warning` — `.rb` → empty structure + warning
  - `test_extract_changed_symbols_single_function` — diff with one changed Python function → correct structure output
  - `test_extract_changed_symbols_mixed_languages` — diff spanning `.py` + `.rs` files → both languages parsed correctly
  - `test_extract_changed_symbols_empty_diff` — empty diff → empty structure list
  - `test_extract_file_structure_python` — file with classes and functions → correct signature extraction
  - `test_extract_file_structure_typescript` — `.ts` file with interface + class → correct extraction
  - `test_extract_file_structure_rust` — `.rs` file with struct + impl + trait → correct extraction
  - `test_incremental_parse_changed_ranges` — two consecutive parses of modified file → only changed ranges re-parsed
  - `test_dead_code_detection` — file with unused function → reported as dead code
  - `test_duplicate_block_detection` — file with similar AST subtrees → duplicate blocks reported
  - `test_cyclomatic_complexity` — function with if/for/while/switch → complexity ≥ threshold
  - `test_query_file_coverage` — all 9 `.scm` query files compile without error
- **Integration Sandbox Targets**:
  - `tests/test_micro/test_judge.py` — verify structured diff section appears in judge prompt (with language annotations)
  - `tests/test_micro/test_refactor.py` — verify upgraded `_check_return_type_mismatch` catches dead code in Python + JS + Rust
  - `tests/test_meso/test_plan.py` — verify file structure appendix appears in plan prompt (with language annotations)
  - `tests/test_cli/test_review.py` — verify structured merge-base diff appendix appears in review contract (with language annotations, per-file symbol changes, change type classification: added/removed/modified/renamed)

## Demonstration Path
```bash
# Unit tests for the new multi-language module
mise run test tests/core/test_treesitter.py -v

# Verify JUDGE prompt contains structured diff section
mise run test tests/test_micro/test_judge.py -v

# Verify REFACTOR dead-code detection across languages
mise run test tests/test_micro/test_refactor.py -v

# Verify PLAN prompt contains file structure appendix
mise run test tests/test_meso/test_plan.py -v

# Verify REVIEW contract contains structured merge-base diff appendix
mise run test tests/test_cli/test_review.py -v

# Full suite regression
mise run test
```
