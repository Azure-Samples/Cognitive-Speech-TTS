from __future__ import annotations

import asyncio
import struct
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import main


def test_resolve_voice_live_project_endpoint_to_account_root() -> None:
    endpoint = main._resolve_endpoint(
        {
            "FOUNDRY_PROJECT_ENDPOINT": (
                "https://example.services.ai.azure.com/api/projects/demo"
            )
        }
    )

    assert endpoint == "https://example.services.ai.azure.com/"


def test_resolve_knowledge_base_endpoint() -> None:
    endpoint = main._resolve_kb_endpoint(
        {
            "AZURE_SEARCH_ENDPOINT": "https://example.search.windows.net/",
            "KNOWLEDGE_BASE_NAME": "night knowledge",
        }
    )

    assert endpoint == (
        "https://example.search.windows.net/knowledgebases/night%20knowledge/mcp"
        "?api-version=2026-08-01-preview"
    )


def test_standard_voice_is_default() -> None:
    voice = main._build_voice_config({})

    assert voice.as_dict() == {
        "type": "azure-standard",
        "name": main.DEFAULT_VOICE,
    }


@pytest.mark.parametrize("name,expected", [
    ("en-US-JennyNeural", "en-US-JennyNeural"),
    ("  en-US-JennyNeural  ", "en-US-JennyNeural"),
    ("  ", main.DEFAULT_VOICE),
])
def test_standard_voice_override(name, expected) -> None:
    voice = main._build_voice_config({"AZURE_VOICELIVE_VOICE": name})

    assert voice.as_dict() == {"type": "azure-standard", "name": expected}


def test_session_uses_knowledge_base_retrieve_and_standard_voice() -> None:
    session = main._build_session(
        "search-token",
        {"KB_MCP_ENDPOINT": "https://example.search.windows.net/knowledgebases/demo/mcp"},
    ).as_dict()

    assert "avatar" not in session
    assert session["voice"] == {"type": "azure-standard", "name": main.DEFAULT_VOICE}
    assert session["modalities"] == ["text", "audio"]
    assert session["tools"] == [
        {
            "type": "mcp",
            "server_label": "knowledge_base",
            "server_url": "https://example.search.windows.net/knowledgebases/demo/mcp",
            "authorization": "search-token",
            "allowed_tools": ["knowledge_base_retrieve"],
            "require_approval": "never",
        }
    ]
    assert session["turn_detection"]["create_response"] is False
    assert session["turn_detection"]["interrupt_response"] is True


@pytest.mark.parametrize("instructions", [None, "", "  "])
def test_default_instructions_use_english_and_keep_knowledge_grounding(instructions) -> None:
    env = {"KB_MCP_ENDPOINT": "https://example.search.windows.net/knowledgebases/demo/mcp"}
    if instructions is not None:
        env["AZURE_VOICELIVE_INSTRUCTIONS"] = instructions
    session = main._build_session("token", env).as_dict()
    assert session["instructions"] == main.DEFAULT_INSTRUCTIONS
    assert "Respond in English by default." in session["instructions"]
    assert "only when the user explicitly requests it" in session["instructions"]
    assert "both spoken and text responses" in session["instructions"]
    assert "Always use the knowledge_base_retrieve tool" in session["instructions"]
    assert "say 'I don't know'" in session["instructions"]


def test_custom_instructions_remain_an_explicit_override() -> None:
    session = main._build_session("token", {
        "KB_MCP_ENDPOINT": "https://example.search.windows.net/knowledgebases/demo/mcp",
        "AZURE_VOICELIVE_INSTRUCTIONS": "  Answer in French using the knowledge base.  ",
    }).as_dict()
    assert session["instructions"] == "Answer in French using the knowledge base."


@pytest.mark.parametrize("value,enabled", [("true", True), (" TRUE ", True), ("false", False), ("", False)])
def test_avatar_is_explicit_opt_in_without_audit_audio(value, enabled) -> None:
    session = main._build_session("token", {
        "KB_MCP_ENDPOINT": "https://example.search.windows.net/knowledgebases/demo/mcp",
        "AZURE_VOICELIVE_ENABLE_AVATAR": value,
    }).as_dict()

    assert session["modalities"] == ["text", "audio"]
    if enabled:
        assert session["avatar"] == {
            "character": "lisa", "style": "casual-sitting",
            "customized": False, "output_protocol": "websocket",
        }
    else:
        assert "avatar" not in session


@pytest.mark.parametrize("env,expected", [
    ({}, main.DEFAULT_GREETING),
    ({"AZURE_VOICELIVE_GREETING": "  Welcome!  "}, "Welcome!"),
    ({"AZURE_VOICELIVE_GREETING": ""}, ""),
    ({"AZURE_VOICELIVE_GREETING": "  "}, ""),
])
def test_greeting_configuration_preserves_explicit_disable(env, expected) -> None:
    assert main._greeting_text(env) == expected


def test_audio_frame_has_little_endian_header() -> None:
    frame = main._audio_frame(b"\x01\x02", sample_rate=24_000, channels=1)

    assert struct.unpack("<II", frame[:8]) == (24_000, 1)
    assert frame[8:] == b"\x01\x02"


def test_token_session_ends_before_expiry() -> None:
    assert main._token_session_seconds(10_000, now=9_000) == 700
    assert main._token_session_seconds(10_000, now=9_800) == 0


class _RecordingResponse:
    def __init__(self) -> None:
        self.event_ids: list[str | None] = []
        self.parameters: list[dict | None] = []

    @property
    def create_count(self) -> int:
        return len(self.event_ids)

    async def create(self, *, event_id: str | None = None, response=None) -> None:
        self.event_ids.append(event_id)
        self.parameters.append(response.as_dict() if response is not None else None)


class _RecordingConversationItems:
    def __init__(self) -> None:
        self.items = []

    async def create(self, *, item) -> None:
        self.items.append(item)


class _EventConnection:
    def __init__(self, events=()) -> None:
        self.events = events
        self.response = _RecordingResponse()
        self.conversation = SimpleNamespace(item=_RecordingConversationItems())

    def __aiter__(self):
        async def iterator():
            for event in self.events:
                yield event

        return iterator()


class _RecordingWebSocket:
    def __init__(self) -> None:
        self.application_state = main.WebSocketState.CONNECTED
        self.messages: list[dict] = []
        self.closed: tuple[int, str] | None = None

    async def send_json(self, payload: dict) -> None:
        self.messages.append(payload)

    async def close(self, code: int, reason: str) -> None:
        self.closed = (code, reason)
        self.application_state = main.WebSocketState.DISCONNECTED


def _event(event_type, item_id: str | None = None, **values):
    if event_type == main.ServerEventType.RESPONSE_DONE and "response" not in values:
        values["response"] = SimpleNamespace(
            status="completed",
            status_details=None,
        )
    return SimpleNamespace(type=event_type, item_id=item_id, **values)


def _mcp_response_done(*item_ids: str):
    return _event(
        main.ServerEventType.RESPONSE_DONE,
        response=SimpleNamespace(
            status="completed",
            status_details=None,
            output=[
                SimpleNamespace(type="mcp_call", id=item_id)
                for item_id in item_ids
            ],
        ),
    )


def _mcp_output_done(item_id: str):
    return _event(
        main.ServerEventType.RESPONSE_OUTPUT_ITEM_DONE,
        item=SimpleNamespace(type="mcp_call", id=item_id),
    )


def _run_service_events(connection: _EventConnection) -> _RecordingWebSocket:
    websocket = _RecordingWebSocket()
    responses = main._ResponseCoordinator(connection)
    asyncio.run(main._voicelive_to_browser(websocket, connection, responses))
    return websocket


def test_session_started_waits_for_mcp_tool_discovery() -> None:
    connection = _EventConnection(
        [
            _event(
                main.ServerEventType.SESSION_UPDATED,
                session=SimpleNamespace(id="session-1"),
            ),
            _event(main.ServerEventType.MCP_LIST_TOOLS_IN_PROGRESS, "list-1"),
            _event(main.ServerEventType.MCP_LIST_TOOLS_COMPLETED, "list-1"),
        ]
    )

    websocket = _run_service_events(connection)

    assert [message["type"] for message in websocket.messages] == [
        "mcp_status",
        "mcp_status",
        "session_started",
    ]
    assert websocket.messages[-1]["session_id"] == "session-1"


def test_early_text_turn_drains_after_session_and_tools_are_ready() -> None:
    async def scenario():
        connection = _EventConnection(
            [
                _event(
                    main.ServerEventType.SESSION_UPDATED,
                    session=SimpleNamespace(id="session-1"),
                ),
                _event(main.ServerEventType.MCP_LIST_TOOLS_COMPLETED, "list-1"),
                _event(main.ServerEventType.RESPONSE_CREATED),
                _event(main.ServerEventType.RESPONSE_DONE),
            ]
        )
        websocket = _RecordingWebSocket()
        responses = main._ResponseCoordinator(connection, tools_ready=False)
        await responses.queue_text("question")
        await main._voicelive_to_browser(websocket, connection, responses)
        return connection, websocket

    connection, websocket = asyncio.run(scenario())

    assert connection.response.event_ids == ["voice-live-response-1"]
    assert connection.conversation.item.items[0].as_dict()["content"][0]["text"] == "question"
    assert [message["type"] for message in websocket.messages] == [
        "mcp_status",
        "session_started",
        "response_done",
    ]


def test_mcp_continuation_waits_for_all_calls_and_hides_intermediate_done() -> None:
    connection = _EventConnection(
        [
            _event(main.ServerEventType.RESPONSE_CREATED),
            _mcp_response_done("call-1", "call-2"),
            _event(main.ServerEventType.RESPONSE_MCP_CALL_IN_PROGRESS, "call-1"),
            _event(main.ServerEventType.RESPONSE_MCP_CALL_IN_PROGRESS, "call-2"),
            _event(main.ServerEventType.RESPONSE_MCP_CALL_COMPLETED, "call-1"),
            _mcp_output_done("call-1"),
            _event(main.ServerEventType.RESPONSE_MCP_CALL_COMPLETED, "call-2"),
            _mcp_output_done("call-2"),
            _event(main.ServerEventType.RESPONSE_CREATED),
            _event(main.ServerEventType.RESPONSE_DONE),
        ]
    )

    websocket = _run_service_events(connection)

    assert connection.response.event_ids == ["voice-live-response-1"]
    assert [message["type"] for message in websocket.messages].count("response_done") == 1


def test_response_done_with_mcp_output_waits_for_late_terminal_event() -> None:
    connection = _EventConnection(
        [
            _event(main.ServerEventType.RESPONSE_CREATED),
            _event(
                main.ServerEventType.RESPONSE_DONE,
                response=SimpleNamespace(
                    status="completed",
                    status_details=None,
                    output=[SimpleNamespace(type="mcp_call", id="call-1")],
                ),
            ),
            _event(main.ServerEventType.RESPONSE_MCP_CALL_IN_PROGRESS, "call-1"),
            _event(main.ServerEventType.RESPONSE_MCP_CALL_COMPLETED, "call-1"),
            _mcp_output_done("call-1"),
            _event(main.ServerEventType.RESPONSE_CREATED),
            _event(main.ServerEventType.RESPONSE_DONE),
        ]
    )

    websocket = _run_service_events(connection)

    assert connection.response.event_ids == ["voice-live-response-1"]
    assert [message["type"] for message in websocket.messages].count("response_done") == 1


def test_duplicate_mcp_completion_creates_only_one_continuation() -> None:
    connection = _EventConnection(
        [
            _event(main.ServerEventType.RESPONSE_CREATED),
            _mcp_response_done("call-1"),
            _event(main.ServerEventType.RESPONSE_MCP_CALL_IN_PROGRESS, "call-1"),
            _event(main.ServerEventType.RESPONSE_MCP_CALL_COMPLETED, "call-1"),
            _event(main.ServerEventType.RESPONSE_MCP_CALL_COMPLETED, "call-1"),
            _mcp_output_done("call-1"),
            _event(main.ServerEventType.RESPONSE_CREATED),
            _event(main.ServerEventType.RESPONSE_DONE),
        ]
    )

    websocket = _run_service_events(connection)

    assert connection.response.create_count == 1
    assert [message["type"] for message in websocket.messages].count("response_done") == 1


@pytest.mark.parametrize(
    ("terminal_event", "output_events"),
    [
        (
            main.ServerEventType.RESPONSE_MCP_CALL_COMPLETED,
            [_mcp_output_done("call-1")],
        ),
        (main.ServerEventType.RESPONSE_MCP_CALL_FAILED, []),
    ],
)
def test_mcp_terminal_event_without_start_still_creates_continuation(
    terminal_event,
    output_events,
) -> None:
    connection = _EventConnection(
        [
            _event(main.ServerEventType.RESPONSE_CREATED),
            _mcp_response_done("call-1"),
            _event(terminal_event, "call-1"),
            *output_events,
            _event(main.ServerEventType.RESPONSE_CREATED),
            _event(main.ServerEventType.RESPONSE_DONE),
        ]
    )

    websocket = _run_service_events(connection)

    assert connection.response.create_count == 1
    assert [message["type"] for message in websocket.messages].count("response_done") == 1


def test_async_active_response_error_requeues_mcp_continuation() -> None:
    conflict = SimpleNamespace(
        code="conversation_already_has_active_response",
        event_id="voice-live-response-1",
        message="A response is already active.",
    )
    connection = _EventConnection(
        [
            _event(main.ServerEventType.RESPONSE_CREATED),
            _mcp_response_done("call-1"),
            _event(main.ServerEventType.RESPONSE_MCP_CALL_IN_PROGRESS, "call-1"),
            _event(main.ServerEventType.RESPONSE_MCP_CALL_COMPLETED, "call-1"),
            _mcp_output_done("call-1"),
            _event(main.ServerEventType.ERROR, error=conflict),
            _event(main.ServerEventType.RESPONSE_DONE),
            _event(main.ServerEventType.RESPONSE_CREATED),
            _event(main.ServerEventType.RESPONSE_DONE),
        ]
    )

    websocket = _run_service_events(connection)

    assert connection.response.event_ids == [
        "voice-live-response-1",
        "voice-live-response-2",
    ]
    assert not [message for message in websocket.messages if message["type"] == "error"]
    assert [message["type"] for message in websocket.messages].count("response_done") == 1


@pytest.mark.parametrize("terminal_first", [False, True])
def test_mcp_continuation_does_not_require_output_item_done(terminal_first) -> None:
    async def scenario():
        connection = _EventConnection()
        responses = main._ResponseCoordinator(connection)
        await responses.queue_text("question")
        await responses.response_created()
        if terminal_first:
            await responses.mcp_finished("call-1")
            assert connection.response.create_count == 1
            assert not await responses.response_done(mcp_item_ids={"call-1"})
        else:
            assert not await responses.response_done(mcp_item_ids={"call-1"})
            assert connection.response.create_count == 1
            await responses.mcp_finished("call-1")
        assert connection.response.create_count == 2
        await responses.response_created()
        assert await responses.response_done()

    asyncio.run(scenario())


def test_queued_text_waits_until_mcp_answer_finishes() -> None:
    async def scenario():
        connection = _EventConnection()
        responses = main._ResponseCoordinator(connection)
        await responses.queue_text("first")
        await responses.response_created()
        await responses.queue_text("second")
        assert not await responses.response_done(mcp_item_ids={"call-1"})
        assert connection.response.create_count == 1
        assert len(connection.conversation.item.items) == 1
        await responses.mcp_finished("call-1")
        assert connection.response.create_count == 2
        assert len(connection.conversation.item.items) == 1
        await responses.response_created()
        assert await responses.response_done()
        assert connection.response.create_count == 3
        assert len(connection.conversation.item.items) == 2
        await responses.response_created()
        assert await responses.response_done()

    asyncio.run(scenario())


@pytest.mark.parametrize("event_id", [None, "unrelated-event"])
def test_unmatched_error_does_not_retry_pending_mcp_continuation(event_id) -> None:
    async def scenario():
        connection = _EventConnection()
        responses = main._ResponseCoordinator(connection)
        await responses.queue_text("question")
        await responses.response_created()
        assert not await responses.response_done(mcp_item_ids={"call-1"})
        await responses.mcp_finished("call-1")
        assert not await responses.handle_error(SimpleNamespace(
            event_id=event_id,
            code="conversation_already_has_active_response",
        ))
        await responses.response_created()
        assert await responses.response_done()
        assert connection.response.create_count == 2

    asyncio.run(scenario())


def test_cancelled_response_output_ignores_late_mcp_without_start() -> None:
    async def scenario():
        connection = _EventConnection()
        responses = main._ResponseCoordinator(connection)
        await responses.queue_text("question")
        await responses.response_created()
        assert not await responses.response_done("cancelled", {"call-1"})
        await responses.mcp_finished("call-1")
        assert connection.response.create_count == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("tools_first", [False, True])
@pytest.mark.parametrize("greeting", ["", "Welcome!"])
def test_greeting_waits_for_both_ready_events_and_runs_once(tools_first, greeting) -> None:
    async def scenario():
        connection = _EventConnection()
        responses = main._ResponseCoordinator(connection, tools_ready=False)
        ready = [
            _event(main.ServerEventType.SESSION_UPDATED, session=SimpleNamespace(id="session-1")),
            _event(main.ServerEventType.MCP_LIST_TOOLS_COMPLETED, "list-1"),
        ]
        if tools_first:
            ready.reverse()

        class ReadyWebSocket(_RecordingWebSocket):
            async def send_json(self, payload):
                if payload["type"] == "session_started":
                    assert connection.response.create_count == 0
                await super().send_json(payload)

        class ReadyConnection(_EventConnection):
            def __aiter__(self):
                async def iterator():
                    yield ready[0]
                    assert connection.response.create_count == 0
                    assert not any(m["type"] == "session_started" for m in websocket.messages)
                    yield ready[1]
                    assert connection.response.create_count == int(bool(greeting))
                    if greeting:
                        yield _event(main.ServerEventType.RESPONSE_CREATED)
                        yield _event(main.ServerEventType.RESPONSE_DONE)
                    yield ready[0]
                    yield ready[1]
                return iterator()

        websocket = ReadyWebSocket()
        await main._voicelive_to_browser(
            websocket, ReadyConnection(), responses, greeting=greeting,
        )
        return connection, websocket

    connection, websocket = asyncio.run(scenario())
    assert connection.response.create_count == int(bool(greeting))
    assert connection.conversation.item.items == []
    ready = [m for m in websocket.messages if m["type"] == "session_started"]
    assert len(ready) == 1
    assert ready[0]["greeting_pending"] is bool(greeting)
    completions = [m for m in websocket.messages if m["type"] == "response_done"]
    assert completions == ([{"type": "response_done", "kind": "greeting", "status": "completed"}] if greeting else [])
    if greeting:
        assert connection.response.parameters == [{
            "pre_generated_assistant_message": {
                "type": "message", "role": "assistant",
                "content": [{"type": "text", "text": greeting}],
            },
            "tool_choice": "none",
        }]


@pytest.mark.parametrize("early_input", ["text", "speech", "audio"])
@pytest.mark.parametrize("tools_first", [False, True])
def test_early_user_input_skips_greeting(early_input, tools_first) -> None:
    async def scenario():
        connection = _EventConnection()
        responses = main._ResponseCoordinator(connection, tools_ready=False)
        if early_input == "text":
            await responses.queue_text("question")
        ready = [
            _event(main.ServerEventType.SESSION_UPDATED, session=SimpleNamespace(id="session-1")),
            _event(main.ServerEventType.MCP_LIST_TOOLS_COMPLETED, "list-1"),
        ]
        if tools_first:
            ready.reverse()
        early_events = {
            "text": [],
            "speech": [_event(main.ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED)],
            "audio": [_event(main.ServerEventType.INPUT_AUDIO_BUFFER_COMMITTED)],
        }
        connection.events = early_events[early_input] + ready
        websocket = _RecordingWebSocket()
        assert connection.response.create_count == 0
        await main._voicelive_to_browser(websocket, connection, responses, greeting="Welcome!")
        return connection, websocket

    connection, websocket = asyncio.run(scenario())
    ready = next(m for m in websocket.messages if m["type"] == "session_started")
    assert ready["greeting_pending"] is False
    assert connection.response.parameters == ([] if early_input == "speech" else [None])
    assert len(connection.conversation.item.items) == int(early_input == "text")


def test_silent_pcm_and_empty_text_do_not_suppress_greeting() -> None:
    async def scenario():
        connection = _EventConnection()
        connection.input_audio_buffer = SimpleNamespace(append=AsyncMock())
        websocket = _RecordingWebSocket()
        websocket.receive = AsyncMock(side_effect=[
            {"bytes": b"\x00\x00" * 2400},
            {"text": '{"type":"text","content":"  "}'},
            {"type": "websocket.disconnect"},
        ])
        responses = main._ResponseCoordinator(connection, tools_ready=False)
        await main._browser_to_voicelive(websocket, connection, responses)
        connection.input_audio_buffer.append.assert_awaited_once()
        notify = AsyncMock()
        await responses.start_session("Welcome!", notify)
        notify.assert_awaited_once_with(True)
        assert connection.response.create_count == 1
        assert connection.conversation.item.items == []

    asyncio.run(scenario())


@pytest.mark.parametrize("status", ["completed", "cancelled", "failed"])
def test_user_turn_waits_for_greeting_then_preserves_mcp_flow(status) -> None:
    async def scenario():
        connection = _EventConnection()
        responses = main._ResponseCoordinator(connection, tools_ready=False)
        notify = AsyncMock()
        await responses.start_session("Welcome!", notify)
        await responses.queue_text("question")
        assert connection.response.create_count == 1
        assert connection.conversation.item.items == []
        await responses.response_created()
        assert responses.greeting_active
        assert await responses.response_done(status) is (status == "completed")
        assert not responses.greeting_active
        assert connection.response.create_count == 2
        assert connection.response.parameters[1] is None
        await responses.start_session("Welcome!", notify)
        notify.assert_awaited_once_with(True)
        await responses.response_created()
        assert not await responses.response_done(mcp_item_ids={"call-1"})
        await responses.mcp_finished("call-1")
        assert connection.response.create_count == 3
        assert connection.response.parameters[2] is None
        await responses.response_created()
        assert await responses.response_done()
        assert len(connection.conversation.item.items) == 1
        assert connection.conversation.item.items[0].as_dict()["content"][0]["text"] == "question"

    asyncio.run(scenario())


@pytest.mark.parametrize("status", ["cancelled", "failed"])
def test_unsuccessful_greeting_has_explicit_completion_without_replay(status) -> None:
    connection = _EventConnection([
        _event(main.ServerEventType.SESSION_UPDATED, session=SimpleNamespace(id="session-1")),
        _event(main.ServerEventType.MCP_LIST_TOOLS_COMPLETED, "list-1"),
        _event(main.ServerEventType.RESPONSE_CREATED),
        _event(main.ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED),
        _event(main.ServerEventType.RESPONSE_DONE, response=SimpleNamespace(status=status)),
        _event(main.ServerEventType.MCP_LIST_TOOLS_COMPLETED, "list-1"),
    ])
    websocket = _RecordingWebSocket()
    asyncio.run(main._voicelive_to_browser(
        websocket, connection, main._ResponseCoordinator(connection, tools_ready=False),
        greeting="Welcome!",
    ))
    assert connection.response.create_count == 1
    assert [m for m in websocket.messages if m["type"] == "response_done"] == [
        {"type": "response_done", "kind": "greeting", "status": status},
    ]
    assert len([m for m in websocket.messages if m["type"] == "error"]) == int(status == "failed")


@pytest.mark.parametrize("code", ["invalid_request_error", "conversation_already_has_active_response"])
def test_greeting_create_error_does_not_retry_or_overlap_user_turn(code) -> None:
    async def scenario():
        connection = _EventConnection()
        responses = main._ResponseCoordinator(connection, tools_ready=False)
        await responses.start_session("Welcome!", AsyncMock())
        await responses.queue_text("question")
        assert not await responses.handle_error(SimpleNamespace(
            event_id="unrelated-event", code=code,
        ))
        assert responses.greeting_active
        assert not await responses.handle_error(SimpleNamespace(
            event_id=connection.response.event_ids[0], code=code,
        ))
        assert not responses.greeting_active
        if code == "conversation_already_has_active_response":
            assert connection.response.create_count == 1
            await responses.response_done()
        assert connection.response.create_count == 2
        assert connection.response.parameters[1] is None
        await responses.response_created()
        assert await responses.response_done()
        assert connection.response.create_count == 2

    asyncio.run(scenario())


def test_new_connection_can_greet_again() -> None:
    async def scenario():
        for _ in range(2):
            connection = _EventConnection()
            responses = main._ResponseCoordinator(connection, tools_ready=False)
            await responses.start_session("Welcome!", AsyncMock())
            assert connection.response.create_count == 1
            await responses.response_created()
            assert await responses.response_done()

    asyncio.run(scenario())


def test_ready_send_failure_does_not_start_greeting() -> None:
    async def scenario():
        connection = _EventConnection()
        responses = main._ResponseCoordinator(connection, tools_ready=False)
        with pytest.raises(main.WebSocketDisconnect):
            await responses.start_session(
                "Welcome!", AsyncMock(side_effect=main.WebSocketDisconnect()),
            )
        assert connection.response.create_count == 0

    asyncio.run(scenario())


def test_response_coordinator_serializes_two_text_turns() -> None:
    async def scenario():
        connection = _EventConnection()
        responses = main._ResponseCoordinator(connection)
        await responses.queue_text("first")
        await responses.queue_text("second")
        assert connection.response.create_count == 1
        assert len(connection.conversation.item.items) == 1

        await responses.response_created()
        assert await responses.response_done()
        assert connection.response.create_count == 2
        assert len(connection.conversation.item.items) == 2

        await responses.response_created()
        assert await responses.response_done()
        return connection

    connection = asyncio.run(scenario())

    assert connection.response.event_ids == [
        "voice-live-response-1",
        "voice-live-response-2",
    ]
    texts = [
        item.as_dict()["content"][0]["text"]
        for item in connection.conversation.item.items
    ]
    assert texts == ["first", "second"]


def test_text_create_conflict_retries_without_duplicate_conversation_item() -> None:
    async def scenario():
        connection = _EventConnection()
        responses = main._ResponseCoordinator(connection)
        await responses.queue_text("question")
        handled = await responses.handle_error(
            SimpleNamespace(
                code="conversation_already_has_active_response",
                event_id="voice-live-response-1",
            )
        )
        assert handled
        await responses.response_done()
        await responses.response_created()
        assert await responses.response_done()
        return connection

    connection = asyncio.run(scenario())

    assert connection.response.event_ids == [
        "voice-live-response-1",
        "voice-live-response-2",
    ]
    assert len(connection.conversation.item.items) == 1


def test_text_create_conflict_preserves_queued_turn_order() -> None:
    async def scenario():
        connection = _EventConnection()
        responses = main._ResponseCoordinator(connection)
        await responses.queue_text("first")
        await responses.queue_text("second")
        await responses.queue_text("third")

        handled = await responses.handle_error(
            SimpleNamespace(
                code="conversation_already_has_active_response",
                event_id="voice-live-response-1",
            )
        )
        assert handled

        await responses.response_done()
        for _ in range(3):
            await responses.response_created()
            assert await responses.response_done()
        return connection

    connection = asyncio.run(scenario())

    assert connection.response.event_ids == [
        "voice-live-response-1",
        "voice-live-response-2",
        "voice-live-response-3",
        "voice-live-response-4",
    ]
    texts = [
        item.as_dict()["content"][0]["text"]
        for item in connection.conversation.item.items
    ]
    assert texts == ["first", "second", "third"]


def test_mcp_continuation_can_request_another_mcp_call() -> None:
    connection = _EventConnection(
        [
            _event(main.ServerEventType.RESPONSE_CREATED),
            _mcp_response_done("call-1"),
            _event(main.ServerEventType.RESPONSE_MCP_CALL_IN_PROGRESS, "call-1"),
            _event(main.ServerEventType.RESPONSE_MCP_CALL_COMPLETED, "call-1"),
            _mcp_output_done("call-1"),
            _event(main.ServerEventType.RESPONSE_CREATED),
            _mcp_response_done("call-2"),
            _event(main.ServerEventType.RESPONSE_MCP_CALL_IN_PROGRESS, "call-2"),
            _event(main.ServerEventType.RESPONSE_MCP_CALL_COMPLETED, "call-2"),
            _mcp_output_done("call-2"),
            _event(main.ServerEventType.RESPONSE_CREATED),
            _event(main.ServerEventType.RESPONSE_DONE),
        ]
    )

    websocket = _run_service_events(connection)

    assert connection.response.create_count == 2
    assert [message["type"] for message in websocket.messages].count("response_done") == 1


def test_committed_audio_turn_uses_response_coordinator() -> None:
    connection = _EventConnection(
        [
            _event(main.ServerEventType.INPUT_AUDIO_BUFFER_COMMITTED),
            _event(main.ServerEventType.RESPONSE_CREATED),
            _event(main.ServerEventType.RESPONSE_DONE),
        ]
    )

    websocket = _run_service_events(connection)

    assert connection.response.event_ids == ["voice-live-response-1"]
    assert connection.conversation.item.items == []
    assert [message["type"] for message in websocket.messages] == ["response_done"]


def test_cancelled_mcp_response_ignores_late_terminal_event() -> None:
    connection = _EventConnection(
        [
            _event(main.ServerEventType.INPUT_AUDIO_BUFFER_COMMITTED),
            _event(main.ServerEventType.RESPONSE_CREATED),
            _event(main.ServerEventType.RESPONSE_MCP_CALL_IN_PROGRESS, "call-1"),
            _event(
                main.ServerEventType.RESPONSE_DONE,
                response=SimpleNamespace(
                    status="cancelled",
                    status_details=SimpleNamespace(reason="turn_detected"),
                ),
            ),
            _event(main.ServerEventType.RESPONSE_MCP_CALL_COMPLETED, "call-1"),
            _mcp_output_done("call-1"),
            _event(main.ServerEventType.INPUT_AUDIO_BUFFER_COMMITTED),
            _event(main.ServerEventType.RESPONSE_CREATED),
            _event(main.ServerEventType.RESPONSE_DONE),
        ]
    )

    websocket = _run_service_events(connection)

    assert connection.response.event_ids == [
        "voice-live-response-1",
        "voice-live-response-2",
    ]
    assert [message["type"] for message in websocket.messages].count("response_done") == 1
    assert not [message for message in websocket.messages if message["type"] == "error"]


def test_failed_response_is_reported_instead_of_completed() -> None:
    connection = _EventConnection(
        [
            _event(main.ServerEventType.INPUT_AUDIO_BUFFER_COMMITTED),
            _event(main.ServerEventType.RESPONSE_CREATED),
            _event(
                main.ServerEventType.RESPONSE_DONE,
                response=SimpleNamespace(
                    status="failed",
                    status_details=SimpleNamespace(
                        error={"message": "model unavailable"},
                    ),
                ),
            ),
        ]
    )

    websocket = _run_service_events(connection)

    assert websocket.messages == [
        {
            "type": "error",
            "message": "Voice Live response failed: model unavailable",
            "code": "response_failed",
        }
    ]


def test_browser_send_failure_ends_service_pump() -> None:
    class FailingWebSocket(_RecordingWebSocket):
        async def send_bytes(self, _data: bytes) -> None:
            raise RuntimeError("browser disconnected")

    connection = _EventConnection(
        [_event(main.ServerEventType.RESPONSE_AUDIO_DELTA, delta=b"audio")]
    )
    websocket = FailingWebSocket()

    with pytest.raises(main.WebSocketDisconnect):
        asyncio.run(
            main._voicelive_to_browser(
                websocket,
                connection,
                main._ResponseCoordinator(connection),
            )
        )


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("delta", ["AAE=", b"\x00\x01"])
def test_avatar_media_uses_one_audio_source(enabled, delta) -> None:
    class AudioWebSocket(_RecordingWebSocket):
        def __init__(self):
            super().__init__()
            self.audio = []

        async def send_bytes(self, data):
            self.audio.append(data)

    connection = _EventConnection([
        _event(main.ServerEventType.SESSION_UPDATED, session=SimpleNamespace(id="session-1")),
        _event(main.ServerEventType.MCP_LIST_TOOLS_COMPLETED, "list-1"),
        _event(main.ServerEventType.RESPONSE_AUDIO_DELTA, delta=b"\x00\x01"),
        _event(main.ServerEventType.RESPONSE_VIDEO_DELTA, delta=delta, codec="h264"),
    ])
    websocket = AudioWebSocket()
    asyncio.run(main._voicelive_to_browser(
        websocket, connection, main._ResponseCoordinator(connection), avatar_enabled=enabled,
    ))

    ready = next(message for message in websocket.messages if message["type"] == "session_started")
    assert ready["avatar_enabled"] is enabled
    video = [message for message in websocket.messages if message["type"] == "video_data"]
    assert video == ([{"type": "video_data", "delta": "AAE=", "codec": "h264"}] if enabled else [])
    assert websocket.audio == ([] if enabled else [main._audio_frame(b"\x00\x01")])


def test_expiring_search_authorization_requests_reconnect() -> None:
    websocket = _RecordingWebSocket()

    asyncio.run(main._expire_search_authorization(websocket, 0))

    assert websocket.messages == [
        {
            "type": "reauth_required",
            "message": "The Search authorization is expiring. Reconnect to continue.",
        }
    ]
    assert websocket.closed == (1012, "Search authorization expiring; reconnect")
