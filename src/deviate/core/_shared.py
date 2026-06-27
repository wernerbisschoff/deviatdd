from __future__ import annotations

import os


def git_env() -> dict[str, str]:
    """Return os.environ with GIT_* and GH_* stripped.

    Production code MUST pass this as the `env` of every `git`/`gh`/`gt`
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
