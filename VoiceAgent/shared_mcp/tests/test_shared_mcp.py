from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp.server.fastmcp import FastMCP

from shared_mcp.auth import BearerTokenGate
from shared_mcp.elevator_service.config import ServerConfig as ElevatorConfig
from shared_mcp.elevator_service.pack import register as register_elevator
from shared_mcp.elevator_service.server import (
    build_service as build_elevator_service,
)
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
    ELEVATOR_SERVICE_PATH,
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
    ELEVATOR_AGENT = Path(CONTRACT_ROOT) / "elevator-service.json"
    HANDOFF_AGENT = Path(CONTRACT_ROOT) / "finance-handoff.json"
    OTP_AGENT = Path(CONTRACT_ROOT) / "finance-otp-officer.json"
else:
    ELEVATOR_AGENT = (
        SAMPLES_ROOT
        / "example3_elevator_service_with_safety_zendesk_and_handoff"
        / "agent.json"
    )
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
        elevator = ElevatorConfig.from_environment({})
        handoff = HandoffConfig.from_environment({})
        otp = OtpConfig.from_environment({"SHARED_MCP_TOKEN": TOKEN})
        self.assertEqual(
            elevator.data_dir,
            ROOT / "data" / "elevator_service",
        )
        self.assertEqual(handoff.data_dir, ROOT / "data" / "finance_handoff")
        self.assertEqual(otp.data_dir, ROOT / "data" / "finance_otp_officer")
        self.assertEqual(otp.directory_id, "loan_officers")
        self.assertEqual(otp.default_access_code, "12345007")

    def test_each_route_contains_every_agent_allowed_tool(self) -> None:
        elevator_definition = json.loads(
            ELEVATOR_AGENT.read_text(encoding="utf-8")
        )["definition"]
        elevator_nodes = {
            node["id"]: node
            for node in elevator_definition["handoff"]["nodes"]
        }
        elevator_edges = {
            edge["id"]: edge
            for edge in elevator_definition["handoff"]["edges"]
        }
        report_instructions = elevator_nodes["report_issue"]["config"][
            "instructions"
        ]
        next_request_instructions = elevator_nodes["next_request"]["config"][
            "instructions"
        ]
        finalize_instructions = elevator_nodes["finalize"]["config"][
            "instructions"
        ]
        human_handoff_instructions = elevator_nodes["human_handoff"]["config"][
            "instructions"
        ]
        elevator_agent_tools = expected_tools_from_agent(ELEVATOR_AGENT)
        handoff_agent_tools = expected_tools_from_agent(HANDOFF_AGENT)
        otp_agent_tools = expected_tools_from_agent(OTP_AGENT)
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            environment = {
                "SHARED_MCP_TOKEN": TOKEN,
                "FINANCE_MCP_STATE_DIR": str(state / "handoff"),
                "FINANCE_OTP_MCP_STATE_DIR": str(state / "otp"),
                "FINANCE_OTP_MCP_AUTH_DIR": str(state / "auth"),
                "ELEVATOR_MCP_STATE_DIR": str(state / "elevator"),
            }
            elevator_mcp = FastMCP("elevator-test")
            handoff_mcp = FastMCP("handoff-test")
            otp_mcp = FastMCP("otp-test")
            with patch.dict("os.environ", environment, clear=False):
                register_elevator(elevator_mcp)
                register_handoff(handoff_mcp)
                register_otp(otp_mcp)

            elevator_inventory = {
                tool.name for tool in asyncio.run(elevator_mcp.list_tools())
            }
            handoff_inventory = {
                tool.name for tool in asyncio.run(handoff_mcp.list_tools())
            }
            otp_inventory = {tool.name for tool in asyncio.run(otp_mcp.list_tools())}

        self.assertTrue(elevator_agent_tools.issubset(elevator_inventory))
        self.assertTrue(handoff_agent_tools.issubset(handoff_inventory))
        self.assertTrue(otp_agent_tools.issubset(otp_inventory))
        self.assertNotEqual(handoff_inventory, otp_inventory)
        self.assertNotEqual(elevator_inventory, handoff_inventory)
        self.assertEqual(
            elevator_nodes["end"]["config"]["tool_choice"],
            "required",
        )
        self.assertIn(
            "handoff_to_next_request",
            report_instructions,
        )
        self.assertIn(
            "Your service ticket is [ticket_id]. Do you need",
            next_request_instructions,
        )
        self.assertIn(
            "Call end_service_call exactly once without speaking.",
            finalize_instructions,
        )
        goodbye = (
            "Thank you for calling the fictional elevator service. Goodbye."
        )
        self.assertEqual(
            elevator_edges["query_issue_to_finalize"]["transfer_message"],
            goodbye,
        )
        self.assertEqual(
            elevator_edges["next_request_to_finalize"]["transfer_message"],
            goodbye,
        )
        self.assertIn("spoken_message", human_handoff_instructions)
        self.assertIn("human_finalize", human_handoff_instructions)
        self.assertNotIn(
            "then go to finalize",
            human_handoff_instructions,
        )

    def test_elevator_safety_loop_has_no_unrelated_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = ElevatorConfig.from_environment(
                {"ELEVATOR_MCP_STATE_DIR": directory}
            )
            service = build_elevator_service(config, TOKEN)
            started = service.start_service_call(
                "call-safety-loop",
                "command-start-loop",
            )
            recorded = service.record_issue(
                "call-safety-loop",
                started["call_token"],
                "command-record-loop",
                "The elevator doors cannot open.",
            )
            statuses = {
                "entrapment_or_egress": "unknown",
                "injury_or_medical": "unknown",
                "fire_heat_or_smoke": "unknown",
                "flooding_or_electrical_hazard": "unknown",
                "unsafe_elevator_movement": "unknown",
            }
            expected_actions = (
                ("entrapment_or_egress", "check_injury"),
                ("injury_or_medical", "check_fire"),
                ("fire_heat_or_smoke", "check_flood_or_electrical"),
                (
                    "flooding_or_electrical_hazard",
                    "check_unsafe_movement",
                ),
                ("unsafe_elevator_movement", "clear"),
            )

            for index, (field, expected_action) in enumerate(
                expected_actions,
                start=1,
            ):
                statuses[field] = "clear"
                result = service.assess_safety(
                    "call-safety-loop",
                    started["call_token"],
                    f"command-safety-loop-{index}",
                    recorded["issue_handle"],
                    recorded["issue_revision"],
                    statuses,
                )
                self.assertTrue(result["ok"])
                self.assertEqual(result["action"], expected_action)
                self.assertNotIn("state_version", result)

        self.assertEqual(recorded["issue_revision"], 1)

    def test_elevator_safety_risk_cannot_be_downgraded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = ElevatorConfig.from_environment(
                {"ELEVATOR_MCP_STATE_DIR": directory}
            )
            service = build_elevator_service(config, TOKEN)
            started = service.start_service_call(
                "call-risk-latch",
                "command-start-risk-latch",
            )
            recorded = service.record_issue(
                "call-risk-latch",
                started["call_token"],
                "command-record-risk-latch",
                "The elevator is moving unexpectedly.",
            )
            risk = service.assess_safety(
                "call-risk-latch",
                started["call_token"],
                "command-risk-present",
                recorded["issue_handle"],
                recorded["issue_revision"],
                {
                    "entrapment_or_egress": "clear",
                    "injury_or_medical": "clear",
                    "fire_heat_or_smoke": "clear",
                    "flooding_or_electrical_hazard": "clear",
                    "unsafe_elevator_movement": "present",
                },
            )
            downgrade = service.assess_safety(
                "call-risk-latch",
                started["call_token"],
                "command-risk-downgrade",
                recorded["issue_handle"],
                recorded["issue_revision"],
                {
                    "entrapment_or_egress": "clear",
                    "injury_or_medical": "clear",
                    "fire_heat_or_smoke": "clear",
                    "flooding_or_electrical_hazard": "clear",
                    "unsafe_elevator_movement": "clear",
                },
            )
            replacement = service.record_issue(
                "call-risk-latch",
                started["call_token"],
                "command-risk-replacement",
                "A replacement issue must not clear the safety hazard.",
            )
            created = service.mock_zendesk_create_ticket(
                "call-risk-latch",
                started["call_token"],
                "command-risk-ticket",
                recorded["issue_handle"],
                recorded["issue_revision"],
                "100 Risk Avenue",
                "98052",
                True,
            )
            unresolved_call = service.start_service_call(
                "call-risk-unresolved",
                "command-start-risk-unresolved",
            )
            unresolved_issue = service.record_issue(
                "call-risk-unresolved",
                unresolved_call["call_token"],
                "command-record-risk-unresolved",
                "The caller cannot confirm whether the elevator is moving.",
            )
            unresolved = service.assess_safety(
                "call-risk-unresolved",
                unresolved_call["call_token"],
                "command-risk-unresolved",
                unresolved_issue["issue_handle"],
                unresolved_issue["issue_revision"],
                {
                    "entrapment_or_egress": "clear",
                    "injury_or_medical": "clear",
                    "fire_heat_or_smoke": "clear",
                    "flooding_or_electrical_hazard": "clear",
                    "unsafe_elevator_movement": "cannot_confirm",
                },
            )

        self.assertEqual("handoff", risk["action"])
        self.assertEqual("emergency", risk["handoff_reason"])
        self.assertEqual("handoff", downgrade["action"])
        self.assertEqual(
            "present",
            downgrade["statuses"]["unsafe_elevator_movement"],
        )
        self.assertFalse(replacement["ok"])
        self.assertEqual(
            "safety_handoff_required",
            replacement["reason_code"],
        )
        self.assertFalse(created["ok"])
        self.assertEqual("safety_clearance_required", created["reason_code"])
        self.assertEqual("handoff", unresolved["action"])
        self.assertEqual(
            "safety_unresolved",
            unresolved["handoff_reason"],
        )

    def test_elevator_call_id_cannot_collide_with_ticket_store(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = ElevatorConfig.from_environment(
                {"ELEVATOR_MCP_STATE_DIR": directory}
            )
            service = build_elevator_service(config, TOKEN)
            started = service.start_service_call(
                "tickets",
                "command-start-tickets",
            )
            restarted = build_elevator_service(config, TOKEN)

        self.assertTrue(started["ok"])
        self.assertIsNotNone(restarted)

    def test_elevator_service_uses_fictional_tickets_and_safety_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            config = ElevatorConfig.from_environment(
                {"ELEVATOR_MCP_STATE_DIR": str(state)}
            )
            service = build_elevator_service(config, TOKEN)
            started = service.start_service_call(
                "call-test-001",
                "command-start-001",
            )
            recorded = service.record_issue(
                "call-test-001",
                started["call_token"],
                "command-issue-001",
                "The elevator doors do not close reliably.",
            )
            safety = service.assess_safety(
                "call-test-001",
                started["call_token"],
                "command-safety-001",
                recorded["issue_handle"],
                recorded["issue_revision"],
                {
                    "entrapment_or_egress": "clear",
                    "injury_or_medical": "clear",
                    "fire_heat_or_smoke": "clear",
                    "flooding_or_electrical_hazard": "clear",
                    "unsafe_elevator_movement": "clear",
                },
            )
            created = service.mock_zendesk_create_ticket(
                "call-test-001",
                started["call_token"],
                "command-ticket-001",
                recorded["issue_handle"],
                recorded["issue_revision"],
                "100 Example Avenue",
                "98052",
                True,
            )
            queried = service.mock_zendesk_get_ticket_status(
                "call-test-001",
                started["call_token"],
                "command-status-001",
                created["ticket_id"],
            )
            restarted = build_elevator_service(config, TOKEN)
            restarted_call = restarted.start_service_call(
                "call-test-002",
                "command-start-002",
            )
            persisted = restarted.mock_zendesk_get_ticket_status(
                "call-test-002",
                restarted_call["call_token"],
                "command-status-002",
                created["ticket_id"],
            )

        self.assertTrue(started["ok"])
        for result in (
            started,
            recorded,
            safety,
            created,
            queried,
            restarted_call,
            persisted,
        ):
            self.assertNotIn("state_version", result)
        self.assertEqual(safety["action"], "clear")
        self.assertEqual(created["command"], "handoff_to_next_request")
        self.assertNotIn("ticket", created)
        self.assertEqual(
            queried["ticket"]["ticket_id"],
            created["ticket_id"],
        )
        self.assertEqual(
            {"ticket_id", "status", "estimated_visit"},
            set(queried["ticket"]),
        )
        self.assertEqual(
            persisted["ticket"]["ticket_id"],
            created["ticket_id"],
        )

    def test_missing_elevator_ticket_returns_complete_handoff_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = ElevatorConfig.from_environment(
                {"ELEVATOR_MCP_STATE_DIR": directory}
            )
            service = build_elevator_service(config, TOKEN)
            started = service.start_service_call(
                "call-missing-ticket",
                "command-start-missing-ticket",
            )
            result = service.mock_zendesk_get_ticket_status(
                "call-missing-ticket",
                started["call_token"],
                "command-query-missing-ticket",
                "missing-ticket",
            )

        self.assertTrue(result["ok"])
        self.assertEqual("handoff", result["action"])
        self.assertEqual("status_unresolved", result["handoff_reason"])
        self.assertIn("could not find", result["spoken_message"])

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
                    "ELEVATOR_MCP_STATE_DIR": str(state / "elevator"),
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
        for path in (
            ELEVATOR_SERVICE_PATH,
            FINANCE_HANDOFF_PATH,
            FINANCE_OTP_OFFICER_PATH,
        ):
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
