# Copyright (c) Microsoft. All rights reserved.

"""Tiny local WebSocket proxy that injects the Foundry Authorization header.

The browser client (``index.html``) cannot set custom WebSocket headers,
but the Foundry gateway requires ``Authorization: Bearer <token>``. This
proxy bridges that gap for local development, and also serves
``index.html`` on the same port so you can just open the browser to
``http://localhost:8765/``:

    Browser  ──http://localhost:8765/──▶  proxy (serves index.html)
    Browser  ──ws://localhost:8765/invocations_ws──▶  proxy
    proxy    ──wss://<foundry>/...?...&Authorization──▶  Foundry

The token is fetched from ``az account get-access-token`` (resource
``https://ai.azure.com``), refreshed lazily per new browser connection.
Frames are forwarded verbatim in both directions (binary PCM + JSON text).

Usage
-----

    pip install websockets
    az login   # once

    python proxy.py \\
        --foundry https://<account>.services.ai.azure.com/api/projects/<project> \\
        --agent voice-live-foundry-iq-avatar

Then open http://localhost:8765/ in your browser — the page is served
by this proxy and pre-configured to connect to
``ws://localhost:8765/invocations_ws``.

Flags
-----
    --listen HOST:PORT   default 127.0.0.1:8765
    --foundry URL        Foundry project endpoint (https://...)
    --agent NAME         agent name registered in Foundry
    --api-version V      default ``v1``

Security note: this proxy is for **local development only**. It listens on
loopback by default and uses your own ``az`` identity. Do not expose it on
a public network.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import subprocess
import sys
import uuid
from http import HTTPStatus
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

import websockets
from websockets.asyncio.server import serve
from websockets.http11 import Response
from websockets.datastructures import Headers

INDEX_HTML_PATH = pathlib.Path(__file__).with_name("index.html")


def _foundry_url(project_endpoint: str, agent: str, session_id: str, api_version: str) -> str:
    parts = urlsplit(project_endpoint)
    if (
        parts.scheme not in ("https", "wss")
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
    ):
        raise ValueError("Foundry endpoint must use https or wss without user information.")
    _ = parts.port  # Reject malformed ports before requesting a token.
    project = parts.path.rstrip("/").rsplit("/", 1)[-1]
    qs = urlencode({
        "api-version": api_version,
        "agent_session_id": session_id,
    })
    path = (
        f"/api/projects/{quote(project, safe='')}"
        f"/agents/{quote(agent, safe='')}"
        "/endpoint/protocols/invocations_ws"
    )
    return urlunsplit((
        "wss",
        parts.netloc,
        path,
        qs, "",
    ))


def _entra_token(resource: str = "https://ai.azure.com") -> str:
    out = subprocess.run(
        ["az", "account", "get-access-token", "--resource", resource, "-o", "json"],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)["accessToken"]


async def _pump(src, dst, label: str) -> None:
    try:
        async for msg in src:
            await dst.send(msg)
    except websockets.ConnectionClosed:
        pass
    except Exception as exc:  # noqa: BLE001
        print(f"[proxy] {label} error: {exc}", file=sys.stderr)
    finally:
        try:
            await dst.close()
        except Exception:  # noqa: BLE001
            pass


def _http_response(status: HTTPStatus, body: bytes, content_type: str) -> Response:
    headers = Headers([
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
    ])
    return Response(status.value, status.phrase, headers, body)


async def _process_request(connection, request):
    """Serve index.html for plain HTTP GETs; let WebSocket upgrades pass."""
    if "upgrade" in request.headers.get("Connection", "").lower():
        port = connection.local_address[1]
        allowed_origins = {f"http://localhost:{port}", f"http://127.0.0.1:{port}"}
        if port == 80:
            allowed_origins.update({"http://localhost", "http://127.0.0.1"})
        origins = request.headers.get_all("Origin")
        if len(origins) > 1 or (origins and origins[0] not in allowed_origins):
            return _http_response(HTTPStatus.FORBIDDEN, b"origin not allowed", "text/plain")
        return None  # Validate the browser origin before the handler obtains a token.
    path = request.path.split("?", 1)[0]
    if path in ("/", "/index.html"):
        try:
            body = INDEX_HTML_PATH.read_bytes()
        except FileNotFoundError:
            return _http_response(HTTPStatus.NOT_FOUND, b"index.html not found", "text/plain")
        return _http_response(HTTPStatus.OK, body, "text/html; charset=utf-8")
    return _http_response(HTTPStatus.NOT_FOUND, b"not found", "text/plain")


def _make_handler(args):
    async def handler(browser_ws):
        peer = browser_ws.remote_address
        session_id = str(uuid.uuid4())
        url = _foundry_url(args.foundry, args.agent, session_id, args.api_version)
        try:
            token = _entra_token()
        except subprocess.CalledProcessError as exc:
            print(f"[proxy] az token failed: {exc.stderr or exc}", file=sys.stderr)
            await browser_ws.close(code=1011, reason="auth failed")
            return
        headers = {
            "Authorization": f"Bearer {token}",
        }
        print(f"[proxy] {peer} -> {url}")
        try:
            async with websockets.connect(
                url,
                additional_headers=list(headers.items()),
                max_size=4 * 1024 * 1024,
            ) as upstream:
                await asyncio.gather(
                    _pump(browser_ws, upstream, "browser->foundry"),
                    _pump(upstream, browser_ws, "foundry->browser"),
                )
        except Exception as exc:  # noqa: BLE001
            print(f"[proxy] upstream connect failed: {exc}", file=sys.stderr)
            try:
                await browser_ws.close(code=1011, reason="upstream failed")
            except Exception:  # noqa: BLE001
                pass
        print(f"[proxy] {peer} closed")
    return handler


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--listen", default="127.0.0.1:8765",
                   help="HOST:PORT to bind (default 127.0.0.1:8765)")
    p.add_argument("--foundry", required=True,
                   help="Foundry project endpoint, e.g. "
                        "https://<account>.services.ai.azure.com/api/projects/<project>")
    p.add_argument("--agent", required=True, help="Agent name")
    p.add_argument("--api-version", default="v1")
    args = p.parse_args()

    host, _, port = args.listen.partition(":")
    port_i = int(port or "8765")
    try:
        _foundry_url(args.foundry, args.agent, "validation", args.api_version)
    except ValueError as exc:
        p.error(str(exc))

    async def run():
        async with serve(
            _make_handler(args),
            host,
            port_i,
            max_size=4 * 1024 * 1024,
            process_request=_process_request,
        ):
            print(
                f"[proxy] listening on http://{host}:{port_i}/  (ws path: /invocations_ws)"
                f"  ->  {args.foundry} (agent={args.agent})"
            )
            await asyncio.Future()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
