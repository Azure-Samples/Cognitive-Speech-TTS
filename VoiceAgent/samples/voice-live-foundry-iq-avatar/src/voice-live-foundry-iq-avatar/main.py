# Copyright (c) Microsoft. All rights reserved.

"""Voice Live and Foundry IQ hosted-agent sample."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import struct
import time
from collections import deque
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import quote, urlsplit, urlunsplit

from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from azure.ai.agentserver.invocations import InvocationAgentServerHost
from azure.ai.voicelive.aio import connect as voicelive_connect
from azure.ai.voicelive.models import (
    AssistantMessageItem,
    AudioEchoCancellation,
    AudioInputTranscriptionOptions,
    AudioNoiseReduction,
    AvatarConfig,
    AzureStandardVoice,
    InputAudioFormat,
    InputTextContentPart,
    MCPServer,
    Modality,
    OutputAudioFormat,
    OutputTextContentPart,
    RequestSession,
    ResponseCreateParams,
    ServerEventType,
    ServerVad,
    ToolChoiceLiteral,
    UserMessageItem,
)
from azure.identity.aio import DefaultAzureCredential

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is pinned for normal runs
    def load_dotenv(*_args: Any, **_kwargs: Any) -> bool:
        return False


load_dotenv(override=False)

logger = logging.getLogger("voice-live-foundry-iq-avatar")
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
)

BROWSER_SAMPLE_RATE = 24_000
BROWSER_CHANNELS = 1
SEARCH_SCOPE = "https://search.azure.com/.default"
SEARCH_API_VERSION = "2026-08-01-preview"
DEFAULT_VOICE = "en-US-Ava:DragonHDLatestNeural"
DEFAULT_GREETING = "Hello! I'm your AI knowledge assistant. How can I help you today?"
SEARCH_TOKEN_EXPIRY_MARGIN_SECONDS = 300
DEFAULT_INSTRUCTIONS = (
    "You are a concise voice assistant grounded in the configured knowledge base. "
    "Respond in English by default. Use another language only when the user "
    "explicitly requests it. Apply this to both spoken and text responses. "
    "Always use the knowledge_base_retrieve tool to answer every user question, and "
    "never answer from prior knowledge. Cite the retrieved sources in text responses. "
    "If the knowledge base does not contain the answer, say 'I don't know'."
)


def _environment(environ: Mapping[str, str] | None = None) -> Mapping[str, str]:
    return os.environ if environ is None else environ


def _absolute_url(raw: str, label: str) -> tuple[str, Any]:
    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise EnvironmentError(f"Invalid {label} {raw!r}: expected an absolute http(s) URL.")
    return raw, parts


def _resolve_endpoint(environ: Mapping[str, str] | None = None) -> str:
    """Resolve the public Voice Live account endpoint at call time."""
    env = _environment(environ)
    raw = (
        env.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
        or env.get("AZURE_VOICELIVE_ENDPOINT", "").strip()
    )
    if not raw:
        raise EnvironmentError(
            "Set FOUNDRY_PROJECT_ENDPOINT or AZURE_VOICELIVE_ENDPOINT to an "
            "AI Services account or Foundry project endpoint."
        )
    _, parts = _absolute_url(raw, "Voice Live endpoint")
    return urlunsplit((parts.scheme, parts.netloc, "/", "", ""))


def _resolve_kb_endpoint(environ: Mapping[str, str] | None = None) -> str:
    """Resolve a direct Foundry IQ MCP endpoint at call time."""
    env = _environment(environ)
    configured = env.get("KB_MCP_ENDPOINT", "").strip()
    if configured:
        _absolute_url(configured, "knowledge-base MCP endpoint")
        return configured

    search_endpoint = env.get("AZURE_SEARCH_ENDPOINT", "").strip()
    kb_name = env.get("KNOWLEDGE_BASE_NAME", "").strip()
    if not search_endpoint or not kb_name:
        raise EnvironmentError(
            "Set KB_MCP_ENDPOINT, or set both AZURE_SEARCH_ENDPOINT and "
            "KNOWLEDGE_BASE_NAME."
        )
    _, parts = _absolute_url(search_endpoint, "Azure AI Search endpoint")
    root = urlunsplit((parts.scheme, parts.netloc, "", "", "")).rstrip("/")
    return (
        f"{root}/knowledgebases/{quote(kb_name, safe='')}/mcp"
        f"?api-version={SEARCH_API_VERSION}"
    )


def _build_voice_config(environ: Mapping[str, str] | None = None) -> AzureStandardVoice:
    env = _environment(environ)
    name = env.get("AZURE_VOICELIVE_VOICE", DEFAULT_VOICE).strip() or DEFAULT_VOICE
    return AzureStandardVoice(name=name)


def _greeting_text(environ: Mapping[str, str] | None = None) -> str:
    return _environment(environ).get("AZURE_VOICELIVE_GREETING", DEFAULT_GREETING).strip()


def _avatar_enabled(environ: Mapping[str, str] | None = None) -> bool:
    value = _environment(environ).get("AZURE_VOICELIVE_ENABLE_AVATAR", "false")
    return value.strip().lower() == "true"


def _build_session(search_token: str, environ: Mapping[str, str] | None = None) -> RequestSession:
    env = _environment(environ)
    instructions = env.get("AZURE_VOICELIVE_INSTRUCTIONS", DEFAULT_INSTRUCTIONS).strip()
    session = RequestSession(
        modalities=[Modality.TEXT, Modality.AUDIO],
        instructions=instructions or DEFAULT_INSTRUCTIONS,
        voice=_build_voice_config(env),
        input_audio_format=InputAudioFormat.PCM16,
        output_audio_format=OutputAudioFormat.PCM16,
        input_audio_transcription=AudioInputTranscriptionOptions(model="azure-speech"),
        turn_detection=ServerVad(
            threshold=0.5,
            prefix_padding_ms=300,
            silence_duration_ms=500,
            create_response=False,
            interrupt_response=True,
        ),
        input_audio_echo_cancellation=AudioEchoCancellation(),
        input_audio_noise_reduction=AudioNoiseReduction(
            type="azure_deep_noise_suppression"
        ),
        tools=[
            MCPServer(
                server_label="knowledge_base",
                server_url=_resolve_kb_endpoint(env),
                authorization=search_token,
                allowed_tools=["knowledge_base_retrieve"],
                require_approval="never",
            )
        ],
        tool_choice=ToolChoiceLiteral.AUTO,
    )
    if _avatar_enabled(env):
        session.avatar = AvatarConfig(
            character="lisa",
            style="casual-sitting",
            customized=False,
            output_protocol="websocket",
        )
    return session


def _audio_frame(
    pcm: bytes,
    sample_rate: int = BROWSER_SAMPLE_RATE,
    channels: int = BROWSER_CHANNELS,
) -> bytes:
    """Prefix PCM16 bytes with sample-rate and channel-count uint32 values."""
    return struct.pack("<II", sample_rate, channels) + pcm


def _token_session_seconds(expires_on: int, now: float | None = None) -> float:
    """Bound a session so its static MCP authorization never reaches expiry."""
    current_time = time.time() if now is None else now
    return max(0.0, expires_on - current_time - SEARCH_TOKEN_EXPIRY_MARGIN_SECONDS)


def _response_status_value(status: Any) -> str:
    value = getattr(status, "value", status)
    return str(value).lower() if value else "unknown"


def _response_failure_message(response: Any, status: str) -> str:
    details = getattr(response, "status_details", None)
    error = getattr(details, "error", None)
    if isinstance(error, Mapping):
        message = error.get("message")
    else:
        message = getattr(error, "message", None)
    reason = getattr(details, "reason", None)
    detail = message or reason
    return f"Voice Live response {status}" + (f": {detail}" if detail else ".")


def _response_mcp_item_ids(response: Any) -> set[str]:
    item_ids: set[str] = set()
    for item in getattr(response, "output", None) or []:
        item_type = item.get("type") if isinstance(item, Mapping) else getattr(item, "type", None)
        if _response_status_value(item_type) != "mcp_call":
            continue
        item_id = item.get("id") if isinstance(item, Mapping) else getattr(item, "id", None)
        if item_id:
            item_ids.add(str(item_id))
    return item_ids


@dataclass
class _ResponseRequest:
    kind: str
    content: str | None = None
    item_created: bool = False
    event_id: str | None = None


class _ResponseCoordinator:
    """Serialize manual responses and MCP continuations for one session."""

    def __init__(self, connection: Any, *, tools_ready: bool = True) -> None:
        self._connection = connection
        self._lock = asyncio.Lock()
        self._tools_ready = tools_ready
        self._pending: deque[_ResponseRequest] = deque()
        self._create_in_flight: _ResponseRequest | None = None
        self._active_request: _ResponseRequest | None = None
        self._response_active = False
        self._event_sequence = 0
        self._active_mcp_items: set[str] = set()
        self._terminal_mcp_items: set[str] = set()
        self._finished_mcp_items: set[str] = set()
        self._abandoned_mcp_items: set[str] = set()
        self._mcp_parent_response_done = False
        self._needs_mcp_continuation = False
        self._continuation_queued = False
        self._user_started = False
        self._session_started = False

    @property
    def greeting_active(self) -> bool:
        request = self._active_request or self._create_in_flight
        return request is not None and request.kind == "greeting"

    async def start_session(
        self,
        greeting: str,
        notify_ready: Callable[[bool], Awaitable[None]],
    ) -> None:
        async with self._lock:
            if self._session_started:
                return
            self._session_started = True
            greet = bool(greeting) and not self._user_started
            await notify_ready(greet)
            if greet:
                self._pending.appendleft(_ResponseRequest(kind="greeting", content=greeting))
            self._tools_ready = True
            await self._drain_locked()

    async def user_speech_started(self) -> None:
        async with self._lock:
            self._user_started = True

    async def queue_text(self, content: str) -> None:
        async with self._lock:
            self._user_started = True
            self._pending.append(_ResponseRequest(kind="text", content=content))
            await self._drain_locked()

    async def queue_audio(self) -> None:
        async with self._lock:
            self._user_started = True
            self._pending.append(_ResponseRequest(kind="audio"))
            await self._drain_locked()

    async def response_created(self) -> None:
        async with self._lock:
            self._response_active = True
            self._active_request = self._create_in_flight
            self._mcp_parent_response_done = False
            if (
                self._active_request is not None
                and self._active_request.kind == "mcp_continuation"
            ):
                self._needs_mcp_continuation = False
                self._continuation_queued = False

    async def mcp_started(self, item_id: str) -> None:
        async with self._lock:
            if (
                item_id in self._finished_mcp_items
                or item_id in self._abandoned_mcp_items
            ):
                return
            self._active_mcp_items.add(item_id)
            self._needs_mcp_continuation = True

    async def mcp_finished(self, item_id: str) -> None:
        async with self._lock:
            if item_id in self._abandoned_mcp_items:
                return
            if item_id in self._finished_mcp_items:
                return
            self._active_mcp_items.add(item_id)
            self._terminal_mcp_items.add(item_id)
            self._needs_mcp_continuation = True
            await self._finish_ready_mcp_items_locked()

    async def response_done(
        self,
        status: Any = "completed",
        mcp_item_ids: set[str] | None = None,
    ) -> bool:
        """Return whether this is a successful final completion for the browser."""
        normalized_status = _response_status_value(status)
        async with self._lock:
            completed_request = self._active_request
            self._response_active = False
            self._active_request = None
            if self._create_in_flight is completed_request:
                self._create_in_flight = None

            if normalized_status != "completed":
                self._abandoned_mcp_items.update(self._active_mcp_items)
                self._abandoned_mcp_items.update(mcp_item_ids or ())
                self._active_mcp_items.clear()
                self._terminal_mcp_items.clear()
                self._finished_mcp_items.clear()
                self._mcp_parent_response_done = False
                self._needs_mcp_continuation = False
                self._continuation_queued = False
                self._pending = deque(
                    request
                    for request in self._pending
                    if request.kind != "mcp_continuation"
                )
                await self._drain_locked()
                return False

            discovered_item_ids = mcp_item_ids or set()
            for item_id in discovered_item_ids:
                if (
                    item_id not in self._finished_mcp_items
                    and item_id not in self._abandoned_mcp_items
                ):
                    self._active_mcp_items.add(item_id)
                    self._needs_mcp_continuation = True

            has_mcp_chain = bool(
                discovered_item_ids
                or self._active_mcp_items
                or self._terminal_mcp_items
                or self._needs_mcp_continuation
            )
            if has_mcp_chain:
                self._mcp_parent_response_done = True
                await self._finish_ready_mcp_items_locked()

            hide_intermediate = bool(
                self._active_mcp_items
                or self._needs_mcp_continuation
                or self._continuation_queued
                or (
                    self._create_in_flight is not None
                    and self._create_in_flight.kind == "mcp_continuation"
                )
            )
            await self._drain_locked()
            if not hide_intermediate:
                self._terminal_mcp_items.clear()
                self._finished_mcp_items.clear()
                self._mcp_parent_response_done = False
            return not hide_intermediate

    async def handle_error(self, error: Any) -> bool:
        """Requeue a create rejected because another response won the race."""
        event_id = getattr(error, "event_id", None)
        code = getattr(error, "code", None)
        async with self._lock:
            request = self._create_in_flight
            if request is None:
                return False
            if not event_id or request.event_id != event_id:
                return False

            self._create_in_flight = None
            if self._active_request is request:
                self._active_request = None
            request.event_id = None

            if request.kind == "greeting":
                if code == "conversation_already_has_active_response":
                    self._response_active = True
                await self._drain_locked()
                return False

            if code == "conversation_already_has_active_response":
                self._response_active = True
                if request.kind == "mcp_continuation":
                    self._needs_mcp_continuation = True
                    self._continuation_queued = True
                    self._pending.appendleft(request)
                else:
                    self._pending.appendleft(request)
                return True

            if request.kind == "mcp_continuation":
                self._needs_mcp_continuation = False
                self._continuation_queued = False
            await self._drain_locked()
            return False

    async def _finish_ready_mcp_items_locked(self) -> None:
        if not self._mcp_parent_response_done:
            return
        if self._terminal_mcp_items:
            self._active_mcp_items.difference_update(self._terminal_mcp_items)
            self._finished_mcp_items.update(self._terminal_mcp_items)
            self._terminal_mcp_items.clear()
            self._queue_mcp_continuation_locked()
            await self._drain_locked()

    def _queue_mcp_continuation_locked(self) -> None:
        if (
            not self._needs_mcp_continuation
            or self._active_mcp_items
            or self._continuation_queued
        ):
            return
        self._pending.appendleft(_ResponseRequest(kind="mcp_continuation"))
        self._continuation_queued = True

    async def _drain_locked(self) -> None:
        if self._response_active or self._create_in_flight or not self._pending:
            return
        request = self._pending[0]
        if not self._tools_ready and request.kind in {"text", "audio", "greeting"}:
            return
        if self._active_mcp_items:
            return
        if request.kind != "mcp_continuation" and self._needs_mcp_continuation:
            return

        self._pending.popleft()
        self._event_sequence += 1
        request.event_id = f"voice-live-response-{self._event_sequence}"
        self._create_in_flight = request
        try:
            options: dict[str, Any] = {}
            if request.kind == "greeting":
                options["response"] = ResponseCreateParams(
                    pre_generated_assistant_message=AssistantMessageItem(
                        content=[OutputTextContentPart(text=request.content or "")]
                    ),
                    tool_choice="none",
                )
            elif request.content is not None and not request.item_created:
                await self._connection.conversation.item.create(
                    item=UserMessageItem(
                        content=[InputTextContentPart(text=request.content)]
                    )
                )
                request.item_created = True
            await self._connection.response.create(event_id=request.event_id, **options)
            logger.debug("Response requested: kind=%s event_id=%s", request.kind, request.event_id)
        except Exception:
            self._create_in_flight = None
            request.event_id = None
            self._pending.appendleft(request)
            raise


async def _safe_send_json(websocket: WebSocket, payload: dict[str, Any]) -> bool:
    if websocket.application_state == WebSocketState.DISCONNECTED:
        return False
    try:
        await websocket.send_json(payload)
        return True
    except Exception:  # noqa: BLE001 - the peer can disappear between checks
        return False


async def _safe_send_bytes(websocket: WebSocket, data: bytes) -> bool:
    if websocket.application_state == WebSocketState.DISCONNECTED:
        return False
    try:
        await websocket.send_bytes(data)
        return True
    except Exception:  # noqa: BLE001 - the peer can disappear between checks
        return False


async def _send_json_or_disconnect(
    websocket: WebSocket,
    payload: dict[str, Any],
) -> None:
    if not await _safe_send_json(websocket, payload):
        raise WebSocketDisconnect(code=1006)


async def _send_bytes_or_disconnect(websocket: WebSocket, data: bytes) -> None:
    if not await _safe_send_bytes(websocket, data):
        raise WebSocketDisconnect(code=1006)


async def _expire_search_authorization(websocket: WebSocket, delay: float) -> None:
    """Close before the MCP bearer token expires so reconnecting gets a new token."""
    await asyncio.sleep(delay)
    await _safe_send_json(
        websocket,
        {
            "type": "reauth_required",
            "message": "The Search authorization is expiring. Reconnect to continue.",
        },
    )
    if websocket.application_state != WebSocketState.DISCONNECTED:
        await websocket.close(code=1012, reason="Search authorization expiring; reconnect")


async def _browser_to_voicelive(
    websocket: WebSocket,
    connection: Any,
    responses: _ResponseCoordinator,
) -> None:
    """Forward browser PCM and serialized text turns to Voice Live."""
    while True:
        message = await websocket.receive()
        if message.get("type") == "websocket.disconnect":
            return

        data: Optional[bytes] = message.get("bytes")
        if data:
            await connection.input_audio_buffer.append(
                audio=base64.b64encode(data).decode("ascii")
            )
            continue

        text = message.get("text")
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if payload.get("type") != "text":
            logger.debug("Ignored browser event: %r", payload)
            continue
        content = str(payload.get("content", "")).strip()
        if not content:
            continue
        await responses.queue_text(content)


_MCP_EVENTS = {
    ServerEventType.MCP_LIST_TOOLS_IN_PROGRESS: ("list_tools", "in_progress"),
    ServerEventType.MCP_LIST_TOOLS_COMPLETED: ("list_tools", "completed"),
    ServerEventType.MCP_LIST_TOOLS_FAILED: ("list_tools", "failed"),
    ServerEventType.RESPONSE_MCP_CALL_IN_PROGRESS: ("call", "in_progress"),
    ServerEventType.RESPONSE_MCP_CALL_COMPLETED: ("call", "completed"),
    ServerEventType.RESPONSE_MCP_CALL_FAILED: ("call", "failed"),
}


async def _voicelive_to_browser(
    websocket: WebSocket,
    connection: Any,
    responses: _ResponseCoordinator,
    *,
    avatar_enabled: bool = False,
    greeting: str = "",
) -> None:
    """Forward the small browser protocol from Voice Live events."""
    session_id: str | None = None
    tools_ready = False

    async def notify_ready(greeting_pending: bool) -> None:
        await _send_json_or_disconnect(
            websocket,
            {
                "type": "session_started",
                "session_id": session_id,
                "avatar_enabled": avatar_enabled,
                "greeting_pending": greeting_pending,
            },
        )

    async for event in connection:
        event_type = event.type

        if event_type == ServerEventType.SESSION_UPDATED:
            session_id = event.session.id
            if tools_ready:
                await responses.start_session(greeting, notify_ready)
        elif event_type == ServerEventType.RESPONSE_CREATED:
            await responses.response_created()
        elif event_type == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED:
            await responses.user_speech_started()
            await _send_json_or_disconnect(websocket, {"type": "user_speech_started"})
        elif event_type == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STOPPED:
            await _send_json_or_disconnect(websocket, {"type": "user_speech_stopped"})
        elif event_type == ServerEventType.INPUT_AUDIO_BUFFER_COMMITTED:
            await responses.queue_audio()
        elif event_type == ServerEventType.RESPONSE_AUDIO_DELTA:
            pcm = event.delta or b""
            if pcm and not avatar_enabled:
                await _send_bytes_or_disconnect(websocket, _audio_frame(pcm))
        elif event_type == ServerEventType.RESPONSE_VIDEO_DELTA:
            delta = event.delta or ""
            if isinstance(delta, bytes):
                delta = base64.b64encode(delta).decode("ascii")
            if avatar_enabled and delta:
                await _send_json_or_disconnect(
                    websocket,
                    {"type": "video_data", "delta": delta, "codec": event.codec},
                )
        elif event_type == ServerEventType.RESPONSE_AUDIO_TRANSCRIPT_DELTA:
            delta = getattr(event, "delta", "") or ""
            if delta:
                await _send_json_or_disconnect(
                    websocket,
                    {"type": "bot_text", "delta": delta, "final": False},
                )
        elif event_type == ServerEventType.RESPONSE_AUDIO_TRANSCRIPT_DONE:
            await _send_json_or_disconnect(
                websocket,
                {
                    "type": "bot_text",
                    "delta": "",
                    "final": True,
                    "text": getattr(event, "transcript", "") or "",
                },
            )
        elif (
            event_type
            == ServerEventType.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED
        ):
            await _send_json_or_disconnect(
                websocket,
                {
                    "type": "transcription",
                    "text": getattr(event, "transcript", "") or "",
                    "final": True,
                },
            )
        elif event_type in _MCP_EVENTS:
            operation, status = _MCP_EVENTS[event_type]
            item_id = getattr(event, "item_id", None)
            await _send_json_or_disconnect(
                websocket,
                {
                    "type": "mcp_status",
                    "operation": operation,
                    "status": status,
                    "item_id": item_id,
                },
            )
            if operation == "list_tools" and status == "completed":
                tools_ready = True
                if session_id:
                    await responses.start_session(greeting, notify_ready)
            elif operation == "call" and item_id:
                if status == "in_progress":
                    await responses.mcp_started(item_id)
                else:
                    await responses.mcp_finished(item_id)
        elif event_type == ServerEventType.RESPONSE_DONE:
            response = getattr(event, "response", None)
            response_status = _response_status_value(
                getattr(response, "status", None)
            )
            mcp_item_ids = _response_mcp_item_ids(response)
            logger.debug(
                "Response done: status=%s mcp_item_ids=%s",
                response_status,
                sorted(mcp_item_ids),
            )
            greeting_completion = responses.greeting_active
            final_completion = await responses.response_done(
                response_status,
                mcp_item_ids,
            )
            if greeting_completion:
                await _send_json_or_disconnect(
                    websocket,
                    {"type": "response_done", "kind": "greeting", "status": response_status},
                )
            elif final_completion:
                await _send_json_or_disconnect(websocket, {"type": "response_done"})
            if response_status not in {"completed", "cancelled"}:
                await _send_json_or_disconnect(
                    websocket,
                    {
                        "type": "error",
                        "message": _response_failure_message(
                            response,
                            response_status,
                        ),
                        "code": f"response_{response_status}",
                    },
                )
        elif event_type == ServerEventType.ERROR:
            error = getattr(event, "error", None)
            if not await responses.handle_error(error):
                await _send_json_or_disconnect(
                    websocket,
                    {
                        "type": "error",
                        "message": getattr(error, "message", str(error)),
                        "code": getattr(error, "code", None),
                    },
                )
        else:
            logger.debug("Voice Live event: %s", event_type)


app = InvocationAgentServerHost()


@app.ws_handler
async def handle_ws(websocket: WebSocket) -> None:
    """Bridge one browser WebSocket to one public Azure Voice Live session."""
    credential = DefaultAzureCredential()
    try:
        search_access_token = await credential.get_token(SEARCH_SCOPE)
        endpoint = _resolve_endpoint()
        model = os.environ.get("AZURE_VOICELIVE_MODEL", "gpt-realtime-1.5").strip()
        async with voicelive_connect(
            endpoint=endpoint,
            credential=credential,
            model=model or "gpt-realtime-1.5",
        ) as connection:
            session = _build_session(search_access_token.token)
            await connection.session.update(session=session)
            avatar_enabled = session.avatar is not None
            responses = _ResponseCoordinator(connection, tools_ready=False)
            tasks = {
                asyncio.create_task(
                    _browser_to_voicelive(websocket, connection, responses),
                    name="browser-to-voice-live",
                ),
                asyncio.create_task(
                    _voicelive_to_browser(
                        websocket, connection, responses,
                        avatar_enabled=avatar_enabled, greeting=_greeting_text(),
                    ),
                    name="voice-live-to-browser",
                ),
                asyncio.create_task(
                    _expire_search_authorization(
                        websocket,
                        _token_session_seconds(search_access_token.expires_on),
                    ),
                    name="search-authorization-expiry",
                ),
            }
            try:
                done, _ = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in done:
                    if task.cancelled():
                        continue
                    error = task.exception()
                    if error and not isinstance(error, WebSocketDisconnect):
                        raise error
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
    except WebSocketDisconnect:
        return
    except Exception as error:  # noqa: BLE001 - report connection/config failures
        logger.exception("WebSocket bridge failed")
        await _safe_send_json(
            websocket,
            {"type": "error", "message": str(error), "code": None},
        )
    finally:
        await credential.close()


if __name__ == "__main__":
    app.run()
