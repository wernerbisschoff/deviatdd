This PR replaces the legacy DeviaTDD bash orchestrator scripts (~8,000 lines across 15 scripts) with a unified Python CLI under `deviate <subcommand> pre/post` commands, eliminating the bash dependency entirely. It implements 11 core shared modules in `src/deviate/core/`, fixes critical data model bugs in the JSONL issue ledger, and refactors the macro/meso CLI layers for the worktree-based TDD workflow.

**Data Model Fixes**: Fixed `IssueRecord` Pydantic schema to match actual JSONL fields (`issue_id`, `type`, `status`, `source_file`, `blocked_by`, `coordinates_with`, `timestamp`), added malformed-line recovery with skip-warn, corrected key mismatches in `resolve_issue_record`, and fixed `macro.py:prd` artifact check to use `design.md` + `data-model.md`.

**Core Modules**: Implemented 11 shared modules (`repo`, `ledger`, `contract`, `commit`, `constitution`, `validation`, `worktree`, `issues`, `epic`, `prd`, `skills`) with repository discovery, JSONL lifecycle, JSON contract round-trip, git commit workflows, constitution parsing, Gherkin validation, worktree management, issue resolution, epic allocation, PRD extraction, and skill installation.

**CLI Layer**: Refactored macro layer (`deviate explore/research/prd/shard pre/post`) and meso layer (`deviate specify/tasks/pr pre/post`) from stubs into full implementations with worktree management, ledger state transitions, content validation gates, and divergence detection.

**Skill Migration**: Moved 15 SKILL.md files from `prompts/` to `src/deviate/prompts/skills/`, rewrote all invocation references from `<SKILL_DIR>/deviate-*.sh` to `deviate <subcommand>`, removed all 15 bash orchestrator scripts, and removed `deviate-cycle` skill.

**Init Integration**: Extended `deviate init` with automatic agent detection (`.claude/`, `.opencode/`, `.factory/`), `--agent` flag override, interactive fallback, and content-hash-based skill installation with skip/overwrite idempotency.

**Session State**: Implemented dual-mode session state enforcing strict phase ordering with filesystem divergence detection, worktree-based state reconstruction on `session.json` loss, and task ID normalization (accepting both `T{NNN}` and `T{NNN}:`).

**Git Isolation**: Applied `GIT_DIR` environment variable stripping across all git subprocess calls to prevent pre-commit hook leaks into the real repository during test execution.
