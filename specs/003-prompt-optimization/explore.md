# Explore: Prompt Optimization

<spec_version>0.1.0</spec_version>

---

## [PROBLEM_DEFINITION]

[Statement]: Investigate prompt optimization tools, techniques, and best practices (Promptfoo, LangSmith, Agenta, etc.) with the goal of codifying guidelines for DeviaTDD's prompt templates (currently 30+ prompt/skill files) and identifying token-efficiency opportunities.

[Scope]: Inventory of all prompt templates, skill files, prompt assembly code, and template variable patterns in the DeviaTDD repo (`src/deviate/prompts/`). Ecosystem research on Promptfoo, prompt evaluation frameworks, prefix caching economics, and structured-output best practices.

[Exclusions]: Architectural decisions, design recommendations, trade-off analysis, risk evaluation, data model changes, implementation code, test generation — all deferred to the `deviate-research` skill.

---

## [DISCOVERY_AUDIT_RESULTS]

### Manifest Files Observed

| Manifest Path | Description |
|:---|---|
| `pyproject.toml` | Project metadata: name `deviate`, version `0.1.0`, Python >=3.13, build system `hatchling` |
| `.mise.toml` | Task runner: defines `test`, `lint`, `check`, `fix`, `format`, `setup`, `clean`, `help` tasks |
| `.deviate/config.toml` | Runtime config: `profile = "default"`, `llm_backend = "opencode"`, `timeout_seconds = 300`, `agent_export_mode = "local"` |

### Verified Dependencies (from `pyproject.toml`)

```
dependencies = ["typer>=0.12", "rich>=13.0", "pydantic>=2.0", "pyyaml>=6.0.3"]
optional-dependencies = { dev = ["pytest>=8.0"] }
dependency-groups = { dev = ["pytest>=9.0.3", "ruff>=0.4"] }
```

- No prompt-specific dependencies declared (`promptfoo`, `langsmith`, `agenta`, etc. are absent from all manifest files)
- No template engine dependency (variable substitution is custom regex-based)

### Ghost Dependencies

- **Promptfoo**: Referenced in the user's problem statement as a target for evaluation integration. Not declared in `pyproject.toml`, no config files found, no references in codebase.
- **LangSmith / Agenta / HumanLoop**: Discussed in ecosystem research context. Not referenced in any code or config file.
- **Any test assertion library for prompts**: No `promptfoo` package, no `langsmith` SDK, no evaluation framework present.

### Test Runner Configuration

```
Test command: pytest tests/ -v (from pyproject.toml and constitution)
Lint command: ruff check . (from pyproject.toml and constitution)
E2E command: bats tests/e2e/ (from constitution)
```

Prompt-related test files:
- `tests/test_meso/test_prompt_assembly.py` — tests `load_template()`, `inject_constitution()`, `assemble_prompt()`
- `tests/test_meso/test_auto_prompt_templates.py` — tests template files exist, have content, have frontmatter/role headers, no placeholders in static templates
- `tests/test_core/test_skills.py` — tests skill discovery
- `tests/test_integration/test_skill_installation.py` — tests skill installation to agent directories

### No Manifest-Constitution Divergence

The constitution's `Tech Stack Standards` (Python 3.13, Typer, Rich, uv, pytest, ruff) match the observed manifests exactly.

---

## [CONSTITUTION_QUOTES]

Quoted verbatim from `specs/constitution.md`. No interpretation, classification, or scoring.

- **Architectural Principles**:
  ```
  - **Three-Layer Architecture**: Macro (feature scoping), Meso (issue engineering), Micro (TDD sandbox). Each layer has strict phase gates — no layer may be skipped.
  - **Append-Only Ledger Protocol**: All state transitions in `issues.jsonl` and `tasks.jsonl` are append-only.
  - **Git Isolation Principle**: Every task loop executes on a clean git branch or worktree.
  - **Tamper Guard & Micro-Sandboxing**: GREEN phase resets test directories to post-RED commit state.
  - **Human-in-the-Loop (HITL)**: Three mandatory gates (Design Approval, Contract Sign-Off, Final Merge Audit).
  - **Session Continuity**: Micro-layer tasks reuse a single LLM session across RED → GREEN → REFACTOR phases.
  - **Model Tiering**: V4 Flash for high-frequency phases; V4 Pro for compliance; Qwen 3.7+ for architecture.
  ```

- **Tech Stack Standards**:
  ```
  ### [2_1_BACKEND]
  - Python 3.13
  - Target: CLI application (`deviate`)
  - Framework: Typer (CLI entry points) with Rich for terminal I/O

  ### [2_5_TOOLING]
  - Package manager: `uv`
  - Test runner: `pytest`
  - Linter: `ruff` (lint + format)
  - E2E testing: `bats` (Bash automated test system)
  - Task runner: `mise` (see `mise.toml` for all tasks)
  - Code quality gate: `mise run check`
  ```

- **Testing Protocols**:
  ```
  ### [3_1_FRAMEWORK]
  - `TEST_FRAMEWORK`: pytest
  - `TEST_ROOT`: tests
  - `TEST_COMMAND`: pytest tests/ -v
  - `LINT_COMMAND`: ruff check .

  ### [3_2_COVERAGE]
  - Coverage target: >= 80%
  - RED phase tests must fail with `AssertionError` or `NotImplementedError`
  - GREEN phase must pass all tests; Tamper Guard resets unauthorized test edits
  - REFACTOR phase runs regression gate: tests must re-pass after polish
  ```

- **Definition of Done**:
  ```
  - [ ] Code implemented (satisfies acceptance criteria from `spec.md`)
  - [ ] Tests passing (pytest with clean exit code 0)
  - [ ] Lint passing (ruff check with no violations)
  - [ ] Judge phase passed (git diff validated against `spec.md` invariants)
  - [ ] E2E tests passing (if applicable; bats for CLI integration)
  - [ ] Documentation updated
  - [ ] No governance violations
  - [ ] Committed with conventional message format
  ```

---

## [ARCHITECTURAL_BASELINES]

### Existing Architectural Patterns

**Two-tier prompt architecture**: "auto" (slim) templates for macro/meso automated pipeline phases, "skill" (full) templates for micro-layer TDD phases.

**Auto templates** (`src/deviate/prompts/auto/*.md` — 11 files):
- Opening `<system_instructions>` XML tag with `## [ROLE_DEFINITION]`
- `CRITICAL INSTRUCTION INVARIANTS` — numbered behavioral rules
- `<traceability_mandates>` — output verification requirements
- `<execution_sequence>` — step-by-step execution instructions
- `## <context>` or `## Context` marker where runtime data gets injected
- No template variables in static templates (verified by tests); variables injected via `assemble_prompt()` context dict at runtime

**Skill templates** (`src/deviate/prompts/skills/<name>/SKILL.md` — 19 files):
- YAML frontmatter (name, description, category, version, aliases)
- `<system_instructions>` XML tag
- Role definition and `CRITICAL INSTRUCTION INVARIANTS`
- Single `$ARGUMENTS` placeholder replaced with JSON task context at runtime

**Governance/seed templates** (`src/deviate/prompts/governance/*.md`, `src/deviate/prompts/constitution_seed.md`):
- `## DeviaTDD Orchestration Rules` section header
- `${VARIABLE}` placeholders resolved by project file scanning during `deviate init`

### Prompt Loading Architecture

Three loading mechanisms:

1. **Macro/Meso layers** (`cli/macro.py`, `cli/meso.py` → `prompts/assembly.py`):
   - `_build_slim_prompt(phase, contract)` calls `assemble_prompt()`:
     1. `load_template(template_name)` — reads `auto/{name}.md` via `importlib.resources.files("deviate.prompts.auto")`
     2. `inject_constitution(template, constitution_path, claude_path)` — prepends `specs/constitution.md` then `CLAUDE.md` content
     3. Regex substitution for `${var}`, `$var`, `{var}` patterns from `context` dict

2. **Micro layer** (`cli/micro.py`):
   - `_load_skill_content(phase_name)` — reads `deviate-{phase}/SKILL.md` via `importlib.resources.files("deviate.prompts.skills")`
   - `_build_agent_prompt(skill_content, ...)` — replaces `$ARGUMENTS` with JSON-serialized task context

3. **Init/governance** (`cli/__init__.py`):
   - `_resolve_seed(content)` — resolves `${VARIABLE}` placeholders from `pyproject.toml` metadata

### Model Routing

Model-per-phase mapping (declared in constitution, not enforced in code):
| Model | Phases | Layer |
|---|---|---|
| DeepSeek V4 Flash | `/explore`, RED, GREEN, REFACTOR | High-volume code tasks |
| DeepSeek V4 Pro | JUDGE, YELLOW | Compliance/security |
| Qwen 3.7+ [Thinking] | `/research`, `/prd`, `/shard`, `/adhoc` | Architecture |

Backend selection: `AgentConfig.backend` (default `"opencode"`), configurable via `.deviate/config.toml` `llm_backend`.

### Template Variable Patterns

Three distinct substitution mechanisms coexist:

1. **`${VAR}` / `$VAR` / `{VAR}`** (in `assembly.py`): Regex `r"\$\{(.+?)\}|\$(\w+)|{(.+?)}"`, matched against `context: dict[str, str]`. Used in macro/meso phases.

2. **`$ARGUMENTS`** (in skill templates): Simple `str.replace("$ARGUMENTS", task_context)`. Task context is `{"phase", "task_id", "issue_id", "description", "execution_mode", "repo_root"}`.

3. **`${VARIABLE}`** (in `constitution_seed.md`): Regex `r"\$\{(\w+)\}"`, resolved from `pyproject.toml` metadata for project name, description, version, repo root.

### Prompt Token Sizes

**Auto templates (11 files): 1,191–2,324 tokens each** (~17,350 total)
| File | Est. Tokens |
|---|---|
| `red.md` | 2,324 |
| `green.md` | 2,219 |
| `yellow.md` | 1,735 |
| `explore.md` | 1,684 |
| `judge.md` | 1,616 |
| `research.md` | 1,539 |
| `tasks.md` | 1,499 |
| `refactor.md` | 1,464 |
| `prd.md` | 1,377 |
| `shard.md` | 1,282 |
| `specify.md` | 1,191 |

**Skill templates (19 files): 1,427–6,832 tokens each** (~53,700 total)
| File | Est. Tokens |
|---|---|
| `deviate-research` | 6,832 |
| `deviate-explore` | 5,013 |
| `deviate-tasks` | 4,361 |
| `deviate-shard` | 3,942 |
| `deviate-prd` | 3,321 |
| `deviate-execute` | 3,179 |
| `deviate-red` | 2,704 |
| `deviate-green` | 2,645 |
| `deviate-prune` | 2,532 |
| `deviate-adhoc` | 2,268 |
| `deviate-specify` | 2,203 |
| `deviate-e2e` | 2,032 |
| `deviate-constitution` | 2,024 |
| `deviate-refactor` | 1,897 |
| `deviate-hotfix` | 1,746 |
| `deviate-yellow` | 1,639 |
| `deviate-triage` | 1,482 |
| `deviate-pr` | 1,465 |
| `deviate-judge` | 1,427 |

**Other: 443–1,228 tokens**
| File | Est. Tokens |
|---|---|
| `constitution_seed.md` | 1,228 |
| `claudemd_seed.md` | 1,106 |
| `agents_seed.md` | 853 |
| `assembly.py` | 443 |

**Total: ~77,500 tokens across 33 prompt files**

---

## [ECOSYSTEM_RESEARCH]

### Promptfoo — Prompt Evaluation Framework

**Source**: https://promptfoo.dev/docs/intro

CLI-first open-source prompt evaluation tool (22.2k GitHub stars). Enables test-driven LLM development with declarative YAML config, multi-provider support, automated scoring, and CI/CD integration. Recently acquired by OpenAI.

```
promptfoo is an open-source CLI and library for evaluating and red-teaming LLM apps.
With promptfoo, you can: Build reliable prompts, models, and RAGs with benchmarks
specific to your use-case; Secure your apps with automated red teaming and pentesting;
Speed up evaluations with caching, concurrency, and live reloading;
Score outputs automatically by defining metrics; Use as a CLI, library, or in CI/CD.
```

**Python provider integration**: Custom Python providers via `call_api(prompt, options, context)` function. Reference: `id: 'file://echo_provider.py'`.

```
# echo_provider.py
def call_api(prompt, options, context):
    config = options.get('config', {})
    prefix = config.get('prefix', 'Tell me about: ')
    return {"output": f"{prefix}{prompt}"}
```

**Config structure**:
```yaml
prompts:
  - file://prompt1.txt
  - file://prompt2.txt
providers:
  - openai:gpt-5-mini
  - vertex:gemini-2.0-flash-exp
defaultTest:
  assert:
    - type: llm-rubric
      value: does not describe self as an AI, model, or chatbot
tests:
  - vars:
      language: French
      input: Hello world
    assert:
      - type: contains-json
      - type: javascript
        value: output.toLowerCase().includes('bonjour')
```

**Assertion types**: Deterministic (`contains-json`, `javascript`, `python`) + model-assisted (`llm-rubric`, `factuality`, `g-eval`, `similar`, `classifier`). Python assertions return `{"pass": bool, "score": float, "reason": str}`.

**CI/CD integration**: Official `promptfoo/promptfoo-action@v1` GitHub Action. Path-filtered to `prompts/**` changes. Posts comparison results as PR comments.

```yaml
- name: Run promptfoo evaluation
  uses: promptfoo/promptfoo-action@v1
  with:
    openai-api-key: ${{ secrets.OPENAI_API_KEY }}
    prompts: 'prompts/**/*.json'
    config: 'prompts/promptfooconfig.yaml'
```

**Caching**: Disk-based, 14-day default TTL. Cache keys include provider ID + prompt digest + config. Configured via env vars (`PROMPTFOO_CACHE_ENABLED`, `PROMPTFOO_CACHE_TYPE`, `PROMPTFOO_CACHE_TTL`).

**Nunjucks template syntax**: Supports loops, conditionals, variable composition in prompt templates.

### Other Prompt Optimization Tools

| Tool | Description | Key Feature |
|---|---|---|
| **LangSmith** | Framework-agnostic LLM evaluation platform by LangChain | Dataset versioning, offline/online eval, human feedback collection |
| **Agenta** | Open-source LLMOps platform (4.2k stars) | Python-native, 20+ pre-built evaluators, branching + environments for prompt versioning |
| **W&B Prompts** | Prompt playground within Weights & Biases MLOps platform | Integrated with experiment tracking |
| **HumanLoop** | Enterprise prompt management | HITL workflows, governance, approval gates |

### Prefix Caching Economics

**DeepSeek** (the models used by DeviaTDD):
| Model | Cache Hit / MTok | Cache Miss / MTok | Discount |
|---|---|---|---|
| deepseek-v4-flash | $0.0028 | $0.14 | **50x** |
| deepseek-v4-pro | $0.003625 | $0.435 | **120x** |

Caching is automatic, disk-based, enabled by default. Cache hit matching requires **exact full match** of prefix segments.

**Anthropic** (Claude models):
| Model | Cache Read / MTok | Base Input / MTok | Discount |
|---|---|---|---|
| Claude Opus 4.8 | $0.50 | $5.00 | **90%** |
| Claude Sonnet 4.6 | $0.15 | $1.50 | **90%** |

Batch processing adds 50% discount on top of caching discounts. Cache write costs: 1.25x (5-min TTL) or 2x (1-hour TTL).

### Prompt Engineering Best Practices

**Prefix-cache friendly structure** (from Anthropic docs):
> "Place static content (tool definitions, system instructions, context, examples) at the beginning of your prompt. Mark the end of the reusable content for caching using the cache_control parameter."

**Structured outputs** (from Anthropic docs):
> Native JSON Schema-constrained output via `output_config.format.type: "json_schema"`. Combined with `strict: true` on tool definitions, this guarantees schema-valid output via grammar-constrained sampling.

**Template versioning** (from Agenta / LangSmith / Promptfoo ecosystems):
- Agenta: branching and environments for prompt versioning
- LangSmith: dataset versioning with taggable milestones
- Promptfoo: CSV/Google Sheets test loading, matrix A/B testing across prompt variants

---

## [FILE_REGISTRY]

| Path (Strictly Relative to Repo Root) | Type | Purpose | Verbatim Snippet (≤10 lines) |
|---|---|---|---|
| `src/deviate/prompts/assembly.py` | Codebase_File | Core prompt assembly engine — loads, injects constitution, substitutes variables | `def load_template(template_name: str) -> str:\n    package_dir = resources.files("deviate.prompts.auto")\n    template_path = package_dir / f"{template_name}.md"\n    if not template_path.is_file():\n        raise FileNotFoundError(\n            f"Template '{template_name}' not found at {template_path}"\n        )\n    return template_path.read_text(encoding="utf-8")` |
| `src/deviate/prompts/auto/__init__.py` | Codebase_File | Package marker | `from __future__ import annotations` |
| `src/deviate/prompts/auto/explore.md` | Prompt_Template | Macro: codebase exploration (V4 Flash) | `<system_instructions>\n\n## [ROLE_DEFINITION]\n\nYou are an **EXPLORATION_CONTEXT_SCANNER** operating inside the **DeviaTDD MACRO LAYER / PHASE_EXPLORE**` |
| `src/deviate/prompts/auto/research.md` | Prompt_Template | Macro: architectural analysis (Qwen 3.7+) | `<system_instructions>\n\n## [ROLE_DEFINITION]\n\nYou are a **SYSTEMS_ARCHITECT** operating inside the **DeviaTDD MACRO LAYER / PHASE_RESEARCH**` |
| `src/deviate/prompts/auto/prd.md` | Prompt_Template | Macro: PRD compilation (Qwen 3.7+) | `<system_instructions>\n\n## [ROLE_DEFINITION]\n\nYou are a **PRODUCT_REQUIREMENTS_COMPILER** operating inside the **DeviaTDD MACRO LAYER / PHASE_PRD**` |
| `src/deviate/prompts/auto/shard.md` | Prompt_Template | Macro: issue sharding (Qwen 3.7+) | `<system_instructions>\n\n## [ROLE_DEFINITION]\n\nYou are a **FEATURE_VERTICAL_SHARDER** operating inside the **DeviaTDD MACRO LAYER / PHASE_SHARD**` |
| `src/deviate/prompts/auto/specify.md` | Prompt_Template | Meso: functional spec writing | `<system_instructions>\n\n## [ROLE_DEFINITION]\n\nYou are a **SPECIFICATION_ENGINE** operating inside the **DeviaTDD MESO LAYER / PHASE_SPECIFY**` |
| `src/deviate/prompts/auto/tasks.md` | Prompt_Template | Meso: task decomposition | `<system_instructions>\n\n## [ROLE_DEFINITION]\n\nYou are a **TASK_DECOMPOSITION_ENGINE** operating inside the **DeviaTDD MESO LAYER / PHASE_TASKS**` |
| `src/deviate/prompts/auto/red.md` | Prompt_Template | Micro RED: test-writing (V4 Flash) | `<system_instructions>\n\n## [ROLE_DEFINITION]\n\nThis engine operates exclusively as an automated, context-isolated test-driven development execution runtime` |
| `src/deviate/prompts/auto/green.md` | Prompt_Template | Micro GREEN: implementation (V4 Flash) | `<system_instructions>\n\n## [ROLE_DEFINITION]\n\nThis system operates exclusively as an automated, context-isolated test-driven development (TDD) execution runtime` |
| `src/deviate/prompts/auto/refactor.md` | Prompt_Template | Micro REFACTOR: code cleanup (V4 Flash) | `<system_instructions>\n\n## [ROLE_DEFINITION]\n\nYou are a **Senior Refactoring Engineer** operating inside the **DeviaTDD REFACTOR phase**` |
| `src/deviate/prompts/auto/yellow.md` | Prompt_Template | Micro YELLOW: test amendment (V4 Pro) | `<system_instructions>\n\n## [ROLE_DEFINITION]\n\nYou are a **Test Amendment Evaluator** operating inside the **DeviaTDD YELLOW phase**` |
| `src/deviate/prompts/auto/judge.md` | Prompt_Template | Micro JUDGE: compliance gate (V4 Pro) | `<system_instructions>\n\n## [ROLE_DEFINITION]\n\nYou are a **Compliance Judge** operating inside the **DeviaTDD JUDGE phase**` |
| `src/deviate/prompts/constitution_seed.md` | Seed_Template | Boilerplate constitution with `${VARIABLE}` placeholders | `# Project Constitution\n\n[CONSTITUTION_VERSION]: 0.1.0\n\n---\n\n## [1_ARCHITECTURAL_PRINCIPLES]` |
| `src/deviate/prompts/governance/claudemd_seed.md` | Governance_Template | CLAUDE.md orchestration rules | `## DeviaTDD Orchestration Rules\n\n### Three-Layer Architecture\n- **Macro Layer** — Feature scoping` |
| `src/deviate/prompts/governance/agents_seed.md` | Governance_Template | AGENTS.md orchestration rules | `## DeviaTDD Orchestration Rules\n\n### Three-Layer Architecture\n- **Macro Layer** — Feature scoping` |
| `src/deviate/prompts/skills/deviate-explore/SKILL.md` | Skill_Template | Full explore (5,013 tokens) | `---\nname: deviate-explore\ndescription: Pure exploration only. Deterministic, factual structural scan` |
| `src/deviate/prompts/skills/deviate-research/SKILL.md` | Skill_Template | Full research (6,832 tokens) | `---\nname: deviate-research\ndescription: Architectural analysis of the feature scope` |
| `src/deviate/prompts/skills/deviate-prd/SKILL.md` | Skill_Template | Full PRD (3,321 tokens) | `---\nname: deviate-prd\ndescription: Compile exploration results into a Product Requirements Document` |
| `src/deviate/prompts/skills/deviate-shard/SKILL.md` | Skill_Template | Full shard (3,942 tokens) | `---\nname: deviate-shard\ndescription: Decompose a Product Requirements Document` |
| `src/deviate/prompts/skills/deviate-specify/SKILL.md` | Skill_Template | Full spec (2,203 tokens) | `---\nname: deviate-specify\ndescription: Write a functional specification contract` |
| `src/deviate/prompts/skills/deviate-tasks/SKILL.md` | Skill_Template | Full tasks (4,361 tokens) | `---\nname: deviate-tasks\ndescription: Decompose spec.md into a granular task decomposition` |
| `src/deviate/prompts/skills/deviate-triage/SKILL.md` | Skill_Template | Workflow routing (1,482 tokens) | `---\nname: deviate-triage\ndescription: Classify development requirements against fixed decision predicates` |
| `src/deviate/prompts/skills/deviate-red/SKILL.md` | Skill_Template | Full RED (2,704 tokens) | `---\nname: deviate-red\ndescription: Use when executing the RED (test-writing) phase of TDD` |
| `src/deviate/prompts/skills/deviate-green/SKILL.md` | Skill_Template | Full GREEN (2,645 tokens) | `---\nname: deviate-green\ndescription: Use when executing the GREEN (implementation) phase of TDD` |
| `src/deviate/prompts/skills/deviate-refactor/SKILL.md` | Skill_Template | Full REFACTOR (1,897 tokens) | `---\nname: deviate-refactor\ndescription: Use when executing the REFACTOR (code cleanup) phase of TDD` |
| `src/deviate/prompts/skills/deviate-yellow/SKILL.md` | Skill_Template | Full YELLOW (1,639 tokens) | `---\nname: deviate-yellow\ndescription: Use when executing the YELLOW (conditional test amendment) phase` |
| `src/deviate/prompts/skills/deviate-judge/SKILL.md` | Skill_Template | Full JUDGE (1,427 tokens) | `---\nname: deviate-judge\ndescription: Use when executing the JUDGE (compliance gate) phase of TDD` |
| `src/deviate/prompts/skills/deviate-execute/SKILL.md` | Skill_Template | Direct execute (3,179 tokens) | `---\nname: deviate-execute\ndescription: Use when executing a single task directly (without TDD cycle)` |
| `src/deviate/prompts/skills/deviate-hotfix/SKILL.md` | Skill_Template | Hotfix workflow (1,746 tokens) | `---\nname: deviate-hotfix\ndescription: Use when decomposing bug reports into autonomous R-G-R hotfix units` |
| `src/deviate/prompts/skills/deviate-e2e/SKILL.md` | Skill_Template | E2E verification (2,032 tokens) | `---\nname: deviate-e2e\ndescription: Use when executing the E2E (end-to-end verification) phase after ALL tasks complete` |
| `src/deviate/prompts/skills/deviate-prune/SKILL.md` | Skill_Template | Test pruning (2,532 tokens) | `---\nname: deviate-prune\ndescription: Use when executing the PRUNE (test optimization) phase of TDD` |
| `src/deviate/prompts/skills/deviate-constitution/SKILL.md` | Skill_Template | Constitution gen (2,024 tokens) | `---\nname: deviate-constitution\ndescription: Governance artifact generation` |
| `src/deviate/prompts/skills/deviate-adhoc/SKILL.md` | Skill_Template | Ad-hoc issue gen (2,268 tokens) | `---\nname: deviate-adhoc\ndescription: Generate a single ad-hoc vertical-slice issue` |
| `src/deviate/prompts/skills/deviate-pr/SKILL.md` | Skill_Template | PR creation (1,465 tokens) | `---\nname: deviate-pr\ndescription: Create a pull request from the current worktree branch` |
| `src/deviate/cli/micro.py` | Codebase_File | Micro layer: loads skill content, builds agent prompts | `def _load_skill_content(phase_name: str) -> str | None:\n    skill_name = _SKILL_NAMES.get(phase_name.upper())\n    if not skill_name:\n        return None\n    try:\n        path = importlib.resources.files("deviate.prompts.skills").joinpath(\n            skill_name, "SKILL.md"\n        )\n        return path.read_text(encoding="utf-8")` |
| `src/deviate/cli/micro.py` | Codebase_File | Builds agent prompt with $ARGUMENTS substitution | `def _build_agent_prompt(skill_content: str, phase: str, task: dict, root: Path) -> str:\n    task_context = json.dumps(\n        {\n            "phase": phase,\n            "task_id": task.get("id", ""),\n            "issue_id": task.get("issue_id", ""),\n            "description": task.get("description", ""),\n            "execution_mode": task.get("execution_mode", "TDD"),\n            "repo_root": str(root.resolve()),\n        },\n        indent=2,\n    )\n    return skill_content.replace("$ARGUMENTS", task_context)` |
| `src/deviate/cli/macro.py` | Codebase_File | Macro layer: builds slim prompts via assemble_prompt() | `def _build_slim_prompt(phase: str, contract: dict[str, str]) -> str:\n    repo_root = Path.cwd()\n    constitution_path = repo_root / "specs" / "constitution.md"\n    claude_path = repo_root / "CLAUDE.md"\n    return assemble_prompt(\n        template_name=phase,\n        context=contract,\n        constitution_path=constitution_path,\n        claude_path=claude_path,\n    )` |
| `src/deviate/cli/__init__.py` | Codebase_File | Init command: resolves constitution seed `${VARIABLE}` placeholders | `return re.sub(r"\$\{(\w+)\}", _resolve_placeholder_match, content)` |
| `src/deviate/core/agent.py` | Codebase_File | AgentBackend.invoke() — sends assembled prompt to agent | `proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)` |
| `tests/test_meso/test_prompt_assembly.py` | Test_File | Tests load_template, inject_constitution, assemble_prompt | `def test_load_template_success(self): ...` |
| `tests/test_meso/test_auto_prompt_templates.py` | Test_File | Tests template existence, content, frontmatter, no placeholders | `def test_all_six_template_files_exist(self): ...` |
| `tests/test_core/test_skills.py` | Test_File | Tests skill discovery | `def test_discover_skills_lists_directories(self): ...` |
| `tests/test_integration/test_skill_installation.py` | Test_File | Tests skill installation to agent directories | `def test_init_installs_skills_to_agent_dirs(self): ...` |
| `specs/constitution.md` | Config | Project constitution — architectural, tech stack, testing rules | (quoted in full in CONSTITUTION_QUOTES above) |
| `pyproject.toml` | Manifest | Project metadata and dependency declarations | `name = "deviate"\nversion = "0.1.0"\ndescription = "DeviaTDD CLI — agent orchestration framework"\nrequires-python = ">=3.13"\ndependencies = ["typer>=0.12", "rich>=13.0", "pydantic>=2.0", "pyyaml>=6.0.3"]` |

---

## [STATUS_SUMMARY]

| Metric | Value |
|---|---|
| STATUS | SUCCESS |
| FEATURE_SLUG | `prompt-optimization` |
| GIT_BRANCH | `main` |
| SPEC_TARGET | `specs/003-prompt-optimization/explore.md` |
| EPIC_ID | `prompt-optimization` |
| PROMPT_FILES_CATALOGUED | 33 (11 auto + 19 skills + 3 seed/governance) |
| TOTAL_ESTIMATED_TOKENS | ~77,500 |
| EVALUATION_FRAMEWORK_PRESENT | No (Promptfoo, LangSmith, Agenta all absent) |
| NEXT_ACTION | Run the `deviate-research` skill |
