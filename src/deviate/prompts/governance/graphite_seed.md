## Graphite Stacked Changes Workflow

When Graphite integration is enabled (`.deviate/config.toml` contains `graphite = true`):

### Branch Creation
- Use `gt create -am "<message>"` to create a branch with an automatic commit
- If the working tree is clean, use `gt create -m "<message>"` instead

### PR Submission
- Use `gt submit --stack` to submit the entire stack for review

### Syncing
- Use `gt sync` to sync your stack with the remote

### Anti-Patterns
- Do NOT use `git checkout -b` alongside `gt` — it bypasses Graphite's stack tracking
- Do NOT use `gh pr create` when Graphite is enabled — use `gt submit --stack`
- Do NOT run `gt` commands outside a Graphite-tracked repository
