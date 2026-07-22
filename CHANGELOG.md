# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- **Native Herdr lifecycle reporting for `deviate run`, `deviate meso run`, and `deviate micro run`.** When launched from a Herdr-tracked pane (with `HERDR_ENV=1`, `HERDR_SOCKET_PATH`, and `HERDR_PANE_ID`), the console-script boundary in `src/deviate/main.py` sends the wrapper-compatible `pane.report_agent` envelope directly over `HERDR_SOCKET_PATH`: `working` on entry, `idle` after a zero exit, and `blocked` after a non-zero exit or uncaught exception. Source is `herdr:deviate`, agent is `omp`, and the exit code or exception type is carried in the message (no payload secrets, ever). Socket delivery is best-effort and cannot change the command's result, so commands behave identically whether or not Herdr is running.
- **Added `deviate inspect issues show <ISS-ID>` and `deviate inspect tasks show <TSK-ID>`.** These commands emit one matching ledger record in JSON or readable form.
- **HTML preview for human-review specs (`deviate render`, plus auto-render on `plan post` / `prd post`).** New `deviate render` subcommand (`plan`, `prd`, `flows`, `all`) renders any spec markdown to standalone HTML — `flows/index.md` and `flows-<domain>.md` use this manual command (they're authored via `/deviate-flows` and have no post-hook); `plan.md` and `prd.md` render automatically when their markdown has pending changes (gated on `git status` so a CSS-only `specs.css` edit doesn't produce a spurious commit). Renderer is byte-deterministic, CommonMark + tables + fenced-code + CodeHilite, embeds `specs.css` inline (works offline via `file://`), and highlights `FR-NNN-ID`, `AC-NNN-ID-NN`, and `FLOW-NN` tokens for visual scanning. New `markdown>=3.6` dep; new `src/deviate/core/specs_html.py` and `src/deviate/assets/specs.css`; new `src/deviate/cli/_render.py` (`render_app`). CLI prints `[cyan]HTML_PREVIEW[/] <path>` after every successful commit.

### Changed
- **`deviate research pre` now moves `explore.md` from `specs/explore/&lt;slug&gt;.md` into the numbered epic directory at `specs/{NNN}-&lt;slug&gt;/explore.md` (clean cutover, source removed — no orphan staging copy).** Every research/PRD/shard artifact for one feature now lives under a single numbered directory: `explore.md` (the empirical input) + `design.md` + `data-model.md` + `prd.md` + `issues/*`. The contract payload for `research pre` updates `explore_md_path` and `explore_path` to the new location, and `prd pre` now requires `explore.md` inside the epic dir (emitting a new `explore_md_path` contract field). `prd pre` halts with `missing upstream artifact: explore.md` if the epic was not promoted through research correctly. **Scope: new epics only** — the in-flight `specs/001-*`, `specs/002-*`, and `specs/003-*` directories are left as-is (they predate the move and lack `explore.md` inside their epic dir); only `deviate research pre` runs from this commit forward will see the moved layout. `_discover_all` (`src/deviate/core/epic.py`) emits a `UserWarning` for any legacy numbered dir missing `explore.md` so the asymmetry is visible to operators. The retired `deviate research pre` legacy-format fallback (`specs/&lt;slug&gt;/explore.md`) is no longer consulted. (`src/deviate/cli/macro.py`, `src/deviate/core/epic.py`, `tests/test_macro/test_research.py`, `tests/test_macro/test_prd.py`, `tests/test_core/test_epic.py`, `tests/test_cli/test_macro_contracts.py`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `specs/constitution.md`, `src/deviate/prompts/commands/deviate-research.md`, `src/deviate/prompts/commands/deviate-adhoc.md`.)
- **Internal phase markers are no longer shown in normal streamed-agent output.** `Status: GREEN_STATE_ACHIEVED`, `Status: TEST_WRITTEN_FAILING`, and `Status: TASK_COMPLETE` are suppressed from the normal console stream while remaining available under `--verbose`; orchestration and Herdr lifecycle status remain independent.
- **Bounded JUDGE feedback history in `tasks.md`.** The runner keeps the last three distinct feedback rounds per task and deduplicates repeated rounds, preventing unbounded prompt growth.
- **Improved DeviaTDD skill discoverability.** The skill now surfaces `deviate micro run <TASK_ID> --dry-run` and the issue/task `show` commands before long-running execution.
- **Stopped stale GREEN/JUDGE retry loops with `GREEN_STATE_DRIFT`.** A first-pass zero-change GREEN still proceeds to JUDGE, but a feedback-driven retry whose ledger already records GREEN and which creates no implementation commit now fails explicitly for operator verification and append-only ledger reconciliation instead of sending JUDGE a feedback-only diff.
- **JUDGE now sees failed GREEN worktree changes, and retried GREEN receives explicit rollback context.** When GREEN tests fail before an implementation commit, JUDGE receives the committed RED-parent diff plus staged, unstaged, and untracked worktree patches instead of falsely evaluating a RED-only snapshot. After `revert_to_red`, the next GREEN prompt states that rollback discarded prior GREEN artifacts and requires on-disk verification and recreation of missing files.
- **Paused Herdr pane on close so failure output stays visible (emit order corrected).** `with_herdr_status` (`src/deviate/core/herdr.py`) emits the terminal `idle` / `blocked` envelope immediately before `pause_for_close()`. Previously the terminal envelope was emitted after the pause; reordering ensures Herdr observes it while its `(source, agent)` authority is still live. The function blocks on stdin until the operator presses Enter, gated on `HERDR_ENV=1`, `sys.stdin.isatty()`, `TERM != "dumb"`, and `HERDR_DEVIATE_NO_PAUSE != "1"`. EOF / Ctrl-D / Ctrl-C return silently without hanging. Use `HERDR_DEVIATE_NO_PAUSE=1` to opt out (e.g. for non-interactive launches that accidentally inherit the Herdr environment).
- **GREEN `failure_kind: test_defect` discriminator routes to RED via JUDGE.** A second routable GREEN failure class, parallel to the existing `mechanical` discriminator. When GREEN observes that the RED test itself is wrong — asserts behavior the spec does not require, exercises the wrong abstraction, or contradicts spec/data-model — it emits `status: FAILURE` + `rationale:` + `failure_kind: test_defect` on the manifest. `_run_green_phase` reads the discriminator and sets `session.failure_kind = "test_defect"`; `_run_judge_phase` injects a `<failure_kind>test_defect</failure_kind>` block that pre-decides `next_action: revert_before` (re-run RED with the GREEN rationale as feedback). `HandoverManifest.failure_kind` (Literal["mechanical", "test_defect"] | None) and `SessionState.failure_kind` (Literal["", "mechanical", "test_defect"]) widened; runner defaults to "mechanical" when the manifest field is unset so prior behavior holds. Specs updated: `DeviaTDD-api.md` § GREEN Test-Defect Failure → JUDGE Routing, `DeviaTDD-architecture.md` § Test-Defect Failure → JUDGE Routing. Tests: `test_micro_green_test_defect_failure_routes_to_judge` (runner routing), `test_judge_auto_prompt_handles_test_defect_failure` (JUDGE prompt content), `test_green_auto_prompt_documents_test_defect_failure` (GREEN prompt content).
- **Native Herdr lifecycle reporting for `deviate run`, `deviate meso run`, and `deviate micro run`.** When launched from a Herdr-tracked pane, each command now sends the wrapper-compatible `pane.report_agent` envelope directly over `HERDR_SOCKET_PATH`: `working` while the callback runs, `idle` after a zero exit, and `blocked` after a non-zero exit or uncaught exception. Socket delivery is best-effort and cannot change the command's result, making the external `~/.local/bin/deviate` process-watching wrapper redundant.

- **Isolated coding-eval harness (`scripts/coding_eval.py`) and `bench-coding-mini` mise task.** New script generates HumanEval+ completions on LM Studio-hosted chat models (one model at a time, loaded/unloaded via the v1 REST API) and grades each by running the model's completion through evalplus's `untrusted_check` (multiprocessing sandbox, no Docker required). Emits a per-cell results jsonl with reasoning-token accounting plus a final markdown summary table — replaces the throughput-only view from `scripts/benchmark_lmstudio.py` with actual pass-rate signal. Default candidate set is the three non-truncated models from the throughput benchmark (`qwen3-coder-30b-a3b-instruct`, `qwen3.5-4b`, `qwen/qwen3.5-9b`) plus the two `qwopus` MTP coder variants so we can answer whether their slowness buys any quality. `bench-coding-mini` runs the 12-problem mini slice through all candidates (~1.5–2h); pass `--problems full` for the 164-problem overnight sweep. Per-cell files (`<out>.<model>.<level>.jsonl` + `.samples.jsonl`) carry the row-level data; the top-level `<out>.jsonl` is an append-only index of `__summary__` records pointing at each cell. Dev deps added: `evalplus>=0.3.1`, `pytest-timeout>=2.4`. First run surfaced and fixed two bugs: per-cell `out_path` was clobbering prior cells (now per-cell files), and the 180s chat-completion timeout was too short for cold-start first-call on 9B-class models (now 600s, matching the load timeout).
- **Flow Ledger Canonical Source of Truth — `specs/_product/flows.jsonl` append-only ledger + Flow Coverage Report in `deviate explore post`.** New `FlowRecord` / `FlowEvent` / `FlowCoverage` Pydantic models in `src/deviate/state/ledger.py` following the append-only ledger protocol (`model_config={"extra": "forbid"}`, `^FLOW-\d{2,}$` regex validation). `load_flow_coverage` derives drift-flag taxonomy by reverse-indexing `specs/issues.jsonl` `flow_refs` fields. `deviate explore post` renders a Rich-formatted Flow Coverage Report table (six columns: `flow_id | actor/job/trigger | documented? | implementation evidence? | last referenced by issue/release? | drift flag`). `.gitattributes` merge=union rule for `specs/_product/flows.jsonl`. Constitution v0.7.0 enumerates `flows.jsonl` alongside `issues.jsonl`/`tasks.jsonl` in §1 Append-Only Ledger Protocol.
- **`deviate inspect flows coverage [--release PATH] [--json]` — read-only query grounding `/deviate-release` Included Work / Deferred Epics.** New subcommand under `deviate inspect` (mirroring the `issues_app` / `tasks_app` Typer sub-app pattern) calls `load_flow_coverage(ledger_path, flows_index, issues_ledger)` from `src/deviate/state/ledger.py` to derive per-FLOW-NN coverage rows (documented / implemented / drift flag / last-referenced-by) from `specs/_product/flows.jsonl` + `specs/_product/flows/index.md` + reverse-indexed `flow_refs` from `specs/issues.jsonl`, rendered as a Rich table that surfaces the seven drift flags. `--release <release-next.md>` parses the Included Flows Markdown table conservatively (rows starting with `| FLOW-`) and filters the FlowCoverage rows to only those flow_ids so operators see "what's incomplete for THIS release" rather than globally. When the ledger has not yet been seeded by `deviate explore post`, the command emits `[yellow]NO_FLOWS_LEDGER[/]` to stderr and exits 0 with an empty JSON `[]`, keeping `inspect` strictly read-only per the append-only ledger contract. The `/deviate-release` skill body (v1.2.0) now invokes `load_flow_coverage` as part of its Included Work / Deferred Epics grounding so release composition is anchored in real coverage state, not prose. (`src/deviate/cli/inspect.py`, `tests/test_cli/test_inspect.py`, `src/deviate/prompts/commands/deviate-release.md`.)
- **Per-task structured logs under `.deviate/logs/<ISSUE_ID>/<TASK_ID>.log`.** New `TaskLogger` in `src/deviate/core/run_logger.py` writes every `INVOKE_AGENT` / `AGENT_RESULT` / `AGENT_RAW_OUTPUT` / `PHASE_*` event for one task into its own append-mode log file, complementing the existing chronological per-run log at `.deviate/logs/run_<UTC>.log`. `set_task_logger` / `set_run_logger` now route through a small registry so `_log_run` fans out to both sinks. Wired in `_execute_task_with_retry` so every dispatched task (single or `--all`) gets a per-task transcript that survives re-runs and is human-scannable. The summary agent's fallback message and the `.deviate/.gitignore` template were updated to reference the new `.deviate/logs/` location instead of the long-gone `.deviate/prompts.log`.
 - **Auto GREEN now consumes persisted JUDGE feedback from `tasks.md` when session feedback is unavailable.** Session `train_feedback` remains authoritative, with exact task scoping and no duplicate injection.
- **`_execute_rollback()` now runs `git clean -fd` after `git reset --hard`.** Previously, a failed GREEN attempt could leave behind untracked artifacts (scratch files, build outputs, helper scripts) that persisted into the next RED attempt — pytest collection could pick them up, the test writer agent could trip over them, and stale `__pycache__` could shadow fresh test imports. After the `git reset --hard <red_sha>` discards the suspect GREEN commits, `_execute_rollback()` now runs `git clean -fd` (force + directories, **without** `-x`) to wipe untracked files and directories while preserving gitignored state (`.deviate/`, `.mise/`, `__pycache__/`, `.worktrees/`) so the audit trail in `.deviate/rollback.jsonl` and session state in `.deviate/session.json` survive the rollback. New integration tests in `tests/test_micro/test_judge.py::TestExecuteRollbackUntrackedCleanup` exercise the untracked-file, untracked-directory, and gitignore-preservation invariants against a real `tmp_git_repo` (with `.gitignore` mirroring production). (`src/deviate/cli/micro.py::_execute_rollback`, `tests/test_micro/test_judge.py::TestExecuteRollbackUntrackedCleanup`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`.)
- **`deviate micro run`: GREEN phase failures with empty rationale now surface the agent's last 50 stdout lines in the FAILED message.**
- **GREEN Stub-PASS Guard was reverted; deciding whether a task is done is JUDGE's job.**
  An earlier revision of `6463060` (and follow-ups) tried to reject `status: PASS`
  manifests with zero observed source changes. The implementation was rolled back:
  the JUDGE prompt's edge case table emits `COMPLIANCE_PASS` with note `NO_DIFF`
  for empty diffs, so a zero-change PASS routes to REFACTOR or the next task
  instead of looping GREEN against a stub-PASS guard. GREEN's invariant is "make
  tests pass"; a feature that already works (e.g. landed in a prior session, a
  docs/rename task) is a legitimate PASS. `HandoverManifest.files: list[str] | None`
  remains on the schema as an optional operator cross-check signal — not evidence.
  `src/deviate/prompts/auto/green.md` was rewritten: `files:` is recommended, not
  required. See `DeviaTDD-api.md` § GREEN Stub-PASS Guard (REMOVED).
- **`/deviate-merge` (v2.1.0) now gates the squash-merge commit on a post-staging git status check.**
  The execution flow gained a new step 4 between ledger staging (`deviate merge --stage-only`) and the
  final `deviate merge --message` commit: `git status --porcelain` must be empty AND
  `git diff --cached --quiet` must succeed, otherwise the prompt halts with
  `Failure_State: Unstaged_Files_Post_Merge`. The diagnostic is **dual-channel** so the operator sees
  it regardless of how the framework renders failure states: `git status --porcelain` is printed
  to stderr verbatim AND embedded inside the `Failure_State` message body
  (`Failure_State: Unstaged_Files_Post_Merge — porcelain non-empty after squash + ledger staging:
  <porcelain dump>`). The prompt no longer silently `git add`s stray files or `--amend`s anything
  in this window — the operator decides whether to investigate, drop, or commit strays. Closes the
  gap where a partial failure between `git merge --squash` and the final commit could leave
  feature-branch files in the index but not in any commit.
- **`/deviate-merge` (v2.3.0) now reads `CONTRIBUTING.md` / `.commit-convention.md` before drafting the squash-merge commit.** The `commit_message_generation` step gained a mandatory **Step 0** before Step A (title format) that `head`s CONTRIBUTING.md (or cats `.commit-convention.md`), confirms whether the project declares an emoji convention, and states that conclusion in the confirmation step so the operator can override. The new Step 0 also forbids bypassing `deviate merge --message` with a direct `git commit` (which would drop the emoji prefix on emoji-convention repos) — the CLI's `format_commit_message` helper in `src/deviate/core/convention.py` is the only path that applies the prefix, and it reads the convention file via `detect_uses_emojis` → `_read_convention_file`. Two new regression tests in `tests/test_cli/test_merge.py` pin the contract end-to-end: `test_merge_honors_contributing_md_emoji_prefix` (CONTRIBUTING.md with `✨` → HEAD subject begins with `✨`) and `test_merge_no_emoji_prefix_when_contributing_md_has_no_emoji` (CONTRIBUTING.md without emoji → HEAD subject unchanged). The two new tests drive a real `git merge --squash` from the fixture's feature branch (unlike the rest of `test_merge.py`, which stage via the CLI alone) so they can assert on the actual `git log -1` subject; cost is ~0.3s per test and bounded at <1s in the suite — flagged in the test file's section header so future contributors do not assume a fast smoke test. (`src/deviate/prompts/commands/deviate-merge.md`, `tests/test_cli/test_merge.py`.)
- **`deviate meso run --no-setup`: run PLAN + TASKS in the current directory without creating a worktree or claiming the issue.** New CLI flag on `deviate meso run` skips the SPECIFY step (worktree creation at `.worktrees/feat/{epic}/{issue}/`, ledger claim, agent-skill sync). PLAN and TASKS then run in `Path.cwd().resolve()` against whatever branch is currently checked out, with phase commits (`plan.md`, `tasks.md`) landing on that branch. The `PipelineBanner` step indicator drops `SPECIFY` (renders `PLAN ▶ TASKS`) and a yellow `[bold]WARN[/]` line above the banner calls out the Git Isolation Principle bypass (`every task loop runs on a clean branch/worktree`). Intended for ephemeral workflows where the operator has prepared a branch manually; the default flow remains the canonical entry point. Source: `src/deviate/cli/meso.py::_meso_run(no_setup=...)` and `meso_run_command(..., no_setup)`; new `skip_auto_claim` kwarg on `_plan_pre` so its contract-building branch runs without a linked worktree. Bypasses `AGENTS.md` Git Isolation Principle — see help string for the footgun.
- **TASKS phase now consumes a bounded plan digest (16 KiB UTF-8 preview) plus `plan_path`.** The meso orchestrator (`src/deviate/cli/meso.py::_build_plan_digest`) replaces the unbounded `plan_content` field with `plan_digest`: when `plan.md` fits, the digest is the full text; when it exceeds 16 KiB the digest keeps the head + tail of the file and inserts a `PLAN_DIGEST_TRUNCATED` marker (with a `plan_path` pointer) so the agent re-reads the full plan on demand. The TASKS auto prompt (`src/deviate/prompts/auto/tasks.md`) was rewritten to reference the literal `<plan_digest>` and `<plan_path>` tags rather than `{plan_digest}` / `{plan_path}` (the latter would re-inject the payload). This prevents the unbounded `plan_content` growth that caused the Gloss 009 TASKS timeout and removes a KV-cache invalidation hazard.
### Fixed
- **`deviate review pre` no longer SIGSEGVs on Rust sources in the diff.** `_compute_structured_diff` in `src/deviate/cli/review.py` now skips Rust files (`get_language_id(filepath) == "rust"`), surfacing the entry in the contract as `language: "unknown"` + empty `symbols` — the same shape the existing non-source-file branch already produces and `deviate-review.md` already documents as the supported fallback. Root cause matches the 2.6.0 JUDGE-phase fix (`OperationError` post-`parser.parse` on `tree_sitter_rust._binding` left the interpreter fork-unsafe; the subsequent `subprocess.Popen` SIGSEGV'd in `_execute_child` → `fork_exec`): `parser.parse()` on large Rust sources observed in this CLI path leaves `tree_sitter_rust._binding` in a state where the next fork segfaults. All non-Rust languages (Python, JS/TS, Go, Elixir, Kotlin, Swift, …) still parse; the four RED-phase `TestReviewPreStructuredDiff` tests covering `.py`/`.txt` shapes still pass unchanged. _Practical note: as of `deviatdd 2.10.0`, the `~/.local/share/uv/tools/deviatdd/` install is **not** editable-mounted — source-tree edits do NOT reach the `deviate` binary live. After pulling this release, re-run `uv tool install --with-editable /Users/werner/Projects/tools/deviatdd` (or `--force` for a copy reinstall) so the patched `review.py` reaches the venv at `…/site-packages/deviate/cli/review.py`._
- **Agent dispatch hardening (Gloss 009 / 013 / Guildwright 001).** `AgentBackend.invoke()` now enforces four contracts: a prompt cap (`MAX_PROMPT_CHARS = 80_000`, head + tail preserved, `PROMPT_TRUNCATED` marker), a streaming stall watchdog (`STREAM_STALL_TIMEOUT_SECONDS = 60`, `AgentTimeoutError(STALL_DETECTED)`), a manifest retry-with-context pass (one extra `subprocess.Popen` whose prompt embeds the previous parse error and a strict-YAML directive; subprocess failures are NOT retried as manifest failures), and widened YAML error hints (backslash-escaped quotes, unbalanced `"` counts, mis-indented `|` block scalars). `HandoverManifest` now defaults `phase` / `status` to `"UNKNOWN"`, populates `parse_errors` when fields are missing, and exposes `is_success…
- **`deviate merge` (CLI) no longer short-circuits on `ALREADY_COMPLETED` when `--stage-only` is followed by `--message`.**
- **Orchestrator JUDGE feedback `git commit` timeout raised from 30s to 300s.** The orchestrator's `git commit` that writes JUDGE feedback (`docs(<tid>): add judge feedback for retry`) at `src/deviate/cli/micro.py::_commit_judge_feedback_and_advance` now uses `JUDGE_FEEDBACK_COMMIT_TIMEOUT_SECONDS = 300` (defined in `src/deviate/core/_shared.py`). Observed pre-commit hook chains on some projects can exceed 30s; the previous deadline surfaced as a raw `subprocess.TimeoutExpired` that propagated up unhandled. The new deadline covers those hook chains while still detecting a genuine hang, and a `subprocess.TimeoutExpired` handler now wraps the commit and raises `PhaseFailedError` with a diagnostic pointing the operator at the active repository's configured Git hooks.
- **Stricter YAML handover manifest extraction.** The `_YAML_MAPPING_START_RE` fallback in `_extract_yaml_block` (`src/deviate/core/agent.py`) now requires the parsed YAML to be a `dict` with at least 2 keys before accepting it. Prose containing a stray `word:` line (e.g. a JUDGE verdict with a verification matrix and a trailing `Status: complete`) no longer gets silently recovered into an `UNKNOWN` `HandoverManifest`; the parser now raises `MalformedHandoverManifestError("No YAML handover manifest detected in agent output.")` with the existing hint, and the manifest-retry path is more likely to recover on the second attempt because the failure now routes through the existing `strict YAML block delimited by \`\`\`yaml ... \`\`\` only` retry directive.
- **`deviate micro run` cycle loop honors JUDGE's forward-route verdict and stops looping GREEN↔JUDGE on RED-only slices.** The TDD cycle (`_run_tdd_cycle` in `src/deviate/cli/micro.py`) previously drove an infinite GREEN↔JUDGE loop when GREEN returned `status: FAILURE` on a task whose slice had no production-code path (e.g. TSK-009-07's RED-only KCH-fabricated fixture + downstream MCP integration test). JUDGE's `next_action: proceed_to_refactor_no_diff` cleared `session.train_feedback` and `session.judge_rejected`, but the cycle's post-JUDGE check `if session.judge_rejected or session.train_feedback or green_tests_failed:` still found `green_tests_failed=True` (the snapshot of `session.train_feedback and session.current_phase == "GREEN"` captured right afte…
- **Herdr pane clears after Enter on the `blocked` exit path.** `with_herdr_status` (`src/deviate/core/herdr.py`) now emits a second `report_state("idle", None)` AFTER `pause_for_close()` on the `blocked` exit path, so the operator-acknowledged output transitions the visible pane to `idle` before the process exits. The post-pause emit lands because Herdr clears the authority on process-exit detection, not on stdin activity; the `report_state` `except BaseException` keeps a failed post-pause emit from altering the command's behavior, leaving the pane at its pre-pause state — same degraded behavior as a failed terminal emit, no worse. The exit-0 path skips the cleanup to avoid a redundant duplicate. Fixes the case where `deviate run` exits with `NO_CLAIMABLE_ISSUES` (or any non-zero exit) and the Herdr-tracked pane stays in `blocked` after the operator presses Enter to close the pane.

### Changed
- **GREEN prompt no longer makes scope/drift judgments — JUDGE owns drift detection.** The GREEN auto prompt (`src/deviate/prompts/auto/green.md`) replaced Mandate 3 ("Contract Drift Detection") and the `Contract drift detected` edge-case row with mechanical scope-boundary language: GREEN implements ONLY production code under `src/`, `lib/`, or `app/` to make the RED test pass via the library/API surface declared in scope; if the RED test cannot be satisfied within that mechanical scope, GREEN sets `status: FAILURE` with a concrete `rationale:` naming the exact test path and why — never `status: ERROR` with `error_kind: contract_drift`, never an `error_kind` string, never a structured escalation dict. `status: "ERROR"` is now strictly tool/orchestration failure. The runner's narrow `_is_hitl_escalation` check stays as a defensive fallback (structured `contract_drift` / `escalates_to` / `hitl_options` dict keys only); it does NOT promote loose-string `error_kind` to a HITL escalation. JUDGE remains the layer that reviews the GREEN diff against the spec and emits `next_action: revert_to_red` / `revert_before` / `continue_refactor` / `skip_refactor` accordingly (with feedback persisted to `tasks.md` so the next GREEN attempt re-reads it via `_read_judge_feedback_from_tasks_md`). Regression pin: `tests/test_micro/test_orchestration.py::test_micro_green_phase_mechanical_failure_does_not_escalate_to_hitl`.
- **GREEN mechanical FAILURE now routes to JUDGE for a routing decision instead of short-circuiting to FAILED.** When GREEN emits ``status: FAILURE`` with a concrete ``rationale:`` (the RED test cannot be satisfied via the library/API surface declared in scope — slice-scope conflict, CLI-surface-out-of-scope, library-API signature mismatch), ``_run_green_phase`` (``src/deviate/cli/micro.py``) now sets ``session.train_feedback = rationale`` + ``session.failure_kind = "mechanical"`` and returns the session so the TDD loop's existing train-failure branch routes control to ``_run_judge_phase``. ``_run_judge_phase`` injects a ``<failure_kind>mechanical</failure_kind>`` discriminator block into the JUDGE prompt instructing the agent to emit ``verdict: COMPLIANCE_VIOLATION`` + ``next_action: revert_before | revert_to_red | skip_refactor`` (the slice-scope test-rewrite / impl-feedback / operator-handoff routing vocabulary) instead of attempting to satisfy the test. The ``SessionState.failure_kind`` field is added to ``src/deviate/state/config.py`` and propagated through both ``transition_to`` and ``force_transition_to``. Empty-rationale ``status: FAILURE`` keeps the prior ``PhaseFailedError("unknown")`` + ``agent_output_tail`` dump behavior (truly broken agent output, no info for JUDGE to review). Two pre-existing bugs fixed in the same commit: ``_run_judge_phase`` reordered ``backend``/``root`` to precede ``_build_auto_prompt`` (latent ``UnboundLocalError`` exposed when JUDGE runs without a prior GREEN success path), and ``_judge_feedback_from_manifest`` now reads ``train_feedback``/``rationale`` from ``model_extra`` as a fallback (previously only ``getattr``, missing values when the manifest was constructed via ``model_construct`` with extra fields). Regression pins: ``tests/test_micro/test_orchestration.py::test_micro_green_mechanical_failure_routes_to_judge_not_failed`` (runner dispatch — 6-call sequence RED→GREEN(mechanical fail)→JUDGE(revert_before)→GREEN(retry)→JUDGE(pass)→REFACTOR), ``test_judge_auto_prompt_handles_mechanical_failure`` (JUDGE prompt content), and ``test_green_auto_prompt_has_no_drift_instruction_language`` (GREEN prompt content, from fc381e9).
- **Prompt-template alignment: layer preambles now share one core file between auto and manual modes.** The 9 near-identical files under `src/deviate/prompts/core/` (`{macro,meso,micro}-{auto,command,skill}.md`) collapsed to 5: `core.md` (universal invariants), `{macro,meso,micro}-shared.md` (layer disciplines, the same source for both modes), and `lifecycle-{auto,manual}.md` (the only thing that varies between CLI-orchestrated and slash-command execution). The three `*-skill.md` files were dead code — nothing in `src/deviate/` loaded them; deleted. `_LAYER_MAP` in `src/deviate/prompts/assembly.py` now points to `*-shared.md`; `compose_command_body` in `src/deviate/core/commands.py` resolves the same shared file plus `lifecycle-manual.md`. The `<context><user_input>$ARGUMENTS</user_input></context>` input marker moved from the macro/meso layer preambles into each per-phase auto file (the 7 macro/meso files: explore, research, prd, shard, specify, plan, tasks), matching the manual-mode pattern that already embedded it in every `commands/deviate-*.md`. Micro auto phases (red, green, refactor, judge, execute) take task injection via `{task_content}`/`{spec_content}` placeholders, not `$ARGUMENTS`, so they correctly remain context-block-free. Behavior is unchanged: all 33 prompt-assembly tests and all 43 command-install/integration tests pass against the new structure; the `deviate setup` install pipeline rewrites existing command files idempotently.
- **`/deviate-architecture` (v1.3.0) now requires explicit user sign-off before committing.** Previously the skill auto-committed `specs/_product/architecture.md` and `specs/_product/domain-model.md` via `commit_artifact` immediately after each write, producing a chain of one-commit-per-edit commits across what is conceptually a single architectural change. The v1.3.0 protocol mirrors `/deviate-flows` v1.4.0: **Phase A (draft)** writes the files to disk and stages them via `deviate.core.commit.stage_files` so the user can `git diff --cached` while iterating — no commit fires mid-conversation; **Phase B (sign-off)** fires exactly once via `deviate.core.commit.stage_and_commit` after the user signals sign-off ("commit", "looks good", "done", "ship it", "approve", "lgtm", "yes" — silence is not sign-off), passing every session-authored architecture and domain-model file in `files=`. The pre-commit `git diff --cached --name-only` audit confirms the staged set is a subset of the session-owned files; any extras halt the commit and surface the discrepancy (no auto-unstage). `commit_artifact`, `git add -A`, and `git commit --only` remain forbidden. The classification banner (`Local` / `Context-Bridging` / `Context-Creating`) rides in the commit body. `--no-verify` is never passed; pre-commit hook failures surface verbatim and stop the skill. (`src/deviate/prompts/commands/deviate-architecture.md`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `tests/test_core/test_commands.py::TestDeviateArchitectureCommitAtSignOff`.)
- **`scripts/coding_eval.py`: default reasoning levels dropped `on` for all models; `--level` is now an opt-in CLI flag.** Empirically `qwen/qwen3.5-9b` at `reasoning_effort=high` burns the entire `max_tokens` budget on the reasoning stream and returns empty visible content (verified live: at `max_tokens=4096` the model emits 4095 reasoning tokens + 0 visible and times out at 600s on a single problem). There is no `max_tokens` value at which this produces a usable signal for HumanEval-sized prompts, so the default sweep no longer tries it. To compare with reasoning enabled on a different model, pass `--level on` (repeatable, defaults still apply per-model when the flag is absent). The internal `off → none` mapping for LM Studio's accepted `reasoning_effort` values is preserved; `_LEVEL_TO_LMS` still has `{'none': 'none', 'off': 'none', 'on': 'high'}` so `--level on` remains a valid path when explicitly requested.
- **`/deviate-architecture` (v1.1.0) now mandates `libref` verification for every architectural claim.**
  Added CRITICAL INVARIANT 10 (Offline Documentation Mandate): the architecture
  skill MUST run `libref list` → `libref query <lib> <topic>` (and `libref add`
  if the package is missing) before writing any component, contract, event
  vocabulary, transport, protocol, framework API, or domain entity. Every
  component description, integration contract, and ADR in `architecture.md`
  MUST carry an inline source anchor (verbatim snippet ≤ 10 lines or exact
  contract field reference) to the `libref` doc that grounded it. Claims that
  cannot be anchored surface as `[yellow]UNVERIFIED_CLAIM[/]` and must be
  grounded before yield or removed. Added a mandatory `### 2a. libref
  Discovery Pass` between flow-catalog read and discovery conversation, and
  added two new edge-case rows (unverified-claim halt + missing-libref-package
  fallback). The mandate was motivated by the FLOW-04 architecture pass,
  where the initial draft asserted an LSP-style transport framing and a
  `tool_call/thinking/edit/message` event vocabulary that did not match the
  actual JSONL-over-stdio protocol and `AgentSessionEvent` taxonomy documented
  in `pi` and `oh-my-pi`; both errors were caught only after libref
  verification. (`src/deviate/prompts/commands/deviate-architecture.md`.)
- **Product-layer skills (`/deviate-flows` v1.3.0, `/deviate-architecture` v1.2.0, `/deviate-release` v1.1.0) now persist and commit their artifacts.**
  All three skills gained a `Persist and Commit` invariant + workflow step +
  edge-case rows. Conversational output alone no longer satisfies a
  Product-layer skill — each skill MUST write its artifact file(s) to disk
  via the `write` tool and create a git commit via
  `deviate.core.commit.commit_artifact` (per `src/deviate/core/commit.py`).
  Conventional Commits subjects per `specs/constitution.md:71-75`:
  `docs(flows): ...`, `docs(architecture): ...`, `docs(release): ...`.
  Architecture commits embed the `Local` / `Context-Bridging` /
  `Context-Creating` classification banner. `--no-verify` is forbidden per
  `AGENTS.md` §Commit Authority; pre-commit hook failures surface verbatim
  and stop the skill. The mandate was motivated by a recurring bug in this
  session where the corrected FLOW-04 architecture, the FLOW-04 release,
  and the FLOW-04 flow block were all emitted into chat but never written
  to disk — blocking `/deviate-release` via its `ARCH_OR_FLOWS_MISSING`
  precondition gate and leaving `/deviate-explore` without a release file
  to read. (`src/deviate/prompts/commands/deviate-{flows,architecture,release}.md`.)
- **`/deviate-flows` (v1.4.0) commits at sign-off instead of after every flow write.**
  Previously the skill committed after each `flows-<domain>.md` write
  (one commit per flow + one for the index row), which split a single
  authoring session across N commits and gave the user no chance to
  review the final shape before anything landed in git. The protocol
  is now split into two phases: **Phase A** writes each flow file +
  matching `index.md` row to disk immediately as the conversation
  progresses (no commit); the working tree stays dirty so the user can
  review with `git diff`. **Phase B** fires exactly once after the user
  signals explicit approval ("commit", "looks good", "done", "ship it",
  "approve", "lgtm", "yes" — silence is not sign-off), invoking
  `deviate.core.commit.stage_and_commit` with the explicit list of
  every session-authored flow file plus `specs/_product/flows/index.md`.
  A pre-commit audit of `git diff --cached --name-only` confirms the
  staged set is a subset of the session-owned files; any extras halt
  the commit and surface the discrepancy (no auto-unstage). The skill
  no longer calls `commit_artifact(path, msg)` (which would emit one
  commit per path) and forbids `git add -A` (which would sweep
  unrelated work). Commit subject follows Conventional Commits:
  `docs(flows): add FLOW-NN[, FLOW-MM, ...] and update index`.
  (`src/deviate/prompts/commands/deviate-flows.md`,
  `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`,
  `tests/test_core/test_commands.py::TestDeviateFlowsCommitAtSignOff`.)
- **`deviate run` is now a full-pipeline orchestrator; per-task dispatch moved to `deviate micro run`.**
  The top-level `deviate run` command now does both `deviate meso run` and
  then runs `deviate micro run --all` inside the worktree the meso step just
  created. The previous per-task / `--all` task dispatcher that used to live
  as top-level `deviate run` was relocated to `deviate micro run [task-id]`
  / `deviate micro run --all`. The new orchestrator supports `--issue`,
  `--force`, `--profile`, `--no-judge`, `--no-refactor`, `--agent`, and
  `--json`. The top-level command remains in the "Run by you (start here)"
  panel as the canonical "go do the next thing" entry point; `deviate micro`
  joined the agent-internal panel alongside `red`/`green`/`judge`/etc.
  `_meso_run` now returns the created worktree path so the orchestrator
  can `chdir` into it without re-deriving the path from the ledger; the
  session's `last_command` is rewritten to the micro subcommand form when
  the orchestrator hands off. (`src/deviate/cli/__init__.py`,
  `src/deviate/cli/micro.py`, `src/deviate/cli/meso.py`,
  `tests/test_cli/test_help.py`, `tests/test_cli/test_micro.py`,
  `tests/test_micro/test_run.py`, `tests/test_micro/test_orchestration.py`,
  `tests/test_cli/test_top_level_run.py`, `README.md`,
  `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`,
  `specs/implementation-gap.md`, `src/deviate/ui/pipeline.py`,
  `src/deviate/prompts/commands/deviate-{walkthrough,review}.md`.)

- **`deviate meso run` default output no longer dumps `_plan_pre` / `_tasks_pre` JSON contracts.**
  Those pre subcommands `print()` their JSON contract on stdout for the
  agent-subprocess CLI workflow (`deviate plan pre` / `deviate tasks pre`).
  When the in-process `_meso_run` parent invoked them directly, the JSON
  leaked onto the user's terminal alongside the useful
  `WORKTREE` / `SPEC_DISCOVERED` lines. A small `_silence_stdout` helper
  captures and discards stdout around the two calls; rich console output
  is unaffected, and the `deviate plan pre` / `deviate tasks pre` CLI
  paths (which route through `@with_json_quiet`) are unchanged.
  (`src/deviate/cli/meso.py`, `tests/test_meso/test_meso_orchestration.py`.)

- `deviate-review` prompt v3.0.0: reframed as JUDGE-aware review. Three domains
  (Clean Code, Constitution, PRD Alignment) downgraded to light-sniff — cross-task
  only, no re-reading governance files. Domain 3 renamed to "Pragmatism &
  Architectural Coherence" with 6 new cross-task checks. Added strategy-gated
  review (full/diff_first/targeted), finding classification with Severity +
  Confidence, and machine-parseable Fix Instructions block. Flow Coverage
  domain made diff-only to match JUDGE-aware posture. (PR #?.)
- `deviate-review` prompt v3.1.0: STEP 4 now autonomously applies
  `[CRITICAL]` and `[SUGGESTION]` fixes from the Quick Fix Summary
  (deterministic selection rule — no `ask` tool, no HITL choice prompt),
  runs the project's aggregate validation gate, then commits the result
  with a Conventional Commit subject
  (`🐛 fix(review): apply N post-review fixes for {ISSUE_ID}`). Explicit
  `git add -- <files>` (never `git add -A`) keeps the advisory report at
  `.deviate/review/reports/` unstaged. `[OPPORTUNITY]` items remain
  deferred to a future slice. Pre-commit and pre-push hooks remain
  non-bypassable (`--no-verify` is never used); aggregate validation
- `/deviate-walkthrough` prompt v1.1.0: enforces true one-section-per-turn cadence. The prompt's STEP 4 previously said "then (optionally) ask a structured question" and the ADHD-friendly laws said sections "may include an `ask`" — both wordings gave the agent permission to skip interactive questioning and dump the entire walkthrough in a single response, defeating the HITL Gate 3 design intent. Replaced with mandatory per-section `ask`, an explicit "Two sections in one response is a bug" rule, a renumbered Law #5 ("One section per turn"), a "When to ask — always" rule that removes the old escape hatch, and an explicit override of universal invariant #1 (the "Automated Execution" no-questions rule) so the HITL gate's interactive posture wins. The `ask` is th…
- `deviate micro run --all` no longer segfaults in the JUDGE phase on diffs that
  contain a Rust (or any tree-sitter) file. Root cause: `_run_judge_phase`
  synchronously called `_build_structured_diff_section(diff)`, which invoked
  `extract_changed_symbols()` → `parser.parse(...)` on each file in the diff.
  Tree-sitter's C extension (`tree_sitter_rust._binding`) was observed to leave
  the interpreter in a fork-unsafe state after `parser.parse()` on sufficiently
  large or freshly-parsed Rust sources. The next `subprocess.Popen` (the
  `omp`/`pi`/etc. child fork) SIGSEGV'd in `_execute_child` → `fork_exec` —
  `except Exception` cannot trap a C-level fault, so the orchestrator died
  silently. The fix drops the entire structured-diff-symbol table from the
  JUDGE prompt and removes the `_build_structured_diff_section` /
  `_parse_diff_filepaths` helpers and the unused `extract_changed_symbols`
  import from `cli.micro`. The raw `<diff>` block (already injected one line
  below where the table used to go) provides the same content with strictly
  more detail than the symbol table, so JUDGE verdict quality is unchanged.
  Tree-sitter is still loaded for REFACTOR-time Python checks
  (`_check_return_type_mismatch`) and for `deviate review pre`; those code
  paths were not implicated in the reported crash and remain untouched per
  minimum-scope discipline. (`src/deviate/cli/micro.py`,
  `tests/test_micro/test_judge.py`.)
- CLI process enables `faulthandler` at startup so future SIGSEGV /
  SIGABRT / SIGBUS / SIGILL / SIGFPE dump a C-level traceback to stderr
  rather than dying as an opaque `[N] segmentation fault` shell line.
  Tree-sitter C extensions have been the culprit in two consecutive
  fixes; future regressions will surface their traceback automatically.
  (`src/deviate/main.py`.)

### Fixed
- `deviate micro run --all` no longer segfaults during the JUDGE phase when GREEN
  fails to deliver passing tests. Root cause: the background-thread reader in
  `_invoke_streaming` called `c.file.flush()` which bypassed Rich's RLock and
  raced with main-thread `c.print` writes on `sys.stdout.fileno()`. Removed the
  flush — both threads now only write through `c.print()`, which Rich
  serializes internally via its own RLock on the shared Console instance.
  (The `stdout_lock` in `_make_output_handler` already serialized the handler
  body against `emit_jsonl` and remains in place for that purpose.)
- Background-thread pipe I/O errors in `_invoke_streaming` no longer surface a
  CPython 3.13 `KeyError` traceback ("Exception ignored in thread ... read_stderr")
  during agent subprocess shutdown. Both `read_stdout` and `read_stderr` now
  catch pipe-closure exceptions (`ValueError`, `OSError`); `read_stdout` also
  sets `stdout_done = True` in a `finally` block so the caller doesn't raise a
  false `AgentTimeoutError` when the pipe closes concurrently with the timeout
  branch. The thread still terminates correctly; losing residual stderr is
  harmless because the manifest comes from stdout.
  (`src/deviate/core/agent.py`.)
- Worktrees created by `deviate meso run` now receive the `.pi/` and `.omp/`
  skill directories alongside `.claude/`, `.opencode/`, and `.factory/`.
  Root cause: `_sync_agent_dirs_to_worktree` in `src/deviate/cli/meso.py`
  iterated a hardcoded `_AGENT_DIRS` tuple that pre-dated the pi/omp
  agent platforms, while `deviate setup`, `detect_agents`, and the
  `.gitignore` patterns in `cli/__init__.py` already targeted all five
  — so users on those platforms had to re-run `deviate setup` inside
  every worktree. Added `.pi` and `.omp` to `_AGENT_DIRS` and updated
  the docstring; added a regression test pinning the sync list.
- JUDGE train rollback no longer leaves tasks stuck on the same RED commit.
  `_run_judge_phase` rejection branch now unconditionally commits a feedback
  marker and advances `session.red_commit_sha` past it (the regressed behavior
  only did so when `tasks.md` existed). The runner also honors
  `HandoverManifest.next_action` (new optional field on the manifest contract):
  `revert_to_red` (default on `COMPLIANCE_VIOLATION`) preserves RED and rolls
  back GREEN; `revert_before` rolls back to `red_commit_sha^` so RED re-runs
  from scratch; `continue_refactor` and `skip_refactor` route a passing GREEN
  straight to REFACTOR or mark the task COMPLETED, respectively. The runner
  has no interactive prompt — operators can override externally
  via a future `--judge-action` flag. `_finish_tdd_cycle` honors
  `session.pending_judge_action` to override `--no-refactor`. The EXECUTE
  phase's inner JUDGE branch mirrors the same routing with `pre_execute_sha`
  as the rollback anchor. Defensive `_resolve_pre_red_sha` matches
  `red_commit_sha^`'s commit subject against the RED-phase regex and logs
  `PRE_RED_AMBIGUOUS` when it doesn't match. Specs updated
  (`specs/DeviaTDD-api.md` SessionState + `next_action` Routing Table;
  `specs/DeviaTDD-architecture.md` §3 + §8 rule 5). Regression test
  `test_judge_feedback_preserved_across_rejection_rounds` now also asserts
  a feedback commit exists past RED; six new tests cover the four actions
  and the helper.
### Added
- PyPI-ready `pyproject.toml` metadata: `readme`, `license = "MIT"` (SPDX),
  `authors`, `keywords`, `classifiers` (incl. `License :: OSI Approved :: MIT
  License` and `Programming Language :: Python :: 3.13`), and a
  `[project.urls]` block (Homepage / Repository / Issues / Changelog).
  `twine check dist/*` now passes cleanly. The `[build-system]` was already
  hatchling-based and is unchanged.
- `mise run publish` task: depends on `check` (lint + format-check), rebuilds
  the sdist + wheel from a clean `dist/`, validates with `twine check`, then
  publishes via `uv publish` using `PYPI_API_TOKEN` loaded from a
  project-local `.env` (loaded by `mise` via `_.file = ".env"` in
  `mise.toml`). The task fails fast with a clear error if the token is
  unset. A new `.env.example` documents the variable; `.env` is gitignored
  via a pattern that ignores `.env` and `.env.*` while keeping
  `.env.example` trackable.
- `/deviate-walkthrough` slash command: human-guided architectural walkthrough
  that curates the diff by concern (DEEP_DIVE / NOTE / SKIM / SKIP triage),
  asks structured yes/no or multiple-choice questions via the `ask` tool with
  a recommended default, and surfaces architectural decisions missed by
  automated phases. Includes `deviate walkthrough pre/post` CLI backend.
  (PR #?.)
- Security: `mise run publish` passes the token via `UV_PUBLISH_TOKEN`
  inline-prefix env var (`UV_PUBLISH_TOKEN="$PYPI_API_TOKEN" uv publish
  dist/*`) instead of the `--token` CLI flag. The inline form scopes the
  export to the single `uv publish` invocation, so the secret never appears
  on the process command line — no exposure in `ps aux`,
  `/proc/<pid>/cmdline`, audit logs, or shell history. `uv publish` reads
  `UV_PUBLISH_TOKEN` natively.
- README: PyPI version badge in the badge row; one-line `deviate --version`
  verification step in Quickstart (right after `uv tool install deviatdd`);
  new `## Troubleshooting` section covering the five most common first-run
  failures (no `uv`, CLI binary confusion, slash commands not appearing,
  missing PyPI token, missing agent backend), each with a one-paragraph
  fix and a link back to the canonical docs (`CONTRIBUTING.md`,
  `specs/constitution.md`).

- README: Quickstart wording updated — "four agent directories" → "all
  supported agent directories" to track the six backends listed in the
  install comment.



- `format_commit_message()` and `_commit_phase()` accept an optional `phase`
  argument that overrides the `test:` emoji for the red-green TDD cycle:
  `phase="red"` → 🚨 (failing test), `phase="green"` → ✅ (passing test).
  Micro-layer RED phase commits are now prefixed with 🚨 so the failing
  test is visible at a glance; `feat:` commits continue to use ✨
  regardless of phase.
- `scripts/benchmark_lmstudio.py` (`mise run bench-lmstudio`): an internal
  benchmark harness that benchmarks every chat model exposed by LM Studio
  across the full DeviaTDD micro cycle (`RED → GREEN → JUDGE → REFACTOR`).
  Renders the real auto-templates from `src/deviate/prompts/auto/` via
  `deviate.prompts.assembly.assemble_prompt` so the measured payloads are
  byte-identical to what `deviate micro red|green|judge|refactor` would
  send. Uses `stream=True` on `/v1/chat/completions` to derive `prefill_ms`
  (time-to-first SSE chunk) and `decode_ms` (first chunk arrival → last
  chunk arrival) from the actual SSE timeline — never aliases total time
  into the decode column. Reports total wall time, `tok/s` including
  prefill, `tok/s` excluding prefill (NaN if the SSE decode span collapses
  to zero on a fast localhost — flagged in the table as `—`), and a
  side-by-side "cache helped?" ratio between cold (fresh prefix per call —
  what the micro layer actually pays in production) and warm (identical
  prefix across rounds — prompt-cache amortised) cache modes, per
  (model × phase × reasoning level × n_ctx × cache mode). Reasoning-level
  sweep (`off | low | medium | high | on`) is the default; levels
  unsupported by each model are read from
  `/api/v1/models` `capabilities.reasoning.allowed_options` rather than a
  runtime probe. Default `--context-lengths` sweep is `[16384, 65536]`
  (set by the `DEFAULT_CONTEXT_LENGTHS` constant) — clears the JUDGE
  auto-template cliff (~7.3K tokens) at the low end and exercises the
  upper bound of every chat model exposed by the host at the high end;
  pass `--context-lengths 16384 32768 65536` to widen to three windows.
  `--context-length N` is the single-value override (loses to
  `--context-lengths` when both are passed). Requested n_ctx is
  auto-capped against the model's reported `max_context_length` from
  `/api/v1/models` (the OpenAI-compat `/v1/models` payload omits it)
  and clamped with a `[warn] ... clamping to ...` line so a 16K-cap
  model never gets a 65K load request; the table row key preserves the
  raw request while the load call and rendered prompt use the clamped
  value. `--load-strategy single` (default) ensures only the model
  under test is loaded at a time — every other loaded LLM is unloaded
  first, and the model is unloaded after timing (the `_evict_self_from_memory`
  cleanup runs in a `finally:` block so Ctrl-C / SIGTERM never leaves a
  model in host memory). The orchestration reloads the model between
  context windows inside a sweep, keeping host memory at one model at
  one n_ctx at a time. Warm-mode prompt-cache stashes are keyed on
  `(phase, n_ctx)` so a 16K sweep round never shares prefix with a 64K
  round — KV cache is per-context-window. Each round also fires a
  non-streaming probe against LM Studio's Responses-shaped `/api/v1/chat`
  endpoint (distinct from the OpenAI Chat Completions stream used for
  the SSE split) to capture the server-truth `stats.tokens_per_second`
  and `stats.time_to_first_token_seconds`, populating
  `stats_decode_tok_per_s` and `stats_ttft_s` per round — a real decode
  rate even when the SSE split collapses to zero on bundled localhost
  writes. Per-round results stream to a JSONL artifact at
  `.deviate/artifacts/benchmark_lmstudio_<ts>.jsonl` (path overridable
  via `--out`), one line per completed round, appended and flushed
  incrementally so Ctrl-C / OOM / network drop never lose completed
  work. Effective `load_config` per model per context window is recorded
  per-round (`load_config` field on the JSONL row) for downstream
  audit. NaN/Inf in any float field are scrubbed to `null` before
  write so the file stays strictly valid JSON. Stdlib-only (no
  external deps), `--list` for preview. (`scripts/benchmark_lmstudio.py`,
  `mise.toml`.)

### Fixed
- `deviate --version` (and any code path importing `deviate.__version__`)
  raised `importlib.metadata.PackageNotFoundError: No package metadata was
  found for deviate` at import time. The two call sites in
  `src/deviate/__init__.py` and `src/deviate/cli/__init__.py` queried
  metadata for the import name `"deviate"` instead of the distribution
  name `"deviatdd"` declared in `pyproject.toml`. Both now query
  `"deviatdd"` and additionally fall back to a `"0.0.0+unknown"` sentinel
  (so source checkouts without a dist-info still import). The
  `test_version` test was tautological (asserted against the same broken
  `version("deviate")` call it was meant to guard); it now asserts
  `deviate --version` stdout equals the real
  `importlib.metadata.version("deviatdd")`, and a new
  `test_module_version_resolves` import-time guard fails loudly if the
  module-level lookup regresses.

:- CLI run output cleaned up: removed redundant "Processing TSK-..." line
  (the rich phase panel already shows task identity), added missing
  JUDGE phase panel/block to the execute-phase path, and fixed
  duplicate JUDGE → text in the TDD-cycle path.
### Changed
- `deviate --help` now renders three Typer help panels instead of a flat
  command list. **"Run by you (start here)"** is the human entry point —
  `setup` (with `Bootstrap a new project with DeviaTDD (start here).`),
  `run` (with `Use \`deviate run --all\` to drain the queue.`), and `meso`
  (with `Use \`deviate meso run\` to run the automated setup → plan →
  tasks pipeline`) — `run` and `meso` are surfaced in the panel by name
  with their literal invocation, since `run --all` and `meso run` are the
  actual entry points. **"Agent/internal (via /deviate-* slash
  commands)"** lists every phase dispatcher (`specify`, `plan`, `tasks`,
  `pr`, `merge`) and Typer group (`explore`, `research`, `prd`, `shard`,
  `macro`, `adhoc`, `red`, `green`, `judge`, `refactor`, `execute`, `e2e`,
  `hotfix`, `init`, `constitution`, `review`) the agent drives; first-
  timers see that those commands are not for them. **"Optional / manual
  utilities"** holds `feature` (create a branch) and `inspect` (list
  issue/task ledgers) — useful but not on the standard path. Each
  agent-internal command gained a one-line description (e.g. `Macro:
  codebase exploration`, `Micro: write a failing test`, `Final PR review
  (Gate 3)`) so the panel reads as a glossary, not a wall of names. The
  `run_command` docstring (`src/deviate/cli/micro.py`) was rewritten to
  lead with the `--all` invocation. Backed by
  `tests/test_cli/test_help.py`, which pins panel names, membership,
  ordering, and the literal meso/run invocations so the first-timer
  wording can't regress.
- **Shard prompts now own all vertical-slicing rules**; the PRD prompt's
  §Issue Sharding Strategy was removed to eliminate drift between the two.
  `src/deviate/prompts/commands/deviate-shard.md` (v1.1.0) now hard-enforces
  the 4–8 / max-10 cap via Pass 1.5 (Slice Cap Gate — halts with
  `SLICE_CAP_EXCEEDED`), flow-anchors issue boundaries via Pass 1 (Topological
  Layout + Flow Anchor), and merges horizontal slices via Pass 3.5 (Merge
  Pass). `src/deviate/prompts/commands/deviate-prd.md` (v1.1.0) gained a
  concise FR-authoring guidance blockquote urging flow-shaped FRs (one
  user-visible capability or flow segment per FR, not module-shaped FRs).
  Architecture spec §2.1 and API spec §1.4 now reflect the enforcement
  surface; PRD-level §Issue Sharding Strategy is gone.

- JUDGE/TRAIN feedback is now actionable for the next GREEN. The JUDGE
  prompts (`src/deviate/prompts/auto/judge.md`,
  `src/deviate/prompts/commands/deviate-judge.md`) now:
  - Carry an explicit **CRITICAL** note that `train_feedback` is the next
    GREEN's only memory of its prior attempt and that the `REFACTOR NOTE:`
    prefix must NEVER appear on a rejection (the prefix tells GREEN to
    defer, defeating training).
  - State **Format Requirements** for rejection `train_feedback`: state
    what GREEN did wrong, tell the next GREEN what to do ("The next GREEN
    attempt must:"), be instruction not observation, and never contain
    `REFACTOR NOTE:` content.
  - Replace the prior "train_feedback is optional but allowed" wording
    with explicit guidance that on rejection `train_feedback` MUST be
    specific actionable instructions (refactoring concerns belong in
    `summary` / `rationale`, not `train_feedback`).
  - Refresh the edge case row for refactoring opportunities to
    COMPLIANCE_PASS/PASS **only**, with the FAILURE/COMPLIANCE_VIOLATION
    branch pointing refactoring observations at `summary` / `rationale`.
  Pre-fix behavior: judges emitted `train_feedback` containing
  `REFACTOR NOTE:` content on `COMPLIANCE_VIOLATION`, which the orchestrator
  injected verbatim into the next GREEN's prompt — GREEN then deferred to
  the REFACTOR phase and the implementation stayed broken. The orchestrator
  code (`micro.py::_run_judge_phase`, `_append_judge_feedback`,
  `_run_green_phase`) is unchanged; only the prompts that drive JUDGE
  emission are fixed.
- Manual command prompt `deviate-judge.md` bumped to `1.2.0`; auto prompt
  `auto/judge.md` has no frontmatter and no version key.
- `/deviate-merge` prompt (`src/deviate/prompts/commands/deviate-merge.md`
  v2.0.0) now performs the full squash-merge pipeline end-to-end: validates
  branch state, resolves the feature branch, generates a conventional-commit
  message from the branch history, runs `git merge --squash`, pushes, and
  writes a full IssueRecord to the ledger via `deviate merge --delete-branch`.
  Previously it only updated the ledger after an external merge. The `deviate
  merge` CLI command is unchanged — the prompt now drives it as a final step
  rather than relying on an external squash-merge tool.
- Active domain discipline applied to `/deviate-research`, `/deviate-prd`, `/deviate-flows`, and `/deviate-architecture`. Each phase now actively term-challenges against the relevant glossary (`data-model.md`, `domain-model.md`, `flows-product.md`), sharpens fuzzy language, stress-tests with concrete scenarios, and updates the artifact inline as terms resolve. The macro-layer `interactive_hitl_gate_1` and the PRD `AMBIGUITY_INTERROGATION` gate now require a discipline pass before presenting HITL questions; the Product-layer discovery steps are upgraded from passive 3–4 bullet blocks to structured 7–8 bullet active disciplines. Spec alignment: `specs/DeviaTDD-architecture.md` §2.1 and §5.0, `specs/DeviaTDD-api.md` §1.5 and §2.
- **Reworked `deviate meso run` and `deviate run --all` output** to a clean,
  professional, rich-CLI format. New module `src/deviate/ui/pipeline.py`
  ships five components — `PipelineBanner` (framed opening panel with
  `MESO <issue_id>` and a `SPECIFY ▶ PLAN ▶ TASKS` step indicator),
  `PhaseCallout` (per-phase rounded panel with `◐`/`●`/`✗` markers and
  elapsed time), `RunBoard` (multi-column Rich `Table` updated in place
  by the `OrchestrationMonitor` event stream), `TrainIndicator`
  (sequential `● 1/3 ─▶─ ◐ 2/3 ─▶─ ○ 3/3` retry visual), and
  `PipelineSummary` (closing totals / duration / status panel). The
  `OrchestrationMonitor` gained an optional `board` parameter that
  updates the board on every `phase_change` / `task_completed` /
  `task_failed` event. All literal tokens the existing test suite
  asserts against (`RED`, `GREEN`, `COMPLETED`, `JUDGE_REJECTED`,
  `TRAIN`, `MESO`, `IDLE`, `DISCOVERED`, `INVOKE_AGENT`, `DRY_RUN`,
  `NO_CLAIMABLE_ISSUES`, `ISSUE_COMPLETED`, `INVALID_ISSUE_ID`,
  `BLOCKED`, `PROGRESS_RESET`, `TASK_ALREADY_DONE`, `TEST_FAILURE`,
  `JUDGE_AGENT_NO_FEEDBACK`, `<PHASE>_FAILED`, etc.) are preserved
  verbatim in the output — the framed panels are additive, not
  replacements. Aesthetic: "Editorial / Refined Engineering" — restrained
  palette (deep blue / semantic green-red-amber), heavy Unicode
  box-drawing (`╭╮╰╯│─`), monospace tabular layout. 46 new tests in
  `tests/test_ui/test_pipeline.py` pin the visual contract. Spec
  alignment: `specs/DeviaTDD-api.md` §5.2 (`deviate run --all`) and §5.3
  (`deviate meso run`) document the new output structure.
- **`deviate merge --delete-branch` now owns the full post-merge lifecycle** — archive tag, remote tag push, worktree cleanup, remote branch delete, and local branch delete in one call. Before deleting the feature branch, the CLI creates a local `archive/<ISSUE_ID>/<YYYY-MM-DD>` tag pointing at the pre-squash branch tip (UTC date) so the per-commit graph survives `git merge --squash` — the tag is the only path back to the per-commit history once `main` collapses the feature commits into one. Tag push (`git push origin <tag>`) and remote branch delete (`git push origin --delete <branch>`) are best-effort: missing `origin` is silently skipped (no `PUSH_WARN` — it's not an error condition), an unreachable remote surfaces `PUSH_WARN` and the lifecycle still completes locally so a transient network blip never strands work on disk; `REMOTE_BRANCH_DELETED` / `REMOTE_BRANCH_SKIP` reflect origin's acknowledgement (`skip` when origin reports the branch is already gone — the expected post-merge state). The `merge_repo` fixture (`tests/test_cli/test_merge.py`) gained four regression tests pinning each contract: tag-points-at-pre-squash-tip, end-to-end push to a bare origin (tag + remote branch both gone), `PUSH_WARN` + complete local cleanup when origin is unreachable, and silent-skip when origin is unconfigured. Skill (`src/deviate/prompts/commands/deviate-merge.md`) v2.1.0 → v2.2.0 documents the new five-step cleanup order. Specs (`specs/DeviaTDD-api.md` §3 `--delete-branch`, `specs/DeviaTDD-architecture.md` §2.2 Merge) reflect the new lifecycle.

### Fixed
- `resolve_issue_record` and `_deduplicate_issues` now treat `COMPLETED`
  as a terminal status that always takes precedence. Previously, both
  surfaced the last entry by file position, so a `SPECIFIED` transition
  appended after the `COMPLETED` write during a merge flow caused the
  issue to appear non-`COMPLETED`. The bug was user-visible in two ways:
  `inspect issues list` showed the wrong status, and `_is_issue_completed`
  (called from `deviate specify` and `select_unblocked_candidates`)
  re-claimed. Among non-`COMPLETED` entries the prior "last valid wins"
  behaviour is preserved.
- `omp` (Oh-My-Pi) is now a first-class dispatch backend, not an alias
  for `pi`. `BackendName` (`src/deviate/core/agent.py:18`) and
  `AgentConfig.backend` (`src/deviate/state/config.py:14`) Literals
  both widened to include `"omp"`; `BACKEND_COMMANDS["omp"] = "omp -p"`
  spawns the Oh-My-Pi CLI binary directly (not `pi -p`); `MODEL_FLAGS`
  recognises `omp` for `--model <id>` dispatch. `AGENT_TO_BACKEND["omp"]`
  is identity (`omp → omp`). User-facing aliases (`factory` for the
  Factory Droid IDE) are still normalised to their canonical backend
  (`droid`) via `deviate.core.agent.resolve_agent_to_backend` at every
  load boundary (`micro.py::_resolve_agent_config`,
  `meso.py::_invoke_agent_phase`) before reaching `AgentConfig` — the
  same fix that previously made `backend = "omp"` valid in the Literal.
  The re-exports `from deviate.cli import AGENT_TO_BACKEND` and
  `_resolve_agent_to_backend` remain as alias shims over the canonical
  home in `deviate.core.agent`.

### Added
- **`specs/_product/flows.jsonl` append-only flow ledger + Flow Coverage Report.** `deviate explore post` now seeds and replays an event-sourced `flows.jsonl` (`FlowRecord` identity rows + `FlowEvent` append-only event rows: `FLOW_DISCOVERED`, `FLOW_DOCUMENTED`, `FLOW_IMPLEMENTATION_EVIDENCE_ADDED`, `FLOW_CONFIRMED_IMPLEMENTED`, `FLOW_REFERENCED_BY_ISSUE`, `FLOW_INCLUDED_IN_RELEASE`, `FLOW_DEPRECATED`) and renders a Rich-formatted Flow Coverage Report to stdout (`flow_id | actor/job/trigger | documented? | implementation evidence? | last referenced by issue/release? | drift flag`). Rows where `drift_flag ∈ {DOCUMENTED_BUT_NOT_IMPLEMENTED, IMPLEMENTED_BUT_UNDOCUMENTED, ORPHANED_FLOW, STALE_DRIFT}` are highlighted in yellow. The reverse index from `specs/issues.jsonl.flow_refs` makes the `specs/_product/release-next.md:58` acceptance criterion enforceable at scan time. Three new Pydantic models (`FlowRecord`, `FlowEvent`, `FlowCoverage`) in `src/deviate/state/ledger.py` enforce `^FLOW-\d{2,}$` regex validation against the canonical `_FLOW_REF_PATTERN` at `src/deviate/cli/adhoc.py:19`. Constitution bumped to v0.7.0; `.gitattributes` gains `specs/_product/flows.jsonl merge=union` parallel to the existing `specs/issues.jsonl` rule. Closes the substrate gap surfaced at `specs/explore/flow-ledger.md:35-38` ("framework has the frontmatter hook (`flow_refs`) but no inventory substrate"). `src/deviate/state/ledger.py`, `src/deviate/cli/explore.py`, `src/deviate/cli/__init__.py`, `specs/constitution.md`, `CHANGELOG.md`, `.gitattributes`.

## [2.4.0] - 2026-07-04
### Changed
- `/deviate-architecture` discovery step now follows "grill with docs"
  discipline: one question at a time with a recommended answer,
  dependency-ordered (components before contracts before ownership),
  and at most one term-challenge per turn when the user's language
  conflicts with existing `domain-model.md` or `architecture.md`
  definitions.
- `/deviate-flows` discovery step now follows the same one-question-at-a-time
  discipline with recommended answers, dependency-ordered (Actor before
  Domain before Trigger before Happy Path).
- `/deviate-architecture` now produces Architectural Decision Records (ADRs)
  as a `## Architectural Decision Records` section within `architecture.md`.
  ADRs are one-paragraph entries gated on three criteria: hard to reverse,
  surprising without context, and the result of a real tradeoff. No ADR is
  written when any criterion is missing.

## [2.3.0] - 2026-07-04
### Added
- `deviate merge` command (`/deviate-merge` slash command) for marking issues
  COMPLETED in the ledger after an external merge (e.g. the `/squash-merge`
  skill). Writes a full IssueRecord with all required fields, unlike bare
  `{issue_id, status, timestamp}` transitions that are silently dropped by
  `resolve_issue_record`. Supports `--delete-branch` and `--delete-worktree`
  flags for post-merge cleanup.

### Fixed
- `resolve_issue_record` now tolerates sparse/bare ledger transitions (e.g.
  `{"issue_id":"ISS-001","status":"COMPLETED","timestamp":"..."}`) by merging
  them with the last fully-resolved record instead of silently dropping them.
  Previously, bare COMPLETED entries written by external tools like
  `/squash-merge` caused `_is_issue_completed` to return `False`, blocking
  downstream issues that depend on the completed one.

### Changed
- `deviate setup` now ensures a symlink relationship between `CLAUDE.md` and
  `AGENTS.md` via `_linkify_governance_files`. If neither file exists, an empty
  `CLAUDE.md` is created and `AGENTS.md` is symlinked to it. If exactly one
  exists, the other is symlinked to it. If both exist as regular files, they are
  left unchanged. Governance seed writes (libref, graphite) now target only the
  canonical file to avoid double-writing through symlinks. The `deviate init pre`
  command uses the same shared helper.
- Commit messages from `deviate` phase commands (`explore post`, `research post`,
  `prd post`, `shard post`, `plan post`, `tasks post`, `constitution post`) now
  respect the project's emoji convention. A new `convention.py` module detects
  emoji usage from CONTRIBUTING.md (or `.commit-convention.md`) and falls back
  to sampling recent git history. When detected, the appropriate emoji is
  prepended to the conventional-commit message (e.g. `📚 docs(epic): create prd.md`).
- `deviate specify` claim commit now respects the project's emoji convention
  via `format_commit_message()`, matching the behavior of all other phase
  commits (e.g. `🔧 chore(001-001): claim ISS-001` when emoji prefixes are
  detected).
- Micro-layer commit messages (`deviate red post`, `deviate green post`,
  `deviate refactor post`, `deviate execute post`, `deviate e2e post`,
  `deviate hotfix post`, and judge feedback commits) now respect the project's
  emoji convention via `format_commit_message()` in `_commit_phase()`, matching
  the behavior already present in macro and meso layer commits.
- `/deviate-prd` now explicitly forbids intermediate `git add`/`git commit` between
  `prd_generation` and `post_script`; the post-script is the sole commit authority.
  The `IMPORTANT` note in the `post_script` step also corrected: pre-commit hooks run
  ruff only, not the test suite — timeout guidance updated from 180s to 60s.

## [2.2.0] - 2026-07-02

### Removed
- Tome subsystem from `main`: the seven `/tome-*` slash commands (`tome-classify`, `tome-setup`, `tome-verify-docs`, `tome-write-tutorial`, `tome-write-how-to`, `tome-write-reference`, `tome-write-explanation`) and their agent-mirror copies under `.claude/commands/`, `.factory/commands/`, `.pi/prompts/`; the pure-Tome specs (`specs/_product/architecture.md`, `domain-model.md`, `release-next.md`, `flows/flows-tome.md`), exploration notes (`specs/explore/tome-subsystem.md`), the `011-tome-subsystem-v1` issue file and plan dir; the FLOW-04..FLOW-10 entries in `_product/flows/index.md`; the `_ensure_root_gitignore` Tome patterns; the Feature issue template Tome checkbox; the `_TOME_LAYER_SKILLS` test trio in `tests/test_cli/test_init.py`; the Tome fixture path in `tests/test_micro/test_judge.py`; and the Tome illustrative examples in `deviate-review` (canonical + 3 agent mirrors). Tome work continues on the `tome` branch.
- YELLOW phase and Tamper Guard: removed the conditional YELLOW test-amendment phase, `TamperGuard`/`TamperContext`/`TamperVerdict` classes, `yellow_pre`/`yellow_post` commands, `deviate-yellow` skill, auto yellow prompt, `yellow_trigger` field from `HandoverManifest`, `yellow_triggered` from `SessionState`, and YELLOW/YELLOW_APPROVED/YELLOW_REJECTED from `TaskRecord.status`. JUDGE now handles scope verification — GREEN may only write to `src/` and permitted paths; modifications to `tests/`, `specs/`, or config files are flagged as scope violations.

### Added
- `deviate setup` now installs slash commands to `.omp/commands/` (Oh-My-Pi),
  in addition to the existing `.claude/commands/`, `.opencode/commands/`,
  `.factory/commands/`, and `.pi/prompts/` targets. `omp` is now a valid
  `--agent` choice and maps to the `pi` backend.
- GitHub Actions CI workflow (`.github/workflows/ci.yml`) running ruff lint,
  ruff format check, and pytest on push to `main` and on pull requests.
- Bats end-to-end smoke suite at `tests/e2e/` covering the installed `deviate`
  CLI binary: `--version`, `--help`, macro / meso / micro subcommand
  discoverability, and unknown-command rejection.
- Issue templates (`.github/ISSUE_TEMPLATE/bug.md`,
  `.github/ISSUE_TEMPLATE/feature.md`) and a pull request template
  (`.github/PULL_REQUEST_TEMPLATE.md`) to standardize contributions.
- This `CHANGELOG.md`.
- Community health files: `CONTRIBUTING.md` (derived from
  `specs/constitution.md` and `AGENTS.md`, covering setup, branch
  strategy, commit conventions, PR workflow, test discipline, spec
  alignment, and slash-command edit policy), `CODE_OF_CONDUCT.md`
  (Contributor Covenant v2.1), and `SECURITY.md` (private disclosure
  via GitHub Security Advisories, supported-versions policy, 90-day
  coordinated-disclosure window, and explicit in-scope / out-of-scope
  threat model).
- `/tome-classify --codebase` mode for whole-codebase ingest (cold-start / retroactive docs). Walks manifests, source tree, CLI definitions, config schemas, and public API surface; emits an exhaustive capability table; pre-marks existing valid docs as `update`. Documented in `specs/_product/architecture.md` §3.1 and `specs/_product/domain-model.md` `ClassificationReport.mode`; verifier (C6) handles the new evidence source by reading source files directly.
- `mise run test-affected` task: runs only tests touched by current changes
  via `pytest --testmon-forceselect`. Companion to the existing
  `mise run test` full-suite task; the populated `.testmondata` file
  makes the selection fast on every subsequent run.

### Changed
- Removed all references to flows (FLOW-04..FLOW-10, `specs/_product/flows/flows-tome.md`) from the seven Tome subsystem prompt bodies under `src/deviate/prompts/commands/tome-*.md`. Flows remain as documentation artifacts under `specs/_product/`; the prompts now reference `/tome-classify`, `/tome-write-tutorial`, `/tome-write-how-to`, `/tome-write-reference`, `/tome-write-explanation`, `/tome-verify-docs`, and `/tome-setup` directly, and read source-of-truth inputs only from `specs/_product/architecture.md` and `specs/_product/domain-model.md`.
- Stripped the framework-internal `FLOW-01/02/03` phase identifiers from the three Product-layer slash-command descriptions (`/deviate-flows`, `/deviate-architecture`, `/deviate-release`) and rewrote them as end-user action phrases ("Author customer flows…", "Author the cross-epic architecture contract…", "Plan the next coherent release…"). Generic terminology that any project would call on — the `flow_refs:` issue-frontmatter field, the `--flow-ref` CLI flag, the `**Flow References**` task anchor, the `Flow Coverage` review domain — is preserved verbatim. Internal anchors in `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, and prompt bodies remain unchanged.
- README reframed around the four-layer architecture (Product · Macro ·

  Meso · Micro). The Product layer (FLOW-01 flows → FLOW-02 architecture →
  FLOW-03 release) was previously absent from the README; it is now
  presented as an optional layer above Macro and reachable through
  `/deviate-flows`, `/deviate-architecture`, and `/deviate-release`.
  The Macro section now surfaces the dual path (full `explore → research
  → prd → shard` *or* `adhoc` shortcut); the Micro section surfaces the
  TDD cycle *or* `/deviate-execute` alternative, including the
  Green → Judge → Green TRAIN loop on `JUDGE_REJECTED`. The "Workflow at
  a Glance" table enumerates every phase with its slash command, the
  artifact committed, and what the human reviews at each gate —
  including the `tasks.md` execution blueprint produced by
  `/deviate-tasks`. Prompt-count claim corrected from 29 to 31
  (24 `deviate-*` + 7 `tome-*`).
- `specs/DeviaTDD-architecture.md` and `specs/DeviaTDD-api.md` aligned with
  the four-layer framing and the corrected Green → Judge → Green TRAIN
  semantics. Architecture spec: Section 1 ASCII diagram now includes the
  Product layer above Macro; Section 2.3 JUDGE/TRAIN phase block describes
  the `git reset --hard <red_sha>` rollback + `force_transition_to("GREEN")`
  retry flow (replacing the prior incorrect `git revert` description);
  Section 3.5 EDD rewritten to call out the Green → Judge → Green loop by
  name; Section 4 micro cycle diagram carries the explicit JUDGE → GREEN
  TRAIN arrow distinct from the YELLOW → GREEN (rejected) branch; new
  Section 5.0 Product Layer Phase Prompts documents FLOW-01..FLOW-03 with
  precondition gates (`[red]FLOWS_MISSING[/]`,
  `[red]ARCH_OR_FLOWS_MISSING[/]`); Section 6 gates diagram shows the
  Product-layer conversational checkpoints as soft gates; Section 8.5
  invariant tightened to the loop name. API spec: command count corrected
  from 32 to 31 in three places (Bootstrap description, output artifacts
  list, file tree blueprint — `deviate-content` removed since it is not
  in the canonical commands directory); new Section 1.5 Product Layer
  documents the three agent-skill commands and their downstream
  `flow_refs:` consumption; `IssueRecord.flow_refs` field documented in
  Section 3 with the `^FLOW-\d{2,}$` validation rule; `deviate run`
  description now uses the Green → Judge → Green loop name and spells
  out the feedback source precedence; `deviate execute pre/post`
  documented with the EXECUTE → JUDGE → EXECUTE retry pattern.
- Bats suite relocated from `tests/test_e2e/` to the canonical `tests/e2e/`
  path referenced by `mise run test-e2e` and `specs/constitution.md`. The
  stale macro-workflow tests have been replaced with a focused CLI smoke
  suite that matches the current `pre|post` subcommand shape.
- `AGENTS.md` now mandates a `## 📝 CHANGELOG Discipline` rule (mirrored
  in `specs/constitution.md` §5 Definition of Done and the PR template's
  CHANGELOG checkbox): user-visible changes must append a bullet to
  `[Unreleased]` in the same commit. Exempts docs-only, test-only,
  CI/tooling, and behavior-preserving refactors. Constitution bumped to
  0.5.0.
- README onboarding flow corrected: the user-facing entrypoint is the
  `/deviate-<phase>` slash commands installed by `deviate setup`, not
  direct `deviate <phase>` CLI invocations. Quickstart rewritten to
  show `deviate setup --agent <name>` → `/deviate-*`; the `Commands`
  section replaced with a `Slash Commands` section grouped by layer.
  Removed stale references to `deviate specify` (deprecated; the SPECIFY
  phase was absorbed into `deviate shard` per
  `src/deviate/cli/meso.py::_specify_legacy` and `specs/DeviaTDD-api.md`)
  and dropped the `M[specify]` node from the architecture mermaid.
  Quickstart also no longer shows `deviate init` — `deviate init` is the
  engine backing the `/deviate-init` slash command, not a user-facing
  shell command; `deviate setup --agent <name>` is the single one-shot
  bootstrap that scaffolds `.deviate/`, `specs/constitution.md`,
  governance blocks, and installs `/deviate-*` slash commands.
- README `Why Each Phase Exists` rationale now annotates each architectural
  claim with inline article citations (Agile-V/SCOPE-V, IACDM, PRIME,
  State Contamination, SDD, Spec Kit, Mise en Place, Runtime Decomp, TDAD,
  TDFlow, TDDev, TDD Governance, TDAID, Red-Green-Refactor Agents, TDD
  Agent Dev, Definitive SDD 2026, Acceptance Test Gen, LLM BDD, Vibe vs
  Agentic, UCCI, RoBatch, Agentic AI Survey) and adds a `## References`
  section consolidating 21 source URLs. DeviaTDD-original claims (Yellow
  test-amendment gate, Product layer optionality, Flows / Architecture /
  Release triad, 4–8 task count, three-gate count, append-only ledger
  rationale, `flow_refs:` frontmatter convention, ledger-derived IDs,
  per-issue Plan cadence, Adhoc complexity classifier, deriving CLI state
  from the ledger) are tagged `_(design proposal)_` and grouped under
  `References § Gaps` for transparency.
- Pre-commit hook (`.githooks/pre-commit`) now lints and format-checks
  only the staged + unstaged `.py` files (was: whole repo via
  `mise run check`). Early-exits cleanly on docs-only, prompt-only, or
  non-Python commits. Adds `set -o pipefail` and the `GIT_DIR` env-var
  guard.
- Pre-push hook (`.githooks/pre-push`) now lints, format-checks, and
  runs `mise run test-affected` against the `.py` files changed since
  the upstream branch (was: full test suite via `mise run test`).
  Adds the `GIT_DIR` env-var guard that the previous script was
  missing, plus `set -o pipefail`.
- `mise run test` and the CI pytest step now pass `--testmon-noselect`
  to pin full-suite behavior. Without the flag, `pytest-testmon`'s
  default selection would silently narrow both commands once
  `.testmondata` exists. New dev dep `pytest-testmon>=2.2` added to
  both `[project.optional-dependencies].dev` and
  `[dependency-groups].dev`; `.testmondata` added to `.gitignore`.
- Phase prompts now prefer the codebase-index MCP tools (`codebase_search`,
  `codebase_peek`, `implementation_lookup`, `call_graph`) over `grep` /
  `glob` for semantic code discovery, symbol location, and call-graph
  traversal. A new universal invariant #9 in
  `src/deviate/prompts/core/core.md` propagates the mandate to every
  `auto/*` phase via `load_template`; the discovery-bearing command
  variants (`deviate-adhoc`, `deviate-explore`, `deviate-hotfix`,
  `deviate-plan`) and the meso `Deterministic Discovery` discipline now
  lead with codebase-index tools, with `grep` / `glob` / `Read` demoted
  to a documented last-mile fallback when the MCP is unavailable. 10 prompt files affected.
- `/deviate-research` now dispatches two sequential subagent stages instead of three parallel ones. The former Alpha (architecture options) and Beta (data modeling) subagents are merged into a single **AlphaBeta** subagent that produces the architecture and data-model fragments in one coherent pass, with data modeling explicitly deriving from the recommended architecture (not from `explore.md` in isolation). The adversarial **Gamma** subagent now runs strictly AFTER AlphaBeta returns and consumes its full fragment output, fixing a latent bug where Gamma was instructed to read Alpha/Beta outputs that ran in parallel with it. Updated files: `src/deviate/prompts/commands/deviate-research.md` (subagent blueprint directory, `map_phase_sequential_fork` step, `reduce_phase` merge language, intro) and `src/deviate/prompts/auto/research.md` (`sequential_fork` step, intro). Command prompt version bumped 2.0.0 → 2.1.0.

## [2.0.0] - 2026-06-28

### Added
- Three-layer agent orchestration framework: Macro (Explore → Research →
  PRD → Shard), Meso (Plan → Tasks), Micro (RED → GREEN → JUDGE →
  REFACTOR). Strict phase gates; no layer may be skipped.
- 30 slash commands spanning macro, meso, micro, and Tome subsystems
  (`src/deviate/prompts/commands/`).
- Tome subsystem v1: seven prompt-only Diátaxis-aware documentation
  curation skills (FLOW-04 .. FLOW-10).
- Multi-agent backend support: opencode, claude, droid, pi.
- Append-only JSONL ledger protocol with `merge=union` in
  `.gitattributes` for safe concurrent feature branches.
- HITL gates at three checkpoints (Gate 1: design approval; Gate 2:
  contract sign-off; Gate 3: final merge audit). No programmatic bypass.
- Per-phase model routing via `.deviate/config.toml [models]` with
  `default` key + phase-specific overrides.
- Constitution and governance bootstrap via `deviate init` / `deviate setup`.
- Pre-commit (`mise run check`) and pre-push (`mise run test`) git hooks.
- `LICENSE` (MIT), `README.md` with architecture diagram and quickstart.

### Notes
- v2.0 ships a v0.x-quality codebase with a governance-first approach;
  expect rapid iteration under the new CHANGELOG + CI discipline.
- Repo transitioned from internal solo development to public launch
  readiness in June 2026.
