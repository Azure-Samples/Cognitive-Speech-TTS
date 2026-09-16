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

    def test_committed_finance_scenarios_match_expected_shapes(self) -> None:
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
