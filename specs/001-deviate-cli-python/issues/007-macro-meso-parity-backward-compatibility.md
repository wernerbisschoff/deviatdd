---
title: "[FR-007] Macro/Meso Parity & Backward Compatibility"
labels: ["epic:001-deviate-cli-python", "layer:macro", "layer:meso", "layer:infra"]
source_file: "specs/001-deviate-cli-python/prd.md"
blocked_by: []
coordinates_with: []
issue_id: "ISS-007"
---

## [SYSTEM_TOPOLOGY_MAPPING]
- **Epic Domain**: `001-deviate-cli-python`
- **Local File Path**: `specs/001-deviate-cli-python/issues/007-macro-meso-parity-backward-compatibility.md`
- **Workstation Paths**:
  - `src/deviate/cli/macro.py` — explore, research, prd, shard contracts & validation
  - `src/deviate/cli/meso.py` — tasks, pr contracts & validation
  - `src/deviate/cli/__init__.py` — CLI wiring (--dry-run flags, new options)
  - `src/deviate/core/validation.py` — content validation for post-phases
  - `src/deviate/state/` — session, config updates for new features
  - `~/.claude/skills/deviate-*.sh` — bash scripts (must remain functional)

## [THE_PROBLEM_CONTRACT]
As a developer migrating from bash to Python CLI, I need the macro (explore, research, prd, shard) and meso (tasks, pr) commands to emit complete contracts with all fields present in the bash originals, enforce rigorous content validation in post-phases, and support all features like `--dry-run`, `--issue-id`, and pre-commit hooks — all while maintaining backward compatibility with the existing bash skill workflow — so that no information is lost in the transition and both systems can coexist during the cutover.

## [SCOPE_BOUNDARIES]

### Priority 1 — Contract Field Parity
- **explore pre**: Add missing fields (repo_root, git_branch, constitution_path, test_cmd, lint_cmd, type_check_cmd, epic_id, is_greenfield, timestamp) — currently emits only 5 fields, bash emits 15.
- **research pre**: Add missing fields (repo_root, git_branch, constitution_path, all commands, is_greenfield, timestamps) — currently emits 3 fields, bash emits 18+.
- **prd pre**: Add missing fields (repo_root, git_branch, constitution_path, test/lint/type_check cmds, timestamps) — currently emits 2 fields, bash emits 17.
- **shard pre**: Add missing fields (repo_root, git_branch, constitution_path, issues_dir, plan_target, dry_run) — currently emits 4 fields, bash emits 17.
- **tasks pre**: Add full JSON contract with issue_id, spec_path, worktree, constitution commands — currently emits no contract at all.
- **pr pre**: Add full JSON contract with branch info, PR metadata, git state — currently emits no contract at all.

### Priority 2 — Content Validation
- **explore post**: Validate 5 required sections (PROBLEM_DEFINITION, DISCOVERY_AUDIT_RESULTS, CONSTITUTION_QUOTES, FILE_REGISTRY, STATUS_SUMMARY) — currently only checks non-empty.
- **research post**: Validate 9 design.md sections + 6 data-model.md sections + constitutional alignment audit — currently only checks non-empty.
- **shard post**: Validate individual NNN-*.md shard files with YAML frontmatter — currently validates wrong files (spec.md + tasks.md).
- **tasks post**: Validate T{NNN} format, checkboxes, verification commands — currently only checks non-empty.

### Priority 3 — Missing Features
- `--dry-run` flag on prd, shard, tasks, pr commands (currently only on specify).
- `--issue-id` option on tasks post (bash derives spec from explicit issue ID).
- `--auto` continuous execute loop flag.
- Pre-commit hooks in post-phase (bash runs pre-commit if config exists).
- Mise setup in new worktrees (bash installs dependencies).
- `deviate execute` TDD task runner (not implemented in Python).
- `deviate context` CLAUDE.md/AGENTS.md sync (not implemented in Python).
- `deviate constitution` generate from project type (not implemented in Python).

### Backward Compatibility Constraints
- All new Python code must coexist with old bash scripts in `~/.claude/skills/deviate-*.sh`.
- Bash skills must remain fully functional — no breaking changes to the contract handoff format they produce or consume.
- Python CLI must detect and work correctly alongside bash-managed worktrees, ledgers, and session state.
- No changes to the JSONL ledger schema or issue file format that would break bash tooling.
- Bash scripts are stateless (discover everything at runtime); Python is session-based. Both approaches must produce compatible artifacts.

### Defensive Exclusions
- Micro-layer TDD sandbox execution (red, green, refactor, execute, e2e, prune, hotfix, YELLOW, JUDGE) — covered by ISS-004.
- State persistence & concurrency safety (fcntl locking, atomic writes) — covered by ISS-006.
- Core module business logic (repo, contract, constitution, epic, issues, commit, prd, skills) — covered by ISS-005.
- CLI initialization & governance provisioning — covered by ISS-001.
- Macro-layer state & ledger management — covered by ISS-002.
- Meso-layer specification & task decomposition — covered by ISS-003.

## [UPSTREAM_REQUIREMENT_TRACING]
- **FR-007-CONTRACT**: All macro/meso pre-commands emit complete JSON contracts matching bash field set.
- **FR-007-VALIDATE**: All post-commands enforce section-level content validation matching bash rigor.
- **FR-007-FEATURES**: All missing CLI features (--dry-run, --issue-id, --auto, pre-commit, mise) implemented.
- **FR-007-BACKWARD**: New Python code maintains backward compatibility with bash skills at all times.

## [MULTI_TIERED_VERIFICATION_TARGETS]
- **Unit Tests**: `tests/test_cli/test_macro_contracts.py`, `tests/test_cli/test_meso_contracts.py`, `tests/test_core/test_validation.py`
- **Integration Tests**: `tests/test_integration/test_parity.py` (runs both bash and Python CLI, compares contract outputs)
- **Backward compat**: Each bash script in `~/.claude/skills/deviate-*.sh` still runs and produces valid output after changes.

## [DEMONSTRATION_PATH]
```bash
# Verify contract field parity for each command
deviate explore pre "test" --dry-run | python -c "import sys,json; c=json.load(sys.stdin); assert all(k in c for k in ['repo_root','git_branch','constitution_path','test_cmd','lint_cmd','type_check_cmd','epic_id','is_greenfield','timestamp'])"
deviate research pre --dry-run | python -c "import sys,json; c=json.load(sys.stdin); assert all(k in c for k in ['repo_root','git_branch','constitution_path','test_cmd','lint_cmd','type_check_cmd'])"

# Verify content validation
deviate explore post  # should validate 5 required sections, not just non-empty

# Verify backward compatibility
ls ~/.claude/skills/deviate-*.sh  # bash scripts still present
bash ~/.claude/skills/deviate-specify/SKILL.md --validate  # still functional

# Full test suite
pytest tests/test_cli/test_macro_contracts.py -v
pytest tests/test_cli/test_meso_contracts.py -v
pytest tests/test_integration/test_parity.py -v
```
