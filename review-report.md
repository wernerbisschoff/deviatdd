# Review Report: `feat/adhoc/007-graphite-cli`

## Positive Patterns

1. **Clean config-to-runtime routing** — `resolve_graphite_config()` is a simple, deterministic helper called at the decision point. No global state, no caching, no DI. Every call reads the TOML file fresh. The pattern is predictable and testable (`cli/__init__.py:151-156`, `feature.py:33`, `meso.py:1048`).

2. **Comprehensive edge case coverage in tests** — `test_resolve_graphite_config_*` covers all four states: `true`, `false`, key absent, file missing. The governance idempotency test (`test_init_graphite_governance_idempotent`) proves the `_upsert_governance_block` pattern works for replace-in-place.

## Critical Issues

*None found.*

## Suggestions

### SUG-001: `_run_gt_submit` ignores `repo_root` parameter
- **File**: `src/deviate/cli/meso.py:933-946`
- **Category**: CleanCode | **Severity**: Medium | **Confidence**: High
- **Problem**: The function receives `repo_root: Path` but never passes it as `cwd` to `subprocess.run`.
- **Status**: **FIXED**

### SUG-002: Both PR creation functions omit `cwd`
- **File**: `src/deviate/cli/meso.py:949-965`
- **Category**: Pragmatism | **Severity**: Low | **Confidence**: Medium
- **Problem**: Both functions rely on process CWD for their subprocess calls.
- **Status**: **FIXED**

### SUG-003: Overly specific install instruction in error message
- **File**: `src/deviate/cli/meso.py:943`
- **Category**: Pragmatism | **Severity**: Low | **Confidence**: High
- **Problem**: Error message recommends `npm install -g @withgraphite/graphite-cli` which is opinionated.
- **Status**: **FIXED**

### SUG-004: Inner `_run` helper redefined on every call
- **File**: `src/deviate/cli/feature.py:30-31`
- **Category**: CleanCode | **Severity**: Low | **Confidence**: High
- **Problem**: Closure `_run` defined inside `_create_feature_branch` recreated on every invocation.
- **Status**: **FIXED**

## Compliance Matrix

| Domain | Status | Summary |
|--------|--------|---------|
| **Security** | ✅ | No injection, auth, or exposure issues. All subprocess calls use `env=_git_env()` for isolation. |
| **Pragmatism** | ✅ | All issues resolved. |
| **Idiomacy** | ✅ | Follows existing codebase patterns. |
| **Clean Code** | ✅ | All issues resolved. |
| **Constitution** | ✅ | Git isolation, three-layer architecture, no tooling auto-install — all aligned. |
| **PRD/Spec** | ✅ | Implements all 5 task requirements. |

## Files Changed

| File | Changes | Issues | Note |
|------|---------|--------|------|
| `src/deviate/cli/__init__.py` | +54/-22 | 0 | Clean `--graphite` flag + config threading + governance |
| `src/deviate/cli/meso.py` | +57/-10 | 2 → 0 | cwd fix + install msg fix |
| `src/deviate/cli/feature.py` | +25/-8 | 1 → 0 | Inlined `_run` helper |
| `src/deviate/state/config.py` | +36/-6 | 0 | `graphite` field + `resolve_graphite_config()` |
| `src/deviate/prompts/governance/graphite_seed.md` | +18 (new) | 0 | Clean seed document |
| `.opencode/skills/deviate-pr/SKILL.md` | +9/-1 | 0 | Graphite mode docs |
| `tests/test_cli/test_init.py` | +176 | 0 | 16 test methods, full coverage |
| `tests/test_cli/test_feature.py` | +68 | 0 | 4 test methods |
| `tests/test_state/test_config.py` | +43 | 0 | 4 graphite config tests |
| `specs/adhoc/007-graphite-cli/plan.md` | +93 (new) | 0 | Plan document |
| `specs/adhoc/007-graphite-cli/tasks.md` | +168 (new) | 0 | Tasks document |
| `specs/adhoc/007-graphite-cli/tasks.jsonl` | +16 (new) | 0 | Task ledger |
| `specs/issues.jsonl` | +3 | 0 | Issue registration |

## Overall Assessment

- **Code Quality**: Good
- **Readability**: High
- **Maintainability**: High

## Fix Instructions

All 4 fixes were applied during the review session. No further action needed.

### FIX-001: `_run_gt_submit` — added `cwd=repo_root` (APPLIED)
- **File**: `src/deviate/cli/meso.py:934-939`

### FIX-002: `_run_gh_pr_create` — added `cwd` parameter (APPLIED)
- **File**: `src/deviate/cli/meso.py:949-965`

### FIX-003: Install instruction — neutralized message (APPLIED)
- **File**: `src/deviate/cli/meso.py:943`

### FIX-004: Inlined `_run` closure (APPLIED)
- **File**: `src/deviate/cli/feature.py:30-31`
