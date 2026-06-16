# Design: Prompt Optimization
<spec_version>0.1.0</spec_version>

---

## [PROBLEM_DEFINITION]

[Statement]: Investigate prompt optimization tools, techniques, and best practices (Promptfoo, LangSmith, Agenta, etc.) with the goal of codifying guidelines for DeviaTDD's prompt templates (currently 30+ prompt/skill files) and identifying token-efficiency opportunities.

[Scope]: Inventory of all prompt templates, skill files, prompt assembly code, and template variable patterns in the DeviaTDD repo (`src/deviate/prompts/`). Ecosystem research on Promptfoo, prompt evaluation frameworks, prefix caching economics, and structured-output best practices.

[Exclusions]: Implementation code, test generation — all deferred to the `specify + tasks + TDD` pipeline.

**Source**: explore.md §PROBLEM_DEFINITION (L7-13)

---

## [SYSTEM_TOPOLOGY_MAPPING]

### Modules to Add

| Module | Purpose |
|--------|---------|
| `src/deviate/prompts/cache_aware.py` | Three-segment prompt assembly; `assemble_cache_optimized_prompt()` |
| `src/deviate/prompts/shared/prefix.md` | Extracted shared static prefix (system_instructions + role + traceability) |
| `src/deviate/prompts/validator.py` | Four-check validation engine; token counter; stats CLI |

### Modules to Modify

| Module | Change |
|--------|--------|
| `src/deviate/prompts/assembly.py` | Adds `optimize_cache` parameter; delegates to cache_aware |
| `src/deviate/prompts/auto/*.md` (11 files) | References to shared prefix; context markers repositioned |
| `src/deviate/prompts/skills/*/SKILL.md` (19 files) | `$ARGUMENTS` moved to absolute tail |
| `src/deviate/cli/__init__.py` | Adds `prompt` subcommand group (check, stats) |
| `pyproject.toml` | Adds `tiktoken>=0.6` dependency |
| `specs/constitution.md` | Appends Prompt Engineering Standards appendix |

### Integration Seams

The cache layer is a drop-in enhancement to `assembly.py` — `assemble_prompt()` acquires an optional `optimize_cache: bool = True` parameter that delegates to the new module. The validator integrates into the existing `mise run check` pipeline as a new pytest marker `@pytest.mark.prompt_quality`, and into the EXPLORE→RESEARCH gate as an automated pre-flight check. No API surface changes to `src/deviate/cli/micro.py` or `src/deviate/cli/macro.py` — they continue calling the same `assemble_prompt()` and `_build_agent_prompt()` signatures.

**Source**: explore.md FILE_REGISTRY (L347-395), assembly.py (L53-62), macro.py (L298-344), micro.py (L121-133)

---

## [THE_PROBLEM_CONTRACT]

This epic delivers a **Dual-Layer Prompt Optimization System** that addresses two independent but complementary concerns:

**Layer 1 — Token Optimization (Prefix Caching Engine)**: Restructures the template assembly order to front-load static, cacheable content, achieving the 50x-120x cache discount documented in explore.md:317-318. Delivers:
- A shared static prefix extracted from duplicated prose across 11 auto templates (eliminating ~1,200 tokens of duplication)
- Three-segment prompt assembly: (1) immutable static preamble → (2) phase-specific procedural instructions → (3) volatile runtime context
- `$ARGUMENTS` repositioned to absolute tail in all 19 skill templates

**Layer 2 — Quality Validation (Prompt Validator)**: Enforces a formal Prompt Quality Rubric codified as a constitution appendix. Delivers:
- Structural integrity check — every template has `<system_instructions>`, `## [ROLE_DEFINITION]`, and closing execution sequence
- Variable completeness check — all `${VAR}` placeholders have matching keys
- Token budget compliance — per-model caps enforced via `tiktoken`
- Duplication audit — shared prose flagged for extraction into `prefix.md`
- `deviate prompt check` and `deviate prompt stats` CLI commands

**Source**: explore.md PROBLEM_DEFINITION (L7-13), ECOSYSTEM_RESEARCH (L238-343), ARCHITECTURAL_BASELINES (L124-234)

---

## [SCOPE_BOUNDARIES]

**In Scope**:
- Codification of prompt engineering standards as a constitution appendix
- Shared static prefix extraction from auto templates
- Three-segment cache-optimized prompt assembly in `cache_aware.py`
- Deterministic prompt quality validation (4 checks) in `validator.py`
- Token budget configuration per (scope, layer, model_tier)
- `deviate prompt check` and `deviate prompt stats` CLI commands
- Pytest plugin (`@pytest.mark.prompt_quality`) for CI integration
- `tiktoken>=0.6` as sole new dependency (pure Python)

**Out of Scope**:
- Promptfoo, LangSmith, Agenta, or any Node.js-based evaluation framework (rejected: constitutional violation — constitution.md:19-22 mandates Python-only)
- Live LLM-based prompt evaluation (scores computed via testing frameworks that call agents — too expensive for CI)
- Automatic prompt rewriting / LLM-driven optimization (future epic; current scope is deterministic guidelines + tooling)
- Model-tier enforcement in AgentBackend (pre-existing gap outside this epic — explore.md L165-174)
- Runtime agent prompt quality scoring during TDD phases (validator is a build-time CI gate)

**Source**: explore.md PROBLEM_DEFINITION (L7-13), ARCHITECTURAL_BASELINES (L128-164), ECOSYSTEM_RESEARCH (L240-301); constitution.md L19-22

---

## [PERFORMANCE_CONSTRAINTS]

| Constraint | Target | Source |
|-----------|--------|--------|
| `deviate prompt stats` CLI latency | ≤ 500ms for full 33-file scan | AGENTS.md performance gate L_max pattern |
| Token counting accuracy (tiktoken vs. actual) | Conservative over-estimate; ≤ 5% margin of error | explore.md L314-321 (DeepSeek pricing) |
| Cache hit ratio target (auto templates) | ≥ 0.85 (85% of prompt tokens are static/cacheable) | explore.md L316-318 (50x-120x discount) |
| Cache hit ratio target (skill templates) | ≥ 0.75 (75% of prompt tokens are static/cacheable, with $ARGUMENTS at tail) | explore.md L316-318 |
| Validator CI integration overhead | ≤ 2s (deterministic checks, no LLM calls) | constitution.md L92 (mise run check) |
| `assemble_cache_optimized_prompt()` overhead vs legacy | ≤ 10ms (in-memory string manipulation only) | assembly.py L53-62 baseline |
| Per-template token reduction (shared prefix extraction) | ≥ 1,200 tokens total across 11 auto templates | explore.md L188-234 (token size inventory) |

---

## [MULTI_TIERED_VERIFICATION_TARGETS]

### Tier 1 — Unit Tests (pytest, every commit)

| Target | Test Location | Source |
|--------|--------------|--------|
| `load_template()` and `assemble_prompt()` regression | `tests/test_meso/test_prompt_assembly.py` | explore.md L389 |
| Static template validation (existence, frontmatter, content) | `tests/test_meso/test_auto_prompt_templates.py` | explore.md L390 |
| Skill discovery and installation | `tests/test_core/test_skills.py`, `tests/test_integration/test_skill_installation.py` | explore.md L391-392 |
| Cache-optimized assembly produces functionally equivalent output to legacy | New: `tests/test_prompts/test_cache_aware.py` | design.md RECOMMENDED_ARCHITECTURE |
| Validator checks (structural, variable, token budget, duplication) | New: `tests/test_prompts/test_validator.py` | design.md RECOMMENDED_ARCHITECTURE |
| `deviate prompt check` and `deviate prompt stats` CLI commands | New: `tests/test_cli/test_prompt.py` | design.md RECOMMENDED_ARCHITECTURE |

### Tier 2 — Lint & Quality (ruff, every commit)

| Target | Command | Source |
|--------|---------|--------|
| Python lint | `ruff check .` | constitution.md L54 |
| Python formatting | `ruff format --check .` | constitution.md L42 |
| Prompt quality | `deviate prompt check` (pytest marker) | design.md RECOMMENDED_ARCHITECTURE |

### Tier 3 — Integration (bats, CI gate)

| Target | Command | Source |
|--------|---------|--------|
| Full CLI pipeline | `bats tests/e2e/` | constitution.md L56 |

---

## [ATDD_ACCEPTANCE_CRITERIA_LEDGER]

**Scenario 1: Prompt quality check passes on valid templates**
- **Given** all 33 prompt templates exist in `src/deviate/prompts/` with valid structure
- **When** `deviate prompt check` is invoked
- **Then** the command exits 0, reporting all 33 templates as structurally valid, variable-complete, and within token budgets

**Scenario 2: Prompt quality check fails on broken template**
- **Given** a template is missing the `## [ROLE_DEFINITION]` section
- **When** `deviate prompt check` is invoked
- **Then** the command exits non-zero, reporting the specific template and missing section

**Scenario 3: Token budget violation detected**
- **Given** a template exceeds its model-tier token budget
- **When** `deviate prompt check` is invoked
- **Then** the command exits non-zero, reporting the template name, actual token count, and budget cap

**Scenario 4: Prompt stats reports accurate token counts**
- **Given** all 33 prompt templates exist on disk
- **When** `deviate prompt stats` is invoked
- **Then** the output shows per-template token counts matching the expected ranges from explore.md:188-234 (within tiktoken margin of error)

**Scenario 5: Cache-optimized assembly produces functionally equivalent output**
- **Given** a valid template and context dict
- **When** `assemble_cache_optimized_prompt(template, context)` and legacy `assemble_prompt(template, context)` are both invoked
- **Then** both produce semantically equivalent output (same constitution injected, same variables substituted, same section ordering of functional content)

**Scenario 6: Shared prefix extraction reduces duplication**
- **Given** 11 auto templates with duplicated `<system_instructions>`, `<traceability_mandates>`, and `CRITICAL INSTRUCTION INVARIANTS` blocks
- **When** `shared/prefix.md` is created and auto templates reference it via `@include` markers
- **Then** each auto template's token count decreases by the size of the extracted blocks, and the validator confirms all structural sections remain present

**Scenario 7: Constitution appendix is validated**
- **Given** `specs/constitution.md` has the new Prompt Engineering Standards appendix
- **When** `deviate prompt check` is invoked
- **Then** every template is validated against the rubric in the appendix (structural integrity, variable completeness, token budget, duplication)
- **Source**: constitution.md §4_DEFINITION_OF_DONE (L64-72); explore.md PROBLEM_DEFINITION (L7-13)

---

## [RECOMMENDED_ARCHITECTURE]

### Executive Summary

The recommended architecture is a **Dual-Layer Prompt Optimization System** — a lightweight, Python-native framework that addresses both dimensions of the problem statement: **quality validation** (how to evaluate prompt quality) and **token cost reduction** (how to shrink and cache-align templates). The system operates entirely within the DeviaTDD three-layer architecture as a **cross-cutting infrastructure layer** that sits orthogonal to the macro/meso/micro stack, augmenting the existing prompt assembly pipeline rather than replacing it.

**Layer 1 — Token Optimization (Prefix Caching Engine):** Restructures the template assembly order in `src/deviate/prompts/assembly.py` (FILE_REGISTRY, explore.md:349) to front-load static, cacheable content before injecting runtime context. The current `inject_constitution()` function prepends constitution + CLAUDE.md — which is correct for caching — but the assembly pipeline then splices in variable runtime context at mid-prompt, fragmenting what would otherwise be a continuous cacheable prefix. The fix is a three-segment prompt structure: (1) immutable static preamble (constitution, CLAUDE.md, system_instructions, role definition, CRITICAL INSTRUCTION INVARIANTS) → (2) phase-specific procedural instructions → (3) volatile runtime context (task ID, diff blocks, issue metadata). Segment 1 achieves the 50x-120x cache discount documented in explore.md:317-318 because identical constitution + system instructions repeat across every invocation using the same model class.

A new `src/deviate/prompts/cache_aware.py` module manages this segmented assembly, introducing `assemble_cache_optimized_prompt(template_name, context, constitution_path, claude_path)` that partitions template content into cacheable vs. volatile zones. The shared static prefix across all auto templates (the `<system_instructions>`, `<traceability_mandates>`, and `<few_shot_examples>` blocks) is extracted into a single `src/deviate/prompts/shared/prefix.md` file, eliminating ~1,200 tokens of duplication across 11 auto templates. Skill templates similarly centralize their `$ARGUMENTS` substitution point to the absolute tail of the prompt, ensuring every preceding byte hits the prefix cache.

**Layer 2 — Quality Validation (Prompt Validator):** A new `src/deviate/prompts/validator.py` module enforces a formal **Prompt Quality Rubric** codified as a constitution appendix (Prompt Engineering Standards). The validator implements four deterministic checks, each runnable as a pytest plugin or as a standalone `deviate prompt check` CLI command: (a) **structural integrity** — every template has `<system_instructions>`, a `## [ROLE_DEFINITION]` section, and a closing execution sequence; (b) **variable completeness** — all `${VAR}` placeholders have matching keys in the assembly context dict; (c) **token budget compliance** — per-model token caps enforced via `tiktoken`; (d) **duplication audit** — shared prose across templates flagged for potential extraction into `prefix.md`. A companion `deviate prompt stats` CLI command reports per-template and aggregate token counts.

**Integration seams**: The cache layer is a drop-in enhancement to `assembly.py` — `assemble_prompt()` acquires an optional `optimize_cache: bool = True` parameter that delegates to the new module. The validator integrates into the existing `mise run check` pipeline as a new pytest marker `@pytest.mark.prompt_quality`, and into the EXPLORE→RESEARCH gate as an automated pre-flight check. No API surface changes to `src/deviate/cli/micro.py` or `src/deviate/cli/macro.py` — they continue calling the same `assemble_prompt()` and `_build_agent_prompt()` signatures.

This architecture is **Python-only** (Python 3.13, Typer, Rich — constitution.md:19-22), adds only one new pure-Python dependency (`tiktoken>=0.6`), integrates with the existing mise/pytest/ruff pipeline, and preserves all existing test fixtures and skill installation paths. It explicitly **rejects** Promptfoo, LangSmith, and Agenta as external dependencies (see REJECTED_OPTIONS).

### Rationale (Constitution-Anchored)

**Constitutional alignment**: The design respects ALL architectural principles (constitution.md:7-15). It is Python-only (constitution.md:19-22). It integrates into the Three-Layer Architecture as a cross-cutting infrastructure concern — prompt quality checks run at HITL Gate 1 and Gate 2. The Append-Only Ledger tracks prompt template version changes via git history (files are in the repo, not runtime-generated). Tamper Guard (constitution.md:12) extends to prompt templates: the validator detects unauthorized template modifications. Session Continuity (constitution.md:14) is preserved — the cache-optimized assembly produces identical functional output to the current pipeline.

**Token cost reduction anchoring**: The 50x-120x cache discount (explore.md:317-318) is only realized when identical prefixes repeat. By front-loading the shared static prefix and separating volatile context, every invocation of the same phase hits the cache. At current scale (~77,500 tokens, explore.md:234), the cost savings compound across all 33 template files.

**Quality evaluation anchoring**: No evaluation framework exists (explore.md:409 confirms Promptfoo/LangSmith/Agenta absent). The problem statement (explore.md:9) asks to "codify guidelines" — a Python-native validator with a constitution-backed rubric achieves this without external platform lock-in.

---

## [OPTIONS_MATRIX]

| Option | Complexity | Testability | Constitutional Alignment | Reversibility | Blast Radius | Verdict |
|--------|-----------|-------------|-------------------------|---------------|-------------|---------|
| **Dual-Layer Caching + Validation** | Medium | High — pytest for both layers, `tiktoken` for deterministic token counting, cache correctness via `assemble_prompt()` output comparison tests | Aligned — Python-only (single new pure-Python dep `tiktoken`), integrates into existing mise/pytest/ruff pipeline, augments (doesn't replace) assembly.py, adds constitution appendix | High — template modifications are git-revertable, `optimize_cache=False` flag restores legacy behavior, validator is a read-only module | ~35 files (33 templates + assembly.py + cache_aware + validator + shared/prefix.md + CLI + pyproject.toml + constitution) | **RECOMMENDED** |

**Single Option Dominance**: Only one option satisfies all constitutional, tech stack, and problem statement constraints simultaneously. See REJECTED_OPTIONS for alternatives considered and rejected.

---

## [REJECTED_OPTIONS]

- **Custom Evaluator Only (No Caching Restructuring)**: Satisfies constitutional constraints (Python-only, pytest-integrable) but addresses only "codify guidelines" and leaves "identifying token-efficiency opportunities" unanswered. The 50x-120x cache discount (explore.md:317-318) is entirely untapped. The validator module from this option is absorbed into the recommended architecture's Layer 2.

- **Prefix Caching Restructure Only (No Quality Validation)**: Reduces token costs but provides no mechanism to evaluate whether templates are *good*. The problem statement (explore.md:9) requires both dimensions. Without a validator, template quality drifts. The caching component from this option is absorbed into the recommended architecture's Layer 1.

- **Promptfoo Integration**: Rejected on three independent grounds: (1) Constitutional violation — Promptfoo is a Node.js/npm package (constitution.md:19-22 mandates Python-only). Adding a Node.js dependency chain is prohibited. (2) Overkill for problem scope — Promptfoo's LLM-rubric scoring, dataset versioning, and multi-provider A/B testing (explore.md:240-284) are designed for production LLM application evaluation, not static template validation. (3) Blast radius mismatch — requires YAML config per phase group, CI/CD GitHub Action integration, and environment variable management. Heavier than the entire existing `assembly.py` pipeline (62 lines).

---

## [DESIGN_TRADE_OFF_MATRIX]

| Decision | Trade-off | Why This Side |
|----------|-----------|---------------|
| Extract shared prefix into `shared/prefix.md` vs. keep duplication | Template readability decreases (one more file to trace) but token costs drop ~1,200 tokens/invocation and cache-hit probability increases | Cache economics dominate: the 50x-120x discount (explore.md:317-318) only triggers on identical prefix matches. Duplicated prose = cache misses. Readability mitigated by `@include` markers in templates pointing to `prefix.md`. |
| Add `tiktoken` as dependency vs. approximate token counting | Adds one new dependency (currently 4, explore.md:29) but replaces manual estimates with deterministic counts | Token budgeting is a **hard constraint** for model selection. Approximation errors compound at ~77,500 tokens scale. `tiktoken` is pure Python, zero system dependencies. |
| Three-segment assembly vs. simpler two-segment | Increases assembly complexity from 62 to ~120 lines | Two-segment (static + dynamic) fails because phase-specific procedural instructions differ between phases and must NOT share a cache key. Three-segment isolates the truly invariant prefix. |
| Validator as pytest plugin vs. standalone CLI | Pytest ties validation to test runner lifecycle; standalone CLI enables use outside test context | Both are provided. The pytest plugin integrates with `mise run check` (constitution.md:92). A thin CLI wrapper (`deviate prompt check`) re-exports the same validator. |
| Modify all 33 templates vs. assembly-layer-only transformation | Template modification = larger blast radius but achieves savings at source level | Assembly-layer regex cannot distinguish cacheable from volatile content without template structure hints. Modifying templates also standardizes the three distinct variable mechanisms (explore.md:180-184) in the same pass. |
| Scope: guidelines only vs. guidelines + tooling | Guidelines without tooling = no enforcement. Tooling without guidelines = framework without standards. | Both are needed: the constitution appendix codifies the standard; the validator enforces deterministically before HITL gates (constitution.md:13). |

---

## [CONTRARIAN_VIEWPOINTS]

**CV-1: The problem to solve is not token count, it's template duplication.** Each skill and auto template independently re-states "CRITICAL INSTRUCTION INVARIANTS" that mirror constitution.md. If these invariants were injected once as a shared prefix (as `inject_constitution()` already does for auto templates, assembly.py:21-42), the per-invocation token count would drop without an optimization framework. **Source**: explore.md L128-136, assembly.py L21-42.

**CV-2: The two-tier architecture is correct and should be preserved, not collapsed.** Auto templates serve as batch-assembled prompts where the CLI controls composition. Skill templates serve as agent-facing instruction documents with a single `$ARGUMENTS` injection point and YAML frontmatter. They serve different trust boundaries: auto templates are internal, skill templates are user-visible and installable to agent directories. Unifying them would violate session isolation. **Source**: explore.md L128-143, constitution.md §1 Session Continuity.

**CV-3: Promptfoo evaluation is misaligned with the ephemeral TDD lifecycle.** Promptfoo is designed for stable benchmarks with caching and reproducibility. DeviaTDD operates on ephemeral branches with task-level git isolation. Promptfoo's 14-day TTL caching would return stale scores across branches. **Source**: explore.md L240-301, constitution.md §1 Git Isolation Principle.

**CV-4: Variable substitution unification is a breaking change disguised as simplification.** The three substitution mechanisms (assembly.py regex, micro.py $ARGUMENTS replace, init.py VARIABLE resolution) have different error semantics and lifecycle boundaries. Unifying them would conflate CLI errors, task-execution errors, and init/bootstrap errors. **Source**: explore.md L176-184.

**CV-5: Model routing "enforcement" would create tight coupling to backend internals.** The AgentBackend dispatches to external binaries via subprocess. It cannot control which model variant those binaries select. Attempting to enforce model tiering would require parsing backend-specific config files and hardcoding model variant names — a maintenance nightmare. **Source**: explore.md L165-174, agent.py L234-244.

**CV-6: Token optimization without constitutional guardrail preservation is unsafe.** Any optimization that removes, shrinks, or reorders "CRITICAL INSTRUCTION INVARIANTS" risks breaking Tamper Guard (constitution.md:12). The optimizer must be constraint-aware: it may compress prose and examples but must never touch sandboxing instructions. **Source**: constitution.md §1 Tamper Guard & Micro-Sandboxing.

---

## [RISK_REGISTER]

| Risk ID | Risk | Likelihood | Impact | Mitigation | Owner | Source Anchor |
|---------|------|-----------|--------|------------|-------|---------------|
| RSK-001 | New Python dependency (`tiktoken`) increases supply chain surface | Medium | Medium | Pin exact version; audit dependency tree; tiktoken maintained by OpenAI, wide adoption | Architect | pyproject.toml L6-11; constitution.md L40 |
| RSK-002 | Token optimization inadvertently removes constitutional guardrails | Low | Critical | Git diff through JUDGE phase; add assertions that critical invariants exist in every template post-optimization | JUDGE phase | constitution.md L12; explore.md L130-135 |
| RSK-003 | tiktoken counts diverge from actual model tokenization | Low | Low — slight inaccuracy | Use cl100k_base as conservative over-estimate; document margin | Architect | explore.md L314-321 |
| RSK-004 | Three-segment assembly changes agent behavior | Medium | Medium | Output-comparison tests: both legacy and optimized must produce behaviorally equivalent prompts | Developer | assembly.py L53-62 |
| RSK-005 | Standards without enforced automation create process drift | High | Low — docs only | Add pytest-based validation tests for prompt invariants | Developer | explore.md L52-56 |
| RSK-006 | Shared prefix.md changes affect 11 auto templates simultaneously | Medium | Medium | Prefix.md changes trigger full auto template test suite | Developer | FILE_REGISTRY explore.md L347-395 |
| RSK-007 | Cache optimization couples independent phases | Low | Medium | Keep per-phase static prefixes independent; no shared blocks across model tiers | Architect | explore.md L312-320; constitution.md L14 |

---

## [CONSTITUTIONAL_ALIGNMENT_AUDIT]

| Constitutional Clause (Verbatim Quote) | Architectural Decision | Alignment | Notes |
|----------|----------------------|-----------|-------|
| "**Three-Layer Architecture**: Macro, Meso, Micro. Each layer has strict phase gates — no layer may be skipped." | Adding cross-cutting prompt optimization layer | Aligned (Tension, addressed) | Prompt optimization is cross-cutting infrastructure, orthogonal to the layer stack. It augments the assembly pipeline without adding layer phases. Quality checks run at HITL gates. |
| "**Append-Only Ledger Protocol**: All state transitions in issues.jsonl and tasks.jsonl are append-only." | Token/cache accounting | Aligned | In-memory/ephemeral caching only. No persistent cache store introduced. If persistent state needed, uses append-only JSONL. |
| "**Git Isolation Principle**: Every task loop executes on a clean git branch or worktree." | Per-template optimization | Aligned | Template changes go through same git-isolated TDD cycle. No cross-branch state leakage. |
| "**Tamper Guard & Micro-Sandboxing**: GREEN phase resets test directories. Micro-layer LLM is sandboxed." | Adding evaluation/optimization framework | Aligned | Validator and cache operate at assembly layer, not inside micro-sandbox. They modify src/**/*.py only — never tests/, specs/, or config. Guardrails explicitly preserved (see RSK-002). |
| "**Human-in-the-Loop (HITL)**: Three mandatory gates. No gate may be programmatically bypassed." | Prompt quality evaluation as pre-gate check | Aligned | Advisory signals before HITL gates. Do not replace or bypass any gate. |
| "**Session Continuity**: Micro-layer tasks reuse a single LLM session across RED → GREEN → REFACTOR." | Caching optimization with shared prefix state | Aligned | Cache operates at assembly layer, not inside LLM session. Same functional output. |
| "**Model Tiering**: V4 Flash for high-frequency; V4 Pro for compliance; Qwen 3.7+ for architecture." | Token budgets per model tier | Aligned (Tension, pre-existing) | Adds token budgets per tier (improves awareness). Pre-existing gap of not code-enforcing (explore.md L165-174) is outside this epic. |
| "**Python 3.13**, Framework: Typer, Package manager: uv." | All new modules Python, no external runtimes | Aligned | `tiktoken` is Python-only. Promptfoo, LangSmith, Agenta explicitly rejected. |
| "**No persistent database runtime** (all state in JSONL ledgers and TOML config)." | In-memory caching, validator output | Aligned | No new persistent database. Caching is in-memory. Validator output → pytest reports. |
| "Test command: `pytest tests/ -v`. Lint command: `ruff check .`." | Adding prompt evaluation test suite | Aligned | New checks use pytest markers. No new test command. Ruff sole linter. |
| "Coverage target: >= 80%" | Prompt quality orthogonal | Aligned | Coverage applies to production code (src/). Prompt quality is orthogonal. |

### Pre-Existing Condition: Model Tiering Not Code-Enforced

The constitution mandates specific model-tier assignments (constitution.md:15), but agent.py dispatches to external binaries without model variant awareness (explore.md L165-174). This is a **pre-existing gap** — not introduced or worsened by this architecture. The recommended approach mitigates by adding token budgets per model tier and documenting tier expectations in the constitution appendix.

### Rejected Option: Promptfoo-Related Violations

Gamma's audit identified constitutional violations for **Promptfoo adoption** (Node.js dependency, CI blocking gate, persistent cache). These violations are moot because the **recommended architecture explicitly rejects Promptfoo** (see REJECTED_OPTIONS). The Dual-Layer approach is Python-only with zero external platform dependencies beyond `tiktoken`.

---

## [SOURCE_REGISTRY]

| ID | Type | Source / Path | Relevance Note |
|----|------|---------------|----------------|
| SRC-001 | Codebase_File | `src/deviate/prompts/assembly.py` | Core prompt assembly engine — load, inject constitution, substitute variables |
| SRC-002 | Codebase_File | `src/deviate/cli/micro.py` | Micro-layer prompt loading and $ARGUMENTS substitution |
| SRC-003 | Codebase_File | `src/deviate/cli/macro.py` | Macro-layer slim prompt building |
| SRC-004 | Codebase_File | `src/deviate/core/agent.py` | AgentBackend.invoke() — sends assembled prompt to agent |
| SRC-005 | Prompt_Template | `src/deviate/prompts/auto/*.md` (11 files) | Auto (slim) templates for macro/meso phases |
| SRC-006 | Skill_Template | `src/deviate/prompts/skills/*/SKILL.md` (19 files) | Skill (full) templates for micro TDD phases |
| SRC-007 | Explore_MD | `specs/003-prompt-optimization/explore.md` | Authoritative empirical input — file registry, token sizes, ecosystem research |
| SRC-008 | Constitution | `specs/constitution.md` | Non-negotiable governance rules for all architectural decisions |
| SRC-009 | Ecosystem | Promptfoo docs (explore.md:240-327) | Prompt evaluation patterns referenced but not adopted |
| SRC-010 | Industry | DeepSeek prefix caching pricing (explore.md:314-321) | 50x-120x discount economics for cache optimization |
| SRC-011 | Test_File | `tests/test_meso/test_prompt_assembly.py` | Existing prompt assembly tests — baseline for regression |
| SRC-012 | Test_File | `tests/test_meso/test_auto_prompt_templates.py` | Existing template validation tests — extended by validator |

---

## [SYSTEM_STATUS_SUMMARY]

| Metric | Value |
|--------|-------|
| STATUS | AWAITING_HITL_GATE_1 |
| FEATURE_SLUG | 003-prompt-optimization |
| EPIC_ID | 003-prompt-optimization |
| GIT_BRANCH | main |
| SPEC_TARGET_DESIGN | specs/003-prompt-optimization/design.md |
| SPEC_TARGET_DATAMODEL | specs/003-prompt-optimization/data-model.md |
| NEXT_ACTION | Human reviews design.md + data-model.md, then invokes the `prd` skill |
