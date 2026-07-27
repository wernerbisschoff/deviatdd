# DeviaTDD Product Flow Starter

> Optional starter. The first time you run `/deviate-flows` against a fresh
> consumer repo, the agent reads this file as a working example and writes
> new `flows-<domain>.md` blocks (or extends this one) for the user-visible
> flows the operator actually cares about. There is **no fixed FLOW-01/02/03
> triple** — FLOW-01 is whatever the consumer's first flow turns out to be,
> FLOW-02 the next, and so on.

## Example — FLOW-01 &lt;Name of First Flow&gt;
- Actor: <actor>
- Domain: <domain>
- Status: Draft

### Problem / job to be done
- <one sentence: the user-visible behavior this flow delivers>

### Trigger
- <what starts the flow — slash command, event, schedule, manual action>

### Preconditions
- <any non-trivial state the consumer must be in before the trigger>

### Happy path (primary steps)
1. <step 1>
2. <step 2>
3. <step 3>

### Alternate / error paths
TBD

### Success State
- <observable end state>

### Metrics / Signals
- references FLOW-01 (this is the starter self-reference only)
