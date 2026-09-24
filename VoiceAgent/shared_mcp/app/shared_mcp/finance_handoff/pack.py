"""Finance tool pack for the va-mcp host.

The host owns transport, auth and deployment; this module owns nothing but the
wiring from this project's configuration to its tools. Same registration the local
server uses, so the func and mcp transports can never drift apart.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .config import ServerConfig
from .server import build_service, register_tools


def register(mcp: FastMCP) -> None:
    config = ServerConfig.from_environment()
    register_tools(mcp, build_service(config), config)
