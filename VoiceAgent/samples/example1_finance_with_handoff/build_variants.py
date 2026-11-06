#!/usr/bin/env python3
"""Build the two Example 1 Agent variants from one shared base definition."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
BASE_PATH = ROOT / "agent.base.json"
ALLOWED_HANDOFF_TOOL_TYPES = {"function", "mcp", "system", "toolbox"}
VARIANTS = {
    "realtime": (
        ROOT / "profiles" / "realtime.json",
        ROOT / "agent.realtime.json",
    ),
    "cascade-luna": (
        ROOT / "profiles" / "cascade-luna.json",
        ROOT / "agent.cascade-luna.json",
    ),
}
COMPATIBILITY_PATH = ROOT / "agent.json"


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def iter_mcp_tools(value: Any):
    if isinstance(value, dict):
        if value.get("type") == "mcp":
            yield value
        for child in value.values():
            yield from iter_mcp_tools(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_mcp_tools(child)


def render_variants() -> dict[Path, str]:
    base = load_json(BASE_PATH)
    rendered: dict[Path, str] = {}
    names: set[str] = set()
    shared_handoff = (base.get("definition") or {}).get("handoff")
    for profile_path, output_path in VARIANTS.values():
        document = deep_merge(base, load_json(profile_path))
        name = str(document.get("name") or "")
        definition = document.get("definition")
        if not name or name in names:
            raise ValueError(f"variant Agent name must be unique: {name!r}")
        if not isinstance(definition, dict) or definition.get("kind") != "voice":
            raise ValueError(f"{profile_path} did not produce a Voice Agent")
        if definition.get("handoff") != shared_handoff:
            raise ValueError(f"{profile_path} must not override the shared handoff graph")
        invalid_tools = [
            tool
            for node in (definition.get("handoff") or {}).get("nodes") or []
            for tool in (node.get("config") or {}).get("tools") or []
            if tool.get("type") not in ALLOWED_HANDOFF_TOOL_TYPES
        ]
        if invalid_tools:
            raise ValueError(
                f"{profile_path} produced unsupported handoff tools: {invalid_tools}"
            )
        if any(
            tool.get("server_url") or tool.get("project_connection_id")
            for tool in iter_mcp_tools(definition)
        ):
            raise ValueError(f"{profile_path} produced a non-portable MCP reference")
        names.add(name)
        rendered[output_path] = json.dumps(document, indent=2) + "\n"
    rendered[COMPATIBILITY_PATH] = rendered[VARIANTS["realtime"][1]]
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when committed variant files do not match the shared base and profiles.",
    )
    args = parser.parse_args()

    stale: list[Path] = []
    for path, content in render_variants().items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                stale.append(path)
        else:
            path.write_text(content, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")
    if stale:
        for path in stale:
            print(f"stale {path.relative_to(ROOT)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
