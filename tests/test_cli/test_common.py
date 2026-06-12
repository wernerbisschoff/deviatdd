from __future__ import annotations

import json

import typer
from typer.testing import CliRunner

from deviate.cli._common import with_json_quiet

runner = CliRunner()


def test_with_json_quiet_exists():
    """@with_json_quiet is a callable decorator."""
    assert callable(with_json_quiet)


def test_with_json_quiet_json_flag():
    """When --json is passed, stdout contains only the JSON contract."""
    app = typer.Typer()

    @app.command()
    @with_json_quiet
    def sample_cmd():
        return {"status": "ok", "count": 42}

    result = runner.invoke(app, ["--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout.strip())
    assert data == {"status": "ok", "count": 42}


def test_with_json_quiet_quiet_flag():
    """When --quiet is passed, Rich/typer output is suppressed on stdout
    but stderr output is preserved."""
    app = typer.Typer()

    @app.command()
    @with_json_quiet
    def sample_cmd():
        typer.echo("visible message")
        typer.echo("error details", err=True)
        return {"status": "ok"}

    result = runner.invoke(app, ["--quiet"])
    assert result.exit_code == 0
    assert "visible message" not in result.stdout
    assert "error details" in result.stderr


def test_with_json_quiet_both():
    """When --json and --quiet are passed together, JSON contract goes to stdout
    and error output goes to stderr (orthogonal flags)."""
    app = typer.Typer()

    @app.command()
    @with_json_quiet
    def sample_cmd():
        typer.echo("ignore me")
        typer.echo("stderr message", err=True)
        return {"status": "ok"}

    result = runner.invoke(app, ["--json", "--quiet"])
    assert result.exit_code == 0
    data = json.loads(result.stdout.strip())
    assert data == {"status": "ok"}
    assert "stderr message" in result.stderr


def test_with_json_quiet_no_flags():
    """When neither flag is passed, normal Rich/typer output is displayed."""
    app = typer.Typer()

    @app.command()
    @with_json_quiet
    def sample_cmd():
        typer.echo("normal output")
        return {"status": "ok"}

    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "normal output" in result.stdout


def test_with_json_quiet_empty_contract():
    """When the wrapped function returns an empty dict, --json emits {} not null."""
    app = typer.Typer()

    @app.command()
    @with_json_quiet
    def sample_cmd():
        return {}

    result = runner.invoke(app, ["--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout.strip())
    assert data == {}


def test_with_json_quiet_integration_macro_pre():
    """Macro layer pre commands have @with_json_quiet applied."""
    from deviate.cli.macro import explore_pre, research_pre, prd_pre, shard_pre

    for cmd in (explore_pre, research_pre, prd_pre, shard_pre):
        assert hasattr(cmd, "__wrapped__"), f"{cmd.__name__} lacks @with_json_quiet"


def test_with_json_quiet_integration_meso_pre():
    """Meso layer pre commands have @with_json_quiet applied."""
    from deviate.cli.meso import _specify_pre, _tasks_pre

    for cmd in (_specify_pre, _tasks_pre):
        assert hasattr(cmd, "__wrapped__"), f"{cmd.__name__} lacks @with_json_quiet"
