# Data Model — Interactive Setup and Production Config Tidy

Epic `006-setup-interactive-config` · Feature Slug `setup-interactive-config` · Phase `RESEARCH`

## Entity Definitions

### CommandPack
- **Source-of-truth**: code-owned map in `src/deviate/core/commands.py` (not frontmatter `category`)
- **Lifecycle owner**: `deviate setup` install path
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  | :--- | :--- | :--- | :--- |
  | `name` | `str` | one of default layer names or optional pack names | explore.md Problem Definition |
  | `kind` | `Literal["default","optional"]` | default = product/macro/meso/micro; optional = merge/pr/review/walkthrough/html/hotfix/triage/prune/e2e | explore.md Problem Definition |
  | `commands` | `tuple[str, ...]` | each value is a `deviate-*` stem from `discover_commands()` | `src/deviate/core/commands.py` |
- **Invariants**:
  - Every packaged `*.md` stem is classified as default, optional, or explicitly ignored. Unclassified stems fail a unit test.
  - Membership is by layer intent, not `category:` frontmatter (`deviate-red.md` is micro despite `category: deviattd-macro-layer`).
  - Optional packs install if and only if selected.

### PackSelection
- **Source-of-truth**: setup invocation (flags + TTY answers). Not persisted in `config.toml`.
- **Lifecycle owner**: `deviate setup`
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  | :--- | :--- | :--- | :--- |
  | `default_packs` | `tuple[str, ...]` | always `("product","macro","meso","micro")` | explore.md Problem Definition |
  | `optional_packs` | `tuple[str, ...]` | subset of optional names; empty when omitted | explore.md Problem Definition |
  | `include_deviatdd_skill` | `bool` | `true` when any default pack is installed | `src/deviate/cli/__init__.py` `_install_deviatdd_skill` |
- **Invariants**:
  - Non-interactive + no `--packs` → `optional_packs == ()`.
  - Interactive TTY + no `--packs` → prompt; default answer is `none`.
  - `--packs none` or empty → defaults only. `--packs all-optional` → every optional pack. `--packs pr,review` → those names only.

### DeviateConfig (generated TOML)
- **Source-of-truth**: `.deviate/config.toml`
- **Lifecycle owner**: `_scaffold_dotfiles` / allowlist serializer
- **Attributes** (serialized when present):
  | Attribute | Type | Invariant | Source Anchor |
  | :--- | :--- | :--- | :--- |
  | `profile` | `Literal["full","fast","secure"]` | default `"full"`; never `"default"` on write | `src/deviate/core/profile.py` `_PROFILE_DEFAULTS` |
  | `timeout_seconds` | `int` | `gt=0`, default 1800 | `src/deviate/state/config.py` |
  | `agent_export_mode` | `Literal["local","global"]` | default `"local"` | `src/deviate/state/config.py` |
  | `base_branch` | `str` | `min_length=1`, default `"main"` | `src/deviate/state/config.py` |
  | `claim_remote` | `bool` | default `True` | `src/deviate/state/config.py` |
  | `use_libref` | `bool` | serialized only when setup `--libref` | explore.md Problem Definition |
  | `agent` | `AgentBlock` | see below | `src/deviate/state/config.py` `AgentConfig` |
  | `models` | `dict[str,str]` | written for Codex seed or preserved user table | constitution §1 Codex seeding |
- **Invariants**:
  - Fresh dump never contains `profile = "default"`.
  - Fresh dump without `--libref` contains no `use_libref` key and no `libref` substring.
  - `base_branch` and `claim_remote` always persist.

### AgentBlock
- **Source-of-truth**: `.deviate/config.toml` `[agent]`
- **Lifecycle owner**: `_scaffold_dotfiles` / `_write_agent_block_to_config`
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  | :--- | :--- | :--- | :--- |
  | `backend` | `Literal["opencode","claude","droid","pi","omp","codex"]` | required; Codex persists `"codex"` | `src/deviate/core/agent.py` `AGENT_TO_BACKEND` |
  | `timeout` | `int` | `gt=0`, default 600 | `src/deviate/state/config.py` |
  | `transport` | `Literal["rpc","cli"]` | serialized only when `backend` in `{"pi","omp"}` | explore.md Problem Definition |
  | `reasoning_effort` | `ReasoningEffort \| None` | Codex only; seed `"high"` if empty | `CODEX_DEFAULT_REASONING_EFFORT` |
  | `pi_rpc` | `bool` | never written on a fresh dump; still accepted on read for legacy | `AgentConfig._normalize_transport` |
- **Invariants**:
  - Non-pi/omp dumps contain no `pi_rpc` and no `transport` key.
  - Switching an existing file to a non-pi/omp backend strips `pi_rpc` and `transport`.
  - Codex if-empty seed does not clobber a user-set `models.default` or `reasoning_effort`.

### ExecutionProfile
- **Source-of-truth**: `src/deviate/core/profile.py` + optional top-level `profile` in config
- **Lifecycle owner**: `deviate micro run`
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  | :--- | :--- | :--- | :--- |
  | `name` | `Literal["full","fast","secure"]` | only these three | `src/deviate/core/profile.py` |
  | `skip_judge` | `bool` | full=False, fast=True, secure=False | `_PROFILE_DEFAULTS` |
  | `skip_refactor` | `bool` | full=False, fast=True, secure=True | `_PROFILE_DEFAULTS` |
- **Invariants**:
  - CLI `--profile` overrides config.
  - Missing / `"default"` / unknown config value coerces to `"full"`.
  - `"default"` is not a valid write value.

### LibrefOptIn
- **Source-of-truth**: presence of `--libref` on the setup invocation
- **Lifecycle owner**: `deviate setup`
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  | :--- | :--- | :--- | :--- |
  | `enabled` | `bool` | `True` only when `--libref` | explore.md Problem Definition |
- **Invariants**:
  - `enabled=False` → no `use_libref` key, no `libref_seed.md` upsert, no libref overlay in composed commands or the `deviatdd` skill.
  - PATH detection (`_detect_libref`) does not flip `enabled`.
  - The packaged `deviatdd` SKILL.md body already contains no `libref` token; keep that.

## Relationship Graph

| From | Relationship | To | Cardinality | On-Delete | On-Cascade | Source Anchor |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `PackSelection` | includes | `CommandPack` | 1:N | drop optional packs | none | explore.md Problem Definition |
| `CommandPack` | installs | command stem files | 1:N | skip file | none | `src/deviate/core/commands.py` `install_command` |
| `PackSelection` | provisions | `deviatdd` skill | 1:0..1 | skip skill | none | `src/deviate/cli/__init__.py` `_install_deviatdd_skill` |
| `DeviateConfig` | embeds | `AgentBlock` | 1:1 | rewrite table | strip dead keys | `src/deviate/state/config.py` |
| `DeviateConfig.profile` | defaults | `ExecutionProfile` | 1:1 | coerce to `full` | none | `src/deviate/core/profile.py` |
| `LibrefOptIn` | gates | `use_libref` key + seed + overlay | 1:0..1 | omit all mentions | none | `src/deviate/cli/__init__.py` `_apply_governance` |

## Schema Tables

Pydantic / TOML shapes (constitution §2: Python 3.13, Pydantic, TOML).

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field

PackKind = Literal["default", "optional"]
ProfileName = Literal["full", "fast", "secure"]
BackendName = Literal["opencode", "claude", "droid", "pi", "omp", "codex"]
OptionalPackName = Literal[
    "merge", "pr", "review", "walkthrough", "html",
    "hotfix", "triage", "prune", "e2e",
]
DEFAULT_PACKS: tuple[str, ...] = ("product", "macro", "meso", "micro")

class CommandPack(BaseModel):
    name: str
    kind: PackKind
    commands: tuple[str, ...]
    model_config = {"extra": "forbid"}

class PackSelection(BaseModel):
    default_packs: tuple[str, ...] = DEFAULT_PACKS
    optional_packs: tuple[str, ...] = ()
    include_deviatdd_skill: bool = True
    model_config = {"extra": "forbid"}

class AgentBlock(BaseModel):
    backend: BackendName
    timeout: int = Field(default=600, gt=0)
    transport: Optional[Literal["rpc", "cli"]] = None  # persist only for pi/omp
    reasoning_effort: Optional[Literal["minimal", "low", "medium", "high", "xhigh"]] = None
    model_config = {"extra": "forbid"}

class DeviateConfig(BaseModel):
    profile: ProfileName = "full"
    timeout_seconds: int = Field(default=1800, gt=0)
    agent_export_mode: Literal["local", "global"] = "local"
    base_branch: str = Field(default="main", min_length=1)
    claim_remote: bool = True
    use_libref: bool = False  # serialized only when True and --libref
    agent: AgentBlock
    models: dict[str, str] = Field(default_factory=dict)
    model_config = {"extra": "forbid"}
```

Allowlist serializer (not `model_dump()` of unset/forbidden keys):

```toml
# Execution profile for `deviate micro run` when --profile is omitted
profile = "full"
timeout_seconds = 1800
agent_export_mode = "local"
base_branch = "main"
claim_remote = true

[agent]
backend = "codex"
timeout = 600
reasoning_effort = "high"

[models]
default = "gpt-5.6-luna"
```

Pi/OMP `[agent]` may add `transport = "rpc"`. A no-`--libref` dump contains no `use_libref` line.

## State Transitions

### Setup pack resolution

| From | Event | To | Guard | Side effect |
| :--- | :--- | :--- | :--- | :--- |
| flags omitted, TTY | operator answers agent + packs | `PackSelection(optional=chosen)` | `is_interactive()` | install default ∪ chosen |
| flags omitted, no TTY | no prompt | `PackSelection(optional=())` | not `is_interactive()` | install default only; agent still required (`NO_AGENT_SELECTED` if missing) |
| `--agent X` | skip agent prompt | agent = X | `X in AGENT_CHOICES` | persist `[agent].backend` |
| `--packs pr,review` | skip pack prompt | optional = (pr, review) | names in optional set | install default ∪ those |
| `--libref` | libref opt-in | `LibrefOptIn(enabled=True)` | flag present | write `use_libref = true`; upsert seed; compose overlay |
| no `--libref` | libref omitted | `LibrefOptIn(enabled=False)` | flag absent | no libref token in config, seeds, or installed bodies |

### Agent block rewrite

| From | Event | To | Guard | Side effect |
| :--- | :--- | :--- | :--- | :--- |
| no config | fresh scaffold | allowlist dump | — | write profile=full; backend-specific `[agent]` |
| existing config + `--agent codex` | upsert | backend=codex | Codex | seed Luna/high if empty; strip `pi_rpc`/`transport` |
| existing config + `--agent pi` | upsert | backend=pi | Pi/OMP | may write `transport = "rpc"`; do not invent `pi_rpc` |
| existing Codex models | setup --agent codex | unchanged models | `models.default` non-empty | no clobber |

### Profile resolution (`deviate micro run`)

| From | Event | To | Guard | Side effect |
| :--- | :--- | :--- | :--- | :--- |
| CLI `--profile P` | explicit flag | `resolve_profile(P)` | P in full/fast/secure | ignore config |
| no CLI profile | read config | `resolve_profile(cfg or "full")` | missing/`default`/invalid → `full` | skip_judge/skip_refactor tuple |

## Data Flow

```
operator
  │  deviate setup [--agent] [--packs] [--libref] [--no-claim-remote]
  ▼
setup()
  ├─ resolve agent (flag → existing backend → TTY prompt → NO_AGENT_SELECTED)
  ├─ resolve PackSelection (flag → TTY prompt → default-only)
  ├─ resolve LibrefOptIn (--libref only)
  ├─ allowlist-serialize .deviate/config.toml
  │     ├─ profile=full|fast|secure
  │     ├─ base_branch, claim_remote
  │     ├─ use_libref only if opted in
  │     └─ [agent] backend + timeout [+ transport iff pi/omp] [+ reasoning_effort iff Codex]
  ├─ _apply_governance (libref_seed iff opted in)
  ├─ install_command(stem) for each stem in selected packs
  └─ _install_deviatdd_skill (default packs)
          │
          ▼
compose_command_body()
  ├─ core.md (no libref mandate)
  └─ libref overlay iff LibrefOptIn.enabled

deviate micro run [--profile]
  ├─ CLI profile if explicitly passed
  └─ else config profile (coerce default/invalid → full)
        ▼
  resolve_profile() → (skip_judge, skip_refactor)
```

## Source Registry

| ID | Type | Source / Path | Relevance Note |
| :--- | :--- | :--- | :--- |
| SRC-001 | Explore_MD | `specs/006-setup-interactive-config/explore.md` | Current config, setup, pack, libref, profile facts |
| SRC-002 | Codebase_File | `src/deviate/state/config.py` | `DeviateConfig` / `AgentConfig` / `ProfileConfig` |
| SRC-003 | Codebase_File | `src/deviate/core/profile.py` | `resolve_profile` |
| SRC-004 | Codebase_File | `src/deviate/core/commands.py` | Unfiltered command discovery |
| SRC-005 | Codebase_File | `src/deviate/cli/__init__.py` | Setup serialization and install |
| SRC-006 | Constitution | `specs/constitution.md` | Four-layer packs; Typer+Rich; TOML; Codex seeds |
