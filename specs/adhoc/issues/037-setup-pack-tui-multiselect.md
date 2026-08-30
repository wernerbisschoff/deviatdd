---
title: "Replace setup optional-pack Prompt.ask with a TTY checkbox multi-select"
labels: [enhancement, adhoc, ux]
blocked_by: []
coordinates_with: ["ISS-ADH-034"]
issue_id: ISS-ADH-037
flow_refs: []
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/037-setup-pack-tui-multiselect.md`
- **Primary Architectural Workstation**: `src/deviate/cli/__init__.py`, `src/deviate/ui/checkbox.py`, `tests/test_cli/test_setup.py`

## The Problem Contract

`deviate setup` on a TTY asks for optional command packs via Rich `Prompt.ask(choices=...)`. Rich renders those names as one slash-separated line that wraps mid-name (`pr` / `une`). The intended multi-select is a second "Add another" loop the operator never reaches because the first prompt is unusable. Replace it with a real TTY checkbox list: one pack per row, Space toggles, Enter confirms, default nothing selected.

## Scope Boundaries
### Hard Inclusions
- File this adhoc issue, `FR-ADHOC-037` on `specs/adhoc/prd.md`, and one BACKLOG ledger row (`flow_refs: []`).
- TTY optional-pack picker is a checkbox list with one row each for `product`, `merge`, `pr`, `review`, `walkthrough`, `html`, `hotfix`, `triage`, `prune`, `e2e`. Space (or equivalent) toggles; Enter confirms. Default: nothing selected (= default layers only: macro+meso+micro).
- `all-optional` may be a row that selects every pack, or omitted because the checklist makes it redundant. Do not keep the slash-separated `Prompt.ask` list.
- `--packs` for scripts is unchanged (`none` / `all-optional` / comma-separated names).
- Non-TTY: no prompt, default-only (no optionals).
- Do not persist the selection in `config.toml`.
- Stay on Typer + Rich if a checkbox list can be built without a new framework. A small extra like `questionary` is OK; do not add Textual.
- Tests pin that the TTY helper is invoked (mock the TUI, not the rendered glyphs) and that toggling `product`+`pr` installs those two packs only. Do not add tests that only assert help/prompt string values.
- `CHANGELOG.md` `[Unreleased]`. Specs api/architecture one-liners if they still describe the `Prompt.ask` comma-box.

### Defensive Exclusions
- Do not change pack membership, the agent picker, libref, `claim_remote`, JUDGE, or Gate 3 review/walkthrough bodies.
- Do not merge. Do not cut a release.
- Do not author or modify Product-layer flows; `flow_refs: []`.
- No Gherkin in this issue file.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-037`
- **Acceptance Criteria Tokens**: `AC-ADHOC-037-01`, `AC-ADHOC-037-02`
- **Data Model Entities**: `PackSelection` (existing; TTY input shape only)

## User Stories Ledger
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- **US-037-01**: As an operator running `deviate setup` on a TTY, I want one optional pack per row with Space to toggle and Enter to confirm so I can pick `product` and `pr` without a wrapping slash list. *(Ref: FR-ADHOC-037)*
- **US-037-02**: As a script author, I want `--packs` and non-TTY default-only behavior unchanged so CI and one-liners keep working. *(Ref: FR-ADHOC-037)*

## Acceptance Outline
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- **AO-037-01** *(Ref: AC-ADHOC-037-01, US-037-01)*: On a TTY, omitted `--packs` opens a checkbox list (one named optional pack per row). Default confirm installs none. Toggling `product` and `pr` then Enter installs those two packs only (product's three commands plus `deviate-pr`). Selection is not written to `config.toml`.
  - **Happy Path**: `deviate setup --agent pi` on a TTY shows the checklist; Enter with nothing checked writes macro+meso+micro only.
  - **Error Category**: Unknown `--packs` names still fail closed.
  - **Boundary Category**: Tests mock the TUI helper (invocation + returned picks), not rendered glyphs or help-string substrings.
- **AO-037-02** *(Ref: AC-ADHOC-037-02, US-037-02)*: `--packs` is unchanged. Non-TTY omitted `--packs` installs default-only and does not prompt.
  - **Happy Path**: `--packs pr,review` and `--packs all-optional` keep today's membership.
  - **Error Category**: Non-TTY without `--packs` does not hang waiting for keys.
  - **Boundary Category**: Agent picker, libref, `claim_remote`, pack membership, JUDGE, and Gate 3 bodies stay untouched.
<!-- `**Given**` / `**When**` / `**Then**` are forbidden here. -->

## Edge Cases and Boundaries
- Rich `Prompt.ask` remains for the agent picker and `claim_remote` only.
- `all-optional` stays a `--packs` token even if the TUI omits that row.
- Empty confirm and `--packs none` are the same install set.

## Performance Constraints
- L_max: the checkbox loop is keystroke-bound; setup init stays ≤ 500 ms before the first prompt.
- Throughput: no new subprocesses or config persistence for pack picks.

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/test_cli/test_setup.py` — TTY helper invoked when `--packs` omitted; mocked `product`+`pr` picks install those two packs only and do not write packs into `config.toml`. `tests/test_ui/test_checkbox.py` — Space on product then pr yields those two names.
- **Integration Sandbox Targets**: existing `--packs` tests in `TestSetupPacks` stay green.

## Demonstration Path
```bash
# Non-TTY / scripted path unchanged
TMP=$(mktemp -d) && cd "$TMP"
deviate setup --agent opencode --packs none
test ! -f .opencode/commands/deviate-pr.md

# TTY helper + product+pr install (mocked TUI)
pytest tests/test_cli/test_setup.py::TestSetupPacks tests/test_ui/test_checkbox.py -v
```
