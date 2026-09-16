from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from aiohttp import ClientSession, DummyCookieJar
from aiohttp.test_utils import TestClient, TestServer

from app import (
    AppConfig,
    McpProbeError,
    TemplateCatalog,
    build_app,
    materialize_template,
    normalize_bearer_token,
    sdk_create_mcp_connection,
    iter_mcp_tools,
    validate_mcp_probe_url,
    validate_agent_name,
    validate_project_endpoint,
    voice_ws_url,
)
from session_log import SessionRecorder, list_sessions, read_events, read_session


class HelperTests(unittest.TestCase):
    def test_validates_endpoint_and_agent_name(self) -> None:
        endpoint = "https://account.services.ai.azure.com/api/projects/customer"
        self.assertEqual(validate_project_endpoint(endpoint + "/"), endpoint)
        self.assertEqual(validate_agent_name("customer-agent.v1"), "customer-agent.v1")
        with self.assertRaises(ValueError):
            validate_project_endpoint("https://<account>/api/projects/<project>")
        with self.assertRaises(ValueError):
            validate_agent_name("invalid agent name")

    def test_materializes_every_mcp_tool_without_mutating_source(self) -> None:
        document = {
            "definition": {
                "kind": "voice",
                "model": "old-model",
                "audio": {"output": {"voice": "old-voice"}},
                "handoff": {
                    "nodes": [
                        {
                            "id": "work",
                            "config": {
                                "tools": [
                                    {
                                        "type": "mcp",
                                        "server_url": "",
                                        "project_connection_id": "",
                                    }
                                ]
                            },
                        }
                    ]
                },
            }
        }
        result = materialize_template(
            document,
            model="gpt-realtime",
            voice="en-US-AvaNeural",
            mcp_server_url="https://tools.example/mcp",
            mcp_connection_id="customer-tools",
        )
        tool = result["handoff"]["nodes"][0]["config"]["tools"][0]
        self.assertEqual(tool["server_url"], "https://tools.example/mcp")
        self.assertEqual(tool["project_connection_id"], "customer-tools")
        self.assertNotIn("authorization", tool)
        self.assertNotIn("headers", tool)
        self.assertEqual(document["definition"]["model"], "old-model")

    def test_normalizes_bearer_tokens_without_accepting_header_injection(self) -> None:
        self.assertEqual(normalize_bearer_token("Bearer scoped-token"), "scoped-token")
        self.assertEqual(normalize_bearer_token("scoped-token"), "scoped-token")
        with self.assertRaises(ValueError):
            normalize_bearer_token("token\nInjected: value")

    def test_builds_voice_websocket_url(self) -> None:
        endpoint = "https://account.services.ai.azure.com/api/projects/customer"
        url = voice_ws_url(endpoint, "my-agent", "session-1")
        self.assertEqual(
            url,
            "wss://account.services.ai.azure.com/api/projects/customer/"
            "agents/my-agent/endpoint/protocols/voice"
            "?api-version=v1&agent_session_id=session-1",
        )

    def test_catalog_contains_handoff_template(self) -> None:
        catalog = TemplateCatalog()
        self.assertEqual(
            [card["id"] for card in catalog.cards()],
            ["finance-example", "finance-with-otp-and-officer-search"],
        )
        detail = catalog.detail("finance-example")
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertGreater(len(detail["graph"]["nodes"]), 1)
        self.assertGreater(len(detail["graph"]["edges"]), 1)
        self.assertTrue(all("layer" in node for node in detail["graph"]["nodes"]))
        self.assertIn("config_groups", detail)
        self.assertIn("tool_servers", detail)
        self.assertIn("yaml", detail)
        self.assertTrue(detail["requires_mcp"])

    def test_catalog_rejects_folders_outside_its_allowed_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            allowed_root = root / "samples"
            config_dir = allowed_root / "local_UI"
            config_dir.mkdir(parents=True)
            config_path = config_dir / "templates.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "templates": [
                            {"id": "outside", "folder": "../../../outside"}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            catalog = TemplateCatalog(config_path, allowed_root)

        self.assertEqual(catalog.cards(), [])
        self.assertIn("must resolve under", catalog.errors[0]["error"])

    def test_catalog_exposes_mcp_readiness_but_not_token_configuration_name(self) -> None:
        with patch.dict(
            os.environ,
            {"VOICE_AGENT_TEMPLATE_FINANCE_EXAMPLE_MCP_TOKEN": "synthetic-token"},
            clear=False,
        ):
            detail = TemplateCatalog().detail("finance-example")
        assert detail is not None
        self.assertTrue(detail["mcp"]["auth_configured"])
        encoded = json.dumps(detail)
        self.assertNotIn("synthetic-token", encoded)
        self.assertNotIn("VOICE_AGENT_TEMPLATE_FINANCE_EXAMPLE_MCP_TOKEN", encoded)

    def test_mcp_connection_stores_bearer_in_custom_keys(self) -> None:
        endpoint = "https://account.services.ai.azure.com/api/projects/customer"
        config = AppConfig(endpoint)
        config._credential = SimpleNamespace(
            get_token=lambda _scope: SimpleNamespace(token="arm-token"),
            close=lambda: None,
        )
        project = {
            "endpoint": endpoint,
            "subscription_id": "sub",
            "resource_group": "rg",
            "account": "account",
        }
        response = SimpleNamespace(ok=True, status_code=200, reason="OK")
        with (
            patch("app.sdk_list_projects", return_value=[project]),
            patch("app.requests.put", return_value=response) as put,
        ):
            result = sdk_create_mcp_connection(
                config,
                endpoint=endpoint,
                connection_name="trial-mcp",
                server_url="https://tools.example/mcp",
                bearer_token="scoped-token",
            )

        properties = put.call_args.kwargs["json"]["properties"]
        self.assertEqual(properties["authType"], "CustomKeys")
        self.assertEqual(properties["category"], "RemoteTool")
        self.assertEqual(properties["target"], "https://tools.example/mcp")
        self.assertEqual(
            properties["credentials"]["keys"]["Authorization"],
            "Bearer scoped-token",
        )
        self.assertEqual(result["name"], "trial-mcp")

    def test_mcp_probe_rejects_private_destinations(self) -> None:
        with patch(
            "app.socket.getaddrinfo",
            return_value=[
                (2, 1, 6, "", ("127.0.0.1", 443)),
            ],
        ):
            with self.assertRaises(McpProbeError):
                validate_mcp_probe_url("https://localhost/mcp")

    def test_session_recorder_writes_searchable_debug_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recorder = SessionRecorder(
                root,
                web_id="../../../unsafe-session",
                agent="trial-agent",
                backend="trial-project",
                upstream="wss://example.test/voice",
            )
            run_id = recorder.run_id
            recorder.record(
                "down",
                json.dumps(
                    {
                        "type": "session.created",
                        "session": {"id": "sess_test"},
                    }
                ),
            )
            recorder.record(
                "down",
                json.dumps(
                    {
                        "type": "conversation.created",
                        "conversation_id": "conv_test",
                    }
                ),
            )
            recorder.record(
                "down",
                json.dumps(
                    {
                        "type": "response.output_audio_transcript.done",
                        "transcript": "Hello.",
                    }
                ),
            )
            recorder.record(
                "down",
                json.dumps(
                    {
                        "type": "response.output_audio.delta",
                        "delta": "large-audio-payload",
                    }
                ),
            )
            recorder.close()

            self.assertEqual(root.resolve(), recorder.dir.parent.resolve())
            self.assertNotIn("/", run_id)
            self.assertEqual(stat.S_IMODE(recorder.dir.stat().st_mode), 0o700)
            for artifact_name in ("meta.json", "timeline.log", "events.jsonl"):
                self.assertEqual(
                    stat.S_IMODE((recorder.dir / artifact_name).stat().st_mode),
                    0o600,
                )
            detail = read_session(root, run_id)
            assert detail is not None
            self.assertEqual(detail["session_id"], "sess_test")
            self.assertEqual(detail["conversation_id"], "conv_test")
            self.assertIn("session.created", detail["timeline"])
            events = read_events(root, run_id)
            assert events is not None
            self.assertTrue(
                any(
                    event["type"] == "response.output_audio_transcript.done"
                    for event in events
                )
            )
            self.assertFalse(
                any(event["type"].endswith("audio.delta") for event in events)
            )
            self.assertEqual(
                [item["run_id"] for item in list_sessions(root, query="conv_test")],
                [run_id],
            )


class HttpSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = TestClient(TestServer(build_app(AppConfig())))
        await self.client.start_server()

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def test_shell_health_config_and_templates_work_without_azure(self) -> None:
        health = await self.client.get("/healthz")
        self.assertEqual(health.status, 200)
        self.assertEqual((await health.json())["status"], "ok")

        config = await self.client.get("/api/config")
        self.assertFalse((await config.json())["configured"])

        templates = await self.client.get("/api/templates")
        self.assertEqual(templates.status, 200)
        templates_payload = await templates.json()
        self.assertTrue(templates_payload["available"])
        self.assertEqual(len(templates_payload["templates"]), 2)

        page = await self.client.get("/")
        self.assertEqual(page.status, 200)
        self.assertIn("Voice Agent Playground", await page.text())

        templates_page = await self.client.get("/templates")
        self.assertEqual(templates_page.status, 200)
        self.assertIn("three-pane", await templates_page.text())

        self.assertEqual((await self.client.get("/sessions")).status, 404)
        self.assertEqual((await self.client.get("/api/demo/sessions")).status, 404)

    async def test_agents_endpoint_explains_missing_project(self) -> None:
        response = await self.client.get("/api/agents")
        self.assertEqual(response.status, 503)
        payload = await response.json()
        self.assertIn("AZURE_AI_PROJECT_ENDPOINT", payload["error"])

    async def test_project_selection_updates_the_active_endpoint(self) -> None:
        endpoint = "https://account.services.ai.azure.com/api/projects/customer"
        response = await self.client.post(
            "/api/project",
            json={"endpoint": endpoint},
        )
        self.assertEqual(response.status, 200)
        self.assertEqual((await response.json())["project"], "customer")

        config = await self.client.get("/api/config")
        payload = await config.json()
        self.assertTrue(payload["configured"])
        self.assertEqual(payload["endpoint"], endpoint)

        async with ClientSession(cookie_jar=DummyCookieJar()) as other_browser:
            other_config = await other_browser.get(
                self.client.make_url("/api/config")
            )
            other_payload = await other_config.json()
        self.assertFalse(other_payload["configured"])
        self.assertEqual(other_payload["endpoint"], "")

    async def test_template_publish_uses_connection_without_exposing_token(self) -> None:
        endpoint = "https://account.services.ai.azure.com/api/projects/customer"
        await self.client.post("/api/project", json={"endpoint": endpoint})
        connection = {
            "name": "trial-mcp",
            "id": "/accounts/account/connections/trial-mcp",
            "account_id": "/subscriptions/sub/resourceGroups/rg/providers/"
            "Microsoft.CognitiveServices/accounts/account",
        }

        def publish_stub(*_args, **kwargs):
            tools = list(iter_mcp_tools(kwargs["definition"]))
            self.assertTrue(tools)
            self.assertTrue(
                all(tool["project_connection_id"] == "trial-mcp" for tool in tools)
            )
            self.assertTrue(all("authorization" not in tool for tool in tools))
            return {
                "name": kwargs["name"],
                "version": "1",
                "definition": kwargs["definition"],
            }

        with (
            patch("app.sdk_create_mcp_connection", return_value=connection) as create,
            patch("app.sdk_publish_template", side_effect=publish_stub),
        ):
            response = await self.client.post(
                "/api/templates/finance-example/publish",
                json={
                    "name": "trial-agent",
                    "model": "gpt-realtime",
                    "voice": "en-US-AvaNeural",
                    "mcp_auth_token": "synthetic-token",
                },
            )

        response_text = await response.text()
        self.assertEqual(response.status, 201, response_text)
        payload = json.loads(response_text)
        self.assertEqual(payload["mcp_connection_name"], "trial-mcp")
        self.assertNotIn("synthetic-token", json.dumps(payload))
        self.assertEqual(
            create.call_args.kwargs["bearer_token"], "synthetic-token"
        )

    async def test_template_publish_failure_cleans_up_new_connection(self) -> None:
        endpoint = "https://account.services.ai.azure.com/api/projects/customer"
        await self.client.post("/api/project", json={"endpoint": endpoint})
        connection = {
            "name": "trial-mcp",
            "id": "/accounts/account/connections/trial-mcp",
            "account_id": "/subscriptions/sub/resourceGroups/rg/providers/"
            "Microsoft.CognitiveServices/accounts/account",
        }
        with (
            patch("app.sdk_create_mcp_connection", return_value=connection),
            patch("app.sdk_publish_template", side_effect=RuntimeError("publish failed")),
            patch("app.sdk_delete_mcp_connection") as delete,
        ):
            response = await self.client.post(
                "/api/templates/finance-example/publish",
                json={"mcp_auth_token": "synthetic-token"},
            )

        self.assertEqual(response.status, 502)
        delete.assert_called_once()

    async def test_mcp_probe_uses_published_agent_server(self) -> None:
        endpoint = "https://account.services.ai.azure.com/api/projects/customer"
        await self.client.post("/api/project", json={"endpoint": endpoint})
        agent = {
            "versions": {
                "latest": {
                    "definition": {
                        "kind": "voice",
                        "tools": [
                            {
                                "type": "mcp",
                                "server_label": "tools",
                                "server_url": "https://tools.example/mcp",
                                "project_connection_id": "trial-mcp",
                                "allowed_tools": ["lookup"],
                            }
                        ],
                    }
                }
            }
        }
        handshake = {
            "initialize_ms": 10.0,
            "tools_ms": 5.0,
            "latency_ms": 15.0,
            "http_status": 200,
            "reached": True,
            "server_name": "test",
            "server_version": "1",
            "tools": ["lookup"],
        }
        with (
            patch("app.sdk_get_agent", return_value=agent),
            patch("app.mcp_handshake", return_value=handshake) as probe,
        ):
            response = await self.client.post(
                "/api/mcp/probe",
                json={"agent": "trial-agent", "server_label": "tools"},
            )

        self.assertEqual(response.status, 200)
        payload = await response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["project_connection_id"], "trial-mcp")
        probe.assert_called_once_with("https://tools.example/mcp")

    async def test_mcp_probe_reports_authenticated_endpoint_as_reachable(self) -> None:
        endpoint = "https://account.services.ai.azure.com/api/projects/customer"
        await self.client.post("/api/project", json={"endpoint": endpoint})
        agent = {
            "versions": {
                "latest": {
                    "definition": {
                        "kind": "voice",
                        "tools": [
                            {
                                "type": "mcp",
                                "server_label": "tools",
                                "server_url": "https://tools.example/mcp",
                                "project_connection_id": "trial-mcp",
                            }
                        ],
                    }
                }
            }
        }
        with (
            patch("app.sdk_get_agent", return_value=agent),
            patch(
                "app.mcp_handshake",
                side_effect=McpProbeError(
                    "initialize returned HTTP 401",
                    latency_ms=12.5,
                    http_status=401,
                ),
            ),
        ):
            response = await self.client.post(
                "/api/mcp/probe",
                json={"agent": "trial-agent", "server_label": "tools"},
            )

        payload = await response.json()
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["reached"])
        self.assertEqual(payload["http_status"], 401)
        self.assertIn("credential remains", payload["error"])


if __name__ == "__main__":
    unittest.main()
