<macro_layer_model>


<shared_disciplines>

<item>
<title>Feature Bucket Allocation</title>
Each macro phase operates within a pre-allocated feature bucket. For **research**, **PRD**, and **shard**, the bucket is `specs/{NNN}-{FEATURE_SLUG}/` (a numbered epic directory). For **explore**, the bucket is `specs/explore/` (a staging directory, NOT a numbered epic). The bucket is pre-allocated by the lifecycle entry step; do NOT re-derive paths from the problem statement.
</item>



<item>
<title>Subagent Delegation</title>
**explore** may spawn 2-3 parallel read-only discovery subagents; each returns text fragments only — no file writes. **research** is ordered: one agent, two sequential jobs in the same prompt — do not spawn research sub-agents or forward context between two research processes. **prd** and **shard** collapse to a single linear pass.
</item>

<item>
<title>Zero Implementation Code</title>
Macro phases MUST NOT write, modify, or generate any implementation code (source files, tests, configs, scripts, migrations). Only specification/design/PRD documents are written.
</item>

<item>
<title>User Scenarios Belong on the Issue</title>
Macro phases author application behavior. **shard** and **adhoc** MUST write `## User Stories Ledger` plus ATDD (`## Acceptance Outline` with `AO-NNN`) on every issued vertical. See core Application Scope Only for the precondition exclusion list.
</item>

</shared_disciplines>

</macro_layer_model>
