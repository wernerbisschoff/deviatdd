from __future__ import annotations

import os
import re


# Orchestrator's `git commit` that writes JUDGE feedback runs through
# the project's pre-commit hook chain. Observed hook chains on some
# projects can exceed 30s. 300s gives legitimate hooks room to complete
# while still detecting a genuine hang.
JUDGE_FEEDBACK_COMMIT_TIMEOUT_SECONDS: int = 300


# Second-worktree branches append -rN to the issue slug: feat/<epic>/<slug>-r2.
# Resolvers try the exact slug first, then this stripped form.
def issue_slug_variants(slug: str) -> list[str]:
    """Return [slug, slug-without--rN-suffix] (second entry only when stripped)."""
    match = re.fullmatch(r"(.+)-r\d+", slug)
    if match is None:
        return [slug]
    return [slug, match.group(1)]


def git_env() -> dict[str, str]:
    """Return os.environ with GIT_* and GH_* stripped.

    Production code MUST pass this as the `env` of every `git`/`gh`
    subprocess call so child processes don't inherit the parent's git
    identity, remotes, or auth state. Prefer creating branch refs
    (`git branch <name>`) over `git checkout -b` in non-interactive code;
    if a checkout is unavoidable, save `git rev-parse --abbrev-ref HEAD`
    first and restore it afterwards.
    """
    return {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("GIT_") and not k.startswith("GH_")
    }
