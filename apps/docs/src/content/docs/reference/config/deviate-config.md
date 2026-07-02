---
title: "Deviate Config Schema"
description: "Reference table for the seven top-level keys and nested [agent] table fields of .deviate/config.toml, the per-workspace DeviaTDD configuration file."
doc_type: reference
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues: []
prev: config/starter-config.md
next: false
---

`.deviate/config.toml` is the per-workspace configuration file scaffolded by `deviate setup` (alias of `deviate init`). Its schema is declared in `src/deviate/state/config.py` as the `DeviateConfig` Pydantic model with `extra = "forbid"` — any unknown key fails validation at load time.

## File location

| Path | Scope | Owner |
|---|---|---|
| `<repo>/.deviate/config.toml` | Per-workspace | `deviate setup` |

Re-running `deviate setup` is idempotent; existing `[models]`, `[agent]`, and comment lines are preserved when `--graphite`, `--libref`, or `--agent` flags are passed.

## Top-level keys

| Key | Type | Default | Description |
|---|---|---|---|
| `profile` | `string` | `"default"` | Reserved preset profile name; the `DeviateConfig` model accepts any string but the scaffolded `#` comment advertises `"default"`, `"full"`, `"fast"`, `"secure"`. |
| `timeout_seconds` | `int` (`> 0`) | `300` | CLI inactivity timeout in seconds; rejected at load when `<= 0`. |
| `agent_export_mode` | `enum("local", "global")` | `"local"` | Where slash commands are exported — `"local"` writes to `<repo>/.<agent>/commands/`, `"global"` writes to `~/.<agent>/commands/`. |
| `agent` | `table` | (nested `[agent]` block) | See the `[agent]` table section below. |
| `models` | `table` | `{}` | Per-phase model overrides; see the `[models]` table section below. |
| `use_libref` | `bool` | `false` | Enable the `libref` CLI for offline documentation lookups across research and plan phases. |
| `graphite` | `bool` | `false` | Enable the `gt` Graphite CLI integration for stacked changes (`gt create`, `gt submit --stack`). |

## ` [agent]` table

| Key | Type | Default | Description |
|---|---|---|---|
| `backend` | `enum("opencode", "claude", "droid", "pi")` | `"opencode"` | The agent CLI binary that meso/micro layers spawn. Set via `deviate setup --agent <name>`; `factory` is normalised to `droid`. |
| `timeout` | `int` (`> 0`) | `600` | Agent invocation timeout in seconds; rejected at load when `<= 0`. |
| `pi_rpc` | `bool` | `false` | Opt-in RPC mode for Pi — spawns `pi --mode rpc --no-session` instead of `pi -p`. Ignored for non-Pi backends. |

The `[agent]` table is nested (`[agent]` header followed by `backend = "..."`), not dotted; the Pydantic model accepts the nested form only. The `AGENT_CHOICES` user-facing prompt adds `"factory"` (mapped to the `droid` backend) for selection during `deviate setup`.

## ` [models]` table

| Aspect | Behaviour |
|---|---|
| Key naming | Phase identifier — case-insensitive on read; the resolution function lower-cases both the phase and the dict keys before lookup. |
| Value format | Model ID string, e.g., `"opencode/deepseek-v4-flash"`. |
| Resolution order | (1) phase-specific key (e.g., `judge = "..."`), (2) `default` key, (3) `null` — the backend falls back to its native default. |
| Phase identifiers | Any string works as a key; the canonical set is `IDLE`, `EXPLORE`, `RESEARCH`, `PRD`, `SHARD`, `SPECIFY`, `PLAN`, `TASKS`, `RED`, `GREEN`, `YELLOW`, `JUDGE`, `REFACTOR`, `E2E`, `EXECUTE`, `HOTFIX`. |
| Backend support | `opencode` and `droid` accept the resolved ID via `--model <id>`; `claude` silently ignores the value; `pi` passes it through its CLI flags. |
| Lookup function | `resolve_phase_model(phase, models)` in `src/deviate/state/config.py:136`; load + resolve wrapper is `resolve_model_for_phase(phase, root)` at `:155`. |

## Validation rules

| Rule | Source | Failure mode |
|---|---|---|
| Top-level `extra` keys forbidden | `DeviateConfig.model_config = {"extra": "forbid"}` | Pydantic raises `ValidationError` at load. |
| `[agent]` `extra` keys forbidden | `AgentConfig.model_config = {"extra": "forbid"}` | Pydantic raises `ValidationError` at load. |
| `timeout_seconds > 0` | `Field(gt=0)` | Pydantic raises `ValidationError` at load. |
| `agent.timeout > 0` | `Field(gt=0)` | Pydantic raises `ValidationError` at load. |
| `agent.backend` literal | `Literal["opencode", "claude", "droid", "pi"]` | Pydantic raises `ValidationError` at load. |
| `agent_export_mode` literal | `Literal["local", "global"]` | Pydantic raises `ValidationError` at load. |
| `[models]` values are strings | Implicit via `dict[str, str]` | `resolve_model_for_phase` filters via `{k: str(v) for k, v in models.items()}` and returns `None` when non-dict. |

The TOML serializer in `src/deviate/cli/__init__.py:119` (`_dict_to_toml`) round-trips through `tomllib.loads()` before writing, so a broken generated file is caught at scaffold time.

## Example

```toml
# Preset config group: "default", "full", "fast", or "secure"
profile = "default"

# CLI inactivity timeout in seconds (must be > 0)
timeout_seconds = 300

# Agent export mode: "local" (project) or "global" (~/.claude/)
agent_export_mode = "local"

# Per-phase model overrides; key = phase name, value = model ID
[models]
default = "opencode/deepseek-v4-flash"
judge = "opencode/deepseek-v4-pro"

# Agent backend configuration
[agent]
backend = "opencode"
timeout = 600
pi_rpc = false

# Enable the libref CLI for offline documentation lookups
use_libref = false

# Enable Graphite CLI integration for stacked changes
graphite = false
```

The scaffolded file also includes `# ` annotations above each key; those comments live in `_CONFIG_TOML_COMMENTS` (`src/deviate/cli/__init__.py:84`) and are the primary inline documentation surface for operators editing the file by hand.

## See Also

- [How to run /deviate-init](/how-to/getting-started/init) — exercises `deviate setup`, which creates this file
- [Tutorial: Run Your First DeviaTDD Cycle](/tutorials/starter-first-run) — walks the full pipeline that reads these keys
- [Why Diátaxis: The Architecture Behind This Docs Site](/explanation/architecture/starter-architecture) — grounding for the schema-vs-ledger separation
