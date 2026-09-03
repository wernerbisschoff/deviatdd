## Plan Summary
- **Issue**: ISS-ADH-034 — Make deviate setup interactive for backend and command packs, and tidy production config.toml
- **Implementation Strategy**: Add a code-owned command-pack map and `--packs` / TTY prompt to `deviate setup`, serialize `config.toml` through an allowlist (truthful `profile`, libref only with `--libref`, backend-specific `[agent]` keys), and let `deviate micro run` read that profile when `--profile` is omitted.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 4-6 hours

## Product Layer Anchors
- **Flow References**: []
- **Source**: `specs/adhoc/issues/034-setup-interactive-config.md` (frontmatter field: `flow_refs`)
- **Release Context**: Enable meso and micro phases to drive Pi or OMP through RPC and stream live progress into a compact TUI.
- **Architecture Components Touched**: C1

## Acceptance Contract

**Scenario AC-PLAN-001: Resolve backend and optional packs from flags or TTY**
- **Source Outline**: `AO-034-01`
- **Upstream Traceability**: `US-034-01`, `FR-ADHOC-034`, `AC-ADHOC-034-01`
- **Current-Code Evidence**: `src/deviate/cli/__init__.py:setup`
- **Given**: Setup accepts `--agent` and a new `--packs` flag, and already prompts for an agent when `--agent` is omitted on a TTY.
- **When**: The operator omits `--packs` on a TTY, or passes `--packs none`, `--packs pr,review`, or `--packs all-optional`.
- **Then**: Default packs install; optional packs install only when named; unknown pack or agent names fail closed; non-interactive sessions without `--packs` install default packs only.
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Install default layer packs and skip optional commands**
- **Source Outline**: `AO-034-02`
- **Upstream Traceability**: `US-034-02`, `FR-ADHOC-034`, `AC-ADHOC-034-02`
- **Current-Code Evidence**: `src/deviate/core/commands.py:discover_commands`
- **Given**: `discover_commands` currently returns every packaged `deviate-*.md` stem and setup installs all of them plus `deviatdd`.
- **When**: Setup runs with default packs (no optional selection).
- **Then**: Product, macro, meso, and micro commands plus the `deviatdd` skill are written, and optional files (`deviate-pr`, `deviate-merge`, `deviate-review`, `deviate-walkthrough`, `deviate-html`, `deviate-hotfix`, `deviate-triage`, `deviate-prune`, `deviate-e2e`) are absent.
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Add only selected optional packs**
- **Source Outline**: `AO-034-02`
- **Upstream Traceability**: `US-034-02`, `FR-ADHOC-034`, `AC-ADHOC-034-02`
- **Current-Code Evidence**: `src/deviate/cli/__init__.py:_install_commands_to_agents`
- **Given**: Pack membership is a code-owned map by layer intent, so `deviate-red` is default micro even though its frontmatter `category` says macro.
- **When**: Setup runs with `--packs pr,review`.
- **Then**: `deviate-pr` and `deviate-review` are installed on top of the default set, and other optional commands stay absent.
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Persist a real micro profile and honor it at run time**
- **Source Outline**: `AO-034-03`
- **Upstream Traceability**: `US-034-03`, `FR-ADHOC-034`, `AC-ADHOC-034-03`
- **Current-Code Evidence**: `src/deviate/state/config.py:DeviateConfig`
- **Given**: `DeviateConfig.profile` currently defaults to `"default"` and `resolve_profile` rejects that string, while `deviate micro run --profile` hard-codes `"full"`.
- **When**: Setup writes a fresh config and `deviate micro run` is invoked without `--profile`.
- **Then**: The file contains `profile = "full"` (never `"default"`), plus `base_branch` and `claim_remote`, and the runner uses the config profile, coercing missing or legacy `"default"` to `"full"`.
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Write backend-correct agent keys**
- **Source Outline**: `AO-034-03`
- **Upstream Traceability**: `US-034-03`, `FR-ADHOC-034`, `AC-ADHOC-034-03`
- **Current-Code Evidence**: `src/deviate/cli/__init__.py:_write_agent_block_to_config`
- **Given**: Fresh `DeviateConfig.model_dump` currently emits `pi_rpc` and `transport` for every backend.
- **When**: Setup runs with `--agent claude` or `--agent pi`, or switches an existing pi config to `--agent codex`.
- **Then**: Non-pi/omp dumps contain `backend` and `timeout` and omit `pi_rpc` and `transport`; pi/omp may write `transport` and do not write `pi_rpc`; switching to Codex strips leftover Pi keys.
- **Verification Mode**: automated

**Scenario AC-PLAN-006: Omit every libref mention without --libref**
- **Source Outline**: `AO-034-04`
- **Upstream Traceability**: `US-034-04`, `FR-ADHOC-034`, `AC-ADHOC-034-04`
- **Current-Code Evidence**: `src/deviate/cli/__init__.py:_apply_governance`
- **Given**: Setup currently PATH-detects `libref`, always writes `use_libref`, always upserts `libref_seed.md`, and `core.md` invariant 7 is composed into every installed command.
- **When**: Setup runs without `--libref`, including when `libref` is on PATH.
- **Then**: Generated `config.toml`, upserted governance files, and installed command/skill bodies contain no `use_libref` key and no `libref` substring.
- **Verification Mode**: automated

**Scenario AC-PLAN-007: Opt in libref only with --libref**
- **Source Outline**: `AO-034-04`
- **Upstream Traceability**: `US-034-04`, `FR-ADHOC-034`, `AC-ADHOC-034-04`
- **Current-Code Evidence**: `src/deviate/prompts/core/core.md`
- **Given**: `--libref` is the only opt-in switch after PATH auto-detect is removed.
- **When**: Setup runs with `--libref`.
- **Then**: `config.toml` contains `use_libref = true` and the libref governance seed or compose overlay is present.
- **Verification Mode**: automated

**Scenario AC-PLAN-008: Keep Codex Luna and high reasoning if empty**
- **Source Outline**: `AO-034-05`
- **Upstream Traceability**: `US-034-05`, `FR-ADHOC-034`, `AC-ADHOC-034-05`
- **Current-Code Evidence**: `src/deviate/cli/__init__.py:_apply_codex_setup_defaults`
- **Given**: Codex setup already seeds `[models].default = gpt-5.6-luna` and `[agent].reasoning_effort = high` when those keys are empty.
- **When**: Setup `--agent codex` runs on a fresh config, a config with custom `models.default` and `reasoning_effort`, or a non-Codex backend.
- **Then**: Empty keys are seeded, user-set values survive, and non-Codex setup writes neither Luna nor `reasoning_effort`.
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/core/commands.py**: Own the pack map and filter discovered stems.
  - **Current State**: `discover_commands` returns every `*.md` stem with no pack filter.
  - **Changes Required**: Add default/optional pack membership and a filter used by install. Fail a unit test when a packaged stem is unclassified.
  - **Integration Surface**: `_install_commands_to_agents`; `_install_codex_command_skills`; `tests/unit/test_core/test_commands.py`.
- **src/deviate/cli/__init__.py**: Interactive packs, allowlist TOML, libref gate, agent-key filter.
  - **Current State**: Agent prompt exists; all commands install; `model_dump` writes every field; libref is PATH-detected and always seeded.
  - **Changes Required**: Add `--packs` and `_prompt_pack_selection`. Serialize via an allowlist. Gate libref on `--libref` only. Strip dead Pi keys for non-pi/omp backends. Keep Codex if-empty upserts.
  - **Integration Surface**: `DeviateConfig`; `compose_command_body`; `tests/unit/test_cli/test_setup.py`.
- **src/deviate/state/config.py**: Make `profile` a real execution profile.
  - **Current State**: `profile: str = "default"`. Unused `ProfileConfig` already types `full`/`fast`/`secure`.
  - **Changes Required**: Type `profile` as `Literal["full","fast","secure"] = "full"`. Keep `use_libref` in-memory; do not require it on disk.
  - **Integration Surface**: `_scaffold_dotfiles`; `tests/unit/test_state/test_config.py`.
- **src/deviate/cli/micro.py**: Read config profile when `--profile` is omitted.
  - **Current State**: Typer default is `"full"` and never reads `DeviateConfig.profile`.
  - **Changes Required**: Resolve implicit profile from config, coercing missing/`default`/invalid to `"full"`. Explicit `--profile` still wins.
  - **Integration Surface**: `resolve_profile`; `tests/unit/test_cli/test_micro.py`.
- **src/deviate/prompts/core/core.md**: Remove always-on libref mandate from the composed core.
  - **Current State**: Invariant 7 mandates `libref` in every installed command.
  - **Changes Required**: Move the mandate to a compose overlay used only when `--libref` is set.
  - **Integration Surface**: `compose_command_body`; `deviate.prompts.assembly.load_template` if it injects the same core.
- **tests/unit/test_cli/test_setup.py**: Pin packs, libref-absent, agent-block keys, Codex no-clobber.
  - **Current State**: Pins per-agent isolation and Codex Luna/reasoning. Codex tests assert every discovered command skill.
  - **Changes Required**: Assert default-vs-optional packs; libref-absent; backend-specific `[agent]` keys; update Codex assertions to the selected pack set.
  - **Integration Surface**: `CliRunner` + temp `chdir`.
- **CHANGELOG.md**: Record the user-visible setup and config change under `[Unreleased]`.
  - **Current State**: Unreleased section exists for other work.
  - **Changes Required**: Add default-pack, profile, libref, and `[agent]` tidy notes.
  - **Integration Surface**: constitution §5 Definition of Done.

## Implementation Strategy
- **Phase 1**: Pack map and setup filter
  - **Files**: `src/deviate/core/commands.py`, `src/deviate/cli/__init__.py`, `tests/unit/test_core/test_commands.py`, `tests/unit/test_cli/test_setup.py`
  - **Approach**: Encode default and optional packs. Filter `discover_commands` results before install. Add `--packs` and a Rich prompt whose default is `none`.
  - **Verification**: Default setup has `deviate-red` and lacks `deviate-pr`; `--packs pr` adds `deviate-pr`.
- **Phase 2**: Allowlist config + profile + agent keys
  - **Files**: `src/deviate/state/config.py`, `src/deviate/cli/__init__.py`, `src/deviate/cli/micro.py`, `tests/unit/test_state/test_config.py`, `tests/unit/test_cli/test_setup.py`
  - **Approach**: Change `profile` default to `full`. Allowlist-serialize TOML. Filter `[agent]` keys by backend. Wire micro run implicit profile.
  - **Verification**: Fresh config has `profile = "full"` and no `pi_rpc` for Claude; pi may have `transport`; micro coerce test passes.
- **Phase 3**: Libref opt-in and Codex keep
  - **Files**: `src/deviate/cli/__init__.py`, `src/deviate/prompts/core/core.md`, compose/assembly, `CHANGELOG.md`
  - **Approach**: Drop PATH auto-enable. Gate seed and overlay on `--libref`. Keep `_apply_codex_setup_defaults`.
  - **Verification**: No `--libref` dump has no `libref` substring; `--libref` writes the key; existing Codex no-clobber tests pass.

## Data Flow Analysis
Setup reads flags and optional TTY answers into `PackSelection`, `LibrefOptIn`, and a backend name. The allowlist serializer writes `.deviate/config.toml`. Install walks selected command stems and the `deviatdd` skill. `compose_command_body` prepends `core.md` and, only when opted in, the libref overlay. `deviate micro run` reads `profile` from that TOML when the CLI flag is implicit, then calls `resolve_profile`.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Existing Codex tests assert every packaged command skill | High | High | Update those tests to the selected pack set; keep Luna/reasoning no-clobber tests |
| `DeviateConfig.profile == "default"` tests fail | Medium | High | Update `tests/unit/test_state/test_config.py`; coerce legacy values on read |
| New command stem is unclassified | Medium | Medium | Unit test that every `discover_commands()` stem is classified |
| Libref leftover in composed `core.md` | High | Medium | Overlay gate plus substring asserts on installed bodies |
| FLOW_CONTEXT_UNAVAILABLE — no existing flow mapping is available | Medium | Low | Preserve empty flow references and plan the requested setup behavior without creating flow work |

## Security Profile

Risk surfaces: file paths (setup writes agent command/skill trees and `.deviate/config.toml`); subprocess (unchanged agent spawn).
Negative tests: unknown `--packs` / `--agent` fail closed; `--libref` omitted never writes a libref token even if `libref` is on PATH; non-pi/omp configs never persist `pi_rpc` or `transport`.
Constraints: no new prompt library; no new runtime dependency; do not clobber user `[models]` or `reasoning_effort`; do not reopen ISS-ADH-030 ACs.

## Integration Points
- **`discover_commands` → setup install**: pack filter sits between discovery and `install_command`.
- **`DeviateConfig` → `_dict_to_toml`**: allowlist replaces full `model_dump` for generated files.
- **`resolve_profile` → `deviate micro run`**: config supplies the implicit `--profile` default.
- **ISS-ADH-030**: coordinates only; 030 stays BACKLOG.

## Constitutional Alignment
- **Architecture**: Four-layer default packs match §1 Product/Macro/Meso/Micro. C1 CLI is the only architecture component touched.
- **Testing**: pytest in `tests/`; every AC-PLAN scenario is automated.
- **Git Isolation**: Work proceeds on `feat/adhoc/034-setup-interactive-config` in the specify worktree.
- **Product Layer**: `flow_refs` stay `[]`; this slice does not author flows.
