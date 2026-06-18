The `context` CLI provides local-first, offline-queryable documentation for all project dependencies. This issue integrates it into every layer of the DeviaTDD framework — config detection at init, universal governance mandates in CLAUDE.md and AGENTS.md, phase-level documentation lookup guidance in core prompts, and per-skill `context add`/`context query` instructions for the explore, adhoc, research, and plan phases.

- **Config & detection**: Added `use_context` boolean to `DeviateConfig` with `shutil.which("context")` auto-detection during `deviate init` — persists in `.deviate/config.toml`
- **Governance seeds**: Appended `## Offline Context Documentation System` section to both `claudemd_seed.md` and `agents_seed.md` — all agents must prefer `context query` over web fetch
- **Core prompt mandate**: Added `### Offline Documentation Lookup` to `core.md` (loaded by every phase) plus context consultation bullets in `macro-skill.md`, `meso-skill.md`, and `micro-skill.md`
- **Skill-level integration**: Threaded `context add <source>` into explore and adhoc skills (registration during discovery), `context query <library> <topic>` into research and plan skills (lookup during analysis)
- **Micro-layer retry**: Backported `train_feedback` capture on green/execute retry cycles for consistent test-failure reporting across the TDD pipeline
