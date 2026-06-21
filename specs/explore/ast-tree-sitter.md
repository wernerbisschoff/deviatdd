# Explore: AST Parsing / Tree-Sitter Integration for DeviaTDD

## Problem Definition

[Statement]: Investigate how AST parsing — specifically Tree-sitter — can be integrated into the DeviaTDD system to enhance structural code analysis, spec compliance verification, and codebase understanding across macro, meso, and micro layers.

[Scope]:
- Existing AST usage in the DeviaTDD codebase (stdlib `ast` module)
- The three-layer architecture (macro/meso/micro) and phase-by-phase integration potential
- Tree-sitter vs stdlib `ast` vs complementary tools (Semgrep, ast-grep, LibCST)
- Concrete insertion points in JUDGE, REFACTOR, PLAN, and GREEN phases
- Ecosystem tooling research for structural pattern matching in Python codebases

[Exclusions]:
- No architectural decisions or trade-off evaluations (deferred to `deviate-research`)
- No implementation code or integration work
- No analysis of non-Python languages (DeviaTDD is Python-only)
- No risk analysis or failure-mode speculation

## Discovery Audit Results

### Verified Dependencies

No AST or tree-sitter dependencies declared in any manifest. The only AST usage is stdlib `ast` (built-in, no dependency).

| Dependency | Manifest | Source Path(s) |
| :--- | :--- | :--- |
| `typer>=0.12` | `pyproject.toml` | `src/deviate/cli/__init__.py`, `src/deviate/main.py` |
| `rich>=13.0` | `pyproject.toml` | `src/deviate/cli/micro.py` |
| `pydantic>=2.0` | `pyproject.toml` | `src/deviate/state/config.py`, `src/deviate/state/ledger.py` |
| `pyyaml>=6.0.3` | `pyproject.toml` | `src/deviate/core/validation.py` |
| `ast` (stdlib) | built-in | `src/deviate/cli/micro.py:2507-2516` |
| `subprocess` (stdlib) | built-in | `src/deviate/core/agent.py`, `src/deviate/cli/micro.py` |

### Ghost Dependencies

None detected. All referenced imports resolve to declared dependencies or stdlib.

### Manifest Files Observed

- `pyproject.toml`: Project metadata, Python 3.13+, dependencies (typer, rich, pydantic, pyyaml), pytest config
- `.mise.toml`: Task runner definitions (test, lint, format, check, type-check, etc.)
- `.deviate/config.toml`: Per-phase model routing, backend config, feature flags

### Test Runner Configuration

- Test command: `pytest tests/ -v` (from `mise.toml` `[tasks.test]`)
- Lint command: `ruff check .`
- E2E command: `bats tests/e2e/` (bash automated test system)
- Type check: not configured (mise no-op)
- Coverage config: `[tool.pytest.ini_options]` in `pyproject.toml`

### Manifest-Constitution Divergence

None observed. The constitution's `[2_TECH_STACK_STANDARDS]` (Python 3.13, Typer, Rich, JSONL/TOML storage) matches `pyproject.toml` declarations exactly.

## Constitution Quotes

Constitution excerpts quoted verbatim. No interpretation, inference, or classification.

- **Architectural Principles**: "Three-Layer Architecture: Macro (feature scoping: Explore → Research → PRD → Shard+Specify), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR). Each layer has strict phase gates — no layer may be skipped."

- **Tech Stack Standards**: "Python 3.13; Target: CLI application (`deviate`); Framework: Typer (CLI entry points) with Rich for terminal I/O; No persistent database runtime (all state tracked in JSONL ledgers and TOML config)"

- **Testing Protocols**: "RED phase tests must fail with `AssertionError` or `NotImplementedError` — syntax crashes are rejected; GREEN phase must pass all tests; Tamper Guard resets unauthorized test edits; REFACTOR phase runs regression gate: tests must re-pass after polish"

- **Definition of Done**: "Code implemented (satisfies acceptance criteria from `spec.md`); Tests passing (pytest with clean exit code 0); Lint passing (ruff check with no violations); Judge phase passed (git diff validated against `spec.md` invariants); No governance violations (constitution rules upheld, no HITL gates bypassed)"

## Architectural Baselines

[Pattern_Over_Instance]: Only representative examples or base classes listed. All paths strictly relative to `repo_root`.

- **Existing Architectural Patterns**:
  - Three-layer hierarchy with strict phase gates — MACRO (explore→research→prd→shard), MESO (plan→tasks), MICRO (RED→GREEN→[YELLOW]→JUDGE→REFACTOR)
  - Pre/post subcommand pattern: every phase has pre (emits JSON contract) and post (validates artifact, transitions state, commits)
  - Agent invocation via `AgentBackend.invoke()` → `subprocess.Popen` pipe with prompt on stdin; agent outputs YAML `HandoverManifest` on stdout
  - Template assembly: `constitution.md → core/{layer}.md → auto/{phase}.md` with `${PLACEHOLDER}` substitution
  - `src/deviate/cli/micro.py:_run_tdd_cycle()` lines 1344-1528 orchestrates the micro flow

- **Infrastructure & Operations**:
  - Package manager: `uv`; Task runner: `mise`
  - No containerization, no CI/CD config detected
  - Git hooks under `.githooks/`
  - `src/deviate/cli/micro.py:1915` `_run_pytest` — subprocess call to pytest
  - `src/deviate/cli/micro.py:2066` `_run_test_cmd` — `subprocess.run(["mise", "run", "test"], ...)`

- **Data & State Management**:
  - Session state: `.deviate/session.json` (`SessionState` Pydantic model)
  - Issue ledger: `specs/issues.jsonl` (append-only JSONL)
  - Task ledger: `specs/**/tasks.jsonl` (append-only JSONL)
  - Config: `.deviate/config.toml` (`DeviateConfig`)
  - Rollback snapshots: `.deviate/rollback.jsonl`

- **Quality, Safety & Observability**:
  - TamperGuard in `src/deviate/core/tamper.py` — protects test files from unauthorized GREEN-phase edits
  - Spec validation in `src/deviate/core/validation.py` — YAML frontmatter + section-heading regex matching (NO AST-based validation)
  - `_run_pytest`/`_run_test_cmd`/`_run_format_cmd` — subprocess-based verification
  - Type check: not configured (mise task is no-op)

- **External Integrations**:
  - `AgentBackend` supports `opencode`, `claude`, `droid` backends via `BACKEND_COMMANDS` map
  - `context` CLI for offline documentation queries
  - No third-party API clients, webhooks, or SDKs

### Existing AST Usage (sole reference)

Found in `src/deviate/cli/micro.py:2469-2539` — `_check_return_type_mismatch()` function in REFACTOR post-command:

```python
def _check_return_type_mismatch(filepath: str) -> list[str]:
    try:
        with open(filepath, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=filepath)
    except SyntaxError:
        return issues
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.returns is None:
            continue
```

This is a lightweight return-type mismatch checker for builtin types (`str`, `int`, `float`, `bool`, `list`, `dict`, `tuple`, `set`). It walks `FunctionDef` nodes and checks `Return` statements against return annotations. Invoked from `refactor_post()` — on mismatch detection, `git restore .` is called and pipeline halts.

**Key limitation**: Uses stdlib `ast` which discards comments, whitespace, and formatting. Single-shot parsing (no incremental). Python-only.

## Ecosystem Research

[Web_Discovery]: Factual cataloging of industry best practices, common use cases, and standard tools for structural code analysis.

### Best Practices

- **Tree-sitter query system uses S-expression patterns with named captures (`@`) for structural matching across languages** — patterns like `(binary_expression (number_literal) (number_literal))` match syntax tree nodes directly, supporting field names (`left:`, `right:`) and wildcards (`_`). [Source](https://tree-sitter.github.io/tree-sitter/using-parsers/queries/1-syntax)
- **Semgrep achieves 20K-100K loc/sec per rule offline** — using tree-sitter for parsing and its own pattern DSL (ellipsis `...`, metavariables `$X`, deep expression `<...>`) for rules that are just code snippets, not AST boilerplate. [Source](https://semgrep.dev/docs/writing-rules/pattern-syntax/)
- **LibCST (Instagram) creates a "lossless CST that looks like an AST"** — preserves comments, whitespace, parentheses, and formatting, enabling round-trip-safe automated refactoring. [Source](https://github.com/Instagram/LibCST)
- **Tree-sitter's incremental parsing (`parser.parse(new_src, old_tree)`) enables real-time/editor integration** — only re-parses changed ranges, `Tree.changed_ranges()` returns only syntactically-affected regions. [Source](https://github.com/tree-sitter/py-tree-sitter)

### Common Use Cases & Pitfalls

- **Python stdlib `ast` module strips formatting details** — no comments, no whitespace, no parentheses. Designed for compilation, not code transformation that must preserve source. `ast.parse()` is single-shot, not incremental. [Source](https://docs.python.org/3/library/ast.html)
- **Key differentiator: tree-sitter produces a Concrete Syntax Tree (CST) preserving all tokens** while python `ast` discards formatting — tree-sitter re-parses only changed regions (incremental), `ast` re-parses the entire file. [Source](https://github.com/tree-sitter/py-tree-sitter)
- **Tree-sitter supports `(ERROR)` and `(MISSING)` node queries** for detecting syntax errors in partially valid files — enables tools to operate on incomplete code during typing. [Source](https://tree-sitter.github.io/tree-sitter/using-parsers/queries/1-syntax)
- **Code2flow generates call graphs for dynamic languages via AST analysis** but warns: "No algorithm can generate a perfect call graph for a dynamic language" — limitations include anonymous/lambda functions, cross-module name collisions. [Source](https://github.com/scottrogowski/code2flow)

### Standard Tooling

| Tool | Language Support | Use Case | Parser | Key Feature |
|------|-----------------|----------|--------|-------------|
| **Semgrep** | 30+ languages | SAST, custom lint, CI | Tree-sitter + OCaml | Pattern DSL with metavariables + ellipsis + dataflow |
| **Ast-grep (sg)** | 20+ languages | Search/replace/lint | Tree-sitter (Rust) | CLI `sg run -p '$A && $A()' -r '$A?.()'` |
| **LibCST** | Python only | Codemod, refactoring | Parso (Rust) | Lossless CST, round-trip safe |
| **Astroid** | Python only | Pylint engine | stdlib `_ast` rebuild | Static type inference + scope resolution |
| **Tree-sitter** (Python) | 100+ grammars | Generic AST, pattern matching | C library | Incremental parsing, `Query`/`QueryCursor` |
| **Python stdlib `ast`** | Python only | Compilation, basic analysis | CPython parser | Zero deps, `NodeTransformer`/`NodeVisitor` |

## File Registry

| Path (Strictly Relative to Repo Root) | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `src/deviate/cli/micro.py` | Source | Micro phase engine, TDD cycle orchestration | `_PHASE_MAP: dict[str, Callable] = {"RED": _run_red_phase, "GREEN": _run_green_phase, "JUDGE": _run_judge_phase, "REFACTOR": _run_refactor_phase}` |
| `src/deviate/cli/micro.py:2469-2539` | Source | `_check_return_type_mismatch` — sole AST usage | `def _check_return_type_mismatch(filepath: str) -> list[str]: try: with open(filepath, encoding="utf-8") as f: tree = ast.parse(f.read(), filename=filepath)` |
| `src/deviate/cli/micro.py:1915` | Source | `_run_pytest` — subprocess test execution | `def _run_pytest(root, report_config=None): test_files = _find_test_files(root); cmd = [sys.executable, "-m", "pytest", *test_file_list, "-v"]` |
| `src/deviate/cli/micro.py:2066` | Source | `_run_test_cmd` — mise task subprocess | `def _run_test_cmd(root): return subprocess.run(["mise", "run", "test"], cwd=root, capture_output=True, text=True)` |
| `src/deviate/cli/micro.py:733-784` | Source | `_build_auto_prompt` — prompt assembly | `def _build_auto_prompt(phase: str, task: TaskRecord, root: Path) -> str: spec_content = _resolve_spec_content(task.source_file)` |
| `src/deviate/cli/meso.py` | Source | Meso layer: plan/tasks/pre/post | `def _invoke_agent_phase(phase, contract, cwd=None): prompt = _build_slim_prompt(phase, contract)` |
| `src/deviate/cli/macro.py` | Source | Macro layer: explore/research/prd/shard | `_PHASE_ORDER = ["explore", "research", "prd", "shard"]` |
| `src/deviate/cli/__init__.py` | Source | CLI root, init command | `cli = typer.Typer(no_args_is_help=True)` |
| `src/deviate/core/agent.py` | Source | Agent subprocess & handover parsing | `BACKEND_COMMANDS: dict[str, str] = {"opencode": "opencode run", "claude": "claude -p", "droid": "droid exec", "stub": "stub"}` |
| `src/deviate/core/agent.py:274` | Source | `AgentBackend.invoke()` — agent launch | `proc = subprocess.Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)` |
| `src/deviate/core/tamper.py` | Source | TamperGuard for test files | `class TamperGuard: ... evaluate(context, repo_path, approved_mods)` |
| `src/deviate/core/validation.py` | Source | Spec artifact validation | `def validate_artifact(content, artifact_type): ...` (YAML + heading regex) |
| `src/deviate/prompts/assembly.py` | Source | Template assembly pipeline | `def assemble_prompt(template_name, context, constitution_path): ...` |
| `src/deviate/prompts/assembly.py:14` | Source | Layer-to-template routing | `_LAYER_MAP = {"explore": "macro-auto", "research": "macro-auto", "prd": "macro-auto", "shard": "macro-auto", "plan": "meso-auto", "tasks": "meso-auto", "red": "micro-auto", "green": "micro-auto", "refactor": "micro-auto", "yellow": "micro-auto", "judge": "micro-auto", "execute": "micro-auto"}` |
| `src/deviate/prompts/auto/judge.md` | Template | JUDGE phase prompt (163 lines) | `You are a **Compliance Judge** operating inside the **DeviaTDD JUDGE phase**...` |
| `src/deviate/prompts/auto/green.md` | Template | GREEN phase prompt (137 lines) | `This system operates exclusively as an automated, context-isolated...` |
| `src/deviate/prompts/core/core.md` | Template | Universal invariants (21 lines) | `## DeviaTDD Universal Invariants` |
| `src/deviate/prompts/core/micro-auto.md` | Template | Micro layer preamble (31 lines) | `## Micro Layer Execution Model — TDD Sandbox` |
| `src/deviate/state/config.py` | Source | Config/Session Pydantic models | `class SessionState(BaseModel): current_phase: str = "IDLE"` |
| `src/deviate/state/config.py:135` | Source | Model resolution per phase | `def resolve_model_for_phase(phase: str, root: Path) -> str | None:` |
| `src/deviate/state/ledger.py` | Source | Append-only JSONL ledger | `class TaskRecord(BaseModel): id: str; issue_id: str; status: Literal[...]` |
| `src/deviate/prompts/` | Directory | Prompt template vault | Contains: `core/`, `auto/`, `skills/`, `governance/` |
| `src/deviate/prompts/skills/` | Directory | Skill definitions (20 skills) | `deviate-red`, `deviate-green`, `deviate-judge`, `deviate-refactor`, `deviate-plan`, `deviate-explore`, etc. |
| `specs/constitution.md` | Spec | Project governance (89 lines) | `[CONSTITUTION_VERSION]: 0.2.0` |
| `specs/DeviaTDD-architecture.md` | Spec | Architecture reference doc | `## DeviaTDD System Architecture` |
| `specs/DeviaTDD-api.md` | Spec | API reference doc | `## DeviaTDD CLI API Reference` |
| `pyproject.toml` | Config | Project metadata & deps (40 lines) | `dependencies = ["typer>=0.12", "rich>=13.0", "pydantic>=2.0", "pyyaml>=6.0.3"]` |
| `mise.toml` | Config | Task definitions (58 lines) | `[tasks.test]\nrun = "uv run pytest tests/ -v"` |
| `tests/conftest.py` | Test | `tmp_git_repo` fixture | `@pytest.fixture\ndef tmp_git_repo(tmp_path): subprocess.run(["git", "init"], cwd=tmp_path,…)` |

## Scope Sizing

| Metric | Value |
| :--- | :--- |
| Estimated Complexity | Medium |
| Files Likely Modified | 4-7 key files: `src/deviate/prompts/auto/judge.md`, `src/deviate/prompts/auto/green.md`, `src/deviate/cli/micro.py`, `src/deviate/core/validation.py`, `src/deviate/prompts/core/core.md`, `pyproject.toml` (new dep), `src/deviate/state/config.py` (optional) |
| New Modules Required | Potentially 1 new module: `src/deviate/core/treesitter.py` or `src/deviate/core/structural/` |
| New Persistence / Data Models | No |
| New External Integrations | No (tree-sitter is a Python package, not an external service) |
| Upstream / Cross-Cutting Concerns | Template assembly pipeline must be updated if adding AST-based checks to JUDGE phase prompt; TamperGuard interaction needs review if AST-based test-file analysis is added |
| Rationale | Tree-sitter integration is contained within the existing CLI architecture — no new infrastructure, databases, or services. It augments existing validation/analysis paths (JUDGE, REFACTOR, PLAN) rather than creating new phase types. The main work is prompt template updates + a new Python module + dependency addition. |

### Phase-by-Phase Integration Potential

| Phase | Layer | Integration Potential | Rationale |
| :--- | :--- | :--- | :--- |
| **JUDGE** | Micro | **High** — Replace YAML/heading-regex spec validation with structural AST comparison: parse the `git diff` output, extract function/class signatures, compare against spec-declared signatures | Tree-sitter `Query` system with named captures can match code patterns against spec requirements structurally |
| **REFACTOR** | Micro | **High** — Replace the basic `_check_return_type_mismatch` with full structural analysis: detect dead code, duplicated patterns, cyclomatic complexity, naming conventions | Tree-sitter's CST preserves formatting for round-trip-safe analysis diffs |
| **GREEN** | Micro | **Medium** — Augment prompts with structural constraints: agent prompt could include tree-sitter-extracted spec signatures to guide implementation | Prompt injection via `_build_auto_prompt` — more context-rich spec sections |
| **PLAN** | Meso | **Medium** — Structural codebase analysis for planning: count function/module complexity, detect violation patterns before implementation begins | Pre-scan current codebase state with tree-sitter queries to inform plan |
| **TASKS** | Meso | **Low-Medium** — Validate that task decomposition covers all structural elements from spec | Primarily a planning aid, less integration value than JUDGE/REFACTOR |
| **RED** | Micro | **Low** — RED phase writes tests, not production code; structural analysis of tests is less valuable | Tests are already verified by pytest failure |
| **MACRO** (explore/research/prd/shard) | Macro | **Low** — Macro layer produces spec documents, not code; tree-sitter cannot analyze markdown | No code to parse |
| **TamperGuard** | Micro | **Medium** — Structural analysis of GREEN-phase test modifications: detect unauthorized scope changes via diff structure | Currently file-hash based; AST diff would detect semantic tampering |
| **YELLOW** | Micro | **Medium** — If TamperGuard detects test tampering, YELLOW evaluates the amendment; tree-sitter could provide structural diff evidence | Amendment analysis with structural context |

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | ast-tree-sitter |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/ast-tree-sitter.md |
| NEXT_ACTION | Run `/deviate-adhoc` (Medium complexity) — the integration is contained within the existing CLI, no new persistence or external services needed. The `explore.md` is on disk and will be auto-consumed. |
