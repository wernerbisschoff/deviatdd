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

### Hard Inclusions

- **`.deviate/prompts/` directory scaffolding** in `deviate init`:
  - Creates `.deviate/prompts/auto/` with all slim automated templates
  - Creates `.deviate/prompts/skills/` with all manual SKILL.md templates
  - Copies from `src/deviate/prompts/` package defaults
  - Idempotent: skips if `.deviate/prompts/` already exists
  - `--refresh-prompts` flag: force overwrite with `--force` confirmation
- **Prompt resolution layer** (`src/deviate/core/prompts.py`):
  - `resolve_prompt(name: str) -> str` — resolve template content via override → fallback chain
  - `resolve_skill(name: str) -> str` — resolve SKILL.md content via override → fallback chain
  - `interpolate(template: str, variables: dict) -> str` — resolve `${PLACEHOLDER}` placeholders
  - `list_overrides() -> list[str]` — enumerate which templates have user overrides
  - `list_defaults() -> list[str]` — enumerate which templates are on package defaults
  - Caching: static placeholders (`${CONSTITUTION}`, `${CLAUDE_MD}`) resolved once, cached for pipeline lifetime
- **Skill installation integration** in `src/deviate/core/skills.py`:
  - `install_skill()` updated to call `resolve_skill()` instead of reading directly from `src/deviate/prompts/skills/`
  - Skill installation now reflects user overrides
- **Automated pipeline integration** in ISS-004, ISS-008:
  - All slim prompt builds call `resolve_prompt("auto/<phase>.md")` instead of reading from `src/deviate/prompts/auto/` directly
- **`deviate init` CLI updates** in `src/deviate/cli/__init__.py`:
  - `--refresh-prompts` flag added to `deviate init`
  - Prompt scaffolding step added to init sequence (after dotfiles, before skill installation)
  - Console output reflecting prompt bootstrapping status

### Defensive Exclusions

- Template validation beyond basic file-existence checks (syntax validation deferred to runtime).
- Web-based prompt editor or GUI.
- Per-phase prompt diffing or merge conflict resolution — `--refresh-prompts` is a blunt overwrite.
- Template versioning or migration — user is responsible for reconciling their overrides with upstream template changes.
- Dynamic prompt generation from database or API sources.

## [UPSTREAM_REQUIREMENT_TRACING]

- **FR-010-PROMPT-DIR**: `.deviate/prompts/` directory created by `deviate init`, containing `auto/` and `skills/` subdirectories mirroring package defaults.
- **FR-010-RESOLUTION**: Prompt resolution layer that checks `.deviate/prompts/` override first, falls back to `src/deviate/prompts/` package default.
- **FR-010-IDEMPOTENCY**: `deviate init` never overwrites existing `.deviate/prompts/` files unless `--refresh-prompts --force` is explicitly passed.
- **FR-010-INTERPOLATION**: `${PLACEHOLDER}` variable interpolation in all templates, with static variables cached per pipeline invocation.
- **FR-010-SKILL-INSTALL**: Skill installation resolves from override chain, so user edits to `.deviate/prompts/skills/` propagate to agent directories on next `deviate init`.
- **FR-010-PIPELINE**: Automated pipelines (ISS-004, ISS-008) resolve slim prompts from the override chain, so user edits to `.deviate/prompts/auto/` take effect immediately.

## [MULTI_TIERED_VERIFICATION_TARGETS]

- **Unit Tests**: `tests/test_core/test_prompts.py` — resolution order, interpolation, caching, idempotency of copy
- **Integration Tests**: `tests/test_cli/test_init.py` — prompt scaffolding assertions, `--refresh-prompts` behavior
- **Integration Tests**: `tests/test_integration/test_prompt_overrides.py` — end-to-end override → agent → execution

## [DEMONSTRATION_PATH]

```bash
# Verify prompt resolution layer
pytest tests/test_core/test_prompts.py -v

# Verify init scaffolding
pytest tests/test_cli/test_init.py -v -k prompt

# Verify end-to-end override flow
pytest tests/test_integration/test_prompt_overrides.py -v

# Manual verification
deviate init
ls .deviate/prompts/auto/
ls .deviate/prompts/skills/

# Edit a prompt, verify it takes effect
echo "# custom" >> .deviate/prompts/auto/red.md
deviate micro T001 --dry-run  # should show custom prompt content

# Reset to defaults
deviate init --refresh-prompts

mise run check
```
