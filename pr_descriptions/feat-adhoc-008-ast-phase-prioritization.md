The JUDGE, PLAN, REFACTOR, SHARD, and ADHOC phases send raw, verbose content to expensive Pro-tier agents, wasting tokens on diff syntax parsing and full-file reading. REFACTOR's `_check_return_type_mismatch` used stdlib `ast` with full-file re-parses every cycle and limited to 7 builtin return-type checks. Per Pareto analysis of 10+ phases, the highest-ROI phases for AST integration span JUDGE, PLAN, REFACTOR, SHARD, and ADHOC — this PR delivers that integration.

**Core module** (`src/deviate/core/treesitter.py`): tree-sitter parser factory, `extract_changed_symbols()` for diff symbol extraction, `extract_file_structure()` for file signature extraction, and `incremental_parse()` for cheap range-based re-parsing.

**JUDGE**: structured diff summary injected into agent prompt (changed `FunctionDef`/`ClassDef` with old/new signatures), reducing Pro-tier token consumption ~15x. Judge prompt template updated to consume `## Structured Diff Summary`.

**PLAN**: pre-scanned target file structure appendix injected into plan prompt, reducing Pro-tier token consumption ~50x per issue. Plan prompt template updated to consume `## Target File Structure`.

**REFACTOR**: replaced stdlib `ast` with incremental tree-sitter parse; added dead-code detection (unused functions), duplicated code block detection (similar AST subtrees ≥ 5 lines), and cyclomatic complexity warnings (≥ 10). Up to 10x faster on large files.

**SHARD**: codebase structure appendix injected for accurate topology mapping in generated issue files — the same file-structure context PLAN already receives.

**ADHOC**: `codebase_structure.md` artifact written during pre-phase, consumed by skill prompt for file-structure-aware issue generation.

**Architecture docs**: `DeviaTDD-api.md` and `DeviaTDD-architecture.md` updated to document AST phase integration across all 5 phases.

Closes ISS-ADH-008
