# Design — Interactive Setup and Production Config Tidy

Epic `006-setup-interactive-config` · Feature Slug `setup-interactive-config` · Phase `RESEARCH`

## Recommended Architecture

`deviate setup` stays the single consumer bootstrap command. When the operator omits a choice flag, setup asks for that choice on a TTY and applies a documented default in non-interactive sessions. The already-shipped agent prompt (`_prompt_agent_selection`) remains the backend picker. A new pack prompt asks which optional command packs to add on top of a hard-coded default set. Command install stops writing every `discover_commands()` stem; it writes only the commands in the resolved pack set, plus the shared `deviatdd` skill whenever any default layer pack is present.

Pack membership is a code-owned map keyed by command stem, not the buggy frontmatter `category` strings. Default packs are the four layers: product (`deviate-flows`, `deviate-architecture`, `deviate-release`), macro (`deviate-explore`, `deviate-research`, `deviate-prd`, `deviate-shard`, `deviate-adhoc`, `deviate-constitution`, `deviate-init`), meso (`deviate-plan`, `deviate-tasks`), micro (`deviate-red`, `deviate-green`, `deviate-judge`, `deviate-refactor`, `deviate-execute`). Optional packs are one command each: `merge`, `pr`, `review`, `walkthrough`, `html`, `hotfix`, `triage`, `prune`, `e2e`. Optional packs stay uninstalled unless the operator selects them (interactive prompt or `--packs`). Non-interactive setup without `--packs` installs only the default set.

Generated `.deviate/config.toml` becomes an allowlist dump, not `DeviateConfig.model_dump()` of every field. Always persist `base_branch` and `claim_remote`. Top-level `profile` becomes a real micro default: `Literal["full", "fast"]` with default `"full"`. `deviate micro run --profile` keeps its CLI override; when the flag is omitted, the runner reads the config value (invalid or legacy `"default"` coerces to `"full"`; legacy `"secure"` stays an internal alias that keeps JUDGE and skips REFACTOR). Do not persist `"default"` as a fourth profile. `use_libref` is omitted from generated config, governance seeds, and composed command bodies unless setup was invoked with `--libref`. PATH detection no longer auto-enables libref. The `[agent]` table always writes `backend` (and `timeout`); it writes `transport` only for `pi` / `omp`; it never writes `pi_rpc` on a fresh dump; Codex still seeds `[models].default = gpt-5.6-luna` and `[agent].reasoning_effort = high` when those keys are empty.

ISS-ADH-030 stays BACKLOG. This epic does not reopen gitignore-all-of-`.deviate`, Graphite removal, timeout consolidation, or install-to-all-agents. Per-agent install and Graphite deletion already shipped on `main` (2.23.1 / CHANGELOG). A new adhoc issue owns this slice and lists `coordinates_with: [ISS-ADH-030]`.

**Module Surface:**
- **Modify** `src/deviate/cli/__init__.py` — pack prompt + `--packs`; allowlist TOML dump; libref gated on `--libref` only; `[agent]` key filter by backend; stop `_apply_governance` libref upsert unless opted in.
- **Modify** `src/deviate/state/config.py` — `DeviateConfig.profile` becomes `Literal["full","fast"] = "full"`; keep `use_libref` as an in-memory optional (default False) that is not serialized unless True and opted in.
- **Modify** `src/deviate/core/commands.py` — pack map + `discover_commands(packs=...)` / filter helper. Do not rewrite frontmatter `category` strings in this slice.
- **Modify** `src/deviate/cli/micro.py` — `--profile` default resolution reads config when the CLI value is the implicit default.
- **Modify** `src/deviate/prompts/core/core.md` — move invariant 7 (libref mandate) behind a compose-time overlay so default installs carry no libref token.
- **Modify** `src/deviate/prompts/assembly.py` (if auto-path composition also injects `core.md`) so the same overlay gate applies.
- **Keep** Codex Luna / reasoning upserts (`_apply_codex_setup_defaults`, `CODEX_DEFAULT_MODEL`).
- **Add** tests in `tests/test_cli/test_setup.py` and `tests/test_state/test_config.py` (and a profile-default test in `tests/test_cli/test_micro.py` if the runner wiring needs it).
- **Modify** `CHANGELOG.md` `[Unreleased]`.
- **Do not modify** ISS-ADH-030 ACs; do not merge PR #125.

**Rationale:** Explore shows setup already isolates a single agent and already prompts for backend + claim_remote (`src/deviate/cli/__init__.py`). The remaining production-cleanliness gaps are (1) install-everything-by-default via `discover_commands()`, (2) `profile = "default"` which `resolve_profile` rejects, (3) unconditional libref in config + `core.md` + `libref_seed.md`, and (4) `model_dump()` writing `pi_rpc` / `transport` for every backend. An allowlist serializer plus a code-owned pack map is the smallest change that matches the existing Typer/Rich/Pydantic stack and the four-layer constitution.

## Options Matrix

| Option | Complexity | Testability | Constitutional Alignment | Reversibility | Blast Radius | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Option A: Rich-only interactive (agent + optional-pack Prompt) + code-owned pack map + allowlist TOML dump + `profile` as micro default `full\|fast` + `--libref`-only libref | M | H | Aligned | Easy | Module | Recommended |
| Option B: Add `questionary` checkbox UI + persist `[packs]` in config.toml + nest `[profile] default` | H | M | Tension | Hard | System | Rejected |
| Option C: Trust frontmatter `category`/`layer` to decide packs; keep `DeviateConfig.model_dump()` | L | L | Tension | Easy | Module | Rejected |
| Option D: Remove `profile` key entirely; keep install-all; only strip Pi keys | L | M | Tension | Easy | Local | Rejected |

## Rejected Options

- **Option B: questionary + persisted pack list + nested `[profile]`** — Constitution §2 names Typer + Rich as the CLI stack. A new prompt library is an undeclared dependency. Persisting installed packs in config.toml is extra scope the operator did not request; pack choice is a setup-time install filter, not a runtime routing key. Nested `[profile]` duplicates the unused `ProfileConfig` without making the existing top-level key truthful.
- **Option C: trust frontmatter categories** — Explore File Registry shows `deviate-red.md` `category: deviattd-macro-layer` with `layer: micro`, and `deviate-prune.md` misspells `deviattd`. The operator directed pack membership "by layer intent, not the buggy category strings."
- **Option D: remove profile only, keep install-all** — Leaves the "install everything by default" leak and the libref leak that the problem statement names. Removing the key is a valid profile strategy in isolation, but the recommended option makes the same key mean the micro default so `deviate micro run` can honor a production config.

## Design Trade-Offs

| Decision | Trade-off | Why This Side |
| :--- | :--- | :--- |
| Code-owned pack map instead of frontmatter `category` | Explicit, testable membership vs. self-describing files | Explore documents mismatched `category`/`layer` (`deviate-red.md`); operator directed layer-intent packs |
| Default packs always on; optional packs off unless selected | Smaller default install vs. "batteries included" | Operator: "Do not install optional packs unless the user selects them" |
| Rich `Prompt.ask` for optional packs (`none` / comma-separated / `all-optional`) | No new dependency vs. checkbox UX | Constitution §2 Typer+Rich; existing `_prompt_agent_selection` already uses `Prompt.ask` |
| `--packs` flag for non-interactive selection | Scriptable CI vs. another prompt | Typer prompt tutorial prefers options so scripts stay non-interactive |
| `profile` kept and typed `full\|fast` (default `full`) | Truthful config vs. deleting the key | Operator allowed either; making it the micro default reuses `resolve_profile` and the unused `ProfileConfig` value set |
| Legacy `profile = "default"` coerces to `full` at read time | Tolerant load vs. hard fail | Existing `.deviate/config.toml` in this repo still has `profile = "default"`; loaders use raw TOML, not `DeviateConfig.model_validate` |
| `use_libref` omitted unless `--libref` | Clean consumer config vs. PATH auto-detect convenience | Operator: "If setup is run WITHOUT `--libref`, there must be no libref mention" |
| Libref mandate extracted from always-on `core.md` into a compose overlay | Default installs have no libref token vs. one-line core invariant | `compose_command_body` prepends `core.md` to every installed command (`src/deviate/core/commands.py`) |
| `[agent]` allowlist: always `backend`+`timeout`; `transport` only for `pi`/`omp`; never write `pi_rpc`; Codex `reasoning_effort` | Tidy TOML vs. dumping the full Pydantic model | Operator: do not write `pi_rpc` or `transport = "rpc"` unless backend is `pi` or `omp` |
| ISS-ADH-030 stays BACKLOG; new issue coordinates | Avoid stale ACs vs. reopening 030 | Graphite already gone; per-agent install already shipped (explore File Registry) |

## Contrarian Viewpoints

- **(Code-owned pack map)** — A later command added under `src/deviate/prompts/commands/` is invisible to setup until the map is updated. Mitigation: unit-test that every packaged stem is classified as default, optional, or explicitly ignored; fail CI on an unclassified stem.
- **(Optional packs off by default)** — Operators who currently rely on `setup` writing `/deviate-pr` and `/deviate-review` will lose those files until they re-run with `--packs`. Mitigation: CHANGELOG `[Unreleased]` names the default set and the `--packs` / prompt escape hatch.
- **(profile as micro default)** — Reading config when `--profile` is omitted can surprise a script that assumed the hard-coded Typer default `"full"` regardless of a leftover `profile = "fast"` in a consumer file. Mitigation: coerce unknown values to `"full"`; document that a valid config `profile` is the micro default.
- **(strip libref from core.md)** — Agents in a `--libref` workspace still need the mandate. Mitigation: compose the overlay only when `use_libref` is opted in; `_apply_governance` upserts `libref_seed.md` only on that path.
- **(do not write transport for Codex)** — A future Codex RPC path would have no persisted transport key. Mitigation: `AgentConfig._normalize_transport` already defaults non-pi/omp to `cli` when the key is absent; omit-is-correct.

## Risk Register

| Risk ID | Risk | Likelihood | Impact | Mitigation | Owner | Source Anchor |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| RSK-001 | New command stem is not in the pack map and is silently skipped | M | M | CI test: every `discover_commands()` stem is classified | commands | `src/deviate/core/commands.py` `discover_commands` |
| RSK-002 | Existing tests assert `setup --agent X` installs `deviate-red.md` and every Codex command skill | H | H | Keep default-pack install of micro commands; update Codex tests to assert default set, not all 26 | setup tests | `tests/test_cli/test_setup.py` |
| RSK-003 | `DeviateConfig.profile` type change breaks tests that set `profile="test"` or assert `"default"` | H | M | Update `tests/test_state/test_config.py`; coerce legacy `"default"` at read | config | `tests/test_state/test_config.py` `assert config.profile == "default"` |
| RSK-004 | `_apply_governance` still upserts libref into CLAUDE.md/AGENTS.md on a no-`--libref` run | M | H | Gate the `libref_seed.md` upsert on the same `--libref` flag | setup | `src/deviate/cli/__init__.py` `_apply_governance` |
| RSK-005 | Composed commands still contain `core.md` invariant 7 after install | M | H | Overlay gate in `compose_command_body` / `load_template` | commands | `src/deviate/prompts/core/core.md` |
| RSK-006 | `_write_agent_block_to_config` leaves stale `pi_rpc`/`transport` when switching an existing file to Codex | M | M | When writing a non-pi/omp backend, strip those keys from the `[agent]` table | setup | `src/deviate/cli/__init__.py` `_write_agent_block_to_config` |
| RSK-007 | ISS-ADH-030 operators confuse this slice with gitignore-all-of-`.deviate` | L | M | New issue `coordinates_with: [ISS-ADH-030]`; 030 stays BACKLOG | adhoc | `specs/adhoc/issues/030-config-rework.md` |
| RSK-008 | Codex Luna / reasoning upserts get clobbered by allowlist rewrite | L | H | Keep `_apply_codex_setup_defaults` if-empty semantics; pin existing no-clobber tests | setup | `tests/test_cli/test_setup.py` `test_setup_codex_does_not_clobber_custom_models_default` |

## Constitutional Alignment Audit

| Constitutional Clause | Architectural Decision | Alignment | Notes |
| :--- | :--- | :--- | :--- |
| "Four-Layer Architecture: Product … Macro … Meso … Micro" (§1) | Default packs are exactly those four layers | Aligned | Pack map follows layer intent, not frontmatter `category` |
| "Config-Driven Model Routing" + Codex Luna / reasoning_effort seeding (§1) | Keep `_apply_codex_setup_defaults` if-empty; do not clobber user models | Aligned | Existing tests stay |
| "Config: TOML via `.deviate/config.toml`; `[models]` section" (§2) | Allowlist dump still writes TOML; `[models]` only when Codex seeds or user already has it | Aligned | No new store |
| "Framework: Typer (CLI entry points) with Rich for terminal I/O" (§2) | Pack prompt uses existing `rich.prompt.Prompt`; `--packs` is a Typer option | Aligned | No new prompt library |
| "No persistent database runtime (all state tracked in JSONL ledgers and TOML config)" (§2) | Pack choice is a setup-time install filter; not a new ledger | Aligned | Config remains TOML |
| "Test command: `pytest tests/ -v`" (§3) | Pin behavior with pytest in `tests/test_cli/test_setup.py` and `tests/test_state/test_config.py` | Aligned | |
| "CHANGELOG.md updated under `[Unreleased]` for user-visible changes" (§5) | Required in the implementation commit | Aligned | Default-pack change is user-visible |

## Pending HITL Decisions

<!-- HITL_DECISIONS -->
<!-- User already directed this work and approved Gate 1. Rows are RESOLVED. -->

| Decision ID | Question | Context | Impact | Recommended Resolution | Status |
|---|---|---|---|---|---|
| `HITL-001` | Keep top-level `profile` as the micro default (`full`/`fast`) instead of deleting the key? | Explore: `DeviateConfig.profile` is `"default"` and `resolve_profile` rejects it. Operator allowed either remove or make it mean the micro default. | Delete = CLI-only `--profile`. Keep = config drives `micro run` default. | Keep and type as `full\|fast`, default `full`; coerce legacy `"default"` to `full`. Legacy `"secure"` stays an internal alias. | `RESOLVED` |
| `HITL-002` | Is `release` a default product command or an optional pack? | Operator listed `release` once under optional packs and once under product (flows, architecture, release). | Changes whether `deviate-release.md` is installed by default. | Default product pack (layer-intent list). | `RESOLVED` |
| `HITL-003` | Leave ISS-ADH-030 BACKLOG and file a new issue? | 030 ACs cover gitignore-all-of-`.deviate`, Graphite, timeout consolidation, install-to-all-agents — Graphite gone, per-agent install shipped. | Reopening 030 would pull stale ACs into this PR. | New adhoc issue; `coordinates_with: [ISS-ADH-030]`. | `RESOLVED` |
| `HITL-004` | Disable PATH auto-detect for libref so only `--libref` opts in? | `_detect_libref()` currently sets `use_libref` when `libref` is on PATH. | Machines with `libref` installed would stop getting the key/seed unless they pass `--libref`. | `--libref` is the only opt-in. | `RESOLVED` |

**Gate Rule**: If ANY row has Status `PENDING`, the `deviate prd pre` command will halt and display this table to the human operator.

## Source Registry

| ID | Type | Source / Path | Relevance Note |
| :--- | :--- | :--- | :--- |
| SRC-001 | Explore_MD | `specs/006-setup-interactive-config/explore.md` | Factual inventory of setup, config, packs, profile, libref |
| SRC-002 | Codebase_File | `src/deviate/cli/__init__.py` | `setup`, `_scaffold_dotfiles`, `_apply_governance`, install helpers |
| SRC-003 | Codebase_File | `src/deviate/state/config.py` | `DeviateConfig`, `AgentConfig`, unused `ProfileConfig` |
| SRC-004 | Codebase_File | `src/deviate/core/profile.py` | `resolve_profile` full/fast |
| SRC-005 | Codebase_File | `src/deviate/core/commands.py` | `discover_commands` unfiltered glob |
| SRC-006 | Codebase_File | `src/deviate/prompts/core/core.md` | Always-on libref mandate |
| SRC-007 | Constitution | `specs/constitution.md` | Four-layer architecture; Typer+Rich; TOML config; Codex seeding |
| SRC-008 | Manifest | `specs/adhoc/issues/030-config-rework.md` | Stale BACKLOG sibling |

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | AWAITING_HITL_GATE_1 |
| FEATURE_SLUG | setup-interactive-config |
| NEXT_ACTION | Human reviews design.md + data-model.md, then invokes the prd skill |
