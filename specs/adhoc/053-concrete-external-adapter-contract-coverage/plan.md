## Plan Summary
- **Issue**: ISS-ADH-053 — Require concrete external adapter contract coverage
- **Implementation Strategy**: Add split and contract rules to the plan/tasks prompts plus fake-only rejection and inspection rules to the judge/red prompts.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 3-5 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Split adapter transport from port behavior in plan output**
- **Source Outline**: `AO-053-01`
- **Upstream Traceability**: `US-053-01`, `FR-ADHOC-053`, `AC-ADHOC-053-01`
- **Current-Code Evidence**: `src/deviate/prompts/auto/plan.md:acceptance_contract`
- **Given**: Plan prompt holds no adapter split rule
- **When**: Plan names an external SDK or provider adapter
- **Then**: Plan emits separate concrete adapter acceptance criteria apart from port behavior criteria
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Require concrete adapter contract tests for dependency signature and auth**
- **Source Outline**: `AO-053-01`
- **Upstream Traceability**: `US-053-01`, `FR-ADHOC-053`, `AC-ADHOC-053-01`
- **Current-Code Evidence**: `src/deviate/prompts/auto/tasks.md:task_construction`
- **Given**: Adapter task card exists for an external provider
- **When**: Tasks decomposes the adapter slice
- **Then**: Adapter task carries concrete tests for dependency signature, authentication wiring, request identity, and response lookup
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Cover import boundary and deferred construction in adapter contract**
- **Source Outline**: `AO-053-01`
- **Upstream Traceability**: `US-053-01`, `FR-ADHOC-053`, `AC-ADHOC-053-01`
- **Current-Code Evidence**: `src/deviate/prompts/auto/red.md:test_writing`
- **Given**: Adapter module defers client construction past import
- **When**: RED authors the adapter contract tests
- **Then**: Tests assert import-time safety plus deferred construction and fail with dependency evidence on missing auth or unsupported fields
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Reject fake-only coverage for claimed provider integration**
- **Source Outline**: `AO-053-02`
- **Upstream Traceability**: `US-053-02`, `FR-ADHOC-053`, `AC-ADHOC-053-02`
- **Current-Code Evidence**: `src/deviate/prompts/auto/judge.md:STEP_2`
- **Given**: Task claims real provider integration and tests exercise only the fake port
- **When**: JUDGE evaluates the diff
- **Then**: JUDGE emits COMPLIANCE_VIOLATION with feedback naming the missing concrete contract evidence
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Keep fake coverage valid for pure port-behavior tasks**
- **Source Outline**: `AO-053-02`
- **Upstream Traceability**: `US-053-02`, `FR-ADHOC-053`, `AC-ADHOC-053-02`
- **Current-Code Evidence**: `src/deviate/prompts/auto/judge.md:evaluation_criteria`
- **Given**: Task makes no integration claim and tests target port behavior
- **When**: JUDGE evaluates the diff
- **Then**: JUDGE passes fake coverage without demanding concrete adapter evidence
- **Verification Mode**: automated

**Scenario AC-PLAN-006: Inspect installed dependency signature offline in adapter tasks**
- **Source Outline**: `AO-053-01`, `AO-053-02`
- **Upstream Traceability**: `US-053-01`, `FR-ADHOC-053`, `AC-ADHOC-053-01`
- **Current-Code Evidence**: `src/deviate/prompts/auto/red.md:traceability_mandates`
- **Given**: Adapter task names an installed dependency version
- **When**: RED or GREEN checks the adapter contract
- **Then**: Agent inspects the installed signature offline with no network call and pins the declared version on absence
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/prompts/auto/plan.md**: carries the adapter split rule — plan names adapter, plan emits separate criteria
  - **Current State**: Holds acceptance contract schema with no adapter transport split
  - **Changes Required**: Add split directive plus concrete contract checklist to execution sequence
  - **Integration Surface**: `src/deviate/prompts/assembly.py::_LAYER_MAP`, `deviate plan pre/post` validator
- **src/deviate/prompts/auto/tasks.md**: carries the adapter task split and contract card rule
  - **Current State**: Holds slice and strategy rules with no adapter transport clause
  - **Changes Required**: Add adapter split directive and per-method contract row rule
  - **Integration Surface**: `deviate tasks pre/post` validator, `tasks.md` schema
- **src/deviate/prompts/auto/judge.md**: carries the fake-only rejection rule
  - **Current State**: Holds Test Integrity and spec compliance checks with no fake-only adapter rule
  - **Changes Required**: Add fake-only rejection category plus correction contract naming missing evidence
  - **Integration Surface**: JUDGE verdict manifest, `train_feedback` repair contract
- **src/deviate/prompts/auto/red.md**: carries the dependency inspection and negative test rule
  - **Current State**: Holds layer lock and honeycomb rules with no dependency signature check
  - **Changes Required**: Add offline signature inspection directive plus import-boundary and auth negative tests
  - **Integration Surface**: RED test strategy contract, `tests/` unit suite

## Implementation Strategy
- **Phase 1**: Plan and tasks split rules — deliverable: adapter transport splits from port behavior with concrete criteria
  - **Files**: `src/deviate/prompts/auto/plan.md`, `src/deviate/prompts/auto/tasks.md`
  - **Approach**: Add split directive keyed on external SDK naming plus concrete contract checklist
  - **Verification**: Unit tests assert split prompts fire on adapter naming and stay silent otherwise
- **Phase 2**: Judge rejection and red inspection rules — deliverable: fake-only rejection plus offline signature checks
  - **Files**: `src/deviate/prompts/auto/judge.md`, `src/deviate/prompts/auto/red.md`
  - **Approach**: Add fake-only violation category with evidence-naming repair plus offline inspect directive
  - **Verification**: Unit tests assert fake-only integration fails and pure port-behavior passes

## Data Flow Analysis
- Plan reads issue AO outlines and emits AC-PLAN contract with adapter criteria. Tasks maps the contract into split task cards. RED writes concrete adapter tests against the installed dependency surface. JUDGE reads the diff plus test evidence and emits pass or violation with named missing evidence.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Split rule fires on non-adapter tasks | Medium | Low | Key the rule on explicit external SDK naming only |
| Judge rejects valid fake port tests | High | Medium | Exempt tasks with no integration claim in the rule text |
| Signature checks hit network | Medium | Low | State offline-only inspection and version pinning in red prompt |

## Security Profile
Risk surfaces: auth, secrets, outbound HTTP, file paths
Negative tests: missing credentials fail adapter tests without live calls, auth wiring asserted without secrets in logs, unsupported fields fail with dependency evidence named
Constraints: no live-credential runs, no network calls in signature checks, no hardcoded secrets in prompts or tests

## Integration Points
- **deviate plan post validator**: must accept AO-053-01 and AO-053-02 traceability in new scenarios
- **deviate tasks post validator**: must accept split adapter task cards with concrete contract criteria
- **JUDGE verdict manifest**: must carry fake-only violation category with evidence-naming feedback

## Constitutional Alignment
- **Architecture**: Implements three-layer flow: plan owns the adapter acceptance contract, tasks maps it, JUDGE enforces it per §1
- **Testing**: pytest unit suite per §3; RED encodes adapter scenarios as failing tests, GREEN passes, JUDGE checks integrity
- **Git Isolation**: Work happens on the issue worktree branch; tests use tmp repos per AGENTS.md
- **User Scenarios**: AC-PLAN-001 through AC-PLAN-003 encode `US-053-01` plus AO-053-01; AC-PLAN-004 and AC-PLAN-005 encode `US-053-02` plus AO-053-02; AC-PLAN-006 encodes the offline inspection shared by both; RED turns each into failing tests
