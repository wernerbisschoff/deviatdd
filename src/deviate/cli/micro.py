"""Re-export shim for the micro phase package (TSK-001-02).

Verbatim logic lives in :mod:`deviate.cli.micro`. This module holds no
logic. It stays under 100 lines and deletes once zero shim imports remain.
"""

from deviate.cli.micro import _find_all_pending_tasks as _find_all_pending_tasks
from deviate.cli.micro import _run_all as _run_all
from deviate.cli.micro import e2e_app as e2e_app
from deviate.cli.micro import execute_app as execute_app
from deviate.cli.micro import (
    existing_verification_suites as existing_verification_suites,
)
from deviate.cli.micro import green_app as green_app
from deviate.cli.micro import hotfix_app as hotfix_app
from deviate.cli.micro import judge_app as judge_app
from deviate.cli.micro import micro_app as micro_app
from deviate.cli.micro import red_app as red_app
from deviate.cli.micro import refactor_app as refactor_app

__all__ = [
    "_find_all_pending_tasks",
    "_run_all",
    "e2e_app",
    "execute_app",
    "existing_verification_suites",
    "green_app",
    "hotfix_app",
    "judge_app",
    "micro_app",
    "red_app",
    "refactor_app",
]
