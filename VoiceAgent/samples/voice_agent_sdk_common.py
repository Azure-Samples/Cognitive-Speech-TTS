"""Shared preview-SDK publishing and text-runtime helpers for Voice Agent samples."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import os
import re
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote, urlparse, urlunparse

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import VoiceAgentDefinition
from azure.identity import AzureCliCredential, DefaultAzureCredential
from azure.identity.aio import (
    AzureCliCredential as AsyncAzureCliCredential,
    DefaultAzureCredential as AsyncDefaultAzureCredential,
)
from dotenv import dotenv_values
from websockets.asyncio.client import connect


TOKEN_SCOPE = "https://ai.azure.com/.default"
VOICE_AGENT_FEATURE = "VoiceAgents=V1Preview"
API_VERSION = "v1"
TEXT_DELTA_EVENTS = {
    "response.audio_transcript.delta",
    "response.output_audio_transcript.delta",
    "response.output_text.delta",
}
HANDOFF_EVENTS = {
    "session.handoff.started",
    "session.handoff.completed",
    "session.handoff.aborted",
}
FOUNDRY_PROJECT_HOST = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?\.services\.ai\.azure\.com$",
    re.IGNORECASE,
)


def _load_settings(sample_dir: Path) -> dict[str, str]:
    file_values = {
        key: str(value)
        for key, value in dotenv_values(sample_dir / ".env").items()
        if value is not None
    }
    mcp_config_value = (
        os.getenv("VOICE_AGENT_MCP_CONFIG")
        or file_values.get("VOICE_AGENT_MCP_CONFIG")
        or ""
    ).strip()
    mcp_config_values: dict[str, str] = {}
    if mcp_config_value:
        mcp_config_path = Path(mcp_config_value).expanduser()
        if not mcp_config_path.is_absolute():
            mcp_config_path = sample_dir / mcp_config_path
        if not mcp_config_path.is_file():
            raise RuntimeError(
                f"VOICE_AGENT_MCP_CONFIG does not exist: {mcp_config_path}"
            )
        mcp_config_values = {
            key: str(value)
            for key, value in dotenv_values(mcp_config_path).items()
            if value is not None
        }
    names = {
        "AZURE_AI_PROJECT_ENDPOINT",
        "AZURE_CREDENTIAL_MODE",
        "VOICE_AGENT_NAME",
        "VOICE_AGENT_MODEL",
        "VOICE_AGENT_MCP_SERVER_URL",
        "VOICE_AGENT_MCP_CONNECTION_ID",
    }
    settings: dict[str, str] = {}
    for name in names:
        configured_value = (
            mcp_config_values.get(name, "")
            if name.startswith("VOICE_AGENT_MCP_")
            else ""
        )
        settings[name] = (
            os.getenv(name) or configured_value or file_values.get(name) or ""
        ).strip()
    return settings


def _sync_credential(settings: Mapping[str, str]) -> Any:
    mode = settings.get("AZURE_CREDENTIAL_MODE", "default").lower()
    if mode == "default":
        return DefaultAzureCredential()
    if mode == "cli":
        return AzureCliCredential()
    raise RuntimeError("AZURE_CREDENTIAL_MODE must be 'default' or 'cli'.")


def _async_credential(settings: Mapping[str, str]) -> Any:
    mode = settings.get("AZURE_CREDENTIAL_MODE", "default").lower()
    if mode == "default":
        return AsyncDefaultAzureCredential()
    if mode == "cli":
        return AsyncAzureCliCredential()
    raise RuntimeError("AZURE_CREDENTIAL_MODE must be 'default' or 'cli'.")


def _required(settings: Mapping[str, str], name: str) -> str:
    value = settings.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name} before running this sample.")
    return value


def _validate_project_endpoint(endpoint: str) -> str:
    value = endpoint.rstrip("/")
    parsed = urlparse(value)
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
        or "<" in value
        or ">" in value
    ):
        raise ValueError(
            "AZURE_AI_PROJECT_ENDPOINT must be an Azure Foundry URL in the "
            "form https://<account>.services.ai.azure.com/api/projects/"
            "<project-name>."
        )
    return value


def _validate_agent_name(agent_name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,62}", agent_name):
        raise ValueError("VOICE_AGENT_NAME must be a valid Agent name.")
    return agent_name


def _validate_mcp_settings(server_url: str, connection_id: str) -> None:
    parsed = urlparse(server_url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or "<" in server_url
        or ">" in server_url
    ):
        raise ValueError("VOICE_AGENT_MCP_SERVER_URL must be a public HTTPS URL.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", connection_id):
        raise ValueError("VOICE_AGENT_MCP_CONNECTION_ID is invalid.")


def _field(value: Any, name: str) -> Any:
    result = getattr(value, name, None)
    if result is None and isinstance(value, Mapping):
        result = value.get(name)
    return result


def _to_plain(value: Any) -> Any:
    if hasattr(value, "as_dict"):
        return _to_plain(value.as_dict())
    if isinstance(value, Mapping):
        return {str(key): _to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(item) for item in value]
    return value


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(
        _to_plain(value),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_definition(value: Any) -> Any:
    definition = copy.deepcopy(_to_plain(value))
    if not isinstance(definition, dict):
        return definition
    audio = definition.get("audio")
    if not isinstance(audio, dict):
        return definition

    input_config = audio.get("input")
    turn_detection = (
        input_config.get("turn_detection")
        if isinstance(input_config, dict)
        else None
    )
    if (
        isinstance(turn_detection, dict)
        and turn_detection.get("remove_filler_words") is False
    ):
        turn_detection.pop("remove_filler_words")

    output_config = audio.get("output")
    if isinstance(output_config, dict):
        voice = output_config.get("voice")
        voice_type = output_config.get("voice_type")
        if isinstance(voice, str) and isinstance(voice_type, str):
            output_config["voice"] = {"type": voice_type, "name": voice}
            output_config.pop("voice_type")
    return definition


def _walk_mcp_tools(value: Any) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if value.get("type") == "mcp":
            tools.append(value)
        for child in value.values():
            tools.extend(_walk_mcp_tools(child))
    elif isinstance(value, list):
        for child in value:
            tools.extend(_walk_mcp_tools(child))
    return tools


def load_materialized_agent(
    sample_dir: Path,
    settings: Mapping[str, str] | None = None,
) -> tuple[str, str, dict[str, Any]]:
    """Load a sanitized template and inject environment-specific references."""
    settings = settings or _load_settings(sample_dir)
    template_path = sample_dir / "agent.json"
    document = json.loads(template_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("definition"), dict):
        raise RuntimeError(f"{template_path} must contain a definition object.")

    definition = document["definition"]
    if definition.get("kind") != "voice":
        raise RuntimeError(f"{template_path} must contain kind=voice.")

    agent_name_value = (
        settings.get("VOICE_AGENT_NAME") or str(document.get("name") or "")
    ).strip()
    if not agent_name_value:
        raise RuntimeError("Set VOICE_AGENT_NAME or provide name in agent.json.")
    agent_name = _validate_agent_name(agent_name_value)

    model = settings.get("VOICE_AGENT_MODEL", "").strip()
    if model:
        definition["model"] = model

    mcp_server_url = _required(settings, "VOICE_AGENT_MCP_SERVER_URL")
    mcp_connection_id = _required(settings, "VOICE_AGENT_MCP_CONNECTION_ID")
    _validate_mcp_settings(mcp_server_url, mcp_connection_id)
    mcp_tools = _walk_mcp_tools(definition)
    if not mcp_tools:
        raise RuntimeError("The Voice Agent definition contains no MCP tools.")
    for tool in mcp_tools:
        tool["server_url"] = mcp_server_url
        tool["project_connection_id"] = mcp_connection_id
        tool.pop("authorization", None)
        tool.pop("headers", None)

    description = str(document.get("description") or "").strip()
    return agent_name, description, definition


def _latest_version_id(agent: Any) -> str:
    versions = _field(agent, "versions")
    latest = _field(versions, "latest")
    version = _field(latest, "version")
    if version is None:
        raise RuntimeError("The Agent response did not contain versions.latest.version.")
    return str(version)


def _validate_readback(
    expected: dict[str, Any],
    observed_model: Any,
    *,
    require_handoff: bool,
) -> dict[str, Any]:
    observed = _to_plain(observed_model)
    if not isinstance(observed, dict) or observed.get("kind") != "voice":
        raise RuntimeError("Published version did not read back as kind=voice.")
    if observed.get("model") != expected.get("model"):
        raise RuntimeError(
            "Published version model does not match the requested model: "
            f"{observed.get('model')!r} != {expected.get('model')!r}."
        )
    if require_handoff and not isinstance(observed.get("handoff"), dict):
        raise RuntimeError("Published Finance version lost its handoff graph.")

    expected_connections = {
        str(tool.get("project_connection_id"))
        for tool in _walk_mcp_tools(expected)
    }
    observed_connections = {
        str(tool.get("project_connection_id"))
        for tool in _walk_mcp_tools(observed)
    }
    if expected_connections != observed_connections:
        raise RuntimeError(
            "Published MCP connection IDs do not match: "
            f"{observed_connections!r} != {expected_connections!r}."
        )
    return observed


def publish_agent(
    sample_dir: Path,
    *,
    mode: Literal["typed", "raw"],
    check_only: bool,
) -> dict[str, Any]:
    """Publish or read back one Voice Agent with the pinned azure-ai-projects SDK."""
    settings = _load_settings(sample_dir)
    agent_name, description, definition = load_materialized_agent(
        sample_dir,
        settings,
    )
    endpoint = _validate_project_endpoint(
        _required(settings, "AZURE_AI_PROJECT_ENDPOINT")
    )
    require_handoff = mode == "raw"

    with _sync_credential(settings) as credential, AIProjectClient(
        endpoint=endpoint,
        credential=credential,
        allow_preview=True,
    ) as client:
        if check_only:
            agent = client.agents.get(agent_name)
            version_id = _latest_version_id(agent)
        else:
            if mode == "typed":
                created = client.agents.create_version(
                    agent_name=agent_name,
                    definition=VoiceAgentDefinition(definition),
                    description=description,
                )
            else:
                created = client.agents.create_version(
                    agent_name,
                    {
                        "definition": definition,
                        "description": description,
                    },
                )
            version_id = str(_field(created, "version"))
            if not version_id or version_id == "None":
                raise RuntimeError("The SDK create_version response had no version.")
            client.agents.enable(agent_name)

        readback = client.agents.get_version(agent_name, version_id)
        observed = _validate_readback(
            definition,
            _field(readback, "definition"),
            require_handoff=require_handoff,
        )

    summary = {
        "action": "check" if check_only else "publish",
        "agent_name": agent_name,
        "version": version_id,
        "definition_mode": mode,
        "kind": observed.get("kind"),
        "model": observed.get("model"),
        "mcp_connections": sorted(
            {
                str(tool.get("project_connection_id"))
                for tool in _walk_mcp_tools(observed)
            }
        ),
        "handoff_present": isinstance(observed.get("handoff"), dict),
        "requested_sha256": _fingerprint(_canonical_definition(definition)),
        "readback_sha256": _fingerprint(_canonical_definition(observed)),
    }
    print(json.dumps(summary, indent=2))
    return summary


def _realtime_url(endpoint: str, agent_name: str, session_id: str) -> str:
    parsed = urlparse(endpoint.rstrip("/"))
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("AZURE_AI_PROJECT_ENDPOINT must be an HTTPS URL.")
    path = (
        f"{parsed.path.rstrip('/')}/agents/{quote(agent_name, safe='')}"
        "/endpoint/protocols/voice"
    )
    query = (
        f"api-version={quote(API_VERSION, safe='')}"
        f"&agent_session_id={quote(session_id, safe='')}"
    )
    return urlunparse(("wss", parsed.netloc, path, "", query, ""))


def _wire_event(event_type: str, **fields: Any) -> str:
    return json.dumps({"type": event_type, **fields}, separators=(",", ":"))


def _text_input(text: str) -> str:
    return _wire_event(
        "conversation.item.create",
        item={
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        },
    )


def _response_output_types(event: dict[str, Any]) -> set[str]:
    response = event.get("response")
    output = response.get("output") if isinstance(response, dict) else None
    if not isinstance(output, list):
        return set()
    return {
        str(item.get("type"))
        for item in output
        if isinstance(item, dict) and item.get("type")
    }


class EventPrinter:
    def __init__(self, verbose: bool) -> None:
        self.verbose = verbose
        self._line_open = False
        self.event_types: set[str] = set()
        self.handoff_events = 0
        self.mcp_events = 0
        self.mcp_call_events = 0
        self.transcript_characters = 0
        self.conversation_id: str | None = None

    def finish_line(self) -> None:
        if self._line_open:
            print()
            self._line_open = False

    def show(self, event: dict[str, Any]) -> None:
        kind = str(event.get("type") or "<unknown>")
        self.event_types.add(kind)

        if kind == "error":
            self.finish_line()
            error = event.get("error")
            error = error if isinstance(error, dict) else {}
            code = error.get("code") or error.get("type") or "unknown"
            message = error.get("message") or "No message provided"
            raise RuntimeError(f"Voice Agent error [{code}]: {message}")

        if kind == "conversation.created":
            conversation = event.get("conversation")
            self.conversation_id = str(
                event.get("conversation_id")
                or (conversation.get("id") if isinstance(conversation, dict) else "")
                or self.conversation_id
                or ""
            ) or None

        if kind in TEXT_DELTA_EVENTS:
            delta = event.get("delta")
            if isinstance(delta, str) and delta:
                self.transcript_characters += len(delta)
                if not self._line_open:
                    print("agent> ", end="", flush=True)
                    self._line_open = True
                print(delta, end="", flush=True)
            return

        if kind in HANDOFF_EVENTS:
            self.handoff_events += 1
            self.finish_line()
            print(
                "handoff> "
                f"{event.get('from_node_id', '?')} -> {event.get('to_node_id', '?')} "
                f"({kind.rsplit('.', 1)[-1]})"
            )
            return

        if ".mcp_call." in kind or kind.startswith("mcp_list_tools."):
            self.mcp_events += 1
            if ".mcp_call." in kind:
                self.mcp_call_events += 1
            self.finish_line()
            name = event.get("name") or event.get("tool_name")
            print(f"mcp> {name or '<event>'} ({kind})")
            return

        if kind == "response.done":
            response = event.get("response")
            output = response.get("output") if isinstance(response, dict) else None
            if isinstance(output, list):
                for item in output:
                    if not isinstance(item, dict):
                        continue
                    if (
                        item.get("type") == "function_call"
                        and item.get("name") == "handoff"
                    ):
                        self.handoff_events += 1
                        self.finish_line()
                        print("handoff> synthesized function call")

        if self.verbose and kind not in {
            "response.audio.delta",
            "response.output_audio.delta",
        }:
            self.finish_line()
            print(f"event> {kind}")

    def summary(self, agent_name: str, session_id: str) -> dict[str, Any]:
        return {
            "agent_name": agent_name,
            "agent_session_id": session_id,
            "conversation_id": self.conversation_id,
            "event_types": sorted(self.event_types),
            "handoff_events": self.handoff_events,
            "mcp_events": self.mcp_events,
            "mcp_call_events": self.mcp_call_events,
            "transcript_characters": self.transcript_characters,
        }


async def _receive_until(
    websocket: Any,
    printer: EventPrinter,
    *,
    phase: str,
    timeout_seconds: float,
    wait_for_session: bool = False,
) -> dict[str, Any]:
    while True:
        try:
            raw = await asyncio.wait_for(websocket.recv(), timeout=timeout_seconds)
        except asyncio.TimeoutError as error:
            printer.finish_line()
            raise RuntimeError(
                f"Timed out after {timeout_seconds:g}s waiting for {phase}."
            ) from error

        try:
            event = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as error:
            raise RuntimeError("Voice Agent returned invalid JSON.") from error
        if not isinstance(event, dict):
            raise RuntimeError("Voice Agent event must be a JSON object.")

        printer.show(event)
        kind = event.get("type")
        if wait_for_session and kind == "session.updated":
            printer.finish_line()
            return event
        if not wait_for_session and kind == "response.done":
            printer.finish_line()
            response = event.get("response")
            response = response if isinstance(response, dict) else {}
            status = response.get("status")
            if status not in {None, "completed"}:
                raise RuntimeError(
                    f"Voice Agent response ended with status={status!r}: "
                    f"{response.get('status_details')!r}"
                )
            if _response_output_types(event) & {"function_call", "mcp_call"}:
                continue
            return event


async def run_text_session(
    sample_dir: Path,
    *,
    messages: list[str],
    connect_only: bool,
    verbose: bool,
    timeout_seconds: float,
    expect_mcp: bool,
    expect_handoff: bool,
    evidence_file: Path | None,
) -> dict[str, Any]:
    settings = _load_settings(sample_dir)
    endpoint = _validate_project_endpoint(
        _required(settings, "AZURE_AI_PROJECT_ENDPOINT")
    )
    agent_name = _validate_agent_name(_required(settings, "VOICE_AGENT_NAME"))
    session_id = f"sdk-sample-{uuid.uuid4().hex}"
    url = _realtime_url(endpoint, agent_name, session_id)
    printer = EventPrinter(verbose)

    credential = _async_credential(settings)
    try:
        token = await credential.get_token(TOKEN_SCOPE)
        headers = {
            "Authorization": f"Bearer {token.token}",
            "Foundry-Features": VOICE_AGENT_FEATURE,
        }
        async with connect(
            url,
            additional_headers=headers,
            max_size=None,
            ping_timeout=None,
            open_timeout=timeout_seconds,
        ) as websocket:
            await _receive_until(
                websocket,
                printer,
                phase="session readiness",
                timeout_seconds=timeout_seconds,
                wait_for_session=True,
            )
            print("session=ready")
            await _receive_until(
                websocket,
                printer,
                phase="opening response",
                timeout_seconds=timeout_seconds,
            )

            if not connect_only:
                total_turns = len(messages)
                for index, message in enumerate(messages, start=1):
                    value = message.strip()
                    if not value:
                        raise ValueError("Messages cannot be empty.")
                    print(f"you> (non-interactive turn {index}/{total_turns})")
                    await websocket.send(_text_input(value))
                    await websocket.send(_wire_event("response.create"))
                    await _receive_until(
                        websocket,
                        printer,
                        phase=f"Agent response {index}/{total_turns}",
                        timeout_seconds=timeout_seconds,
                    )
    finally:
        await credential.close()

    summary = printer.summary(agent_name, session_id)
    if evidence_file is not None:
        evidence_file.parent.mkdir(parents=True, exist_ok=True)
        evidence_file.write_text(
            json.dumps(summary, indent=2) + "\n",
            encoding="utf-8",
        )
    if expect_mcp and summary["mcp_call_events"] == 0:
        raise RuntimeError("The smoke test expected an MCP call but observed none.")
    if expect_handoff and summary["handoff_events"] == 0:
        raise RuntimeError("The smoke test expected handoff activity but observed none.")
    if summary["transcript_characters"] == 0:
        raise RuntimeError("The smoke test observed no Agent transcript output.")
    print(json.dumps(summary, indent=2))
    return summary


def _add_runtime_arguments(
    parser: argparse.ArgumentParser,
    *,
    allow_messages: bool,
) -> None:
    if allow_messages:
        parser.add_argument(
            "--message",
            action="append",
            required=True,
            help="Send one non-interactive turn; repeat for multiple turns.",
        )
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--expect-mcp", action="store_true")
    parser.add_argument("--expect-handoff", action="store_true")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--evidence-file", type=Path)


def sample_cli(sample_dir: Path, *, mode: Literal["typed", "raw"]) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Publish, verify, or run this Voice Agent with the preview "
            "azure-ai-projects SDK."
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "publish",
        help="Create and enable an immutable Agent version, then read it back.",
    )
    commands.add_parser(
        "check",
        help="Read and validate the latest published Agent version.",
    )
    connect_parser = commands.add_parser(
        "connect",
        help="Validate Voice session readiness and the opening response.",
    )
    _add_runtime_arguments(connect_parser, allow_messages=False)
    run_parser = commands.add_parser(
        "run",
        help="Run one or more text turns against the published Voice Agent.",
    )
    _add_runtime_arguments(run_parser, allow_messages=True)
    args = parser.parse_args()

    if args.command in {"publish", "check"}:
        publish_agent(
            sample_dir,
            mode=mode,
            check_only=args.command == "check",
        )
        return

    if args.timeout <= 0:
        parser.error("--timeout must be positive.")
    asyncio.run(
        run_text_session(
            sample_dir,
            messages=args.message if args.command == "run" else [],
            connect_only=args.command == "connect",
            verbose=args.verbose,
            timeout_seconds=args.timeout,
            expect_mcp=args.expect_mcp,
            expect_handoff=args.expect_handoff,
            evidence_file=args.evidence_file,
        )
    )
