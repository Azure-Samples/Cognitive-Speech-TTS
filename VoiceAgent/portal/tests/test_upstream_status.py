# Copyright (c) Microsoft. All rights reserved.
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import upstream_status as tracking


class UpstreamTrackingTests(unittest.TestCase):
    def test_reports_added_changed_removed_files(self):
        self.assertEqual(
            tracking.compare({"same": "a", "old": "b", "edit": "c"}, {"same": "a", "new": "d", "edit": "e"}),
            {"added": ["new"], "removed": ["old"], "changed": ["edit"]},
        )

    def test_record_keeps_upstream_hashes_and_distinguishes_local_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.py").write_bytes(b"ported")
            (root / "README.md").write_bytes(b"local instructions")
            (root / ".env").write_bytes(b"never include this")
            (root / ".venv").mkdir()
            (root / ".venv" / "secret").write_bytes(b"never include this")
            manifest = {
                "upstream": {"commit": "original-pin"},
                "files": [
                    {"path": "source.py", "upstream_sha256": tracking.sha256(b"source"), "action": "copied"},
                    {"path": "internal.txt", "upstream_sha256": "x", "action": "omitted", "reason": "private artifact"},
                ],
            }
            tracking.record_local(root, manifest)
            self.assertEqual(manifest["upstream"]["commit"], "original-pin")
            self.assertEqual(manifest["files"][0]["action"], "modified")
            self.assertEqual(manifest["files"][0]["upstream_sha256"], tracking.sha256(b"source"))
            self.assertEqual(set(manifest["local_files"]), {"README.md"})
            self.assertEqual(tracking.expected_local(manifest), tracking.local_files(root))
            (root / "internal.txt").write_bytes(b"accidental copy")
            with self.assertRaises(ValueError):
                tracking.record_local(root, manifest)

    def test_paths_cannot_escape_portal(self):
        for relative in ("../secret", "/etc/passwd", "C:/secret", "folder\\secret"):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                tracking.safe_path(ROOT, relative)
        self.assertEqual(tracking.safe_path(ROOT, "web/package.json"), ROOT / "web" / "package.json")


if __name__ == "__main__":
    unittest.main()
