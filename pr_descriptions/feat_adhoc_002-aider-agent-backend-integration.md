The Aider Agent Backend Integration adds aider as a fourth code-generation backend alongside opencode/claude/droid, with aider-specific `--message` invocation, chat-style output parsing, and timeout/retry handling. This extends the existing `AgentBackend` abstraction to support aider's fundamentally different invocation semantics (no heredoc pipe, `--file`/`--read` context args, `--yes` non-interactive mode).

Agent Backend: Added `AiderBackend` provider in `src/deviate/core/agent.py` with `AiderConfig` Pydantic model for model selection, `read_files` context injection, and post-invocation test guard (always runs `mise run test` after aider). AiderNotFound errors hard-abort with non-zero exit. Added `AgentConfig.backend` Literal `"aider"` and full integration tests in `tests/test_integration/test_aider_backend.py`.

Closes ISS-ADH-002
