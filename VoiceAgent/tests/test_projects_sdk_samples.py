"""Offline contract tests against the released Projects SDK, not a client stub."""

from __future__ import annotations

import asyncio
import base64
import importlib
from importlib import metadata
import io
import json
import os
import runpy
import sys
import tempfile
import unittest
import wave
from collections import deque
from contextlib import ExitStack, redirect_stdout
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

from aiohttp import WSMessage, WSMsgType
from azure.ai.projects.aio import AIProjectClient
from azure.ai.projects.aio.operations import AsyncBetaRealtimeConnection
from azure.core.credentials import AccessToken
from azure.core.exceptions import HttpResponseError
from azure.core.pipeline.transport import AsyncHttpResponse, AsyncHttpTransport
from azure.core.utils import case_insensitive_dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "samples"))
with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}):
    SAMPLES = [
        importlib.import_module(name)
        for name in (
            "basic_voice_agent",
            "voice_agent_with_mcp",
            "voice_agent_with_foundry_iq",
            "voice_agent_with_local_function",
            "voice_agent_with_toolbox",
        )
    ]
    artifacts = importlib.import_module("download_conversation_artifacts")
    rest_sample = importlib.import_module("simple_rest_lifecycle")

ENDPOINT = "https://sample.services.ai.azure.com/api/projects/sample"
AGENT_NAME = "voice-sample"
CONVERSATION_ID = "conversation-1"
CONVERSATION_PATH = (
    f"/agents/{AGENT_NAME}/endpoint/protocols/voice/conversations/{CONVERSATION_ID}"
)
NOT_FOUND = {"error": {"code": "not_found", "message": "Not ready."}}
ENVIRONMENT = {
    "AZURE_VOICE_AGENTS_ENDPOINT": ENDPOINT,
    "AZURE_VOICE_AGENTS_MODEL": "gpt-realtime",
    "AZURE_VOICE_AGENTS_VOICE": "en-US-AvaNeural",
    "AZURE_VOICE_AGENTS_MCP_CONNECTION_ID": "mcp-connection",
    "AZURE_VOICE_AGENTS_FOUNDRY_IQ_CONNECTION_ID": "iq-connection",
    "AZURE_VOICE_AGENTS_FOUNDRY_IQ_URL": (
        "https://sample.search.windows.net/knowledgebases/sample/mcp"
    ),
}


class OfflineCredential:
    async def get_token(self, *scopes, **kwargs):
        return AccessToken("offline-test-token", 4102444800)

    async def close(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()


class OfflineResponse(AsyncHttpResponse):
    def __init__(self, request, status_code, payload):
        super().__init__(request, None)
        self.status_code = status_code
        self.reason = HTTPStatus(status_code).phrase
        self.content_type = (
            "audio/wav" if isinstance(payload, bytes) else "application/json"
        )
        self.headers = case_insensitive_dict({"Content-Type": self.content_type})
        self._body = (
            payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        )

    def body(self):
        return self._body

    def json(self):
        return json.loads(self._body)

    async def read(self):
        return self._body

    async def iter_bytes(self):
        for offset in range(0, len(self._body), 16):
            yield self._body[offset : offset + 16]


class OfflineTransport(AsyncHttpTransport):
    def __init__(self, handler):
        self.handler = handler
        self.requests = []
        self.session = None

    def with_session(self, *, session):
        self.session = session
        return self

    async def open(self):
        pass

    async def close(self):
        if self.session is not None:
            await self.session.close()

    async def __aexit__(self, *args):
        await self.close()

    async def send(self, request, **kwargs):
        self.requests.append(request)
        status_code, payload = self.handler(request)
        return OfflineResponse(request, status_code, payload)


def isolated_environment(**overrides):
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("AZURE_VOICE_AGENTS_")
    }
    environment.update(ENVIRONMENT)
    environment.update(overrides)
    return patch.dict(os.environ, environment, clear=True)


def wav_bytes(channels):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(24000)
        output.writeframes(bytes(24 * channels * 2))
    return buffer.getvalue()


def conversation(status="completed"):
    return {
        "id": CONVERSATION_ID,
        "object": "voice.conversation",
        "status": status,
        "created_at": 1700000000,
    }


def session_created(**fields):
    return {
        "type": "session.created",
        "event_id": "event-session-created",
        "session": {"id": "session-not-conversation", "model": "gpt-realtime"},
        **fields,
    }


def wire_event(event_type, **fields):
    """Keep wire fixtures independent of the SDK enums used for dispatch."""
    return {"type": event_type, "event_id": f"event-{event_type}", **fields}


def audio_metadata(item_id=None, blob_uri=None):
    metadata = {
        "conversation_id": CONVERSATION_ID,
        "format": "wav",
        "sample_rate": 24000,
        "channels": 1 if item_id else 2,
        "duration_ms": 1,
    }
    if item_id:
        metadata.update(
            item_id=item_id,
            role="user" if item_id == "user-1" else "agent",
            codec="pcm16",
            start_offset_ms=0,
        )
    else:
        metadata["channel_layout"] = {"left": "user", "right": "agent"}
    if blob_uri:
        metadata["blob_uri"] = blob_uri
    return metadata


class ProjectsSDKSampleTests(unittest.IsolatedAsyncioTestCase):
    def test_released_sdk_requirements(self):
        self.assertIn(
            "voice", metadata.metadata("azure-ai-projects").get_all("Provides-Extra")
        )
        voice_requirements = {
            "requirements.txt",
            "subagent/client/requirements.txt",
            "subagent/voice-subagent-prompt-basic/requirements.txt",
            "subagent/voice-subagent-hosted-agent/requirements.txt",
        }
        management_requirements = {
            "create-agent-with-iq-avatar-voice/requirements.txt",
            "example1_finance_with_handoff/requirements.txt",
            "example2_finance_with_OTP_and_Officer_Search/requirements.txt",
        }
        for relative_path in sorted(voice_requirements | management_requirements):
            path = ROOT / "samples" / relative_path
            requirements = path.read_text(encoding="utf-8").splitlines()
            projects = [
                line for line in requirements
                if "azure-ai-projects" in line or "azure_ai_projects" in line
            ]
            with self.subTest(path=relative_path):
                extra = "[voice]" if relative_path in voice_requirements else ""
                self.assertEqual(projects, [f"azure-ai-projects{extra}>=2.7.0"])

    def test_supporting_scripts_import(self):
        with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}):
            for path in sorted((ROOT / "samples").glob("*.py")):
                with self.subTest(path=path.name):
                    importlib.import_module(path.stem)
            for path in sorted((ROOT / "skills").rglob("*.py")):
                with self.subTest(path=str(path.relative_to(ROOT))):
                    runpy.run_path(str(path))

    def test_subagent_scripts_import_and_build_definitions(self):
        for path in sorted((ROOT / "samples" / "subagent").rglob("*.py")):
            with (
                self.subTest(path=str(path.relative_to(ROOT))),
                patch.object(sys, "path", [str(path.parent), *sys.path]),
                patch.dict(sys.modules),
                patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}),
            ):
                sys.modules.pop("sample_utils", None)
                namespace = runpy.run_path(str(path))
                if "voice_definition" in namespace:
                    definition = namespace["voice_definition"](
                        "gpt-realtime", "subagent", "en-US-AvaNeural"
                    )
                    self.assertEqual(definition.as_dict()["kind"], "voice")

    async def test_trace_url_uses_only_voice_agent_bundle(self):
        trace_urls = importlib.import_module("foundry_trace_url")
        subscription_id = "00000000-0000-0000-0000-000000000001"
        with (
            patch.object(
                trace_urls,
                "_list_subscription_ids",
                AsyncMock(return_value=[subscription_id]),
            ),
            patch.object(
                trace_urls,
                "_find_account_resource",
                AsyncMock(
                    return_value={
                        "subscriptionId": subscription_id,
                        "resourceGroup": "sample-rg",
                    }
                ),
            ),
        ):
            url = await trace_urls.build_foundry_trace_url(
                ENDPOINT, AGENT_NAME, OfflineCredential()
            )
        self.assertIsNotNone(url)
        parsed = urlparse(url)
        self.assertEqual(parsed.query, "flight=voice_agent_bundle")
        self.assertTrue(parsed.path.endswith(f"/build/agents/{AGENT_NAME}/traces"))

    def test_samples_have_no_voice_live_dependency(self):
        requirements = (ROOT / "samples" / "requirements.txt").read_text()
        self.assertNotIn("azure-ai-voicelive", requirements)
        for path in sorted((ROOT / "samples").glob("*.py")):
            with self.subTest(sample=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertNotIn("azure.ai.voicelive", source)
                self.assertNotIn("_prepare_url", source)

    async def run_microphone_events(
        self, sample, events, *, cancel=False, capture_error=None
    ):
        websocket = MagicMock()
        websocket.close_code = 1000
        websocket.send_str = AsyncMock()
        websocket.close = AsyncMock()
        websocket.receive = AsyncMock(
            side_effect=[
                *(WSMessage(WSMsgType.TEXT, json.dumps(event), "") for event in events),
                asyncio.CancelledError()
                if cancel
                else WSMessage(WSMsgType.CLOSE, 1000, ""),
            ]
        )
        # Mock only the network boundary. The Projects SDK owns the handshake,
        # credential scopes, URL, event decoding, serialization, and cleanup.
        session = MagicMock()
        session.ws_connect = AsyncMock(return_value=websocket)
        session.close = AsyncMock()
        credential = OfflineCredential()
        credential.get_token = AsyncMock(wraps=credential.get_token)
        transport = OfflineTransport(
            lambda request: self.fail("Realtime must not send a management request.")
        )
        async with AIProjectClient(
            ENDPOINT, credential, allow_preview=True, transport=transport
        ) as client:
            with (
                patch("aiohttp.ClientSession", return_value=session),
                patch.object(sample, "AudioProcessor") as processor,
                patch.object(sample, "pyaudio", object()),
                redirect_stdout(io.StringIO()) as output,
            ):
                processor.return_value.start_capture.side_effect = capture_error
                if capture_error is None:
                    result = await sample.run_microphone_session(client, AGENT_NAME)
                else:
                    with self.assertRaises(type(capture_error)) as raised:
                        await sample.run_microphone_session(client, AGENT_NAME)
                    self.assertIs(raised.exception, capture_error)
                    result = None
        processor.assert_called_once()
        self.assertIsInstance(processor.call_args.args[0], AsyncBetaRealtimeConnection)
        processor.return_value.start_capture.assert_called_once()
        processor.return_value.start_playback.assert_called_once()
        processor.return_value.shutdown.assert_called_once()
        credential.get_token.assert_awaited_once_with("https://ai.azure.com/.default")
        session.ws_connect.assert_awaited_once()
        handshake = session.ws_connect.await_args
        self.assertEqual(
            handshake.args,
            (
                "wss://sample.services.ai.azure.com/api/projects/sample"
                f"/agents/{AGENT_NAME}/endpoint/protocols/voice",
            ),
        )
        self.assertEqual(handshake.kwargs["params"]["api-version"], "v1")
        self.assertIn(
            f"ai-projects/{metadata.version('azure-ai-projects')}",
            handshake.kwargs["params"]["x-ms-client-sdk"],
        )
        self.assertEqual(
            handshake.kwargs["headers"]["Foundry-Features"], "VoiceAgents=V1Preview"
        )
        self.assertEqual(
            handshake.kwargs["headers"]["Authorization"], "Bearer offline-test-token"
        )
        self.assertEqual(handshake.kwargs["protocols"], ("realtime",))
        websocket.close.assert_awaited_once()
        session.close.assert_awaited_once()
        return SimpleNamespace(
            conversation_id=result,
            audio=processor.return_value,
            websocket=websocket,
            output=output.getvalue(),
        )

    async def test_microphone_cleanup_on_capture_failure(self):
        for sample in SAMPLES:
            with self.subTest(sample=sample.__name__):
                await self.run_microphone_events(
                    sample, [], capture_error=RuntimeError("No microphone available.")
                )

    async def test_microphone_passes_pcm_bytes_to_projects_sdk(self):
        pcm = b"\x01\x00\xff\x7f" * 24
        loop = asyncio.get_running_loop()
        for sample in SAMPLES:
            with self.subTest(sample=sample.__name__):
                websocket = MagicMock()
                websocket.send_str = AsyncMock()
                connection = AsyncBetaRealtimeConnection(websocket, MagicMock())
                pyaudio = MagicMock()
                scheduled = []

                def schedule(coroutine, target_loop):
                    self.assertIs(target_loop, loop)
                    scheduled.append(coroutine)

                with (
                    patch.object(sample, "pyaudio", pyaudio),
                    patch.object(
                        sample.asyncio, "run_coroutine_threadsafe", side_effect=schedule
                    ),
                    patch.object(
                        connection.input_audio_buffer,
                        "append",
                        AsyncMock(wraps=connection.input_audio_buffer.append),
                    ) as append,
                ):
                    processor = sample.AudioProcessor(connection)
                    try:
                        processor.start_capture()
                        callback = pyaudio.PyAudio.return_value.open.call_args.kwargs[
                            "stream_callback"
                        ]
                        self.assertEqual(
                            callback(pcm, len(pcm) // 2, None, None),
                            (None, pyaudio.paContinue),
                        )
                        self.assertEqual(len(scheduled), 1)
                        await scheduled[0]
                        append.assert_awaited_once_with(audio=pcm)
                    finally:
                        processor.shutdown()
                websocket.send_str.assert_awaited_once()
                sent = json.loads(websocket.send_str.await_args.args[0])
                self.assertEqual(sent["type"], "input_audio_buffer.append")
                self.assertEqual(base64.b64decode(sent["audio"]), pcm)

    async def test_microphone_reads_session_created_conversation_id(self):
        for sample in SAMPLES:
            for cancel in (False, True):
                with self.subTest(sample=sample.__name__, cancel=cancel):
                    result = await self.run_microphone_events(
                        sample,
                        [session_created(conversation_id=CONVERSATION_ID)],
                        cancel=cancel,
                    )
                    self.assertEqual(result.conversation_id, CONVERSATION_ID)

    async def test_microphone_does_not_use_session_id_as_conversation_id(self):
        for sample in SAMPLES:
            for fields in ({}, {"conversation_id": None}):
                with self.subTest(sample=sample.__name__, fields=fields):
                    result = await self.run_microphone_events(
                        sample, [session_created(**fields)]
                    )
                    self.assertIsNone(result.conversation_id)

    async def test_microphone_dispatches_current_audio_and_transcript_events(self):
        pcm = b"\x01\x00\x02\x00"
        events = [
            session_created(conversation_id=CONVERSATION_ID),
            wire_event(
                "input_audio_buffer.speech_started",
                item_id="user-1",
                audio_start_ms=0,
            ),
            wire_event(
                "conversation.item.input_audio_transcription.completed",
                item_id="user-1",
                content_index=0,
                transcript="Hello from the caller.",
            ),
            wire_event(
                "response.output_audio.delta",
                response_id="response-1",
                item_id="agent-1",
                output_index=0,
                content_index=0,
                delta=base64.b64encode(pcm).decode(),
            ),
            wire_event(
                "response.output_audio_transcript.done",
                response_id="response-1",
                item_id="agent-1",
                output_index=0,
                content_index=0,
                transcript="Hello from the agent.",
            ),
            wire_event("error", error={"message": "Sample session error."}),
        ]
        for sample in SAMPLES:
            with self.subTest(sample=sample.__name__):
                result = await self.run_microphone_events(sample, events)
                self.assertEqual(result.conversation_id, CONVERSATION_ID)
                result.audio.queue_audio.assert_called_once_with(pcm)
                result.audio.skip_pending_audio.assert_called_once()
                self.assertIn("You:   Hello from the caller.", result.output)
                self.assertIn("Agent: Hello from the agent.", result.output)
                self.assertIn("Session error: Sample session error.", result.output)

    async def test_microphone_dispatches_mcp_events(self):
        events = [
            wire_event("mcp_list_tools.in_progress"),
            wire_event("mcp_list_tools.completed"),
            wire_event("mcp_list_tools.failed"),
            wire_event(
                "response.mcp_call_arguments.delta",
                item_id="mcp-1",
                delta='{"query": "enum-test"}',
            ),
            wire_event("response.mcp_call_arguments.done", item_id="mcp-1"),
            wire_event(
                "response.mcp_call.completed",
                item_id="mcp-1",
                output="completed-output",
            ),
            wire_event(
                "response.output_item.done",
                item={
                    "id": "mcp-2",
                    "type": "mcp_call",
                    "name": "output-item-tool",
                    "arguments": "{}",
                    "output": "output-item-output",
                },
            ),
            wire_event(
                "conversation.item.done",
                item={
                    "id": "mcp-3",
                    "type": "mcp_call",
                    "name": "conversation-item-tool",
                    "arguments": "{}",
                    "output": "conversation-item-output",
                },
            ),
            wire_event(
                "response.mcp_call.failed",
                item_id="mcp-4",
                error={"message": "MCP failure details."},
            ),
        ]
        for name in (
            "voice_agent_with_mcp",
            "voice_agent_with_foundry_iq",
            "voice_agent_with_toolbox",
        ):
            with self.subTest(sample=name):
                result = await self.run_microphone_events(
                    importlib.import_module(name), events
                )
                for status in ("in_progress", "completed", "failed"):
                    self.assertIn(
                        f"(MCP event: mcp_list_tools.{status})", result.output
                    )
                for expected in (
                    "enum-test",
                    "completed-output",
                    "MCP tool: output-item-tool",
                    "output-item-output",
                    "MCP tool: conversation-item-tool",
                    "conversation-item-output",
                    "MCP call failed:",
                    "MCP failure details.",
                ):
                    self.assertIn(expected, result.output)

    async def test_microphone_dispatches_local_function_events(self):
        result = await self.run_microphone_events(
            importlib.import_module("voice_agent_with_local_function"),
            [
                wire_event(
                    "response.function_call_arguments.delta",
                    item_id="function-1",
                    delta='{"a": 5, "b": 7}',
                ),
                wire_event(
                    "response.function_call_arguments.done",
                    item_id="function-1",
                    call_id="call-1",
                    name="add_numbers",
                ),
                wire_event(
                    "response.done",
                    response={"id": "response-1", "status": "completed", "output": []},
                ),
            ],
        )
        sent = [
            json.loads(call.args[0])
            for call in result.websocket.send_str.await_args_list
        ]
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0]["type"], "conversation.item.create")
        self.assertEqual(sent[0]["item"]["type"], "function_call_output")
        self.assertEqual(sent[0]["item"]["call_id"], "call-1")
        self.assertEqual(json.loads(sent[0]["item"]["output"]), {"sum": 12.0})
        self.assertEqual(sent[1]["type"], "response.create")

    async def test_local_function_waits_for_response_done(self):
        result = await self.run_microphone_events(
            importlib.import_module("voice_agent_with_local_function"),
            [
                wire_event(
                    "response.function_call_arguments.done",
                    item_id="function-1",
                    call_id="call-1",
                    name="add_numbers",
                    arguments='{"a": 5, "b": 7}',
                )
            ],
        )
        result.websocket.send_str.assert_not_awaited()
        self.assertIn("Local function: add_numbers", result.output)

    async def test_local_function_submits_all_outputs_before_one_follow_up(self):
        result = await self.run_microphone_events(
            importlib.import_module("voice_agent_with_local_function"),
            [
                *(
                    wire_event(
                        "response.function_call_arguments.done",
                        item_id=f"function-{number}",
                        call_id=f"call-{number}",
                        name="add_numbers",
                        arguments=json.dumps({"a": number, "b": 7}),
                    )
                    for number in (1, 2)
                ),
                wire_event(
                    "response.done",
                    response={"id": "response-1", "status": "completed", "output": []},
                ),
                wire_event(
                    "response.done",
                    response={"id": "response-2", "status": "completed", "output": []},
                ),
            ],
        )
        sent = [
            json.loads(call.args[0])
            for call in result.websocket.send_str.await_args_list
        ]
        self.assertEqual(
            [event["type"] for event in sent],
            ["conversation.item.create", "conversation.item.create", "response.create"],
        )
        self.assertEqual([event["item"]["call_id"] for event in sent[:2]], ["call-1", "call-2"])
        self.assertEqual(
            [json.loads(event["item"]["output"]) for event in sent[:2]],
            [{"sum": 8.0}, {"sum": 9.0}],
        )

    async def run_lifecycle(self, sample, transport, existing_name=None):
        microphone = AsyncMock(return_value=CONVERSATION_ID)
        credential = OfflineCredential()
        with ExitStack() as stack:
            stack.enter_context(isolated_environment())
            # Reusing an agent must not require the tool-creation settings.
            if existing_name:
                for key in list(os.environ):
                    if "_MCP_" in key or "_FOUNDRY_IQ_" in key:
                        del os.environ[key]
            stack.enter_context(
                patch.object(sample, "DefaultAzureCredential", return_value=credential)
            )
            stack.enter_context(
                patch.object(
                    sample, "AioHttpTransport", side_effect=transport.with_session
                )
            )
            stack.enter_context(
                patch.object(sample, "run_microphone_session", microphone)
            )
            stack.enter_context(
                patch.object(
                    sample, "build_foundry_trace_url", AsyncMock(return_value=None)
                )
            )
            output = stack.enter_context(redirect_stdout(io.StringIO()))
            await sample.lifecycle(existing_name)
        microphone.assert_awaited_once()
        self.assertIsInstance(microphone.await_args.args[0], AIProjectClient)
        self.assertEqual(len(microphone.await_args.args), 2)
        if existing_name:
            self.assertEqual(microphone.await_args.args[1], existing_name)
        self.assertTrue(transport.session.closed)
        return output.getvalue()

    async def test_create_versions_and_tool_payloads(self):
        for sample in SAMPLES:
            with self.subTest(sample=sample.__name__):
                bodies = []

                def respond(request, bodies=bodies):
                    self.assertEqual(request.method, "POST")
                    self.assertIn(
                        "VoiceAgents=V1Preview",
                        request.headers.get("Foundry-Features", ""),
                    )
                    self.assertEqual(
                        parse_qs(urlparse(request.url).query), {"api-version": ["v1"]}
                    )
                    self.assertRegex(
                        request.url, r"/agents/voice-[a-z-]+-[0-9a-f]{8}/versions\?"
                    )
                    body = json.loads(request.content)
                    bodies.append(body)
                    return 200, {
                        "object": "agent.version",
                        "id": "agent-version-id",
                        "name": urlparse(request.url).path.split("/")[-2],
                        "version": str(len(bodies)),
                        "created_at": 1700000000,
                        "metadata": {},
                        "definition": body["definition"],
                    }

                transport = OfflineTransport(respond)
                output = await self.run_lifecycle(sample, transport)
                self.assertEqual(
                    len(bodies), 2 if sample.__name__ == "basic_voice_agent" else 1
                )
                for body in bodies:
                    self.assertNotIn("name", body)
                    definition = body["definition"]
                    self.assertEqual(definition["kind"], "voice")
                    self.assertEqual(definition["model"], "gpt-realtime")
                    self.assertEqual(definition["model_type"], "managed")
                    self.assertTrue(definition["store"])
                    self.assertEqual(definition["output_modalities"], ["text", "audio"])
                    audio = definition["audio"]
                    self.assertEqual(audio["output"]["voice"], "en-US-AvaNeural")
                    self.assertEqual(audio["output"]["voice_type"], "azure-standard")
                    for direction in ("input", "output"):
                        self.assertEqual(
                            audio[direction]["format"],
                            {"type": "audio/pcm", "rate": 24000},
                        )
                    self.assertEqual(
                        audio["input"]["turn_detection"]["type"], "server_vad"
                    )
                    self.assertEqual(
                        audio["input"]["noise_reduction"]["type"],
                        "azure_deep_noise_suppression",
                    )
                    self.assertEqual(
                        audio["input"]["transcription"]["model"], "whisper-1"
                    )
                definition = bodies[0]["definition"]
                if sample.__name__ == "basic_voice_agent":
                    self.assertNotEqual(
                        definition["instructions"],
                        bodies[1]["definition"]["instructions"],
                    )
                    self.assertEqual(
                        transport.requests[0].url, transport.requests[1].url
                    )
                    self.assertIn("new version: 2", output)
                else:
                    tool = definition["tools"][0]
                    if sample.__name__ == "voice_agent_with_local_function":
                        self.assertEqual(tool["type"], "function")
                        self.assertEqual(tool["name"], "add_numbers")
                        self.assertEqual(tool["parameters"]["required"], ["a", "b"])
                        self.assertFalse(tool["parameters"]["additionalProperties"])
                        self.assertNotIn("strict", tool)
                    elif sample.__name__ == "voice_agent_with_toolbox":
                        self.assertEqual(tool["type"], "toolbox")
                        self.assertEqual(tool["toolbox_version"], "1")
                    else:
                        is_iq = sample.__name__ == "voice_agent_with_foundry_iq"
                        self.assertEqual(tool["type"], "mcp")
                        self.assertEqual(tool["require_approval"], "never")
                        self.assertEqual(
                            tool["project_connection_id"],
                            "iq-connection" if is_iq else "mcp-connection",
                        )
                        if is_iq:
                            self.assertEqual(
                                tool["server_url"],
                                ENVIRONMENT["AZURE_VOICE_AGENTS_FOUNDRY_IQ_URL"],
                            )

    async def test_existing_agents_skip_creation(self):
        for sample in SAMPLES:
            with self.subTest(sample=sample.__name__):

                def respond(request):
                    self.assertEqual(request.method, "GET")
                    self.assertEqual(
                        request.url, f"{ENDPOINT}/agents/{AGENT_NAME}?api-version=v1"
                    )
                    return 200, {"name": AGENT_NAME, "id": "agent-id"}

                transport = OfflineTransport(respond)
                await self.run_lifecycle(sample, transport, AGENT_NAME)
                self.assertEqual(len(transport.requests), 1)

    async def download_with_responses(self, responses, output_dir):
        pending = deque(responses)

        def respond(request):
            self.assertEqual(request.method, "GET")
            self.assertEqual(
                request.headers.get("Foundry-Features"), "VoiceAgents=V1Preview"
            )
            suffix, status, payload = pending.popleft()
            parsed = urlparse(request.url)
            self.assertEqual(
                parsed.path, f"/api/projects/sample{CONVERSATION_PATH}{suffix}"
            )
            query = parse_qs(parsed.query)
            self.assertEqual(query["api-version"], ["v1"])
            if suffix in {"/items", "/responses"}:
                self.assertEqual(query["order"], ["asc"])
            return status, payload

        transport = OfflineTransport(respond)
        with (
            isolated_environment(AZURE_VOICE_AGENTS_OUTPUT_DIR=str(output_dir)),
            patch.object(artifacts, "DefaultAzureCredential", OfflineCredential),
            patch.object(
                artifacts, "AioHttpTransport", side_effect=transport.with_session
            ),
            patch.object(artifacts.asyncio, "sleep", AsyncMock()),
            redirect_stdout(io.StringIO()),
        ):
            await artifacts.download(AGENT_NAME, CONVERSATION_ID)
        self.assertFalse(pending)
        self.assertTrue(transport.session.closed)
        return transport

    async def test_managed_downloads_pagination_and_persistence_retries(self):
        items = [
            {
                "id": item_id,
                "type": "message",
                "role": role,
                "content": [{"type": "input_text", "text": "Hello"}],
            }
            for item_id, role in (("user-1", "user"), ("agent-1", "assistant"))
        ]
        items.append({"id": "tool-1", "type": "function_call", "name": "lookup"})
        mono, stereo = wav_bytes(1), wav_bytes(2)
        responses = [
            ("", 404, NOT_FOUND),
            ("", 200, conversation("in_progress")),
            ("", 200, conversation()),
            ("/items", 200, {"data": items[:1], "last_id": "user-1"}),
            ("/items", 200, {"data": items[1:]}),
            (
                "/responses",
                200,
                {"data": [{"id": "response-1"}], "last_id": "response-1"},
            ),
            ("/responses", 200, {"data": [{"id": "response-2"}]}),
            ("/items/user-1/audio", 200, audio_metadata("user-1")),
            ("/items/user-1/audio/content", 200, mono),
            ("/items/agent-1/audio", 200, audio_metadata("agent-1")),
            ("/items/agent-1/audio/content", 200, mono),
            ("/items/tool-1/audio", 404, NOT_FOUND),
            ("/audio", 409, NOT_FOUND),
            ("/audio", 200, audio_metadata()),
            ("/audio/content", 404, NOT_FOUND),
            ("/audio", 200, audio_metadata()),
            ("/audio/content", 200, stereo),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            transport = await self.download_with_responses(responses, temporary)
            folder = Path(temporary) / CONVERSATION_ID
            manifest = json.loads((folder / "conversation.json").read_text())
            self.assertEqual(
                [item["id"] for item in manifest["items"]],
                ["user-1", "agent-1", "tool-1"],
            )
            self.assertEqual(len(manifest["responses"]), 2)
            self.assertEqual(len(manifest["turn_audio"]), 2)
            self.assertEqual(
                (folder / "turns" / "001_user_user-1.wav").read_bytes(), mono
            )
            self.assertEqual(
                (folder / "turns" / "002_agent_agent-1.wav").read_bytes(), mono
            )
            self.assertEqual((folder / "merged.wav").read_bytes(), stereo)
            self.assertEqual(manifest["merged_audio"]["metadata"]["duration_ms"], 1)
            cursors = [
                parse_qs(urlparse(request.url).query).get("after")
                for request in transport.requests
            ]
            self.assertIn(["user-1"], cursors)
            self.assertIn(["response-1"], cursors)

    async def test_customer_storage_records_blob_uris_without_downloading_audio(self):
        item_uri = "https://sample.blob.core.windows.net/audio/user-1.wav"
        merged_uri = "https://sample.blob.core.windows.net/audio/merged.wav"
        responses = [
            ("", 200, conversation()),
            (
                "/items",
                200,
                {"data": [{"id": "user-1", "type": "message", "role": "user"}]},
            ),
            ("/responses", 200, {"data": []}),
            ("/items/user-1/audio", 200, audio_metadata("user-1", item_uri)),
            ("/audio", 200, audio_metadata(blob_uri=merged_uri)),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            await self.download_with_responses(responses, temporary)
            folder = Path(temporary) / CONVERSATION_ID
            manifest = json.loads((folder / "conversation.json").read_text())
            self.assertIsNone(manifest["turn_audio"][0]["file"])
            self.assertEqual(
                manifest["turn_audio"][0]["metadata"]["blob_uri"], item_uri
            )
            self.assertIsNone(manifest["merged_audio"]["file"])
            self.assertEqual(
                manifest["merged_audio"]["metadata"]["blob_uri"], merged_uri
            )
            self.assertEqual(list(folder.rglob("*.wav")), [])

    async def test_download_errors_are_not_hidden_as_persistence_delays(self):
        transport = OfflineTransport(lambda request: (403, NOT_FOUND))
        async with AIProjectClient(
            ENDPOINT, OfflineCredential(), transport=transport, allow_preview=True
        ) as client:
            with self.assertRaises(HttpResponseError) as raised:
                await artifacts._wait_for_completed_conversation(
                    client.beta.voice_agents.conversations,
                    AGENT_NAME,
                    CONVERSATION_ID,
                    timeout_seconds=1,
                )
            self.assertEqual(raised.exception.status_code, 403)

    def test_rest_creation_matches_the_new_sdk_route_and_audio_shape(self):
        credential = MagicMock()
        credential.__enter__.return_value = credential
        credential.get_token.return_value = AccessToken(
            "offline-test-token", 4102444800
        )
        for existing_name in (None, AGENT_NAME):
            with (
                self.subTest(existing_name=existing_name),
                isolated_environment(),
                patch.object(
                    rest_sample, "DefaultAzureCredential", return_value=credential
                ),
                patch.object(
                    sys,
                    "argv",
                    ["simple_rest_lifecycle.py"]
                    + ([existing_name] if existing_name else []),
                ),
                patch.object(rest_sample.requests, "post") as post,
                patch.object(rest_sample.requests, "get") as get,
                redirect_stdout(io.StringIO()),
            ):
                rest_sample.main()
                if existing_name:
                    post.assert_not_called()
                    self.assertEqual(
                        get.call_args.args[0], f"{ENDPOINT}/agents/{AGENT_NAME}"
                    )
                else:
                    get.assert_not_called()
                    self.assertRegex(
                        post.call_args.args[0],
                        r"/agents/voice-rest-[0-9a-f]{8}/versions$",
                    )
                    body = post.call_args.kwargs["json"]
                    self.assertNotIn("name", body)
                    output = body["definition"]["audio"]["output"]
                    self.assertEqual(output["voice"], "en-US-AvaNeural")
                    self.assertEqual(output["voice_type"], "azure-standard")


if __name__ == "__main__":
    unittest.main()
