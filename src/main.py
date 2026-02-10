"""Entry point: delegates to CLI app (one module per mode: interactive, batch, graph, webhook)."""

from src.cli import app
from src.utils.tracing import shutdown_tracing

if __name__ == "__main__":
    try:
        app()
    finally:
        shutdown_tracing()
