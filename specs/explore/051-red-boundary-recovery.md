## Problem Definition
**Statement**: The micro runner loses the committed RED boundary after session loss and reruns RED.
**Scope**: `src/deviate/cli/micro.py` pre-GREEN decision, session state, task ledger records.
**Exclusions**: RED test authoring, GREEN implementation, retry budgets, model routing, JUDGE verdict behavior.

## Discovery Audit Results
### Verified Dependencies
- Typer + Rich CLI, Pydantic ledger models, Aider execution substrate, pytest + ruff + mise gates.

### Ghost Dependencies
- None observed.

### Manifest Files Observed
- `pyproject.toml` declares the `deviate` CLI package.
- `.mise.toml` defines `test`, `check`, `lint`, `format` tasks.
- `specs/adhoc/issues/051-micro-restores-committed-red-boundary.md` carries the issue contract.

### Test Runner Configuration
- Unit targets named by the issue: `tests/unit/test_micro/test_orchestration.py`, `tests/unit/test_micro/test_run.py`.
- Command from the issue: `uv run pytest tests/unit/test_micro/test_orchestration.py tests/unit/test_micro/test_run.py -q`.

### Manifest-Constitution Divergence
- None observed. Constitution mandates pytest, ruff, mise; manifests declare the same stack.

## Constitution Quotes
- **Architectural Principles**: "Micro-layer tasks reuse a single LLM session across RED → GREEN → REFACTOR phases."
- **Tech Stack Standards**: "Target: CLI application (`deviate`)"
- **Testing Protocols**: "Test framework: pytest"
- **Definition of Done**: "Judge phase passed (git diff validated against the authoritative plan acceptance contract)"

## Architectural Baselines
- **Existing Architectural Patterns**
  - Pre-GREEN gate returns `escalate` when the session SHA is empty (`src/deviate/cli/micro.py`).
  - Rollback helpers already resolve rewritten SHAs via `_resolve_rewritten_sha` and `_refresh_session_commit_anchors`.
  - Forward-route stale detection already binds JUDGE routes to task + SHA (`_forward_route_is_stale`).
- **Infrastructure & Operations**
  - Phase commits land via `_commit_phase`; HEAD SHA is read with `git rev-parse HEAD`.
  - Session persists at `.deviate/session.json` (`SessionState`).
- **Data & State Management**
  - Task ledger rows are append-only; latest record per `(issue_id, task ID)` is canonical (`_collect_latest_task_records`).
  - `TaskRecord` carries optional `head_sha`, `reset_to`, `recovery_ref` fields.
- **Quality, Safety & Observability**
  - Per-task transcripts persist under `.deviate/logs/<ISSUE_ID>/<TASK_ID>.log`.
  - JUDGE postmortems persist under `.deviate/logs/<ISSUE_ID>/<TASK_ID>.verdicts.jsonl`.
- **External Integrations**
  - None observed.

## Sibling Flow Inventory
| Dimension | Observed fact | Path |
| :--- | :--- | :--- |
| Amount vs fee | none observed | n/a |
| Lock vs reserve | none observed | n/a |
| Vendor call | none observed | n/a |
| Idempotency | ledger append uses compound-key dedup for rollback snapshots | src/deviate/state/ledger.py |
| Destination shape | task record carries head_sha / reset_to / recovery_ref | src/deviate/state/ledger.py |

## Ecosystem Research
- **Best Practices**
  - Rebuild volatile session caches from the append-only log on startup. Source: project ledger protocol.
- **Common Use Cases & Pitfalls**
  - Session file loss after crash or cherry-pick orphans in-memory SHAs. Source: issue contract edge cases.
- **Standard Tooling**
  - `git rev-parse HEAD`, `git merge-base --is-ancestor`, commit subject matching. Source: existing rollback helpers.

## File Registry
| Path | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| src/deviate/cli/micro.py | source | Pre-GREEN gate and RED boundary check | `def _has_red_commit_boundary(session: SessionState) -> bool:` / `"""Return True when ``session.red_commit_sha`` is a non-empty SHA."""` / `return bool(session.red_commit_sha.strip())` |
| src/deviate/cli/micro.py | source | Missing SHA redispatches RED | `if not _has_red_commit_boundary(session):` / `return "escalate"` |
| src/deviate/cli/micro.py | source | RED clears the session SHA before the agent runs | `session.red_commit_sha = ""` / `session.save(session_path)` |
| src/deviate/cli/micro.py | source | RED ledger row stores status only, no SHA | `record = TaskRecord.model_validate(task)` / `record.status = "RED"` / `append_task_transition(record, ledger_path)` |
| src/deviate/cli/micro.py | source | RED commit SHA lands only in session after commit | `head_sha = subprocess.run(` / `["git", "rev-parse", "HEAD"],` / `session.red_commit_sha = head_sha` |
| src/deviate/state/config.py | source | Session cache fields | `red_commit_sha: str = ""` / `judge_red_commit_sha: str = ""` |
| src/deviate/state/ledger.py | source | Task record carries optional commit pointers | `head_sha: str \| None = None` / `reset_to: str \| None = None` / `recovery_ref: str \| None = None` |
| src/deviate/cli/micro.py | source | Canonical ledger parse is latest-per-task | `for ledger_file in sorted(root.glob(_LEDGER_GLOB)):` / `key = (issue_id, tid)` / `latest[key] = rec` |
| src/deviate/cli/micro.py | source | Rewrite-aware SHA resolution exists | `def _resolve_rewritten_sha(root: Path, stored_sha: str) -> str:` |
| tests/unit/test_micro/test_orchestration.py | test | Recovery and stale-rejection cases live here | per-issue verification target |
| tests/unit/test_micro/test_run.py | test | Session-resume cases live here | per-issue verification target |

## Scope Sizing
| Metric | Value |
| :--- | :--- |
| Estimated Complexity | Medium |
| Files Likely Modified | 3 — src/deviate/cli/micro.py, tests/unit/test_micro/test_orchestration.py, tests/unit/test_micro/test_run.py |
| New Modules Required | No |
| New Persistence / Data Models | No |
| New External Integrations | No |
| Upstream / Cross-Cutting Concerns | None |
| Rationale | The fix reuses the ledger plus git. It changes one decision point and its tests. |

## Status Summary
| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | 051-red-boundary-recovery |
| GIT_BRANCH | feat/adhoc/051-micro-restores-committed-red-boundary |
| SPEC_TARGET | specs/explore/051-red-boundary-recovery.md |
| NEXT_ACTION | Run `/deviate-adhoc` (Low/Medium complexity) or `/deviate-research` (High complexity) — see `## Scope Sizing` |
