# Copyright (c) Microsoft. All rights reserved.

import json
import tempfile
import unittest
from pathlib import Path

from tools.source_sync_status import (
    SYNC_MANIFEST,
    exact_drift,
    porcelain_paths,
    safe_relative,
)


class SourceSyncStatusTests(unittest.TestCase):
    def test_safe_relative_rejects_parent_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                safe_relative(Path(directory), "../outside")

    def test_exact_drift_accepts_identical_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            source_file = source / "same.txt"
            source_file.write_text("same", encoding="utf-8")
            destination = Path(__file__).resolve().parents[1] / "same-test.txt"
            try:
                destination.write_text("same", encoding="utf-8")
                self.assertIsNone(
                    exact_drift(
                        source,
                        "WORKTREE",
                        {
                            "source": "same.txt",
                            "destination": "same-test.txt",
                            "action": "exact",
                        },
                    )
                )
            finally:
                destination.unlink(missing_ok=True)

    def test_non_exact_mapping_does_not_require_byte_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(
                exact_drift(
                    Path(directory),
                    "WORKTREE",
                    {
                        "source": "missing-source.py",
                        "destination": "missing-destination.py",
                        "action": "adapted",
                    },
                )
            )

    def test_porcelain_paths_preserves_both_sides_of_renames(self) -> None:
        self.assertEqual(
            {"new-name.py", "old-name.py", "regular.py"},
            porcelain_paths(
                b"R  new-name.py\0old-name.py\0 M regular.py\0"
            ),
        )

    def test_manifest_tracks_shared_mcp_source_review(self) -> None:
        manifest = json.loads(
            SYNC_MANIFEST.read_text(encoding="utf-8")
        )
        mcp = manifest["mcp_source"]
        self.assertEqual("docs/voice_agent/11_mcp_server", mcp["root"])
        self.assertIn("../shared_mcp", mcp["review_targets"])
        self.assertIn("templates.config.json", mcp["review_targets"])

    def test_manifest_tracks_template_inputs_and_public_sample_definitions(
        self,
    ) -> None:
        manifest = json.loads(
            SYNC_MANIFEST.read_text(encoding="utf-8")
        )
        mappings = {
            item["root"]: item
            for item in manifest["sample_mappings"]
        }
        self.assertEqual(
            "adapted",
            mappings["template_config"]["action"],
        )
        for root in (
            "template_example1",
            "template_example2",
        ):
            self.assertEqual("exact", mappings[root]["action"])
            self.assertEqual(
                "voice_agent",
                mappings[root]["destination_root"],
            )

    def test_manifest_accepts_the_latest_template_pr_revision(self) -> None:
        manifest = json.loads(
            SYNC_MANIFEST.read_text(encoding="utf-8")
        )
        source = manifest["source"]
        self.assertEqual(
            "feb7ee1e1ab0cad98e630ba5f83a778fc3db1842",
            source["base_commit"],
        )
        self.assertEqual(
            "refs/heads/agents/add-voice-agent-template-prototypes",
            source["accepted_ref"],
        )
        self.assertEqual("2026-09-17", source["accepted_on"])
        omitted = {
            item["source"]: item
            for item in manifest["template_mappings"]
            if item["action"] == "omitted"
        }
        self.assertIn("test_static_contract.py", omitted)
        self.assertIn("ACA image packaging", omitted["test_static_contract.py"]["reason"])


if __name__ == "__main__":
    unittest.main()
