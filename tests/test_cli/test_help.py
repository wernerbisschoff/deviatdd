"""Regression test for ``deviate --help``.

The first-timer help output is the project's primary onboarding surface;
regressions in panel grouping or in the literal ``Use `deviate meso run` `` /
``Use `deviate run --all` `` strings would directly harm new users. This
test pins the panel names, panel membership, and the literal first-timer
wording so it cannot drift.

Pin target: Typer's ``rich_help_panel`` groups in
``src/deviate/cli/__init__.py``. Adding a new top-level command without
choosing a panel, or moving a command between panels, must update this
test on purpose.

The assertions are deliberately substring-based rather than exact-match:
Rich wraps table cells by terminal width, so a byte-exact comparison is
brittle. What we pin here is the *meaning* — the panel labels, the
ordered presence of key commands, and the literal first-timer strings.
"""

from __future__ import annotations

import re

from typer.testing import CliRunner

from deviate.cli import cli

runner = CliRunner()

USER_PANEL = "Run by you (start here)"
OPTIONAL_PANEL = "Optional / manual utilities"
AGENT_PANEL = "Agent/internal (via /deviate-* slash commands)"


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    """Remove ANSI SGR escape sequences (color, bold, dim, etc.)."""
    return _ANSI_RE.sub("", text)


def _help_output() -> str:
    """Return ``deviate --help`` stdout via CliRunner, with ANSI codes stripped.

    Rich/Typer uses SGR codes even for basic box-drawing: on non-TTY stdout
    (CI, pipes) it wraps panel markers in ``\\x1b[2m`` (dim) which breaks
    ``str.find`` — strip them so panel searching is encoding-agnostic.
    """
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0, result.output
    return _strip_ansi(result.output)


def _panel_block(output: str, panel_name: str) -> str:
    """Slice *output* between the panel header and the next box-drawing boundary.

    Typer renders panels as framed boxes. Within a panel each command
    occupies a row starting with ``│ <cmd>``. We return the raw text
    between the panel header and the next ``╭─`` (next panel) or ``╰─``
    (footer) so the substring tests can search within it.
    """
    header_marker = f"╭─ {panel_name}"
    start = output.find(header_marker)
    assert start != -1, (
        f"Panel {panel_name!r} not found in --help output. Output was:\n{output}"
    )
    # Advance past the header line (the box-drawing top border).
    line_end = output.find("\n", start)
    assert line_end != -1
    start = line_end + 1

    # End at the next panel header (╭─) or the panel footer (╰─).
    for terminator in ("╭─", "╰─"):
        idx = output.find(terminator, start)
        if idx != -1:
            return output[start:idx]
    return output[start:]


def test_help_exits_zero_and_shows_brand():
    """``deviate --help`` exits 0 and prints the DeviaTDD brand string."""
    output = _help_output()
    assert "DeviaTDD" in output


def test_help_user_panel_lists_human_entry_points():
    """The 'Run by you (start here)' panel must list ``setup``, ``run``, and
    ``meso`` — the three commands a first-timer actually runs by hand."""
    output = _help_output()
    block = _panel_block(output, USER_PANEL)
    for cmd in ("setup", "run", "meso"):
        assert cmd in block, (
            f"Expected {cmd!r} in {USER_PANEL!r} panel; panel block was:\n{block}"
        )


def test_help_optional_panel_lists_feature_and_inspect():
    """The 'Optional / manual utilities' panel must hold ``feature`` and
    ``inspect`` — useful but not on the standard first-timer path."""
    output = _help_output()
    block = _panel_block(output, OPTIONAL_PANEL)
    for cmd in ("feature", "inspect"):
        assert cmd in block, (
            f"Expected {cmd!r} in {OPTIONAL_PANEL!r} panel; panel block was:\n{block}"
        )


def test_help_agent_panel_lists_phase_dispatchers():
    """The 'Agent/internal' panel must list the pre/post phase dispatchers
    (``specify``, ``plan``, ``tasks``, ``pr``, ``merge``) so first-timers
    see they are not for them."""
    output = _help_output()
    block = _panel_block(output, AGENT_PANEL)
    for cmd in ("specify", "plan", "tasks", "pr", "merge"):
        assert cmd in block, (
            f"Expected {cmd!r} in {AGENT_PANEL!r} panel; panel block was:\n{block}"
        )


def test_help_agent_panel_lists_macro_micro_groups():
    """The 'Agent/internal' panel must list every macro/micro Typer group
    the agent drives, so first-timers see them all in one labeled bucket."""
    output = _help_output()
    block = _panel_block(output, AGENT_PANEL)
    # Macro-phase groups
    for cmd in ("explore", "research", "prd", "shard", "macro", "adhoc"):
        assert cmd in block, f"Expected macro group {cmd!r} in {AGENT_PANEL!r} panel"
    # Micro-phase groups (per-phase dispatchers + umbrella `micro` group).
    # `micro` is the umbrella for `deviate micro run [task-id] --all`; it
    # used to live as a top-level `run` and was moved to `micro run` when
    # the top-level `deviate run` was promoted to the full-pipeline
    # orchestrator.
    for cmd in (
        "red",
        "green",
        "judge",
        "refactor",
        "execute",
        "e2e",
        "hotfix",
        "micro",
    ):
        assert cmd in block, f"Expected micro group {cmd!r} in {AGENT_PANEL!r} panel"
    # Operational (still agent-internal)
    for cmd in ("constitution", "init", "review"):
        assert cmd in block, (
            f"Expected operational command {cmd!r} in {AGENT_PANEL!r} panel"
        )


def test_help_user_panel_appears_before_agent_panel():
    """The 'Run by you' panel must precede the agent panel in the rendered
    output — first-timers read top-down and the human entry points must
    come first."""
    output = _help_output()
    user_idx = output.find(USER_PANEL)
    agent_idx = output.find(AGENT_PANEL)
    assert user_idx != -1, f"{USER_PANEL!r} not found in --help"
    assert agent_idx != -1, f"{AGENT_PANEL!r} not found in --help"
    assert user_idx < agent_idx, (
        "Run-by-you panel must appear before the agent-internal panel"
    )


def test_help_meso_row_pins_literal_invocation():
    """The ``meso`` row in --help must call out the literal
    ``Use `deviate meso run` `` invocation, since ``--help`` only renders
    the ``meso`` group row and the actual command lives one level deeper.
    Without this hint a first-timer would have to discover ``meso --help``
    on their own.
    """
    output = _help_output()
    assert "Use `deviate meso run`" in output, (
        "Expected the literal 'Use `deviate meso run`' string in --help. "
        "First-timers see only the 'meso' group row in the panel; without "
        "this hint they cannot find `meso run`."
    )


def test_help_run_docstring_promotes_full_pipeline():
    """The ``run`` row in --help must lead with the full-pipeline
    invocation so first-timers discover it as the canonical entry point.

    `deviate run` is now an orchestrator that runs ``deviate meso run``
    followed by ``deviate micro run --all`` in the created worktree;
    it does not take a task-id argument. The old per-task / ``--all``
    dispatcher lives at ``deviate micro run`` now.
    """
    output = _help_output()
    assert "Use `deviate run`" in output, (
        "Expected the literal 'Use `deviate run`' string in --help. "
        "The 'run' row must lead with the full-pipeline invocation."
    )
    assert "`deviate micro run`" in output, (
        "Expected the docstring to mention `deviate micro run` so "
        "operators know where the per-task / --all dispatcher moved."
    )


def test_help_setup_row_has_bootstrap_description():
    """The ``setup`` row must carry the ``Bootstrap`` description, not just
    the bare name. Before this change ``setup`` appeared with no
    description at all.
    """
    output = _help_output()
    block = _panel_block(output, USER_PANEL)
    # The setup row starts with "│ setup" and runs until the next "│".
    # Substring match is sufficient — Rich may wrap the description.
    assert "setup" in block
    assert "Bootstrap" in block, (
        f"Expected 'Bootstrap' description in the user panel; panel block was:\n{block}"
    )


def _extract_panel_command_names(panel_block: str) -> list[str]:
    """Extract command names from a Typer panel block.

    Typer renders each command on its own row whose first non-whitespace
    token is the command name, followed by enough padding to push the
    description to the next column. Continuation rows (Rich wrapping of a
    long description) start with the box-drawing border then many spaces
    of padding and never contain a command name.

    The pattern ``│ <token><3+ spaces>`` matches command rows only —
    continuation rows either lack a leading token (only padding) or have
    only single-space gaps between description words.
    """
    pattern = re.compile(r"^│ (\S+)\s{3,}", re.MULTILINE)
    return pattern.findall(panel_block)


def test_help_user_panel_has_exactly_three_commands():
    """The 'Run by you' panel must contain exactly ``setup``, ``run``,
    ``meso`` as command rows. If a phase dispatcher or agent-internal
    command ever leaks into this panel, a first-timer will think it is
    for them — this assertion catches that regression.
    """
    output = _help_output()
    user_block = _panel_block(output, USER_PANEL)
    user_command_names = set(_extract_panel_command_names(user_block))
    assert user_command_names == {"setup", "run", "meso"}, (
        f"User panel must contain exactly {{setup, run, meso}} as "
        f"command rows; got {sorted(user_command_names)}"
    )


def test_help_phase_dispatchers_not_user_panel_commands():
    """The pre/post phase dispatchers (``specify``/``plan``/``tasks``/
    ``pr``/``merge``) must not appear as command rows in the user panel.

    Note: they may legitimately appear as substrings of the ``meso`` row
    description (``setup → plan → tasks pipeline``); the regex parser
    above only matches command-row tokens, so description words are
    ignored.
    """
    output = _help_output()
    user_block = _panel_block(output, USER_PANEL)
    user_command_names = set(_extract_panel_command_names(user_block))
    for dispatcher in ("specify", "plan", "tasks", "pr", "merge"):
        assert dispatcher not in user_command_names, (
            f"Phase dispatcher {dispatcher!r} must not appear as a "
            f"command in the Run-by-you panel; got "
            f"{sorted(user_command_names)}"
        )
