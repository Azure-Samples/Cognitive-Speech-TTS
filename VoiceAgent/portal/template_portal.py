# Copyright (c) Microsoft. All rights reserved.
"""Portal-owned template catalog, MCP checks, and publishing routes."""

from __future__ import annotations

import asyncio
import copy
import ipaddress
import json
import re
import socket
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import requests
from aiohttp import web
from azure.ai.projects import AIProjectClient
from dotenv import dotenv_values

try:
    from .common import AgentsConfig, FOUNDRY_FEATURES
except ImportError:
    from common import AgentsConfig, FOUNDRY_FEATURES


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
VOICE_AGENT_ROOT = ROOT.parent
SAMPLES_DIR = VOICE_AGENT_ROOT / "samples"
SHARED_MCP_DIR = VOICE_AGENT_ROOT / "shared_mcp"
DOCS_DIR = VOICE_AGENT_ROOT / "docs"
DEFAULT_TEMPLATE_CONFIG = ROOT / "templates.config.json"
ARM_TOKEN_SCOPE = "https://management.azure.com/.default"
ARM_MANAGEMENT_BASE = "https://management.azure.com"
CONNECTION_API_VERSION = "2025-04-01-preview"
MCP_PROBE_TIMEOUT_SECONDS = 15
MCP_PROTOCOL_VERSION = "2025-06-18"
TEMPLATE_AGENT_PREFIX = "local-only-"
TEMPLATE_AGENT_NAME = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
)
AGENT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
ENTRYPOINT_NODE_ID = "$entrypoint"
CATALOG_KEY = web.AppKey("voice_portal_template_catalog", object)
MODEL_OVERRIDE_KEY = web.AppKey("voice_portal_template_model_override", str)
AGENTS_CONFIG_KEY = web.AppKey("voice_portal_agents_config", AgentsConfig)
CONFIG_RESOLVER_KEY = web.AppKey("voice_portal_config_resolver", object)
TEMPLATE_ASSETS = frozenset({
    "template-app.js",
    "template-graph.js",
    "template-styles.css",
})


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


def template_agent_name(requested_name: str, template_id: str) -> str:
    base_name = requested_name.strip() or f"{template_id}-{uuid.uuid4().hex[:8]}"
    base_name = re.sub(r"[^A-Za-z0-9-]+", "-", base_name).strip("-")
    name = (
        base_name
        if base_name.startswith(TEMPLATE_AGENT_PREFIX)
        else f"{TEMPLATE_AGENT_PREFIX}{base_name}"
    )
    if len(name) > 63 or not TEMPLATE_AGENT_NAME.fullmatch(name):
        max_base_length = 63 - len(TEMPLATE_AGENT_PREFIX)
        raise ValueError(
            f"Template Agent name must be at most {max_base_length} characters before the "
            f"required '{TEMPLATE_AGENT_PREFIX}' prefix and may contain only "
            "letters, numbers, and hyphens."
        )
    return name


def iter_mcp_tools(value: Any):
    if isinstance(value, dict):
        if value.get("type") == "mcp":
            yield value
        for child in value.values():
            yield from iter_mcp_tools(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_mcp_tools(child)


def tool_names(tools: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for tool in tools:
        if tool.get("type") == "mcp":
            names.extend(
                str(name)
                for name in tool.get("allowed_tools") or []
                if name
            )
        elif tool.get("name"):
            names.append(str(tool["name"]))
    return names


def tool_refs(tools: list[dict[str, Any]]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for tool in tools:
        if tool.get("type") == "mcp":
            server = str(tool.get("server_label") or "mcp")
            refs.extend(
                {"name": str(name), "server": server}
                for name in tool.get("allowed_tools") or []
                if name
            )
        elif tool.get("name"):
            refs.append({"name": str(tool["name"]), "server": ""})
    return refs


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
        headers["Authorization"] = f"Bearer {bearer_token}"
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
                        "name": "voice-agent-portal-probe",
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
    session_id = initialized.headers.get("Mcp-Session-Id", "")
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
    tools = sorted(
        str(tool.get("name") or "")
        for tool in (listing.get("result") or {}).get("tools") or []
        if isinstance(tool, dict)
    )
    return {
        "initialize_ms": round(initialize_ms, 1),
        "tools_ms": round(tools_ms, 1),
        "latency_ms": round(initialize_ms + tools_ms, 1),
        "http_status": listed.status_code,
        "reached": True,
        "server_name": str(server_info.get("name") or ""),
        "server_version": str(server_info.get("version") or ""),
        "tools": tools,
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
        output = definition.setdefault("audio", {}).setdefault("output", {})
        output["voice"] = {"type": "azure-standard", "name": voice.strip()}
        output.pop("voice_type", None)
    mcp_tools = list(iter_mcp_tools(definition))
    if mcp_tools:
        server_url = validate_https_url(mcp_server_url, "MCP server URL")
        connection_id = mcp_connection_id.strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", connection_id):
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
        if not isinstance(node, dict):
            continue
        config = node.get("config") or {}
        config_tools = [
            tool
            for tool in config.get("tools") or []
            if isinstance(tool, dict)
        ]
        nodes.append(
            {
                "id": str(node.get("id") or ""),
                "description": str(node.get("description") or ""),
                "instructions": str(config.get("instructions") or ""),
                "tools": tool_names(config_tools),
                "tool_refs": tool_refs(config_tools),
            }
        )
    return {
        "nodes": nodes,
        "edges": [
            {
                "id": str(edge.get("id") or f"{edge.get('source')}:{edge.get('target')}"),
                "source": str(edge.get("source") or ""),
                "target": str(edge.get("target") or ""),
                "description": str(edge.get("description") or ""),
            }
            for edge in handoff.get("edges") or []
            if isinstance(edge, dict)
        ],
    }


def template_graph_view(definition: dict[str, Any]) -> dict[str, Any]:
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
        config_tools = [
            tool
            for tool in config.get("tools") or []
            if isinstance(tool, dict)
        ]
        nodes.append({
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
            "tools": tool_names(config_tools),
            "tool_refs": tool_refs(config_tools),
            "tool_choice": str(config.get("tool_choice") or "auto"),
            "layer": layer,
            "order": order,
        })
    edges = [
        {
            "id": str(edge.get("id") or f"{edge.get('source')}:{edge.get('target')}:{index}"),
            "from": str(edge.get("source") or ""),
            "to": str(edge.get("target") or ""),
            "description": str(edge.get("description") or ""),
            "target_response": str(edge.get("target_response") or "auto"),
        }
        for index, edge in enumerate(raw_edges)
    ]
    return {"nodes": nodes, "edges": edges}


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
    connection_mode: str
    allowed_backends: tuple[str, ...]
    source_label: str
    source_reference: str
    mcp_config_path: Path | None
    mcp_token_file: Path | None


class TemplateCatalog:
    def __init__(
        self,
        config_path: Path = DEFAULT_TEMPLATE_CONFIG,
        allowed_root: Path = SAMPLES_DIR,
        mcp_root: Path = SHARED_MCP_DIR,
    ) -> None:
        self.config_path = config_path.resolve()
        self.allowed_root = allowed_root.resolve()
        self.mcp_root = mcp_root.resolve()
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
            template_id = ""
            try:
                if not isinstance(entry, dict):
                    raise ValueError("Template entry must be an object.")
                template_id = str(entry.get("id") or "").strip()
                if entry.get("enabled", True) is False:
                    continue
                if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", template_id):
                    raise ValueError("id must be a lowercase DNS label of at most 63 characters")
                if template_id in seen:
                    raise ValueError("id is duplicated")
                folder_value = str(entry.get("folder") or "").strip()
                if not folder_value:
                    raise ValueError("folder is required")
                folder = (self.config_path.parent / folder_value).resolve()
                if not folder.is_relative_to(self.allowed_root):
                    raise ValueError(f"folder must resolve under {self.allowed_root}")
                agent_file = str(entry.get("agent_file") or "agent.json").strip()
                path = (folder / agent_file).resolve()
                if not path.is_relative_to(folder) or not path.is_relative_to(self.allowed_root):
                    raise ValueError("agent_file resolves outside the configured folder")
                if not path.is_file():
                    raise ValueError(f"Agent definition does not exist: {path}")
                mcp_config = entry.get("mcp") or {}
                if not isinstance(mcp_config, dict):
                    raise ValueError("mcp must be an object")
                connection_mode = str(
                    mcp_config.get("connection_mode") or "managed"
                ).strip()
                if connection_mode not in {"managed", "existing"}:
                    raise ValueError(
                        "mcp.connection_mode must be 'managed' or 'existing'"
                    )
                allowed_backends_value = (
                    mcp_config.get("allowed_backends") or []
                )
                if not isinstance(allowed_backends_value, list) or any(
                    not isinstance(value, str) or not value.strip()
                    for value in allowed_backends_value
                ):
                    raise ValueError(
                        "mcp.allowed_backends must be an array of "
                        "non-empty strings"
                    )
                mcp_config_path = None
                mcp_values: dict[str, str] = {}
                config_file = str(mcp_config.get("config_file") or "").strip()
                if config_file:
                    mcp_config_path = (self.config_path.parent / config_file).resolve()
                    if not mcp_config_path.is_relative_to(self.mcp_root):
                        raise ValueError(f"mcp.config_file must resolve under {self.mcp_root}")
                    if mcp_config_path.is_file():
                        mcp_values = {
                            key: str(value)
                            for key, value in dotenv_values(mcp_config_path).items()
                            if value is not None
                        }
                token_file = str(mcp_config.get("token_file") or "").strip()
                mcp_token_file = (
                    (self.config_path.parent / token_file).resolve()
                    if token_file
                    else None
                )
                if mcp_token_file and not mcp_token_file.is_relative_to(self.mcp_root):
                    raise ValueError(f"mcp.token_file must resolve under {self.mcp_root}")
                source = TemplateSource(
                    id=template_id,
                    name=str(entry.get("name") or "").strip(),
                    path=path,
                    category=str(entry.get("category") or "Voice Agent").strip(),
                    accent=str(entry.get("accent_color") or "#147d64").strip(),
                    summary=str(entry.get("summary") or "").strip(),
                    mcp_server_url=str(
                        mcp_values.get("VOICE_AGENT_MCP_SERVER_URL")
                        or mcp_config.get("server_url")
                        or ""
                    ).strip(),
                    mcp_connection_id=str(
                        mcp_values.get("VOICE_AGENT_MCP_CONNECTION_ID")
                        or mcp_config.get("connection_id")
                        or ""
                    ).strip(),
                    connection_mode=connection_mode,
                    allowed_backends=tuple(
                        value.strip() for value in allowed_backends_value
                    ),
                    source_label=str(
                        mcp_config.get("source_label") or "MCP server"
                    ).strip(),
                    source_reference=str(
                        mcp_config.get("source_reference") or ""
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
                        raise ValueError("MCP connection ID has an invalid format")
                    if (
                        source.mcp_config_path
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
            mcp_tools = list(iter_mcp_tools(definition))
            cards.append({
                "id": source.id,
                "name": source.name or str(document.get("name") or source.id),
                "category": source.category,
                "summary": source.summary or str(document.get("description") or "Voice Agent template."),
                "accent": source.accent,
                "accent_color": source.accent,
                "tags": ["mcp", "voice-agent"] if mcp_tools else ["voice-agent"],
                "featured": bool(mcp_tools),
                "node_count": len(graph["nodes"]),
                "edge_count": len(graph["edges"]),
                "tool_count": len(mcp_tools),
                "input_count": 0,
                "error_count": 0,
                "warning_count": 0,
                "requires_mcp": bool(mcp_tools),
            })
        return cards

    def detail(self, template_id: str) -> dict[str, Any] | None:
        source = self.source(template_id)
        if source is None:
            return None
        document = self._load(source)
        definition = document["definition"]
        graph = template_graph_view(definition)
        mcp_tools = list(iter_mcp_tools(definition))
        connection_configured = bool(
            source.mcp_server_url
            and source.mcp_connection_id
            and (
                source.connection_mode == "existing"
                or (
                    source.mcp_token_file
                    and source.mcp_token_file.is_file()
                )
            )
        )
        source_description = source.source_label + (
            f" · {source.source_reference}"
            if source.source_reference
            else ""
        )
        tool_servers: dict[str, dict[str, Any]] = {}
        tools: dict[tuple[str, str], dict[str, Any]] = {}
        for tool in mcp_tools:
            server_label = str(tool.get("server_label") or "mcp")
            tool_servers.setdefault(server_label, {
                "id": server_label,
                "kind": "mcp",
                "module": source_description,
            })
            for tool_name in tool.get("allowed_tools") or []:
                key = (server_label, str(tool_name))
                tools.setdefault(
                    key,
                    {
                        "name": str(tool_name),
                        "server": server_label,
                        "kind": "mcp",
                        "transport": "mcp",
                        "description": "",
                        "parameters": {},
                    },
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
                },
                {
                    "title": "MCP source",
                    "items": [
                        {"label": "Runtime", "value": source.source_label},
                        {
                            "label": "Reference",
                            "value": source.source_reference or "—",
                        },
                        {
                            "label": "Connection mode",
                            "value": source.connection_mode,
                        },
                    ],
                },
            ],
            "tool_servers": list(tool_servers.values()),
            "tools": list(tools.values()),
            "issues": [],
            "yaml": json.dumps(document, indent=2),
            "mcp": {
                "auth_configured": connection_configured,
                "connection_configured": connection_configured,
                "configuration_required": bool(mcp_tools and not connection_configured),
                "token_required": False,
                "connection_mode": source.connection_mode,
                "allowed_backends": list(source.allowed_backends),
                "source_label": source.source_label,
                "source_reference": source.source_reference,
                "allow_user_token": False,
            },
        }

    def document(self, template_id: str) -> dict[str, Any] | None:
        source = self.source(template_id)
        return copy.deepcopy(self._load(source)) if source else None

    def source(self, template_id: str) -> TemplateSource | None:
        return next((item for item in self._sources if item.id == template_id), None)


def voice_name(definition: dict[str, Any]) -> str:
    voice = ((definition.get("audio") or {}).get("output") or {}).get("voice")
    if isinstance(voice, dict):
        return str(voice.get("name") or "")
    return str(voice or "")


def discover_projects(
    cfg: AgentsConfig,
    current_endpoint: str = "",
) -> list[dict[str, str]]:
    token = cfg.credential().get_token(ARM_TOKEN_SCOPE).token
    headers = {"Authorization": f"Bearer {token}"}
    subscriptions = requests.get(
        f"{ARM_MANAGEMENT_BASE}/subscriptions",
        params={"api-version": "2020-01-01"},
        headers=headers,
        timeout=30,
    )
    subscriptions.raise_for_status()
    subscription_ids = [
        item["subscriptionId"]
        for item in subscriptions.json().get("value", [])
        if item.get("subscriptionId")
    ]
    query = (
        "resources "
        "| where type =~ 'microsoft.cognitiveservices/accounts/projects' "
        "| extend proj=tostring(split(name, '/')[-1]), acct=tostring(split(name, '/')[0]) "
        "| project proj, acct, resourceGroup, subscriptionId"
    )
    rows = []
    for index in range(0, len(subscription_ids), 1000):
        response = requests.post(
            f"{ARM_MANAGEMENT_BASE}/providers/Microsoft.ResourceGraph/resources",
            params={"api-version": "2021-03-01"},
            headers={**headers, "Content-Type": "application/json"},
            json={"subscriptions": subscription_ids[index:index + 1000], "query": query},
            timeout=60,
        )
        response.raise_for_status()
        rows.extend(response.json().get("data", []))
    projects = [
        {
            "name": str(row.get("proj") or ""),
            "account": str(row.get("acct") or ""),
            "label": f"{row.get('proj')} · {row.get('acct')}",
            "endpoint": (
                f"https://{row.get('acct')}.services.ai.azure.com"
                f"/api/projects/{row.get('proj')}"
            ),
            "subscription_id": str(row.get("subscriptionId") or ""),
            "resource_group": str(row.get("resourceGroup") or ""),
        }
        for row in rows
        if row.get("proj") and row.get("acct")
    ]
    projects.sort(
        key=lambda item: (
            item["endpoint"] != current_endpoint,
            item["name"].lower(),
            item["account"].lower(),
        )
    )
    return projects


def create_mcp_connection(
    cfg: AgentsConfig,
    *,
    connection_name: str,
    server_url: str,
    bearer_token: str,
) -> None:
    project = next(
        (item for item in discover_projects(cfg, cfg.host) if item["endpoint"] == cfg.host),
        None,
    )
    if project is None:
        raise RuntimeError(
            "The configured Project could not be resolved to an Azure resource. "
            "Reader access is required before its MCP connection can be created."
        )
    account_id = (
        f"/subscriptions/{project['subscription_id']}"
        f"/resourceGroups/{project['resource_group']}"
        "/providers/Microsoft.CognitiveServices"
        f"/accounts/{project['account']}"
    )
    token = cfg.credential().get_token(ARM_TOKEN_SCOPE).token
    response = requests.put(
        (
            f"{ARM_MANAGEMENT_BASE}{account_id}/connections/"
            f"{quote(connection_name, safe='')}"
        ),
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
                    "source": "voice-agent-portal",
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


def publish_agent(
    cfg: AgentsConfig,
    *,
    name: str,
    description: str,
    definition: dict[str, Any],
) -> dict[str, Any]:
    preview_headers = {"Foundry-Features": FOUNDRY_FEATURES}
    with AIProjectClient(
        endpoint=cfg.host,
        credential=cfg.credential(),
        allow_preview=True,
    ) as client:
        created = client.agents.create_version(
            name,
            {"definition": definition, "description": description},
            headers=preview_headers,
        )
        client.agents.enable(name, headers=preview_headers)
        version = str(getattr(created, "version", "") or "")
        readback = client.agents.get_version(name, version, headers=preview_headers)
    readback_definition = getattr(readback, "definition", definition)
    if hasattr(readback_definition, "as_dict"):
        readback_definition = readback_definition.as_dict()
    return {"name": name, "version": version, "definition": readback_definition}


def get_agent(cfg: AgentsConfig, name: str) -> dict[str, Any]:
    with AIProjectClient(
        endpoint=cfg.host,
        credential=cfg.credential(),
        allow_preview=True,
    ) as client:
        resource = client.agents.get(
            name,
            headers={"Foundry-Features": FOUNDRY_FEATURES},
        )
    return resource.as_dict() if hasattr(resource, "as_dict") else resource


async def _cfg(request: web.Request) -> AgentsConfig:
    resolver = request.app[CONFIG_RESOLVER_KEY]
    return await resolver(request)


def _catalog(request: web.Request) -> TemplateCatalog:
    return request.app[CATALOG_KEY]


def require_template_backend(source: TemplateSource, backend: str) -> None:
    if source.allowed_backends and backend not in source.allowed_backends:
        allowed = ", ".join(source.allowed_backends)
        raise ValueError(
            f"Template '{source.id}' requires Agent backend {allowed}; "
            f"the selected backend is {backend}."
        )


async def templates_index(_: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR / "templates.html")


async def template_asset(request: web.Request) -> web.FileResponse:
    name = request.match_info["asset"]
    if name not in TEMPLATE_ASSETS:
        raise web.HTTPNotFound()
    return web.FileResponse(STATIC_DIR / name)


async def examples_guide(_: web.Request) -> web.FileResponse:
    return web.FileResponse(DOCS_DIR / "03_run_samples.md")


async def template_config(request: web.Request) -> web.Response:
    cfg = await _cfg(request)
    return web.json_response({
        "configured": True,
        "project": cfg.project,
        "endpoint": cfg.host,
        "credential_mode": "default",
        "api_version": cfg.api_version,
        "foundry_features": FOUNDRY_FEATURES,
    })


async def list_templates(request: web.Request) -> web.Response:
    catalog = _catalog(request)
    if request.query.get("reload") == "1":
        try:
            await asyncio.to_thread(catalog.reload)
        except RuntimeError as error:
            return web.json_response({
                "available": False,
                "reason": str(error),
                "templates": [],
                "errors": [],
            })
    cards = catalog.cards()
    return web.json_response({
        "available": bool(cards),
        "reason": "" if cards else "No valid templates are configured.",
        "templates": cards,
        "errors": catalog.errors,
    })


async def templates_env(request: web.Request) -> web.Response:
    catalog = _catalog(request)
    cards = catalog.cards()
    return web.json_response({
        "available": bool(cards),
        "reason": "" if cards else "No valid templates are configured.",
        "templates_root": str(catalog.config_path),
        "template_count": len(cards),
    })


async def get_template(request: web.Request) -> web.Response:
    detail = _catalog(request).detail(request.match_info["template_id"])
    if detail is None:
        raise web.HTTPNotFound(text="Unknown template.")
    model_override = request.app[MODEL_OVERRIDE_KEY]
    if model_override:
        detail["model"] = model_override
        for group in detail["config_groups"]:
            for item in group["items"]:
                if item["label"] == "Model":
                    item["value"] = model_override
    return web.json_response(detail)


def _probe_report(source: TemplateSource) -> dict[str, Any]:
    return {
        "ok": False,
        "reached": False,
        "server_url": source.mcp_server_url,
        "project_connection_id": source.mcp_connection_id,
        "guide_url": "/guide/run-samples",
        "start_command": "cd VoiceAgent/shared_mcp && ./scripts/e2e-local.sh",
        "checked_at": time.strftime("%H:%M:%S", time.localtime()),
    }


async def probe_template_mcp(request: web.Request) -> web.Response:
    catalog = _catalog(request)
    template_id = request.match_info["template_id"]
    source = catalog.source(template_id)
    document = catalog.document(template_id)
    if source is None or document is None:
        raise web.HTTPNotFound(text="Unknown template.")
    cfg = await _cfg(request)
    report = _probe_report(source)
    report["backend"] = cfg.backend
    try:
        require_template_backend(source, cfg.backend)
    except ValueError as error:
        return web.json_response({**report, "error": str(error)})
    if (
        not source.mcp_server_url
        or not source.mcp_connection_id
        or (
            source.connection_mode == "managed"
            and (
                source.mcp_token_file is None
                or not source.mcp_token_file.is_file()
            )
        )
    ):
        return web.json_response({
            **report,
            "error": (
                "Local MCP configuration is not ready. "
                "Start the local MCP E2E, then reload templates."
            ),
        })
    try:
        bearer_token = (
            ""
            if source.connection_mode == "existing"
            else normalize_bearer_token(
                source.mcp_token_file.read_text(encoding="utf-8")
            )
        )
        result = await asyncio.to_thread(
            mcp_handshake,
            source.mcp_server_url,
            bearer_token,
        )
    except McpProbeError as error:
        if (
            source.connection_mode == "existing"
            and error.http_status in {401, 403}
        ):
            return web.json_response({
                **report,
                "ok": True,
                "reached": True,
                "auth_gate": True,
                "project_connection_auth": True,
                "http_status": error.http_status,
                "latency_ms": error.latency_ms,
                "error": (
                    "The endpoint is reachable; authentication is held by "
                    "the existing Foundry Project connection."
                ),
            })
        return web.json_response({
            **report,
            "reached": bool(error.http_status),
            "auth_gate": error.http_status in {401, 403},
            "http_status": error.http_status,
            "latency_ms": error.latency_ms,
            "error": str(error),
        })
    except Exception as error:
        return web.json_response({**report, "error": f"{type(error).__name__}: {error}"})
    expected_tools = {
        name
        for tool in iter_mcp_tools(document["definition"])
        for name in tool.get("allowed_tools") or []
        if isinstance(name, str) and name
    }
    missing_tools = sorted(expected_tools - set(result["tools"]))
    if missing_tools:
        return web.json_response({
            **report,
            **result,
            "error": f"MCP tools/list is missing expected tools: {missing_tools}",
        })
    return web.json_response({
        **report,
        **result,
        "ok": True,
        "reached": True,
        "auth_gate": False,
        "message": "MCP handshake and tools/list succeeded.",
    })


async def probe_published_mcp(request: web.Request) -> web.Response:
    cfg = await _cfg(request)
    try:
        body = await request.json()
        agent_name = str(body.get("agent") or "").strip()
        server_label = str(body.get("server_label") or "").strip()
        if not AGENT_NAME.fullmatch(agent_name):
            raise ValueError(
                "Agent name must be 1-63 characters and contain only letters, "
                "numbers, '.', '_', or '-'."
            )
        agent = await asyncio.to_thread(get_agent, cfg, agent_name)
    except (json.JSONDecodeError, ValueError) as error:
        raise web.HTTPBadRequest(text=str(error)) from error
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
        return web.json_response({
            "ok": False,
            "no_mcp": True,
            "server_label": server_label,
            "error": f"the published '{agent_name}' declares no MCP server '{server_label}'",
        })
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
    if not server_url and report["project_connection_id"]:
        return web.json_response({
            **report,
            "connection_only": True,
            "error": (
                "this MCP tool resolves through a project connection, so it "
                "has no URL the portal can call directly"
            ),
        })
    inline_token = ""
    if tool.get("authorization"):
        try:
            inline_token = normalize_bearer_token(
                str(tool["authorization"])
            )
        except ValueError as error:
            return web.json_response({**report, "error": str(error)})
    try:
        result = await asyncio.to_thread(
            mcp_handshake,
            server_url,
            inline_token,
        )
    except McpProbeError as error:
        if (
            error.http_status in {401, 403}
            and report["project_connection_id"]
        ):
            return web.json_response({
                **report,
                "reached": True,
                "auth_gate": True,
                "project_connection_auth": True,
                "http_status": error.http_status,
                "latency_ms": error.latency_ms,
                "error": (
                    "the endpoint is reachable; authentication is held by "
                    "the Foundry Project connection"
                ),
            })
        return web.json_response({
            **report,
            "reached": bool(error.http_status),
            "http_status": error.http_status,
            "latency_ms": error.latency_ms,
            "error": str(error),
        })
    except Exception as error:
        return web.json_response({**report, "error": f"{type(error).__name__}: {error}"})
    missing = [name for name in allowed_tools if name not in result["tools"]]
    return web.json_response({
        **report,
        **result,
        "ok": not missing,
        "missing_tools": missing,
        "error": (
            f"allowed_tools missing on the server: {', '.join(missing)}"
            if missing
            else ""
        ),
    })


async def reject_browser_mcp_token(_: web.Request) -> web.Response:
    raise web.HTTPConflict(
        text=(
            "Portal Templates use the managed Local Dev Tunnel connection; "
            "browser-provided MCP tokens are disabled."
        )
    )


async def publish_template(request: web.Request) -> web.Response:
    cfg = await _cfg(request)
    template_id = request.match_info["template_id"]
    catalog = _catalog(request)
    document = catalog.document(template_id)
    source = catalog.source(template_id)
    if document is None or source is None:
        raise web.HTTPNotFound(text="Unknown template.")
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("Expected a JSON object.")
        name = template_agent_name(str(body.get("name") or ""), template_id)
        require_template_backend(source, cfg.backend)
        mcp_tools = list(iter_mcp_tools(document["definition"]))
        connection_name = ""
        if mcp_tools:
            if (
                not source.mcp_server_url
                or not source.mcp_connection_id
                or (
                    source.connection_mode == "managed"
                    and (
                        source.mcp_token_file is None
                        or not source.mcp_token_file.is_file()
                    )
                )
            ):
                raise ValueError(
                    "The local MCP config is not ready. Run "
                    "VoiceAgent/shared_mcp/scripts/e2e-local.sh and reload templates."
                )
            connection_name = source.mcp_connection_id
            bearer_token = (
                normalize_bearer_token(
                    source.mcp_token_file.read_text(encoding="utf-8")
                )
                if (
                    source.connection_mode == "managed"
                    and source.mcp_token_file is not None
                )
                else ""
            )
            validate_mcp_probe_url(source.mcp_server_url)
            if source.connection_mode == "managed":
                await asyncio.to_thread(
                    create_mcp_connection,
                    cfg,
                    connection_name=connection_name,
                    server_url=source.mcp_server_url,
                    bearer_token=bearer_token,
                )
        definition = materialize_template(
            document,
            model=str(body.get("model") or request.app[MODEL_OVERRIDE_KEY]),
            voice=str(body.get("voice") or ""),
            mcp_server_url=source.mcp_server_url,
            mcp_connection_id=connection_name,
        )
        result = await asyncio.to_thread(
            publish_agent,
            cfg,
            name=name,
            description=str(document.get("description") or ""),
            definition=definition,
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise web.HTTPBadRequest(text=str(error)) from error
    except Exception as error:
        return web.json_response(
            {"error": f"{type(error).__name__}: {error}."},
            status=502,
        )
    return web.json_response({
        **result,
        "agent_name": result["name"],
        "backend": cfg.project,
        "source_agent_name": str(document.get("name") or template_id),
        "mcp_connection_name": connection_name,
    }, status=201)


def install_template_routes(
    app: web.Application,
    *,
    cfg: AgentsConfig,
    config_resolver,
    model_override: str = "",
    template_config_path: Path = DEFAULT_TEMPLATE_CONFIG,
) -> None:
    app[AGENTS_CONFIG_KEY] = cfg
    app[CONFIG_RESOLVER_KEY] = config_resolver
    app[CATALOG_KEY] = TemplateCatalog(template_config_path)
    app[MODEL_OVERRIDE_KEY] = model_override
    app.router.add_get("/templates", templates_index)
    app.router.add_get("/templates/", templates_index)
    app.router.add_get("/guide/run-samples", examples_guide)
    app.router.add_get("/api/config", template_config)
    app.router.add_get("/api/templates", list_templates)
    app.router.add_get("/api/templates/env", templates_env)
    app.router.add_get("/api/templates/{template_id}", get_template)
    app.router.add_get(
        "/api/templates/{template_id}/mcp/probe",
        probe_template_mcp,
    )
    app.router.add_post(
        "/api/templates/{template_id}/mcp/configure",
        reject_browser_mcp_token,
    )
    app.router.add_post("/api/templates/{template_id}/publish", publish_template)
    app.router.add_get("/static/{asset}", template_asset)
