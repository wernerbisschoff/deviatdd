from __future__ import annotations

import subprocess as _real_subprocess
from unittest.mock import MagicMock, patch

import pytest


class _MockSubprocess:
    """Replaces ``deviate.cli.micro.subprocess`` with a proxy.

    Subprocess calls from micro.py are intercepted:
    * ``subprocess.run(...)`` — Git commands pass through to the real
      ``subprocess`` module (needed by ``_detect_phase_changes``,
      ``_commit_phase``, ``_verify_clean_worktree``).  All other
      commands (pytest, misc) return a default ``CompletedProcess``
      with ``returncode=0``.
    * ``subprocess.Popen(...)`` — Always returns a mock process
      (used by ``_invoke_agent`` to launch the agent binary).

    Modules other than ``deviate.cli.micro`` (test code, fixtures,
    other modules) continue to use the real ``subprocess`` module
    because only the namespace reference inside micro.py is replaced.
    """

    CompletedProcess = _real_subprocess.CompletedProcess
    PIPE = _real_subprocess.PIPE

    @staticmethod
    def run(*args, **kwargs) -> _real_subprocess.CompletedProcess:
        cmd = args[0] if args else kwargs.get("args", [])
        if isinstance(cmd, (list, tuple)) and cmd and str(cmd[0]) == "git":
            return _real_subprocess.run(*args, **kwargs)
        return _real_subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

    @staticmethod
    def Popen(*args, **kwargs) -> MagicMock:
        proc = MagicMock()
        proc.communicate.return_value = ("", "")
        proc.poll.return_value = 0
        proc.returncode = 0
        proc.__enter__.return_value = proc
        return proc

    def __getattr__(self, name: str):
        return getattr(_real_subprocess, name)


@pytest.fixture(autouse=True)
def mock_micro_subprocess():
    """Prevent ``deviate.cli.micro`` from running real subprocesses.

    This fixture replaces *only* the ``subprocess`` module reference
    inside ``deviate.cli.micro`` with a mock proxy.  Subprocess calls
    from test code, fixtures, and non-micro modules still use the
    real ``subprocess`` module, so ``tmp_git_repo``, git setup
    commands, and direct ``subprocess.run`` calls work normally.

    Git commands from micro.py are allowed through (needed for
    ``_detect_phase_changes``, ``_commit_phase``, etc.).  Agent and
    pytest subprocesses are blocked with safe defaults.
    """
    with (
        patch("deviate.cli.micro.subprocess", _MockSubprocess()),
        patch("deviate.core.agent.subprocess", _MockSubprocess()),
    ):
        yield
