# Copyright (c) Microsoft. All rights reserved.
"""Browser integration fixture, never imported by the production portal.

Runs the real Foundry-only portal with an explicitly configured project. Only
the Azure credential and upstream HTTP/WebSocket boundaries are substituted.
The UI has no special test mode and never receives offline protocol flags.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

from aiohttp import WSMsgType, web
from aiohttp.test_utils import TestServer

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import demo_server as portal

ENDPOINT = "https://sample.services.ai.azure.com/api/projects/sample-project"
TOKEN = "integration-fixture-token"
REPLY = "Fixture response from the simulated Foundry service."
DEFINITION = {
    "kind": "voice", "model_type": "managed", "model": "gpt-realtime",
    "instructions": "Integration fixture.", "store": True,
    "audio": {
        "input": {"format": {"type": "audio/pcm", "rate": 24000}},
        "output": {"voice": "en-US-AvaNeural", "voice_type": "azure-standard"},
    },
}


class FixtureCredential:
    def get_token(self, *scopes):
        return SimpleNamespace(token=TOKEN, expires_on=4102444800)

    def close(self):
        pass


class FoundryFixture:
    def __init__(self):
        self.agents = {}
        self.conversations = {}
        self.save("fixture-agent", DEFINITION)

    def save(self, name, definition, description="Test fixture"):
        previous = self.agents.get(name, {}).get("versions", {}).get("latest", {})
        latest = {
            "version": str(int(previous.get("version", "0")) + 1),
            "created_at": 1, "definition": copy.deepcopy(definition),
            "description": description, "metadata": {},
        }
        self.agents[name] = {"name": name, "versions": {"latest": latest}}
        return latest

    async def handle(self, request):
        assert request.headers.get("Authorization") == f"Bearer {TOKEN}"
        assert request.headers.get("Foundry-Features") == portal.FOUNDRY_FEATURES
        segments = request.match_info["tail"].strip("/").split("/")
        if segments == ["agents:generate"]:
            body = await request.json()
            definition = {**DEFINITION, "instructions": "Generated definition from the test fixture."}
            self.save(body["name"], definition)
            return web.json_response(self.agents[body["name"]])
        if segments == ["agents"]:
            kind = request.query.get("kind")
            data = [
                value for value in self.agents.values()
                if not kind or value["versions"]["latest"]["definition"]["kind"] == kind
            ]
            return web.json_response({"data": data, "has_more": False})
        if len(segments) < 2 or segments[0] != "agents":
            raise web.HTTPNotFound()
        name = segments[1]
        if segments[2:] == ["versions"] and request.method == "POST":
            body = await request.json()
            assert "name" not in body
            return web.json_response(self.save(name, body["definition"], body.get("description", "")))
        agent = self.agents.get(name)
        if agent is None:
            raise web.HTTPNotFound()
        if len(segments) == 2:
            return web.json_response(agent)
        if segments[2] == "versions":
            return web.json_response(agent["versions"]["latest"])
        if segments[2:] == ["endpoint", "protocols", "voice"]:
            return await self.voice(request, agent)
        if len(segments) > 6 and segments[5] == "conversations":
            conversation = self.conversations[segments[6]]
            if segments[-1] == "items":
                return web.json_response({"data": conversation["items"], "has_more": False})
            return web.json_response({"id": segments[6], "status": "completed"})
        raise web.HTTPNotFound()

    async def voice(self, request, agent):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        conversation_id = f"fixture-conversation-{len(self.conversations) + 1}"
        conversation = {"items": []}
        self.conversations[conversation_id] = conversation
        session = {"id": "fixture-session", **agent["versions"]["latest"]["definition"]}
        await ws.send_json({"type": "session.created", "conversation_id": conversation_id, "session": session})
        await ws.send_json({"type": "session.updated", "session": session})
        async for message in ws:
            if message.type != WSMsgType.TEXT:
                continue
            event = json.loads(message.data)
            if event["type"] == "conversation.item.create":
                conversation["items"].append({**event["item"], "id": f"item-{len(conversation['items'])}"})
            elif event["type"] == "response.create":
                item = {
                    "id": f"item-{len(conversation['items'])}", "type": "message", "role": "assistant",
                    "content": [{"type": "output_text", "text": REPLY}],
                }
                conversation["items"].append(item)
                for frame in (
                    {"type": "response.created", "response": {"id": "fixture-response"}},
                    {"type": "response.output_text.delta", "response_id": "fixture-response", "delta": REPLY},
                    {"type": "response.output_text.done", "response_id": "fixture-response", "text": REPLY},
                    {"type": "response.done", "response": {"id": "fixture-response", "status": "completed", "output": [item]}},
                ):
                    await ws.send_json(frame)
            # Microphone PCM comes from Playwright's fake media device and is ignored.
        return ws


async def create_test_app():
    fixture = FoundryFixture()
    upstream_app = web.Application()
    upstream_app.router.add_route("*", "/api/projects/sample-project/{tail:.*}", fixture.handle)
    upstream = TestServer(upstream_app, host="127.0.0.1")
    await upstream.start_server()
    base = str(upstream.make_url("/api/projects/sample-project"))
    original_http = portal._forward_to_service
    original_ws = portal.ProjectWebSocketConnect

    def http_boundary(method, url, *args):
        assert url.startswith(ENDPOINT + "/")
        return original_http(method, base + url[len(ENDPOINT):], *args)

    def ws_boundary(url, **kwargs):
        expected = ENDPOINT.replace("https:", "wss:")
        assert url.startswith(expected + "/")
        return original_ws(base.replace("http:", "ws:") + url[len(expected):], proxy=None, **kwargs)

    patches = (
        patch.object(portal, "_forward_to_service", http_boundary),
        patch.object(portal, "ProjectWebSocketConnect", ws_boundary),
    )
    for item in patches:
        item.start()
    app = portal.build_app(portal.parse_args(["--project-endpoint", ENDPOINT]))
    app[portal.DEFAULT_CONFIG_KEY]._credential = FixtureCredential()

    async def cleanup(_app):
        for item in patches:
            item.stop()
        await upstream.close()

    app.on_cleanup.append(cleanup)
    return app


if __name__ == "__main__":
    web.run_app(create_test_app(), host="127.0.0.1", port=8097, print=None, access_log=None)
