"""CLI entry point for the ``deviate`` script.

Imports ``faulthandler`` first and enables it before any other module
loads. This guarantees a C-level traceback is dumped to stderr on any
SIGSEGV/SIGABRT/SIGBUS/SIGILL/SIGFPE — `except Exception` cannot trap
those, so without this hook the orchestrator process dies silently and
the only signal to the operator is the shell's ``[N] segmentation
fault`` line. Tree-sitter and other C extensions have been observed to
leave the interpreter in a fork-unsafe state, so this hook pays for
itself the first time a third-party C extension crashes.
"""

import faulthandler
import sys

faulthandler.enable()
# ``from .cli import cli`` must come AFTER faulthandler.enable() so the
# faulthandler is registered before any tree-sitter or subprocess code
# loads. The intentional ordering is required to catch SIGSEGV during
# import-time C-extension initialization.
from .cli import cli  # noqa: E402
from .core.herdr import with_herdr_status  # noqa: E402


def _tracked_run_command(argv: list[str]) -> str | None:
    if argv[:2] == ["micro", "run"]:
        return "micro run"
    if argv[:2] == ["meso", "run"]:
        return "meso run"
    if argv[:1] == ["run"]:
        return "run"
    return None


def app() -> None:
    command = _tracked_run_command(sys.argv[1:])
    if command is None:
        cli()
        return
    with_herdr_status(command)(cli)()


__all__ = ["app"]
