# Copyright (c) Microsoft. All rights reserved.
"""Standalone, local-only Voice Agent portal.

The React studio and service-shaped REST/WebSocket bridge are ported from the
upstream demo. See UPSTREAM.json for the exact source and CHANGELOG.md for the
public-repository adaptations. Run `python demo_server.py --help` or see README.md.
"""
from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import os
import urllib.parse
import uuid
from pathlib import Path

import requests
import websockets
from aiohttp import WSMsgType, web
from dotenv import load_dotenv

# Read only this portal's ignored .env, never an ancestor or the sibling samples.
load_dotenv(Path(__file__).with_name(".env"), override=False)

try:
    from .session_log import SessionRecorder, list_sessions, read_events, read_session
except ImportError:
    from session_log import SessionRecorder, list_sessions, read_events, read_session

try:
    from .common import (
        AZURE_VOICES,
        CASCADED_MODELS,
        DEFAULT_AZURE_VOICE,
        FOUNDRY_FEATURES,
        INPUT_TRANSCRIPTION_MODEL,
        MODELS,
        OPENAI_VOICES,
        REALTIME_MODELS,
        AgentsConfig,
        build_voice_config,
        list_byom_deployments,
        validate_project_endpoint,
    )
    from .foundry_trace import build_foundry_trace_url
except ImportError:
    from common import (
        AZURE_VOICES,
        CASCADED_MODELS,
        DEFAULT_AZURE_VOICE,
        FOUNDRY_FEATURES,
        INPUT_TRANSCRIPTION_MODEL,
        MODELS,
        OPENAI_VOICES,
        REALTIME_MODELS,
        AgentsConfig,
        build_voice_config,
        list_byom_deployments,
        validate_project_endpoint,
    )
    from foundry_trace import build_foundry_trace_url

STATIC_DIR = Path(__file__).parent / "static"

# Header the Agents service reads for the connect-time per-session override.
VOICE_OVERRIDE_HEADER = "x-ms-voice-session-override"
STRUCTURED_INPUT_QUERY_PARAMETER = "structured_input"
STRUCTURED_INPUT_HEADER = "x-ms-voice-structured-inputs"
MAX_STRUCTURED_INPUT_BYTES = 32 * 1024
REDACTED_QUERY_VALUE = "<redacted>"
_SENSITIVE_QUERY_KEYS = frozenset({
    STRUCTURED_INPUT_QUERY_PARAMETER, "authorization", "access_token", "token",
    "api_key", "api-key", "key", "sig", "password", "client_secret",
})


class ProjectWebSocketConnect(websockets.connect):
    """Never carry the developer's bearer token across a WebSocket redirect."""

    def process_redirect(self, exc: Exception) -> Exception:
        # websockets 15 exposes this hook; the supported dependency is bounded
        # below 16 and an actual redirect handshake is covered by integration tests.
        return exc

DEFAULT_CONFIG_KEY = web.AppKey("voice_demo_default_config", AgentsConfig)
# None disables recording; the demo still runs, it just leaves nothing behind.
SESSION_LOG_ROOT = web.AppKey("voice_demo_session_log_root", object)
LIVE_SOCKETS_KEY = web.AppKey("voice_portal_live_sockets", set)

async def _request_config(request: web.Request) -> AgentsConfig:
    cfg = request.app[DEFAULT_CONFIG_KEY]
    requested = (request.query.get("backend") or "").strip()
    if requested and requested != cfg.backend:
        raise web.HTTPBadRequest(text="This portal only uses its configured Azure Foundry project.")
    return cfg


_ASSET_FILENAMES = (
    "bundle.js", "bundle.css", "styles.css", "pcm-capture-worklet.js",
    "webrtc-bundle.js", "webrtc-bundle.css",
    "THIRD_PARTY_NOTICES.txt",
)


def _asset_version() -> str:
    """A token that changes whenever a served asset changes."""
    stamps = []
    for filename in _ASSET_FILENAMES:
        path = STATIC_DIR / filename
        stamps.append(str(int(path.stat().st_mtime)) if path.exists() else "0")
    return "-".join(stamps)


async def index(request: web.Request) -> web.Response:
    await _request_config(request)
    version = _asset_version()
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    for filename in _ASSET_FILENAMES:
        html = html.replace(f"/static/demo/{filename}", f"/static/demo/{filename}?v={version}")
    return web.Response(text=html, content_type="text/html")


async def webrtc_index(request: web.Request) -> web.Response:
    """Serve the standalone WebRTC experience for the configured Foundry project."""
    await _request_config(request)
    return web.FileResponse(STATIC_DIR / "webrtc.html")


def _redact_sensitive_query_values(path_qs: str) -> str:
    """Redact customer-provided query values before writing a request URL to demo logs."""
    parsed = urllib.parse.urlsplit(path_qs)
    if not parsed.query:
        return path_qs
    query = [
        (
            key,
            REDACTED_QUERY_VALUE
            if key.lower() in _SENSITIVE_QUERY_KEYS
            else value,
        )
        for key, value in urllib.parse.parse_qsl(
            parsed.query,
            keep_blank_values=True,
        )
    ]
    return urllib.parse.urlunsplit((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        urllib.parse.urlencode(query),
        parsed.fragment,
    ))


def _redact_sensitive_query_mapping(query) -> dict[str, str]:
    """Return recorder-safe query metadata without the structured-input JSON."""
    return {
        key: (
            REDACTED_QUERY_VALUE
            if key.lower() in _SENSITIVE_QUERY_KEYS
            else value
        )
        for key, value in query.items()
    }


def _log_api(request: web.Request, cfg: AgentsConfig) -> str:
    """Log (server console) the Agents service API the portal is about to proxy. The portal routes
    mirror the service path templates AND the browser now sends the real query string, so the logged
    line is the exact service request line (method + path + query). Returns the path for callers."""
    api_path = _redact_sensitive_query_values(request.path_qs)
    print(f"[api:{cfg.backend}] -> {request.method} {api_path}")
    return api_path


# Only service-contract headers cross the local proxy. Never forward browser
# cookies, caller authorization, proxy-routing headers, or upstream cookies/CORS.
_SERVICE_REQUEST_HEADERS = frozenset({
    "accept", "content-type", "foundry-features", VOICE_OVERRIDE_HEADER, STRUCTURED_INPUT_HEADER,
})
_SERVICE_RESPONSE_HEADERS = frozenset({
    "content-type", "content-disposition", "retry-after", "x-ms-request-id",
})
_SERVICE_GET_ROUTES = (
    "/agents",
    "/agents/{agent}",
    "/agents/{agent}/versions/{version}",
    "/agents/{agent}/endpoint/protocols/voice/conversations",
    "/agents/{agent}/endpoint/protocols/voice/conversations/{conversation}",
    "/agents/{agent}/endpoint/protocols/voice/conversations/{conversation}/items",
    "/agents/{agent}/endpoint/protocols/voice/conversations/{conversation}/items/{item}",
    "/agents/{agent}/endpoint/protocols/voice/conversations/{conversation}/responses",
    "/agents/{agent}/endpoint/protocols/voice/conversations/{conversation}/responses/{response}",
    "/agents/{agent}/endpoint/protocols/voice/conversations/{conversation}/responses/{response}/items",
    "/agents/{agent}/endpoint/protocols/voice/conversations/{conversation}/audio",
    "/agents/{agent}/endpoint/protocols/voice/conversations/{conversation}/audio/content",
    "/agents/{agent}/endpoint/protocols/voice/conversations/{conversation}/items/{item}/audio",
    "/agents/{agent}/endpoint/protocols/voice/conversations/{conversation}/items/{item}/audio/content",
)


def _forward_to_service(method: str, url: str, params, headers, body):
    """Blocking pass-through call to the Agents service (run off the event loop)."""
    return requests.request(method, url, params=params, headers=headers,
                            data=body if body else None, timeout=(10, 120), allow_redirects=False)


async def service_proxy(request: web.Request) -> web.StreamResponse:
    """Keep the service path/body contract; inject credentials for the configured Foundry project."""
    cfg = await _request_config(request)
    _log_api(request, cfg)

    url = f"{cfg.agents_base}{request.rel_url.raw_path}"
    params = [(k, v) for k, v in request.rel_url.query.items() if k != "backend"]
    headers = {k: v for k, v in request.headers.items() if k.lower() in _SERVICE_REQUEST_HEADERS}
    if not any(key.lower() == "foundry-features" for key in headers):
        headers["Foundry-Features"] = FOUNDRY_FEATURES
    body = await request.read()

    try:
        headers.update(await asyncio.to_thread(cfg.auth_headers))
        resp = await asyncio.to_thread(_forward_to_service, request.method, url, params, headers, body)
    except Exception as exc:
        # Authentication exceptions can contain credential details; do not echo them.
        print(f"[proxy] {type(exc).__name__}; check Azure sign-in, project access and connectivity.")
        return web.json_response({
            "error": "Cannot reach the configured Azure project. Check az login, preview access, and the endpoint.",
        }, status=502)
    if 300 <= resp.status_code < 400:
        return web.json_response({"error": "Upstream redirects are not followed by this credentialed proxy."}, status=502)

    out_headers = {k: v for k, v in resp.headers.items() if k.lower() in _SERVICE_RESPONSE_HEADERS}
    return web.Response(status=resp.status_code, body=resp.content, headers=out_headers)


def _session_log_root(request: web.Request) -> Path | None:
    return request.app.get(SESSION_LOG_ROOT)


async def demo_sessions(request: web.Request) -> web.Response:
    """Recorded demo sessions, newest first. `?q=` matches any id the session is known by."""
    root = _session_log_root(request)
    if root is None:
        return web.json_response({"available": False, "reason": "session recording is disabled",
                                  "sessions": []})
    try:
        limit = max(1, min(int(request.query.get("limit", 50)), 500))
    except ValueError:
        limit = 50
    sessions = list_sessions(root, limit=limit, query=(request.query.get("q") or "").strip())
    return web.json_response({"available": True, "root": str(root), "sessions": sessions})


async def demo_session_detail(request: web.Request) -> web.Response:
    root = _session_log_root(request)
    if root is None:
        raise web.HTTPNotFound(text="session recording is disabled")
    found = read_session(root, request.match_info["run_id"])
    if found is None:
        raise web.HTTPNotFound(text="no such recorded session")
    return web.json_response(found)


async def demo_session_events(request: web.Request) -> web.Response:
    root = _session_log_root(request)
    if root is None:
        raise web.HTTPNotFound(text="session recording is disabled")
    try:
        limit = max(1, min(int(request.query.get("limit", 2000)), 20000))
    except ValueError:
        limit = 2000
    events = read_events(root, request.match_info["run_id"], limit=limit)
    if events is None:
        raise web.HTTPNotFound(text="no such recorded session")
    return web.json_response({"run_id": request.match_info["run_id"], "events": events})


async def mcp_probe(request: web.Request) -> web.Response:
    # No server-side arbitrary URL probing or retrieval of connection secrets.
    return web.json_response({"error": "MCP probing is not included in this local public sample. Test tools in a live session."}, status=501)


def _mcp_auth_presets(cfg: AgentsConfig) -> list:
    presets = []
    connection = os.getenv("AZURE_VOICE_AGENTS_MCP_CONNECTION_ID", "").strip()
    if connection:
        presets.append({
            "value": "project-connection", "label": "Your configured project connection",
            "mode": "connection", "server_label": os.getenv("AZURE_VOICE_AGENTS_MCP_SERVER_LABEL", "mcp"),
            "project_connection_id": connection,
        })
    iq_url = os.getenv("AZURE_VOICE_AGENTS_FOUNDRY_IQ_URL", "").strip()
    iq_connection = os.getenv("AZURE_VOICE_AGENTS_FOUNDRY_IQ_CONNECTION_ID", "").strip()
    if iq_url and iq_connection:
        presets.append({
            "value": "foundry-iq", "label": "Your configured Foundry IQ knowledge base",
            "mode": "foundry_iq", "server_label": "foundry-iq",
            "server_url": iq_url, "project_connection_id": iq_connection,
        })
    return presets


async def config(request: web.Request) -> web.Response:
    """Selectable models/voices + defaults for the UI."""
    cfg = await _request_config(request)
    deployed = list_byom_deployments(cfg)
    return web.json_response({
        "models": list(dict.fromkeys([cfg.voice_model, *MODELS])),
        "realtimeModels": REALTIME_MODELS,
        "cascadedModels": CASCADED_MODELS,
        # BYOM (self_deployed) deployment names — distinct from the managed model names above; used when
        # inferenceMode is "deployment" so the demo sends a real, reachable customer deployment.
        "byomRealtimeModels": [item["deployment"] for item in deployed["realtime"]],
        "byomCascadedModels": [item["deployment"] for item in deployed["cascaded"]],
        "openaiVoices": OPENAI_VOICES,
        "azureVoices": AZURE_VOICES,
        "defaultModel": cfg.voice_model,
        "defaultVoice": cfg.voice,
        "defaultAzureVoice": cfg.voice if "-" in cfg.voice else DEFAULT_AZURE_VOICE,
        # Voice inference modes: managed model, BYOM deployment, or an existing
        # same-project hosted agent referenced through target_agent.
        "inferenceModes": [
            {"value": "deployment", "label": "BYOM — your Foundry deployment"},
            {"value": "model", "label": "Direct — Voice Live-hosted model"},
            {"value": "hosted_agent", "label": "Hosted agent"},
        ],
        "defaultInferenceMode": "model",
        # Only presets explicitly supplied by the developer.
        "mcpAuthPresets": _mcp_auth_presets(cfg),
        # Saving real conversation/audio content is opt-in.
        "defaultStore": False,
        "defaultToolbox": {
            "name": os.environ.get("AZURE_VOICE_AGENTS_TOOLBOX_NAME", ""),
            "version": os.environ.get("AZURE_VOICE_AGENTS_TOOLBOX_VERSION", ""),
        },
        "subagentCapabilityOverrides": {},
        # Which backend the demo server is talking to (informational; surfaced in the UI header).
        "backend": cfg.backend,
        "backends": [cfg.backend],
        "host": cfg.host,
        "project": f"{cfg.account}@{cfg.project}",
        "traceEnabled": bool(cfg.subscription and cfg.resource_group),
        "mcpProbeEnabled": False,
        "notice": (
            "Azure Foundry project — requests use your server-side identity and may incur charges. "
            "Preview feature availability depends on your project. Created agents are retained."
        ),
        # The service contract bits the browser needs so its requests match the service exactly: the
        # `api-version` query param and the `Foundry-Features` header go on normal fetch calls. The backend
        # supplies the feature header for native media requests. INPUT_TRANSCRIPTION_MODEL feeds audio.input.
        "apiVersion": cfg.api_version,
        "foundryFeatures": FOUNDRY_FEATURES,
        "inputTranscriptionModel": INPUT_TRANSCRIPTION_MODEL,
    })


async def deployments(request: web.Request) -> web.Response:
    """Return user-supplied BYOM deployment names without accessing ARM."""
    cfg = await _request_config(request)
    return web.json_response(list_byom_deployments(cfg))


async def foundry_trace(request: web.Request) -> web.StreamResponse:
    """Redirect to the selected agent's trace view in Microsoft Foundry."""

    agent_name = (request.query.get("agent") or "").strip()
    if not agent_name:
        raise web.HTTPBadRequest(text="agent is required")
    cfg = await _request_config(request)
    if not cfg.subscription or not cfg.resource_group:
        raise web.HTTPBadRequest(
            text="Trace links require AZURE_SUBSCRIPTION_ID and AZURE_RESOURCE_GROUP."
        )
    try:
        uuid.UUID(cfg.subscription)
    except ValueError as exc:
        raise web.HTTPBadRequest(text="AZURE_SUBSCRIPTION_ID must be a UUID.") from exc
    raise web.HTTPFound(
        location=build_foundry_trace_url(
            subscription_id=cfg.subscription,
            resource_group=cfg.resource_group,
            account_name=cfg.account,
            project_name=cfg.project,
            agent_name=agent_name,
        )
    )


def _voice_override_header(voice: str) -> str:
    """Use the same flat voice/voice_type fields as the public agent definition."""
    descriptor = build_voice_config(voice)
    override = {"audio": {"output": {"voice": descriptor["name"], "voice_type": descriptor["type"]}}}
    return json.dumps(override)


def _structured_input_header(raw: str | None) -> str | None:
    """Normalize browser JSON for an HTTP header without raw newlines or non-ASCII bytes."""
    if not raw or not raw.strip():
        return None
    if len(raw.encode("utf-8")) > MAX_STRUCTURED_INPUT_BYTES:
        raise ValueError("Structured input must not exceed 32 KiB.")
    try:
        values = json.loads(raw)
        if not isinstance(values, dict):
            raise ValueError
        value = json.dumps(values, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    except (ValueError, RecursionError) as exc:
        raise ValueError("Structured input must be a valid JSON object.") from exc
    if len(value) > MAX_STRUCTURED_INPUT_BYTES:
        raise ValueError("Structured input must not exceed 32 KiB when encoded for transport.")
    return value


def build_upstream_ws_headers(cfg: AgentsConfig, query) -> dict[str, str]:
    """Translate browser-only query overrides into the service's supported upgrade headers."""
    structured_input = _structured_input_header(query.get(STRUCTURED_INPUT_QUERY_PARAMETER))
    headers = cfg.ws_headers()
    voice_override = (query.get("voiceOverride") or "").strip()
    if voice_override:
        headers[VOICE_OVERRIDE_HEADER] = _voice_override_header(voice_override)
    if structured_input is not None:
        headers[STRUCTURED_INPUT_HEADER] = structured_input
    return headers


def build_upstream_ws_url(cfg: AgentsConfig, path: str, query) -> tuple[str, str]:
    """Build the upstream voice WS URL, defaulting api-version + agent_session_id.

    Voice/structured-input overrides use headers. The deployed Foundry WS endpoint rejects the
    structured_input query, while the supported legacy header renders the same values successfully.
    All other parameters (store, transport, version overrides, etc.) pass through unchanged.
    ``query`` is any mapping with ``.items()`` (e.g. ``request.rel_url.query``).
    Returns ``(url, agent_session_id)``."""
    header_params = {"voiceOverride", STRUCTURED_INPUT_QUERY_PARAMETER, "backend"}
    q = {k: v for k, v in query.items() if k not in header_params}
    q.setdefault("api-version", cfg.api_version)
    q.setdefault("agent_session_id", f"web-{uuid.uuid4().hex[:8]}")
    url = f"{cfg.ws_agents_base}{path}?{urllib.parse.urlencode(q)}"
    return url, q["agent_session_id"]


async def bridge(request: web.Request) -> web.WebSocketResponse:
    """Step 2: bridge the browser WebSocket to the chosen agent's protocols/voice endpoint."""
    cfg = await _request_config(request)
    _log_api(request, cfg)
    try:
        _structured_input_header(request.query.get(STRUCTURED_INPUT_QUERY_PARAMETER))
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    agent_name = request.match_info.get("agent")
    # Browser WebSockets cannot supply custom headers. Validate and translate overrides before
    # accepting the browser upgrade, so malformed input never opens an upstream connection.
    voice_override = (request.query.get("voiceOverride") or "").strip()
    try:
        headers = await asyncio.to_thread(build_upstream_ws_headers, cfg, request.query)
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    except Exception as exc:
        print(f"[bridge] authentication failed: {type(exc).__name__}")
        raise web.HTTPBadGateway(text="Azure authentication failed. Check az login and project access.") from None

    browser_ws = web.WebSocketResponse(max_msg_size=16 * 1024 * 1024)
    await browser_ws.prepare(request)
    request.app[LIVE_SOCKETS_KEY].add(browser_ws)

    if not agent_name:
        await browser_ws.send_json({"type": "error", "error": {"message": "missing agent path segment; create an agent first"}})
        await browser_ws.close()
        return browser_ws

    # Keep voiceOverride and structured_input out of the public upstream URL; their values are
    # carried in headers instead. The remaining service query parameters keep their native shape.
    url, session_id = build_upstream_ws_url(cfg, request.rel_url.raw_path, request.rel_url.query)
    print(f"[bridge] browser connected; upstream {url.split('?')[0]} "
          f"(agent={agent_name}, voiceOverride={voice_override or '(none)'}, session={session_id})")

    recorder = None
    log_root = request.app.get(SESSION_LOG_ROOT)
    if log_root:
        try:
            recorder = SessionRecorder(
                log_root,
                web_id=session_id,
                agent=agent_name,
                backend=cfg.backend,
                upstream=url.split("?")[0],
                voice_override=voice_override,
                query=_redact_sensitive_query_mapping({
                    k: v
                    for k, v in request.rel_url.query.items()
                    if k != "voiceOverride"
                }),
            )
            print(f"[bridge] recording -> {recorder.dir}")
        except Exception as exc:  # noqa: BLE001 - a session must run even if it cannot be recorded
            print(f"[bridge] recorder unavailable: {type(exc).__name__}: {exc}")

    bridge_error = ""
    upstream_close_code = 1000
    upstream_close_reason = ""
    try:
        # open_timeout must be generous: a BYOM (self_deployed) connect makes the Agents service resolve
        # the customer's cognitive resource + mint a model-auth token before it accepts the upstream WS
        # upgrade, which is markedly slower than the managed path. The websockets default (10s) is too short
        # and shows up as "timed out during opening handshake". Also relax ping timeouts so a brief upstream
        # stall doesn't drop an otherwise-healthy voice session.
        connect_kwargs = {
            "max_size": 16 * 1024 * 1024,
            "open_timeout": 60,
            "ping_interval": 20,
            "ping_timeout": 60,
        }
        async with ProjectWebSocketConnect(url, additional_headers=headers, **connect_kwargs) as upstream:
            async def browser_to_upstream():
                async for msg in browser_ws:
                    if msg.type in (WSMsgType.TEXT, WSMsgType.BINARY):
                        if recorder:
                            recorder.record("up", msg.data)
                        await upstream.send(msg.data)
                    elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.ERROR):
                        break

            async def upstream_to_browser():
                nonlocal upstream_close_code, upstream_close_reason
                try:
                    async for msg in upstream:
                        if recorder:
                            recorder.record("down", msg)
                        if isinstance(msg, (bytes, bytearray)):
                            await browser_ws.send_bytes(msg)
                        else:
                            await browser_ws.send_str(msg)
                finally:
                    if upstream.close_code is not None:
                        upstream_close_code = int(upstream.close_code)
                    upstream_close_reason = upstream.close_reason or ""

            t1 = asyncio.create_task(browser_to_upstream())
            t2 = asyncio.create_task(upstream_to_browser())
            try:
                done, _ = await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
            finally:
                for task in (t1, t2):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(t1, t2, return_exceptions=True)
    except Exception as exc:  # noqa: BLE001 - surface bridge errors to the page
        bridge_error = type(exc).__name__
        print(f"[bridge] error: {bridge_error}")
        if not browser_ws.closed:
            await browser_ws.send_json({
                "type": "error",
                "error": {"message": "Voice connection failed. Check Azure project access, agent settings, and network connectivity."},
            })
        upstream_close_code = 1011
    finally:
        if not browser_ws.closed:
            await browser_ws.close(
                code=upstream_close_code if upstream_close_code not in (1005, 1006, 1015) else 1011,
                # This service-defined reason controls successful completion and
                # draining queued audio in the browser. Preserve it, not arbitrary
                # upstream error text that might include sensitive details.
                message=(
                    b"Conversation ended by agent"
                    if upstream_close_reason == "Conversation ended by agent"
                    else b"Voice session closed"
                ),
            )
        if recorder:
            recorder.close(bridge_error)
        request.app[LIVE_SOCKETS_KEY].discard(browser_ws)
        print("[bridge] closed")
    return browser_ws


@web.middleware
async def local_boundary(request: web.Request, handler):
    """Protect the developer's identity from cross-site requests and DNS rebinding.

    This is a single-user local sample, not authentication for remote deployment.
    Only loopback listeners and same-origin browser requests are supported.
    """
    try:
        host = urllib.parse.urlsplit(f"http://{request.host}")
        if host.hostname not in {"127.0.0.1", "::1", "localhost"} or host.username or host.path:
            raise ValueError
        if request.remote and not ipaddress.ip_address(request.remote).is_loopback:
            raise ValueError
    except ValueError:
        return web.json_response({"error": "This portal only accepts localhost requests."}, status=403)
    origin = request.headers.get("Origin")
    if origin is not None and origin != f"{request.scheme}://{request.host}":
        return web.json_response({"error": "Cross-origin requests are not allowed."}, status=403)
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        return web.json_response({"error": "Cross-site requests are not allowed."}, status=403)
    for value in request.match_info.values():
        if value in {".", ".."} or "/" in value or "\\" in value:
            return web.json_response({"error": "Invalid path component."}, status=400)
    if request.method == "POST" and request.content_type != "application/json":
        return web.json_response({"error": "POST requests require application/json."}, status=415)
    try:
        return await handler(request)
    except web.HTTPException as exc:
        if exc.status < 400:
            raise
        return web.json_response({"error": exc.text or exc.reason}, status=exc.status)


async def security_headers(request: web.Request, response: web.StreamResponse) -> None:
    response.headers.update({
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "no-store",
        "Content-Security-Policy": (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "media-src 'self' blob:; worker-src 'self' blob:; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        ),
    })


async def health(request: web.Request) -> web.Response:
    cfg = request.app[DEFAULT_CONFIG_KEY]
    return web.json_response({"status": "ok", "project": cfg.project})


async def on_shutdown(app: web.Application) -> None:
    for socket in tuple(app[LIVE_SOCKETS_KEY]):
        await socket.close(code=1001, message=b"Portal stopping")


async def on_cleanup(app: web.Application) -> None:
    # Created Azure agents are NEVER deleted automatically.
    await asyncio.to_thread(app[DEFAULT_CONFIG_KEY].close)


def build_app(args) -> web.Application:
    cfg = AgentsConfig.from_endpoint(args.project_endpoint)
    if args.model:
        cfg.voice_model = args.model
    if args.voice:
        cfg.voice = args.voice
    app = web.Application(middlewares=[local_boundary], client_max_size=2 * 1024 * 1024)
    app[DEFAULT_CONFIG_KEY] = cfg
    app[LIVE_SOCKETS_KEY] = set()
    root = Path(__file__).parent / "session-logs" if args.record_sessions else None
    if root is not None:
        root.mkdir(parents=True, exist_ok=True)
    app[SESSION_LOG_ROOT] = root
    for path in ("/", "/demo", "/demo/"):
        app.router.add_get(path, index)
    for path in ("/webrtc", "/webrtc/", "/demo/webrtc", "/demo/webrtc/"):
        app.router.add_get(path, webrtc_index)
    app.router.add_get("/healthz", health)
    app.router.add_get("/config", config)
    app.router.add_get("/deployments", deployments)
    app.router.add_get("/foundry-trace", foundry_trace)
    app.router.add_post("/api/mcp/probe", mcp_probe)
    app.router.add_get("/api/demo/sessions", demo_sessions)
    app.router.add_get("/api/demo/sessions/{run_id}", demo_session_detail)
    app.router.add_get("/api/demo/sessions/{run_id}/events", demo_session_events)
    for route in _SERVICE_GET_ROUTES:
        app.router.add_get(route, service_proxy)
    for route in ("/agents:generate", "/agents/{agent}/versions"):
        app.router.add_post(route, service_proxy)
    app.router.add_get("/agents/{agent}/endpoint/protocols/voice", bridge)
    app.router.add_static("/static/demo/", STATIC_DIR, show_index=False, follow_symlinks=False)
    app.on_response_prepare.append(security_headers)
    app.on_shutdown.append(on_shutdown)
    app.on_cleanup.append(on_cleanup)
    return app


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Local Voice Agent portal for your Azure Foundry project",
        allow_abbrev=False,  # Do not interpret the removed --mode as --model.
    )
    parser.add_argument("--project-endpoint", default=os.getenv("AZURE_VOICE_AGENTS_ENDPOINT", ""),
                        help="Your HTTPS Azure Foundry project endpoint; also read from AZURE_VOICE_AGENTS_ENDPOINT.")
    parser.add_argument("--port", type=int, default=int(os.getenv("DEMO_PORT", "9527")))
    parser.add_argument("--bind", choices=("127.0.0.1", "::1", "localhost"), default="127.0.0.1",
                        help="Loopback only. Remote hosting requires a separate authentication/security design.")
    parser.add_argument("--model", default=None, help="Default managed voice model.")
    parser.add_argument("--voice", default=None, help="Default voice name.")
    parser.add_argument("--record-sessions", action="store_true",
                        help="Opt in to local voice-session event logs (may contain transcripts/tool data).")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    try:
        args.project_endpoint = validate_project_endpoint(args.project_endpoint)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def main() -> None:
    args = parse_args()
    if any(not (STATIC_DIR / name).is_file() for name in _ASSET_FILENAMES):
        raise SystemExit(
            "Missing browser assets or third-party notices. Restore the shipped static files; "
            "to rebuild JavaScript/CSS, run `npm ci` then `npm run build:all` in portal/web."
        )
    try:
        app = build_app(args)
    except ValueError as exc:
        raise SystemExit(f"Configuration error: {exc}") from None
    cfg = app[DEFAULT_CONFIG_KEY]
    print(f"Project  : {cfg.host}")
    print("Azure calls use your identity and may incur charges. Agents are retained on shutdown.")
    if args.record_sessions:
        print("Local event recording enabled; session-logs may contain conversation/tool data. Do not publish them.")
    host = f"[{args.bind}]" if ":" in args.bind else args.bind
    print(f"Open     : http://{host}:{args.port}  (Ctrl+C to stop)")
    # Default access logs would disclose raw structured input query parameters.
    web.run_app(app, host=args.bind, port=args.port, print=None, access_log=None)


if __name__ == "__main__":
    main()
