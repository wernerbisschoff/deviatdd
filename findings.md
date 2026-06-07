# Findings: DeviaTDD CLI Architecture Alignment

> **Date**: 2026-06-07
> **Target Architecture**: Python CLI completely replaces bash scripts. CLI invokes skills, skills call CLI.
> **Scope**: All 18 skills in `prompts/`, Python CLI in `src/deviate/`, `mise.toml`, `specs/issues.jsonl`

---

## TL;DR

The Python CLI must absorb the functionality of **15 bash orchestrator scripts** (~8,000 lines of bash). Every SKILL.md must be rewritten to call `deviate <subcommand> pre/post` instead of `<SKILL_DIR>/deviate-*.sh`. `deviate init` must install skills (SKILL.md only, no scripts) into agent skill directories. The `specs/issues.jsonl` has corrupted JSON on line 10.

---

## 1. Architecture: Current vs Target

### Current (broken)
```
Skill SKILL.md → <SKILL_DIR>/deviate-*.sh pre/post (bash)
                 ↓
            Shell functions (find_repo_root, jq queries, git ops)
                 ↓
            Filesystem mutations

Python CLI (src/deviate/) → Parallel implementation, never calls scripts
                            Broken ledger schema, wrong artifact checks
```

### Target
```
CLI (Python) → Loads skill prompt → Agent executes
                  ↓
            Agent calls: deviate <subcommand> pre
                  ↓
            CLI outputs JSON contract to stdout
                  ↓
            Agent writes artifact (spec.md, tasks.md, etc.)
                  ↓
            Agent calls: deviate <subcommand> post
                  ↓
            CLI validates, commits, updates ledger

deviate init → Installs SKILL.md files into ~/.config/opencode/skills/
               (and ~/.claude/skills/ if present)
               NO bash scripts shipped
```

---

## 2. CLI Subcommands Required

Every bash script's `pre`/`post` functionality must become a CLI subcommand.

### 2.1 Macro Layer

| Subcommand | Replaces | Key Functionality |
|---|---|---|
| `deviate explore pre "<problem>" [--slug <slug>]` | `deviate-explore.sh pre` | Repo discovery, constitution validation, feature bucket allocation (next NNN index), slug derivation, ledger scratch entry, JSON contract to stdout |
| `deviate explore post` | `deviate-explore.sh post` | Content validation (required sections in explore.md), atomic commit |
| `deviate research pre [<epic>]` | `deviate-research.sh pre` | Active feature resolution (bare ID, NNN-slug, absolute path, specs-relative, explore.md path, env var, most-recent fallback), constitution re-validation, explore.md gate, design/data-model target allocation |
| `deviate research post` | `deviate-research.sh post` | Content validation (design.md + data-model.md required sections), constitutional violation warning scan, atomic commit |
| `deviate prd pre` | `deviate-prd.sh pre` | Epic slug discovery, upstream artifact path resolution (constitution, explore.md, design.md, data-model.md), contract emission |
| `deviate prd post <manifest>` | `deviate-prd.sh post` | Manifest reading, PRD validation (required sections), staging, commit |
| `deviate shard pre` | `deviate-shard.sh pre` | Epic slug discovery, PRD path resolution, issues dir creation, `next_issue_id` calculation |
| `deviate shard post <manifest>` | `deviate-shard.sh post` | Shard file validation (YAML frontmatter), inline ledger registration, staging, commit |

### 2.2 Meso Layer

| Subcommand | Replaces | Key Functionality |
|---|---|---|
| `deviate specify pre [--issue <id>] [--dry-run]` | `deviate-specify.sh pre` | **Auto-select next unblocked BACKLOG issue** when `--issue` omitted. Epic discovery, worktree creation, ledger claim + push-to-claim, PRD traceability validation, spec target resolution |
| `deviate specify post [--force]` | `deviate-specify.sh post` | Spec content validation (required sections, Gherkin Given/When/Then, FR references), commit, ledger update (`specify_complete` event) |
| `deviate tasks pre` | `deviate-tasks.sh pre` | Worktree detection (via `git rev-parse`), branch validation, spec.md discovery + section validation, research artifact discovery (design.md, data-model.md) |
| `deviate tasks post [--force]` | `deviate-tasks.sh post` | Tasks content validation (sections, `T{NNN}` format, empty checkboxes, verification commands), commit |

### 2.3 PR Lifecycle

| Subcommand | Replaces | Key Functionality |
|---|---|---|
| `deviate pr pre` | `deviate-pr.sh pre` | Worktree state validation, issue ID discovery from branch name, PR body data gathering (commit titles, changed files, diff summary) |
| `deviate pr run --body-file <path> [--merge] [--auto-merge]` | `deviate-pr.sh run` | PR creation via `gh`, merge/auto-merge, COMPLETED event append to ledger on merge |

### 2.4 Micro Layer

| Subcommand | Replaces | Key Functionality |
|---|---|---|
| `deviate execute pre [--task <id>]` | `deviate-execute.sh pre` | Workflow discovery, task context surfacing, validation command resolution |
| `deviate execute post <manifest>` | `deviate-execute.sh post` | Task completion marking, staging, precommit hooks, commit |
| `deviate red pre [--task <id>]` | `deviate-red.sh pre` | Task context, test/lint command resolution, spec_dir discovery |
| `deviate red post <manifest>` | `deviate-red.sh post` | Test failure validation, commit |
| `deviate green pre [--task <id>]` | `deviate-green.sh pre` | Task context, test/lint command resolution |
| `deviate green post <manifest>` | `deviate-green.sh post` | Test pass validation, commit |
| `deviate refactor pre [--task <id>]` | `deviate-refactor.sh pre` | Task context, test/lint command resolution |
| `deviate refactor post <manifest>` | `deviate-refactor.sh post` | Test invariance validation, commit |
| `deviate e2e pre` | `deviate-e2e.sh pre` | Phase completion verification, E2E test discovery |
| `deviate e2e post` | `deviate-e2e.sh post` | E2E test execution results, commit |
| `deviate prune pre [--file <path>]` | `deviate-prune.sh pre` | Test file discovery, task context |
| `deviate prune post <manifest>` | `deviate-prune.sh post` | Validation, commit |

### 2.5 Utility

| Subcommand | Replaces | Key Functionality |
|---|---|---|
| `deviate constitution pre` | `deviate-constitution.sh pre` | Constitution discovery, contract emission |
| `deviate constitution post <manifest>` | `deviate-constitution.sh post` | Constitution validation, commit |
| `deviate context pre` | `deviate-context.sh pre` | Spec dir discovery, context file path resolution, language detection |
| `deviate context post <manifest>` | `deviate-context.sh post` | Symlink enforcement, file staging, commit |
| `deviate hotfix pre` | `deviate-hotfix.sh pre` | Bug context discovery |
| `deviate hotfix post <manifest>` | `deviate-hotfix.sh post` | Commit |

---

## 3. Python Core Modules Required

All bash shared-library functions must be reimplemented in Python.

### 3.1 `deviate/core/repo.py`
- `find_repo_root(start: Path) -> Path` — walk-up `.git` discovery
- `gather_git_state(repo: Path) -> dict` — staged/unstaged/untracked as JSON-serializable dict

### 3.2 `deviate/core/ledger.py` (REWRITE — current model is wrong)
- `read_ledger(path: Path) -> list[dict]` — parse JSONL, skip malformed lines
- `append_ledger(path: Path, entry: dict)` — append with file locking
- `get_issue_by_id(ledger: Path, issue_id: str) -> dict | None` — latest state per issue_id
- `select_next_unblocked_issue(ledger: Path) -> dict | None` — oldest unblocked BACKLOG feature
- `check_ledger_dirty(ledger: Path, repo: Path) -> bool` — uncommitted changes check
- `next_issue_id(ledger: Path) -> str` — next ISS-NNN
- `register_issue(ledger: Path, ...)` — register with dedup by source_file
- `IssueRecord` model — **must match actual JSONL schema** (see §6.1)

### 3.3 `deviate/core/worktree.py`
- `create_worktree(repo: Path, branch: str) -> Path`
- `detect_worktree() -> Path` — via `git rev-parse`
- `validate_branch(worktree: Path) -> str` — reject main/master/HEAD
- `branch_exists_remote(branch: str) -> bool`
- `branch_exists_local(branch: str) -> bool`

### 3.4 `deviate/core/issues.py`
- `resolve_issue(ledger: Path, issue_id: str | None) -> dict` — by ID or auto-select
- `claim_issue(ledger: Path, issue_id: str, worker: str) -> dict` — append CLAIMED event
- `read_issue_body(repo: Path, source_file: str) -> str`
- `parse_source_file(path: str) -> tuple[str, str, str, int]` — epic, number, slug, int
- `is_issue_completed(ledger: Path, issue_id: str) -> bool` — check event log

### 3.5 `deviate/core/epic.py`
- `discover_epic(specs_dir: Path) -> tuple[Path, str, str]` — most-recent NNN-*, slug, id
- `allocate_feature_bucket(specs_dir: Path) -> tuple[str, str]` — next NNN index, dir name
- `resolve_active_feature(explicit: str | None, repo: Path) -> Path` — multi-form resolution
- `epic_id_from_slug(slug: str) -> str`

### 3.6 `deviate/core/constitution.py`
- `resolve_constitution(repo: Path) -> Path | None` — search chain: specs/, .deviate/, root
- `extract_constitution_commands(path: Path) -> dict` — test, lint, typecheck commands
- `validate_constitution(path: Path) -> bool`

### 3.7 `deviate/core/prd.py`
- `extract_prd_requirements(prd_path: Path) -> list[dict]` — FR-NNN extraction
- `validate_traceability(issue_body: str, prd_path: Path) -> tuple[str, list]` — PASS/FAIL + details

### 3.8 `deviate/core/validation.py`
- `extract_spec_sections(file: Path, *headers: str) -> list[str]` — missing headers
- `extract_section_body(file: Path, header: str) -> str`
- `validate_gherkin_syntax(content: str) -> tuple[int, list[str]]` — count + missing clauses

### 3.9 `deviate/core/commit.py`
- `commit_artifact(worktree: Path, file: str, subject: str, body: str = "")`
- `commit_files(worktree: Path, subject: str, body: str, *files: str)`
- `stage_and_commit(worktree: Path, subject: str, files: list[str]) -> str` — returns SHA

### 3.10 `deviate/core/contract.py`
- `emit_contract(data: dict) -> None` — JSON to stdout (for skill consumption)
- `persist_contract(data: dict, path: Path | None) -> Path` — temp file for post-script handoff
- `load_contract(path: Path | None) -> dict` — post-script reads persisted contract

### 3.11 `deviate/core/skills.py`
- `install_skills(agent_mode: str) -> None` — copy SKILL.md to agent directories
- `resolve_skill_dir(agent: str, skill_name: str) -> Path`
- `discover_available_skills() -> list[str]` — from package resources

---

## 4. SKILL.md Changes Required

Every SKILL.md must be rewritten. The changes are mechanical but pervasive.

### 4.1 Universal Changes (apply to ALL 18 skills)

| What | From | To |
|---|---|---|
| Script invocation | `<SKILL_DIR>/deviate-specify.sh pre` | `deviate specify pre` |
| Script invocation | `<SKILL_DIR>/deviate-specify.sh post` | `deviate specify post` |
| Prerequisites block | `<required_scripts_path>The script is colocated...</required_scripts_path>` | Remove entirely |
| Failure mode | `ERROR: Operational orchestrator not found at <SKILL_DIR>/deviate-specify.sh` | Remove or replace with `ERROR: deviate CLI not found. Run 'pip install deviate' first.` |
| IMPORTANT banner | `**IMPORTANT**: The script deviate-specify.sh lives in this skill's directory...` | Remove |

### 4.2 Per-Skill Changes

| Skill | Specific Changes |
|---|---|
| **deviate-explore** | `deviate-explore.sh pre "<problem>" --slug "<slug>"` → `deviate explore pre "<problem>" --slug "<slug>"`. Add greenfield support (`is_greenfield` in contract). |
| **deviate-research** | `deviate-research.sh pre [--feature <dir>]` → `deviate research pre [<epic>]`. Add greenfield constitution bootstrapping. |
| **deviate-prd** | `deviate-prd.sh pre` → `deviate prd pre`. Post takes manifest path: `deviate prd post <manifest>`. |
| **deviate-shard** | `deviate-shard.sh pre` → `deviate shard pre`. Add anti-pattern gate (horizontal slice detection). |
| **deviate-specify** | `deviate-specify.sh pre` → `deviate specify pre [--issue <id>]`. Add pre-write HITL gate. Add `--force` for push-to-claim. |
| **deviate-tasks** | `deviate-tasks.sh pre` → `deviate tasks pre`. Add execution mode decision tree (6-step). Align task ID format. |
| **deviate-pr** | `deviate-pr.sh pre` → `deviate pr pre`. `deviate-pr.sh run` → `deviate pr run`. |
| **deviate-execute** | `deviate-execute.sh pre` → `deviate execute pre`. Post takes manifest: `deviate execute post <manifest>`. |
| **deviate-red** | `deviate-red.sh pre` → `deviate red pre`. Post takes manifest. |
| **deviate-green** | `deviate-green.sh pre` → `deviate green pre`. Post takes manifest. |
| **deviate-refactor** | `deviate-refactor.sh pre` → `deviate refactor pre`. Post takes manifest. |
| **deviate-e2e** | `deviate-e2e.sh pre` → `deviate e2e pre`. |
| **deviate-prune** | `deviate-prune.sh pre` → `deviate prune pre`. Post takes manifest. |
| **deviate-hotfix** | `deviate-hotfix.sh pre` → `deviate hotfix pre`. Post takes manifest. |
| **deviate-constitution** | `deviate-constitution.sh pre` → `deviate constitution pre`. Post takes manifest. |
| **deviate-context** | `deviate-context.sh pre` → `deviate context pre`. Post takes manifest. |
| **deviate-triage** | No script exists. No changes needed (pure prompt). |
| **deviate-adhoc** | No script exists. Needs ledger registration via `deviate` CLI. |

### 4.3 Skill Storage in Package

SKILL.md files must be stored as package resources so `deviate init` can install them:

```
src/deviate/prompts/skills/
  deviate-explore/SKILL.md
  deviate-research/SKILL.md
  deviate-prd/SKILL.md
  deviate-shard/SKILL.md
  deviate-specify/SKILL.md
  deviate-tasks/SKILL.md
  deviate-pr/SKILL.md
  deviate-execute/SKILL.md
  deviate-red/SKILL.md
  deviate-green/SKILL.md
  deviate-refactor/SKILL.md
  deviate-e2e/SKILL.md
  deviate-prune/SKILL.md
  deviate-hotfix/SKILL.md
  deviate-constitution/SKILL.md
  deviate-context/SKILL.md
  deviate-triage/SKILL.md
  deviate-adhoc/SKILL.md
  deviate-cycle/SKILL.md
```

The current `prompts/` directory can serve as the source, but the `.sh` files should be removed and the SKILL.md files updated to reference CLI commands.

---

## 5. `deviate init` Skill Installation

### 5.1 Current Behavior
- Scaffolds `.deviate/` (config.toml, session.json)
- Provisions `specs/constitution.md`
- Applies governance to CLAUDE.md and AGENTS.md

### 5.2 Required New Behavior
Add skill installation step:

```
deviate init [--agent-export-mode local|global]
```

1. Detect agent directories:
   - **opencode**: `~/.config/opencode/skills/`
   - **claude**: `~/.claude/skills/`
   - If `--agent-export-mode global`, install to user-level dirs above
   - If `local`, install to `{repo_root}/.opencode/skills/` and `{repo_root}/.claude/skills/`

2. For each skill in `src/deviate/prompts/skills/`:
   - Create `{agent_dir}/deviate-{name}/`
   - Write `SKILL.md` from package resource
   - **Do NOT write any .sh files**

3. Idempotency:
   - If SKILL.md already exists and is identical, skip
   - If SKILL.md exists and differs, overwrite (log UPDATE)
   - If directory exists with extra files (old .sh scripts), remove them

---

## 6. Critical Bugs (Independent of Architecture)

### 6.1 `specs/issues.jsonl` line 10 — malformed JSON

```
{"issue_id":"ISS-003,"status":"COMPLETED","timestamp":"2026-06-07T09:14:18Z"}
```

The `issue_id` value is `"ISS-003,"` — trailing comma inside the string. This breaks `json.loads()` and `jq`. ISS-003's COMPLETED status is invisible to all tooling.

**Fix**: Correct to `{"issue_id":"ISS-003","status":"COMPLETED","timestamp":"2026-06-07T09:14:18Z"}`.

### 6.2 Python CLI `IssueRecord` model doesn't match JSONL schema

| IssueRecord field | Actual JSONL field | Problem |
|---|---|---|
| `id: str` (UUID4) | `issue_id: str` (ISS-NNN) | Wrong name AND format |
| `status: DRAFT\|SPECIFIED\|SHARDED\|COMPLETED` | `status: BACKLOG\|CLAIMED\|COMPLETED` | Wrong enum values |
| `epic_slug: str` | (not present) | Not in JSONL |
| `issue_slug: str` | (not present) | Not in JSONL |
| (not modeled) | `type: str` | Missing |
| (not modeled) | `source_file: str` | Missing |
| (not modeled) | `blocked_by: list` | Missing |
| (not modeled) | `coordinates_with: list` | Missing |
| (not modeled) | `timestamp: str` | Missing |

Plus `model_config = {"extra": "forbid"}` rejects real entries.

### 6.3 `resolve_issue_record` matches on wrong key

`ledger.py:104` uses `data.get("id")` but JSONL uses `"issue_id"`. Always returns `None`.

### 6.4 `macro.py:prd` checks for non-existent `research.md`

```python
_run_command("PRD", epic_slug, ["explore.md", "research.md"])
```

Research produces `design.md` + `data-model.md`, not `research.md`. Always fails.

### 6.5 `mise dev specify` requires explicit issue_id

The Python CLI's `specify(issue_id: str = typer.Argument(...))` never auto-selects. The bash script's `resolve_issue()` auto-selects the oldest unblocked BACKLOG issue when no ID is given.

---

## 7. Improvements from Installed Skills to Preserve

The installed skills in `~/.config/opencode/skills/` have improvements over `prompts/` that must be preserved in the rewritten SKILL.md files:

| Skill | Improvement |
|---|---|
| **deviate-specify** | Pre-write HITL gate (3 edge-case questions before authoring). `--force` flag for push-to-claim failures. |
| **deviate-tasks** | 6-step Execution_Mode decision tree (don't default to TDD). `**Files**`/`**Details**` format markers. `T{NNN}:` ID format with colon. |
| **deviate-explore** | Greenfield support (`is_greenfield` boolean in contract). Constitution-optional for new projects. |
| **deviate-research** | Greenfield constitution bootstrapping from exploration findings. Relaxed constitution gate. |
| **deviate-shard** | Anti-pattern gate (named horizontal slice anti-patterns: "state issue", "data model issue"). Horizontal slice audit pass (Pass 3). Litmus test for vertical slices. |
| **All scripts** | `agent-artifacts/` temp dir paths (pre-approved by Claude Code and Opencode). |

---

## 8. Files to Remove

| File | Reason |
|---|---|
| `prompts/deviate-explore/deviate-explore.sh` | Replaced by `deviate explore pre/post` |
| `prompts/deviate-research/deviate-research.sh` | Replaced by `deviate research pre/post` |
| `prompts/deviate-prd/deviate-prd.sh` | Replaced by `deviate prd pre/post` |
| `prompts/deviate-shard/deviate-shard.sh` | Replaced by `deviate shard pre/post` |
| `prompts/deviate-specify/deviate-specify.sh` | Replaced by `deviate specify pre/post` |
| `prompts/deviate-tasks/deviate-tasks.sh` | Replaced by `deviate tasks pre/post` |
| `prompts/deviate-execute/deviate-execute.sh` | Replaced by `deviate execute pre/post` |
| `prompts/deviate-red/deviate-red.sh` | Replaced by `deviate red pre/post` |
| `prompts/deviate-green/deviate-green.sh` | Replaced by `deviate green pre/post` |
| `prompts/deviate-refactor/deviate-refactor.sh` | Replaced by `deviate refactor pre/post` |
| `prompts/deviate-e2e/deviate-e2e.sh` | Replaced by `deviate e2e pre/post` |
| `prompts/deviate-prune/deviate-prune.sh` | Replaced by `deviate prune pre/post` |
| `prompts/deviate-hotfix/deviate-hotfix.sh` | Replaced by `deviate hotfix pre/post` |
| `prompts/deviate-constitution/deviate-constitution.sh` | Replaced by `deviate constitution pre/post` |
| `prompts/deviate-context/deviate-context.sh` | Replaced by `deviate context pre/post` |
| `~/.config/opencode/skills/deviate-*/deviate-*.sh` | Installed scripts — remove on next `deviate init` |
| `~/.claude/skills/deviate-*/deviate-*.sh` | Installed scripts — remove on next `deviate init` |

---

## 9. Execution Order

### Phase 1: Fix Data (unblocks everything)
1. Fix `specs/issues.jsonl` line 10 (malformed JSON)
2. Rewrite `IssueRecord` model to match actual JSONL schema
3. Fix `resolve_issue_record` key mismatch (`id` → `issue_id`)
4. Fix `macro.py:prd` artifact check (`research.md` → `design.md` + `data-model.md`)

### Phase 2: Core Modules (foundation for all subcommands)
5. Implement `deviate/core/repo.py` (find_repo_root, gather_git_state)
6. Implement `deviate/core/ledger.py` (full rewrite for JSONL)
7. Implement `deviate/core/contract.py` (emit/persist/load contracts)
8. Implement `deviate/core/commit.py` (stage, commit, hooks)
9. Implement `deviate/core/constitution.py` (resolve, validate, extract commands)
10. Implement `deviate/core/epic.py` (discover, allocate, resolve)
11. Implement `deviate/core/validation.py` (sections, Gherkin)

### Phase 3: Meso Layer CLI (highest priority — user's immediate blocker)
12. Implement `deviate/core/worktree.py`
13. Implement `deviate/core/issues.py` (resolve, claim, auto-select)
14. Implement `deviate/core/prd.py` (FR extraction, traceability)
15. Implement `deviate specify pre/post` subcommands
16. Implement `deviate tasks pre/post` subcommands
17. Implement `deviate pr pre/post` subcommands

### Phase 4: Macro Layer CLI
18. Implement `deviate explore pre/post` subcommands
19. Implement `deviate research pre/post` subcommands
20. Implement `deviate prd pre/post` subcommands
21. Implement `deviate shard pre/post` subcommands

### Phase 5: Micro Layer CLI
22. Implement `deviate execute pre/post`
23. Implement `deviate red pre/post`
24. Implement `deviate green pre/post`
25. Implement `deviate refactor pre/post`
26. Implement `deviate e2e pre/post`
27. Implement `deviate prune pre/post`
28. Implement `deviate hotfix pre/post`

### Phase 6: Skill Installation
29. Move SKILL.md files to `src/deviate/prompts/skills/`
30. Rewrite all SKILL.md files to use `deviate <subcommand>` instead of `<SKILL_DIR>/deviate-*.sh`
31. Implement `deviate/core/skills.py` (install, discover, resolve)
32. Wire skill installation into `deviate init`
33. Add cleanup of old `.sh` files during skill installation

### Phase 7: Cleanup
34. Remove all `.sh` files from `prompts/`
35. Remove `deviate-cycle` (references non-existent `$HOME/.config/ai/spec/scripts/`)
36. Update `mise.toml` if needed
37. Update `AGENTS.md` to reflect new CLI architecture

---

## 10. Open Questions

1. **Task ID format**: Installed tasks SKILL.md uses `T{NNN}:` (with colon), source uses `T{NNN}` (without). Which is canonical? The validator regex must match.

2. **Contract handoff**: Bash scripts use temp files for pre→post handoff. Should the CLI use the same approach, or store state in `.deviate/session.json`?

3. **Session state machine**: The current `_TRANSITION_MAP` in `config.py` enforces strict phase ordering. The skills don't use session state at all — they detect state from filesystem. Should the session state machine be kept, simplified, or removed?

4. **`deviate-cycle`**: References `$HOME/.config/ai/spec/scripts/manage-tasks.sh` which doesn't exist. Is this skill deprecated or does it need to be rewritten for the new architecture?

5. **Agent detection**: `deviate init` needs to know which agents are installed. Should it auto-detect (check for `~/.config/opencode/`, `~/.claude/`) or require explicit flags?
