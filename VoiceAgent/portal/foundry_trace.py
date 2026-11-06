from __future__ import annotations

import base64
import uuid
from urllib.parse import quote, urlencode

DEFAULT_PROVIDER = "Microsoft.CognitiveServices"
# Match the preview trace link already used by ../samples/foundry_trace_url.py;
# do not enable unrelated internal feature flights.
FOUNDRY_TRACE_FLIGHTS = ("voice_agent_bundle",)


def compress_subscription_id(subscription_id: str) -> str:
    raw = uuid.UUID(subscription_id).bytes
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def encode_project_resource_context(
    *,
    subscription_id: str,
    resource_group: str,
    account_name: str,
    project_name: str,
    provider: str = DEFAULT_PROVIDER,
) -> str:
    provider_segment = (
        ""
        if provider == DEFAULT_PROVIDER
        else quote(provider, safe="")
    )
    return ",".join(
        (
            compress_subscription_id(subscription_id),
            quote(resource_group, safe=""),
            provider_segment,
            quote(account_name, safe=""),
            quote(project_name, safe=""),
        )
    )


def build_foundry_trace_url(
    *,
    subscription_id: str,
    resource_group: str,
    account_name: str,
    project_name: str,
    agent_name: str,
) -> str:
    """Build the Microsoft Foundry agent-traces URL used by the sample portal."""

    encoded_resource = encode_project_resource_context(
        subscription_id=subscription_id,
        resource_group=resource_group,
        account_name=account_name,
        project_name=project_name,
    )
    path = (
        "https://ai.azure.com/nextgen/r/"
        f"{encoded_resource}/build/agents/{quote(agent_name, safe='')}/traces"
    )
    return f"{path}?{urlencode({'flight': ','.join(FOUNDRY_TRACE_FLIGHTS)})}"
