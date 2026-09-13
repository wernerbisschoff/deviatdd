# Verification

How to prove the app works, beyond the test suite.

| Command | What it proves | What it does not prove | Environment | Evidence | Cleanup |
|---|---|---|---|---|---|
| `mise run verify:cli` | Installed `deviate` binary reports the `pyproject.toml` version; `--help` exits 0 | Any phase behavior | `uv sync` done | `cli: ok (x.y.z)` | None |
| `mise run verify:setup` | Non-interactive `deviate setup` provisions `.deviate/` + `.claude/commands` in a fresh dir (see `scripts/verify/setup`) | TTY prompts, global export, claim-remote push | `uv sync` done | `setup: ok` | Temp dir removed via trap |
| `mise run verify` | All of the above | Full phase lifecycle | Same as above | Both lines | Same as above |
| `mise run test-e2e` | Bats smoke suite against the installed binary | Agent-spawned phases (no live agent) | `uv tool install --editable .`, bats | bats TAP output | Per-test tmpdirs |
| `mise run integration` | Layer orchestration + init/export cycle via pytest (`tests/test_integration/`) | Live-agent phases (mocked workspaces only) | `uv sync` done | pytest summary | pytest tmp_path |

`mise run check` covers lint + format only. `mise run test` covers pytest only.
