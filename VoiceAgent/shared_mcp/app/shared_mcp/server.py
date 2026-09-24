from __future__ import annotations

import contextlib
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .auth import BearerTokenGate
from .elevator_service.pack import register as register_elevator_service
from .finance_handoff.pack import register as register_finance_handoff
from .finance_otp_officer.pack import register as register_finance_otp_officer


logger = logging.getLogger("shared_mcp")
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]

ELEVATOR_SERVICE_PATH = "/mcp/elevator-service"
FINANCE_HANDOFF_PATH = "/mcp/finance-handoff"
FINANCE_OTP_OFFICER_PATH = "/mcp/finance-otp-officer"


@dataclass(frozen=True)
class HostConfig:
    host: str
    port: int
    token: str
    allowed_hosts: tuple[str, ...]

    @classmethod
    def from_environment(
        cls,
        environment: dict[str, str] | None = None,
    ) -> "HostConfig":
        values = os.environ if environment is None else environment
        token = values.get("SHARED_MCP_TOKEN", "").strip()
        if len(token) < 32:
            raise ValueError("SHARED_MCP_TOKEN must contain at least 32 characters")
        try:
            port = int(values.get("PORT", values.get("SHARED_MCP_PORT", "8000")))
        except ValueError as error:
            raise ValueError("PORT must be an integer") from error
        if not 1 <= port <= 65535:
            raise ValueError("PORT must be between 1 and 65535")
        return cls(
            host=values.get("SHARED_MCP_HOST", "0.0.0.0").strip() or "0.0.0.0",
            port=port,
            token=token,
            allowed_hosts=tuple(
                item.strip()
                for item in values.get("SHARED_MCP_ALLOWED_HOSTS", "").split(",")
                if item.strip()
            ),
        )


@dataclass(frozen=True)
class LoadedRoute:
    path: str
    streamable_app: Any
    sse_app: Any
    lifespan_app: Any


class SharedMcpApp:
    def __init__(self, routes: tuple[LoadedRoute, ...]) -> None:
        self._routes = {route.path: route for route in routes}
        self._lifespan_apps = tuple(route.lifespan_app for route in routes)
        self._stack: contextlib.AsyncExitStack | None = None

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] == "lifespan":
            await self._lifespan(receive, send)
            return
        if scope["type"] != "http":
            await self._respond(send, 404, {"error": "not found"})
            return

        request_path = scope.get("path", "") or "/"
        path = request_path.rstrip("/") or "/"
        if path == "/healthz":
            await self._respond(send, 200, {"status": "ok"})
            return

        route = self._routes.get(path)
        relative_path = "/"
        if route is None:
            for candidate in self._routes.values():
                if request_path.startswith(candidate.path + "/"):
                    route = candidate
                    relative_path = request_path[len(candidate.path):]
                    break
        if route is None:
            await self._respond(send, 404, {"error": "not found"})
            return
        headers = dict(scope.get("headers") or [])
        use_legacy_sse = (
            scope.get("method") == "GET"
            and b"mcp-session-id" not in headers
        ) or relative_path != "/"
        app = route.sse_app if use_legacy_sse else route.streamable_app
        root_path = scope.get("root_path", "").rstrip("/") + route.path
        await app(
            {
                **scope,
                "path": relative_path,
                "raw_path": relative_path.encode(),
                "root_path": root_path,
            },
            receive,
            send,
        )

    async def _lifespan(self, receive: Receive, send: Send) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                try:
                    self._stack = contextlib.AsyncExitStack()
                    await self._stack.__aenter__()
                    for app in self._lifespan_apps:
                        await self._stack.enter_async_context(
                            app.router.lifespan_context(app)
                        )
                except Exception as error:
                    await send(
                        {
                            "type": "lifespan.startup.failed",
                            "message": str(error),
                        }
                    )
                    return
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                if self._stack is not None:
                    await self._stack.__aexit__(None, None, None)
                await send({"type": "lifespan.shutdown.complete"})
                return

    @staticmethod
    async def _respond(send: Send, status: int, value: dict[str, str]) -> None:
        body = json.dumps(value, separators=(",", ":")).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body})


def _load_route(
    path: str,
    name: str,
    register: Callable[[FastMCP], None],
    config: HostConfig,
) -> LoadedRoute:
    mcp = FastMCP(name)
    mcp.settings.streamable_http_path = "/"
    mcp.settings.sse_path = "/"
    mcp.settings.message_path = "/messages/"
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=bool(config.allowed_hosts),
        allowed_hosts=list(config.allowed_hosts),
    )
    register(mcp)
    streamable_app = mcp.streamable_http_app()
    return LoadedRoute(
        path=path,
        streamable_app=BearerTokenGate(streamable_app, config.token),
        sse_app=BearerTokenGate(mcp.sse_app(), config.token),
        lifespan_app=streamable_app,
    )


def build_app(config: HostConfig) -> SharedMcpApp:
    return SharedMcpApp(
        (
            _load_route(
                ELEVATOR_SERVICE_PATH,
                "elevator_service_mcp",
                register_elevator_service,
                config,
            ),
            _load_route(
                FINANCE_HANDOFF_PATH,
                "finance_handoff_mcp",
                register_finance_handoff,
                config,
            ),
            _load_route(
                FINANCE_OTP_OFFICER_PATH,
                "finance_otp_officer_mcp",
                register_finance_otp_officer,
                config,
            ),
        )
    )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    config = HostConfig.from_environment()
    logger.info(
        "shared_mcp_start host=%s port=%s routes=%s,%s,%s",
        config.host,
        config.port,
        ELEVATOR_SERVICE_PATH,
        FINANCE_HANDOFF_PATH,
        FINANCE_OTP_OFFICER_PATH,
    )
    uvicorn.run(
        build_app(config),
        host=config.host,
        port=config.port,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
