from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp.server.fastmcp import FastMCP

from shared_mcp.auth import BearerTokenGate
from shared_mcp.finance_handoff.config import ServerConfig as HandoffConfig
from shared_mcp.finance_handoff.pack import register as register_handoff
from shared_mcp.finance_handoff.server import build_service as build_handoff_service
from shared_mcp.finance_otp_officer.config import ServerConfig as OtpConfig
from shared_mcp.finance_otp_officer.data import DataStore
from shared_mcp.finance_otp_officer.directory import search_candidates
from shared_mcp.finance_otp_officer.pack import register as register_otp
from shared_mcp.finance_otp_officer.server import build_service as build_otp_service
from shared_mcp.probe import expected_tools_from_agent
from shared_mcp.server import (
    FINANCE_HANDOFF_PATH,
    FINANCE_OTP_OFFICER_PATH,
    HostConfig,
    build_app,
)


ROOT = Path(__file__).resolve().parents[1]
TOKEN = "0123456789abcdef0123456789abcdef"
SAMPLES_ROOT = ROOT.parent / "samples"
CONTRACT_ROOT = os.getenv("SHARED_MCP_AGENT_CONTRACT_ROOT", "").strip()
if CONTRACT_ROOT:
    HANDOFF_AGENT = Path(CONTRACT_ROOT) / "finance-handoff.json"
    OTP_AGENT = Path(CONTRACT_ROOT) / "finance-otp-officer.json"
else:
    HANDOFF_AGENT = SAMPLES_ROOT / "example1_finance_with_handoff" / "agent.json"
    OTP_AGENT = (
        SAMPLES_ROOT
        / "example2_finance_with_OTP_and_Officer_Search"
        / "agent.json"
    )


async def _request(app: object, method: str, path: str, token: str = "") -> int:
    messages: list[dict[str, object]] = []
    headers = []
    if token:
        headers.append(
            (b"authorization", b"Bear" + b"er " + token.encode())
        )
    received = False

    async def receive() -> dict[str, object]:
        nonlocal received
        if received:
            return {"type": "http.disconnect"}
        received = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        messages.append(message)

    await app(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": headers,
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1234),
        },
        receive,
        send,
    )
    start = next(
        message for message in messages if message["type"] == "http.response.start"
    )
    return int(start["status"])


class SharedMcpTests(unittest.TestCase):
    def test_default_configs_use_committed_fixtures(self) -> None:
        handoff = HandoffConfig.from_environment({})
        otp = OtpConfig.from_environment({"SHARED_MCP_TOKEN": TOKEN})
        self.assertEqual(handoff.data_dir, ROOT / "data" / "finance_handoff")
        self.assertEqual(otp.data_dir, ROOT / "data" / "finance_otp_officer")
        self.assertEqual(otp.directory_id, "loan_officers")
        self.assertEqual(otp.default_access_code, "12345007")

    def test_each_route_contains_every_agent_allowed_tool(self) -> None:
        handoff_agent_tools = expected_tools_from_agent(HANDOFF_AGENT)
        otp_agent_tools = expected_tools_from_agent(OTP_AGENT)
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            environment = {
                "SHARED_MCP_TOKEN": TOKEN,
                "FINANCE_MCP_STATE_DIR": str(state / "handoff"),
                "FINANCE_OTP_MCP_STATE_DIR": str(state / "otp"),
                "FINANCE_OTP_MCP_AUTH_DIR": str(state / "auth"),
            }
            handoff_mcp = FastMCP("handoff-test")
            otp_mcp = FastMCP("otp-test")
            with patch.dict("os.environ", environment, clear=False):
                register_handoff(handoff_mcp)
                register_otp(otp_mcp)

            handoff_inventory = {
                tool.name for tool in asyncio.run(handoff_mcp.list_tools())
            }
            otp_inventory = {tool.name for tool in asyncio.run(otp_mcp.list_tools())}

        self.assertTrue(handoff_agent_tools.issubset(handoff_inventory))
        self.assertTrue(otp_agent_tools.issubset(otp_inventory))
        self.assertNotEqual(handoff_inventory, otp_inventory)

    def test_fake_name_search_returns_one_fictional_available_officer(self) -> None:
        directory = DataStore(ROOT / "data" / "finance_otp_officer").load_directory(
            "loan_officers"
        )
        result = search_candidates(directory, ["any spoken name"])
        self.assertEqual(result["status"], "one_match")
        self.assertEqual(result["implementation"], "fake_random_sample")
        self.assertEqual(len(result["matches"]), 1)
        self.assertEqual(result["matches"][0]["status"], "available")

    def test_vendored_business_services_start_with_fictional_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            handoff_config = HandoffConfig.from_environment(
                {"FINANCE_MCP_STATE_DIR": str(state / "handoff")}
            )
            handoff = build_handoff_service(handoff_config).start_call(
                handoff_config.lead_id,
                handoff_config.campaign_id,
                handoff_config.ivr_menu_id,
                "handoff-test-operation",
                handoff_config.agent_persona_ref,
            )

            otp_config = OtpConfig.from_environment(
                {
                    "SHARED_MCP_TOKEN": TOKEN,
                    "FINANCE_OTP_MCP_STATE_DIR": str(state / "otp"),
                    "FINANCE_OTP_MCP_AUTH_DIR": str(state / "auth"),
                }
            )
            otp = build_otp_service(otp_config).start_and_verify_caller_otp(
                otp_config.caller_id,
                otp_config.directory_id,
                "otp-test-operation",
                "12345007",
                otp_config.routing_persona_ref,
            )

        self.assertTrue(handoff["ok"])
        self.assertEqual(handoff["calling_first_name"], "Mengyou")
        self.assertTrue(otp["ok"])
        self.assertTrue(otp["authenticated"])
        self.assertEqual(otp["customer"]["fixture"], "fictional")

    def test_health_is_public_and_mcp_routes_require_bearer_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            environment = {
                "SHARED_MCP_TOKEN": TOKEN,
                "FINANCE_MCP_STATE_DIR": str(state / "handoff"),
                "FINANCE_OTP_MCP_STATE_DIR": str(state / "otp"),
                "FINANCE_OTP_MCP_AUTH_DIR": str(state / "auth"),
            }
            with patch.dict("os.environ", environment, clear=False):
                app = build_app(HostConfig.from_environment(environment))

        self.assertEqual(asyncio.run(_request(app, "GET", "/healthz")), 200)
        for path in (FINANCE_HANDOFF_PATH, FINANCE_OTP_OFFICER_PATH):
            for method in ("GET", "POST", "DELETE"):
                self.assertEqual(asyncio.run(_request(app, method, path)), 401)

    def test_bearer_gate_accepts_the_configured_token(self) -> None:
        async def downstream(
            scope: dict[str, object],
            receive: object,
            send: object,
        ) -> None:
            del scope, receive
            await send(
                {
                    "type": "http.response.start",
                    "status": 204,
                    "headers": [],
                }
            )
            await send({"type": "http.response.body", "body": b""})

        gate = BearerTokenGate(downstream, TOKEN)
        self.assertEqual(
            asyncio.run(_request(gate, "POST", "/mcp", TOKEN)),
            204,
        )

    def test_host_rejects_short_tokens(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 32"):
            HostConfig.from_environment({"SHARED_MCP_TOKEN": "short"})


if __name__ == "__main__":
    unittest.main()
