"""AC-PLAN-002/005: micro public-surface parity lock (RED)."""

import pytest
from typer.testing import CliRunner

pytestmark = pytest.mark.behavioral

PUBLIC_NAMES = [
    "micro_app",
    "red_app",
    "green_app",
    "judge_app",
    "refactor_app",
    "e2e_app",
    "execute_app",
    "hotfix_app",
    "_run_all",
    "_find_all_pending_tasks",
    "existing_verification_suites",
]

APP_COMMANDS = {
    "micro_app": ["run"],
    "red_app": ["pre", "post"],
    "green_app": ["pre", "post"],
    "judge_app": ["pre", "post"],
    "refactor_app": ["pre", "post"],
    "e2e_app": ["pre", "post"],
    "execute_app": ["pre", "post"],
    "hotfix_app": ["pre", "post"],
}

HELP_MUST_CONTAIN = [
    "micro",
    "red",
    "green",
    "judge",
    "refactor",
    "execute",
    "e2e",
    "hotfix",
]


def _app_command_names(app) -> list[str]:
    names = []
    for c in app.registered_commands:
        names.append(c.name or (c.callback.__name__ if c.callback else ""))
    return sorted(names)


def test_public_names_importable():
    import deviate.cli.micro as m

    for name in PUBLIC_NAMES:
        assert hasattr(m, name), name


def test_typer_apps_expose_commands():
    import deviate.cli.micro as m

    for app_name, expected in APP_COMMANDS.items():
        assert _app_command_names(getattr(m, app_name)) == sorted(expected), app_name


def test_callables_are_callable():
    import deviate.cli.micro as m

    assert callable(m._run_all)
    assert callable(m._find_all_pending_tasks)
    assert callable(m.existing_verification_suites)


def test_deviate_help_snapshot():
    from deviate.cli import cli

    out = CliRunner().invoke(cli, ["--help"]).output
    for token in HELP_MUST_CONTAIN:
        assert token in out, token
