## Problem Definition
**Statement**: The `deviate micro run` runner crashed with an uncaught `PermissionError` during integration-test timeout cleanup in `_kill_process_group`.
**Scope**: Timeout cleanup path in `src/deviate/cli/_safe_commands.py` and its unit tests in `tests/unit/test_cli/`.
**Exclusions**: The underlying integration timeout cause needs separate diagnosis. No change to test selection, reporting, or ledger behavior.

## Discovery Audit Results
### Verified Dependencies
- The cleanup path uses only the standard library (`os`, `signal`, `subprocess`, `time`). No new dependency is involved.
- Manifest observed: `pyproject.toml` declares the `deviate` CLI package. Test runner is `pytest`. Linter is `ruff`.

### Ghost Dependencies
- None observed. `os.killpg` and `signal.SIGKILL` resolve to the standard library.

### Manifest Files Observed
- `pyproject.toml` — package manifest for the `deviate` CLI.
- `.mise.toml` — task runner (`mise unit`, `mise integration` cited in the issue).
- `specs/constitution.md` — project constitution, version 0.11.0.

### Test Runner Configuration
- Unit tests live in `tests/unit/test_cli/test_safe_commands.py` and `tests/unit/test_cli/test_timeout_safe_command.py`.
- `src/deviate/cli/micro.py::_run_pytest` invokes pytest as a subprocess. Tests that hit this function must mock `deviate.cli.micro._run_pytest`.

### Manifest-Constitution Divergence
- None observed. The constitution mandates `pytest` and `ruff`. The repo uses both.

## Constitution Quotes
- **Architectural Principles**: "`## 1. Architectural Principles` — Three-Layer Architecture: Macro, Meso, Micro (RED → GREEN → JUDGE → REFACTOR). Micro-layer tasks reuse a single LLM session across RED → GREEN → REFACTOR. Two HITL gates remain: Gate 1 (Design Approval after research) and Gate 3 (Final Merge Audit after micro)."
- **Tech Stack Standards**: "Python 3.13. Target: CLI application (`deviate`). Framework: Typer (CLI entry points) with Rich for terminal I/O. Package manager: `uv`. Test runner: `pytest`. Linter: `ruff` (lint + format)."
- **Testing Protocols**: "Test framework: pytest. Test root: `tests/`. Test command: `pytest tests/ -v`. Lint command: `ruff check .`. E2E command: `bats tests/e2e/`. Coverage target: >= 80%."
- **Definition of Done**: "Tests passing (pytest with clean exit code 0). Lint passing (ruff check with no violations). CHANGELOG.md updated under `[Unreleased]` for user-visible changes (new commands/flags, behavior changes, user-affecting bug fixes, breaking changes, new user-visible dependencies)."

## Architectural Baselines
- **Existing Architectural Patterns**: CLI entry via Typer in `src/deviate/main.py`. Safe-command gate (`parse_safe_command`) before any subprocess spawn in `src/deviate/cli/_safe_commands.py`. Timeout escalation pattern: SIGTERM, grace sleep, SIGKILL on the process group, then reap.
- **Infrastructure & Operations**: Task runner is `mise` (`.mise.toml`). The issue cites `mise unit` and `mise integration` as the failing invocation.
- **Data & State Management**: No database. State lives in JSONL ledgers (`specs/issues.jsonl`, `specs/**/tasks.jsonl`) and run logs under `.deviate/logs/`.
- **Quality, Safety & Observability**: Unit tests in `tests/unit/test_cli/test_timeout_safe_command.py` cover the timeout path, including a test that `killpg` swallows `ProcessLookupError`. Run log cited: `.deviate/logs/run_20260908T130314.log`.
- **External Integrations**: None involved in this path. The crash is local process-group cleanup.

## Sibling Flow Inventory
The nearest sibling is the `OSError` cleanup branch in the same function, which already wraps `_kill_process_group` with a broad except. Quote paths below.

| Dimension | Observed fact | Path |
| :--- | :--- | :--- |
| Amount vs fee | none observed (no amount/fee concept in this path) | `src/deviate/cli/_safe_commands.py` |
| Lock vs reserve | none observed (no lock/reserve concept in this path) | `src/deviate/cli/_safe_commands.py` |
| Vendor call | none observed (local `os.killpg` only, no HTTP/job vendor call) | `src/deviate/cli/_safe_commands.py:414` |
| Idempotency | single escalation sequence per timeout: SIGTERM, grace sleep, SIGKILL | `src/deviate/cli/_safe_commands.py:524-526` |
| Destination shape | deterministic `CompletedProcess` with `returncode == TEST_TIMEOUT_EXIT_CODE` (124) plus partial output | `src/deviate/cli/_safe_commands.py:555-560` |

Sibling fact: the `OSError` branch at `src/deviate/cli/_safe_commands.py:503-513` already catches `(ProcessLookupError, OSError, subprocess.TimeoutExpired)` around `_kill_process_group`. The timeout branch at lines 524-526 calls `_kill_process_group` with no guard, and `_kill_process_group` itself catches only `ProcessLookupError`.

## Ecosystem Research
Catalog only. Later phases must not treat these rows as Required unless a local flow, constitution clause, or money/auth/provider integrity test applies.
- **Best Practices**: The standard library documents `os.killpg` raising `ProcessLookupError` (ESRCH) for exited groups and `PermissionError` (EPERM) when the caller lacks permission to signal the group. The repo wrapper handles ESRCH only.
- **Common Use Cases & Pitfalls**: EPERM arises when the target process group contains or is owned by another user, or the group id was recycled. A best-effort cleanup wrapper treats both ESRCH and EPERM as terminal end-states.
- **Standard Tooling**: No new tooling required. Fix stays inside `src/deviate/cli/_safe_commands.py` plus its existing unit tests.

## File Registry
| Path | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `src/deviate/cli/_safe_commands.py` | Source | Safe test-command runner with timeout cleanup | `def _kill_process_group(pid: int, sig: int) -> None:` / `"""Best-effort ``os.killpg`` wrapper that swallows ESRCH.` / `if pid <= 0:` / `return` / `try:` / `os.killpg(pid, sig)` / `except ProcessLookupError:` / `return` |
| `src/deviate/cli/_safe_commands.py` | Source | Timeout escalation: SIGTERM, grace, SIGKILL | `_kill_process_group(proc.pid, signal.SIGTERM)` / `time.sleep(_TIMEOUT_GRACE_SECONDS)` / `_kill_process_group(proc.pid, signal.SIGKILL)` |
| `src/deviate/cli/_safe_commands.py` | Source | Sibling OSError branch already guards cleanup | `except OSError as exc:` / `try:` / `_kill_process_group(proc.pid, signal.SIGKILL)` / `proc.wait(timeout=_TIMEOUT_GRACE_SECONDS + 1.0)` / `except (ProcessLookupError, OSError, subprocess.TimeoutExpired):` / `pass` |
| `src/deviate/cli/_safe_commands.py` | Source | Timeout sentinel constants | `TEST_TIMEOUT_EXIT_CODE: int = 124` / `_TIMEOUT_GRACE_SECONDS: float = 5.0` |
| `src/deviate/cli/micro.py` | Source | Pytest subprocess entry hit by the runner | `def _run_pytest(` / `Tests that exercise CLI commands which internally call this function` / `(e.g. red/green/refactor `_post` commands) MUST mock` / `` `deviate.cli.micro._run_pytest` `` |
| `tests/unit/test_cli/test_timeout_safe_command.py` | Test | Existing ESRCH coverage for the wrapper | `def test_killpg_swallows_process_lookup_error(` / `monkeypatch.setattr("deviate.cli._safe_commands.os.killpg", _raise_esrch)` |
| `specs/constitution.md` | Doc | Governance: stack, testing, done criteria | `Version: 0.11.0` / `Python 3.13` / `Test runner: pytest` / `Coverage target: >= 80%` |
| `pyproject.toml` | Manifest | Package manifest for the CLI | `deviate` CLI package declaration (build target for `uv run deviate`) |
| `.mise.toml` | Config | Task runner with unit/integration tasks | `mise unit` and `mise integration` task definitions cited by the issue |

## Scope Sizing

| Metric | Value |
| :--- | :--- |
| Estimated Complexity | Low |
| Files Likely Modified | 2 — `src/deviate/cli/_safe_commands.py`, `tests/unit/test_cli/test_timeout_safe_command.py` |
| New Modules Required | No |
| New Persistence / Data Models | No |
| New External Integrations | No |
| Upstream / Cross-Cutting Concerns | None |
| Rationale | The crash is one uncaught errno in one wrapper. The fix is a wider except plus one unit test. |

## Status Summary
| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | killpg-permission-error |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/killpg-permission-error.md |
| NEXT_ACTION | Run `/deviate-adhoc` (Low complexity) — see `## Scope Sizing` |
