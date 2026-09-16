from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROTOCOL_VERSION = "2025-06-18"
TIMEOUT_SECONDS = 20


class ProbeError(RuntimeError):
    pass


def expected_tools_from_agent(agent_path: Path) -> set[str]:
    document = json.loads(agent_path.read_text(encoding="utf-8"))
    expected: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("type") == "mcp":
                allowed = value.get("allowed_tools")
                if not isinstance(allowed, list):
                    raise ProbeError(
                        f"MCP tool in {agent_path} must define allowed_tools"
                    )
                for name in allowed:
                    if not isinstance(name, str) or not name:
                        raise ProbeError(
                            f"MCP allowed_tools in {agent_path} contains an invalid name"
                        )
                    expected.add(name)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(document.get("definition"))
    if not expected:
        raise ProbeError(f"No MCP allowed_tools found in {agent_path}")
    return expected


def _decode_payload(body: bytes, content_type: str) -> dict[str, Any]:
    text = body.decode("utf-8")
    if "text/event-stream" in content_type:
        for line in text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        raise ProbeError("MCP event stream carried no data frame")
    return json.loads(text) if text.strip() else {}


def _post(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> tuple[int, Any, dict[str, Any]]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            response_headers = response.headers
            body = response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        response_headers = error.headers
        body = error.read()
    except urllib.error.URLError as error:
        raise ProbeError(f"MCP request failed: {error.reason}") from error

    if status >= 300:
        raise ProbeError(f"MCP request returned HTTP {status}")
    return (
        status,
        response_headers,
        _decode_payload(body, response_headers.get("Content-Type", "")),
    )


def probe(url: str, token: str, expected_tools: set[str]) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    _, response_headers, initialized = _post(
        url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "shared-mcp-deployment-probe",
                    "version": "1.0",
                },
            },
        },
        headers,
    )
    if initialized.get("error"):
        raise ProbeError(f"MCP initialize failed: {initialized['error']}")

    session_id = response_headers.get("Mcp-Session-Id", "")
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    _post(
        url,
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers,
    )
    _, _, listing = _post(
        url,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
        headers,
    )
    if listing.get("error"):
        raise ProbeError(f"MCP tools/list failed: {listing['error']}")
    tools = {
        str(tool.get("name") or "")
        for tool in (listing.get("result") or {}).get("tools") or []
        if isinstance(tool, dict) and tool.get("name")
    }
    missing = sorted(expected_tools - tools)
    if missing:
        raise ProbeError(f"MCP tools/list is missing expected tools: {missing}")
    return {
        "url": url,
        "server": (initialized.get("result") or {}).get("serverInfo") or {},
        "tools": sorted(tools),
        "expected_tools": sorted(expected_tools),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run an authenticated MCP initialize/tools-list deployment probe."
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--agent-json", type=Path, required=True)
    args = parser.parse_args()

    token = os.getenv("SHARED_MCP_TOKEN", "").strip()
    if len(token) < 32:
        raise ProbeError("SHARED_MCP_TOKEN must contain at least 32 characters")
    result = probe(
        args.url,
        token,
        expected_tools_from_agent(args.agent_json),
    )
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, ProbeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
