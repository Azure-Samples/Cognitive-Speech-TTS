#!/usr/bin/env python3
"""Customer-facing local UI for published Microsoft Foundry Voice Agents."""

from __future__ import annotations

import argparse
import asyncio
import copy
import ipaddress
import json
import logging
import os
import re
import socket
import time
import uuid
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote, urlencode, urlparse, urlunparse

import websockets
import requests
from aiohttp import WSMsgType, web
from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential, DefaultAzureCredential
from dotenv import dotenv_values, load_dotenv
from session_log import SessionRecorder


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
SAMPLES_DIR = ROOT.parent
VOICE_AGENT_ROOT = SAMPLES_DIR.parent
DOCS_DIR = VOICE_AGENT_ROOT / "docs"
DEFAULT_TEMPLATE_CONFIG = ROOT / "templates.config.json"
TOKEN_SCOPE = "https://ai.azure.com/.default"
ARM_TOKEN_SCOPE = "https://management.azure.com/.default"
ARM_MANAGEMENT_BASE = "https://management.azure.com"
FOUNDRY_FEATURES = "VoiceAgents=V1Preview"
API_VERSION = "v1"
CONNECTION_API_VERSION = "2025-04-01-preview"
MCP_PROBE_TIMEOUT_SECONDS = 15
MCP_PROTOCOL_VERSION = "2025-06-18"
PROJECT_COOKIE = "voice_agent_local_ui_project"
AGENT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
FOUNDRY_PROJECT_HOST = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?\.services\.ai\.azure\.com$",
    re.IGNORECASE,
)
TEMPLATE_AGENT_PREFIX = "gft-"
TEMPLATE_AGENT_NAME = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
)
APP_CONFIG_KEY = web.AppKey("local_ui_config", object)
LOGGER = logging.getLogger("voice_agent_local_ui")


def to_plain(value: Any) -> Any:
    """Convert Azure SDK models into JSON-safe values."""
    if hasattr(value, "as_dict"):
        return to_plain(value.as_dict())
    if isinstance(value, Mapping):
        return {str(key): to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(item) for item in value]
    return value


def validate_project_endpoint(value: str) -> str:
    endpoint = value.strip().rstrip("/")
    parsed = urlparse(endpoint)
    parts = [part for part in parsed.path.split("/") if part]
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not FOUNDRY_PROJECT_HOST.fullmatch(parsed.hostname)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parts[:2] != ["api", "projects"]
        or len(parts) != 3
        or parsed.query
        or parsed.fragment
        or "<" in endpoint
        or ">" in endpoint
    ):
        raise ValueError(
            "Project endpoint must be an Azure Foundry URL in the form "
            "https://<account>.services.ai.azure.com/api/projects/<project-name>."
        )
    return endpoint


def validate_agent_name(value: str) -> str:
    name = value.strip()
    if not AGENT_NAME.fullmatch(name):
        raise ValueError(
            "Agent name must be 1-63 characters and contain only letters, "
            "numbers, '.', '_', or '-'."
        )
    return name


def template_agent_name(requested_name: str, template_id: str) -> str:
    base_name = requested_name.strip() or f"{template_id}-{uuid.uuid4().hex[:8]}"
    base_name = re.sub(r"[^A-Za-z0-9-]+", "-", base_name).strip("-")
    name = (
        base_name
        if base_name.startswith(TEMPLATE_AGENT_PREFIX)
        else f"{TEMPLATE_AGENT_PREFIX}{base_name}"
    )
    if not TEMPLATE_AGENT_NAME.fullmatch(name):
        raise ValueError(
            "Template Agent name must be at most 59 characters before the "
            f"required '{TEMPLATE_AGENT_PREFIX}' prefix and may contain only "
            "letters, numbers, and hyphens."
        )
    return name


def project_name(endpoint: str) -> str:
    return endpoint.rsplit("/", 1)[-1] if endpoint else ""


def validate_https_url(value: str, field: str) -> str:
    url = value.strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or "<" in url or ">" in url:
        raise ValueError(f"{field} must be a public HTTPS URL.")
    return url


def normalize_bearer_token(value: str) -> str:
    token = value.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token:
        raise ValueError("MCP bearer token is required.")
    if "\r" in token or "\n" in token:
        raise ValueError("MCP bearer token cannot contain newlines.")
    if len(token.encode("utf-8")) > 16 * 1024:
        raise ValueError("MCP bearer token must not exceed 16 KiB.")
    return token


def iter_mcp_tools(value: Any):
    if isinstance(value, dict):
        if value.get("type") == "mcp":
            yield value
        for child in value.values():
            yield from iter_mcp_tools(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_mcp_tools(child)


class McpProbeError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        latency_ms: float = 0.0,
        http_status: int = 0,
    ) -> None:
        super().__init__(message)
        self.latency_ms = round(latency_ms, 1)
        self.http_status = http_status


def validate_mcp_probe_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise McpProbeError("MCP probes require an absolute HTTPS URL")
    if parsed.username or parsed.password or parsed.fragment:
        raise McpProbeError("MCP probe URLs cannot contain credentials or fragments")
    try:
        addresses = {
            ipaddress.ip_address(record[4][0])
            for record in socket.getaddrinfo(
                parsed.hostname,
                parsed.port or 443,
                type=socket.SOCK_STREAM,
            )
        }
    except (OSError, ValueError) as error:
        raise McpProbeError(
            f"MCP server address could not be resolved: {error}"
        ) from error
    if not addresses or any(not address.is_global for address in addresses):
        raise McpProbeError(
            "MCP probes cannot target private, loopback, link-local, or reserved addresses"
        )


def decode_mcp_response(response: requests.Response) -> dict[str, Any]:
    text = response.text or ""
    if "text/event-stream" in (response.headers.get("Content-Type") or ""):
        for line in text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        raise ValueError("event stream carried no data frame")
    return json.loads(text) if text.strip() else {}


def mcp_handshake(url: str, bearer_token: str = "") -> dict[str, Any]:
    validate_mcp_probe_url(url)
    session = requests.Session()
    session.trust_env = False
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if bearer_token:
        headers["Authorization"] = (
            f"Bearer {normalize_bearer_token(bearer_token)}"
        )
    started = time.perf_counter()
    try:
        initialized = session.post(
            url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {
                        "name": "voice-agent-local-ui-probe",
                        "version": "1.0",
                    },
                },
            },
            headers=headers,
            timeout=MCP_PROBE_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
    except requests.RequestException as error:
        raise McpProbeError(f"{type(error).__name__}: {error}") from error
    initialize_ms = (time.perf_counter() - started) * 1000
    if initialized.status_code >= 300:
        raise McpProbeError(
            f"initialize returned HTTP {initialized.status_code}",
            latency_ms=initialize_ms,
            http_status=initialized.status_code,
        )
    payload = decode_mcp_response(initialized)
    if payload.get("error"):
        raise McpProbeError(
            f"initialize failed: {payload['error']}",
            latency_ms=initialize_ms,
            http_status=initialized.status_code,
        )
    server_info = (payload.get("result") or {}).get("serverInfo") or {}
    session_id = (
        initialized.headers.get("Mcp-Session-Id")
        or initialized.headers.get("mcp-session-id")
        or ""
    )
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    session.post(
        url,
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers=headers,
        timeout=MCP_PROBE_TIMEOUT_SECONDS,
        allow_redirects=False,
    )

    started = time.perf_counter()
    listed = session.post(
        url,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        headers=headers,
        timeout=MCP_PROBE_TIMEOUT_SECONDS,
        allow_redirects=False,
    )
    tools_ms = (time.perf_counter() - started) * 1000
    if listed.status_code >= 300:
        raise McpProbeError(
            f"tools/list returned HTTP {listed.status_code}",
            latency_ms=initialize_ms + tools_ms,
            http_status=listed.status_code,
        )
    listing = decode_mcp_response(listed)
    if listing.get("error"):
        raise McpProbeError(
            f"tools/list failed: {listing['error']}",
            latency_ms=initialize_ms + tools_ms,
            http_status=listed.status_code,
        )
    tools = [
        str(tool.get("name") or "")
        for tool in (listing.get("result") or {}).get("tools") or []
        if isinstance(tool, dict)
    ]
    return {
        "initialize_ms": round(initialize_ms, 1),
        "tools_ms": round(tools_ms, 1),
        "latency_ms": round(initialize_ms + tools_ms, 1),
        "http_status": listed.status_code,
        "reached": True,
        "server_name": str(server_info.get("name") or ""),
        "server_version": str(server_info.get("version") or ""),
        "tools": sorted(tools),
    }
def materialize_template(
    document: dict[str, Any],
    *,
    model: str,
    voice: str,
    mcp_server_url: str,
    mcp_connection_id: str,
) -> dict[str, Any]:
    definition = copy.deepcopy(document["definition"])
    if model.strip():
        definition["model"] = model.strip()
    if voice.strip():
        audio = definition.setdefault("audio", {})
        output = audio.setdefault("output", {})
        output["voice"] = {
            "type": "azure-standard",
            "name": voice.strip(),
        }
        output.pop("voice_type", None)

    mcp_tools = list(iter_mcp_tools(definition))
    if mcp_tools:
        server_url = validate_https_url(mcp_server_url, "MCP server URL")
        connection_id = mcp_connection_id.strip()
        if not connection_id or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]*", connection_id
        ):
            raise ValueError("MCP connection ID is required and has an invalid format.")
        for tool in mcp_tools:
            tool["server_url"] = server_url
            tool["project_connection_id"] = connection_id
            tool.pop("authorization", None)
            tool.pop("headers", None)
    return definition


def graph_summary(definition: dict[str, Any]) -> dict[str, Any]:
    handoff = definition.get("handoff")
    if not isinstance(handoff, dict):
        return {"nodes": [], "edges": []}
    nodes = []
    for node in handoff.get("nodes") or []:
        config = node.get("config") or {}
        nodes.append(
            {
                "id": str(node.get("id") or ""),
                "description": str(node.get("description") or ""),
                "instructions": str(config.get("instructions") or ""),
                "tools": [
                    str(tool.get("server_label") or tool.get("name") or tool.get("type"))
                    for tool in config.get("tools") or []
                    if isinstance(tool, dict)
                ],
            }
        )
    edges = [
        {
            "id": str(edge.get("id") or f"{edge.get('source')}:{edge.get('target')}"),
            "source": str(edge.get("source") or ""),
            "target": str(edge.get("target") or ""),
            "description": str(edge.get("description") or ""),
        }
        for edge in handoff.get("edges") or []
        if isinstance(edge, dict)
    ]
    return {"nodes": nodes, "edges": edges}


def template_graph_view(definition: dict[str, Any]) -> dict[str, Any]:
    """Build the graph contract consumed by the original dashboard template view."""
    handoff = definition.get("handoff") or {}
    authored_nodes = {
        str(node.get("id")): node
        for node in handoff.get("nodes") or []
        if isinstance(node, dict) and node.get("id")
    }
    raw_edges = [
        edge for edge in handoff.get("edges") or [] if isinstance(edge, dict)
    ]
    node_ids = [ENTRYPOINT_NODE_ID, *authored_nodes]
    for edge in raw_edges:
        for key in ("source", "target"):
            value = str(edge.get(key) or "")
            if value and value not in node_ids:
                node_ids.append(value)

    outgoing = {node_id: [] for node_id in node_ids}
    for edge in raw_edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source in outgoing and target in outgoing:
            outgoing[source].append(target)

    back_edges: set[tuple[str, str]] = set()
    color: dict[str, int] = {}

    def visit(node_id: str) -> None:
        color[node_id] = 1
        for target in outgoing[node_id]:
            if color.get(target) == 1:
                back_edges.add((node_id, target))
            elif not color.get(target):
                visit(target)
        color[node_id] = 2

    if ENTRYPOINT_NODE_ID in outgoing:
        visit(ENTRYPOINT_NODE_ID)
    for node_id in node_ids:
        if not color.get(node_id):
            visit(node_id)

    indegree = {node_id: 0 for node_id in node_ids}
    for source, targets in outgoing.items():
        for target in targets:
            if (source, target) not in back_edges:
                indegree[target] += 1
    depth = {node_id: 0 for node_id in node_ids}
    queue = [node_id for node_id, degree in indegree.items() if degree == 0]
    while queue:
        current = queue.pop(0)
        for target in outgoing[current]:
            if (current, target) in back_edges:
                continue
            depth[target] = max(depth[target], depth[current] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    orders: dict[int, int] = {}
    nodes = []
    for node_id in node_ids:
        authored = authored_nodes.get(node_id) or {}
        config = definition if node_id == ENTRYPOINT_NODE_ID else authored.get("config") or {}
        layer = depth[node_id]
        order = orders.get(layer, 0)
        orders[layer] = order + 1
        nodes.append(
            {
                "id": node_id,
                "label": "entrypoint" if node_id == ENTRYPOINT_NODE_ID else node_id,
                "kind": (
                    "entry"
                    if node_id == ENTRYPOINT_NODE_ID
                    else "node"
                    if outgoing[node_id]
                    else "terminal"
                ),
                "description": str(authored.get("description") or ""),
                "instructions": str(config.get("instructions") or ""),
                "tools": [
                    str(tool.get("server_label") or tool.get("name") or tool.get("type"))
                    for tool in config.get("tools") or []
                    if isinstance(tool, dict)
                ],
                "tool_choice": str(config.get("tool_choice") or "auto"),
                "layer": layer,
                "order": order,
            }
        )
    edges = [
        {
            "id": str(
                edge.get("id")
                or f"{edge.get('source')}:{edge.get('target')}:{index}"
            ),
            "from": str(edge.get("source") or ""),
            "to": str(edge.get("target") or ""),
            "description": str(edge.get("description") or ""),
            "target_response": str(edge.get("target_response") or "auto"),
        }
        for index, edge in enumerate(raw_edges)
    ]
    return {"nodes": nodes, "edges": edges}


ENTRYPOINT_NODE_ID = "$entrypoint"


@dataclass(frozen=True)
class TemplateSource:
    id: str
    name: str
    path: Path
    category: str
    accent: str
    summary: str
    mcp_server_url: str
    mcp_connection_id: str
    mcp_config_path: Path | None
    mcp_token_file: Path | None


class TemplateCatalog:
    def __init__(
        self,
        config_path: Path = DEFAULT_TEMPLATE_CONFIG,
        allowed_root: Path = SAMPLES_DIR,
        mcp_root: Path | None = None,
    ) -> None:
        self.config_path = config_path.resolve()
        self.allowed_root = allowed_root.resolve()
        self.mcp_root = (
            mcp_root.resolve()
            if mcp_root is not None
            else (self.allowed_root.parent / "shared_mcp").resolve()
        )
        self._sources: tuple[TemplateSource, ...] = ()
        self._documents: dict[str, dict[str, Any]] = {}
        self._errors: list[dict[str, str]] = []
        self.reload()

    @property
    def errors(self) -> list[dict[str, str]]:
        return copy.deepcopy(self._errors)

    def reload(self) -> None:
        self._documents.clear()
        self._errors = []
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f"Could not read template config {self.config_path}: {error}"
            ) from error
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise RuntimeError("Template config must be an object with version=1.")
        entries = payload.get("templates")
        if not isinstance(entries, list):
            raise RuntimeError("Template config must contain a templates array.")

        sources: list[TemplateSource] = []
        seen: set[str] = set()
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                self._errors.append(
                    {"id": f"entry-{index}", "error": "Template entry must be an object."}
                )
                continue
            template_id = str(entry.get("id") or "").strip()
            if entry.get("enabled", True) is False:
                continue
            try:
                if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", template_id):
                    raise ValueError(
                        "id must be a lowercase DNS label of at most 63 characters"
                    )
                if template_id in seen:
                    raise ValueError("id is duplicated")
                folder_value = str(entry.get("folder") or "").strip()
                if not folder_value:
                    raise ValueError("folder is required")
                folder = (self.config_path.parent / folder_value).resolve()
                if not folder.is_relative_to(self.allowed_root):
                    raise ValueError(
                        f"folder must resolve under {self.allowed_root}"
                    )
                agent_file = str(entry.get("agent_file") or "agent.json").strip()
                path = (folder / agent_file).resolve()
                if not path.is_relative_to(folder) or not path.is_relative_to(
                    self.allowed_root
                ):
                    raise ValueError("agent_file resolves outside the configured folder")
                if not path.is_file():
                    raise ValueError(f"Agent definition does not exist: {path}")
                mcp_config = entry.get("mcp") or {}
                if not isinstance(mcp_config, dict):
                    raise ValueError("mcp must be an object")
                mcp_config_path = None
                mcp_file_values: dict[str, str] = {}
                mcp_config_file = str(
                    mcp_config.get("config_file") or ""
                ).strip()
                if mcp_config_file:
                    mcp_config_path = (
                        self.config_path.parent / mcp_config_file
                    ).resolve()
                    if not mcp_config_path.is_relative_to(self.mcp_root):
                        raise ValueError(
                            f"mcp.config_file must resolve under {self.mcp_root}"
                        )
                    if mcp_config_path.is_file():
                        mcp_file_values = {
                            key: str(value)
                            for key, value in dotenv_values(
                                mcp_config_path
                            ).items()
                            if value is not None
                        }
                mcp_token_file = None
                mcp_token_file_value = str(
                    mcp_config.get("token_file") or ""
                ).strip()
                if mcp_token_file_value:
                    mcp_token_file = (
                        self.config_path.parent / mcp_token_file_value
                    ).resolve()
                    if not mcp_token_file.is_relative_to(self.mcp_root):
                        raise ValueError(
                            f"mcp.token_file must resolve under {self.mcp_root}"
                        )
                source = TemplateSource(
                    id=template_id,
                    name=str(entry.get("name") or "").strip(),
                    path=path,
                    category=str(entry.get("category") or "Voice Agent").strip(),
                    accent=str(entry.get("accent_color") or "#147d64").strip(),
                    summary=str(entry.get("summary") or "").strip(),
                    mcp_server_url=str(
                        mcp_file_values.get("VOICE_AGENT_MCP_SERVER_URL")
                        or mcp_config.get("server_url")
                        or ""
                    ).strip(),
                    mcp_connection_id=str(
                        mcp_file_values.get("VOICE_AGENT_MCP_CONNECTION_ID")
                        or mcp_config.get("connection_id")
                        or ""
                    ).strip(),
                    mcp_config_path=mcp_config_path,
                    mcp_token_file=mcp_token_file,
                )
                document = self._load(source)
                if list(iter_mcp_tools(document["definition"])):
                    if not source.mcp_server_url and source.mcp_config_path is None:
                        raise ValueError("mcp.server_url is required for an MCP template")
                    if source.mcp_server_url:
                        validate_https_url(source.mcp_server_url, "mcp.server_url")
                    if source.mcp_connection_id and not re.fullmatch(
                        r"[A-Za-z0-9][A-Za-z0-9._-]*",
                        source.mcp_connection_id,
                    ):
                        raise ValueError(
                            "MCP connection ID has an invalid format"
                        )
                    if (
                        source.mcp_config_path is not None
                        and source.mcp_config_path.is_file()
                        and not (
                            source.mcp_server_url
                            and source.mcp_connection_id
                        )
                    ):
                        raise ValueError(
                            "mcp.config_file must define both "
                            "VOICE_AGENT_MCP_SERVER_URL and "
                            "VOICE_AGENT_MCP_CONNECTION_ID"
                        )
            except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
                self._errors.append(
                    {"id": template_id or f"entry-{index}", "error": str(error)}
                )
                continue
            seen.add(template_id)
            sources.append(source)
        self._sources = tuple(sources)

    def _load(self, source: TemplateSource) -> dict[str, Any]:
        if source.id not in self._documents:
            document = json.loads(source.path.read_text(encoding="utf-8"))
            if not isinstance(document.get("definition"), dict):
                raise RuntimeError(f"{source.path} has no definition object.")
            self._documents[source.id] = document
        return self._documents[source.id]

    def cards(self) -> list[dict[str, Any]]:
        cards = []
        for source in self._sources:
            document = self._load(source)
            definition = document["definition"]
            graph = graph_summary(definition)
            cards.append(
                {
                    "id": source.id,
                    "name": source.name or str(document.get("name") or source.id),
                    "category": source.category,
                    "summary": (
                        source.summary
                        or str(document.get("description") or "Voice Agent template.")
                    ),
                    "accent": source.accent,
                    "accent_color": source.accent,
                    "tags": (
                        ["mcp", "voice-agent"]
                        if list(iter_mcp_tools(definition))
                        else ["voice-agent"]
                    ),
                    "featured": bool(list(iter_mcp_tools(definition))),
                    "node_count": len(graph["nodes"]),
                    "edge_count": len(graph["edges"]),
                    "tool_count": len(list(iter_mcp_tools(definition))),
                    "input_count": 0,
                    "error_count": 0,
                    "warning_count": 0,
                    "requires_mcp": bool(list(iter_mcp_tools(definition))),
                }
            )
        return cards

    def detail(self, template_id: str) -> dict[str, Any] | None:
        source = next((item for item in self._sources if item.id == template_id), None)
        if source is None:
            return None
        document = self._load(source)
        definition = document["definition"]
        graph = template_graph_view(definition)
        mcp_tools = list(iter_mcp_tools(definition))
        connection_configured = bool(
            source.mcp_server_url
            and source.mcp_connection_id
            and source.mcp_token_file is not None
            and source.mcp_token_file.is_file()
        )
        tool_servers: dict[str, dict[str, Any]] = {}
        tools: list[dict[str, Any]] = []
        for tool in mcp_tools:
            server_label = str(tool.get("server_label") or "mcp")
            tool_servers.setdefault(
                server_label,
                {
                    "id": server_label,
                    "kind": "mcp",
                    "module": str(tool.get("server_url") or "configured at publish time"),
                },
            )
            for tool_name in tool.get("allowed_tools") or []:
                tools.append(
                    {
                        "name": str(tool_name),
                        "server": server_label,
                        "kind": "mcp",
                        "transport": "mcp",
                        "description": "",
                        "parameters": {},
                    }
                )
        return {
            **next(card for card in self.cards() if card["id"] == template_id),
            "description": document.get("description") or source.summary,
            "model": definition.get("model") or "gpt-realtime",
            "voice": voice_name(definition),
            "instructions": definition.get("instructions") or "",
            "graph": graph,
            "agent_name": str(document.get("name") or source.id),
            "config_groups": [
                {
                    "title": "Voice Agent",
                    "items": [
                        {"label": "Model", "value": definition.get("model") or "—"},
                        {"label": "Voice", "value": voice_name(definition) or "—"},
                        {
                            "label": "Store conversation",
                            "value": "On" if definition.get("store") else "Off",
                        },
                    ],
                }
            ],
            "tool_servers": list(tool_servers.values()),
            "tools": tools,
            "issues": [],
            "yaml": json.dumps(document, indent=2),
            "mcp": {
                "auth_configured": connection_configured,
                "connection_configured": connection_configured,
                "configuration_required": bool(
                    mcp_tools and not connection_configured
                ),
                "token_required": False,
            },
        }

    def document(self, template_id: str) -> dict[str, Any] | None:
        source = next((item for item in self._sources if item.id == template_id), None)
        return copy.deepcopy(self._load(source)) if source else None

    def source(self, template_id: str) -> TemplateSource | None:
        return next((item for item in self._sources if item.id == template_id), None)


def voice_name(definition: dict[str, Any]) -> str:
    voice = ((definition.get("audio") or {}).get("output") or {}).get("voice")
    if isinstance(voice, dict):
        return str(voice.get("name") or "")
    return str(voice or "")


class AppConfig:
    def __init__(
        self,
        endpoint: str = "",
        credential_mode: str = "default",
        template_config: Path = DEFAULT_TEMPLATE_CONFIG,
        data_dir: Path | None = None,
    ) -> None:
        self.endpoint = validate_project_endpoint(endpoint) if endpoint else ""
        self.credential_mode = credential_mode.strip().lower() or "default"
        if self.credential_mode not in {"default", "cli"}:
            raise ValueError("Credential mode must be 'default' or 'cli'.")
        self.catalog = TemplateCatalog(template_config)
        self.data_dir = data_dir.resolve() if data_dir else None
        self.sessions_dir = self.data_dir / "sessions" if self.data_dir else None
        if self.sessions_dir:
            self.sessions_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.sessions_dir.chmod(0o700)
            for run_dir in self.sessions_dir.iterdir():
                if not run_dir.is_dir() or run_dir.is_symlink():
                    continue
                run_dir.chmod(0o700)
                for name in ("meta.json", "timeline.log", "events.jsonl"):
                    artifact = run_dir / name
                    if artifact.is_file() and not artifact.is_symlink():
                        artifact.chmod(0o600)
        self._credential: Any | None = None
        self._token = ""
        self._token_expires_on = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.endpoint)

    @property
    def project_name(self) -> str:
        return project_name(self.endpoint)

    def credential(self):
        if self._credential is None:
            self._credential = (
                AzureCliCredential()
                if self.credential_mode == "cli"
                else DefaultAzureCredential()
            )
        return self._credential

    def token(self) -> str:
        if not self._token or time.time() >= self._token_expires_on - 300:
            token = self.credential().get_token(TOKEN_SCOPE)
            self._token = token.token
            self._token_expires_on = float(token.expires_on)
        return self._token

    def client(self, endpoint: str | None = None) -> AIProjectClient:
        selected_endpoint = endpoint or self.endpoint
        if not selected_endpoint:
            raise RuntimeError("AZURE_AI_PROJECT_ENDPOINT is not configured.")
        return AIProjectClient(
            endpoint=selected_endpoint,
            credential=self.credential(),
            allow_preview=True,
        )

    def close(self) -> None:
        if self._credential is not None:
            self._credential.close()


def get_config(request: web.Request) -> AppConfig:
    return request.app[APP_CONFIG_KEY]  # type: ignore[return-value]


def request_endpoint(request: web.Request) -> str:
    config = get_config(request)
    selected = request.cookies.get(PROJECT_COOKIE, "").strip()
    if selected:
        try:
            return validate_project_endpoint(selected)
        except ValueError:
            pass
    return config.endpoint


def require_endpoint(request: web.Request) -> str:
    endpoint = request_endpoint(request)
    if not endpoint:
        raise web.HTTPServiceUnavailable(
            text=json.dumps(
                {
                    "error": (
                        "Set AZURE_AI_PROJECT_ENDPOINT in local_UI/.env and restart "
                        "the server."
                    )
                }
            ),
            content_type="application/json",
        )
    return endpoint


def sdk_list_agents(config: AppConfig, endpoint: str) -> list[dict[str, Any]]:
    with config.client(endpoint) as client:
        resources = [to_plain(item) for item in client.agents.list(kind="voice", limit=100)]
    resources.sort(
        key=lambda item: (
            -int((((item.get("versions") or {}).get("latest") or {}).get("created_at") or 0)),
            str(item.get("name") or ""),
        )
    )
    return resources


def sdk_get_agent(config: AppConfig, endpoint: str, name: str) -> dict[str, Any]:
    with config.client(endpoint) as client:
        return to_plain(
            client.agents.get(
                name,
                headers={"Foundry-Features": FOUNDRY_FEATURES},
            )
        )


def sdk_publish_template(
    config: AppConfig,
    *,
    endpoint: str,
    name: str,
    description: str,
    definition: dict[str, Any],
) -> dict[str, Any]:
    preview_headers = {"Foundry-Features": FOUNDRY_FEATURES}
    with config.client(endpoint) as client:
        created = client.agents.create_version(
            name,
            {"definition": definition, "description": description},
            headers=preview_headers,
        )
        client.agents.enable(name, headers=preview_headers)
        version = str(getattr(created, "version", "") or "")
        readback = client.agents.get_version(
            name,
            version,
            headers=preview_headers,
        )
    return {
        "name": name,
        "version": version,
        "definition": to_plain(getattr(readback, "definition", definition)),
    }


def sdk_list_projects(config: AppConfig, current_endpoint: str) -> list[dict[str, str]]:
    token = config.credential().get_token(ARM_TOKEN_SCOPE).token
    headers = {"Authorization": f"Bearer {token}"}
    subscriptions_response = requests.get(
        f"{ARM_MANAGEMENT_BASE}/subscriptions",
        params={"api-version": "2020-01-01"},
        headers=headers,
        timeout=30,
    )
    subscriptions_response.raise_for_status()
    subscription_ids = [
        item["subscriptionId"]
        for item in subscriptions_response.json().get("value", [])
        if item.get("subscriptionId")
    ]
    if not subscription_ids:
        return []

    query = (
        "resources "
        "| where type =~ 'microsoft.cognitiveservices/accounts/projects' "
        "| extend proj=tostring(split(name, '/')[-1]), "
        "acct=tostring(split(name, '/')[0]) "
        "| project proj, acct, resourceGroup, subscriptionId "
        "| order by proj asc"
    )
    graph_url = (
        f"{ARM_MANAGEMENT_BASE}/providers/Microsoft.ResourceGraph/resources"
    )
    rows: list[dict[str, Any]] = []
    for index in range(0, len(subscription_ids), 1000):
        response = requests.post(
            graph_url,
            params={"api-version": "2021-03-01"},
            headers={**headers, "Content-Type": "application/json"},
            json={
                "subscriptions": subscription_ids[index : index + 1000],
                "query": query,
            },
            timeout=60,
        )
        if not response.ok:
            raise RuntimeError(
                f"Resource Graph returned HTTP {response.status_code}: "
                f"{response.text[:1000]}"
            )
        rows.extend(response.json().get("data", []))

    projects = []
    seen: set[str] = set()
    for row in rows:
        account = str(row.get("acct") or "")
        project = str(row.get("proj") or "")
        if not account or not project:
            continue
        endpoint = f"https://{account}.services.ai.azure.com/api/projects/{project}"
        if endpoint in seen:
            continue
        seen.add(endpoint)
        projects.append(
            {
                "name": project,
                "account": account,
                "label": f"{project} · {account}",
                "endpoint": endpoint,
                "subscription_id": str(row.get("subscriptionId") or ""),
                "resource_group": str(row.get("resourceGroup") or ""),
            }
        )
    if current_endpoint and current_endpoint not in seen:
        projects.insert(
            0,
            {
                "name": project_name(current_endpoint),
                "account": urlparse(current_endpoint).netloc.split(".")[0],
                "label": f"{project_name(current_endpoint)} · current",
                "endpoint": current_endpoint,
                "subscription_id": "",
                "resource_group": "",
            },
        )
    projects.sort(
        key=lambda item: (
            item["endpoint"] != current_endpoint,
            item["name"].lower(),
            item["account"].lower(),
        )
    )
    return projects


def sdk_create_mcp_connection(
    config: AppConfig,
    *,
    endpoint: str,
    connection_name: str,
    server_url: str,
    bearer_token: str,
) -> dict[str, str]:
    project = next(
        (
            item
            for item in sdk_list_projects(config, endpoint)
            if item["endpoint"] == endpoint
        ),
        None,
    )
    if project is None or not project["subscription_id"] or not project["resource_group"]:
        raise RuntimeError(
            "The selected Project could not be resolved to an Azure resource. "
            "Reader access is required before its MCP connection can be created."
        )
    account_id = (
        f"/subscriptions/{project['subscription_id']}"
        f"/resourceGroups/{project['resource_group']}"
        "/providers/Microsoft.CognitiveServices"
        f"/accounts/{project['account']}"
    )
    token = config.credential().get_token(ARM_TOKEN_SCOPE).token
    url = (
        f"{ARM_MANAGEMENT_BASE}{account_id}/connections/"
        f"{quote(connection_name, safe='')}"
    )
    response = requests.put(
        url,
        params={"api-version": CONNECTION_API_VERSION},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "properties": {
                "category": "RemoteTool",
                "target": server_url,
                "authType": "CustomKeys",
                "isDefault": False,
                "isSharedToAll": False,
                "credentials": {
                    "keys": {"Authorization": f"Bearer {bearer_token}"}
                },
                "metadata": {
                    "displayName": connection_name,
                    "source": "voice-agent-local-ui",
                },
            }
        },
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(
            f"Create MCP Project connection failed with HTTP "
            f"{response.status_code} ({response.reason}). "
            "The signed-in identity needs connection write permission."
        )
    return {
        "name": connection_name,
        "id": f"{account_id}/connections/{connection_name}",
        "account_id": account_id,
    }


def sdk_delete_mcp_connection(
    config: AppConfig,
    *,
    account_id: str,
    connection_name: str,
) -> None:
    token = config.credential().get_token(ARM_TOKEN_SCOPE).token
    response = requests.delete(
        (
            f"{ARM_MANAGEMENT_BASE}{account_id}/connections/"
            f"{quote(connection_name, safe='')}"
        ),
        params={"api-version": CONNECTION_API_VERSION},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    if response.status_code not in {200, 202, 204, 404}:
        raise RuntimeError(
            f"cleanup returned HTTP {response.status_code} ({response.reason})"
        )


async def health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def config_info(request: web.Request) -> web.Response:
    config = get_config(request)
    endpoint = request_endpoint(request)
    return web.json_response(
        {
            "configured": bool(endpoint),
            "project": project_name(endpoint),
            "endpoint": endpoint,
            "credential_mode": config.credential_mode,
            "api_version": API_VERSION,
            "foundry_features": FOUNDRY_FEATURES,
        }
    )


async def list_projects(request: web.Request) -> web.Response:
    config = get_config(request)
    endpoint = request_endpoint(request)
    try:
        projects = await asyncio.to_thread(sdk_list_projects, config, endpoint)
    except Exception as error:
        return web.json_response(
            {"error": f"{type(error).__name__}: {error}"}, status=502
        )
    return web.json_response(
        {"current_endpoint": endpoint, "projects": projects}
    )


async def select_project(request: web.Request) -> web.Response:
    config = get_config(request)
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("Expected a JSON object.")
        endpoint = validate_project_endpoint(str(body.get("endpoint") or ""))
    except (json.JSONDecodeError, ValueError) as error:
        raise web.HTTPBadRequest(text=str(error)) from error
    response = web.json_response(
        {"endpoint": endpoint, "project": project_name(endpoint)}
    )
    response.set_cookie(
        PROJECT_COOKIE,
        endpoint,
        httponly=True,
        samesite="Strict",
        max_age=30 * 24 * 60 * 60,
    )
    return response


async def list_agents(request: web.Request) -> web.Response:
    config = get_config(request)
    endpoint = require_endpoint(request)
    try:
        agents = await asyncio.to_thread(sdk_list_agents, config, endpoint)
    except Exception as error:
        return web.json_response(
            {"error": f"{type(error).__name__}: {error}"}, status=502
        )
    return web.json_response({"agents": agents})


async def get_agent(request: web.Request) -> web.Response:
    config = get_config(request)
    endpoint = require_endpoint(request)
    try:
        name = validate_agent_name(request.match_info["agent"])
        agent = await asyncio.to_thread(sdk_get_agent, config, endpoint, name)
    except ValueError as error:
        raise web.HTTPBadRequest(text=str(error)) from error
    except Exception as error:
        return web.json_response(
            {"error": f"{type(error).__name__}: {error}"}, status=502
        )
    return web.json_response(agent)


async def mcp_probe(request: web.Request) -> web.Response:
    config = get_config(request)
    endpoint = require_endpoint(request)
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("Expected a JSON object.")
        agent_name = validate_agent_name(str(body.get("agent") or ""))
        server_label = str(body.get("server_label") or "").strip()
    except (json.JSONDecodeError, ValueError) as error:
        raise web.HTTPBadRequest(text=str(error)) from error

    try:
        agent = await asyncio.to_thread(
            sdk_get_agent,
            config,
            endpoint,
            agent_name,
        )
    except Exception as error:
        return web.json_response(
            {"ok": False, "error": f"{type(error).__name__}: {error}"},
            status=502,
        )
    definition = (
        ((agent.get("versions") or {}).get("latest") or {}).get("definition")
        or agent.get("definition")
        or {}
    )
    tool = next(
        (
            item
            for item in iter_mcp_tools(definition)
            if not server_label or item.get("server_label") == server_label
        ),
        None,
    )
    if tool is None:
        return web.json_response(
            {
                "ok": False,
                "no_mcp": True,
                "server_label": server_label,
                "error": (
                    f"the published '{agent_name}' declares no MCP server "
                    f"'{server_label}'"
                ),
            }
        )

    server_url = str(tool.get("server_url") or "")
    allowed_tools = [str(name) for name in tool.get("allowed_tools") or []]
    report = {
        "ok": False,
        "reached": False,
        "server_label": str(tool.get("server_label") or server_label),
        "server_url": server_url,
        "project_connection_id": str(tool.get("project_connection_id") or ""),
        "allowed_tools": allowed_tools,
        "checked_at": time.strftime("%H:%M:%S", time.localtime()),
    }
    if not server_url:
        return web.json_response(
            {
                **report,
                "error": (
                    "this MCP tool has no published server_url to probe directly"
                ),
            }
        )
    try:
        result = await asyncio.to_thread(mcp_handshake, server_url)
    except McpProbeError as error:
        credential_note = (
            " — the endpoint answered, so it is reachable; its credential "
            "remains in the Foundry Project connection"
            if error.http_status in {401, 403}
            else ""
        )
        return web.json_response(
            {
                **report,
                "reached": bool(error.http_status),
                "http_status": error.http_status,
                "latency_ms": error.latency_ms,
                "error": f"{error}{credential_note}",
            }
        )
    except Exception as error:
        return web.json_response(
            {
                **report,
                "reached": False,
                "error": f"{type(error).__name__}: {error}",
            }
        )

    missing = [name for name in allowed_tools if name not in result["tools"]]
    return web.json_response(
        {
            **report,
            **result,
            "ok": not missing,
            "missing_tools": missing,
            "error": (
                f"allowed_tools missing on the server: {', '.join(missing)}"
                if missing
                else ""
            ),
        }
    )


async def list_templates(request: web.Request) -> web.Response:
    catalog = get_config(request).catalog
    if request.query.get("reload") == "1":
        try:
            await asyncio.to_thread(catalog.reload)
        except RuntimeError as error:
            return web.json_response(
                {
                    "available": False,
                    "reason": str(error),
                    "templates": [],
                    "errors": [],
                }
            )
    cards = catalog.cards()
    return web.json_response(
        {
            "available": bool(cards),
            "reason": "" if cards else "No valid templates are configured.",
            "templates": cards,
            "errors": catalog.errors,
        }
    )


async def templates_env(request: web.Request) -> web.Response:
    catalog = get_config(request).catalog
    return web.json_response(
        {
            "available": bool(catalog.cards()),
            "reason": "" if catalog.cards() else "No valid templates are configured.",
            "templates_root": str(catalog.config_path),
            "template_count": len(catalog.cards()),
        }
    )


async def get_template(request: web.Request) -> web.Response:
    detail = get_config(request).catalog.detail(request.match_info["template_id"])
    if detail is None:
        raise web.HTTPNotFound(text="Unknown template.")
    return web.json_response(detail)


async def probe_template_mcp(request: web.Request) -> web.Response:
    catalog = get_config(request).catalog
    template_id = request.match_info["template_id"]
    source = catalog.source(template_id)
    document = catalog.document(template_id)
    if source is None or document is None:
        raise web.HTTPNotFound(text="Unknown template.")
    report = {
        "ok": False,
        "reached": False,
        "server_url": source.mcp_server_url,
        "project_connection_id": source.mcp_connection_id,
        "guide_url": "/guide/run-samples",
        "start_command": "cd VoiceAgent/shared_mcp && ./scripts/e2e-local.sh",
        "checked_at": time.strftime("%H:%M:%S", time.localtime()),
    }
    if (
        not source.mcp_server_url
        or not source.mcp_connection_id
        or source.mcp_token_file is None
        or not source.mcp_token_file.is_file()
    ):
        return web.json_response(
            {
                **report,
                "error": (
                    "Local MCP configuration is not ready. "
                    "Start the local MCP E2E, then reload templates."
                ),
            }
        )
    try:
        bearer_token = normalize_bearer_token(
            source.mcp_token_file.read_text(encoding="utf-8")
        )
        result = await asyncio.to_thread(
            mcp_handshake,
            source.mcp_server_url,
            bearer_token,
        )
    except McpProbeError as error:
        return web.json_response(
            {
                **report,
                "reached": bool(error.http_status),
                "auth_gate": error.http_status in {401, 403},
                "http_status": error.http_status,
                "latency_ms": error.latency_ms,
                "error": str(error),
            }
        )
    except Exception as error:
        return web.json_response(
            {**report, "error": f"{type(error).__name__}: {error}"}
        )
    expected_tools = {
        name
        for tool in iter_mcp_tools(document["definition"])
        for name in tool.get("allowed_tools") or []
        if isinstance(name, str) and name
    }
    observed_tools = set(result["tools"])
    missing_tools = sorted(expected_tools - observed_tools)
    if missing_tools:
        return web.json_response(
            {
                **report,
                **result,
                "error": f"MCP tools/list is missing expected tools: {missing_tools}",
            }
        )
    return web.json_response(
        {
            **report,
            **result,
            "ok": True,
            "reached": True,
            "auth_gate": False,
            "message": "MCP handshake and tools/list succeeded.",
        }
    )


async def cleanup_failed_connection(
    config: AppConfig,
    connection: dict[str, str] | None,
) -> str:
    if connection is None:
        return ""
    try:
        await asyncio.to_thread(
            sdk_delete_mcp_connection,
            config,
            account_id=connection["account_id"],
            connection_name=connection["name"],
        )
    except Exception as error:
        return f" Connection '{connection['name']}' cleanup failed: {error}"
    return ""


async def publish_template(request: web.Request) -> web.Response:
    config = get_config(request)
    endpoint = require_endpoint(request)
    template_id = request.match_info["template_id"]
    document = config.catalog.document(template_id)
    source = config.catalog.source(template_id)
    if document is None or source is None:
        raise web.HTTPNotFound(text="Unknown template.")
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("Expected a JSON object.")
        requested_name = str(body.get("name") or "").strip()
        name = template_agent_name(requested_name, template_id)
        mcp_tools = list(iter_mcp_tools(document["definition"]))
        connection_name = ""
        if mcp_tools:
            if (
                not source.mcp_server_url
                or not source.mcp_connection_id
                or source.mcp_token_file is None
                or not source.mcp_token_file.is_file()
            ):
                raise ValueError(
                    "The local MCP config is not ready. Run "
                    "VoiceAgent/shared_mcp/scripts/e2e-local.sh and reload templates."
                )
            connection_name = source.mcp_connection_id
            bearer_token = normalize_bearer_token(
                source.mcp_token_file.read_text(encoding="utf-8")
            )
            await asyncio.to_thread(
                sdk_create_mcp_connection,
                config,
                endpoint=endpoint,
                connection_name=connection_name,
                server_url=source.mcp_server_url,
                bearer_token=bearer_token,
            )
        definition = materialize_template(
            document,
            model=str(body.get("model") or ""),
            voice=str(body.get("voice") or ""),
            mcp_server_url=source.mcp_server_url,
            mcp_connection_id=connection_name,
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise web.HTTPBadRequest(text=str(error)) from error
    except Exception as error:
        return web.json_response(
            {"error": f"{type(error).__name__}: {error}."}, status=502
        )

    try:
        result = await asyncio.to_thread(
            sdk_publish_template,
            config,
            endpoint=endpoint,
            name=name,
            description=str(document.get("description") or ""),
            definition=definition,
        )
    except Exception as error:
        return web.json_response(
            {"error": f"{type(error).__name__}: {error}."}, status=502
        )
    return web.json_response(
        {
            **result,
            "agent_name": result["name"],
            "backend": project_name(endpoint),
            "source_agent_name": str(document.get("name") or template_id),
            "mcp_connection_name": connection_name,
        },
        status=201,
    )


def voice_ws_url(endpoint: str, agent_name: str, session_id: str) -> str:
    parsed = urlparse(endpoint)
    path = (
        f"{parsed.path.rstrip('/')}/agents/{quote(agent_name, safe='')}"
        "/endpoint/protocols/voice"
    )
    query = urlencode(
        {"api-version": API_VERSION, "agent_session_id": session_id}
    )
    return urlunparse(("wss", parsed.netloc, path, "", query, ""))


async def bridge_session(request: web.Request) -> web.WebSocketResponse:
    config = get_config(request)
    endpoint = require_endpoint(request)
    try:
        agent_name = validate_agent_name(request.match_info["agent"])
        token = await asyncio.to_thread(config.token)
    except ValueError as error:
        raise web.HTTPBadRequest(text=str(error)) from error
    except Exception as error:
        raise web.HTTPServiceUnavailable(text=f"Credential unavailable: {error}") from error

    browser = web.WebSocketResponse(max_msg_size=16 * 1024 * 1024)
    await browser.prepare(request)
    session_id = f"local-ui-{uuid.uuid4().hex[:12]}"
    url = voice_ws_url(endpoint, agent_name, session_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "Foundry-Features": FOUNDRY_FEATURES,
    }
    connect_kwargs = {
        "max_size": 16 * 1024 * 1024,
        "open_timeout": 60,
        "ping_interval": 20,
        "ping_timeout": 60,
    }
    recorder: SessionRecorder | None = None
    if config.sessions_dir is not None:
        try:
            recorder = SessionRecorder(
                config.sessions_dir,
                web_id=session_id,
                agent=agent_name,
                backend=project_name(endpoint),
                upstream=url.split("?", 1)[0],
                query={
                    key: value
                    for key, value in request.rel_url.query.items()
                    if key not in {"mcp_auth_token", "authorization"}
                },
            )
            LOGGER.info("Recording session %s in %s", recorder.run_id, recorder.dir)
        except Exception:
            LOGGER.exception("Could not initialize session recorder")
            recorder = None

    bridge_error = ""
    try:
        try:
            upstream_context = websockets.connect(
                url, additional_headers=headers, **connect_kwargs
            )
        except TypeError:
            upstream_context = websockets.connect(
                url, extra_headers=headers, **connect_kwargs
            )
        async with upstream_context as upstream:
            async def browser_to_upstream() -> None:
                async for message in browser:
                    if message.type in (WSMsgType.TEXT, WSMsgType.BINARY):
                        if recorder:
                            recorder.record("up", message.data)
                        await upstream.send(message.data)
                    elif message.type in (
                        WSMsgType.CLOSE,
                        WSMsgType.CLOSING,
                        WSMsgType.ERROR,
                    ):
                        break

            async def upstream_to_browser() -> None:
                async for message in upstream:
                    if recorder:
                        recorder.record("down", message)
                    if isinstance(message, (bytes, bytearray)):
                        await browser.send_bytes(message)
                    else:
                        await browser.send_str(message)

            tasks = {
                asyncio.create_task(browser_to_upstream()),
                asyncio.create_task(upstream_to_browser()),
            }
            _, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
    except Exception as error:
        bridge_error = f"{type(error).__name__}: {error}"
        LOGGER.exception("Voice bridge failed for %s", agent_name)
        if not browser.closed:
            await browser.send_json(
                {"type": "error", "error": {"message": f"bridge: {error}"}}
            )
    finally:
        if not browser.closed:
            await browser.close()
        if recorder:
            recorder.close(bridge_error)
    return browser


async def index(_: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR / "index.html")


async def templates_index(_: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR / "templates.html")


async def examples_guide(_: web.Request) -> web.FileResponse:
    return web.FileResponse(DOCS_DIR / "02_run_samples.md")


async def close_app(app: web.Application) -> None:
    get_config_from_app(app).close()


def get_config_from_app(app: web.Application) -> AppConfig:
    return app[APP_CONFIG_KEY]  # type: ignore[return-value]


def build_app(config: AppConfig) -> web.Application:
    app = web.Application()
    app[APP_CONFIG_KEY] = config
    app.router.add_get("/", index)
    app.router.add_get("/templates", templates_index)
    app.router.add_get("/templates/", templates_index)
    app.router.add_get("/guide/run-samples", examples_guide)
    app.router.add_get("/healthz", health)
    app.router.add_get("/api/config", config_info)
    app.router.add_get("/api/projects", list_projects)
    app.router.add_post("/api/project", select_project)
    app.router.add_get("/api/agents", list_agents)
    app.router.add_get("/api/agents/{agent}", get_agent)
    app.router.add_post("/api/mcp/probe", mcp_probe)
    app.router.add_get("/api/templates", list_templates)
    app.router.add_get("/api/templates/env", templates_env)
    app.router.add_get("/api/templates/{template_id}", get_template)
    app.router.add_get(
        "/api/templates/{template_id}/mcp/probe",
        probe_template_mcp,
    )
    app.router.add_post("/api/templates/{template_id}/publish", publish_template)
    app.router.add_get("/api/sessions/{agent}", bridge_session)
    app.router.add_get(
        "/agents/{agent}/endpoint/protocols/voice",
        bridge_session,
    )
    app.router.add_static("/static/", STATIC_DIR, show_index=False)
    app.on_cleanup.append(close_app)
    return app


def configure_file_logging(data_dir: Path) -> logging.Logger:
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    data_dir.chmod(0o700)
    server_log = data_dir / "server.log"
    file_handler = RotatingFileHandler(
        server_log,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    server_log.chmod(0o600)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
    )
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        logging.Formatter("%(levelname)s %(name)s %(message)s")
    )
    LOGGER.setLevel(logging.INFO)
    LOGGER.addHandler(file_handler)
    LOGGER.addHandler(stream_handler)
    LOGGER.propagate = False
    access_logger = logging.getLogger("aiohttp.access")
    access_logger.setLevel(logging.INFO)
    access_logger.addHandler(file_handler)
    access_logger.propagate = False
    return access_logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("LOCAL_UI_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("LOCAL_UI_PORT", "8097"))
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(
            os.getenv(
                "LOCAL_UI_DATA_DIR",
                str(Path.home() / ".voice-agent-local-ui"),
            )
        ).expanduser(),
    )
    parser.add_argument(
        "--project-endpoint",
        default=(
            os.getenv("AZURE_AI_PROJECT_ENDPOINT")
            or os.getenv("AZURE_VOICE_AGENTS_ENDPOINT")
            or ""
        ),
    )
    parser.add_argument(
        "--credential-mode",
        choices=("default", "cli"),
        default=os.getenv("AZURE_CREDENTIAL_MODE", "default"),
    )
    configured_template_path = Path(
        os.getenv("LOCAL_UI_TEMPLATE_CONFIG", str(DEFAULT_TEMPLATE_CONFIG))
    )
    if not configured_template_path.is_absolute():
        configured_template_path = ROOT / configured_template_path
    parser.add_argument(
        "--template-config",
        type=Path,
        default=configured_template_path,
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv(ROOT / ".env")
    os.umask(0o077)
    args = parse_args()
    config = AppConfig(
        args.project_endpoint,
        args.credential_mode,
        args.template_config,
        args.data_dir,
    )
    access_logger = configure_file_logging(args.data_dir.resolve())
    LOGGER.info(
        f"Voice Agent local UI: http://{args.host}:{args.port} "
        f"(project={config.project_name or 'not configured'}, "
        f"data_dir={args.data_dir.resolve()})"
    )
    web.run_app(
        build_app(config),
        host=args.host,
        port=args.port,
        access_log=access_logger,
    )


if __name__ == "__main__":
    main()
