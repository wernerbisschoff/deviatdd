# Plan: Fixing the TDD Integration Gap in DeviaTDD

## Problem Statement

### The Architectural Trap

When the code under test is responsible for **orchestration or external integration** (spawning subprocesses, hitting external APIs, sending prompts to agents), mocking the orchestration function itself (`_invoke_agent`) means you end up testing the mock rather than the integration logic.

**The Failure Mode:**
1. Agent satisfies the test by ensuring the mock is called
2. The actual critical-path wiring code inside the function is left completely unexecuted
3. The agent never implements the real subprocess invocation logic
4. Tests pass, but production code is broken

**Example from Current Codebase:**
```python
# micro.py:250-254
if agent:
    skill = _load_skill_content("RED")
    if skill:
        prompt = _build_agent_prompt(skill, "RED", task, Path.cwd())
        _invoke_agent(prompt, c, backend_name=agent)
```

The `_invoke_agent` function is mocked in tests, so the actual `AgentBackend.invoke()` subprocess logic is never driven by a failing test.

---

## Root Cause Analysis

The DeviaTDD architecture already contains the conceptual tools to solve this. The Meso Layer specification for `tasks.md` explicitly dictates that each task entry includes defined **mock boundaries**.

The breakdown occurs when:
1. Task decomposition doesn't enforce system-edge mock boundaries
2. Tests mock high-level internal functions instead of external boundaries
3. The TDD cycle satisfies the test without implementing the wiring code

---

## Solution Strategy

### 1. Push Mock Boundary to System Edge (Recommended)

**Principle:** Instead of allowing the agent to mock high-level internal Python functions like `_invoke_agent`, the task definition must force the mock boundary out to the true external environment boundary (e.g., `subprocess.run`, `subprocess.Popen`, or network sockets).

**How it works in the RED phase:**
- The agent writes an integration/contract test
- Instead of patching `_invoke_agent`, it uses `pytest-mock` to patch `subprocess.Popen` or uses a loopback fixture
- The test asserts that a subprocess is executed with the exact expected CLI arguments, environment variables, and input streams

**Why this solves the gap:**
- Because `_invoke_agent` itself is *not* mocked, the test will remain RED until the agent actually implements the real subprocess invocation logic
- The test correctly wires the prompt strings into the command execution stream
- This preserves the strict TDD state machine (RED → GREEN → JUDGE) while fully driving the implementation of the wiring code

**Example Test Pattern:**
```python
def test_agent_invokes_subprocess_with_correct_prompt(mock_popen):
    # Arrange
    backend = AgentBackend(config=AgentConfig(backend="opencode"))
    prompt = "Write a failing test for..."
    
    # Act
    backend.invoke(prompt)
    
    # Assert - subprocess.Popen was called with correct args
    mock_popen.assert_called_once()
    call_args = mock_popen.call_args
    assert call_args[0][0] == ["opencode", "run"]
    assert call_args[1]["stdin"] == subprocess.PIPE
    # Verify the prompt was passed via stdin
    stdin_write = mock_popen.return_value.communicate.call_args
    assert prompt.encode("utf-8") in stdin_write[1]["input"]
```

---

### 2. Handle the `if agent:` Gate in micro.py

**Problem:** The integration code contains an operational gate that skips execution unless a live agent backend is specified.

**Solution Options:**

#### Option A: Introduce a Stub/Test Agent Backend (Recommended)

Add a lightweight, deterministic stub backend option to `AgentBackend` (located in `src/deviate/core/agent.py`).

**Implementation:**
```python
# In src/deviate/core/agent.py
BACKEND_COMMANDS: dict[str, str] = {
    "opencode": "opencode run",
    "claude": "claude -p",
    "droid": "droid exec",
    "stub": "echo",  # Deterministic stub for testing
}

class StubAgentBackend(AgentBackend):
    """Deterministic stub backend for testing integration logic."""
    
    def invoke(self, prompt: str, backend=None, timeout=None) -> HandoverManifest:
        # Return a valid mock HandoverManifest without subprocess overhead
        return HandoverManifest(
            phase="RED",
            status="success",
            test_file="tests/test_example.py",
            verification_command="pytest tests/test_example.py"
        )
```

**Usage in Tests:**
```python
def test_red_phase_invokes_agent(backend=StubAgentBackend()):
    # Test the full integration flow without live LLM costs
    _run_red_phase(task, ledger_path, session, session_path, console, agent="stub")
    # Assert state transitions, ledger updates, etc.
```

#### Option B: Expose the Gate to Environment Variables

Allow the test suite to bypass or force-satisfy the `if agent:` gate by injecting a test-specific environment flag during the pytest run loop.

```python
# In micro.py
if agent or os.getenv("DEVIATE_TEST_AGENT"):
    # ... invoke agent
```

**Recommendation:** Use Option A (stub backend) as it's more explicit and doesn't leak test concerns into production code.

---

### 3. Why NOT Use Direct Tasks for Wiring Code?

**Question:** Should we make wiring code a direct task with downstream regression tests?

**Answer:** No, this is not recommended for critical path integration.

**Rationale:**
- Direct tasks are architecturally reserved for boilerplate, dependency updates, or static asset syncing
- Using direct for critical integration logic loses the safety of the failing test driver
- Increases the risk that the agent writes hallucinated or broken subprocess structures that pass silently until much later
- The TDD cycle provides immediate feedback on integration correctness

**When to use Direct/IMMEDIATE:**
- Config file updates
- Documentation changes
- Dependency version bumps
- Static asset syncing
- Pure refactoring with existing test coverage

---

### 4. Leveraging the Existing E2E Task Entry

**Principle:** You do not need a new acceptance entry point. The architecture allows the agent to append a terminal `type: "e2e"` task to issues modifying user-facing behavior (recommended but no longer mandatory per `specs/DeviaTDD-architecture.md`).

**How it works:**
1. Individual integration tasks are completed via outer-boundary TDD
2. When present, the terminal e2e task executes at the **Issue Gate** boundary
3. This system-level evaluation orchestrates the real runtime environment
4. Verifies via exit codes that the fully wired components operate successfully end-to-end

**Example E2E Verification:**
```bash
# E2E task runs the actual deviate micro command
deviate micro TSK-001-01 --agent opencode
# Verifies:
# - Agent subprocess is invoked
# - Prompt is correctly formatted
# - Handover manifest is parsed
# - State transitions occur
# - Ledger is updated
```

---

## Concrete Action Plan

### Action 1: Update Meso Layer Task Decomposition Prompt

**File:** `src/deviate/prompts/skills/deviate-tasks/SKILL.md`

**Change:** Modify the prompt instructions used during `deviate tasks pre`. Explicitly instruct the model that if a task involves:
- "wiring components"
- "subprocess execution"
- "sending prompts to underlying agents"
- "external API integration"

Then it **must** be typed as `TDD`, and its mock boundaries metadata field **must** be explicitly defined at the system layer.

**Example Task Definition:**
```yaml
- [ ] T001: Agent backend subprocess invocation
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Mock Boundary**: subprocess.Popen (NOT _invoke_agent)
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_core/test_agent.py -v`
  - **Details**:
    - **Red**: Write test that patches `subprocess.Popen` and asserts correct CLI args
    - **Green**: Implement `AgentBackend.invoke()` using `subprocess.Popen`
    - **Refactor**: Extract backend command mapping to constant
```

---

### Action 2: Implement Test Agent Backend

**File:** `src/deviate/core/agent.py`

**Change:** Add a deterministic stub backend that returns a valid `HandoverManifest` response without subprocess overhead.

**Implementation:**
```python
class StubAgentBackend(AgentBackend):
    """Deterministic stub backend for testing integration logic."""
    
    def invoke(self, prompt: str, backend=None, timeout=None) -> HandoverManifest:
        return HandoverManifest(
            phase="RED",
            status="success",
            test_file="tests/test_stub.py",
            verification_command="pytest tests/test_stub.py"
        )
```

**Registration:**
```python
BACKEND_COMMANDS: dict[str, str] = {
    "opencode": "opencode run",
    "claude": "claude -p",
    "droid": "droid exec",
    "stub": "echo",  # Stub backend for testing
}
```

---

### Action 3: Refactor Existing Tests

**Files:** 
- `tests/test_micro/test_red.py`
- `tests/test_micro/test_green.py`
- `tests/test_micro/test_orchestration.py`

**Change:** Remove function-level mocks of core orchestrator loops (`_invoke_agent`). Force tests to inspect system interaction hooks.

**Before (Bad):**
```python
@patch("deviate.cli.micro._invoke_agent")
def test_red_phase_invokes_agent(mock_invoke):
    _run_red_phase(task, ...)
    mock_invoke.assert_called_once()
```

**After (Good):**
```python
def test_red_phase_invokes_subprocess(mock_popen):
    # Use stub backend to avoid live LLM calls
    _run_red_phase(task, ..., agent="stub")
    # Assert subprocess was invoked with correct structure
    mock_popen.assert_called_once()
    # Verify prompt was passed correctly
```

---

### Action 4: Update Task Decomposition Decision Tree

**File:** `src/deviate/prompts/skills/deviate-tasks/SKILL.md`

**Change:** Add explicit guidance for integration/wiring code in the decision tree (step 4b).

**Add to Decision Tree:**
```
7. Does this task primarily **connect/wire already-tested components** via subprocess, API, or message passing? 
   → **TDD** with system-edge mock boundary (mock subprocess.run, not the wiring function)
```

---

## Verification Criteria

### Success Metrics

1. **Mock Boundary Enforcement:**
   - All integration tasks define mock boundaries at system edge (subprocess, network)
   - No tests mock internal orchestration functions like `_invoke_agent`

2. **Stub Backend Availability:**
   - `AgentBackend` accepts `backend="stub"` parameter
   - Stub backend returns valid `HandoverManifest` without subprocess overhead

3. **Test Coverage:**
   - Integration tests verify subprocess invocation structure
   - Tests assert correct CLI args, environment variables, input streams
   - E2E task verifies full pipeline with real agent backend

4. **Task Decomposition:**
   - Wiring code tasks are typed as TDD (not IMMEDIATE)
   - Mock boundary metadata is explicitly defined in task details

---

## Risk Mitigation

### Risk 1: Stub Backend Diverges from Real Behavior

**Mitigation:** 
- Stub backend must return the same `HandoverManifest` schema as real backends
- E2E tests verify real backend integration
- Stub is only used for unit/integration tests, not production

### Risk 2: System-Edge Mocks Are Harder to Write

**Mitigation:**
- Provide example test patterns in task decomposition prompt
- Include fixture helpers for common subprocess mocking scenarios
- Document mock boundary patterns in constitution

### Risk 3: Tests Become Brittle with Subprocess Assertions

**Mitigation:**
- Focus on contract testing (args, env vars) not implementation details
- Use `pytest-mock` for flexible assertion patterns
- Refactor to extract subprocess invocation into testable units

---

## Implementation Sequence

1. **Phase 1: Foundation**
   - Implement stub agent backend in `src/deviate/core/agent.py`
   - Add stub to `BACKEND_COMMANDS` mapping
   - Write tests for stub backend behavior

2. **Phase 2: Task Decomposition**
   - Update `deviate-tasks` SKILL.md with mock boundary guidance
   - Add integration/wiring code to decision tree
   - Update task template to include mock boundary metadata

3. **Phase 3: Test Refactoring**
   - Identify tests that mock `_invoke_agent` or similar
   - Refactor to use system-edge mocks (subprocess.Popen)
   - Verify tests still pass with stub backend

4. **Phase 4: Validation**
   - Run full test suite to verify no regressions
   - Execute E2E task with real agent backend
   - Verify wiring code is now properly tested

---

## Conclusion

This plan addresses the TDD integration gap by:
1. Enforcing system-edge mock boundaries in task decomposition
2. Providing a stub backend for deterministic testing
3. Refactoring existing tests to verify integration logic
4. Leveraging the optional E2E task for end-to-end validation when present

The solution preserves the strict TDD state machine while ensuring that critical wiring code is properly driven by failing tests and verified through the full execution pipeline.
