import typer
from .cli import cli

app = typer.Typer()
app.add_typer(cli, name="cli")
