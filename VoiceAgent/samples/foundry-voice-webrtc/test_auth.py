"""Offline checks for local and Azure-hosted credential selection."""

import os
import unittest
from unittest.mock import patch

from auth import authentication_mode


class AuthenticationModeTests(unittest.TestCase):
    def test_uses_cli_outside_azure_host(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(authentication_mode(), "azure_cli")

    def test_uses_managed_identity_in_container_apps(self):
        with patch.dict(os.environ, {"IDENTITY_ENDPOINT": "http://localhost/identity"}, clear=True):
            self.assertEqual(authentication_mode(), "managed_identity")


if __name__ == "__main__":
    unittest.main()
