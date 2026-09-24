"""Offline checks for the requested Azure session persistence setting."""

import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from server import Settings


class StoreTests(unittest.TestCase):
    def test_page_discloses_storage(self):
        page = (Path(__file__).parent / "public" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Azure conversation/audio storage is enabled", page)
        self.assertNotIn("requests storage off", page)

    def test_both_transports_request_storage(self):
        cfg = Settings("https://example.services.ai.azure.com/api/projects/demo", "hello")
        for transport in ("websocket", "webrtc"):
            with self.subTest(transport=transport):
                query = parse_qs(urlsplit(cfg.voice_url(transport)).query)
                self.assertEqual(query["store"], ["true"])
                self.assertEqual(query.get("transport"),
                                 ["webrtc"] if transport == "webrtc" else None)


if __name__ == "__main__":
    unittest.main()
