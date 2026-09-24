from __future__ import annotations

import secrets
from typing import Any, Awaitable, Callable


Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


class BearerTokenGate:
    """Authenticate every HTTP operation used by Streamable HTTP."""

    def __init__(self, app: Any, token: str) -> None:
        self._app = app
        self._expected = b"Bear" + b"er " + token.encode("utf-8")

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Receive,
        send: Send,
    ) -> None:
        if scope.get("type") == "http":
            headers = dict(scope.get("headers") or [])
            supplied = headers.get(b"authorization", b"")
            if not secrets.compare_digest(supplied, self._expected):
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b'{"error":"unauthorized"}',
                    }
                )
                return
        await self._app(scope, receive, send)
