from __future__ import annotations

import asyncio
import json
import struct
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from websockets.datastructures import Headers

import e2e_local
from chat_client import proxy


class _BrowserWebSocket:
    remote_address = ("127.0.0.1", 12345)

    def __init__(self) -> None:
        self.closed: tuple[int, str] | None = None

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = (code, reason)

    def __aiter__(self):
        async def iterator():
            if False:
                yield None

        return iterator()


class _UpstreamWebSocket(_BrowserWebSocket):
    async def send(self, _message) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        pass


class _ConnectContext:
    def __init__(self, websocket: _UpstreamWebSocket) -> None:
        self.websocket = websocket

    async def __aenter__(self):
        return self.websocket

    async def __aexit__(self, *_args) -> None:
        pass


def test_handler_creates_a_new_foundry_session_per_browser_connection(monkeypatch) -> None:
    session_ids = iter(["session-one", "session-two"])
    urls: list[str] = []
    monkeypatch.setattr(proxy.uuid, "uuid4", lambda: next(session_ids))
    monkeypatch.setattr(proxy, "_entra_token", lambda: "token")

    def connect(url: str, **_kwargs):
        urls.append(url)
        return _ConnectContext(_UpstreamWebSocket())

    monkeypatch.setattr(proxy.websockets, "connect", connect)
    handler = proxy._make_handler(
        SimpleNamespace(
            foundry="https://example.services.ai.azure.com/api/projects/demo",
            agent="sample-agent",
            api_version="v1",
        )
    )

    asyncio.run(handler(_BrowserWebSocket()))
    asyncio.run(handler(_BrowserWebSocket()))

    assert "agent_session_id=session-one" in urls[0]
    assert "agent_session_id=session-two" in urls[1]
    assert urls[0] != urls[1]


@pytest.mark.parametrize("origin", [
    "https://untrusted.example",
    "null",
    "http://localhost:8765.untrusted.example",
    "http://localhost:8766",
    "http://127.0.0.1:8765/",
])
def test_untrusted_origin_is_rejected_before_token_retrieval(monkeypatch, origin) -> None:
    token = Mock(return_value="token")
    monkeypatch.setattr(proxy, "_entra_token", token)

    async def check():
        async with proxy.serve(
            proxy._make_handler(SimpleNamespace(
                foundry="https://example.services.ai.azure.com/api/projects/demo",
                agent="sample-agent", api_version="v1",
            )),
            "127.0.0.1", 0,
            process_request=proxy._process_request,
        ) as server:
            port = server.sockets[0].getsockname()[1]
            with pytest.raises(proxy.websockets.InvalidStatus) as exc:
                async with proxy.websockets.connect(
                    f"ws://127.0.0.1:{port}/invocations_ws", origin=origin,
                ):
                    pytest.fail("Untrusted origin was accepted")
            assert exc.value.response.status_code == 403

    asyncio.run(check())
    token.assert_not_called()


@pytest.mark.parametrize("origin", [None, "http://localhost:9876", "http://127.0.0.1:9876"])
def test_request_accepts_exact_local_origin_or_headless(origin) -> None:
    headers = Headers([("Connection", "Upgrade")])
    if origin is not None:
        headers["Origin"] = origin
    result = asyncio.run(proxy._process_request(
        SimpleNamespace(local_address=("127.0.0.1", 9876)),
        SimpleNamespace(headers=headers, path="/invocations_ws"),
    ))
    assert result is None


def test_request_rejects_multiple_origins() -> None:
    headers = Headers([
        ("Connection", "Upgrade"),
        ("Origin", "http://localhost:9876"),
        ("Origin", "http://127.0.0.1:9876"),
    ])
    result = asyncio.run(proxy._process_request(
        SimpleNamespace(local_address=("127.0.0.1", 9876)),
        SimpleNamespace(headers=headers, path="/invocations_ws"),
    ))
    assert result.status_code == 403


@pytest.mark.parametrize("endpoint", [
    "http://example.services.ai.azure.com/api/projects/demo",
    "ws://example.services.ai.azure.com/api/projects/demo",
    "ftp://example.services.ai.azure.com/api/projects/demo",
    "https://user:password@example.services.ai.azure.com/api/projects/demo",
    "https:///api/projects/demo",
])
def test_proxy_rejects_unsafe_foundry_endpoint_before_token(monkeypatch, endpoint) -> None:
    token = Mock(return_value="token")
    monkeypatch.setattr(proxy, "_entra_token", token)
    handler = proxy._make_handler(SimpleNamespace(
        foundry=endpoint, agent="sample-agent", api_version="v1",
    ))
    with pytest.raises(ValueError):
        asyncio.run(handler(_BrowserWebSocket()))
    token.assert_not_called()


@pytest.mark.parametrize("module", [proxy, e2e_local])
@pytest.mark.parametrize("scheme", ["https", "wss"])
def test_foundry_url_always_uses_tls(module, scheme) -> None:
    assert module._foundry_url(
        f"{scheme}://example.services.ai.azure.com/api/projects/demo",
        "sample-agent", "session", "v1",
    ).startswith("wss://example.services.ai.azure.com/")


@pytest.mark.parametrize("endpoint,override", [
    ("http://example.services.ai.azure.com/api/projects/demo", None),
    ("ws://example.services.ai.azure.com/api/projects/demo", None),
    ("https://user@example.services.ai.azure.com/api/projects/demo", None),
    ("http://example.services.ai.azure.com/api/projects/demo", "wss://example.services.ai.azure.com/ws"),
    ("https://example.services.ai.azure.com/api/projects/demo", "ws://example.services.ai.azure.com/ws"),
    ("https://example.services.ai.azure.com/api/projects/demo", "https://example.services.ai.azure.com/ws"),
    ("https://example.services.ai.azure.com/api/projects/demo", "wss://untrusted.example/ws"),
    ("https://example.services.ai.azure.com/api/projects/demo", "wss://example.services.ai.azure.com.untrusted.example/ws"),
    ("https://example.services.ai.azure.com/api/projects/demo", "wss://user@example.services.ai.azure.com/ws"),
    ("https://example.services.ai.azure.com/api/projects/demo", "wss://example.services.ai.azure.com:444/ws"),
])
def test_e2e_rejects_unsafe_authenticated_urls_before_token(monkeypatch, endpoint, override) -> None:
    token = Mock(return_value="token")
    run = AsyncMock(return_value=0)
    argv = ["e2e_local.py", "--foundry", endpoint]
    if override:
        argv += ["--url", override]
    monkeypatch.setattr(e2e_local.sys, "argv", argv)
    monkeypatch.setattr(e2e_local, "_entra_token", token)
    monkeypatch.setattr(e2e_local, "_run", run)
    with pytest.raises(SystemExit) as exc:
        e2e_local.main()
    assert exc.value.code == 2
    token.assert_not_called()
    run.assert_not_called()


@pytest.mark.parametrize("override", [None, "wss://example.services.ai.azure.com:443/ws"])
def test_e2e_accepts_same_host_tls_url(monkeypatch, override) -> None:
    token = Mock(return_value="token")
    run = AsyncMock(return_value=0)
    argv = ["e2e_local.py", "--foundry", "https://example.services.ai.azure.com/api/projects/demo"]
    if override:
        argv += ["--url", override]
    monkeypatch.setattr(e2e_local.sys, "argv", argv)
    monkeypatch.setattr(e2e_local, "_entra_token", token)
    monkeypatch.setattr(e2e_local, "_run", run)
    assert e2e_local.main() == 0
    token.assert_called_once()
    assert run.call_args.args[4] == {"Authorization": "Bearer token"}


def test_e2e_local_ws_does_not_request_token(monkeypatch) -> None:
    token = Mock(return_value="token")
    run = AsyncMock(return_value=0)
    monkeypatch.setattr(e2e_local.sys, "argv", ["e2e_local.py", "--url", "ws://localhost:8088/invocations_ws"])
    monkeypatch.setattr(e2e_local, "_entra_token", token)
    monkeypatch.setattr(e2e_local, "_run", run)
    assert e2e_local.main() == 0
    token.assert_not_called()
    assert run.call_args.args[4] == {}


@pytest.mark.parametrize("flags,required", [([], True), (["--skip-mcp"], False)])
def test_e2e_requires_knowledge_by_default(monkeypatch, flags, required) -> None:
    run = AsyncMock(return_value=0)
    monkeypatch.setattr(e2e_local.sys, "argv", ["e2e_local.py", *flags])
    monkeypatch.setattr(e2e_local, "_run", run)
    assert e2e_local.main() == 0
    assert run.call_args.kwargs == {"require_mcp": required, "require_avatar": False}


def test_e2e_avatar_cli_is_explicit(monkeypatch) -> None:
    run = AsyncMock(return_value=0)
    monkeypatch.setattr(e2e_local.sys, "argv", ["e2e_local.py", "--require-avatar"])
    monkeypatch.setattr(e2e_local, "_run", run)
    assert e2e_local.main() == 0
    assert run.call_args.kwargs == {"require_mcp": True, "require_avatar": True}


@pytest.mark.parametrize("enabled,delta,include_answer,expected_result", [
    (True, "AAE=", True, 0),
    (False, "AAE=", True, 1),
    (True, "", True, 1),
    (True, "not-base64!", True, 1),
    (True, "AAE=", False, 1),
])
def test_e2e_avatar_requires_answer_and_media_not_audit_pcm(
    monkeypatch, capsys, enabled, delta, include_answer, expected_result,
) -> None:
    events = [
        json.dumps({"type": "session_started", "avatar_enabled": enabled}),
        json.dumps({"type": "video_data", "delta": delta, "codec": "h264"}),
        json.dumps({"type": "mcp_status", "operation": "call", "status": "completed"}),
        json.dumps({"type": "bot_text", "delta": "vessels" if include_answer else ""}),
        json.dumps({"type": "response_done"}),
    ]
    websocket = _UpstreamWebSocket()
    websocket.recv = AsyncMock(side_effect=events)
    monkeypatch.setattr(e2e_local.websockets, "connect", lambda *_args, **_kwargs: _ConnectContext(websocket))
    assert asyncio.run(e2e_local._run(
        "ws://localhost:8088/invocations_ws", 1, "question", "vessel", require_avatar=True,
    )) == expected_result
    output = capsys.readouterr().out
    pcm = next(line for line in output.splitlines() if line.startswith("[e2e] audio_bytes_received"))
    assert pcm.endswith("SKIP")
    assert "NOT VALIDATED (manual browser test required)" in output


@pytest.mark.parametrize("require_mcp", [True, False])
def test_e2e_reports_knowledge_checks_and_skips(monkeypatch, capsys, require_mcp) -> None:
    events = [
        json.dumps({"type": "session_started"}),
        json.dumps({"type": "bot_text", "delta": "vessels"}),
        struct.pack("<II", 24000, 1) + b"\x00\x00",
        json.dumps({"type": "response_done"}),
    ]
    if require_mcp:
        events.insert(1, json.dumps({"type": "mcp_status", "operation": "call", "status": "completed"}))
    websocket = _UpstreamWebSocket()
    websocket.recv = AsyncMock(side_effect=events)
    monkeypatch.setattr(e2e_local.websockets, "connect", lambda *_args, **_kwargs: _ConnectContext(websocket))
    assert asyncio.run(e2e_local._run(
        "ws://localhost:8088/invocations_ws", 1, "question", "vessel",
        require_mcp=require_mcp,
    )) == 0
    output = capsys.readouterr().out
    line = next(line for line in output.splitlines() if line.startswith("[e2e] knowledge_mcp_completed"))
    assert line.endswith("PASS" if require_mcp else "SKIP")
    result = next(line for line in output.splitlines() if line.startswith("[e2e] result:"))
    assert result.endswith("PASS" if require_mcp else "PASS (partial; checks skipped)")


def _e2e_websocket(monkeypatch, events):
    websocket = _UpstreamWebSocket()
    websocket.send = AsyncMock()
    websocket.recv = AsyncMock(side_effect=[*events, asyncio.TimeoutError()])
    monkeypatch.setattr(
        e2e_local.websockets, "connect",
        lambda *_args, **_kwargs: _ConnectContext(websocket),
    )
    return websocket


def _json_event(event_type, **values):
    return json.dumps({"type": event_type, **values})


@pytest.mark.parametrize("greeting_pending", [False, True])
def test_e2e_sends_once_after_greeting_or_ready(monkeypatch, capsys, greeting_pending) -> None:
    ready = _json_event("session_started", greeting_pending=greeting_pending)
    events = [ready, ready]
    if greeting_pending:
        events += [
            _json_event("bot_text", delta="Hello, welcome!"),
            struct.pack("<II", 24000, 1) + b"\x00\x00" * 10,
            _json_event("response_done", kind="greeting", status="completed"),
            ready,
            _json_event("response_done", kind="greeting", status="completed"),
        ]
    events += [
        _json_event("mcp_status", operation="call", status="completed"),
        _json_event("bot_text", final=True, text="vessels"),
        struct.pack("<II", 24000, 1) + b"\x00\x00",
        _json_event("response_done"),
    ]
    websocket = _e2e_websocket(monkeypatch, events)
    assert asyncio.run(e2e_local._run(
        "ws://localhost:8088/invocations_ws", 1, "question", "vessel",
    )) == 0
    websocket.send.assert_awaited_once_with(json.dumps({"type": "text", "content": "question"}))
    output = capsys.readouterr().out
    assert "[e2e] assistant transcript:      'vessels'" in output
    assert "[e2e] audio bytes:               2" in output
    if greeting_pending:
        line = next(line for line in output.splitlines() if line.startswith("[e2e] greeting_completed "))
        assert line.endswith("PASS")


@pytest.mark.parametrize("greeting_status", ["cancelled", "failed", None])
def test_e2e_rejects_unsuccessful_greeting(monkeypatch, capsys, greeting_status) -> None:
    websocket = _e2e_websocket(monkeypatch, [
        _json_event("session_started", greeting_pending=True),
        _json_event("response_done", kind="greeting", status=greeting_status),
    ])
    assert asyncio.run(e2e_local._run(
        "ws://localhost:8088/invocations_ws", 1, "question", "vessel",
    )) == 1
    websocket.send.assert_not_awaited()
    output = capsys.readouterr().out
    assert "Greeting did not complete successfully." in output


def test_e2e_greeting_alone_is_not_an_answer(monkeypatch, capsys) -> None:
    websocket = _e2e_websocket(monkeypatch, [
        _json_event("session_started", greeting_pending=True),
        _json_event("bot_text", delta="vessels"),
        _json_event("mcp_status", operation="call", status="completed"),
        struct.pack("<II", 24000, 1) + b"\x00\x00",
        _json_event("response_done", kind="greeting", status="completed"),
    ])
    assert asyncio.run(e2e_local._run(
        "ws://localhost:8088/invocations_ws", 1, "question", "vessel",
    )) == 1
    websocket.send.assert_awaited_once()
    output = capsys.readouterr().out
    assert "[e2e] assistant transcript:      ''" in output
    assert "[e2e] audio bytes:               0" in output
    mcp = next(line for line in output.splitlines() if line.startswith("[e2e] knowledge_mcp_completed"))
    assert mcp.endswith("FAIL")


@pytest.mark.parametrize("require_avatar", [False, True])
def test_e2e_greeting_media_cannot_satisfy_answer_media(monkeypatch, capsys, require_avatar) -> None:
    _e2e_websocket(monkeypatch, [
        _json_event("video_data", delta="AAE=", codec="h264"),
        _json_event("session_started", greeting_pending=True, avatar_enabled=require_avatar),
        struct.pack("<II", 24000, 1) + b"\x00\x00",
        _json_event("video_data", delta="AAE=", codec="h264"),
        _json_event("response_done", kind="greeting", status="completed"),
        _json_event("mcp_status", operation="call", status="completed"),
        _json_event("bot_text", delta="vessels"),
        _json_event("response_done"),
    ])
    assert asyncio.run(e2e_local._run(
        "ws://localhost:8088/invocations_ws", 1, "question", "vessel",
        require_avatar=require_avatar,
    )) == 1
    output = capsys.readouterr().out
    assert "[e2e] audio bytes:               0" in output
    check = "avatar_media_received" if require_avatar else "audio_bytes_received"
    line = next(line for line in output.splitlines() if line.startswith(f"[e2e] {check}"))
    assert line.endswith("FAIL")


@pytest.mark.parametrize("error_event", [
    _json_event("error", message="Greeting synthesis failed"),
    _json_event("video_data", delta="not-base64!", codec="h264"),
])
def test_e2e_does_not_clear_errors_after_greeting(monkeypatch, capsys, error_event) -> None:
    _e2e_websocket(monkeypatch, [
        _json_event("session_started", greeting_pending=True),
        error_event,
        _json_event("response_done", kind="greeting", status="completed"),
        _json_event("mcp_status", operation="call", status="completed"),
        _json_event("bot_text", delta="vessels"),
        struct.pack("<II", 24000, 1) + b"\x00\x00",
        _json_event("response_done"),
    ])
    assert asyncio.run(e2e_local._run(
        "ws://localhost:8088/invocations_ws", 1, "question", "vessel",
    )) == 1
    line = next(line for line in capsys.readouterr().out.splitlines() if line.startswith("[e2e] no_error"))
    assert line.endswith("FAIL")


def test_e2e_requires_marked_greeting_completion(monkeypatch) -> None:
    websocket = _e2e_websocket(monkeypatch, [
        _json_event("session_started", greeting_pending=True),
        _json_event("response_done"),
    ])
    assert asyncio.run(e2e_local._run(
        "ws://localhost:8088/invocations_ws", 1, "question", "vessel",
    )) == 1
    websocket.send.assert_not_awaited()
