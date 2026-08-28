# Implementation Tasks: `feat/adhoc/034-setup-interactive-config`

## Phase 1: Pack-filtered setup
**Goal**: Setup installs default layer packs only, plus optional packs the operator selects.

### Tasks

- TSK-034-01: Filter setup command install through a code-owned pack map
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/test_core/test_commands.py tests/test_cli/test_setup.py -q --tb=short -k "pack or Pack or default_layer or optional"`
  - **Estimated Time**: 75 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/core/commands.py`
    - `src/deviate/cli/__init__.py`
    - `tests/test_core/test_commands.py`
    - `tests/test_cli/test_setup.py`
  - **Rationale**: US-034-01 / `AC-PLAN-001` require `--packs` and a TTY optional-pack prompt. US-034-02 / `AC-PLAN-002` / `AC-PLAN-003` require default four-layer install plus selected optional packs. `discover_commands` currently returns every stem. Constitution §3: pytest under `tests/`.
  - **Details**:
    - **Red**: Add pack-map tests that every discovered stem is classified default or optional. Add setup tests: default install has `deviate-red` and `deviatdd` and lacks `deviate-pr`; `--packs pr,review` adds only those two; unknown `--packs` fails closed; `--packs none` is default-only.
    - **Green**: Add `DEFAULT_LAYER_PACKS` / `OPTIONAL_PACKS` and `commands_for_selection`. Thread `--packs` and a Rich prompt (default `none`) through `setup`. Filter `_install_commands_to_agents` and Codex skill install.
    - **Refactor**: Keep one map as the source of truth. Do not rewrite frontmatter `category` strings.
    - **Edge Cases**: Non-interactive without `--packs` installs defaults only. `deviate-red` is default micro despite `category: deviattd-macro-layer`.
    - **Acceptance**: Default vs optional files match the plan map. Unknown pack names fail closed.

---

## Phase 2: Production config allowlist
**Goal**: Generated `config.toml` has a real `profile`, backend-correct `[agent]` keys, and `micro run` honors the profile.

### Tasks

- TSK-034-02: Allowlist-serialize profile and backend-specific agent keys
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/test_state/test_config.py tests/test_cli/test_setup.py tests/test_core/test_profile.py -q --tb=short`
  - **Estimated Time**: 75 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/state/config.py`
    - `src/deviate/cli/__init__.py`
    - `src/deviate/cli/micro.py`
    - `tests/test_state/test_config.py`
    - `tests/test_cli/test_setup.py`
  - **Rationale**: US-034-03 / `AC-PLAN-004` require `profile = "full"` (never `"default"`) plus `base_branch` and `claim_remote`, and `micro run` without `--profile` reads that value. US-034-03 / `AC-PLAN-005` require non-pi/omp `[agent]` to omit `pi_rpc` and `transport`. US-034-05 / `AC-PLAN-008` keep Codex Luna/high if-empty.
  - **Details**:
    - **Red**: Assert `DeviateConfig().profile == "full"` and reject `"default"` as a write value. Assert Claude setup omits `pi_rpc`/`transport`; pi may write `transport` and not `pi_rpc`. Assert switching pi→codex strips leftover Pi keys. Assert implicit micro profile coerce of `"default"` to `full`.
    - **Green**: Type `profile` as `Literal["full","fast","secure"] = "full"`. Allowlist-serialize TOML. Rewrite `[agent]` with a backend allowlist. Resolve implicit `--profile` from config.
    - **Refactor**: Reuse existing Codex if-empty helpers. Do not dump `model_dump()` of unused keys.
    - **Edge Cases**: Legacy `profile = "default"` and a missing key coerce to `full`. User `timeout` survives a backend switch.
    - **Acceptance**: Fresh config is tidy. Codex no-clobber tests still pass.
  - **Dependency**: TSK-034-01

---

## Phase 3: Libref opt-in
**Goal**: Setup without `--libref` mentions libref nowhere; `--libref` opts in.

### Tasks

- TSK-034-03: Gate libref on --libref only
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/test_cli/test_setup.py tests/test_cli/test_init.py -q --tb=short`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/__init__.py`
    - `src/deviate/prompts/core/core.md`
    - `tests/test_cli/test_setup.py`
    - `tests/test_cli/test_init.py`
    - `CHANGELOG.md`
  - **Rationale**: US-034-04 / `AC-PLAN-006` / `AC-PLAN-007` require `--libref` as the only opt-in. PATH detection must not write the key or seed. Composed `core.md` must not leak libref into default installs. Constitution §5 requires `CHANGELOG.md` `[Unreleased]`.
  - **Details**:
    - **Red**: Setup without `--libref` (even with `libref` on PATH) has no `use_libref` key and no `libref` substring in config, CLAUDE.md/AGENTS.md, or installed command bodies. `--libref` writes `use_libref = true` and the governance seed.
    - **Green**: Drop PATH auto-enable. Gate `_apply_governance` seed on the flag. Remove always-on `core.md` invariant 7 (keep a compose overlay or seed-only path for `--libref`). Update init tests that assumed PATH detect / always-seed.
    - **Refactor**: One boolean `use_libref` flows from the flag into scaffold, governance, and compose.
    - **Edge Cases**: Existing `use_libref = false` is not re-written on a no-flag re-run. `--libref` on an existing file upserts the key.
    - **Acceptance**: No-`--libref` workspaces are libref-free. CHANGELOG `[Unreleased]` names packs, profile, libref, and `[agent]` tidy.
  - **Dependency**: TSK-034-02

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 pack map
2. Phase 2 config allowlist
3. Phase 3 libref + CHANGELOG

**Critical Dependency Chains**:
- TSK-034-01 must precede TSK-034-02
- TSK-034-02 must precede TSK-034-03

**Risk Hotspots**:
- Codex tests that assert every packaged command skill
- Init tests that assume PATH-detect libref and always-seeded governance
- `DeviateConfig.profile == "default"` assertions
