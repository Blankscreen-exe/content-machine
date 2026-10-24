"""The tools as Claude Code meets them: `cm mcp` started as a process, spoken to over stdio."""
from __future__ import annotations

import sys
from pathlib import Path

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from sqlmodel import Session, create_engine, select

from cm import crud
from cm.database import configure_connections, migrate
from cm.models import Actor, Event
from helpers import type_id

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(name="workspace")
def workspace_fixture(tmp_path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    migrate(f"sqlite:///{workspace / 'content.db'}")
    engine = configure_connections(create_engine(f"sqlite:///{workspace / 'content.db'}"))
    with Session(engine) as session:
        brand = crud.create_brand(session, "personal", "Example Person")
        crud.create_piece(session, brand_id=brand.id, type_id=type_id(session, "blog"), title="Legacy systems")
    engine.dispose()
    return workspace


def _talk(workspace: Path, calls: list[tuple[str, dict]]) -> tuple[list[str], list]:
    """Start the server as Claude Code would, list its tools, make `calls`; return both."""
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "cm.cli", "mcp", "--brand", "personal"],
        env={"CM_WORKSPACE": str(workspace), "PYTHONPATH": str(REPO)}, cwd=workspace)

    async def conversation():
        async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
            await client.initialize()
            names = [tool.name for tool in (await client.list_tools()).tools]
            return names, [await client.call_tool(name, arguments) for name, arguments in calls]

    return anyio.run(conversation)


def test_claude_code_gets_the_tools_and_a_refusal_it_can_read(workspace):
    names, (moved, refused, dated) = _talk(workspace, [
        ("set_stage", {"piece_id": 1, "stage": "draft"}),
        ("set_stage", {"piece_id": 1, "stage": "published"}),
        ("update_piece", {"piece_id": 1, "due_on": "2026-11-02"}),      # dates arrive as text
    ])

    assert {"brand_context", "create_piece", "set_stage", "add_note", "render_draft", "still"} <= set(names)
    assert not moved.is_error and not dated.is_error
    assert refused.is_error and "Published is mine" in refused.content[0].text

    engine = create_engine(f"sqlite:///{workspace / 'content.db'}")
    with Session(engine) as session:
        piece = crud.get_piece(session, 1)
        assert piece.stage.value == "draft" and piece.due_on.isoformat() == "2026-11-02"
        actors = [event.actor for event in session.exec(select(Event).order_by(Event.id)).all()]
        mode = session.connection().exec_driver_sql("PRAGMA journal_mode").scalar()
    engine.dispose()
    assert mode == "wal"                    # the tools brought the workspace's database up, WAL included
    assert actors == [Actor.me, Actor.claude, Actor.claude]      # created in the app; moved and dated by Claude
