## Summary

<!-- 1–3 bullets. What changed and why. -->

-

## Related

<!-- Issue(s), spec file(s), task ID(s). Use "Fixes #N" / "Refs #N" syntax. -->

-

## Phase

<!-- Tick the TDD phase this PR resolves (or "non-TDD" for chores/docs). -->

- [ ] RED — failing test added
- [ ] GREEN — minimum implementation
- [ ] REFACTOR — cleanup (no behavior change)
- [ ] Non-TDD: chore / docs / ci

## Validation

<!-- Run these locally before requesting review. CI runs the same gates. -->

- [ ] `mise run check` (lint + format-check) passes locally
- [ ] `mise run test` (pytest) passes locally
- [ ] `mise run test-e2e` (bats) passes locally (if CLI behavior changed)
- [ ] New tests added for behavior changes

## Spec alignment

<!-- Confirm spec docs were updated in the same commit, if applicable. -->

- [ ] `specs/DeviaTDD-api.md` reflects the change (CLI surface)
- [ ] `specs/DeviaTDD-architecture.md` reflects the change (phase workflow, routing)
- [ ] `specs/constitution.md` reflects the change (governance / invariants)
- [ ] `CHANGELOG.md` updated under `[Unreleased]`

## Risk & rollback

<!-- One or two sentences. How reversible is this? Any breaking changes? -->
