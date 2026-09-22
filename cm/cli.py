"""Command line entry point.

`cm serve` runs the web app. The other commands exist so a terminal session working on a
piece can report back — moving a stage or recording a publication — without the web app
having to watch the folder.
"""
from __future__ import annotations

import webbrowser

import typer
import uvicorn
from sqlmodel import Session

from . import choices, crud, scaffold, workspace
from .database import engine, migrate
from .models import Platform, Stage
from .net import lan_ip
from .security import rotate_token, token
from .settings import get_settings

app = typer.Typer(help="content machine: local idea pool and content pipeline", no_args_is_help=True)


@app.command()
def serve(
    lan: bool = typer.Option(False, "--lan", help="also reachable from other devices on this network"),
    port: int = typer.Option(None, help="port to listen on"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="open a browser on start"),
) -> None:
    """Run the web app."""
    settings = get_settings()
    host = "0.0.0.0" if lan else settings.host
    port = port or settings.port

    if not _port_is_free(host, port):
        typer.echo(f"Port {port} is already in use - another copy of cm is probably running.")
        typer.echo(f"Close it, or start this one elsewhere: cm serve --port {port + 1}")
        raise typer.Exit(1)

    shown = lan_ip() if lan else settings.host
    typer.echo(f"content machine: http://{shown}:{port}/?t={token()}")
    if lan:
        typer.echo("reachable on this network - open that address on your phone")
    if open_browser:
        webbrowser.open(f"http://{settings.host}:{port}/?t={token()}")

    uvicorn.run("cm.app:app", host=host, port=port, log_level="warning")


@app.command()
def pieces(brand: str = typer.Option(None, help="limit to one brand slug")) -> None:
    """List pieces and their stages."""
    migrate()
    with Session(engine) as session:
        brand_row = crud.get_brand_by_slug(session, brand) if brand else None
        if brand and not brand_row:
            raise typer.BadParameter(f"no brand with slug {brand!r}")
        for piece in crud.list_pieces(session, brand_id=brand_row.id if brand_row else None):
            due = piece.due_on.isoformat() if piece.due_on else "-"
            typer.echo(f"{piece.id:>4}  {piece.stage.value:<12} {piece.type.name:<14} {due:<12} {piece.title}")


@app.command()
def stage(piece_id: int, stage: str) -> None:
    """Move a piece to a stage: not started, draft, wip, ready, published."""
    migrate()
    try:
        target = Stage(stage)
    except ValueError as exc:
        raise typer.BadParameter(f"stage must be one of: {', '.join(s.value for s in Stage)}") from exc

    with Session(engine) as session:
        piece = crud.get_piece(session, piece_id)
        if not piece:
            raise typer.BadParameter(f"no piece with id {piece_id}")
        crud.update_piece(session, piece, stage=target)
        typer.echo(f"{piece.title}: {target.value}")


@app.command()
def note(piece_id: int, text: str) -> None:
    """Append a note to a piece."""
    migrate()
    with Session(engine) as session:
        piece = crud.get_piece(session, piece_id)
        if not piece:
            raise typer.BadParameter(f"no piece with id {piece_id}")
        joined = f"{piece.notes}\n{text}".strip() if piece.notes else text
        crud.update_piece(session, piece, notes=joined)
        typer.echo("noted")


@app.command()
def published(piece_id: int,
              platform: str = typer.Option(..., help="one of the platforms under Manage"),
              url: str = typer.Option("", help="link to the published post")) -> None:
    """Mark a piece published and record where it went."""
    migrate()
    with Session(engine) as session:
        piece = crud.get_piece(session, piece_id)
        if not piece:
            raise typer.BadParameter(f"no piece with id {piece_id}")
        found = choices.by_name(session, Platform, platform)
        if not found or not found.active:
            known = ", ".join(p.name for p in choices.options(session, Platform)) or "none yet"
            raise typer.BadParameter(f"no platform called {platform!r} (known: {known}). "
                                     "Add it under Manage in the app.")
        crud.record_publication(session, piece, platform_id=found.id, url=url)
        typer.echo(f"{piece.title}: published {url}".strip())


@app.command()
def brief(piece_id: int) -> None:
    """Rewrite brief.md for a piece and print its path."""
    migrate()
    with Session(engine) as session:
        piece = crud.get_piece(session, piece_id)
        if not piece:
            raise typer.BadParameter(f"no piece with id {piece_id}")
        typer.echo(str(workspace.write_brief(session, piece)))


@app.command()
def init(force: bool = typer.Option(False, "--force", help="overwrite the starter files")) -> None:
    """Create the workspace folder, CLAUDE.md and the starter skills."""
    written = scaffold.init_workspace(force=force)
    if not written:
        typer.echo("workspace already set up (use --force to rewrite the starter files)")
    for path in written:
        typer.echo(f"wrote {path}")


@app.command(name="token")
def token_command(rotate: bool = typer.Option(False, "--rotate",
                                              help="replace it; every open tab needs the new link")) -> None:
    """Print the access token, or replace it."""
    typer.echo(rotate_token() if rotate else token())


@app.command()
def where() -> None:
    """Show the workspace paths."""
    settings = get_settings()
    typer.echo(f"workspace: {settings.workspace}")
    typer.echo(f"database:  {settings.db_path}")
    typer.echo(f"content:   {settings.content_dir}")
    typer.echo(f"trash:     {settings.trash_dir}")


def _port_is_free(host: str, port: int) -> bool:
    """Check before uvicorn does, so the failure is a sentence rather than a stack trace."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


if __name__ == "__main__":
    app()
