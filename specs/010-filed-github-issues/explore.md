## Problem Definition
**Statement**: The repository has four open GitHub issues about JUDGE and GREEN task-runner recovery behavior.
**Scope**: Open issues #242, #243, #244, and #245; local CLI, agent, state, test, and workflow artifacts.
**Exclusions**: No implementation changes, test changes, or architecture decisions.

## Discovery Audit Results
### Verified Dependencies
- `pyproject.toml` declares the Python package and test tooling. Quote: `requires-python = ">=3.13"`.
- `mise.toml` declares project task commands. Quote: `test = "uv run pytest tests/ -q"`.

### Ghost Dependencies
None observed.

### Test Runner Configuration
- Pytest is configured in `pyproject.toml`. Quote: `[tool.pytest.ini_options]`.
- The repository test command is `pytest tests/ -v`. Quote: `Test command: pytest tests/ -v` in `specs/constitution.md`.
- CI runs the project checks. Quote: `mise run check` in `.github/workflows/ci.yml`.

## Constitution Quotes
- **Architectural Principles**: "**Three-Layer Architecture**: Macro (feature scoping: Explore → Research → PRD → Shard), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR)."
- **Tech Stack Standards**: "Python 3.13"; "Target: CLI application (`deviate`)"; "Framework: Typer (CLI entry points) with Rich for terminal I/O".
- **Testing Protocols**: "- Test framework: pytest"; "- Test root: `tests/`"; "- Test command: `pytest tests/ -v`".
- **Definition of Done**: "- [ ] Code implemented (satisfies assigned `AC-PLAN-NNN` scenarios from `plan.md`)"; "- [ ] Tests passing (pytest with clean exit code 0)"; "- [ ] Judge phase passed (git diff validated against the authoritative plan acceptance contract)".

## Architectural Baselines
- **Routing and entry points**: `src/deviate/cli` contains CLI modules. Quote: `src/deviate/cli` from the repository tree.
- **Agent execution**: `src/deviate/core/agent.py` contains the agent backend. Quote: `class AgentBackend:` from `specs/constitution.md`.
- **State and ledgers**: The project uses JSONL issue and task ledgers. Quote: `Issue ledger: specs/issues.jsonl (append-only JSONL)` from `specs/constitution.md`.
- **Quality automation**: CI uses the project check task. Quote: `mise run check` in `.github/workflows/ci.yml`.

## Sibling Flow Inventory
None observed.

## Related Epic Candidates
None observed.

## Ecosystem Research
SKIPPED (sibling + constitution sufficient)

## File Registry
| Path | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `specs/constitution.md` | Governance | Defines architecture and testing rules. | `Version: 0.12.0` |
| `pyproject.toml` | Manifest | Defines Python package metadata and tooling. | `requires-python = ">=3.13"` |
| `mise.toml` | Task configuration | Defines project commands. | `test = "uv run pytest tests/ -q"` |
| `src/deviate/core/agent.py` | Python module | Defines agent execution. | `class AgentBackend:` |
| `src/deviate/cli` | Source directory | Contains CLI entry-point modules. | `src/deviate/cli` |
| `tests/` | Test directory | Contains automated tests. | `tests/` |
| `.github/workflows/ci.yml` | CI workflow | Runs repository checks. | `mise run check` |
| `specs/issues.jsonl` | JSONL ledger | Stores issue state transitions. | `specs/issues.jsonl` |

## GitHub Issue Inventory
- **#245 — bug: JUDGE contradiction detection halts after oscillating GREEN/RED requirements**
  - URL: `https://github.com/wernerbisschoff/deviatdd/issues/245`
  - Label: `bug`
  - Evidence: `JUDGE requirements oscillated between two incompatible interpretations (A → B → A).`
  - Evidence: `The final verdict reported: verdict: COMPLIANCE_VIOLATION`.
- **#244 — bug: GREEN post sees PENDING after runner commits RED during retry**
  - URL: `https://github.com/wernerbisschoff/deviatdd/issues/244`
  - Label: `bug`
  - Evidence: `GREEN phase rejected for TSK-004-03: expected RED, found PENDING`.
  - Evidence: `Investigate transition selection and append_task_transition deduplication after repeated RED/PENDING cycles.`
- **#243 — bug: manual green post retains rejection state and retrains completed work**
  - URL: `https://github.com/wernerbisschoff/deviatdd/issues/243`
  - Label: `bug`
  - Evidence: `green post reported GREEN_POST_OK`.
  - Evidence: `_green_post_kernel transitions the ledger and commits but leaves train_feedback, failure_kind, pending_judge_action, judge_rejected, and matching pending_judge_feedback intact.`
- **#242 — bug: JUDGE rejects retained task behavior absent from the diff**
  - URL: `https://github.com/wernerbisschoff/deviatdd/issues/242`
  - Label: `bug`
  - Evidence: `JUDGE repeatedly rejected wallet-service TSK-004-02 because snapshots and fingerprint replay were absent from the GREEN diff.`
  - Evidence: `This contradicts preservation tasks and encourages duplicate implementation and tests.`

## Scope Sizing
| Metric | Value |
| :--- | :--- |
| Estimated Complexity | Medium |
| Files Likely Modified | 4 issue-linked behavior areas; exact files not established by this exploration |
| New Modules Required | No |
| New Persistence / Data Models | No |
| New External Integrations | No |
| Upstream / Cross-Cutting Concerns | JUDGE, RED retry, GREEN post, task ledger transitions, and prompt contracts overlap |
| Related Epic Attach | new_epic |
| Rationale | Four open issues describe related runner and JUDGE lifecycle behavior. The issues identify existing source and log paths but do not define an implementation plan. |

## Status Summary
| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | filed-github-issues |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/filed-github-issues.md |
| NEXT_ACTION | `new_epic` (`/deviate-research`) |
| ATTACH_EPIC |  |
| HITL_OVERRIDE | none |
