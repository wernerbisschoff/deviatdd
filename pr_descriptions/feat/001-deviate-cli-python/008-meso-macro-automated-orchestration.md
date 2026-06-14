Implement `deviate meso` and `deviate macro` automated pipeline commands that sequence the existing pre/post phase functions with agent invocations, eliminating the need to manually step through individual `deviate <phase> pre` and `deviate <phase> post` commands.

**Slim prompt templates** (`src/deviate/prompts/auto/`): Six prompt files for explore, research, prd, shard, specify, and tasks phases following the established KV-cacheable static-prefix + dynamic-suffix pattern. Each includes constitution/CLAUDE.md injection.

**Prompt assembly** (`src/deviate/prompts/assembly.py`): `load_template()`, `inject_constitution()`, and `assemble_prompt()` for loading templates from package resources, injecting governance artifacts, and interpolating context variables — shared by both pipelines.

**`deviate meso`** (`src/deviate/cli/meso.py`): Automated specify→tasks pipeline with `--issue`, `--dry-run`, and `--force` flags. Discovers next unblocked BACKLOG (or targets specific issue), sequences SPECIFY→agent→post→TASKS→agent→post, and handles recovery, PROGRESS-reset, and COMPLETED-abort semantics.

**`deviate macro`** (`src/deviate/cli/macro.py`): Automated explore→research→prd→shard pipeline with `--target`, `--from`, and `--dry-run` flags. Sequences all four phases with agent invocations, validates upstream artifacts at phase boundaries, and supports `--from` resume for interrupted pipelines.

**CLI registration**: Both commands wired into `deviate --help` via `__init__.py`.
