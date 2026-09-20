"""Offline tests for the preview Voice Agent SDK sample helpers."""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voice_agent_sdk_common import (
    EventPrinter,
    _canonical_definition,
    _load_settings,
    _realtime_url,
    _validate_agent_name,
    _validate_project_endpoint,
    load_materialized_agent,
)


class VoiceAgentSdkCommonTests(unittest.TestCase):
    def test_validates_project_endpoint_and_agent_name(self) -> None:
        endpoint = "https://account.services.ai.azure.com/api/projects/project"
        self.assertEqual(_validate_project_endpoint(endpoint + "/"), endpoint)
        self.assertEqual(_validate_agent_name("sdk-sample-agent"), "sdk-sample-agent")

        with self.assertRaises(ValueError):
            _validate_project_endpoint("https://<account>/api/projects/<project>")
        with self.assertRaises(ValueError):
            _validate_project_endpoint("https://evil.example/api/projects/stolen")
        with self.assertRaises(ValueError):
            _validate_project_endpoint(
                "https://account.services.ai.azure.com.evil.example/api/projects/stolen"
            )
        with self.assertRaises(ValueError):
            _validate_agent_name("invalid agent name")

    def test_materializes_each_sample_without_environment_leakage(self) -> None:
        template = {
            "name": "template-name",
            "description": "test",
            "definition": {
                "kind": "voice",
                "model_type": "managed",
                "model": "default-model",
                "tools": [
                    {
                        "type": "mcp",
                        "server_label": "tools",
                        "server_url": "",
                        "project_connection_id": "",
                    }
                ],
            },
        }
        environments = [
            (
                "first-agent",
                "first-model",
                "https://first.example/mcp",
                "first-connection",
            ),
            (
                "second-agent",
                "second-model",
                "https://second.example/mcp",
                "second-connection",
            ),
        ]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sample_dirs = []
            for index, values in enumerate(environments):
                agent_name, model, server_url, connection_id = values
                sample_dir = root / str(index)
                sample_dir.mkdir()
                (sample_dir / "agent.json").write_text(
                    json.dumps(template),
                    encoding="utf-8",
                )
                (sample_dir / ".env").write_text(
                    "\n".join(
                        [
                            "AZURE_AI_PROJECT_ENDPOINT="
                            "https://account.services.ai.azure.com/api/projects/project",
                            f"VOICE_AGENT_NAME={agent_name}",
                            f"VOICE_AGENT_MODEL={model}",
                            f"VOICE_AGENT_MCP_SERVER_URL={server_url}",
                            f"VOICE_AGENT_MCP_CONNECTION_ID={connection_id}",
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
                sample_dirs.append(sample_dir)

            with patch.dict(os.environ, {}, clear=True):
                first_name, _, first = load_materialized_agent(sample_dirs[0])
                second_name, _, second = load_materialized_agent(sample_dirs[1])

        self.assertEqual(first_name, "first-agent")
        self.assertEqual(second_name, "second-agent")
        self.assertEqual(first["model_type"], "managed")
        self.assertEqual(second["model_type"], "managed")
        self.assertEqual(first["model"], "first-model")
        self.assertEqual(second["model"], "second-model")
        self.assertEqual(
            first["tools"][0]["project_connection_id"],
            "first-connection",
        )
        self.assertEqual(
            second["tools"][0]["project_connection_id"],
            "second-connection",
        )

    def test_mcp_config_switch_overrides_sample_mcp_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sample_dir = Path(directory)
            config_dir = sample_dir / "config"
            config_dir.mkdir()
            (config_dir / "shared.env").write_text(
                "\n".join(
                    [
                        "VOICE_AGENT_MCP_SERVER_URL="
                        "https://shared.example/mcp/finance",
                        "VOICE_AGENT_MCP_CONNECTION_ID=shared-connection",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (sample_dir / ".env").write_text(
                "\n".join(
                    [
                        "AZURE_AI_PROJECT_ENDPOINT="
                        "https://account.services.ai.azure.com/api/projects/project",
                        "VOICE_AGENT_MCP_CONFIG=config/shared.env",
                        "VOICE_AGENT_MCP_SERVER_URL=https://internal.example/mcp",
                        "VOICE_AGENT_MCP_CONNECTION_ID=internal-connection",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                settings = _load_settings(sample_dir)

        self.assertEqual(
            settings["VOICE_AGENT_MCP_SERVER_URL"],
            "https://shared.example/mcp/finance",
        )
        self.assertEqual(
            settings["VOICE_AGENT_MCP_CONNECTION_ID"],
            "shared-connection",
        )

    def test_mcp_config_switch_reports_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sample_dir = Path(directory)
            (sample_dir / ".env").write_text(
                "VOICE_AGENT_MCP_CONFIG=missing.env\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "VOICE_AGENT_MCP_CONFIG does not exist",
                ):
                    _load_settings(sample_dir)

    def test_canonicalizes_service_audio_defaults(self) -> None:
        authored = {
            "audio": {
                "input": {
                    "turn_detection": {
                        "remove_filler_words": False,
                    }
                },
                "output": {
                    "voice": "en-US-AvaNeural",
                    "voice_type": "azure-standard",
                },
            }
        }
        readback = {
            "audio": {
                "input": {"turn_detection": {}},
                "output": {
                    "voice": {
                        "type": "azure-standard",
                        "name": "en-US-AvaNeural",
                    }
                },
            }
        }
        self.assertEqual(
            _canonical_definition(authored),
            _canonical_definition(readback),
        )

    def test_builds_encoded_realtime_url(self) -> None:
        url = _realtime_url(
            "https://account.services.ai.azure.com/api/projects/project",
            "sample-agent",
            "session-id",
        )
        self.assertEqual(
            url,
            "wss://account.services.ai.azure.com/api/projects/project/"
            "agents/sample-agent/endpoint/protocols/voice"
            "?api-version=v1&agent_session_id=session-id",
        )

    def test_committed_directory_scenarios_match_expected_shapes(self) -> None:
        samples = Path(__file__).resolve().parent
        common_settings = {
            "AZURE_AI_PROJECT_ENDPOINT": (
                "https://account.services.ai.azure.com/api/projects/project"
            ),
            "AZURE_CREDENTIAL_MODE": "default",
            "VOICE_AGENT_MODEL": "gpt-realtime",
            "VOICE_AGENT_MCP_SERVER_URL": "https://tools.example/mcp",
        }
        _, _, finance = load_materialized_agent(
            samples / "example1_finance_with_handoff",
            {
                **common_settings,
                "VOICE_AGENT_NAME": "finance-test",
                "VOICE_AGENT_MCP_CONNECTION_ID": "finance-connection",
            },
        )
        _, _, otp_officer_search = load_materialized_agent(
            samples / "example2_finance_with_OTP_and_Officer_Search",
            {
                **common_settings,
                "VOICE_AGENT_NAME": "finance-otp-officer-search-test",
                "VOICE_AGENT_MCP_CONNECTION_ID": "finance-otp-officer-search-connection",
            },
        )
        _, _, elevator_service = load_materialized_agent(
            samples / "example3_elevator_service_with_safety_zendesk_and_handoff",
            {
                **common_settings,
                "VOICE_AGENT_NAME": "elevator-service-test",
                "VOICE_AGENT_MCP_CONNECTION_ID": "elevator-service-connection",
            },
        )


        self.assertEqual(finance["model_type"], "managed")
        self.assertEqual(finance["model"], "gpt-realtime")
        self.assertEqual(len(finance["handoff"]["nodes"]), 13)
        self.assertEqual(len(finance["handoff"]["edges"]), 24)

        self.assertEqual(otp_officer_search["model_type"], "managed")
        self.assertEqual(otp_officer_search["model"], "gpt-realtime")
        self.assertNotIn("handoff", otp_officer_search)
        self.assertEqual(
            otp_officer_search["tools"][0]["allowed_tools"],
            [
                "verify_caller_otp",
                "calculate_loan_offer",
                "record_loan_interest",
                "auto_assign_loan_officer",
                "search_loan_officer",
                "confirm_loan_officer",
                "end_call",
            ],
        )
        self.assertEqual(elevator_service["model_type"], "managed")
        self.assertEqual(elevator_service["model"], "gpt-realtime")
        self.assertEqual(
            "en-US-Ava:DragonHDLatestNeural",
            elevator_service["audio"]["output"]["voice"]["name"],
        )
        self.assertEqual(
            "azure-standard",
            elevator_service["audio"]["output"]["voice"]["type"],
        )
        self.assertEqual(len(elevator_service["handoff"]["nodes"]), 9)
        self.assertEqual(len(elevator_service["handoff"]["edges"]), 17)
        query_edge = next(
            edge
            for edge in elevator_service["handoff"]["edges"]
            if edge["id"] == "intent_router_to_query_issue"
        )
        self.assertEqual("auto", query_edge["target_response"])
        self.assertNotIn("transfer_message", query_edge)
        report_issue = next(
            node
            for node in elevator_service["handoff"]["nodes"]
            if node["id"] == "report_issue"
        )
        self.assertEqual(
            [
                "record_issue",
                "assess_safety",
                "mock_zendesk_create_ticket",
            ],
            report_issue["config"]["tools"][0]["allowed_tools"],
        )
        query_issue = next(
            node
            for node in elevator_service["handoff"]["nodes"]
            if node["id"] == "query_issue"
        )
        self.assertEqual(
            ["mock_zendesk_get_ticket_status"],
            query_issue["config"]["tools"][0]["allowed_tools"],
        )
        human_handoff = next(
            node
            for node in elevator_service["handoff"]["nodes"]
            if node["id"] == "human_handoff"
        )
        self.assertEqual(
            ["request_human_handoff"],
            human_handoff["config"]["tools"][0]["allowed_tools"],
        )
        self.assertNotIn(
            "transfer_call",
            {
                tool.get("name")
                for node in elevator_service["handoff"]["nodes"]
                for tool in node["config"]["tools"]
            },
        )

    def test_example1_variants_share_workflow_and_pin_runtime(self) -> None:
        sample_dir = (
            Path(__file__).resolve().parent / "example1_finance_with_handoff"
        )
        settings = {
            "AZURE_AI_PROJECT_ENDPOINT": (
                "https://account.services.ai.azure.com/api/projects/project"
            ),
            "AZURE_CREDENTIAL_MODE": "default",
            "VOICE_AGENT_NAME": "stale-env-agent",
            "VOICE_AGENT_MODEL": "stale-env-model",
            "VOICE_AGENT_MCP_SERVER_URL": "https://tools.example/mcp",
            "VOICE_AGENT_MCP_CONNECTION_ID": "finance-connection",
        }
        with patch.dict(os.environ, {}, clear=True):
            realtime_name, _, realtime = load_materialized_agent(
                sample_dir,
                settings,
                agent_file="agent.realtime.json",
                prefer_document_name=True,
            )
            cascade_name, _, cascade = load_materialized_agent(
                sample_dir,
                settings,
                agent_file="agent.cascade-luna.json",
                prefer_document_name=True,
            )

        self.assertEqual("finance-example-realtime", realtime_name)
        self.assertEqual("finance-example-cascade-luna", cascade_name)
        self.assertEqual(realtime["handoff"], cascade["handoff"])
        self.assertEqual(
            {
                "type": "template",
                "text": (
                    "Hello, thank you for taking the call. "
                    "This is Virtual Finance calling."
                ),
            },
            realtime["greeting"],
        )
        edges = {
            edge["id"]: edge for edge in realtime["handoff"]["edges"]
        }
        self.assertEqual(
            (
                "Thank you. This call is to introduce a personal loan offer. "
                "Please hold for a moment while I bring up the call details."
            ),
            edges["entrypoint_to_dial_assess"]["transfer_message"],
        )
        self.assertEqual(
            (
                "Before I share the details, please hold while I confirm who "
                "I'm speaking with."
            ),
            edges["dial_assess_to_rpc"]["transfer_message"],
        )
        rpc = next(
            node
            for node in realtime["handoff"]["nodes"]
            if node["id"] == "rpc"
        )
        self.assertIn(
            "Am I speaking with <calling_first_name>?",
            " ".join(rpc["config"]["instructions"].split()),
        )
        end = next(
            node
            for node in realtime["handoff"]["nodes"]
            if node["id"] == "end"
        )
        self.assertEqual(
            {
                "type": "system",
                "name": "end_conversation",
                "description": (
                    "End the active conversation only after its business "
                    "disposition has been recorded. First say one brief, "
                    "context-appropriate closing sentence, then call "
                    "end_conversation as a separate final output item in the "
                    "same response with only a non-empty reason. Produce no "
                    "content after the tool call."
                ),
            },
            end["config"]["tools"][0],
        )
        self.assertEqual("gpt-realtime-2.1", realtime["model"])
        self.assertEqual(
            "whisper-1",
            realtime["audio"]["input"]["transcription"]["model"],
        )
        self.assertIsNone(
            realtime["audio"]["input"]["turn_detection"][
                "end_of_utterance_detection"
            ]
        )
        self.assertEqual(
            "en-IN-Diya:DragonHDLatestNeural",
            realtime["audio"]["output"]["voice"]["name"],
        )
        self.assertEqual("gpt-5.6-luna", cascade["model"])
        self.assertEqual(
            "azure-speech",
            cascade["audio"]["input"]["transcription"]["model"],
        )
        self.assertEqual(
            {
                "model": "smart_end_of_turn_detection",
                "threshold_level": "medium",
                "timeout_ms": 2000,
            },
            cascade["audio"]["input"]["turn_detection"][
                "end_of_utterance_detection"
            ],
        )
        self.assertEqual(
            "en-IN-Diya:DragonHDLatestNeural",
            cascade["audio"]["output"]["voice"]["name"],
        )

    def test_sample_env_defaults_match_committed_model_mode(self) -> None:
        samples = Path(__file__).resolve().parent
        for directory in (
            "example1_finance_with_handoff",
            "example2_finance_with_OTP_and_Officer_Search",
            "example3_elevator_service_with_safety_zendesk_and_handoff",
        ):
            sample = samples / directory
            definition = json.loads(
                (sample / "agent.json").read_text(encoding="utf-8")
            )["definition"]
            defaults = {
                key.strip(): value.strip()
                for line in (sample / ".env.example").read_text(
                    encoding="utf-8"
                ).splitlines()
                if line and not line.startswith("#") and "=" in line
                for key, value in [line.split("=", 1)]
            }
            self.assertEqual(definition["model_type"], "managed")
            self.assertNotIn("VOICE_AGENT_MODEL_TYPE", defaults)
            if directory == "example1_finance_with_handoff":
                self.assertNotIn("VOICE_AGENT_MODEL", defaults)
            else:
                self.assertEqual(
                    defaults["VOICE_AGENT_MODEL"],
                    definition["model"],
                )

    def test_counts_handoff_and_mcp_call_evidence(self) -> None:
        printer = EventPrinter(verbose=False)
        with contextlib.redirect_stdout(io.StringIO()):
            printer.show(
                {
                    "type": "response.done",
                    "response": {
                        "output": [
                            {
                                "type": "function_call",
                                "name": "handoff",
                            }
                        ]
                    },
                }
            )
            printer.show({"type": "response.mcp_call.completed"})
            printer.show({"type": "mcp_list_tools.completed"})

        summary = printer.summary("agent", "session")
        self.assertEqual(summary["handoff_events"], 1)
        self.assertEqual(summary["mcp_events"], 2)
        self.assertEqual(summary["mcp_call_events"], 1)

if __name__ == "__main__":
    unittest.main()
