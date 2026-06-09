## Summary

The bash-to-Python CLI transition created a parity gap: macro and meso commands emitted 2–5 JSON contract fields instead of the 15–18 fields the bash originals produce, breaking downstream tooling that depends on complete contracts. This PR brings all six macro/meso pre-commands to full contract parity with bash, adds section-level content validation for all post-phases, integrates pre-commit hooks and mise setup, implements the `deviate run` task dispatcher, and verifies end-to-end parity via integration tests.

## Changes

- **Macro contract parity**: Added shared `_resolve_repo_context()` to `explore`, `research`, `prd`, and `shard` pre-commands in `macro.py`, emitting 15–18 fields (repo_root, git_branch, constitution_path, test/lint/type_check commands, epic_id, is_greenfield, timestamps) matching the bash originals
- **Meso contract emission**: Implemented full JSON contract emission for `tasks pre` and `pr pre` in `meso.py`, which previously emitted no contract at all
- **Content validation engine**: Built section-level validators (`validate_sections`, `validate_yaml_frontmatter`, `validate_task_id`) in `validation.py` with a `PostValidator` registry, wired into all macro/meso post-commands
- **CLI flags**: Added `--dry-run` to `prd`, `shard`, `tasks`, and `pr` commands; added `--issue-id` option to `tasks post` for explicit spec resolution
- **Task dispatcher**: Implemented `deviate run` in `micro.py` with dual-format task ID support (`T{NNN}` + `TSK-{issue_number}-{NN}`) and TDD/IMMEDIATE execution mode routing
- **Infrastructure**: Pre-commit hook execution in post-phases, mise setup in new worktrees, ledger protocol alignment with constitution and PRD data models
- **E2E verification**: Integration tests comparing Python vs bash contract field sets and confirming backward compatibility
