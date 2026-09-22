"""Offline contracts for the Linux/WSL local setup entry points."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "scripts" / "setup-local-examples.sh"
MANAGER = ROOT / "scripts" / "manage-local-mcp-and-ui.sh"
LOGIN = ROOT / "scripts" / "login-devtunnel.sh"
MCP_E2E = ROOT / "shared_mcp" / "scripts" / "e2e-local.sh"


def shell_function(source: str, name: str) -> str:
    start = source.index(f"{name}() {{")
    end = source.index("\n}\n", start) + 3
    return source[start:end]


class LocalSetupScriptContractTests(unittest.TestCase):
    def test_shell_entry_points_parse(self):
        subprocess.run(
            ["bash", "-n", str(SETUP), str(MANAGER), str(LOGIN)],
            check=True,
            cwd=ROOT,
        )

    def test_node_is_ensured_after_base_tools(self):
        source = SETUP.read_text(encoding="utf-8")
        base_tools = shell_function(source, "check_base_tools")

        self.assertNotIn("require_command node", base_tools)
        self.assertNotIn("node --version", base_tools)
        self.assertLess(
            source.rindex("check_base_tools\n"),
            source.rindex("ensure_node\n"),
        )
        self.assertIn("latest-v22.x/SHASUMS256.txt", source)
        self.assertIn("Node.js archive checksum verification failed", source)

    def test_minimal_python_can_bootstrap_component_pip(self):
        source = SETUP.read_text(encoding="utf-8")
        installer = shell_function(source, "install_python_environment")

        self.assertIn("import ensurepip", installer)
        self.assertIn("venv --without-pip", installer)
        self.assertIn("https://bootstrap.pypa.io/get-pip.py", installer)
        self.assertIn('"${python}" -m pip --version', installer)

    def test_lifecycle_commands_discover_repo_local_tools(self):
        setup_source = SETUP.read_text(encoding="utf-8")
        manager_source = MANAGER.read_text(encoding="utf-8")

        self.assertIn("${LOCAL_NODE_ROOT}/bin:", setup_source)
        self.assertIn("${LOCAL_DEVTUNNEL_ROOT}/bin:", setup_source)
        self.assertIn("${LOCAL_TOOLS_ROOT}/node/bin:", manager_source)
        self.assertIn("${LOCAL_TOOLS_ROOT}/devtunnel/bin:", manager_source)

    def test_devtunnel_login_uses_repo_cli_and_mcp_working_directory(self):
        source = LOGIN.read_text(encoding="utf-8")

        self.assertIn(".local-mcp-and-ui/tools/devtunnel/bin/devtunnel", source)
        self.assertIn("user login --github --use-device-code-auth", source)
        self.assertNotIn("--entra", source)
        self.assertIn('cd "${ROOT}/shared_mcp"', source)
        self.assertIn("--use-device-code-auth", source)

    def test_setup_recommends_github_devtunnel_login(self):
        source = SETUP.read_text(encoding="utf-8")
        authentication = shell_function(source, "check_authentication")

        self.assertIn("required GitHub device-code authentication", authentication)
        self.assertIn("./scripts/login-devtunnel.sh", authentication)
        self.assertNotIn("For Microsoft Entra", authentication)

    def test_local_mcp_e2e_recommends_github_wrapper(self):
        source = MCP_E2E.read_text(encoding="utf-8")

        self.assertIn("scripts/login-devtunnel.sh", source)
        self.assertNotIn("--entra", source)


if __name__ == "__main__":
    unittest.main()