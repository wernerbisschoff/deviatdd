## Graphite Routing

When Graphite is enabled (`.deviate/config.toml` has `graphite = true`), this skill routes PR operations through the Graphite CLI (`gt`) instead of the GitHub CLI (`gh`).

### PR Submission

- Use `gt submit --stack` to submit the entire stacked branch for review.
- Do NOT invoke `gh pr create` — Graphite owns PR creation from stacked branches.
- The `--merge` and `--auto-merge` flags are incompatible with `gt submit --stack` and will be ignored at runtime; surface a warning to the stakeholder if they were requested.

### Branch Context

- The PR body and title generation (steps 1-3 of the execution sequence) still produce a `pr_descriptions/<branch>.md` file for `gt submit --stack` to consume as the stack description.
- Squash-merge commits still read as conventional commit subjects because `gt submit` preserves commit metadata.

### Anti-Patterns

- Do NOT call `git checkout -b` to create the issue branch — `gt create -am` was already used by the meso layer.
- Do NOT mix `gh` and `gt` commands in the same PR lifecycle — pick one based on the config flag.
- Do NOT skip the Graphite routing even if the user requests `gh pr create` manually — defer to the runtime config.
