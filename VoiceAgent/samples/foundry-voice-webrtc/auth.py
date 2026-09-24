"""Server-side Entra tokens from the user's Azure CLI login; never resource keys."""

import os
import shutil
from pathlib import Path

SCOPE = "https://ai.azure.com/.default"


class AuthenticationError(Exception):
    """A safe user-facing authentication error, without credential details."""


def find_azure_cli():
    """Locate az, including a new Windows install before terminal PATH refreshes."""
    executable = shutil.which("az")
    if executable:
        return executable
    if os.name == "nt":
        for folder in ["C:/Program Files", "C:/Program Files (x86)"]:
            executable = Path(folder) / "Microsoft SDKs/Azure/CLI2/wbin/az.cmd"
            if executable.is_file():
                return str(executable)
    return None


def _create_credential():
    """Use Azure Identity's supported CLI adapter, not shell-built commands."""
    executable = find_azure_cli()
    if not executable:
        raise AuthenticationError("Azure CLI is not installed or cannot be found. Install it, open a normal PowerShell window and run az login.")
    if not shutil.which("az"):
        os.environ["PATH"] = str(Path(executable).parent) + os.pathsep + os.environ.get("PATH", "")
    try:
        from azure.identity.aio import AzureCliCredential
    except ImportError as error:
        raise AuthenticationError("The Azure authentication dependency could not load. In the server's Python environment, run python -m pip install -r requirements.txt.") from error
    return AzureCliCredential(process_timeout=20)


class AzureCliTokenProvider:
    """Request a token for each new call; Azure CLI handles cached-token renewal."""

    async def get_token(self, client=None):
        credential = _create_credential()
        try:
            async with credential:
                token = await credential.get_token(SCOPE)
        except Exception as error:
            # Raw SDK errors may contain account details. Do not forward them.
            raise AuthenticationError("Azure CLI could not obtain a Foundry token. Run az login in a normal PowerShell window, select the correct tenant/subscription, then retry. The server must run as the same Windows user with outbound network access.") from error
        if not token.token or not token.token.isascii() or any(c.isspace() for c in token.token):
            raise AuthenticationError("Azure CLI returned an invalid token. Run az login again.")
        return token.token
