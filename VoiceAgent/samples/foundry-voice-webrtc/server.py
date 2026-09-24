"""Local Foundry voice bridge: WebRTC signaling or PCM audio over WebSocket."""

import asyncio
import base64
import binascii
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit

import aiohttp
from aiohttp import web
from dotenv import load_dotenv

from auth import AuthenticationError, AzureCliTokenProvider, find_azure_cli

ROOT = Path(__file__).resolve().parent
LOGGER = logging.getLogger(__name__)
MAX_FRAME = 256 * 1024
MAX_UPSTREAM_FRAME = 4 * 1024 * 1024
TRANSPORTS = {"websocket", "webrtc"}


@dataclass
class CallState:
    active: bool = False


@dataclass(frozen=True)
class Settings:
    endpoint: str
    agent: str
    api_version: str = "v1"
    features: str = "VoiceAgents=V1Preview"
    ice_servers: tuple = ()

    @property
    def setup_issues(self):
        issues = []
        if not self.endpoint or "YOUR-" in self.endpoint:
            issues.append("Set AZURE_AI_PROJECT_ENDPOINT to your Foundry project endpoint.")
        if not self.agent:
            issues.append("Set AZURE_VOICE_AGENT_NAME to your saved voice agent's name.")
        return issues

    @property
    def configured(self):
        return not self.setup_issues

    def project_url(self):
        parsed = urlsplit(self.endpoint)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment
                or not parsed.path.startswith("/api/projects/")
                or len(parsed.path.rstrip('/').split('/')) != 4
                or not parsed.path.rstrip('/').split('/')[-1]):
            raise ValueError("Use the HTTPS Foundry project endpoint from the project overview.")
        return f"https://{parsed.netloc}{parsed.path.rstrip('/')}"

    def agent_url(self, collection=False):
        path = "/agents" if collection else f"/agents/{quote(self.agent, safe='')}"
        params = {"api-version": self.api_version}
        if collection:
            params["limit"] = 1
        return f"{self.project_url()}{path}?{urlencode(params)}"

    def voice_url(self, transport="webrtc"):
        if transport not in TRANSPORTS:
            raise ValueError("Unsupported transport.")
        project = self.project_url().replace("https://", "wss://", 1)
        params = {"api-version": self.api_version,
                  "agent_session_id": f"web-{uuid.uuid4().hex}", "store": "true"}
        # The default service transport is WebSocket; only WebRTC needs a selector.
        if transport == "webrtc":
            params["transport"] = "webrtc"
        query = urlencode(params)
        return (f"{project}/agents/"
                f"{quote(self.agent, safe='')}/endpoint/protocols/voice?{query}")


def load_settings():
    load_dotenv(ROOT / ".env")
    ice = json.loads(os.getenv("ICE_SERVERS_JSON", '[{"urls":"stun:stun.l.google.com:19302"}]'))
    if not isinstance(ice, list) or any(not isinstance(s, dict) or not s.get("urls") for s in ice):
        raise ValueError("ICE_SERVERS_JSON must be a JSON array of ICE server objects.")
    return Settings(os.getenv("AZURE_AI_PROJECT_ENDPOINT", "").strip().rstrip("/"),
                    os.getenv("AZURE_VOICE_AGENT_NAME", "").strip(),
                    os.getenv("AZURE_API_VERSION", "v1"),
                    os.getenv("FOUNDRY_FEATURES", "VoiceAgents=V1Preview"), tuple(ice))


def allowed_origin(request):
    # Local development only: reject foreign Host / Origin to prevent cross-site use
    # of the developer's Azure credentials (including DNS-rebinding attempts).
    host = urlsplit(f"http://{request.host}").hostname
    if host not in {"localhost", "127.0.0.1", "::1"}:
        return False
    origin = request.headers.get("Origin")
    return origin == f"{request.scheme}://{request.host}"


@web.middleware
async def security_headers(request, handler):
    response = await handler(request)
    response.headers.update({
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer", "Permissions-Policy": "microphone=(self)",
        "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; "
                                   "connect-src 'self'; media-src 'self' blob:; "
                                   "frame-ancestors 'none'; base-uri 'none'",
    })
    return response


async def public_config(request):
    cfg = request.app[SETTINGS]
    return web.json_response({"configured": cfg.configured, "agent": cfg.agent,
                              "iceServers": list(cfg.ice_servers),
                              "authentication": "azure_cli", "azureCliInstalled": bool(find_azure_cli()),
                              "setupIssues": cfg.setup_issues,
                              "transports": ["websocket", "webrtc"], "defaultTransport": "websocket"})


async def asset(request):
    name = request.match_info.get("file", "index.html")
    if name not in {"index.html", "app.js", "style.css", "pcm-audio.mjs", "pcm-capture.js"}:
        raise web.HTTPNotFound()
    return web.FileResponse(ROOT / "public" / name)


def validate_client_frame(raw, started, transport="webrtc"):
    frame = json.loads(raw)
    if not isinstance(frame, dict):
        raise ValueError("Expected an event object.")
    kind = frame.get("type")
    if transport == "websocket":
        if kind != "input_audio_buffer.append" or not isinstance(frame.get("audio"), str):
            raise ValueError("WebSocket mode only accepts PCM audio append events.")
        try:
            audio = base64.b64decode(frame["audio"], validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError("Invalid base64 audio.") from error
        if not audio or len(audio) % 2 or len(audio) > 48000:
            raise ValueError("Audio must be PCM16, at most one second per event.")
        return {"type": kind, "audio": frame["audio"]}
    if transport != "webrtc":
        raise ValueError("Unsupported transport.")
    if not started:
        if kind != "rtc.call.sdp.create" or not isinstance(frame.get("sdp_offer"), str):
            raise ValueError("The first event must contain a WebRTC SDP offer.")
        if not frame["sdp_offer"].startswith("v=0"):
            raise ValueError("Invalid SDP offer.")
        return {"type": kind, "sdp_offer": frame["sdp_offer"]}
    # Keep all agent configuration in Foundry, not client-controlled session updates.
    raise ValueError("This voice-only starter accepts one SDP offer per connection.")


async def forward_browser(browser, upstream, transport):
    started = False
    async for message in browser:
        if message.type == aiohttp.WSMsgType.TEXT:
            frame = validate_client_frame(message.data, started, transport)
            await upstream.send_json(frame)
            started = True
        elif message.type == aiohttp.WSMsgType.BINARY:
            raise ValueError("Send JSON events; binary frames are not supported.")


async def forward_upstream(upstream, browser, transport):
    async for message in upstream:
        if message.type == aiohttp.WSMsgType.TEXT:
            # WebRTC plays RTP; WebSocket mode needs base64 PCM audio deltas.
            frame = json.loads(message.data)
            if transport == "websocket" or frame.get("type") not in {"response.audio.delta", "response.output_audio.delta"}:
                await browser.send_str(message.data)


async def relay(browser, upstream, transport):
    tasks = [asyncio.create_task(forward_browser(browser, upstream, transport)),
             asyncio.create_task(forward_upstream(upstream, browser, transport))]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


class VoiceEndpointError(Exception):
    """A sanitized result of read-only checks after a failed voice upgrade."""


async def diagnose_voice_not_found(client, cfg, headers, transport):
    """Do not guess a new route or create an agent when an upgrade returns 404."""
    fallback = ("Azure returned HTTP 404 for the voice endpoint. The cause could not be verified. "
                "Check the exact project endpoint and saved voice agent name in .env, then restart. "
                "Also confirm voice-agent preview access for this project.")
    try:
        async with asyncio.timeout(12):
            async with client.get(cfg.agent_url(), headers=headers, allow_redirects=False) as response:
                status = response.status
                if status == 200:
                    # Never relay definitions, instructions, headers or arbitrary service errors.
                    raw = await response.content.read(65537)
                    if len(raw) > 65536:
                        return fallback
                    agent = json.loads(raw)
                    latest = (agent.get("versions") or {}).get("latest") or {}
                    kind = (latest.get("definition") or {}).get("kind")
                    if kind and kind != "voice":
                        return ("The configured agent exists, but its latest definition is not a voice agent. "
                                "Set AZURE_VOICE_AGENT_NAME to a saved voice agent in this project, then restart.")
                    if kind == "voice":
                        hint = ("Try WebSocket to check whether only WebRTC is unavailable. "
                                if transport == "webrtc" else "")
                        return ("The configured voice agent exists, but Azure returned HTTP 404 for its "
                                "voice connection endpoint. " + hint +
                                "Check that it has an invokable version and that this project's region/resource "
                                "has the voice-agent preview route enabled. Test the same agent in Foundry.")
                    return ("The configured agent exists, but Azure returned HTTP 404 for its voice endpoint. "
                            "Verify a saved voice-agent version and preview availability in Foundry.")
            if status == 404:
                # A missing agent and a missing project can both produce 404.
                async with client.get(cfg.agent_url(collection=True), headers=headers,
                                      allow_redirects=False) as response:
                    if response.status == 200:
                        return ("The project's agents API is reachable, but the configured agent was not found "
                                "(HTTP 404). Copy the saved voice agent's exact name into "
                                "AZURE_VOICE_AGENT_NAME in .env and restart. Use its name, not a model "
                                "deployment name or an agent ID from the classic Agents API.")
                    if response.status == 404:
                        return ("Both the agent lookup and the project's agents API returned HTTP 404. "
                                "Copy the project endpoint from Foundry's project overview into "
                                "AZURE_AI_PROJECT_ENDPOINT, then restart. If it already matches, ask the "
                                "resource owner to confirm this API/preview is available on the resource.")
            if status in {401, 403}:
                return ("The voice endpoint returned HTTP 404; the follow-up agent lookup was denied "
                        f"(HTTP {status}), so agent existence could not be verified. "
                        "Confirm the agent in Foundry or ask the project owner to check it. "
                        "Invoking an agent and reading its definition can require different permissions.")
    except (aiohttp.ClientError, TimeoutError, ValueError, AttributeError, TypeError):
        pass
    return fallback


@asynccontextmanager
async def connect_voice(client, cfg, headers, transport):
    # Only diagnose a failed handshake; do not make metadata-read access a
    # prerequisite for callers who have invoke-only permissions.
    try:
        upstream = await client.ws_connect(cfg.voice_url(transport), headers=headers,
                                           heartbeat=20, max_msg_size=MAX_UPSTREAM_FRAME)
    except aiohttp.WSServerHandshakeError as error:
        if error.status != 404:
            raise
        raise VoiceEndpointError(await diagnose_voice_not_found(client, cfg, headers, transport)) from None
    async with upstream:
        yield upstream


def describe_connection_error(error):
    """Return actionable diagnostics without exposing URLs, keys or raw exceptions."""
    if isinstance(error, (AuthenticationError, VoiceEndpointError)):
        return str(error)
    if isinstance(error, aiohttp.WSServerHandshakeError):
        if error.status == 401:
            return "Foundry rejected the Azure CLI bearer token (HTTP 401). Run az login for the tenant containing this project and select the correct subscription. Resource API keys are not supported by Agent Service."
        if error.status == 403:
            return "Foundry denied your signed-in account access (HTTP 403). Ask the resource owner to grant you the appropriate Foundry role on this project or agent and check network access policies."
        return f"Azure rejected the WebSocket upgrade (HTTP {error.status}). Check the project endpoint, agent name and selected transport support."
    if isinstance(error, (aiohttp.ClientConnectorCertificateError, aiohttp.ClientConnectorSSLError)):
        return "TLS certificate validation failed. Check trusted certificates and your network proxy; do not disable certificate validation."
    if isinstance(error, aiohttp.ClientConnectorError):
        cause = error.os_error
        if getattr(cause, "errno", None) in {1, 13} or getattr(cause, "winerror", None) in {5, 10013}:
            return "The operating system denied the server's outbound connection to Azure. Run the server outside the restricted environment or allow Python outbound HTTPS to Entra and Foundry. Authentication has not completed."
        if isinstance(error, aiohttp.ClientConnectorDNSError):
            return "Azure hostname lookup failed. Check the project endpoint and DNS/network connection."
        return "The server could not reach Azure over HTTPS. Check the network, proxy and firewall. No Azure authentication response was received."
    if isinstance(error, TimeoutError):
        return "Connecting to Azure timed out. Check outbound HTTPS access, proxy and firewall settings."
    if isinstance(error, ValueError):
        return "Invalid connection configuration or client audio event. Check the project endpoint and selected transport."
    return "The voice connection failed unexpectedly. Check the server log for the error type."


async def bridge(request):
    if not allowed_origin(request):
        raise web.HTTPForbidden(text="Open the page on this local server.")
    transport = request.query.get("transport", "webrtc")
    if transport not in TRANSPORTS:
        raise web.HTTPBadRequest(text="Choose websocket or webrtc.")
    cfg = request.app[SETTINGS]
    if not cfg.configured:
        raise web.HTTPServiceUnavailable(text="Configure .env first.")
    # One active local call prevents accidental duplicate usage.
    if request.app[ACTIVE].active:
        raise web.HTTPTooManyRequests(text="A call is already active.")
    request.app[ACTIVE].active = True
    browser = web.WebSocketResponse(max_msg_size=MAX_FRAME, heartbeat=20)
    try:
        await browser.prepare(request)
        cfg.project_url()  # Validate before acquiring credentials.
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=35)) as client:
            token = await request.app[TOKENS].get_token(client)
            headers = {"Authorization": f"Bearer {token}", "Foundry-Features": cfg.features}
            async with connect_voice(client, cfg, headers, transport) as upstream:
                await relay(browser, upstream, transport)
    except Exception as exc:
        # Never send auth exceptions, headers or tokens to the browser or logs.
        LOGGER.warning("Voice bridge failed (%s)", type(exc).__name__)
        message = describe_connection_error(exc)
        if not browser.closed and browser.prepared:
            await browser.send_json({"type": "bridge.error", "error": {"message": message}})
    finally:
        request.app[ACTIVE].active = False
        if browser.prepared:
            await browser.close()
    return browser


SETTINGS = web.AppKey("settings", Settings)
ACTIVE = web.AppKey("active", CallState)
TOKENS = web.AppKey("tokens", AzureCliTokenProvider)


def create_app(settings=None, token_provider=None):
    app = web.Application(middlewares=[security_headers], client_max_size=MAX_FRAME)
    app[SETTINGS] = settings or load_settings()
    app[TOKENS] = token_provider or AzureCliTokenProvider()
    app[ACTIVE] = CallState()
    app.router.add_get("/api/config", public_config)
    app.router.add_get("/api/voice", bridge)
    app.router.add_get("/", asset)
    app.router.add_get("/{file}", asset)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    web.run_app(app, host="127.0.0.1", port=int(os.getenv("PORT", "8080")))
