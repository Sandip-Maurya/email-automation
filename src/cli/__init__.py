"""CLI commands: one module per mode (interactive, batch, graph, webhook)."""

from typer import Typer

from src.cli import batch_mode, graph_mode, interactive_mode, validate_config as validate_config_module, webhook_mode
from src.utils.tracing import init_tracing

init_tracing()

app = Typer(help="Pharmaceutical Email Agentic Network")


def register_commands() -> None:
    """Register all CLI commands on the global app."""
    app.command()(interactive_mode.interactive)
    app.command()(batch_mode.batch)
    app.command()(graph_mode.graph)
    app.command()(webhook_mode.webhook)
    app.command(name="validate-config")(validate_config_module.validate_config)


register_commands()
