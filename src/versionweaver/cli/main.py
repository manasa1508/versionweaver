import json
import signal
import threading
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from versionweaver.analyzers.repository import scan_repository
from versionweaver.api.app import app as api_app
from versionweaver.application.outbox import LoggingPublisher, dispatch_outbox
from versionweaver.client import VersionWeaverClient
from versionweaver.config import get_settings
from versionweaver.logging import configure_logging
from versionweaver.persistence.database import SessionLocal, init_database
from versionweaver.schemas import ChangeCreate
from versionweaver.workers.runner import run_forever, run_once

app = typer.Typer(no_args_is_help=True, help="VersionWeaver dependency and model migrations")
project_app = typer.Typer(no_args_is_help=True)
change_app = typer.Typer(no_args_is_help=True)
app.add_typer(project_app, name="project")
app.add_typer(change_app, name="change")


def _print(value: object) -> None:
    typer.echo(json.dumps(value, indent=2, default=str))


def _client() -> VersionWeaverClient:
    settings = get_settings()
    return VersionWeaverClient(settings.server_url, settings.api_token)


@app.command("init-db")
def initialize_database() -> None:
    """Create database tables for a development installation."""
    init_database()
    typer.echo("VersionWeaver database initialized")


@app.command()
def serve(
    host: Annotated[str, typer.Option()] = "0.0.0.0",
    port: Annotated[int, typer.Option(min=1, max=65535)] = 8000,
) -> None:
    """Run the API server."""
    uvicorn.run(api_app, host=host, port=port)


@app.command()
def scan(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, resolve_path=True)],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    project_id: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Scan dependency declarations and model usages."""
    inventory = scan_repository(path)
    if output:
        output.write_text(json.dumps(inventory, indent=2))
    if project_id:
        _client().upload_inventory(project_id, inventory)
    _print(inventory)


@project_app.command("create")
def create_project(
    name: str,
    source_uri: str,
    default_branch: Annotated[str, typer.Option()] = "main",
) -> None:
    """Register a local path or Git repository."""
    _print(
        _client().create_project(
            {"name": name, "source_uri": source_uri, "default_branch": default_branch}
        )
    )


@change_app.command("create")
def create_change(
    project_id: str,
    spec_file: Annotated[Path, typer.Argument(exists=True, dir_okay=False, resolve_path=True)],
    title: Annotated[str, typer.Option()] = "Migration change",
    requested_by: Annotated[str, typer.Option()] = "cli-user",
    idempotency_key: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Create a planned change from a JSON ChangeSpec."""
    spec = json.loads(spec_file.read_text())
    request = ChangeCreate(
        project_id=project_id,
        title=title,
        requested_by=requested_by,
        spec=spec,
    )
    _print(
        _client().create_change(request.model_dump(mode="json"), idempotency_key=idempotency_key)
    )


@change_app.command("approve")
def approve_change(
    change_id: str,
    actor: Annotated[str, typer.Option()] = "cli-approver",
    expected_version: Annotated[int | None, typer.Option()] = None,
) -> None:
    """Approve and queue a planned change."""
    _print(_client().approve_change(change_id, actor, expected_version))


@change_app.command("cancel")
def cancel_change(
    change_id: str,
    reason: Annotated[str, typer.Option()],
    actor: Annotated[str, typer.Option()] = "cli-user",
    expected_version: Annotated[int | None, typer.Option()] = None,
) -> None:
    """Cancel a non-terminal change with optional optimistic concurrency."""
    _print(_client().cancel_change(change_id, actor, reason, expected_version))


@change_app.command("status")
def change_status(change_id: str) -> None:
    """Show current change status."""
    _print(_client().get_change(change_id))


@app.command()
def runner(once: Annotated[bool, typer.Option("--once")] = False) -> None:
    """Run a self-hosted migration runner."""
    settings = get_settings()
    settings.validate_for_startup()
    configure_logging(settings.log_level)
    if once:
        worked = run_once(settings)
        if not worked:
            typer.echo("No queued jobs")
        return
    stop = threading.Event()

    def request_shutdown(signum: int, frame: object) -> None:
        del signum, frame
        stop.set()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)
    run_forever(settings, stop)


@app.command("dispatch-outbox")
def dispatch_events(
    batch_size: Annotated[int, typer.Option(min=1, max=1000)] = 100,
) -> None:
    """Publish one transactional-outbox batch through the development publisher."""
    configure_logging(get_settings().log_level)
    with SessionLocal() as session:
        published, failed = dispatch_outbox(session, LoggingPublisher(), batch_size=batch_size)
    _print({"published": published, "failed": failed})


if __name__ == "__main__":
    app()
