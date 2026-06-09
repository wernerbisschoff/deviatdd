---
title: "[FR-010] Prompt Configuration & User-Editable Template Overrides"
labels: ["epic:001-deviate-cli-python", "layer:infra", "layer:prompts"]
source_file: "specs/001-deviate-cli-python/prd.md"
blocked_by: []
coordinates_with: ["ISS-004", "ISS-005"]
issue_id: "ISS-010"
---

## [SYSTEM_TOPOLOGY_MAPPING]
- **Epic Domain**: `001-deviate-cli-python`
- **Local File Path**: `specs/001-deviate-cli-python/issues/010-prompt-configuration-template-overrides.md`
- **Workstation Paths**:
  - `src/deviate/cli/__init__.py` — `deviate init` extended with prompt scaffolding + `--refresh-prompts`
  - `src/deviate/core/prompts.py` — Prompt resolution layer (override → package fallback), template loading, placeholder interpolation
  - `src/deviate/core/skills.py` — Skill installation updated to resolve from `.deviate/prompts/` first
  - `.deviate/prompts/` — User-editable prompt template overrides (created by `deviate init`)
  - `.deviate/prompts/auto/` — Slim automated prompt overrides
  - `.deviate/prompts/skills/` — Manual SKILL.md overrides
  - `src/deviate/prompts/` — Package defaults (unchanged, read-only reference)
  - `tests/test_core/test_prompts.py`
  - `tests/test_cli/test_init.py` — Extended for prompt scaffolding assertions

## [THE_PROBLEM_CONTRACT]
As a developer customizing the DeviaTDD workflow for my project, I need user-visible, editable prompt templates in `.deviate/prompts/` that override the package defaults — so I can see exactly what prompts my agents receive, customize them without editing package source, and have confidence that editing the right file affects the right execution path (manual skills vs. automated pipeline). I also need `deviate init` to bootstrap these templates idempotently, never overwriting my customizations unless I explicitly request a refresh.

## [ARCHITECTURAL_OVERVIEW]

### Dual Template Source Model

```
.deviate/prompts/              ← USER LAND (created by deviate init)
├── auto/                      ← Overrides for automated slim prompts
│   ├── red.md                 ← Used by deviate micro RED phase
│   ├── green.md               ← Used by deviate micro GREEN phase
│   ├── refactor.md            ← Used by deviate micro REFACTOR phase
│   ├── judge.md               ← Used by deviate micro JUDGE phase
│   ├── yellow.md              ← Used by deviate micro YELLOW phase
│   ├── specify.md             ← Used by deviate meso SPECIFY phase
│   ├── tasks.md               ← Used by deviate meso TASKS phase
│   ├── explore.md             ← Used by deviate macro EXPLORE phase
│   ├── research.md            ← Used by deviate macro RESEARCH phase
│   ├── prd.md                 ← Used by deviate macro PRD phase
│   └── shard.md               ← Used by deviate macro SHARD phase
└── skills/                    ← Overrides for manual SKILL.md prompts
    ├── deviate-red/SKILL.md
    ├── deviate-green/SKILL.md
    ├── deviate-refactor/SKILL.md
    ├── deviate-specify/SKILL.md
    ├── deviate-tasks/SKILL.md
    └── ... (all 18 skills)

src/deviate/prompts/           ← PACKAGE DEFAULTS (read-only, versioned)
├── auto/                      ← Fallback for automated slim prompts
│   ├── red.md
│   ├── green.md
│   └── ...
└── skills/                    ← Fallback for manual SKILL.md prompts
    ├── deviate-red/SKILL.md
    └── ...
```

### Resolution Order (for every prompt load)

```
resolve_prompt("auto/red.md"):
  1. .deviate/prompts/auto/red.md     ← user override (if exists)
  2. src/deviate/prompts/auto/red.md  ← package default (fallback)

resolve_skill("deviate-red"):
  1. .deviate/prompts/skills/deviate-red/SKILL.md  ← user override
  2. src/deviate/prompts/skills/deviate-red/SKILL.md ← package default
```

### `deviate init` Behavior

```
deviate init (normal):
  └─ If .deviate/prompts/ does not exist:
       ├─ Create .deviate/prompts/auto/   ← copy ALL from src/deviate/prompts/auto/
       └─ Create .deviate/prompts/skills/ ← copy ALL from src/deviate/prompts/skills/
     Else:
       └─ IDEMPOTENT — do NOT overwrite existing files
       └─ Output: "prompts/ already exists, skipping (use --refresh-prompts to reset)"

deviate init --refresh-prompts:
  └─ Force overwrite ALL .deviate/prompts/ from package defaults
  └─ Output warning: "This will overwrite any custom prompt edits in .deviate/prompts/"
  └─ Require --force confirmation
```

### Skill Installation Integration

When `deviate init` installs skills to agent directories (e.g., `.opencode/skills/deviate-red/SKILL.md`), it now resolves from the override chain:

```
install_skill("deviate-red", target_dir):
  content = resolve_skill("deviate-red")   ← checks .deviate/ override first
  write content to target_dir / "deviate-red" / "SKILL.md"
```

This means: user edits `.deviate/prompts/skills/deviate-red/SKILL.md` → runs `deviate init` → agent skill is updated with their customizations.

### Placeholder Variable Interpolation

All templates (both auto and skills) support `${PLACEHOLDER}` variables resolved at prompt-build time:

| Placeholder | Source | Cached? |
|-------------|--------|---------|
| `${CONSTITUTION}` | `specs/constitution.md` content | Yes (static per project) |
| `${CLAUDE_MD}` | `CLAUDE.md` content | Yes (static per project) |
| `${TASK_DESCRIPTION}` | `TaskRecord.description` | No |
| `${TASK_ID}` | `TaskRecord.id` | No |
| `${SPEC_EXCERPT}` | Relevant `spec.md` section | No |
| `${TEST_COMMAND}` | Constitution extract or task contract | No |
| `${LINT_COMMAND}` | Constitution extract or task contract | No |
| `${REPO_ROOT}` | `Path.cwd()` | Yes (static per invocation) |
| `${FEATURE_SLUG}` | Epic slug from session | No |
| `${ISSUE_ID}` | Active issue ID from session | No |

Static variables (`${CONSTITUTION}`, `${CLAUDE_MD}`, `${REPO_ROOT}`) are resolved once per pipeline invocation and cached. Dynamic variables are resolved per phase.

### Template Format

Each template is a plain Markdown file with `${PLACEHOLDER}` variables:

```markdown
## [ROLE]
You are a test writer in the RED phase of TDD.

## [GOVERNANCE]
${CONSTITUTION}

## [AGENT_RULES]
${CLAUDE_MD}

## [TASK]
Task ID: ${TASK_ID}
${TASK_DESCRIPTION}

## [CONSTRAINTS]
- Write tests to: tests/
- Test command: ${TEST_COMMAND}
- Tests MUST fail due to missing implementation

## [OUTPUT]
\`\`\`yaml
phase: RED
task_id: "${TASK_ID}"
test_file: path/to/test.py
\`\`\`
```

## [SCOPE_BOUNDARIES]

### Hard Inclusions (✅ Infrastructure — Implemented)

- **`.deviate/prompts/` directory scaffolding** in `deviate init`:
  - Creates `.deviate/prompts/auto/` with all automated templates
  - Creates `.deviate/prompts/commands/` with all command templates (instead of `skills/`)
  - Copies from `src/deviate/prompts/` package defaults
  - Idempotent: skips if `.deviate/prompts/` already exists
  - `--refresh-prompts` flag: force overwrite with `--force` confirmation
- **Prompt resolution layer** (`src/deviate/core/prompts.py`):
  - `resolve_prompt(name: str) -> str` — resolve auto template content via override → fallback chain
  - `resolve_command(name: str) -> str` — resolve command template content via override → fallback chain
  - `interpolate(template: str, variables: dict) -> str` — resolve `${PLACEHOLDER}` placeholders
  - `list_overrides() -> list[str]` — enumerate which templates have user overrides
  - `list_defaults() -> list[str]` — enumerate which templates are on package defaults
  - Caching: static placeholders (`${CONSTITUTION}`, `${CLAUDE_MD}`) resolved once, cached for pipeline lifetime
- **Command installation integration** in `src/deviate/core/skills.py`:
  - `install_command()` reads from the override chain before package defaults
  - Installed commands now reflect user overrides
- **Automated pipeline integration** in ISS-004, ISS-008:
  - All automated prompt builds call `resolve_prompt("auto/<phase>.md")` instead of reading from `src/deviate/prompts/auto/` directly
- **`deviate init` CLI updates** in `src/deviate/cli/__init__.py`:
  - `--refresh-prompts` flag added to `deviate init`
  - Prompt scaffolding step added to init sequence (after dotfiles, before command installation)
  - Console output reflecting prompt bootstrapping status

### Hard Inclusions (❌ Template Content — Needs Restoration)

Source-of-truth prompt templates in `src/deviate/prompts/` were created as stripped-down stubs (~28-34 lines) that lost all the rich behavioral instructions, XML structure, invariants, subagent blueprints, execution sequences, and edge case handling from the original skills. These must be restored:

- **`src/deviate/prompts/commands/` (18 files)** — Must contain the FULL original skill content (restored from git history at `bd18ddc^:src/deviate/prompts/skills/`). Each file = the complete original `SKILL.md` verbatim, including:
  - YAML frontmatter with name, description, category, version, aliases
  - `<system_instructions>` with ROLE_DEFINITION, CRITICAL INSTRUCTION INVARIANTS, tier classification
  - `<subagent_blueprint_directory>` with subagent prompts for parallel delegation
  - `<execution_sequence>` with step-by-step workflow including `deviate * pre/post` CLI calls
  - `<output_format_schemas>` with full output structure
  - `<edge_case_handling>` with condition/action tables
  - `<context>` with `<user_input>$ARGUMENTS</user_input>`
- **`src/deviate/prompts/auto/` (11 files)** — Must contain the CORE content from the originals, stripping ONLY:
  - `<subagent_blueprint_directory>` blocks (attached files — not needed in auto mode)
  - `<execution_sequence>` blocks (CLI pre/post orchestration — handled by deviate engine)
  - `<context>` blocks (user input — handled by pipeline)
  - Preserve: `<system_instructions>`, `<output_format_schemas>`, `<edge_case_handling>` with full invariant rules and behavioral instructions

### Defensive Exclusions

- Template validation beyond basic file-existence checks (syntax validation deferred to runtime).
- Web-based prompt editor or GUI.
- Per-phase prompt diffing or merge conflict resolution — `--refresh-prompts` is a blunt overwrite.
- Template versioning or migration — user is responsible for reconciling their overrides with upstream template changes.
- Dynamic prompt generation from database or API sources.

## [UPSTREAM_REQUIREMENT_TRACING]

### Infrastructure (✅ Implemented)
- **FR-010-PROMPT-DIR**: `.deviate/prompts/` directory created by `deviate init`, containing `auto/` and `commands/` subdirectories mirroring package defaults.
- **FR-010-RESOLUTION**: Prompt resolution layer that checks `.deviate/prompts/` override first, falls back to `src/deviate/prompts/` package default.
- **FR-010-IDEMPOTENCY**: `deviate init` never overwrites existing `.deviate/prompts/` files unless `--refresh-prompts --force` is explicitly passed.
- **FR-010-INTERPOLATION**: `${PLACEHOLDER}` variable interpolation in all templates, with static variables cached per pipeline invocation.
- **FR-010-COMMAND-INSTALL**: Command installation resolves from override chain, so user edits to `.deviate/prompts/commands/` propagate to agent directories on next `deviate init`.
- **FR-010-PIPELINE**: Automated pipelines (ISS-004, ISS-008) resolve auto prompts from the override chain, so user edits to `.deviate/prompts/auto/` take effect immediately.

### Template Content (❌ Needs Work)
- **FR-010-CMD-CONTENT**: Each `src/deviate/prompts/commands/deviate-*.md` must contain the FULL original skill content restored from git history — XML tags, subagent blueprints, execution sequences, pre/post CLI calls, output schemas, edge cases, and `<user_input>` context blocks intact. All 18 commands restored.
- **FR-010-AUTO-CONTENT**: Each `src/deviate/prompts/auto/*.md` must contain the CORE content from the original skills: `<system_instructions>` with invariants, `<output_format_schemas>`, `<edge_case_handling>` — stripping only subagent blueprints, execution sequences, and context blocks. All 11 auto prompts restored.

## [MULTI_TIERED_VERIFICATION_TARGETS]

### Infrastructure (✅ Already Passing)
- **Unit Tests**: `tests/test_core/test_prompts.py` — resolution order, interpolation, caching, idempotency of copy
- **Integration Tests**: `tests/test_cli/test_init.py` — prompt scaffolding assertions, `--refresh-prompts` behavior
- **Integration Tests**: `tests/test_integration/test_prompt_overrides.py` — end-to-end override → agent → execution

### Template Content (❌ Needs Verification)
- **Content Integrity**: Each `commands/deviate-*.md` line count matches original skill (119–360 lines), not stub (~28 lines)
- **Structural Integrity**: Each `commands/deviate-*.md` contains `<system_instructions>`, `<execution_sequence>`, `<edge_case_handling>`
- **Auto Integrity**: Each `auto/*.md` contains `<system_instructions>`, `<output_format_schemas>`, `<edge_case_handling>`
- **Auto Exclusion**: No `auto/*.md` contains `<subagent_blueprint_directory>`, `<execution_sequence>`, or `<context>` blocks
- **No Regression**: `pytest tests/test_core/ tests/test_cli/ tests/test_integration/ -v`

## [DEMONSTRATION_PATH]

```bash
# Verify infrastructure (should pass without content changes)
pytest tests/test_core/test_prompts.py -v

# Verify init scaffolding
pytest tests/test_cli/test_init.py -v -k prompt

# Verify end-to-end override flow
pytest tests/test_integration/test_prompt_overrides.py -v

# Verify command content restored (line counts match originals)
for f in src/deviate/prompts/commands/*.md; do
  name=$(basename "$f" .md)
  lines=$(wc -l < "$f")
  echo "$name: $lines lines"
done

# Verify auto content has XML tags but no subagent/execution blocks
grep -l '<system_instructions>' src/deviate/prompts/auto/*.md
grep -l '<subagent_blueprint_directory>' src/deviate/prompts/auto/*.md && echo "FAIL: auto has subagent blueprints"

# Full check
mise run check
```
