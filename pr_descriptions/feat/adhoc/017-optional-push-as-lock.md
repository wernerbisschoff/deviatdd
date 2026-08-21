Optional push-as-lock for work repos: standing `claim_remote` in `.deviate/config.toml` (default `true`) plus `--local` on `deviate specify`, `deviate meso run`, and `deviate run`. Flag overrides config. Worktree + `feat/{epic}/{issue}` + ledger SPECIFIED stay; only the remote-branch lock and `git push` are skipped when local.

`deviate setup --no-claim-remote` persists `claim_remote = false`. Personal projects with no config change still push the claim branch.

Closes #64
