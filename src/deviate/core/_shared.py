from __future__ import annotations

import os


def git_env() -> dict[str, str]:
    return {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("GIT_") and not k.startswith("GH_")
    }
