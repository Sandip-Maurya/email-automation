"""Entry point: delegates to CLI app (one module per mode: interactive, batch, graph, webhook)."""

from src.cli import app

if __name__ == "__main__":
    app()
