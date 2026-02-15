"""Entry point: delegates to CLI app (one module per mode: interactive, batch, graph, webhook)."""

from src.cli import app
from src.utils.tracing import shutdown_tracing
from rich.traceback import install

if __name__ == "__main__":
    try:
        install(show_locals=False, max_frames=5, word_wrap=True)
        app()
    finally:
        shutdown_tracing()
