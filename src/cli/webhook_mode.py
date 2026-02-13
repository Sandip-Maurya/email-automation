"""Webhook mode: run FastAPI listener for Microsoft Graph change notifications."""

import os
import sys

import typer
import uvicorn

from src.config import (
    WEBHOOK_PORT,
    WEBHOOK_URL,
    WEBHOOK_CLIENT_STATE,
    SUBSCRIPTION_EXPIRATION_MINUTES,
)
from src.db import init_db
from src.webhook.server import create_app

from .shared import console, logger


def webhook(
    port: int = typer.Option(WEBHOOK_PORT, "--port", "-p", help="Port for the webhook server"),
    create_subscription: bool = typer.Option(
        False,
        "--create-subscription",
        "-c",
        help="Create a Graph subscription on startup (requires WEBHOOK_URL and WEBHOOK_CLIENT_STATE)",
    ),
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Bind host"),
) -> None:
    """Start the webhook listener; optionally create a Graph subscription for new mail."""
    init_db()
    log = logger.bind(command="webhook", port=port)
    log.info("webhook.start")

    required = ("AZURE_TENANT_ID", "AZURE_CLIENT_ID")
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        console.print(f"[red]Missing environment variables: {', '.join(missing)}[/red]")
        log.warning("webhook.missing_env", missing=missing)
        raise typer.Exit(1)

    subscription_config = None
    if create_subscription:
        if not WEBHOOK_URL or not WEBHOOK_CLIENT_STATE:
            console.print(
                "[red]--create-subscription requires WEBHOOK_URL and WEBHOOK_CLIENT_STATE in .env[/red]"
            )
            log.warning("webhook.create_subscription_missing_config")
            raise typer.Exit(1)
        console.print("[yellow]Ensure your dev tunnel is running and forwarding port %s to this machine.[/yellow]" % port)
        subscription_config = {
            "notification_url": f"{WEBHOOK_URL.rstrip('/')}/webhook/notifications",
            "client_state": WEBHOOK_CLIENT_STATE,
            "expiration_minutes": SUBSCRIPTION_EXPIRATION_MINUTES,
        }
        console.print("[dim]Provider and subscription will be created when the server starts.[/dim]")

    console.print("[dim]Using delegated auth (token cache). Sign in when the server starts if prompted.[/dim]")
    app = create_app(provider=None, subscription_config=subscription_config)

    console.print(f"[green]Starting webhook server on http://{host}:{port}[/green]")
    console.print("[dim]Endpoints: GET/POST /webhook/notifications, GET /health[/dim]")
    if subscription_config:
        console.print("[green]Press Ctrl+C to stop the server.[/green]")
    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            timeout_graceful_shutdown=15,
        )
    except KeyboardInterrupt:
        console.print("\n[dim]Shutting down...[/dim]")
        sys.exit(0)
