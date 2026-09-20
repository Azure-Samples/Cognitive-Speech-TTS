# Copyright (c) Microsoft. All rights reserved.
"""Template catalog and route tests that do not require Azure or a live MCP."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aiohttp.test_utils import TestClient, TestServer

import demo_server
from template_portal import (
    McpProbeError,
    TemplateCatalog,
    template_agent_name,
)


ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://sample.services.ai.azure.com/api/projects/sample-project"
EXPECTED_TEMPLATES = [
    "finance-example",
    "finance-with-otp-and-officer-search",
    "elevator-service-example",
]


class TemplateCatalogTests(unittest.TestCase):
    def test_default_catalog_detects_both_sample_projects(self) -> None:
        catalog = TemplateCatalog()

        self.assertEqual(
            [card["id"] for card in catalog.cards()],
            EXPECTED_TEMPLATES,
        )
        self.assertEqual(catalog.errors, [])
        first = catalog.detail("finance-example")
        second = catalog.detail("finance-with-otp-and-officer-search")
        third = catalog.detail("elevator-service-example")
        assert first is not None and second is not None and third is not None
        self.assertGreater(len(first["graph"]["nodes"]), 1)
        self.assertGreater(len(first["graph"]["edges"]), 1)
        self.assertTrue(first["requires_mcp"])
        self.assertTrue(second["requires_mcp"])
        self.assertTrue(third["requires_mcp"])
        self.assertEqual("managed", first["mcp"]["connection_mode"])
        self.assertEqual("managed", second["mcp"]["connection_mode"])
        self.assertEqual("managed", third["mcp"]["connection_mode"])
        self.assertFalse(first["mcp"]["allow_user_token"])
        self.assertFalse(second["mcp"]["allow_user_token"])
        self.assertFalse(third["mcp"]["allow_user_token"])
        self.assertEqual(
            "Local shared_mcp Dev Tunnel",
            first["mcp"]["source_label"],
        )
        self.assertEqual(
            "VoiceAgent/shared_mcp",
            first["mcp"]["source_reference"],
        )
        self.assertEqual(second["agent_name"], "finance-with-otp-and-officer-search")
        self.assertEqual(third["agent_name"], "elevator-service-example")
        self.assertEqual(
            "en-US-Ava:DragonHDLatestNeural",
            third["voice"],
        )
        self.assertEqual(len(third["graph"]["nodes"]), 10)
        self.assertEqual(len(third["graph"]["edges"]), 17)
        self.assertEqual(
            "Local shared_mcp Dev Tunnel",
            third["mcp"]["source_label"],
        )
        self.assertEqual(
            "VoiceAgent/shared_mcp",
            third["mcp"]["source_reference"],
        )
        dial_assess = next(
            node
            for node in first["graph"]["nodes"]
            if node["id"] == "dial_assess"
        )
        self.assertEqual(["start_call"], dial_assess["tools"])
        report_issue = next(
            node
            for node in third["graph"]["nodes"]
            if node["id"] == "report_issue"
        )
        self.assertEqual(
            [
                "record_issue",
                "assess_safety",
                "mock_zendesk_create_ticket",
            ],
            report_issue["tools"],
        )
        human_handoff = next(
            node
            for node in third["graph"]["nodes"]
            if node["id"] == "human_handoff"
        )
        self.assertEqual(
            ["request_human_handoff"],
            human_handoff["tools"],
        )
        query_issue = next(
            node
            for node in third["graph"]["nodes"]
            if node["id"] == "query_issue"
        )
        self.assertEqual(
            ["mock_zendesk_get_ticket_status"],
            query_issue["tools"],
        )

    def test_template_agent_names_are_limited_to_63_characters(self) -> None:
        self.assertEqual(
            63,
            len(template_agent_name(f"local-only-{'a' * 52}", "finance-example")),
        )
        self.assertEqual(
            "local-only-finance-example",
            template_agent_name("finance-example", "finance-example"),
        )
        self.assertEqual(
            "local-only-finance-example",
            template_agent_name("local-only-finance-example", "finance-example"),
        )
        with self.assertRaisesRegex(ValueError, "at most 52 characters"):
            template_agent_name(f"local-only-{'a' * 53}", "finance-example")

    def test_catalog_rejects_projects_outside_samples(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            samples = root / "samples"
            portal = root / "portal"
            shared_mcp = root / "shared_mcp"
            samples.mkdir()
            portal.mkdir()
            shared_mcp.mkdir()
            config = portal / "templates.config.json"
            config.write_text(
                json.dumps({
                    "version": 1,
                    "templates": [{"id": "outside", "folder": "../outside"}],
                }),
                encoding="utf-8",
            )

            catalog = TemplateCatalog(config, samples, shared_mcp)

        self.assertEqual(catalog.cards(), [])
        self.assertIn("must resolve under", catalog.errors[0]["error"])

    def test_portal_owns_complete_template_assets(self) -> None:
        for name in (
            "templates.html",
            "template-app.js",
            "template-graph.js",
            "template-styles.css",
        ):
            with self.subTest(name=name):
                self.assertTrue((ROOT / "static" / name).is_file())
        html = (ROOT / "static" / "templates.html").read_text(encoding="utf-8")
        self.assertIn("VoiceAgent/portal/templates.config.json", html)
        self.assertIn('id="mcp-token"', html)
        self.assertIn('type="password"', html)
        for name in (
            "components/HandoffGraphPanel.jsx",
            "lib/projectPicker.mjs",
            "lib/projectPicker.test.mjs",
        ):
            with self.subTest(name=name):
                self.assertTrue((ROOT / "web" / "src" / name).is_file())
        handoff_panel = (
            ROOT / "web/src/components/HandoffGraphPanel.jsx"
        ).read_text(encoding="utf-8")
        self.assertIn("data.connection_only", handoff_panel)
        self.assertIn(
            "no direct MCP URL is available to test",
            handoff_panel,
        )


class TemplateRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        args = demo_server.parse_args([
            "--project-endpoint", ENDPOINT, "--no-record-sessions",
        ])
        self.client = TestClient(TestServer(demo_server.build_app(args)))
        await self.client.start_server()

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def test_templates_page_and_catalog_routes(self) -> None:
        page = await self.client.get("/templates")
        self.assertEqual(page.status, 200)
        self.assertIn("three-pane", await page.text())

        config = await self.client.get("/api/config")
        self.assertEqual(config.status, 200)
        config_payload = await config.json()
        self.assertTrue(config_payload["configured"])
        self.assertEqual(config_payload["project"], "sample-project")

        templates = await self.client.get("/api/templates")
        self.assertEqual(templates.status, 200)
        payload = await templates.json()
        self.assertTrue(payload["available"])
        self.assertEqual(
            [item["id"] for item in payload["templates"]],
            EXPECTED_TEMPLATES,
        )

        detail = await self.client.get("/api/templates/finance-example")
        self.assertEqual(detail.status, 200)
        detail_payload = await detail.json()
        self.assertEqual(detail_payload["agent_name"], "finance-example")
        self.assertGreater(len(detail_payload["graph"]["nodes"]), 1)

    async def test_template_assets_are_served_without_azure_credentials(self) -> None:
        for name in (
            "template-app.js",
            "template-graph.js",
            "template-styles.css",
        ):
            with self.subTest(name=name):
                response = await self.client.get(f"/static/{name}")
                self.assertEqual(response.status, 200)

        cfg = self.client.server.app[demo_server.DEFAULT_CONFIG_KEY]
        self.assertIsNone(cfg._credential)

    async def test_unknown_template_and_asset_are_not_exposed(self) -> None:
        self.assertEqual(
            (await self.client.get("/api/templates/not-configured")).status,
            404,
        )
        self.assertEqual(
            (await self.client.get("/static/not-allowlisted.txt")).status,
            404,
        )

    async def test_connection_only_mcp_is_reported_as_non_probeable(self) -> None:
        agent = {
            "versions": {
                "latest": {
                    "definition": {
                        "kind": "voice",
                        "tools": [
                            {
                                "type": "mcp",
                                "server_label": "connection-only",
                                "project_connection_id": "sample-connection",
                                "allowed_tools": ["lookup"],
                            }
                        ],
                    }
                }
            }
        }
        with patch("template_portal.get_agent", return_value=agent):
            response = await self.client.post(
                "/api/mcp/probe",
                json={
                    "agent": "sample-agent",
                    "server_label": "connection-only",
                },
            )

        self.assertEqual(200, response.status)
        payload = await response.json()
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["connection_only"])
        self.assertIn("project connection", payload["error"])

    async def test_connection_backed_mcp_auth_gate_is_reachable(self) -> None:
        agent = {
            "versions": {
                "latest": {
                    "definition": {
                        "kind": "voice",
                        "tools": [
                            {
                                "type": "mcp",
                                "server_label": "connection-backed",
                                "server_url": "https://mcp.example/mcp",
                                "project_connection_id": "sample-connection",
                                "allowed_tools": ["lookup"],
                            }
                        ],
                    }
                }
            }
        }
        with (
            patch("template_portal.get_agent", return_value=agent),
            patch(
                "template_portal.mcp_handshake",
                side_effect=McpProbeError(
                    "initialize returned HTTP 401",
                    latency_ms=12,
                    http_status=401,
                ),
            ),
        ):
            response = await self.client.post(
                "/api/mcp/probe",
                json={
                    "agent": "sample-agent",
                    "server_label": "connection-backed",
                },
            )

        self.assertEqual(200, response.status)
        payload = await response.json()
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["reached"])
        self.assertTrue(payload["project_connection_auth"])

    async def test_portal_rejects_browser_provided_mcp_tokens(self) -> None:
        response = await self.client.post(
            "/api/templates/finance-example/mcp/configure",
            json={"token": "synthetic-token"},
        )
        self.assertEqual(409, response.status)
        self.assertIn("browser-provided MCP tokens are disabled", await response.text())


if __name__ == "__main__":
    unittest.main()
