<graphite_routing>
When Graphite is enabled (`.deviate/config.toml` has `graphite = true`), this skill routes PR operations through the Graphite CLI (`gt`) instead of the GitHub CLI (`gh`).

<pr_submission>
- Use `gt submit --stack --no-edit` to submit the entire stacked branch for review.
- After `gt submit --stack`, the `deviate pr run` command calls `_update_gt_prs()` in `src/deviate/cli/meso.py:959` which parses the submit output for PR URLs and runs `gh pr edit <number> --title <title> --body-file <path>` on each created PR. This is because `gt submit` has no `--title` or `--body-file` flag — `gh pr edit` post-submit is the only non-interactive fixup path.
- Do NOT invoke `gh pr create` directly — Graphite owns PR creation from stacked branches.
- The `--merge` and `--auto-merge` flags are incompatible with `gt submit --stack` and will be ignored at runtime; surface a warning if they were requested.
</pr_submission>

<branch_creation_between_tasks>
When `graphite = true` and the micro layer runs all tasks via `_run_all()` in `src/deviate/cli/micro.py:1854`, it calls `gt create -m "feat(<next_id>): <description>"` after each successful task (except the last) to create a stacked branch for the next task. This ensures each task lands on its own branch in the Graphite stack.
</branch_creation_between_tasks>

<anti_patterns>
- Do NOT call `git checkout -b` to create the issue branch — `gt create -am` was already used by the meso layer.
- Do NOT mix `gh` and `gt` commands in the same PR lifecycle — pick one based on the config flag.
- Do NOT skip the Graphite routing even if the user requests `gh pr create` manually — defer to the runtime config.
</anti_patterns>
</graphite_routing>
