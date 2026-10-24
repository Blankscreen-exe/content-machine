"""The MCP server a Claude session talks to: the tools in claude_tools, served over stdio.

Claude Code starts it as a child process (`cm mcp --brand <slug>`, written into the
session's config by claude_session.py), so there is no port and no token, and it works
whether or not the app is running. This module only adapts: the rules are in claude_tools,
and swapping the MCP library means changing this file alone.
"""
from __future__ import annotations

import functools
from collections.abc import Callable

from mcp.server.mcpserver import Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import claude_tools
from .claude_session import SERVER_NAME
from .database import engine, migrate

INSTRUCTIONS = """\
Content Machine's database, for one brand. Use these tools to read and file ideas and
pieces and to report what you did; write drafts with your file tools, in the folder a
piece's tools give. Moving a piece to ready or published, publishing, deleting, and
changing the brand's voice or settings are not here: they are the person's.
"""


def build(brand_slug: str) -> MCPServer:
    tools = claude_tools.Tools(engine, brand_slug)
    server = MCPServer(SERVER_NAME, instructions=INSTRUCTIONS)
    for tool in tools.all():
        server.add_tool(_reporting_refusals(tool))
    server.add_tool(_reporting_refusals(_as_picture(tools.still)), structured_output=False)
    return server


def serve(brand_slug: str) -> None:
    """Bring the database up to date, then answer on stdin and stdout until Claude Code stops."""
    migrate()
    build(brand_slug).run("stdio")


def _reporting_refusals(tool: Callable) -> Callable:
    """Hand a refusal's message to Claude. The library shows Claude the message of a
    ToolError only; anything else arrives as a bare "Error executing tool"."""
    @functools.wraps(tool)       # the library reads the name, parameters and docstring through this
    def call(*args, **kwargs):
        try:
            return tool(*args, **kwargs)
        except claude_tools.Refused as exc:
            raise ToolError(str(exc)) from exc
    return call


def _as_picture(tool: Callable[..., bytes]) -> Callable:
    """PNG bytes as an image Claude can look at."""
    @functools.wraps(tool)
    def call(*args, **kwargs):
        return Image(data=tool(*args, **kwargs), format="png")
    return call
