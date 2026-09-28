"""Offline checks for local and explicitly configured public origins."""

import unittest

from server import origin_allowed


class OriginTests(unittest.TestCase):
    def test_local_origin_is_allowed(self):
        self.assertTrue(origin_allowed("127.0.0.1:8080", "http",
                                       "http://127.0.0.1:8080"))

    def test_unconfigured_public_origin_is_rejected(self):
        self.assertFalse(origin_allowed("voice.example.com", "https",
                                        "https://voice.example.com"))

    def test_configured_public_origin_is_allowed(self):
        self.assertTrue(origin_allowed("voice.example.com", "http",
                                       "https://voice.example.com",
                                       "https://voice.example.com"))

    def test_mismatched_public_host_is_rejected(self):
        self.assertFalse(origin_allowed("attacker.example", "http",
                                        "https://voice.example.com",
                                        "https://voice.example.com"))


if __name__ == "__main__":
    unittest.main()
