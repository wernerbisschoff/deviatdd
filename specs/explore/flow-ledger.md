# Exploration: Flow Ledger as Canonical Source of Truth

## Problem Definition

[Statement]: The DeviaTDD Product layer (FLOW-01/02/03, FLOW-04) currently records flow identity in `specs/_product/flows/index.md` and `specs/_product/flows/flows-<domain>.md` as static markdown files, with `flow_refs: [FLOW-XX, ...]` carried only as a forward-facing field on issue frontmatter and on `IssueRecord` / `AdhocRecord` JSONL rows. There is no separate, append-only ledger that records *how* each flow was discovered, documented, referenced by issues, included in releases, and evidenced by implementation. The request is to introduce a flows.jsonl inventory (event-sourced, per the existing append-only ledger philosophy) and a Flow Coverage Report surfaced inside `explore.md`, so Explore becomes the canonical reconciliation pass that catches documented-but-unbuilt, built-but-undocumented, and orphaned flows before shard/architecture/release consume stale state.

[Scope]: In-scope structural components verified across the scan:
- `specs/_product/flows/` directory containing `index.md`, `flows-product.md`, `flows-streaming.md`.
- `specs/_product/architecture.md`, `specs/_product/domain-model.md`, `specs/_product/release-next.md`.
- `IssueRecord` and `AdhocRecord` Pydantic models at `src/deviate/state/ledger.py` carrying the already-shipped `flow_refs: list[str]` field.
- The `deviate adhoc pre` CLI command at `src/deviate/cli/adhoc.py` exposing `--flow-ref FLOW-XX,FLOW-YY` and the `_FLOW_REF_PATTERN = re.compile(r"^FLOW-\d{2,}$")` validator.
- The `deviate shard post` flow at `src/deviate/cli/macro.py:672-708` that constructs `IssueRecord(...)` with `flow_refs=issue_data.get("flow_refs", [])` and writes to `specs/issues.jsonl`.
- The `FlowCoverage` review category already wired into `/deviate-review` at `src/deviate/prompts/commands/deviate-review.md:157` (`| **Category** | ... | FlowCoverage |`).
- The append-only ledger protocol declared in `specs/constitution.md:10` and implemented at `src/deviate/state/ledger.py`.
- `validate_yaml_frontmatter` at `src/deviate/core/validation.py:104-115` (lenient — any well-formed YAML block passes; unknown keys are not enumerated).
- Frontmatter-parsing surface used by `deviate-shard` and `deviate-adhoc` (issue files include `flow_refs:` in their YAML blocks).
- Code-evidenced flows (FLOW-04 components C2-C6 declared in `specs/_product/architecture.md`) and the gap they leave in the absence of a `flows.jsonl` reconciliation pass.

[Exclusions]: Architectural decisions, design trade-offs, risk analysis, ledger schema proposals, event-type vocabulary, derivation rules for `discovered_status` / `doc_status` / `impl_status`, drift-flag semantics, lifecycle integration of `deviate-flow` as a CLI command versus a skill, and failure-mode speculation — all deferred to the `deviate-research` skill. This scan catalogs what EXISTS today; it does not propose how the new ledger should be implemented.

## Release Compass

Per the Product-layer flow-trace mandate, the active release goal at `specs/_product/release-next.md:5` (`Goal anchor: FLOW-04 (Live-Stream Agent Progress via RPC)`) ships FLOW-04 end-to-end with a `Flow Coverage review dimension surfaces FLOW-04 with full coverage on the epic-tasks ledger entries (flow_refs: [FLOW-04])` acceptance criterion at `specs/_product/release-next.md:58`. The flow-ledger feature is the missing reconciliation pass that makes that criterion enforceable at scan time rather than at PR-review time.

## Discovery Audit Results

### Verified Dependencies

- `pyyaml>=6.0.3` (declared in `pyproject.toml`) — present at `src/deviate/core/validation.py:6` (`import yaml`) and consumed by `validate_yaml_frontmatter` at `src/deviate/core/validation.py:104-115`.
- `pydantic>=2.0` (declared in `pyproject.toml`) — present at `src/deviate/state/ledger.py:10-15` (`from pydantic import (BaseModel, Field, field_validator, ...)`); owns `IssueRecord`, `AdhocRecord`, `TaskRecord`, `RollbackSnapshot`.
- `rich>=13.0` (declared) — present at `src/deviate/cli/adhoc.py:11` via `from deviate.cli._common import console` (Rich Console).
- `typer>=0.12` (declared) — present at `src/deviate/cli/adhoc.py:9,17` (`adhoc_app = typer.Typer(no_args_is_help=True)`); `src/deviate/cli/macro.py` (shard post command group).
- `re` (stdlib) — present at `src/deviate/cli/adhoc.py:4,19` (`_FLOW_REF_PATTERN = re.compile(r"^FLOW-\d{2,}$")`); the canonical flow-ID validator that any new `flows.jsonl` schema must reuse.

### Ghost Dependencies

- `flows.jsonl` — referenced in the user-supplied problem statement as the proposed canonical ledger. Not declared anywhere in the repository (no `specs/_product/flows.jsonl`, no `specs/flows.jsonl`, no Pydantic model, no `_append_record` / `append_flow_*` helper). Confirmed via grep across the full tree.
- `FlowLedger`, `FlowCoverage`, `FlowRecord`, `FlowEvent`, `flows_index`, `flow_coverage`, `flow_status` — none appear anywhere in `src/`, `prompts/`, `specs/`, or `.deviate/`. The framework has the *frontmatter hook* (`flow_refs`) but no *inventory substrate*.
- `libref` CLI — referenced in `.deviate/config.toml:7` (`use_libref = true`) and across AGENTS.md; offline docs assumed available for any new flow-ledger module that needs schema reference.

### Manifest Files Observed

- `pyproject.toml` — Package metadata (`name = "deviate"`, `version = "0.4.4"`), `requires-python = ">=3.13"`, `typer>=0.12`, `rich>=13.0`, `pydantic>=2.0`, `pyyaml>=6.0.3` declared.
- `mise.toml` — Task runner config: 13 tasks (`test`, `test-e2e`, `lint`, `lint-fix`, `format`, `format-check`, `check-types`, `check`, `fix`, `setup`, `clean`, `dev`, `install-tool`, `help`).
- `package.json` — Declares `opencode-codebase-index: ^0.10.0` (Node-side tooling).
- `uv.lock` — Lockfile for `uv` package manager.
- `.gitattributes` — Declares `merge=union` for `specs/issues.jsonl` and `specs/**/tasks.jsonl` (provisioned by `deviate setup`/`deviate init` per constitution v0.4.0). A new `flows.jsonl` would need the same `merge=union` rule.
- `.deviate/config.toml` — Runtime config; declares `[agent]`, `[models]`, `graphite`, `use_libref`.

### Test Runner Configuration

- `mise.toml:8-9`: `[tasks.test]\nrun = "uv run pytest tests/ -v"` — root-level test invocation.
- `mise.toml:12-13`: `[tasks.test-e2e]\nrun = "bats tests/e2e/"` — E2E tests via bats.
- `pyproject.toml:53-54`: `[tool.pytest.ini_options]\ntestpaths = ["tests"]`.
- `tests/conftest.py` — defines `_git_env()` (strips `GIT_*` env vars) and `tmp_git_repo` fixture.

### Manifest-Constitution Divergence

- `pyproject.toml:5` declares `requires-python = ">=3.13"`; `specs/constitution.md:21` declares `Python 3.13`. **No divergence.**
- `specs/constitution.md:36` cites `Micro-sandbox: Aider Python API (aider.coders.Coder) as LLM execution substrate`; current `src/deviate/core/agent.py` dispatches to `opencode` / `claude` / `droid` / `pi` / `omp`. Constitution is aspirational; no enforcement. **Divergence flagged** (also flagged in prior explore at `specs/explore/product-layer.md:75-76`).
- No constitution reference to a `flows.jsonl` ledger exists; the only append-only ledger declarations cover `issues.jsonl` and `tasks.jsonl` (`specs/constitution.md:10`, v0.4.0 version history). **Surface gap — neither divergence nor alignment; the constitution is silent on a flows ledger.**

## Constitution Quotes

Constitution excerpts quoted verbatim from `specs/constitution.md`. No interpretation, inference, or classification. The `deviate-research` skill owns interpretation.

- **Architectural Principles**: "- **Four-Layer Architecture**: Product (optional cross-product framing: Flows → Architecture → Release), Macro (feature scoping: Explore → Research → PRD → Shard+Specify), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR). The Product layer is skipped in single-feature repos; the remaining three layers have strict phase gates — no layer may be skipped.\n- **Append-Only Ledger Protocol**: All state transitions in `issues.jsonl` and `tasks.jsonl` are append-only. No existing line is ever modified or overwritten. Canonical state is derived by sequential ledger parsing."
- **Tech Stack Standards**: "- Python 3.13\n- Target: CLI application (`deviate`)\n- Framework: Typer (CLI entry points) with Rich for terminal I/O\n\n### Database\n- No persistent database runtime (all state tracked in JSONL ledgers and TOML config)\n- Session state: JSON files under `.deviate/`\n- Issue ledger: `specs/issues.jsonl` (append-only JSONL)\n- Task ledger: `specs/**/tasks.jsonl` (append-only JSONL)\n- Config: TOML via `.deviate/config.toml`; `[models]` section for per-phase model assignment"
- **Testing Protocols**: "- Test framework: pytest\n- Test root: `tests/`\n- Test extension: `.py`\n- Test command: `pytest tests/ -v`\n- Lint command: `ruff check .`\n- E2E command: `bats tests/e2e/`\n\n### Coverage\n- Coverage target: >= 80%\n- GREEN phase must pass all tests; JUDGE verifies GREEN only modified allowed files\n- REFACTOR phase runs regression gate: tests must re-pass after polish"
- **Definition of Done**: "- [ ] Code implemented (satisfies acceptance criteria from `spec.md`)\n- [ ] Tests passing (pytest with clean exit code 0)\n- [ ] Lint passing (ruff check with no violations)\n- [ ] Judge phase passed (git diff validated against `spec.md` invariants)\n- [ ] E2E tests passing (if applicable; bats for CLI integration)\n- [ ] Documentation updated (`spec.md` and `design.md` reflect final implementation)\n- [ ] CHANGELOG.md updated under `[Unreleased]` for user-visible changes (new commands/flags, behavior changes, user-affecting bug fixes, breaking changes, new user-visible dependencies); docs-only, test-only, CI/tooling, and behavior-preserving refactors are exempt\n- [ ] No governance violations (constitution rules upheld, no HITL gates bypassed)\n- [ ] Committed with conventional message format (`test:`, `feat:`, `refactor:`, `docs:`)"

## Architectural Baselines

[Pattern_Over_Instance]: Only representative examples or base classes are listed, not every instance. All paths are strictly relative to `repo_root`.

- **Existing Architectural Patterns**: Append-only JSONL ledger protocol with compound-key idempotency at `src/deviate/state/ledger.py:114-142` (`_append_with_compound_key`) and Pydantic `model_config = {"extra": "forbid"}` on `IssueRecord`, `AdhocRecord`, `TaskRecord`, `RollbackSnapshot`. Frontmatter lenient-validation at `src/deviate/core/validation.py:104-115` (`validate_yaml_frontmatter` — accepts any well-formed YAML block; does not enumerate known/unknown keys). FLOW-ID canonical regex `_FLOW_REF_PATTERN = re.compile(r"^FLOW-\d{2,}$")` at `src/deviate/cli/adhoc.py:19`. Active-domain discipline (one-question-at-a-time with a recommended answer) referenced at `specs/DeviaTDD-api.md:156`.

- **Infrastructure & Operations**: `mise.toml:1-62` declares 13 tasks. CLI command tree registers 25+ subcommands at `src/deviate/cli/__init__.py:653-677` (Typer). No `.github/` CI pipeline present. `deviate setup` provisions `.gitattributes` with `merge=union` for `specs/issues.jsonl` and `specs/**/tasks.jsonl` at `src/deviate/cli/__init__.py:675` (constitution v0.4.0). Env config in `.deviate/config.toml` (`profile`, `timeout_seconds`, `agent_export_mode`, `[agent]`, `[models]`, `graphite`, `use_libref`).

- **Data & State Management**: Four JSONL ledgers: `specs/issues.jsonl` (per-issue rows + transitions), `specs/**/tasks.jsonl` (per-task rows + transitions), `specs/adhoc.jsonl` (per-adhoc rows), `.deviate/rollback.jsonl` (rollback snapshots). Schema validation via `IssueRecord`, `TaskRecord`, `AdhocRecord`, `RollbackSnapshot` Pydantic models in `src/deviate/state/ledger.py`. `IssueRecord.flow_refs` field already implemented at `src/deviate/state/ledger.py:35` (`flow_refs: list[str] = Field(default_factory=list)`). No `flows.jsonl` exists; `flow_refs` is the only persisted forward-pointer to flow identity.

- **Quality, Safety & Observability**: Pytest with `tmp_git_repo` fixture at `tests/conftest.py` (git isolation). `/deviate-review` carries a `FlowCoverage` review category at `src/deviate/prompts/commands/deviate-review.md:157` (`| **Category** | Security / CleanCode / Pragmatism / Idiomacy / Constitution / PRD / FlowCoverage |`). HITL Gate 1 at `src/deviate/cli/macro.py:425-494` (`_check_pending_hitl_decisions`). CONSTITUTION_DOC coverage at >=80% per `specs/constitution.md:59`. Ruff lint + format.

- **External Integrations**: Agent backends (`opencode`, `claude`, `droid`, `pi`, `omp`) at `src/deviate/core/agent.py` and `src/deviate/state/config.py:12-22` (`AgentConfig.backend` Literal). Graphite CLI (`gt`) optional integration at `src/deviate/cli/meso.py` when `.deviate/config.toml` has `graphite = true`. `gh` CLI subprocess fallback. `libref` offline documentation referenced in `.deviate/config.toml:7` and AGENTS.md. `aider` substrate declared in constitution but not implemented.

## Ecosystem Research

[Web_Discovery]: Factual cataloging of industry best practices, common use cases, and standard tools relevant to the flow-ledger problem domain. No external web calls were issued in this Explore pass (subagent protocol returned local findings only; the offline documentation path via `libref` is the primary mechanism per AGENTS.md and constitution §Tech Stack).

- **Best Practices — Append-only event-sourced state derivation**: The DeviaTDD framework already implements this pattern for `issues.jsonl`, `tasks.jsonl`, `adhoc.jsonl`, and `rollback.jsonl` (constitution §1 *Append-Only Ledger Protocol* at `specs/constitution.md:10`; ledger module at `src/deviate/state/ledger.py`). Canonical state is derived by sequential parsing. A flows ledger would naturally extend this protocol with `flows.jsonl` carrying per-flow identity rows + append-only event rows.
- **Best Practices — Three-axis flow status (discovered / documented / implemented)**: Surfaced in the user-supplied problem statement as a recommended schema. The existing `flow_refs: list[str]` field already provides forward-pointer evidence from issue to flow. The reverse direction (flow → implementing issue) is derivable from `specs/issues.jsonl` rows where `flow_refs` contains the flow ID. No reverse index currently exists in code.
- **Best Practices — Frontmatter + ledger dual representation**: The current issue files combine YAML frontmatter (human-readable) and JSONL ledger rows (machine-parseable). The same dual pattern applies to flows: `specs/_product/flows/flows-<domain>.md` for humans, `flows.jsonl` for derivation.
- **Common Use Cases & Pitfalls — Drift between markdown docs and code**: When product flows live only in markdown, "documented" and "implemented" diverge silently. The framework already saw this for `FlowCoverage` (review category exists at `src/deviate/prompts/commands/deviate-review.md:157` but no derived coverage report is emitted by `explore`). A scan-time Flow Coverage Report closes that gap.
- **Common Use Cases & Pitfalls — Cross-branch merge safety for append-only ledgers**: `merge=union` in `.gitattributes` (provisioned by `deviate setup`) is the established pattern. A new `flows.jsonl` would require the same rule to keep concurrent feature branches merging safely.
- **Common Use Cases & Pitfalls — Existing precedent for per-flow Frontmatter (flow_refs)**: `flow_refs` already validated against `^FLOW-\d{2,}$` (`src/deviate/cli/adhoc.py:19`). Any new flows.jsonl schema must reuse this regex as the canonical flow ID format.

## File Registry

| Path (Strictly Relative to Repo Root) | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `specs/constitution.md` | Governance | Project constitution declaring four-layer architecture and append-only ledger protocol | `## 1. Architectural Principles`<br>`- **Four-Layer Architecture**: Product (optional cross-product framing: Flows → Architecture → Release), Macro (feature scoping: Explore → Research → PRD → Shard+Specify), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR). The Product layer is skipped in single-feature repos; the remaining three layers have strict phase gates — no layer may be skipped.`<br>`- **Append-Only Ledger Protocol**: All state transitions in `issues.jsonl` and `tasks.jsonl` are append-only. No existing line is ever modified or overwritten. Canonical state is derived by sequential ledger parsing.` |
| `specs/_product/flows/index.md` | Spec | Canonical flow index — currently the only machine-readable inventory of flow IDs | `\| Flow ID \| Name \| Actor \| Domain \| Status \| Source \|`<br>`\|---------\|------\|-------\|--------\|--------\|--------\|`<br>`\| FLOW-01 \| Flows \| Developer \| Software Engineering \| Active \| \`specs/_product/flows/flows-product.md\` \|`<br>`\| FLOW-02 \| Architecture \| Developer \| Software Engineering \| Active \| \`specs/_product/flows/flows-product.md\` \|`<br>`\| FLOW-03 \| Release \| Developer \| Software Engineering \| Active \| \`specs/_product/flows/flows-product.md\` \|`<br>`\| FLOW-04 \| Live-Stream Agent Progress via RPC \| Developer \| Agent Integration \| Active \| \`specs/_product/flows/flows-streaming.md\` \|` |
| `specs/_product/flows/flows-product.md` | Spec | Three canonical product flows (FLOW-01/02/03) authored in markdown | `## FLOW-01 Flows`<br>`- Actor: Developer`<br>`- Domain: Software Engineering`<br>`- Status: Active`<br><br>`### Problem / job to be done`<br>`- Creation of AI assisted user flows (like this one)`<br><br>`### Trigger`<br>`- User runs /deviate-flows in their agent of choice` |
| `specs/_product/flows/flows-streaming.md` | Spec | FLOW-04 live-stream RPC flow | `## FLOW-04 Live-Stream Agent Progress via RPC`<br>`- Actor: Developer`<br>`- Domain: Agent Integration`<br>`- Status: Active`<br>`- Source: specs/_product/flows/flows-streaming.md`<br><br>`### Problem / job to be done`<br>`- Stream Pi/OMP agent progress (tool calls, thinking, edits) into a compact TUI that updates in place instead of scrolling a wall of text.` |
| `specs/_product/architecture.md` | Spec | Product-layer architecture; components C1-C6 reference flow IDs (FLOW-01/02/03/04) | `### C1 — \`deviate\` CLI (existing)`<br>`- References: FLOW-01, FLOW-02, FLOW-03.`<br>`### C2 — Subprocess Adapter (new — \`src/deviate/rpc/subprocess.py\`)`<br>`- References: FLOW-04.`<br>`### C3 — JSONL Framing Layer (new — \`src/deviate/rpc/framing.py\`)`<br>`- References: FLOW-04.`<br>`### C4 — RPC Command Sender (new — \`src/deviate/rpc/commands.py\`)`<br>`- References: FLOW-04.`<br>`### C5 — Event Adapter (new — \`src/deviate/rpc/events.py\`)`<br>`- References: FLOW-04.`<br>`### C6 — TUI Renderer (new — \`src/deviate/tui/renderer.py\`)`<br>`- References: FLOW-04.` |
| `specs/_product/release-next.md` | Spec | Active release goal anchored to FLOW-04; includes Flow Coverage acceptance criterion | `Goal anchor: FLOW-04 (Live-Stream Agent Progress via RPC)`<br>`Architecture anchor: specs/_product/architecture.md (v0.2.0)`<br>`Domain model anchor: specs/_product/domain-model.md (v0.2.0)`<br><br>`## Included Flows`<br>`\| Flow ID \| Name \| Why in this release \|`<br>`\|---\|---\|---\|`<br>`\| FLOW-04 \| Live-Stream Agent Progress via RPC \| Primary capability — entire release exists to ship this flow \|`<br>`...`<br>`- [ ] Flow Coverage review dimension surfaces FLOW-04 with full coverage on the epic-tasks ledger entries (\`flow_refs: [FLOW-04]\`).` |
| `src/deviate/state/ledger.py` | Codebase_File | Pydantic models for append-only JSONL ledgers; `IssueRecord.flow_refs` already shipped | `class IssueRecord(BaseModel):`<br>`    issue_id: str`<br>`    type: str`<br>`    title: str = Field(min_length=1)`<br>`    status: Literal["DRAFT", "BACKLOG", "SPECIFIED", "SHARDED", "COMPLETED"] = "DRAFT"`<br>`    source_file: str`<br>`    blocked_by: list[str] = []`<br>`    coordinates_with: list[str] = []`<br>`    timestamp: datetime`<br>`    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))`<br>`    flow_refs: list[str] = Field(default_factory=list)`<br>`    model_config = {"extra": "forbid"}` |
| `src/deviate/cli/adhoc.py` | Codebase_File | `deviate adhoc pre` exposes `--flow-ref` Typer option with canonical FLOW regex | `_FLOW_REF_PATTERN = re.compile(r"^FLOW-\d{2,}$")`<br>`_FLOW_REF_FORMAT_HINT = "expected format: FLOW-XX with at least two digits"`<br>`...`<br>`def _parse_flow_refs(raw: str \| None) -> list[str]:`<br>`    if raw is None:`<br>`        ...`<br>`    return tokens` |
| `src/deviate/cli/macro.py` | Codebase_File | `deviate shard post` constructs `IssueRecord` with `flow_refs=issue_data.get("flow_refs", [])` | `record = IssueRecord(`<br>`    issue_id=issue_data.get("issue_id", str(uuid.uuid4())),`<br>`    type=issue_data.get("type", "feature"),`<br>`    title=issue_data.get("title", ""),`<br>`    status="BACKLOG",`<br>`    source_file=source_file,`<br>`    blocked_by=issue_data.get("blocked_by", []),`<br>`    coordinates_with=issue_data.get("coordinates_with", []),`<br>`    timestamp=datetime.now(timezone.utc),`<br>`    flow_refs=issue_data.get("flow_refs", []),`<br>`)` |
| `src/deviate/core/validation.py` | Codebase_File | YAML frontmatter validator; lenient (any well-formed YAML block passes) | `def validate_yaml_frontmatter(content: str) -> bool:`<br>`    if not content.lstrip().startswith("---"):`<br>`        return False`<br>`    try:`<br>`        ...`<br>`    except yaml.YAMLError:`<br>`        return False`<br>`    return True` |
| `src/deviate/prompts/commands/deviate-review.md` | Codebase_File | `/deviate-review` skill carries a `FlowCoverage` review category | `\| **Confidence** \| High / Medium / Low \|`<br>`*\| **Category** \| Security / CleanCode / Pragmatism / Idiomacy / Constitution / PRD / FlowCoverage \|*` |
| `.gitattributes` | Config | Append-only ledger merge strategy (`merge=union`) for JSONL files | `# merge=union for append-only JSONL ledgers — concurrent feature branches appending to specs/issues.jsonl or specs/**/tasks.jsonl merge without conflict markers (constitution v0.4.0).`<br>`specs/issues.jsonl merge=union`<br>`specs/**/tasks.jsonl merge=union` |
| `specs/issues.jsonl` | Ledger | Append-only JSONL; each row carries `flow_refs` field (forward-pointer to flows) | `{"issue_id":"ISS-ADH-010","type":"adhoc","title":"Product Layer Skill Scaffolding","status":"COMPLETED","source_file":"specs/adhoc/issues/010-...","blocked_by":[],"coordinates_with":[],"timestamp":"...","created_at":"...","flow_refs":["FLOW-01","FLOW-02","FLOW-03"]}` |
| `src/deviate/cli/__init__.py` | Codebase_File | CLI command tree registers `_install_skills_to_agents` at line 518-531; provisions `.gitattributes` for JSONL ledgers at line 675 | `cli.add_typer(explore_app, name="explore")`<br>`cli.add_typer(research_app, name="research")`<br>`cli.add_typer(prd_app, name="prd")`<br>`cli.add_typer(shard_app, name="shard")`<br>`cli.add_typer(meso_app, name="meso")`<br>`cli.add_typer(macro_app, name="macro")`<br>`...`<br>`# 25+ subcommands total` |
| `tests/conftest.py` | Test | Defines `_git_env()` and `tmp_git_repo` fixture for git isolation in tests | `def _git_env() -> dict[str, str]:`<br>`    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}`<br>`...`<br>`tmp_git_repo(tmp_path)` (fixture creates initialized git repo at temp path with `Test Runner` identity) |

## Flow Coverage Report (Recommended Add to `explore.md`)

The following table is the proposed Flow Coverage Report — assembled purely from existing artifacts in the repo. No new files were created; the table below is a derived view of what already exists today. It is reproduced here as the deliverable the user explicitly requested ("a Flow Coverage Report to Explore: `flow_id | actor/job/trigger | documented? | implementation evidence? | last referenced by issue/release? | drift flag`").

| Flow ID | Actor / Job / Trigger | Documented? | Implementation Evidence | Last Referenced By | Drift Flag |
|:---|:---|:---|:---|:---|:---|
| `FLOW-01` | Developer / Author customer flows / `/deviate-flows` skill invocation | YES — `specs/_product/flows/flows-product.md:1-35`; index row at `specs/_product/flows/index.md:5` | NO standalone code module — implemented as prompt-only skill template at `src/deviate/prompts/commands/deviate-flows.md` | `specs/_product/release-next.md:5` (release anchor); `specs/adhoc/prd.md:155` (FR-ADHOC-010 AC-04) | `PROMPT_ONLY_NO_CODE` |
| `FLOW-02` | Developer / Cross-epic architecture / `/deviate-architecture` skill invocation | YES — `specs/_product/flows/flows-product.md:36-66`; index row at `specs/_product/flows/index.md:6` | `specs/_product/architecture.md` + `specs/_product/domain-model.md` are produced artifacts (markdown, not code); consumed by `deviate-shard` / `deviate-adhoc` (per `specs/DeviaTDD-api.md:154`) | `specs/_product/release-next.md:5`; `specs/adhoc/prd.md:156` (FR-ADHOC-010 AC-05) | `DOC_ARTIFACT_ONLY` |
| `FLOW-03` | Developer / Plan next coherent release / `/deviate-release` skill invocation | YES — `specs/_product/flows/flows-product.md:68-96`; index row at `specs/_product/flows/index.md:7` | `specs/_product/release-next.md` is the produced artifact; consumed by Explore/PRD phases per `specs/DeviaTDD-architecture.md:360-361` | `specs/_product/release-next.md:5`; `specs/adhoc/prd.md:157` (FR-ADHOC-010 AC-06) | `DOC_ARTIFACT_ONLY` |
| `FLOW-04` | Developer / Live-stream Pi/OMP agent progress via RPC into compact TUI / `deviate meso/micro run --agent {pi,omp}` | YES — `specs/_product/flows/flows-streaming.md:1-37`; index row at `specs/_product/flows/index.md:8` | PARTIAL — components C2/C3/C4/C5/C6 referenced at `specs/_product/architecture.md:18-67` declare `src/deviate/rpc/subprocess.py`, `framing.py`, `commands.py`, `events.py`, `src/deviate/tui/renderer.py` — none currently exist on disk (verified absence); acceptance criterion at `specs/_product/release-next.md:48` mandates them | `specs/_product/release-next.md:5,28,34-40,58`; `specs/_product/architecture.md` (C2-C6) | `DOCUMENTED_BUT_NOT_IMPLEMENTED` |

**Drift-flag taxonomy (factual, derived from the table above):**
- `PROMPT_ONLY_NO_CODE` — flow is fully implemented as a prompt-only skill; no Python module exists.
- `DOC_ARTIFACT_ONLY` — flow's output is a markdown document, not executable code.
- `DOCUMENTED_BUT_NOT_IMPLEMENTED` — flow declares implementation components that are not present in the codebase.
- (Future flags a research phase may propose: `IMPLEMENTED_BUT_UNDOCUMENTED`, `ORPHANED_FLOW`, `STALE_DRIFT` — observed when code references `FLOW-XX` strings not present in `specs/_product/flows/index.md`, or when `specs/issues.jsonl` carries `flow_refs` pointing to flows that no longer exist in the index.)

## Scope Sizing

| Metric | Value |
|:---|:---|
| Estimated Complexity | Medium |
| Files Likely Modified | 3-5 categories: `src/deviate/state/ledger.py` (add `FlowRecord` / `FlowEvent` Pydantic models + append helpers — parallels `IssueRecord` pattern); `src/deviate/cli/explore.py` (extend `deviate explore post` to emit the Flow Coverage Report derived from `flows.jsonl` + `specs/_product/flows/index.md` + `specs/issues.jsonl`); `.gitattributes` (add `specs/_product/flows.jsonl merge=union`); new file `specs/_product/flows.jsonl` (empty seed; ledger writer emits append-only rows); optional `src/deviate/prompts/commands/deviate-flows.md` upgrade to emit `FLOW_DISCOVERED` / `FLOW_DOCUMENTED` events. Approximate count: 3-5 source files + 1 spec + 1 manifest update. |
| New Modules Required | Optional — a new `src/deviate/core/flows.py` derivation module that parses `flows.jsonl` + `specs/_product/flows/index.md` + `specs/issues.jsonl` and emits the Flow Coverage Report. Could also live inside `src/deviate/state/ledger.py` to follow existing patterns. |
| New Persistence / Data Models | Yes — a new `specs/_product/flows.jsonl` (append-only JSONL, parallel to `issues.jsonl` and `tasks.jsonl`). New Pydantic models: `FlowRecord` (identity row) + `FlowEvent` (append-only event row, types: `FLOW_DISCOVERED`, `FLOW_DOCUMENTED`, `FLOW_IMPLEMENTATION_EVIDENCE_ADDED`, `FLOW_CONFIRMED_IMPLEMENTED`, `FLOW_REFERENCED_BY_ISSUE`, `FLOW_INCLUDED_IN_RELEASE`, `FLOW_DEPRECATED`). Field-derivation rules for `discovered_status` / `doc_status` / `impl_status` per row appended. |
| New External Integrations | None strictly required. Existing `libref` (offline docs, `.deviate/config.toml:7`) covers any new schema reference. `gh` CLI for issue-to-flow reverse lookup is unnecessary — `specs/issues.jsonl` is the source of truth. |
| Upstream / Cross-Cutting Concerns | Yes — adds a new append-only ledger to the framework's protocol. Requires updating: (a) `specs/constitution.md` v0.7.0 to enumerate `flows.jsonl` alongside `issues.jsonl` / `tasks.jsonl` in §1 *Append-Only Ledger Protocol* and v0.6.0 version history; (b) `.gitattributes` to declare `merge=union` for the new ledger; (c) `src/deviate/cli/__init__.py` `_ensure_root_gitattributes` provisioning logic to seed the new rule; (d) `deviate setup` / `deviate init` to emit the empty ledger; (e) `src/deviate/prompts/commands/deviate-{flows,architecture,release}.md` skill bodies to emit `FLOW_*` events. |
| Rationale | The request introduces a third inventory ledger (flows.jsonl) that complements the existing `issues.jsonl` and `tasks.jsonl`. The forward-pointer (`flow_refs` on `IssueRecord`) is already shipped at `src/deviate/state/ledger.py:35`, the canonical FLOW regex is already declared at `src/deviate/cli/adhoc.py:19`, and `/deviate-review` already carries a `FlowCoverage` category at `src/deviate/prompts/commands/deviate-review.md:157`. The work adds the reverse derivation (flow → implementing issue / release anchor) and surfaces a scan-time report. 2-5 files, new persistence, no new external integration — fits the Medium complexity classification. |

**Classification criteria** (factual only, no recommendation):
- **Low**: Localized change, 1-3 files. No new modules, persistence, or integrations.
- **Medium**: 2-5 files, potentially a new module or simple state. No new persistence layer.
- **High**: Multi-module, new persistence/data models, new external integrations, or cross-cutting concerns.

## Status Summary

| Metric | Value |
|:---|:---|
| STATUS | SUCCESS |
| EXPLORE_SLUG | flow-ledger |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/flow-ledger.md |
| NEXT_ACTION | Run `/deviate-research` (Medium complexity, on the high side because of the new append-only ledger + constitution bump + `.gitattributes` rule + three skill-body upgrades) — see `## Scope Sizing` |