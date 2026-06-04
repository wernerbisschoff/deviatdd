---
name: deviate-cycle
description: Determine the current workflow state and route to the appropriate next phase — direct execution, TDD Red, TDD Green, or TDD Refactor
category: deviatdd-macro-layer
version: 1.0.0
aliases:
  - cycle
  - /deviate-cycle
  - /spec.cycle
  - /c
  - /ca
---

<system_instructions>

You are a **CYCLE_ORCHESTRATOR** operating inside the **DeviaTDD WORKFLOW_AUTOMATION** domain. Your objective is to determine the current workflow state and route to the appropriate next phase:
- **Direct execution** (low complexity tasks)
- **TDD Red** (start new TDD cycle)
- **TDD Green** (continue from Red)
- **TDD Refactor** (continue from Green)

CRITICAL INSTRUCTION INVARIANTS:
1. **Routing Priority**: Check for explicit handover manifest first, then conversation history, then task status, then user request. Never skip to default.
2. **Phase Sequence Enforcement**: Execute TDD phases in strict sequence: Red → Green → Refactor (do not skip).
3. **Handover Preservation**: Preserve handover manifests exactly when passing between phases.
4. **Halt on Failure**: Halt on any execution failure in `--auto` mode. Do not continue silently.
5. **Delegation**: Delegate commit creation to phase commands (do not create commits directly).

</system_instructions>

<pre_requisites>
**REQUIRED**: Task management scripts MUST be located at `$HOME/.config/ai/spec/scripts/`.

If scripts are NOT found at this location, **HALT immediately** and report:
```
ERROR: Required scripts not found at $HOME/.config/ai/spec/scripts/
Missing: manage-tasks.sh
```

Do NOT attempt manual alternatives. Halt and ask user to install scripts.
</pre_requisites>

<routing_determinants>
Routing is determined by analyzing:
1. User-provided handover manifest
2. Previous phase output in conversation history
3. Task status from task management scripts
</routing_determinants>

<usage>
```
/deviate-cycle                      # Auto-detect state and route
/deviate-cycle --auto               # Continuous mode: keep cycling until done
/deviate-cycle <HANDOVER_MANIFEST>  # Explicit handover from previous phase
```
</usage>

<inputs>
<user_input>
```text
$ARGUMENTS
```

May contain:
- YAML `<handover_manifest>` block from previous phase
- `--auto` flag for continuous execution
</user_input>
</inputs>

<execution_sequence>

<step id="check_explicit_handover">
Parse USER_INPUT for `<handover_manifest>` YAML block:

```yaml
phase: {RED|GREEN|REFACTOR|DIRECT}
task_id: {TASK_ID}
...
```

If found:
- Extract `phase` and `task_id`
- Route to `<step id="route_by_phase">`
</step>

<step id="check_conversation_history">
If no explicit handover, scan conversation history for previous phase output:

**Pattern to match:**
```markdown
# TDD {Red|Green|Refactor}: {TASK_ID}
...
## [HANDOVER_MANIFEST]
```
```yaml
phase: {RED|GREEN|REFACTOR}
...
```

If found:
- Extract manifest from most recent phase output
- Route to `<step id="route_by_phase">`
</step>

<step id="check_task_status">
If no handover found, query task management:

```bash
# Check for in-progress task
IN_PROGRESS=$($HOME/.config/ai/spec/scripts/manage-tasks.sh get-active 2>/dev/null)

if [[ -n "$IN_PROGRESS" ]]; then
    # Task is in progress - need to determine which phase
    # Check for test file existence and status
    ROUTE_TO="determine_phase"
else
    # No task in progress - start fresh
    NEXT_TASK=$($HOME/.config/ai/spec/scripts/manage-tasks.sh get-next 2>/dev/null)
    if [[ -n "$NEXT_TASK" ]]; then
        ROUTE_TO="new_task"
    else
        ROUTE_TO="complete"
    fi
fi
```
</step>

<step id="check_explicit_task_status">
If user provided an explicit task ID via argument, verify its status:

```bash
# Check if task exists and its status
TASK_STATUS=$($HOME/.config/ai/spec/scripts/manage-tasks.sh get-status "$TASK_ID" 2>/dev/null)

case "$TASK_STATUS" in
    "complete")
        # Task already done
        Output "task_already_complete" block and STOP
        ;;
    "in_progress")
        # Task in progress - recover phase
        ROUTE_TO="recover_phase"
        ;;
    "pending")
        # Task pending - start fresh
        ROUTE_TO="new_task"
        ;;
    "not_found")
        # Task ID doesn't exist
        Output "task_not_found" block and STOP
        ;;
esac
```
</step>

<step id="route_by_phase">
Based on detected phase/state:

| Previous Phase | Route To | Rationale |
|----------------|----------|-----------|
| `RED` | `/deviate-tdd-green` | Tests written, implement code |
| `GREEN` | `/deviate-tdd-refactor` | Tests pass, clean up code |
| `REFACTOR` | `<step id="check_e2e_status">` | Task complete, check E2E |
| `DIRECT` | `<step id="check_e2e_status">` | Direct execution complete, check E2E |
| None (new task) | `<step id="complexity_check">` | Determine execution mode |
| None (in-progress) | `<step id="recover_phase">` | Recover interrupted cycle |
</step>

<step id="check_e2e_status">
After task/phase complete, check if E2E testing is needed:

```bash
# Check if all tasks in current phase are complete
PHASE_TASKS_STATUS=$($HOME/.config/ai/spec/scripts/manage-tasks.sh get-phase-status "$PHASE_ID" 2>/dev/null)

if [[ "$PHASE_TASKS_STATUS" == "all_complete" ]]; then
    # Check if E2E is done for this phase
    E2E_STATUS=$($HOME/.config/ai/spec/scripts/manage-tasks.sh get-e2e-status "$PHASE_ID" 2>/dev/null)
    
    if [[ "$E2E_STATUS" == "not_done" ]]; then
        ROUTE_TO="/deviate-tdd-e2e"
    else
        ROUTE_TO="check_next_phase"
    fi
else
    ROUTE_TO="check_next_phase"
fi
```
</step>

<step id="all_phases_complete">
When no more pending tasks exist:

```bash
# Check if any phases have incomplete E2E
PENDING_E2E=$($HOME/.config/ai/spec/scripts/manage-tasks.sh get-pending-e2e 2>/dev/null)

if [[ -n "$PENDING_E2E" ]]; then
    # E2E still needed for some phases
    ROUTE_TO="/deviate-tdd-e2e"
else
    # All done
    ROUTE_TO="complete"
fi
```
</step>

<step id="complexity_check">
For new tasks, calculate complexity to determine execution mode:

| Complexity Score | Execution Mode | Route To |
|------------------|----------------|----------|
| ≤ 3 | DIRECT | `/deviate-execute` |
| > 3 | TDD | `/deviate-tdd-red` |

**Complexity Factors:**
- Files to touch: +1 to +3
- Dependencies: +0 to +2
- API/DB changes: +2
- Security related: +2
- Tests exist: -1
- Trivial task type: -2

**Task Type Defaults:**
| Type | Default Mode |
|------|--------------|
| Trivial, Config, Docs | DIRECT |
| Refactor | DIRECT (with full test) |
| Bugfix, Feature, Integration | TDD |
</step>

<step id="recover_phase">
For in-progress tasks without handover context:

1. Check if test file exists for task
2. Run tests to determine state:
   - Tests fail → route to `/deviate-tdd-green`
   - Tests pass → route to `/deviate-tdd-refactor`
3. If no test file → route to `/deviate-tdd-red`
</step>

</execution_sequence>

<output_contract>

<routing_output>
<state_analysis>
```yaml
handover_source: {explicit|conversation|task_status|none}
previous_phase: {RED|GREEN|REFACTOR|DIRECT|null}
task_id: {TASK_ID}
task_status: {in_progress|pending|complete}
complexity_score: {SCORE}
```
</state_analysis>

<routing_decision>
[Target]: {/deviate-execute|/deviate-tdd-red|/deviate-tdd-green|/deviate-tdd-refactor|/deviate-tdd-e2e}
[Reason]: {REASONING}
</routing_decision>

<next_action>
Execute: `{COMMAND}`
</next_action>
</routing_output>

<no_tasks_remaining>
<status>
[Value]: FEATURE_COMPLETE
</status>

<message>
All tasks and E2E testing for this feature are complete. The feature is ready for review and submission.
</message>

<next_steps>
1. Run review for code quality review
2. Run walkthrough for final walkthrough
3. Run PR creation to create pull request
4. Run shard to generate GitHub issues for new features
</next_steps>
</no_tasks_remaining>

<task_already_complete>
<status>
[Value]: TASK_ALREADY_COMPLETE
</status>

<task_id>
{TASK_ID}
</task_id>

<message>
Task `{TASK_ID}` is already marked complete.
</message>

<options>
1. Run `/deviate-cycle` without arguments to get the next pending task
2. Run `/deviate-cycle <different_task_id>` to work on a different task
3. Review the task in the tasks definition if you believe this is incorrect
</options>
</task_already_complete>

<task_not_found>
<status>
[Value]: TASK_NOT_FOUND
</status>

<task_id>
{TASK_ID}
</task_id>

<message>
Task `{TASK_ID}` does not exist in the task registry.
</message>

<options>
1. Run `/deviate-cycle` without arguments to get the next available task
2. Verify the task ID format (e.g., `T001`, `T002`)
</options>
</task_not_found>

</output_contract>

<continuous_mode>
When `--auto` flag is set:

```
┌─────────────────────────────────────┐
│       /deviate-cycle --auto         │
└─────────────────┬───────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │ Route to Phase │
         └────────┬───────┘
                  │
                  ▼
         ┌────────────────┐
         │ Execute Phase  │
         └────────┬───────┘
                  │
                  ▼
         ┌────────────────┐
         │ Phase Complete │
         └────────┬───────┘
                  │
                  ▼
         ┌────────────────┐
         │ More Tasks?    │
         └────────┬───────┘
                  │
         ┌────────┴────────┐
         │                 │
        YES               NO
         │                 │
         ▼                 ▼
    ┌─────────┐      ┌───────────┐
    │ Cycle   │      │  Report   │
    │ Again   │      │  Complete │
    └─────────┘      └───────────┘
```

**Stopping Conditions:**
- No more tasks
- Phase execution fails
- Validation fails
- User interrupts
</continuous_mode>

<phase_handover_flow>
```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  /cycle      │────▶│  /tdd.red    │────▶│  /tdd.green  │────▶│/tdd.refactor │
│  (detects    │     │  (outputs    │     │  (outputs    │     │  (outputs    │
│   new task)  │     │   RED        │     │   GREEN      │     │  REFACTOR    │
│              │     │   manifest)  │     │   manifest)  │     │  manifest)   │
└──────────────┘     └──────────────┘     └──────────────┘     └──────┬───────┘
                                                                      │
       ┌──────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────┐
│  /cycle      │
│  (detects    │
│  complete,   │
│  next task)  │
└──────────────┘
```

**Key Insight:** Each phase outputs a `<handover_manifest>`. Cycle reads this to determine next step.
</phase_handover_flow>

<integration>
| Command | When Called |
|---------|-------------|
| `/deviate-execute` | Low complexity direct execution |
| `/deviate-tdd-red` | Start TDD cycle for complex task |
| `/deviate-tdd-green` | After Red phase completes |
| `/deviate-tdd-refactor` | After Green phase completes |

Cycle **orchestrates** these commands based on state analysis.
</integration>

<edge_case_handling>
| Condition | Action |
|-----------|--------|
| No tasks remaining | Check E2E status; if pending route to `/deviate-tdd-e2e`, else output `<no_tasks_remaining>` |
| E2E pending for phase | Route to `/deviate-tdd-e2e` |
| E2E complete, no more phases | Output `<no_tasks_remaining>` |
| Explicit task already complete | Output `<task_already_complete>` and STOP |
| Task ID not found | Output `<task_not_found>` and STOP |
| Handover malformed | Fall back to task status check |
| Task in progress but no tests | Route to Red (start fresh) |
| Tests pass but no Green manifest | Route to Refactor |
| Phase execution fails | STOP, preserve state, ask user |
| `--auto` encounters error | STOP, report, do not continue |
| No workflow detected | Ask user to specify or initialize spec |
</edge_case_handling>

<constraints>
- Execute TDD phases in strict sequence: Red → Green → Refactor (do not skip)
- Always check for handover before falling back to task status
- Preserve handover manifests exactly when passing between phases
- Halt on any execution failure in `--auto` mode
- Delegate commit creation to phase commands (do not create commits directly)
</constraints>

<phase_transition>
```
Previous: {ANY}
Current:  /deviate-cycle
Next:     {/deviate-execute|/deviate-tdd-red|/deviate-tdd-green|/deviate-tdd-refactor}
```
</phase_transition>

<aliases>
| Alias | Command |
|-------|---------|
| `/c` | `/deviate-cycle` |
| `/ca` | `/deviate-cycle --auto` |
</aliases>

<examples>

<example>
<title>Example 1: Start New Task</title>
```
User: /deviate-cycle

Agent:
<routing_output>
<state_analysis>
<yaml>
handover_source: none
previous_phase: null
task_id: T001
task_status: pending
complexity_score: 5
</yaml>
</state_analysis>

<routing_decision>
[Target]: /deviate-tdd-red
[Reason]: New task T001 has complexity 5 (TDD required)
</routing_decision>

<next_action>
Execute: `/deviate-tdd-red`
</next_action>
</routing_output>
```
</example>

<example>
<title>Example 2: Continue From Red</title>
```
User: /deviate-cycle

Agent:
<routing_output>
<state_analysis>
<yaml>
handover_source: conversation
previous_phase: RED
task_id: T001
task_status: in_progress
</yaml>
</state_analysis>

<routing_decision>
[Target]: /deviate-tdd-green
[Reason]: Red phase complete, tests written and failing
</routing_decision>

<next_action>
Execute: `/deviate-tdd-green` with RED manifest
</next_action>
</routing_output>
```
</example>

<example>
<title>Example 3: Direct Execution</title>
```
User: /deviate-cycle

Agent:
<routing_output>
<state_analysis>
<yaml>
handover_source: none
previous_phase: null
task_id: T002
task_status: pending
complexity_score: 1
</yaml>
</state_analysis>

<routing_decision>
[Target]: /deviate-execute
[Reason]: Task T002 has complexity 1 (direct execution)
</routing_decision>

<next_action>
Execute: `/deviate-execute T002`
</next_action>
</routing_output>
```
</example>

<example>
<title>Example 4: Continuous Mode</title>
```
User: /deviate-cycle --auto

Agent:
🔍 Starting continuous cycle...

[Cycle 1]
→ Task T001 (complexity 5)
  Route to /deviate-tdd-red
  [Executes Red]
  Route to /deviate-tdd-green
  [Executes Green]
  Route to /deviate-tdd-refactor
  [Executes Refactor]
  ✅ T001 complete

[Cycle 2]
→ Task T002 (complexity 2)
  Route to /deviate-execute
  [Executes direct]
  ✅ T002 complete

[Cycle 3]
→ No tasks remaining

<routing_output>
<status>
[Value]: NO_TASKS_REMAINING
</status>

<summary>
Tasks completed: 2
Time elapsed: 45 minutes
</summary>
</routing_output>
```
</example>

</examples>

