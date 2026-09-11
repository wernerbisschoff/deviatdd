## Plan Summary
- **Issue**: ISS-ADH-058 — Opt-in /deviate-converge pack after Micro, before PR
- **Implementation Strategy**: Reuse the existing command-pack installer and ledger append path. Add issue-scoped readiness, present-state assessment, append-only Convergence task creation, and the opt-in runner handoff.

## Acceptance Contract
**Scenario AC-PLAN-001: Install Converge only for the selected optional pack**
- **Source Outline**: `AO-058-01`
- **Upstream Traceability**: `US-058-01`, `FR-ADHOC-058`, `AC-ADHOC-058-01`
- **Current-Code Evidence**: `src/deviate/core/commands.py:OPTIONAL_PACKS`
- **Given**: Operator runs setup with no optional pack or with `converge` selected
- **When**: Setup resolves and installs command stems
- **Then**: Default setup omits `deviate-converge`, selected `converge` installs it, and unknown packs fail closed
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Emit a bounded readiness contract for this issue**
- **Source Outline**: `AO-058-02`
- **Upstream Traceability**: `US-058-02`, `FR-ADHOC-058`, `AC-ADHOC-058-02`
- **Current-Code Evidence**: `src/deviate/core/converge.py:build_pre_contract`
- **Given**: This issue has a brief, plan, tasks file, and a drained Micro queue
- **When**: Operator runs `deviate converge pre`
- **Then**: The JSON contract identifies this issue, its brief, plan, tasks, constitution MUST when filled, and in-scope paths without epic artifacts
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Stop Converge when required inputs or Micro work are unavailable**
- **Source Outline**: `AO-058-02`
- **Upstream Traceability**: `US-058-02`, `FR-ADHOC-058`, `AC-ADHOC-058-02`
- **Current-Code Evidence**: `src/deviate/cli/converge.py:pre`
- **Given**: This issue lacks a required artifact or has pending task records
- **When**: Operator runs `deviate converge pre`
- **Then**: The command returns a non-zero result with an actionable `CONVERGE_NOT_READY` diagnostic
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Append Convergence tasks without rewriting prior state**
- **Source Outline**: `AO-058-03`
- **Upstream Traceability**: `US-058-03`, `FR-ADHOC-058`, `AC-ADHOC-058-03`
- **Current-Code Evidence**: `src/deviate/core/converge.py:apply_findings`
- **Given**: Converge receives valid gap findings for a drained issue
- **When**: Operator runs `deviate converge post` with the findings payload
- **Then**: The command appends one next-numbered Convergence phase, creates PENDING `TSK-{issue}-{nn}` rows through `append_task_record`, and preserves all prior task text
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Classify findings and preserve clean or failed writes**
- **Source Outline**: `AO-058-04`
- **Upstream Traceability**: `US-058-04`, `FR-ADHOC-058`, `AC-ADHOC-058-04`
- **Current-Code Evidence**: `src/deviate/core/converge.py:parse_findings_payload`
- **Given**: Converge receives empty, invalid, critical, or `unrequested` findings
- **When**: Operator runs `deviate converge post`
- **Then**: Empty findings leave `tasks.md` byte-unchanged and report `CONVERGED`, valid findings use the four allowed taxonomies with critical findings first, and invalid or failed ledger writes leave task text unchanged
- **Verification Mode**: automated

**Scenario AC-PLAN-006: Re-enter Micro through the optional Converge loop before PR**
- **Source Outline**: `AO-058-05`
- **Upstream Traceability**: `US-058-05`, `FR-ADHOC-058`, `AC-ADHOC-058-05`
- **Current-Code Evidence**: `src/deviate/cli/__init__.py:run_command`
- **Given**: Micro drains this issue and the operator selects Converge or installs its pack
- **When**: The operator runs the issue workflow
- **Then**: The runner hands off to Converge, re-drains appended tasks until clean, and leaves walkthrough, review, and PR outside the Converge loop
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/core/commands.py**: Register `converge` as an optional pack and preserve default and fail-closed pack resolution; evidence `OPTIONAL_PACKS`; Integrates: setup command installation.
- **src/deviate/prompts/commands/deviate-converge.md**: Define the bounded assessor read set, taxonomy, and append-only handoff; evidence `CONVERGE` system instructions; Integrates: agent slash-command installation.
- **src/deviate/cli/converge.py**: Expose `deviate converge pre|post` JSON contracts and ledger error diagnostics; evidence `pre` and `post`; Integrates: `deviate.core.converge` and `append_task_record`.
- **src/deviate/cli/__init__.py**: Register the Converge Typer app and support the opt-in runner tail; evidence `run_command`; Integrates: Micro runner and `converge_pack_available`.
- **src/deviate/core/converge.py**: Resolve issue artifacts, assess readiness, classify findings, and append task records; evidence `build_pre_contract` and `apply_findings`; Integrates: review artifact resolution and ledger.
- **src/deviate/state/ledger.py**: Keep task creation append-only through `append_task_record`; evidence `append_task_record`; Integrates: Convergence task ledger.
- **tests/unit/test_cli/test_converge.py**: Verify pack selection, contracts, clean no-op, taxonomy, append ordering, and runner loop; evidence `TestConvergePackOptIn`, `TestConvergePre`, and `TestConvergePost`.

## Data Flow Analysis
- `deviate setup --packs` or installed pack files → pack resolution → command installation.
- Issue session and branch → artifact resolution → bounded pre-contract with relative in-scope paths.
- Agent findings JSON → taxonomy validation and severity ordering → `append_task_record` → one appended `tasks.md` Convergence section.
- Runner drain result → optional Converge handoff → appended task drain and repeat → clean handoff to walkthrough, review, and PR.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Converge reads artifacts outside the issue boundary | High | Medium | Build the contract from the issue brief, plan, tasks, constitution, and extracted in-scope paths only |
| Ledger append succeeds before markdown write fails | High | Low | Keep append and file update ordered, surface named append diagnostics, and test unchanged-file failure behavior |
| Pending Micro tasks trigger premature assessment | Medium | Medium | Reject `pre` with `CONVERGE_NOT_READY` until the issue queue drains |
| Optional pack changes default workflow | High | Low | Keep `converge` outside default pack stems and gate runner entry on selection or `--converge` |

## Security Profile
Risk surfaces: filesystem paths, JSON findings, append-only task ledger, subprocess workflow
Negative tests: missing prerequisites fail, invalid taxonomy fails, unknown pack fails, failed ledger append preserves tasks
Constraints: relative artifact paths, no application-code writes, no hand-edited JSONL, no secrets in findings or logs

## Constitutional Alignment
- **Constitution**: §1 optional Product Layer and Micro-Layer Scope; §1 append-only ledger and session workflow; §3 pytest verification; §4 branch isolation and conventional phase commits
