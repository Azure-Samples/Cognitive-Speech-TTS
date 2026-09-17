# Copyright (c) Microsoft. All rights reserved.
"""Public-release regressions; use only checked-in files and synthetic events."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from session_log import SessionRecorder, _clip


class ReleaseArtifactTests(unittest.TestCase):
    def test_source_alias_keeps_the_commit_without_publishing_a_clone_url(self):
        upstream = json.loads((ROOT / "UPSTREAM.json").read_text(encoding="utf-8"))["upstream"]
        self.assertEqual(upstream["source_id"], "voice-agent-demo")
        self.assertNotIn("repository", upstream)
        self.assertRegex(upstream["commit"], r"^[0-9a-f]{40}$")
        self.assertTrue(upstream["path"].endswith("/voice_demo"))

    def test_stack_manager_launches_from_owned_directories(self):
        script = (
            ROOT.parent / "scripts/manage-local-mcp-and-ui.sh"
        ).read_text(encoding="utf-8")
        self.assertIn('cd "${MCP_ROOT}"', script)
        self.assertIn('cd "${UI_ROOT}"', script)
        self.assertIn("exec setsid env", script)

    def test_shipped_notices_cover_browser_dependencies(self):
        notice = (ROOT / "static/THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")
        self.assertIn("Copyright (C) 2011-2015 by Vitaly Puzrin", notice)
        self.assertIn("Copyright (c) Facebook, Inc. and its affiliates.", notice)
        self.assertEqual(notice.count("Permission is hereby granted"), 2)
        locked = json.loads((ROOT / "web/package-lock.json").read_text(encoding="utf-8"))["packages"]
        for name, label in {"react": "React", "react-dom": "React DOM",
                            "scheduler": "Scheduler", "js-yaml": "js-yaml"}.items():
            self.assertIn(f"{label} {locked[f'node_modules/{name}']['version']}", notice)
        # A development installation allows an exact notice comparison; running
        # the portal/tests with checked-in assets alone never requires Node.js.
        for name in ("react", "react-dom", "scheduler", "js-yaml"):
            with self.subTest(package=name):
                license_path = ROOT / "web/node_modules" / name / "LICENSE"
                if license_path.is_file():
                    self.assertIn(license_path.read_text(encoding="utf-8").strip(), notice)

    def test_built_and_watch_bundles_retain_notice_references(self):
        package = json.loads((ROOT / "web/package.json").read_text(encoding="utf-8"))
        for name in ("build", "build:webrtc", "watch", "watch:webrtc"):
            self.assertIn("THIRD_PARTY_NOTICES.txt", package["scripts"][name])
            self.assertIn("--legal-comments=eof", package["scripts"][name])
        for name in ("bundle.js", "webrtc-bundle.js"):
            text = (ROOT / "static" / name).read_text(encoding="utf-8")
            self.assertIn("THIRD_PARTY_NOTICES.txt", text.splitlines()[0])
            self.assertIn("Copyright (c) Facebook", text)


class SerializedToolRedactionTests(unittest.TestCase):
    def test_arguments_are_redacted_without_changing_the_protocol_input(self):
        frame = {
            "type": "response.output_item.done",
            "item": {"arguments": json.dumps({
                "api_key": "SYNTHETIC_KEY", "city": "Paris",
                "headers": {"Authorization": "SYNTHETIC_AUTH"},
            })},
        }
        original = copy.deepcopy(frame)
        redacted = _clip(frame)
        self.assertEqual(frame, original)
        self.assertIsInstance(redacted["item"]["arguments"], str)
        self.assertEqual(json.loads(redacted["item"]["arguments"]), {
            "api_key": "<redacted>", "city": "Paris",
            "headers": {"Authorization": "<redacted>"},
        })

    def test_json_outputs_and_nested_mcp_text_are_redacted(self):
        output = json.dumps({"content": [{
            "type": "text",
            "text": json.dumps({"access_token": "SYNTHETIC_TOKEN", "answer": 42}),
        }]})
        frame = _clip({"item": {"output": output}})
        payload = json.loads(frame["item"]["output"])
        self.assertEqual(json.loads(payload["content"][0]["text"]), {
            "access_token": "<redacted>", "answer": 42,
        })

    def test_double_encoded_json_is_sanitized_without_losing_string_types(self):
        value = json.dumps(json.dumps({"password": "SYNTHETIC_PASSWORD", "ok": True}))
        clean = _clip({"result": value})["result"]
        self.assertEqual(json.loads(json.loads(clean)), {"password": "<redacted>", "ok": True})

    def test_invalid_or_oversized_json_fails_closed(self):
        for value in ('{"api_key":"SYNTHETIC_UNCLOSED"', json.dumps({
            "api_key": "SYNTHETIC_OVERSIZED", "large": "x" * (65 * 1024),
        })):
            with self.subTest(size=len(value)):
                clean = _clip({"arguments": value})["arguments"]
                self.assertIn("<omitted:", clean)
                self.assertNotIn("SYNTHETIC", clean)

    def test_plain_text_results_and_regular_fields_remain_readable(self):
        self.assertEqual(_clip({"output": "The answer is 42.", "status": "completed"}), {
            "output": "The answer is 42.", "status": "completed",
        })
        self.assertEqual(_clip({"instructions": "{customer_name}, welcome."})["instructions"],
                         "{customer_name}, welcome.")
        self.assertIn("(+100 chars)", _clip({"output": "x" * 500})["output"])

    def test_deep_tool_payloads_are_bounded(self):
        value = {"secret": "SYNTHETIC_DEEP"}
        for _ in range(30):
            value = {"child": value}
        clean = json.dumps(_clip({"arguments": json.dumps(value)}))
        self.assertNotIn("SYNTHETIC_DEEP", clean)
        self.assertIn("nesting limit", clean)

    def test_recorder_writes_only_sanitized_tool_frames(self):
        with tempfile.TemporaryDirectory(prefix="voice-portal-release-") as directory:
            root = Path(directory).resolve()
            self.assertTrue(root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
            recorder = SessionRecorder(root, web_id="release-test", agent="synthetic",
                                       backend="synthetic", upstream="wss://example.invalid")
            raw = json.dumps({"type": "response.output_item.done", "item": {
                "id": "tool-item", "type": "function_call", "name": "lookup",
                "arguments": '{"client_secret":"SYNTHETIC_DISK_SECRET","query":"weather"}',
            }})
            recorder.record("down", raw)
            recorder.close()
            saved = (recorder.dir / "events.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("SYNTHETIC_DISK_SECRET", saved)
            self.assertIn("weather", saved)
            self.assertIn("<redacted>", saved)
            self.assertIn("SYNTHETIC_DISK_SECRET", raw)


if __name__ == "__main__":
    unittest.main()
