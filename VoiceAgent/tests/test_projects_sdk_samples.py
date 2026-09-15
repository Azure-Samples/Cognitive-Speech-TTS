"""Offline contract tests against the bundled Projects SDK, not a client stub."""

from __future__ import annotations

import hashlib
import importlib
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
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse
from zipfile import ZipFile

from azure.ai.projects.aio import AIProjectClient
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
    def test_bundled_wheel(self):
        wheels = list((ROOT / "dist").glob("*.whl"))
        self.assertEqual(len(wheels), 1)
        wheel = wheels[0]
        self.assertEqual(wheel.name, "azure_ai_projects-2.6.1-py3-none-any.whl")
        self.assertIn(
            hashlib.sha256(wheel.read_bytes()).hexdigest(),
            (ROOT / "dist" / "README.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            f"./dist/{wheel.name}",
            (ROOT / "samples" / "requirements.txt").read_text(encoding="utf-8"),
        )
        with ZipFile(wheel) as archive:
            self.assertIsNone(archive.testzip())
            self.assertIn(
                "azure/ai/projects/aio/operations/_operations.py",
                archive.namelist(),
            )
            installed_root = Path(
                importlib.import_module("azure.ai.projects").__file__
            ).parent
            for name in archive.namelist():
                if name.startswith("azure/ai/projects/"):
                    installed = installed_root / name.removeprefix("azure/ai/projects/")
                    self.assertEqual(
                        installed.read_bytes(),
                        archive.read(name),
                        f"Install the bundled SDK wheel: {name} differs.",
                    )

    def test_supporting_scripts_import(self):
        with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}):
            for path in sorted((ROOT / "samples").glob("*.py")):
                with self.subTest(path=path.name):
                    importlib.import_module(path.stem)
            for path in sorted((ROOT / "skills").rglob("*.py")):
                with self.subTest(path=str(path.relative_to(ROOT))):
                    runpy.run_path(str(path))

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
