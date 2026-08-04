"""Build the Azure AI Foundry traces-page URL for a voice agent."""

from __future__ import annotations

import base64
import uuid
from typing import Any
from urllib.parse import quote, unquote, urlencode, urlparse

import aiohttp
from azure.core.credentials_async import AsyncTokenCredential

MANAGEMENT_SCOPE = "https://management.azure.com/.default"
SUBSCRIPTIONS_URL = (
    "https://management.azure.com/subscriptions?api-version=2022-12-01"
)
RESOURCE_GRAPH_URL = (
    "https://management.azure.com/providers/Microsoft.ResourceGraph/resources"
    "?api-version=2022-10-01"
)
DEFAULT_PROVIDER = "Microsoft.CognitiveServices"
TRACE_FLIGHTS = (
    "voice_first_experience",
    "voice_agent_bundle",
    "voice_first_agent_query_auth_dynamic_resource",
)


def _parse_project_endpoint(endpoint: str) -> tuple[str, str]:
    """Extract the globally unique account name and project name."""
    parsed = urlparse(endpoint)
    if not parsed.hostname:
        raise ValueError("The Foundry project endpoint has no host name.")
    account_name = parsed.hostname.split(".", 1)[0]

    segments = [unquote(segment) for segment in parsed.path.split("/") if segment]
    try:
        project_index = segments.index("projects")
        project_name = segments[project_index + 1]
    except (ValueError, IndexError) as error:
        raise ValueError(
            "Expected a Foundry endpoint ending in /api/projects/<project>."
        ) from error
    return account_name, project_name


def compress_subscription_id(subscription_id: str) -> str:
    """Match Foundry UI's URL-safe Base64 encoding of subscription GUID bytes."""
    raw = uuid.UUID(subscription_id).bytes
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def encode_project_resource_context(
    subscription_id: str,
    resource_group: str,
    account_name: str,
    project_name: str,
    provider: str = DEFAULT_PROVIDER,
) -> str:
    """Match the UI's comma-delimited ``encodedResourceId`` route segment."""
    provider_segment = "" if provider == DEFAULT_PROVIDER else quote(
        provider, safe=""
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


async def _list_subscription_ids(
    session: aiohttp.ClientSession,
    headers: dict[str, str],
) -> list[str]:
    """List enabled subscriptions available to the signed-in identity."""
    subscription_ids: list[str] = []
    next_url: str | None = SUBSCRIPTIONS_URL
    while next_url:
        async with session.get(next_url, headers=headers) as response:
            response.raise_for_status()
            payload = await response.json()
        subscription_ids.extend(
            item["subscriptionId"]
            for item in payload.get("value", [])
            if item.get("state") == "Enabled" and item.get("subscriptionId")
        )
        next_url = payload.get("nextLink")
    return subscription_ids


async def _find_account_resource(
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    subscription_ids: list[str],
    account_name: str,
) -> dict[str, Any] | None:
    """Find the Cognitive Services account through Azure Resource Graph."""
    escaped_name = account_name.replace("'", "''")
    query = (
        "Resources "
        "| where type =~ 'microsoft.cognitiveservices/accounts' "
        f"| where name =~ '{escaped_name}' "
        "| project id, name, resourceGroup, subscriptionId "
        "| limit 2"
    )
    matches: list[dict[str, Any]] = []
    for index in range(0, len(subscription_ids), 1000):
        async with session.post(
            RESOURCE_GRAPH_URL,
            headers=headers,
            json={
                "subscriptions": subscription_ids[index : index + 1000],
                "query": query,
            },
        ) as response:
            response.raise_for_status()
            payload = await response.json()
        matches.extend(payload.get("data", []))
        if len(matches) > 1:
            break

    if not matches:
        return None
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple Azure AI accounts named {account_name!r} were found."
        )
    return matches[0]


async def build_foundry_trace_url(
    endpoint: str,
    agent_name: str,
    credential: AsyncTokenCredential,
) -> str | None:
    """Discover the project resource and build its agent traces-page URL."""
    account_name, project_name = _parse_project_endpoint(endpoint)
    token = await credential.get_token(MANAGEMENT_SCOPE)
    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        subscription_ids = await _list_subscription_ids(session, headers)
        account = await _find_account_resource(
            session,
            headers,
            subscription_ids,
            account_name,
        )
    if account is None:
        return None

    encoded_resource = encode_project_resource_context(
        str(account["subscriptionId"]),
        str(account["resourceGroup"]),
        account_name,
        project_name,
    )
    path = (
        "https://ai.azure.com/nextgen/r/"
        f"{encoded_resource}/build/agents/{quote(agent_name, safe='')}/traces"
    )
    return f"{path}?{urlencode({'flight': ','.join(TRACE_FLIGHTS)})}"
