---
title: "[FR-005] CLI Architecture Realignment & Skill Integration"
labels: ["epic:001-deviate-cli-python", "layer:macro", "layer:meso", "layer:infra"]
source_file: "specs/001-deviate-cli-python/prd.md"
blocked_by: []
coordinates_with: ["ISS-004"]
issue_id: "ISS-005"
---

## [SYSTEM_TOPOLOGY_MAPPING]
- **Epic Domain**: `001-deviate-cli-python`
- **Local File Path**: `specs/001-deviate-cli-python/issues/005-cli-architecture-realignment-skill-integration.md`
- **Workstation Paths**:
  - `src/deviate/core/` — repo, ledger, contract, commit, constitution, epic, validation, worktree, issues, prd, skills
  - `src/deviate/cli/` — macro and meso subcommands
  - `src/deviate/state/` — session, config updates
  - `src/deviate/prompts/skills/` — SKILL.md storage vault
  - `specs/issues.jsonl` — data fixes
  - `prompts/` — .sh file removal
  - `AGENTS.md` — documentation update

## [THE_PROBLEM_CONTRACT]
As a developer, I need the Python CLI to fully replace 15 bash orchestrator scripts (~8,000 lines) with `deviate <subcommand> pre/post` commands, fix critical data model bugs (malformed JSON, mismatched IssueRecord schema), implement core shared modules, and install SKILL.md files into agent directories, so that the architecture is unified and the bash dependency is eliminated.

## [SCOPE_BOUNDARIES]
- **Hard Inclusions**:
  - **Data fixes**: malformed JSON on issues.jsonl line 10; rewrite `IssueRecord` Pydantic model to match actual JSONL schema (`issue_id`, `type`, `status`, `source_file`, `blocked_by`, `coordinates_with`, `timestamp`); fix `resolve_issue_record` key mismatch (`id` -> `issue_id`); fix `macro.py:prd` artifact check (`research.md` -> `design.md` + `data-model.md`)
  - **Core modules**: `repo.py` (find_repo_root, gather_git_state), `ledger.py` (full rewrite: read/append JSONL, get_issue_by_id, select_next_unblocked_issue, check_ledger_dirty, next_issue_id, register_issue), `contract.py` (emit/persist/load JSON contracts), `commit.py` (stage_and_commit, commit_artifact), `constitution.py` (resolve, validate, extract commands), `epic.py` (discover_epic, allocate_feature_bucket, resolve_active_feature), `validation.py` (extract_spec_sections, extract_section_body, validate_gherkin_syntax), `worktree.py` (create/detect/validate worktrees, branch checks), `issues.py` (resolve_issue, claim_issue, read_issue_body, is_issue_completed), `prd.py` (extract_prd_requirements, validate_traceability), `skills.py` (install/discover/resolve skills)
  - **Meso Layer CLI**: `deviate specify pre [--issue <id>] [--force]` (auto-select next unblocked BACKLOG, worktree creation, ledger claim, spec target resolution), `deviate specify post [--force]` (content validation, commit, ledger update), `deviate tasks pre` (worktree detection, spec discovery, artifact discovery), `deviate tasks post [--force]` (content validation, commit), `deviate pr pre` (worktree validation, issue discovery, body gathering), `deviate pr run --body-file <path> [--merge] [--auto-merge]` (PR creation, merge, COMPLETED event)
  - **Macro Layer CLI**: `deviate explore pre "<problem>" [--slug <slug>]` (repo discovery, constitution validation, feature bucket allocation, ledger scratch entry), `deviate explore post` (content validation, commit), `deviate research pre [<epic>]` (active feature resolution, constitution re-validation, explore.md gate), `deviate research post` (content validation, constitutional violation scan, commit), `deviate prd pre` (epic slug discovery, upstream artifact resolution), `deviate prd post <manifest>` (manifest reading, PRD validation, staging, commit), `deviate shard pre` (epic discovery, PRD resolution, issues dir, next_issue_id), `deviate shard post <manifest>` (shard validation, ledger registration, commit)
  - **Skill installation**: Move SKILL.md files to `src/deviate/prompts/skills/<name>/SKILL.md`; rewrite all SKILL.md to call `deviate <subcommand>` instead of `<SKILL_DIR>/deviate-*.sh`; wire into `deviate init`; add cleanup of old `.sh` files; auto-detect agents in cwd with flag overrides and interactive fallback
  - **Contract handoff**: Configurable between temp files and `.deviate/session.json` (default: session.json); add `.deviate/session.json` to `.gitignore` during init
  - **Session state**: Dual-mode for Macro/Meso — both strict phase ordering AND filesystem state validation; detect divergence when user alters filesystem or undoes commits
  - **Task ID format**: Both `T{NNN}` and `T{NNN}:` accepted
  - **Cleanup**: Remove all `.sh` files from `prompts/`; remove `deviate-cycle` skill; update `mise.toml` and `AGENTS.md`
  - **Installed skill improvements preserved**: specify pre-write HITL gate + --force flag; tasks 6-step execution mode decision tree; explore greenfield support; research greenfield constitution bootstrapping; shard anti-pattern gate + horizontal slice audit
- **Defensive Exclusions**:
  - Micro-layer TDD sandbox execution (execute, red, green, refactor, e2e, prune, hotfix, YELLOW, JUDGE) — covered by ISS-004
  - Direct LLM sandbox or Tamper Guard implementation

## [UPSTREAM_REQUIREMENT_TRACING]
- **FR-005-DATA**: Fixes critical data model bugs and schema misalignment in the Python CLI
- **FR-005-CORE**: Implements all core shared modules (repo, ledger, contract, commit, constitution, epic, validation, worktree, issues, prd, skills)
- **FR-005-MESO**: Implements Meso Layer CLI subcommands (specify, tasks, pr)
- **FR-005-MACRO**: Implements Macro Layer CLI subcommands (explore, research, prd, shard)
- **FR-005-SKILLS**: Installs and rewrites SKILL.md files, removes bash dependency
- **FR-005-INIT**: Wire skill installation and agent detection into `deviate init`
- **FR-005-SESSION**: Dual-mode session state with filesystem divergence detection

## [MULTI_TIERED_VERIFICATION_TARGETS]
- **Unit Tests**: `tests/test_core/test_ledger.py`, `tests/test_core/test_repo.py`, `tests/test_core/test_contract.py`, `tests/test_core/test_commit.py`, `tests/test_core/test_constitution.py`, `tests/test_core/test_epic.py`, `tests/test_core/test_validation.py`, `tests/test_core/test_worktree.py`, `tests/test_core/test_issues.py`, `tests/test_core/test_prd.py`, `tests/test_core/test_skills.py`
- **Integration Tests**: `tests/test_integration/test_macro_layer.py`, `tests/test_integration/test_meso_layer.py`, `tests/test_integration/test_skill_installation.py`
- **Data verification**: `python -c "import json; [json.loads(l) for l in open('specs/issues.jsonl')]"`

## [DEMONSTRATION_PATH]
```bash
# Verify data model fixes
python -c "import json; [json.loads(l) for l in open('specs/issues.jsonl')]"

# Verify core modules
pytest tests/test_core/ -v

# Verify macro and meso layer CLI
pytest tests/test_integration/test_macro_layer.py -v
pytest tests/test_integration/test_meso_layer.py -v

# Verify skill installation
deviate init --dry-run
ls ~/.config/opencode/skills/deviate-*/
```
