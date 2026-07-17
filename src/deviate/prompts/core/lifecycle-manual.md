<lifecycle mode="manual">

**Pre/Post Script Lifecycle**: Every phase begins with `deviate <phase> pre` (allocates bucket / resolves worktree, emits JSON contract on stdout). Parse the contract to extract runtime attributes — the contract carries layer-specific fields listed in the per-phase template below. Do NOT re-derive paths from the problem statement. Every phase ends with `deviate <phase> post` (validates artifacts, commits, returns status). The post-script runs precommit hooks which include the full test suite — allocate a timeout of at least 180s (3 minutes) when running this command.

**HITL Gate Handoff**: After the post-script completes successfully, terminate. Do NOT auto-advance to the next phase. The phase terminates at a HITL (Human In The Loop) gate — the human decides when to proceed.

</lifecycle>