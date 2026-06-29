"""Tome subsystem runtime.

Adds Python runtime for the Tome Subsystem (FLOW-04..FLOW-10). The seven
writer/verifier/setup skills remain prompt-only at
``src/deviate/prompts/commands/tome-*.md``; this package only orchestrates
them. Currently ships:

- ``parser`` — extract capability rows from a ``/tome-classify`` markdown report
- ``dispatch`` — run a single writer against the configured agent backend
- ``batch`` — fan-out orchestration with resume + parallel workers

The CLI surface is mounted at ``deviate tome`` via
``src/deviate/cli/tome.py``. This module is intentionally minimal: the
classification/verifier/setup skills carry the semantic content; this
package is the deterministic enforcement shell.
"""
