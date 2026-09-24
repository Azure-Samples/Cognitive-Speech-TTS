from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from .config import ServerConfig
from .server import build_service, register_tools


def register(mcp: FastMCP) -> None:
    secret = os.environ.get(
        "ELEVATOR_MCP_CALL_TOKEN_SECRET",
        os.environ.get("SHARED_MCP_TOKEN", ""),
    )
    register_tools(
        mcp,
        build_service(ServerConfig.from_environment(), secret),
    )
