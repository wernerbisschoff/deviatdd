## Plan Summary
- **Issue**: ISS-ADH-006 — Offline Context Documentation System — Integrate `context` CLI into DeviaTDD Framework
- **Implementation Strategy**: Add `use_context: bool` to `DeviateConfig`, detect `context` binary on `$PATH` during `deviate init`, inject an `## Offline Context Documentation System` governance section into `claudemd_seed.md` and `agents_seed.md`, add a universal documentation mandate to `core.md`, and thread `context add`/`context query` instructions through the explore, adhoc, research, and plan skill prompts, plus the macro/meso/micro layer core skill files.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 3-4 hours

## Workstation Mapping
- **`src/deviate/state/config.py`**: Add `use_context: bool = False` field to `DeviateConfig`.
  - **Current State**: `DeviateConfig` has profile, agent, models, and export fields. No `use_context` flag. TOML serialization via `_dict_to_toml()` dumps all model fields.
  - **Changes Required**: Add `use_context: bool = Field(default=False)` to `DeviateConfig`. No validator needed — boolean default suffices with `_dict_to_toml` which already handles `bool` via `_serialize_value(key, value)`.
  - **Integration Surface**: Consumed by `cli/__init__.py:_scaffold_dotfiles()` and tests (round-trip through `model_dump()` → TOML → `model_validate()`).

- **`src/deviate/cli/__init__.py`**: Detect `context` binary during `init`, set `use_context = true` in config when found.
  - **Current State**: `_scaffold_dotfiles()` creates `DeviateConfig(agent_export_mode)` with defaults. No binary detection.
  - **Changes Required**: In `init()` (or `_scaffold_dotfiles()`), call `shutil.which("context")`. If found, pass `use_context=True` to `DeviateConfig`. The `_dict_to_toml` serializer handles boolean values correctly.
  - **Integration Surface**: Called during `deviate init`. The `use_context` value persists in `.deviate/config.toml`.

- **`src/deviate/prompts/governance/claudemd_seed.md`**: Add `## Offline Context Documentation System` section.
  - **Current State**: Contains `## DeviaTDD Orchestration Rules` with architecture, ledger, git isolation, model tiering, etc. No offline documentation mandate.
  - **Changes Required**: Append a new `## Offline Context Documentation System` section with three subsections: `context list` (discover available packages), `context query <library> <topic>` (primary lookup mechanism), `context add <source>` (register documentation). The section must mandate that ALL agents use `context query` as their primary documentation source, with web fetch as last resort.
  - **Integration Surface**: Read by `_apply_governance()` → `_upsert_governance_block()`. Rendered into CLEAUDE.md on init.

- **`src/deviate/prompts/governance/agents_seed.md`**: Add `## Offline Context Documentation System` section (same content as claudemd_seed.md).
  - **Current State**: Mirrors claudemd_seed.md content with `## DeviaTDD Orchestration Rules`. No context mandate.
  - **Changes Required**: Same section appended.
  - **Integration Surface**: Read by `_apply_governance()` for AGENTS.md.

- **`src/deviate/prompts/core/core.md`**: Add universal documentation section loaded by ALL phase prompts.
  - **Current State**: Contains `## DeviaTDD Universal Invariants` (automated execution, path normalization, source anchoring, output discipline, pointer convention, positive invariants) and `## KV Cache Preservation`. No documentation lookup guidance.
  - **Changes Required**: Add a section (e.g., `### Offline Documentation Lookup`) requiring agents to prefer `context query <library> <topic>` over web fetching. Keep it concise — 3-4 bullet points.
  - **Integration Surface**: Loaded by `assembly.py:assemble_prompt()` as `core.md` — injected into every phase prompt.

- **`src/deviate/prompts/skills/deviate-explore/SKILL.md`**: Add `context add <source>` step to the ecosystem subagent.
  - **Current State**: Ecosystem subagent performs web searches for best practices, common use cases, and standard tooling.
  - **Changes Required**: Add a step in the ecosystem researcher subagent to run `context add <source>` for detected dependency libraries (e.g., `context add <git-repo-url> --name <lib> --path docs --tag <semver>`). Place this before the web search step so local docs are indexed first.
  - **Integration Surface**: Used during `/explore` phase.

- **`src/deviate/prompts/skills/deviate-adhoc/SKILL.md`**: Add `context add <source>` step in lightweight discovery.
  - **Current State**: Lightweight discovery uses grep/glob to find files and modules. No documentation registration.
  - **Changes Required**: Add an instruction after file discovery to run `context add <source>` for libraries detected during the scan.
  - **Integration Surface**: Used during `/adhoc` phase.

- **`src/deviate/prompts/skills/deviate-research/SKILL.md`**: Add `context query` mandate for library-specific decisions.
  - **Current State**: Subagent Alpha (architectural options) and subagent Beta (data modeler) are instructed to rely primarily on `explore.md` and use web search as last resort. No `context query` step.
  - **Changes Required**: In the Token Efficiency & Context Primacy Rule section, add `context query <library> <topic>` as the preferred documentation lookup mechanism before web search. Also add a discovery step to run `context list` to see available packages.
  - **Integration Surface**: Used during `/research` phase.

- **`src/deviate/prompts/skills/deviate-plan/SKILL.md`**: Add `context query` step for localized codebase research.
  - **Current State**: Plan phase scans codebase with `git log`, reads issue ledger, reads workstation files. No documentation lookup.
  - **Changes Required**: Add a step in the codebase scan sequence to query `context` for framework conventions and library APIs detected in workstation files. For example, if `src/deviate/state/config.py` uses Pydantic, run `context query pydantic@2.13.4 "field types"`.
  - **Integration Surface**: Used during `/plan` phase.

- **`src/deviate/prompts/core/macro-skill.md`**: Add context consultation requirement.
  - **Current State**: Contains shared macro disciplines (feature bucket, constitutional gate, output mandate, pre/post lifecycle, HITL handoff, subagent delegation, zero implementation code). No documentation lookup.
  - **Changes Required**: Add a bullet point under shared disciplines requiring agents to use `context query` for library-specific decisions during macro phases.
  - **Integration Surface**: Loaded by all macro phase prompts.

- **`src/deviate/prompts/core/meso-skill.md`**: Add context consultation requirement.
  - **Current State**: Contains shared meso disciplines (worktree execution, spec loading, ledger state, post-script validation, branch discipline, zero speculative scope, deterministic discovery). No documentation lookup.
  - **Changes Required**: Add a bullet point under shared disciplines requiring agents to use `context query` for library APIs and framework conventions during meso phases.
  - **Integration Surface**: Loaded by all meso phase prompts.

- **`src/deviate/prompts/core/micro-skill.md`**: Add context consultation guidance.
  - **Current State**: Contains shared micro disciplines (R-G-R cycle, test-first, sociable tests, verification-is-done, git isolation, post-script protocol, handover manifest). No documentation lookup.
  - **Changes Required**: Add a bullet point under shared disciplines encouraging agents to use `context query` for API lookups during implementation phases.
  - **Integration Surface**: Loaded by all micro phase prompts.

- **`tests/test_state/test_config.py`**: Add tests for `use_context` field.
  - **Current State**: Tests exist for config defaults, round-trip serialization, extra field rejection.
  - **Changes Required**: Add `test_config_use_context_default` (defaults to `False`), `test_config_use_context_round_trip` (`use_context=True` survives serialize→deserialize).
  - **Integration Surface**: Verified via pytest.

- **`tests/test_cli/test_init.py`**: Add tests for context binary detection during init.
  - **Current State**: Tests exist for dotfile scaffolding, governance blocks, constitution provisioning.
  - **Changes Required**: Add `test_init_detects_context` (mock `shutil.which("context")` to return a path, verify config contains `use_context = true`), `test_init_missing_context` (mock `which` to return `None`, verify `use_context = false`), `test_init_context_governance_block` (verify CLAUDE.md/AGENTS.md contain `## Offline Context Documentation System` section).
  - **Integration Surface**: Verified via pytest with mocked `$PATH`.

## Implementation Strategy
- **Phase 1**: Config model — add `use_context` field to `DeviateConfig`
  - **Files**: `src/deviate/state/config.py`, `tests/test_state/test_config.py`
  - **Approach**: Add `use_context: bool = Field(default=False)` to `DeviateConfig`. Add two unit tests: default value and round-trip.
  - **Verification**: `pytest tests/test_state/test_config.py::test_config_use_context_default tests/test_state/test_config.py::test_config_use_context_round_trip -v`

- **Phase 2**: CLI detection — wire `which context` into `deviate init`
  - **Files**: `src/deviate/cli/__init__.py`, `tests/test_cli/test_init.py`
  - **Approach**: In `init()`, call `shutil.which("context")` after `_scaffold_dotfiles()`. If found, reload config, set `use_context=True`, write updated TOML. Add tests mocking `shutil.which` for found/not-found scenarios.
  - **Verification**: `pytest tests/test_cli/test_init.py::test_init_detects_context tests/test_cli/test_init.py::test_init_missing_context -v`

- **Phase 3**: Governance seeds — add context mandate section to claudemd_seed.md and agents_seed.md
  - **Files**: `src/deviate/prompts/governance/claudemd_seed.md`, `src/deviate/prompts/governance/agents_seed.md`, `tests/test_cli/test_init.py`
  - **Approach**: Append `## Offline Context Documentation System` section to both seed files with `context list`, `context query`, `context add` mandates. Add integration test verifying governance blocks contain the new section.
  - **Verification**: `pytest tests/test_cli/test_init.py::test_init_context_governance_block -v`

- **Phase 4**: Universal documentation mandate in core.md
  - **Files**: `src/deviate/prompts/core/core.md`
  - **Approach**: Add a concise `### Offline Documentation Lookup` subsection to core.md requiring all agents to prefer `context query` over web fetching.
  - **Verification**: Read output file; verify section exists. No test change needed.

- **Phase 5**: Skill prompt modifications — explore, adhoc, research, plan
  - **Files**: `src/deviate/prompts/skills/deviate-explore/SKILL.md`, `src/deviate/prompts/skills/deviate-adhoc/SKILL.md`, `src/deviate/prompts/skills/deviate-research/SKILL.md`, `src/deviate/prompts/skills/deviate-plan/SKILL.md`
  - **Approach**: Thread `context add` or `context query` instructions into each skill file at appropriate insertion points.
  - **Verification**: Read each output file; verify expected sections/references exist. No test change needed.

- **Phase 6**: Layer core skill modifications — macro-skill.md, meso-skill.md, micro-skill.md
  - **Files**: `src/deviate/prompts/core/macro-skill.md`, `src/deviate/prompts/core/meso-skill.md`, `src/deviate/prompts/core/micro-skill.md`
  - **Approach**: Add one bullet point each under shared disciplines referencing `context query` as the primary documentation mechanism.
  - **Verification**: Read each output file; verify bullet point present. No test change needed.

## Data Flow Analysis
1. **Init-time detection**: `deviate init` → `shutil.which("context")` → returns `str | None` → if str, `config.use_context = True` → `_dict_to_toml()` serializes `use_context = true` → written to `.deviate/config.toml`.
2. **Config persistence**: `.deviate/config.toml` → `tomllib.load()` → `DeviateConfig.model_validate()` → `use_context` available as `bool`. Future CLI behavior (sync, verify) can gate on this flag.
3. **Governance injection**: `_apply_governance()` reads `claudemd_seed.md` and `agents_seed.md` (updated with context mandate section) → `_upsert_governance_block()` writes to `CLAUDE.md` and `AGENTS.md` → agents at runtime read the governance blocks and use `context query` as primary documentation lookup.
4. **Prompt-time injection**: `assemble_prompt()` loads `core.md` (updated with context mandate) → injected into every agent prompt → agents see the context mandate at the top of every phase.
5. **Skill-time instructions**: Each skill's execution sequence references `context add <source>` (explore/adhoc) or `context query <library> <topic>` (research/plan) → agents execute these steps during their phases.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `shutil.which("context")` returns false positive (stale binary) | Low — if binary exists but is broken, agent catches subprocess error and falls back | Low | Simple `which` check is sufficient for init-time detection; runtime errors are handled by agent subprocess error handling |
| Governance seeds grow too long, diluting core DeviaTDD rules | Low — context section is a separate `##` header, easily scannable | Low | Keep section concise (3-4 bullet points + 1 example block). Reference existing patterns. |
| Skill prompt edits drift from actual skill behavior | Medium — prompts are static MD; agents follow instructions verbatim | Low | Each skill file is tested via its own execution path; prompt content is reviewed in JUDGE phase |
| Missing `core.md` context section results in agents ignoring context | Low — core.md is loaded by every phase; if absent, agents fall back to existing web-fetch behavior | Medium | core.md is always loaded; verify section exists after Phase 4 via manual read |
| `use_context` boolean unused after this issue | Low — reserved for future CLI-layer behavior; no harm in unused config field | Low | Field is documented in config; any future feature can gate on it |
| Concurrent init runs — `_write_if_missing` prevents overwrite, so `use_context` may be stale | Low — user must manually edit config.toml to update | Low | Documented edge case in issue spec; acceptable behavior |

## Integration Points
- **`shutil.which("context")`**: Standard library `shutil.which()` returns the path to the `context` binary or `None`. Called once during `deviate init`. No error expected for non-existent binary.
- **`_scaffold_dotfiles()` → `_dict_to_toml()`**: TOML serialization of `DeviateConfig`. The `use_context` boolean is handled by the existing `_serialize_value()` which maps `bool` → `"true"`/`"false"` (TOML-compliant lowercase).
- **`_apply_governance()` → `_upsert_governance_block()`**: Governance block injection into CLAUDE.md and AGENTS.md. The context mandate section is appended to the seed files; `_upsert_governance_block()` checks for the `## Offline Context Documentation System` header key for idempotency.
- **`assemble_prompt()` in `assembly.py`**: Loads `core.md` for every phase prompt. The new offline documentation section is automatically available to all agents.
- **Skill execution sequences**: Each skill's `<execution_sequence>` references `context` commands. These are static markdown — agents read and execute them during their phase.

## Constitutional Alignment
- **Architecture**: This issue adds a cross-cutting documentation infrastructure layer that spans all three DeviaTDD layers (macro, meso, micro). The `use_context` config boolean in `.deviate/config.toml` follows the same config-driven pattern established by `[models]` in ISS-ADH-005. Context mandate in governance seeds aligns with the constitutional principle that agents should prefer deterministic, local operations over network-dependent fallbacks.
- **Testing**: Unit tests for `use_context` default and round-trip (`tests/test_state/test_config.py`). Integration tests for init-time detection with mocked `$PATH` (`tests/test_cli/test_init.py`). All skill files are verified by reading the output — no automated test for prompt content (prompts are human-readable MD, not code).
- **Git Isolation**: No git state mutation. Config reads are read-only (TOML parsing). All changes are in source files or new test files, committed via standard TDD cycle.
||||||| parent of 55772e7 (docs(adhoc-006): create plan.md)
=======
- **Implementation Strategy**: Add a `use_context: bool` field to `DeviateConfig`, detect the `context` binary via `shutil.which()` during `deviate init`, and thread context-mandate documentation blocks through all governance seeds, core prompts, and skill prompts — no runtime checking required; prompts are static.
- **Estimated Complexity**: Low
- **Estimated Effort**: 1-2 hours

## Workstation Mapping
- **`src/deviate/state/config.py`**: Add `use_context: bool = False` field to `DeviateConfig`
  - **Current State**: `DeviateConfig` (line 98-106) has `profile`, `llm_backend`, `timeout_seconds`, `agent_export_mode`, `agent`, `models` — no `use_context` field. `model_config = {"extra": "forbid"}` is active.
  - **Changes Required**: Add `use_context: bool = Field(default=False)` to `DeviateConfig`. No validation logic needed — a simple boolean with default False.
  - **Integration Surface**: Consumed by `cli/__init__.py` for writing config during init and by future CLI-layer behavior for conditional `context sync`.

- **`src/deviate/cli/__init__.py`**: Detect `context` binary during init, set `use_context = true`, write governance blocks
  - **Current State**: `_scaffold_dotfiles` (line 225-236) creates `DeviateConfig` with hardcoded defaults and writes it via `_dict_to_toml` + `_write_if_missing`. No context detection exists. `_apply_governance` (line 257-270) writes CLAUDE.md/AGENTS.md from seed files. `_dict_to_toml` (line 65-91) already handles `bool` values via `_serialize_value` (line 54-62: `f"{key} = {'true' if value else 'false'}"`).
  - **Changes Required**: In `_scaffold_dotfiles`, use `shutil.which("context")` to detect the binary before constructing `DeviateConfig`. Pass `use_context=True` if found, `False` otherwise. The `_dict_to_toml` function already correctly serializes `True`/`False` to `true`/`false` in TOML (line 57-58: `f"{key} = {'true' if value else 'false'}"`). No other CLI logic changes needed — config write is already idempotent via `_write_if_missing`.
  - **Integration Surface**: `_dict_to_toml` function (line 65-91), `_write_if_missing` function (line 45-51), `DeviateConfig` model.

- **`src/deviate/prompts/governance/claudemd_seed.md`**: Add `## Offline Context Documentation System` section
  - **Current State**: 77 lines covering DeviaTDD Orchestration Rules — architecture, ledger protocol, git isolation, tamper guard, HITL gates, model tiering, session continuity, task execution, code quality, quick-start workflow. No context documentation section.
  - **Changes Required**: Append a `## Offline Context Documentation System` section with: mandate to use `context query` as primary docs mechanism, instructions to call `context list` to discover packages, `context add` for missing libraries, example queries, and note that `context` availability is best-effort (graceful fallback).
  - **Integration Surface**: Written unconditionally during `deviate init` via `_upsert_governance_block`. The `## DeviaTDD Orchestration Rules` section header (line 209 in `__init__.py`) handles create/append/update idempotency.

- **`src/deviate/prompts/governance/agents_seed.md`**: Add `## Offline Context Documentation System` section
  - **Current State**: 68 lines, mirrors `claudemd_seed.md` structure. No context documentation section.
  - **Changes Required**: Same content as `claudemd_seed.md` — append `## Offline Context Documentation System` section with identical mandate.
  - **Integration Surface**: Same idempotency mechanics as `claudemd_seed.md`.

- **`src/deviate/prompts/core/core.md`**: Add context documentation system section to universal invariants
  - **Current State**: 19 lines covering Universal Invariants and KV Cache Preservation. No context documentation mention.
  - **Changes Required**: Add a `## Offline Context Documentation System` section between `## KV Cache Preservation` and the end of the file. Content: mandate that agents use `context query <library@version> "<topic>"` as primary documentation lookup over web fetching.
  - **Integration Surface**: Loaded by ALL phase prompts (macro, meso, micro layers via `assemble_prompt` in `src/deviate/prompts/assembly.py`).

- **`src/deviate/prompts/skills/deviate-explore/SKILL.md`**: Add `context add <source>` discovery step
  - **Current State**: 252 lines. Discovery phase uses subagent_scanner_prompt with `Context Bounding Rules`. Unknown documentation source registration.
  - **Changes Required**: Add `context add <source>` step in the subagent discovery section: after identifying ecosystem dependencies, the subagent should register documentation sources.
  - **Integration Surface**: Subagent scanner prompt at line 29-60.

- **`src/deviate/prompts/skills/deviate-adhoc/SKILL.md`**: Add `context add <source>` for lightweight discovery
  - **Current State**: 193 lines. Lightweight Discovery Pass (step 3, line 42-47) uses grep/glob for codebase discovery. No documentation registration.
  - **Changes Required**: Add instruction to run `context add <source>` for detected frameworks after the Lightweight Discovery Pass identifies the dependency ecosystem.
  - **Integration Surface**: Execution sequence step 3 (Lightweight Discovery Pass) at line 42-47.

- **`src/deviate/prompts/skills/deviate-research/SKILL.md`**: Add `context query` mandate for architectural analysis
  - **Current State**: 365 lines. Subagent Alpha uses web search as last resort (line 45: "Token Efficiency" instructs web search tools as last resort only). Subagent Beta uses same pattern (line 59). No context query mention.
  - **Changes Required**: Replace all "web search" / "web fetch" last-resort references with `context query <library@version> "<topic>"` as the primary documentation mechanism. Web search remains only when `context` documentation is not installed.
  - **Integration Surface**: Subagent Alpha prompt (line 36-46) and Subagent Beta prompt (line 48-60).

- **`src/deviate/prompts/skills/deviate-plan/SKILL.md`**: Add `context query` mandate for codebase research
  - **Current State**: 154 lines. Execution sequence step 3 ("Current Codebase State Scan", line 49-55) lists deterministic local operations only. No context query mention.
  - **Changes Required**: Add instruction to use `context query` for understanding library APIs and framework conventions detected during codebase scan.
  - **Integration Surface**: Execution sequence step 3 (Current Codebase State Scan) at line 49-55.

- **`src/deviate/prompts/core/macro-skill.md`**: Add context consultation requirement
  - **Current State**: 24 lines covering shared macro disciplines. No context mention.
  - **Changes Required**: Add a discipline entry: "Context Documentation Mandate": agents MUST prefer `context query` over web fetching for library documentation lookups.
  - **Integration Surface**: Shared Macro Disciplines list at line 5-19.

- **`src/deviate/prompts/core/meso-skill.md`**: Add context consultation requirement
  - **Current State**: 29 lines covering shared meso disciplines. No context mention.
  - **Changes Required**: Add same discipline entry as macro-skill.md.
  - **Integration Surface**: Shared Meso Disciplines list at line 5-19.

- **`src/deviate/prompts/core/micro-skill.md`**: Add context consultation guidance
  - **Current State**: 25 lines covering shared micro disciplines. No context mention.
  - **Changes Required**: Add same discipline entry as macro/meso.
  - **Integration Surface**: Shared Micro Disciplines list at line 13-25.

## Implementation Strategy
- **Phase 1**: Config model — add `use_context` field to `DeviateConfig`
  - **Files**: `src/deviate/state/config.py`
  - **Approach**: Add `use_context: bool = Field(default=False)` to `DeviateConfig` at line 105 (before `model_config`). No validators needed.
  - **Verification**: `pytest tests/test_state/test_config.py::test_config_use_context_default -v` (new test), `pytest tests/test_state/test_config.py::test_config_use_context_round_trip -v` (new test), `pytest tests/test_state/test_config.py -v` (existing tests still pass)

- **Phase 2**: CLI init — detect `context` binary during `deviate init`
  - **Files**: `src/deviate/cli/__init__.py`
  - **Approach**: In `_scaffold_dotfiles`, before constructing `DeviateConfig`, call `shutil.which("context")`. If found, set `use_context = True`. Pass to `DeviateConfig(agent_export_mode=agent_export_mode, use_context=...)`. The `_dict_to_toml` function already handles bool serialization (line 57-58). `_write_if_missing` prevents overwrite on re-init.
  - **Verification**: `pytest tests/test_cli/test_init.py::test_init_detects_context -v` (new test with `context` on PATH), `pytest tests/test_cli/test_init.py::test_init_missing_context -v` (new test without `context`)

- **Phase 3**: Governance seeds — add `## Offline Context Documentation System` section
  - **Files**: `src/deviate/prompts/governance/claudemd_seed.md`, `src/deviate/prompts/governance/agents_seed.md`
  - **Approach**: Append identical `## Offline Context Documentation System` section to both files, after the Quick-Start Workflow section. Content: mandate to prefer `context query` over web fetching, `context list` to discover packages, `context add` for missing libraries, example queries, best-effort availability note.
  - **Verification**: `pytest tests/test_cli/test_init.py::test_init_context_governance_block -v` (new test verifying CLAUDE.md/AGENTS.md contain the section)

- **Phase 4**: Core prompt — add context documentation mandate to `core.md`
  - **Files**: `src/deviate/prompts/core/core.md`
  - **Approach**: Add `## Offline Context Documentation System` section between `## KV Cache Preservation` and end of file. Three bullet points: primary mechanism mandate, discovery (`context list`), registration (`context add`).
  - **Verification**: Manual inspection; this file has no corresponding unit test (prompt content is verified via integration test in Phase 5)

- **Phase 5**: Skill and layer prompts — thread context instructions
  - **Files**: 7 files (explore SKILL.md, adhoc SKILL.md, research SKILL.md, plan SKILL.md, macro-skill.md, meso-skill.md, micro-skill.md)
  - **Approach**:
    - explore SKILL.md: Add `context add <source>` step to subagent scanner after dependency identification
    - adhoc SKILL.md: Add `context add <source>` step after Lightweight Discovery Pass
    - research SKILL.md: Replace all "web search" / "web fetch" last-resort references with `context query` as primary mechanism
    - plan SKILL.md: Add `context query` instruction to step 3 (Current Codebase State Scan)
    - macro-skill.md: Add context documentation mandate as discipline entry #8
    - meso-skill.md: Add context documentation mandate as discipline entry #8
    - micro-skill.md: Add context documentation mandate as discipline entry #7
  - **Verification**: `pytest tests/test_integration/test_init_export_cycle.py -v` (existing integration test with context detection)

## Data Flow Analysis
1. **Init Time**: `deviate init` calls `_scaffold_dotfiles()` → `shutil.which("context")` resolves binary presence → `use_context: bool` set on `DeviateConfig` → `_dict_to_toml()` serializes as `use_context = true` or `use_context = false` → written to `.deviate/config.toml` via `_write_if_missing()` (atomic, idempotent — skips if file exists).
2. **Governance Writing**: `_apply_governance()` reads `claudemd_seed.md` and `agents_seed.md` from package resources → writes to `CLAUDE.md` and `AGENTS.md` via `_upsert_governance_block()` (idempotent — detects `## DeviaTDD Orchestration Rules` header, appends/updates accordingly).
3. **Prompt Assembly**: `assemble_prompt()` in `src/deviate/prompts/assembly.py` loads `core.md` prefix for all phase prompts → all agents see the `## Offline Context Documentation System` mandate regardless of config state.
4. **Agent Runtime**: Agents read the context mandate from assembled prompts → use `context query <lib> <topic>` as primary docs lookup → fall back to training data / web fetch if `context` unavailable or library not installed. No runtime config check — all prompts are static.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `shutil.which("context")` returns a broken binary | Low — detection only confirms PATH presence, not behavior | Low | Agents catch subprocess errors when `context query` fails and fall back gracefully. No pre-verification of binary health needed. |
| `_dict_to_toml` fails to serialize `use_context=True` | Medium — config.toml becomes malformed if bool not handled | Very Low | `_dict_to_toml` line 57-58 already has explicit `isinstance(value, bool)` check with correct `true`/`false` serialization. Verified by `_serialize_value` function. |
| Governance block idempotency conflict — `_upsert_governance_block` section header changed | Low — only the prompt seed changes, not the detection logic | Low | The `_upsert_governance_block` function at line 196-222 handles create/append/update via `## DeviaTDD Orchestration Rules` header regex. Adding new sections after Quick-Start Workflow doesn't affect the detection pattern. |
| Research skill loses web-fetch fallback entirely | Medium — agents can't resolve novel library questions without `context` docs | Low | Web-fetch remains as explicit last-resort fallback in research skill. The change reorders priority from `web-fetch → first` to `context query → first, web-fetch → last`. |
| Prompt files grow too large | Low — each addition is <10 lines | Low | All prompt additions are compact sections (5-10 lines each). Per spec, "no dynamic prompt injection based on config — all prompt files are static". |

## Integration Points
- **`DeviateConfig.use_context`**: The contract between config serialization and CLI init. Consumed by `_scaffold_dotfiles` → `_dict_to_toml`. Reserved for future CLI-layer behavior (conditional `context sync`). Not consumed at runtime by prompt assembly per defensive exclusions.
- **`shutil.which("context")`**: Standard library binary detection. Returns `str | None` — `None` means `context` not on PATH, `str` means found. Called once during init.
- **`_upsert_governance_block(target_path, seed_content)`**: Idempotent governance writer. Detects `## DeviaTDD Orchestration Rules` header (line 209). On first init (no target file): writes seed_content. On append (target exists, header missing): appends seed_content. On update (target exists, header found): regex-replaces the block.
- **`importlib.resources.files("deviate.prompts.governance")`**: Package resource access for seed files. Used by `_read_seed` (line 187-193) to read governance seeds and prompt files.
- **`_dict_to_toml(data: dict) -> str`**: TOML serializer at line 65-91. Already handles bool via `_serialize_value` (line 57-58). Already handles dict sub-sections via bracket `[key]` syntax (line 70-75).

## Constitutional Alignment
- **Architecture**: Aligns with `[2_5_TOOLING]` — adds `context` CLI as a documentation tool in the DeviaTDD framework. The `use_context` boolean in `DeviateConfig` follows the existing `[models]` config pattern established by ISS-ADH-005 (coordinates_with). No architectural layer violations — prompt changes are limited to existing files with no new modules or interfaces.
- **Testing**: Unit tests for `DeviateConfig` model round-trip with `use_context` field. Unit tests for `deviate init` with and without `context` on PATH (mocked via monkeypatched `shutil.which`). Unit test for governance block content. Integration test for full init → export cycle with context detection. Target coverage: all new lines covered.
- **Git Isolation**: No git state mutation in init (init writes files to the worktree but does not create branches or commits — the post-script handles commits). All changes are in source files or new test files, committed via standard TDD cycle.
