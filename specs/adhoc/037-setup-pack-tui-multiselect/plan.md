## Plan Summary
- **Issue**: ISS-ADH-037 — Replace setup optional-pack Prompt.ask with a TTY checkbox multi-select
- **Implementation Strategy**: Keep the Rich-only checkbox loop in `src/deviate/ui/checkbox.py` as the sole TTY picker, route omitted `--packs` through it in `src/deviate/cli/__init__.py`, and pin behavior with mocked-TUI tests plus a CHANGELOG entry.
- **Estimated Complexity**: Low
- **Estimated Effort**: 2-4 hours

## Acceptance Contract
**Scenario AC-PLAN-001: TTY empty confirm installs default layers only**
- **Source Outline**: `AO-037-01`
- **Upstream Traceability**: `US-037-01`, `FR-ADHOC-037`, `AC-ADHOC-037-01`
- **Current-Code Evidence**: `src/deviate/cli/__init__.py:_prompt_pack_selection`
- **Given**: Operator runs setup on a TTY with `--packs` omitted
- **When**: Operator confirms the checklist with nothing checked
- **Then**: Setup installs macro plus meso plus micro commands and no optional pack files
- **Verification Mode**: automated

**Scenario AC-PLAN-002: TTY product plus pr picks install those two packs only**
- **Source Outline**: `AO-037-01`
- **Upstream Traceability**: `US-037-01`, `FR-ADHOC-037`, `AC-ADHOC-037-01`
- **Current-Code Evidence**: `src/deviate/ui/checkbox.py:checkbox_select`
- **Given**: Operator runs setup on a TTY with `--packs` omitted
- **When**: Operator toggles `product` and `pr` with Space and confirms with Enter
- **Then**: Setup installs the product pack commands plus `deviate-pr` only and writes no pack selection into `config.toml`
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Comma-separated and all-optional flags keep current membership**
- **Source Outline**: `AO-037-02`
- **Upstream Traceability**: `US-037-02`, `FR-ADHOC-037`, `AC-ADHOC-037-02`
- **Current-Code Evidence**: `src/deviate/core/commands.py:parse_optional_packs`
- **Given**: Operator passes an explicit `--packs` value on any terminal
- **When**: Operator uses `pr,review`, `all-optional`, `none`, or an unknown name
- **Then**: Setup installs the named packs, every optional pack, default layers only, or fails closed on unknown names
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Non-TTY omitted packs installs default-only without prompting**
- **Source Outline**: `AO-037-02`
- **Upstream Traceability**: `US-037-02`, `FR-ADHOC-037`, `AC-ADHOC-037-02`
- **Current-Code Evidence**: `src/deviate/ui/render.py:is_interactive`
- **Given**: Operator runs setup without a TTY and omits `--packs`
- **When**: Setup resolves the optional pack set
- **Then**: Setup installs default layers only and never blocks on key input
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/ui/checkbox.py**: TTY checkbox loop (Space toggles, Enter confirms, arrows move)
  - **Current State**: Implemented and tested; Rich Live render with injectable `read_key` seam
  - **Changes Required**: None expected; adjust only if a defect surfaces during verification
  - **Integration Surface**: `checkbox_select` called by `src/deviate/cli/__init__.py:_ask_optional_pack_picks`
- **src/deviate/cli/__init__.py**: Setup pack resolution (`_optional_pack_rows`, `_packs_from_selector_picks`, `_ask_optional_pack_picks`, `_prompt_pack_selection`, `_resolve_setup_optional_packs`)
  - **Current State**: TTY path already routes through the checkbox; `Prompt.ask` remains only for agent, export-mode, and claim-remote prompts
  - **Changes Required**: None expected; keep `--packs` parsing and non-TTY default-only behavior unchanged
  - **Integration Surface**: `OPTIONAL_PACK_NAMES`, `parse_optional_packs`, `commands_for_packs`, `is_interactive`
- **tests/unit/test_cli/test_setup.py**: Setup pack tests including `TestSetupPacks`
  - **Current State**: Covers default-only, named packs, `all-optional`, `none`, unknown-name failure, TTY helper invocation, and no pack persistence
  - **Changes Required**: Add or adjust one mocked-TUI case pinning `product` plus `pr` picks install those two packs only
  - **Integration Surface**: `deviate.cli._ask_optional_pack_picks`, `deviate.cli._packs_from_selector_picks`
- **tests/unit/test_ui/test_checkbox.py**: Checkbox unit tests
  - **Current State**: Covers empty default, Space toggle, ESC not confirming, arrow keys, and the `read_key` loop
  - **Changes Required**: None expected; extend only if the loop contract changes
  - **Integration Surface**: `CheckboxSession.apply`, `checkbox_select`
- **CHANGELOG.md**: `[Unreleased]` entry for the TTY picker change
  - **Current State**: No entry for this issue yet
  - **Changes Required**: Append one bullet under `[Unreleased]`
  - **Integration Surface**: None

## Implementation Strategy
- **Phase 1**: Verify picker wiring and pin product plus pr coverage
  - **Files**: `src/deviate/cli/__init__.py`, `src/deviate/ui/checkbox.py`, `src/deviate/core/commands.py`, `tests/unit/test_cli/test_setup.py`, `tests/unit/test_ui/test_checkbox.py`, `CHANGELOG.md`
  - **Approach**: Run the existing pack and checkbox suites, confirm no slash-separated `Prompt.ask` remains on the pack path, add the `product` plus `pr` mocked-TUI case, and append the CHANGELOG bullet
  - **Verification**: Run `pytest tests/unit/test_cli/test_setup.py tests/unit/test_ui/test_checkbox.py -v` and confirm green

## Data Flow Analysis
- Input is `--packs` or TTY keystrokes. `--packs` parses via `parse_optional_picks` into pack names. Omitted `--packs` on a TTY opens `checkbox_select` over `_optional_pack_rows`, and `_packs_from_selector_picks` maps picks to pack names (`all-optional` expands to every pack). The name tuple feeds `commands_for_packs`, which sums default layer stems plus selected optional stems. Installers write command files to the agent tree. The selection never enters the `config.toml` payload.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Raw terminal mode leaves stdin altered on error | Medium | Low | Keep try-finally termios restore in `_read_key_posix` and covered tests |
| Leftover Enter from prior prompt confirms empty checklist | Medium | Low | Flush pending input before the loop and keep the drain test |
| New test asserts rendered glyphs or help strings | Low | Low | Mock `_ask_optional_pack_picks` and assert invocation plus installed files only |

## Security Profile
Risk surfaces: file paths (command install targets), terminal input (raw keystroke reads)
Negative tests: unknown `--packs` names fail closed; pack picks never persist into `config.toml`
Constraints: no new dependencies without checksum, no Textual, stay on Typer plus Rich, no hardcoded secrets

## Integration Points
- **`parse_optional_packs`**: `--packs` string contract (`none`, `all-optional`, comma-separated names, unknown fails closed)
- **`commands_for_packs`**: pack names to command stem list consumed by the agent installers
- **`is_interactive`**: TTY gate for all setup prompts including the pack checklist
- **Agent picker and `claim_remote` prompts**: keep Rich `Prompt.ask` there; this issue changes the pack picker only

## Constitutional Alignment
- **Architecture**: Meso PLAN authors the Gherkin contract for one adhoc issue; Tasks maps it and Micro RED encodes the user scenarios as failing tests (constitution §1 three-layer model)
- **Testing**: pytest via `tests/unit/test_cli/test_setup.py` and `tests/unit/test_ui/test_checkbox.py`; mocked-TUI assertions per the issue boundary, no glyph or help-string tests (constitution §3)
- **Git Isolation**: Work happens on the dedicated issue worktree and branch; commits occur at phase boundaries via the orchestrator (constitution §1, §4)
- **User Scenarios**: `AC-PLAN-001` and `AC-PLAN-002` encode `US-037-01` (TTY checklist picking); `AC-PLAN-003` and `AC-PLAN-004` encode `US-037-02` (script and non-TTY paths unchanged); RED turns these into failing-then-passing tests
