# Contributing to DeviaTDD

Thanks for your interest in contributing. DeviaTDD is a governance-first
project: the contracts in `specs/constitution.md`, `specs/DeviaTDD-api.md`,
and `specs/DeviaTDD-architecture.md` are authoritative. This guide explains
how to land a change within that framework.

> **Read first**: [`specs/constitution.md`](specs/constitution.md) is the
> governance source of truth. The rules below restate the parts external
> contributors actually need; when in doubt, the constitution wins.

---

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md) (v2.1).
By participating, you agree to its terms.

---

## Ways to contribute

| Contribution | Where it goes |
|---|---|
| Bug reports | [GitHub Issue](../../issues) using the **Bug report** template |
| Feature requests | [GitHub Issue](../../issues) using the **Feature request** template |
| Code, docs, tests | Pull request (see workflow below) |
| Security vulnerabilities | See [`SECURITY.md`](SECURITY.md) — **do not** file a public issue |

Issues labeled **`good first issue`** are scoped for first-time
contributors.

---

## Development setup

DeviaTDD targets **Python 3.13+** and uses [`uv`](https://docs.astral.sh/uv/)
for dependency management and [`mise`](https://mise.jdx.dev/) as a task
runner.

```bash
# Clone your fork
git clone https://github.com/<you>/deviatdd.git
cd deviatdd

# Install dependencies + project (editable) + dev extras
uv sync --extra dev

# Install git hooks (pre-commit + pre-push)
mise run setup

# Sanity-check the install
uv run deviate --version
uv run pytest tests/ -q          # unit tests
bats tests/e2e/                  # CLI smoke suite (requires `bats` binary)
```

The full task surface is defined in [`.mise.toml`](.mise.toml). The
common ones:

| Task | Purpose |
|---|---|
| `mise run test` | pytest unit tests |
| `mise run test-e2e` | bats CLI smoke suite |
| `mise run lint` | `ruff check` |
| `mise run format` / `format-check` | `ruff format` write / verify |
| `mise run check-types` | static type checks |
| `mise run check` | lint + format-check bundle (pre-commit gate) |
| `mise run fix` | lint `--fix` + format |
| `mise run help` | list every task with description |

---

## Branch strategy

Per [`specs/constitution.md` §4](specs/constitution.md#4-development-workflow):

- Features: `feat/<epic-slug>/<issue-slug>`
- Hotfixes: `fix/<short-description>`
- All commits reference a task ID (e.g. `T001`) in the conventional
  commit scope.

Direct commits to `main` are acceptable for **docs-only or CI-only
changes** that do not touch `src/` or `specs/`. Anything else goes
through a feature branch.

---

## Commit convention

```
<type>(<scope>): <description>

[optional body, wrapped at 72 chars]

[optional footer, e.g. Fixes #N, Refs #N]
```

| Type | Use for |
|---|---|
| `feat` | New user-facing capability |
| `fix` | Bug fix |
| `test` | Test-only change |
| `refactor` | Internal cleanup, no behavior change |
| `docs` | Docs-only change |
| `chore` | Tooling, CI, deps — no production code change |

Scope is typically the task ID (`T001`) or a tight subsystem
(`cli`, `micro`, `prompts`, `init`). Body lines wrap at 72 characters.

> **Never** use `git commit --no-verify` or `git push --no-verify`. The
> pre-commit (`mise run check`) and pre-push (`mise run test`) hooks
> enforce the same gates CI runs.

---

## Pull request workflow

1. **Open or find an issue first.** Even small fixes benefit from a
   tracking issue with an acceptance criterion.
2. **Branch from `main`** using the convention above.
3. **Develop in tight commits.** Each commit should leave the tree in
   a passing state.
4. **Run the gates locally** before pushing:
   ```bash
   mise run check         # lint + format
   mise run test          # pytest
   mise run test-e2e      # bats (if CLI behavior changed)
   ```
5. **Open the PR** using [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md).
   Tick the phase checkboxes (RED / GREEN / REFACTOR / Non-TDD) and the
   spec-alignment checkboxes that apply.
6. **Address review feedback in new commits** — not force-pushes
   during review — unless the reviewer asks for a rebase.
7. **Squash or rebase** before merge once approved. `main`'s history
   must stay linear.

A maintainer performs **HITL Gate 3** (final merge audit) before merge;
see [`specs/DeviaTDD-architecture.md`](specs/DeviaTDD-architecture.md) for
the merge-audit contract.

---

## Test discipline

The Micro-layer TDD loop is RED → GREEN → JUDGE → REFACTOR:

- **RED**: the failing test must fail with `AssertionError` or
  `NotImplementedError`. A syntax error or import-time crash is
  rejected; fix the test first.
- **GREEN**: minimum implementation to make the test pass. No drive-bys.
- **JUDGE**: the Tamper Guard verifies that GREEN did not edit files
  outside `src/**/*.py`. Any unauthorized mutation triggers an
  immediate rollback.
- **REFACTOR**: polish with no behavior change. Tests must re-pass.

Coverage target is **≥ 80%** (`specs/constitution.md` §3).

> **Performance note** — `src/deviate/cli/micro.py::_run_pytest` invokes
> pytest as a subprocess (~5 s). Tests that call CLI commands hitting
> this function **must** mock `_run_pytest` with a
> `subprocess.CompletedProcess` fixture so the full suite stays under
> 30 s. See `tests/conftest.py` for the canonical pattern.

> **Git isolation note** — every test that runs `git` must use
> `cwd=<tmp_git_repo>` + `env=_git_env()`. Production code must use
> `src/deviate/core/_shared.py::git_env`. Micro-layer agents **must
> never** run branch-mutating git commands — branch creation lives in
> `src/deviate/cli/feature.py::_create_feature_branch`.

---

## Spec alignment

The specs are part of the contract. If your change touches any of:

- **CLI surface** (`deviate <subcommand>`) → update
  [`specs/DeviaTDD-api.md`](specs/DeviaTDD-api.md) in the **same commit**.
- **Phase workflow, routing, or layer semantics** → update
  [`specs/DeviaTDD-architecture.md`](specs/DeviaTDD-architecture.md) in
  the **same commit**.
- **Governance / invariants** (HITL gates, append-only ledger, Tamper
  Guard, model tiering) → update
  [`specs/constitution.md`](specs/constitution.md) in the **same commit**.
- **Anything user-visible** → add a bullet under `[Unreleased]` in
  [`CHANGELOG.md`](CHANGELOG.md) in the **same commit**.

The PR template's "Spec alignment" checklist enforces this. A PR that
updates code without updating the matching spec will be asked for
revisions.

---

## Slash commands and prompt edits

Slash-command templates live under `src/deviate/prompts/` and are
installed as package resources to `<workdir>/.<agent>/commands/<name>.md`
by `deviate setup`. **Do not** edit
`~/.config/opencode/skills/` (or similar mirrors) — that directory is a
read-only install target. Edit the source in
`src/deviate/prompts/commands/<name>.md`.

If you are adding a new command, follow the existing layer routing in
`src/deviate/prompts/assembly.py::_LAYER_MAP` (macro / meso /
micro) and update `specs/DeviaTDD-api.md` §"Slash commands" accordingly.

---

## Style guide (beyond ruff)

- Prefer **boring, explicit code** over clever abstractions. The
  project favors clarity over brevity in the hot paths.
- Match existing conventions in the file you're editing — local
  consistency outranks personal preference.
- Public functions get a one-line docstring; complex ones get full
  NumPy-style docstrings.
- Module-level side effects are forbidden. The CLI is the only entry
  point.
- No bare `print()` in production code — use `rich.console.Console` or
  return values.

`ruff` enforces formatting and lint; if you disagree with a rule,
change `.ruff.toml` or `pyproject.toml`'s `[tool.ruff]` section and
explain why in the PR.

---

## AI-assisted contributions

DeviaTDD's own micro-layer agents may produce code that lands here.
That code is held to the **same** standards as human-written code:

- It must originate from a tracked task in `specs/issues.jsonl` /
  `specs/**/tasks.jsonl`.
- It must pass the Tamper Guard and the human merge audit (Gate 3).
- It must include a test that fails before the change and passes after.

If you are submitting AI-generated code, declare it in the PR
description. We will not reject AI-assisted work on principle, but we
do require the same traceability.

---

## Getting help

- **General questions**: open a [GitHub Discussion](../../discussions)
  (once enabled) or a `question` issue.
- **Bugs / features**: use the issue templates.
- **Security**: [`SECURITY.md`](SECURITY.md).
- **Conduct issues**: see the enforcement section of
  [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

---

## Release process (for maintainers)

1. Update `CHANGELOG.md` — move `[Unreleased]` bullets into a dated
   `[X.Y.Z]` section.
2. Bump `version` in `pyproject.toml`.
3. `git tag -s vX.Y.Z -m "Release vX.Y.Z"` (signed tag).
4. `git push origin main --follow-tags`.
5. CI publishes to PyPI via trusted publishing once the workflow is
   enabled.
