# Checkpoint verification

Verify the checkpoint task. You receive the full verification context:
task, issue, contract, commands, worktree, doc, and capabilities.

Report a CHECKPOINT handover with PASS or FAIL, covering every declared
command and criterion with nonempty evidence.

Read the issue's tasks.md and plan.md to find the verification commands and acceptance criteria.
Run the declared commands. Do not modify the task ledger.
Return a YAML handover in a fenced yaml block with these fields:
- phase: CHECKPOINT
- status: PASS or FAIL
- results: nonempty list of checks with check and ok fields
- declared_commands: all verification commands
- command_reports: one command and exit_code mapping per command
- declared_criteria: all applicable criterion identifiers
- criterion_coverage: verified criterion identifiers
- evidence: nonempty list with ac, test_path, and test_quote fields
- rationale: explain any failure
Report PASS only when all commands and criteria pass. Report FAIL when verification cannot finish.
