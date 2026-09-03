## Plan Summary
- **Issue**: ISS-ADH-036 — Make deviate --help and README phase-transparent
- **Implementation Strategy**: Keep existing help strings, add the missing `COVERAGE_INCOMPLETE` token to the README review row, pin `--review` and `fast` help wording with a small test, and append a CHANGELOG entry.
- **Estimated Complexity**: Low
- **Estimated Effort**: 1-2 hours

## Acceptance Contract
**Scenario AC-PLAN-001: README names every commit, spawn, and fail-closed fact**
- **Source Outline**: `AO-036-01`
- **Upstream Traceability**: `US-036-01`, `FR-ADHOC-036`, `AC-ADHOC-036-01`
- **Current-Code Evidence**: `README.md:_Phase transparency table_`
- **Given**: A coworker reads the README phase-transparency table
- **When**: The coworker asks which phases commit, spawn Codex, or fail closed
- **Then**: The table answers with RED `git commit --no-verify`, the Codex spawn argv, nested spawn in `meso run` / `micro run`, `pre`/`post` roles, fail-closed tokens, default versus optional packs, worktree versus `--no-setup --local`, and `claim_remote` default false
- **Verification Mode**: manual

**Scenario AC-PLAN-002: Micro run help separates fast skip from review pause**
- **Source Outline**: `AO-036-02`
- **Upstream Traceability**: `US-036-02`, `FR-ADHOC-036`, `AC-ADHOC-036-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:run_command`
- **Given**: A coworker runs `deviate micro run --help`
- **When**: The coworker reads the `--profile` and `--review` help lines
- **Then**: The output keeps the pinned `Execution profile: full, fast` substring, states `fast` skips JUDGE and REFACTOR, and states `--review` is a TTY pause before the phase commit and not `/deviate-review`
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Review and walkthrough rows match sibling language**
- **Source Outline**: `AO-036-03`
- **Upstream Traceability**: `US-036-03`, `FR-ADHOC-036`, `AC-ADHOC-036-03`
- **Current-Code Evidence**: `README.md:_review row_`
- **Given**: A coworker reads the README review and walkthrough rows
- **When**: The coworker compares them against the sibling review contract
- **Then**: The review row states comments-only default, not a merge gate, and names `COVERAGE_INCOMPLETE` as the `review pre` fail-closed token, the walkthrough row states the four-look map, PyPI 2.23.1 is not taught as current main, and sibling prompt bodies stay untouched
- **Verification Mode**: manual

## Workstation Mapping
- **README.md**: role in this issue — add the missing `COVERAGE_INCOMPLETE` token to the review row and verify the transparency table covers every fact the issue lists
  - **Current State**: Phase-transparency table already exists with setup, adhoc, meso, micro, review, and walkthrough rows
  - **Changes Required**: Name `COVERAGE_INCOMPLETE` as the `review pre` fail-closed token in the review row; no other rows change
  - **Integration Surface**: `tests/unit/test_cli/test_setup.py::TestReadmeNewUserPath` (Quickstart wording must keep passing)
- **src/deviate/cli/micro.py**: role in this issue — already carries the required `run_command` help strings; verify only
  - **Current State**: `--profile` help keeps `Execution profile: full, fast` and states `fast skips JUDGE and REFACTOR`; `--review` help states TTY pause and not `/deviate-review`; docstring names the RED `--no-verify` commit
  - **Changes Required**: None expected; change only if the new test finds a gap
  - **Integration Surface**: `tests/unit/test_core/test_profile.py::test_help_lists_only_full_and_fast`
- **tests/unit/test_cli/test_help.py**: role in this issue — pin the `--review` pause-versus-slash distinction and the `fast` skip wording in `--help` output
  - **Current State**: Pins panel names, panel membership, and first-timer wording; pins nothing about `--review` or `fast`
  - **Changes Required**: Add one small test that `deviate micro run --help` mentions the pause-versus-slash distinction for `--review` and that `fast` mentions skipping JUDGE
  - **Integration Surface**: Typer `CliRunner` against `deviate.cli:cli`
- **CHANGELOG.md**: role in this issue — record the user-visible docs change
  - **Current State**: `[Unreleased]` has no entry for this issue
  - **Changes Required**: Append one bullet under `[Unreleased]` in the same commit
  - **Integration Surface**: None

## Implementation Strategy
- **Phase 1**: Verify help strings, extend README review row, pin with test, changelog
  - **Files**: `README.md`, `tests/unit/test_cli/test_help.py`, `CHANGELOG.md`
  - **Approach**: Run `deviate micro run --help` and confirm the `fast` and `--review` lines already satisfy the issue; add `COVERAGE_INCOMPLETE` to the README review row; add the small help-pinning test; append the CHANGELOG bullet
  - **Verification**: Run `pytest tests/unit/test_cli/test_help.py tests/unit/test_core/test_profile.py tests/unit/test_cli/test_setup.py::TestReadmeNewUserPath -v` and `mise run check`

## Data Flow Analysis
- Inputs are the existing `--help` strings and the README table; the transform is one README token addition plus one test file addition; outputs are rendered help text and the updated table; no runtime data, storage, or subprocess flow changes.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| README edit breaks the Quickstart pin test | Medium | Low | Run `TestReadmeNewUserPath` before commit |
| Help test becomes brittle across Rich wrapping | Medium | Low | Use substring assertions, matching the existing style in `test_help.py` |
| Accidental edits to sibling review or walkthrough runtime | High | Low | Touch only the README review row; never open `src/deviate/cli/review.py`, `src/deviate/cli/walkthrough.py`, or sibling prompt files |

## Security Profile
Risk surfaces: none (docs plus help strings plus one help-output test)
Negative tests: none required; the new test asserts help wording only and spawns no agent
Constraints: no new dependencies; no runtime behavior change; no pack membership, JUDGE, profile flag, or Gate 3 prompt body changes

## Integration Points
- **Sibling ISS-ADH-035 / PR #135**: coordination only; this plan never edits sibling prompt bodies and never merges the sibling branch
- **`tests/unit/test_core/test_profile.py::test_help_lists_only_full_and_fast`**: pinned `Execution profile: full, fast` substring must keep passing

## Constitutional Alignment
- **Architecture**: Meso PLAN authors the authoritative Gherkin contract from the shard issue AO outlines; Tasks maps this contract and Micro RED encodes it; no layer is skipped
- **Testing**: pytest pins `--help` wording; no new subprocesses or ledgers; full suite stays under 30s
- **Git Isolation**: Work happens on the dedicated issue worktree branch; no branch switches and no commits by the agent
- **User Scenarios**: `AC-PLAN-001` encodes `US-036-01`, `AC-PLAN-002` encodes `US-036-02`, `AC-PLAN-003` encodes `US-036-03`; RED turns the automated scenario into a failing-then-passing test
