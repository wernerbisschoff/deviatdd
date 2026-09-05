## Plan Summary
- **Issue**: ISS-ADH-045 — Malformed phase handovers fail with specific diagnostics and one correction retry
- **Implementation Strategy**: Add consistency validation in the handover parse path plus one constrained format-correction retry in the phase runner; keep failures diagnostic and specific.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 3-5 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Reject manifest with mismatched task id**
- **Source Outline**: `AO-045-01`
- **Upstream Traceability**: `US-045-01`, `FR-ADHOC-045`, `AC-ADHOC-045-01`
- **Current-Code Evidence**: `src/deviate/core/agent.py:parse_output`
- **Given**: The active task is `TSK-001-01` with its expected id known to the runner
- **When**: The agent emits a manifest carrying a different task id
- **Then**: The run fails with an error naming expected versus received ids
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Reject contradictory PASS with violation verdict**
- **Source Outline**: `AO-045-01`
- **Upstream Traceability**: `US-045-01`, `FR-ADHOC-045`, `AC-ADHOC-045-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_invoke_agent`
- **Given**: A JUDGE manifest arrives with `status: PASS`
- **When**: The same manifest carries `verdict: COMPLIANCE_VIOLATION` with `next_action: revert_red`
- **Then**: The run rejects the manifest as a contradiction and never treats it as a pass
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Attach output tail to ERROR without rationale**
- **Source Outline**: `AO-045-01`
- **Upstream Traceability**: `US-045-01`, `FR-ADHOC-045`, `AC-ADHOC-045-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_invoke_agent`
- **Given**: An agent manifest arrives with `status: ERROR` and empty rationale
- **When**: The runner records the phase failure
- **Then**: The failure carries the preserved output tail and a `HANDOVER_INVALID`-style event instead of `unknown`
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Preserve plain-output diagnosis when manifest is missing**
- **Source Outline**: `AO-045-01`
- **Upstream Traceability**: `US-045-01`, `FR-ADHOC-045`, `AC-ADHOC-045-01`
- **Current-Code Evidence**: `src/deviate/core/agent.py:parse_output`
- **Given**: Agent output holds no parseable manifest but holds a plain `test_defect` diagnosis
- **When**: The handover path fails the run
- **Then**: The failure preserves the `test_defect` diagnosis from plain output
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Pass valid consistent manifest through unchanged**
- **Source Outline**: `AO-045-01`
- **Upstream Traceability**: `US-045-01`, `FR-ADHOC-045`, `AC-ADHOC-045-01`
- **Current-Code Evidence**: `src/deviate/core/agent.py:HandoverManifest`
- **Given**: An agent emits a manifest with consistent phase, task id, status, verdict, and next action
- **When**: The phase runner processes the handover
- **Then**: The phase continues with the manifest unchanged
- **Verification Mode**: automated

**Scenario AC-PLAN-006: Recover through exactly one format-correction retry**
- **Source Outline**: `AO-045-02`
- **Upstream Traceability**: `US-045-02`, `FR-ADHOC-045`, `AC-ADHOC-045-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_invoke_agent`
- **Given**: An agent emits an unparseable manifest on the first attempt
- **When**: The runner issues one constrained format-correction prompt
- **Then**: A valid manifest from the retry continues the phase with no further retry
- **Verification Mode**: automated

**Scenario AC-PLAN-007: Fail with specific error when correction retry fails**
- **Source Outline**: `AO-045-02`
- **Upstream Traceability**: `US-045-02`, `FR-ADHOC-045`, `AC-ADHOC-045-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_invoke_agent`
- **Given**: The single format-correction retry returns no valid manifest
- **When**: The runner records the phase failure
- **Then**: The run raises the specific correction failure and never emits bare `unknown`
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/core/agent.py**: Hosts handover parse and consistency checks
  - **Current State**: `parse_output` detects missing YAML and recovers invalid fields into `parse_errors` with `UNKNOWN` fallbacks
  - **Changes Required**: Add one consistency check for task id, status/verdict/next-action coherence, and rationale presence; emit specific `HANDOVER_INVALID`-style errors with preserved tail
  - **Integration Surface**: `HandoverManifest` model; `MalformedHandoverManifestError`; callers in `src/deviate/cli/micro.py`
- **src/deviate/cli/micro.py**: Hosts phase runners and the correction retry
  - **Current State**: `_invoke_agent` returns empty results on malformed output and keeps a 50-line tail only as fallback diagnostic
  - **Changes Required**: Validate manifest consistency after invoke; issue exactly one constrained format-correction retry on unparseable manifests; surface specific failures
  - **Integration Surface**: `_invoke_agent`, `_run_red_phase`, `_run_green_phase`, `_run_judge_phase`
- **tests/unit/test_micro/test_handover_validation.py**: New unit sandbox for the contract
  - **Current State**: File does not exist yet
  - **Changes Required**: Add tests for mismatch rejection, contradiction rejection, tail preservation, single retry recovery, retry-failure specificity, and plain-output diagnosis preservation
  - **Integration Surface**: `AgentBackend.parse_output`; mocked agent invoke; mocked `_run_pytest`

## Implementation Strategy
- **Phase 1**: Consistency validation in the handover path — deliverable: specific named defects
  - **Files**: `src/deviate/core/agent.py`, `src/deviate/cli/micro.py`
  - **Approach**: Check task id, verdict/next-action coherence, and ERROR rationale in one result; attach output tail to failures
  - **Verification**: Run new unit tests for mismatch, contradiction, and tail cases
- **Phase 2**: One constrained format-correction retry — deliverable: single retry then specific failure
  - **Files**: `src/deviate/cli/micro.py`
  - **Approach**: Retry once with a format-only correction suffix; cap at one call; raise correction failure on second miss
  - **Verification**: Run retry recovery and retry-failure unit tests plus the fixture micro-run check

## Data Flow Analysis
- Agent stdout enters `_invoke_agent`; raw lines feed the 50-line tail buffer. The tail plus stdout enter `parse_output`; YAML extraction yields a manifest or a malformed error. The new consistency check validates task id, status/verdict/next-action coherence, and rationale presence; valid manifests flow to the phase runner unchanged. Unparseable manifests trigger one format-correction agent call; its result flows through the same check once. Failures exit as specific `HANDOVER_INVALID`-style errors carrying rationale or tail; plain-output `test_defect` diagnoses survive a missing manifest.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Over-strict validation rejects legacy valid manifests | High | Medium | Allow unknown extra fields; reject only the named inconsistencies |
| Retry prompt changes RED/GREEN verdict content | Medium | Low | Keep retry suffix format-only; change no prompt content |
| Validation cost exceeds 200ms gate | Low | Low | Keep checks to string compares; exclude retry call from budget |
| Contradiction check reroutes JUDGE semantics | High | Low | Reject contradictions; change no verdict routing |

## Security Profile
Risk surfaces: deserialization (YAML manifest parse), subprocess (single correction-retry agent call), file paths (tail buffer to sidecars)
Negative tests: crafted YAML mapping with hostile keys stays inert; retry prompt injection in agent output yields specific failure, not execution; oversized output truncates to the tail bound
Constraints: use safe YAML loading only; no new dependencies; no secrets in logs or sidecars

## Integration Points
- **Agent backends via `AgentBackend.invoke`**: Correction retry reuses the same backend call with a format-only suffix
- **Phase runners (`_run_red_phase`, `_run_green_phase`, `_run_judge_phase`)**: Consume validated manifests; receive specific failures instead of opaque errors
- **JUDGE verdict routing**: Reads manifest verdicts; contradiction rejection adds no rerouting

## Constitutional Alignment
- **Architecture**: Follows the three-layer model (§1); this plan covers Meso planning for one Micro hardening slice with no layer skipped and no Gate 2 step.
- **Testing**: Uses pytest under `tests/unit/test_micro/` per §3; mocks agent invoke and `_run_pytest` to keep the suite under 30s.
- **Git Isolation**: Runs on the dedicated issue worktree and branch per §1; commits occur at phase boundaries through the orchestrator.
- **User Scenarios**: Each `AC-PLAN-NNN` encodes `US-045-01` or `US-045-02` plus the issue ATDD; RED turns those scenarios into failing tests in `tests/unit/test_micro/test_handover_validation.py`.
