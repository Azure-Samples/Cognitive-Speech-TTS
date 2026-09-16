"""Validate, create, and inspect one native Foundry voice agent without a UI."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
from importlib import metadata
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    """The input is outside this sample's supported configuration."""


class LifecycleError(RuntimeError):
    """A lifecycle operation failed, possibly after creating an agent."""

    def __init__(self, message: str, report: dict[str, Any] | None = None):
        super().__init__(message)
        self.report = report or {}


def _object(value: Any, keys: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{path} must be an object.")
    if value.keys() - keys:
        raise ConfigurationError(f"{path} contains unsupported fields.")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{path} must be a nonempty string.")
    if value != value.strip() or any(c in value for c in "<>\x00") or "${" in value:
        raise ConfigurationError(f"{path} contains a placeholder or invalid whitespace.")
    return value


def _name(value: Any, path: str) -> str:
    value = _text(value, path)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,62}", value):
        raise ConfigurationError(f"{path} must be a name, not an ID, URL, or resource path.")
    return value


def _runtime_name(value: Any, path: str) -> str:
    """Reject obvious URLs/paths, without claiming to identify every asset ID."""
    value = _text(value, path)
    if (
        re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", value)
        or any(c in value for c in "/\\\r\n\t")
        or value in (".", "..")
        or value.lower().startswith("www.")
    ):
        raise ConfigurationError(f"{path} must be a runtime asset name, not a URL or file/resource path.")
    return value


def _url(value: Any, path: str):
    value = _text(value, path)
    try:
        parts = urlsplit(value)
        valid = (
            parts.scheme == "https"
            and parts.hostname
            and not parts.username
            and not parts.password
            and not parts.fragment
            and parts.port in (None, 443)
        )
    except ValueError:
        valid = False
    if not valid:
        raise ConfigurationError(f"{path} must be an HTTPS URL without credentials.")
    return parts


def _pcm(value: Any, path: str) -> None:
    value = _object(value, {"type", "rate"}, path)
    if value != {"type": "audio/pcm", "rate": 24000}:
        raise ConfigurationError(f"{path} must select audio/pcm at 24000 Hz.")


def validate_config(config: Any) -> dict[str, Any]:
    """Validate the supported voice/avatar combinations without credentials or a network."""
    config = _object(config, {"project_endpoint", "agent_name", "description", "definition"}, "config")
    endpoint = _url(config.get("project_endpoint"), "project_endpoint")
    if (
        not endpoint.hostname.endswith(".services.ai.azure.com")
        or not re.fullmatch(r"/api/projects/[A-Za-z0-9_-]+", endpoint.path)
        or endpoint.query
    ):
        raise ConfigurationError("project_endpoint must be a Foundry project endpoint.")
    name = _name(config.get("agent_name"), "agent_name")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", name):
        raise ConfigurationError("agent_name must start/end with a letter or digit; only interior hyphens are allowed.")
    _text(config.get("description"), "description")
    definition = _object(
        config.get("definition"),
        {"kind", "model_type", "model", "instructions", "audio", "output_modalities", "tools", "store", "avatar"},
        "definition",
    )
    if "avatar" in definition:
        common = {"type", "character", "customized", "output_protocol"}
        avatar = _object(definition["avatar"], common | {"style", "model"}, "avatar")
        if avatar.get("type") == "video_avatar":
            _object(avatar, common | {"style"}, "avatar")
            _text(avatar.get("style"), "avatar.style")
            if avatar.get("customized") is not False:
                raise ConfigurationError("avatar.customized must be the boolean false for a standard avatar.")
        elif avatar.get("type") == "photo_avatar":
            _object(avatar, common | {"model"}, "avatar")
            if avatar.get("customized") is not True:
                raise ConfigurationError("avatar.customized must be the boolean true for a custom photo avatar.")
            if avatar.get("model") != "vasa-1":
                raise ConfigurationError("avatar.model must be vasa-1.")
        else:
            raise ConfigurationError("avatar.type must be video_avatar or photo_avatar, not a hyphenated runtime wire value.")
        _runtime_name(avatar.get("character"), "avatar.character")
        if avatar.get("output_protocol") not in ("webrtc", "websocket"):
            raise ConfigurationError("avatar.output_protocol must be webrtc or websocket.")
    if definition.get("kind") != "voice":
        raise ConfigurationError("definition.kind must be voice, not prompt or hosted.")
    if definition.get("model_type") not in ("managed", "self_deployed"):
        raise ConfigurationError("model_type must be managed or self_deployed.")
    _text(definition.get("model"), "definition.model")
    _text(definition.get("instructions"), "definition.instructions")
    modalities = ["text", "audio", "avatar"] if "avatar" in definition else ["text", "audio"]
    if definition.get("output_modalities") != modalities:
        raise ConfigurationError(f"output_modalities must be {modalities} for this configuration.")
    if not isinstance(definition.get("store"), bool):
        raise ConfigurationError("store must be an explicit boolean; false avoids conversation storage.")

    audio = _object(definition.get("audio"), {"input", "output"}, "audio")
    audio_input = _object(audio.get("input"), {"format", "turn_detection"}, "audio.input")
    _pcm(audio_input.get("format"), "audio.input.format")
    turn = _object(audio_input.get("turn_detection"), {"type", "threshold", "prefix_padding_ms", "silence_duration_ms"}, "turn_detection")
    if turn.get("type") != "server_vad":
        raise ConfigurationError("The baseline uses server_vad turn detection.")
    threshold = turn.get("threshold")
    if type(threshold) not in (int, float) or not 0 <= threshold <= 1:
        raise ConfigurationError("VAD threshold must be a number between 0 and 1.")
    for key in ("prefix_padding_ms", "silence_duration_ms"):
        if type(turn.get(key)) is not int or not 0 <= turn[key] <= 5000:
            raise ConfigurationError(f"VAD {key} must be an integer between 0 and 5000.")
    output = _object(audio.get("output"), {"format", "voice", "voice_type", "personal_voice_model"}, "audio.output")
    voice_type = output.get("voice_type")
    if voice_type == "azure-personal":
        _runtime_name(output.get("voice"), "audio.output.voice")
        if output.get("personal_voice_model") not in ("DragonLatestNeural", "DragonHDOmniLatestNeural"):
            raise ConfigurationError("Personal Voice requires an explicit DragonLatestNeural or DragonHDOmniLatestNeural personal_voice_model.")
    elif voice_type == "azure-standard":
        if "personal_voice_model" in output:
            raise ConfigurationError("azure-standard must not include personal_voice_model.")
        _text(output.get("voice"), "audio.output.voice")
    else:
        raise ConfigurationError("audio.output.voice_type must be azure-standard or azure-personal.")
    _pcm(output.get("format"), "audio.output.format")

    tools = definition.get("tools")
    if not isinstance(tools, list) or len(tools) != 1:
        raise ConfigurationError("The baseline requires exactly one Knowledge MCP tool.")
    tool = _object(tools[0], {"type", "server_label", "server_url", "project_connection_id", "allowed_tools", "require_approval"}, "tools[0]")
    if tool.get("type") != "mcp" or tool.get("require_approval") != "never":
        raise ConfigurationError("Configure the trusted Knowledge MCP tool with require_approval=never.")
    _name(tool.get("server_label"), "tools[0].server_label")
    _name(tool.get("project_connection_id"), "tools[0].project_connection_id")
    mcp = _url(tool.get("server_url"), "tools[0].server_url")
    if (
        not mcp.hostname.endswith(".search.windows.net")
        or not re.fullmatch(r"/knowledgebases/[A-Za-z0-9_-]+/mcp", mcp.path)
        or not re.fullmatch(r"api-version=[0-9]{4}-[0-9]{2}-[0-9]{2}(?:-[Pp]review)?", mcp.query)
    ):
        raise ConfigurationError(
            "Copy the Search Knowledge MCP URL from the RemoteTool connection target, with exactly one "
            "api-version=YYYY-MM-DD or YYYY-MM-DD-preview query parameter and no extra parameters."
        )
    if tool.get("allowed_tools") != ["knowledge_base_retrieve"]:
        raise ConfigurationError("Only knowledge_base_retrieve is allowed.")
    return deepcopy(config)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ConfigurationError("Duplicate JSON keys are not allowed.")
        result[key] = value
    return result


def load_config(path: Path) -> dict[str, Any]:
    return validate_config(json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object))


def require_sdk() -> None:
    """Verify pip's wheel provenance before constructing any Azure client."""
    expected = "f857a1281e2fa3414f25e02aed95dfe2275495027b0a764f38921a8589f15e75"
    try:
        dist = metadata.distribution("azure-ai-projects")
        origin = json.loads(dist.read_text("direct_url.json") or "{}")
        archive = origin.get("archive_info", {})
        digest = archive.get("hashes", {}).get("sha256")
        legacy_hash = archive.get("hash", "")
        valid = dist.version == "2.7.0b1" and (
            digest == expected or legacy_hash == f"sha256={expected}"
        )
    except (metadata.PackageNotFoundError, ValueError, AttributeError):
        valid = False
    if not valid:
        raise ConfigurationError(
            "Install the exact bundled Projects wheel from VoiceAgent/dist using this sample's "
            "requirements. A same-version PyPI or source installation is not this SDK build."
        )


def build_definition(config: dict[str, Any]):
    from azure.ai.projects.models import VoiceAgentDefinition

    return VoiceAgentDefinition(deepcopy(config["definition"]))


def _data(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else value.as_dict()


def definition_hash(definition: dict[str, Any]) -> str:
    payload = json.dumps(definition, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _matches(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and _matches(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected) == len(actual) and all(_matches(e, a) for e, a in zip(expected, actual))
    return type(expected) is type(actual) and expected == actual


def _version_report(version: dict[str, Any]) -> dict[str, Any]:
    return {
        "agent_name": version.get("name"),
        "version_id": version.get("id"),
        "version": version.get("version"),
        "agent_guid": version.get("agent_guid"),
    }


def _verify(client: Any, config: dict[str, Any], version_id: str, report: dict[str, Any]) -> dict[str, Any]:
    saved = _data(client.agents.get_version(agent_name=config["agent_name"], agent_version=version_id))
    agent = _data(client.agents.get(agent_name=config["agent_name"]))
    requested = config["definition"]
    actual = saved.get("definition", {})
    report.update({
        "agent_id": agent.get("id"),
        "state": agent.get("state"),
        "agent_endpoint": agent.get("agent_endpoint"),
        "requested_definition_sha256": definition_hash(requested),
        "readback_definition_sha256": definition_hash(actual),
        "definition_verified": False,
    })
    if (
        saved.get("name") != config["agent_name"]
        or agent.get("name") != config["agent_name"]
        or saved.get("version") != version_id
        or not saved.get("id")
        or not agent.get("id")
        or (report.get("version_id") and saved["id"] != report["version_id"])
    ):
        raise LifecycleError("Agent/version identifiers failed read-back verification.", report)
    if not _matches(requested, actual) or ("avatar" not in requested and actual.get("avatar") is not None):
        raise LifecycleError("Stored definition differs from the requested configuration.", report)
    saved_output = actual.get("audio", {}).get("output", {})
    if requested["audio"]["output"]["voice_type"] == "azure-standard" and saved_output.get("personal_voice_model") is not None:
        raise LifecycleError("Stored voice contains an unexpected personal model.", report)
    report.update(_version_report(saved))
    report["definition_verified"] = True
    return report


def _failure(action: str, exc: Exception, report: dict[str, Any] | None = None) -> LifecycleError:
    status = getattr(exc, "status_code", None)
    suffix = f" (HTTP {status})" if isinstance(status, int) else ""
    return LifecycleError(f"{action} failed{suffix}. Check access and service diagnostics; do not blindly retry creation.", report)


def create_agent(client: Any, config: dict[str, Any]) -> dict[str, Any]:
    config = validate_config(config)
    try:
        client.agents.get(agent_name=config["agent_name"])
    except Exception as exc:
        if getattr(exc, "status_code", None) != 404:
            raise _failure("Existing-name check", exc) from exc
    else:
        raise LifecycleError("The agent name already exists. Choose a fresh name; no new version was created.")
    report: dict[str, Any] = {"creation_status": "unknown", "definition_verified": False}
    try:
        created = _data(client.agents.create_version(
            agent_name=config["agent_name"],
            description=config["description"],
            definition=build_definition(config),
            retry_total=0,
        ))
        report.update(_version_report(created))
        report["creation_status"] = "created"
        if not created.get("version") or not created.get("id") or created.get("name") != config["agent_name"]:
            raise LifecycleError("Creation returned incomplete or inconsistent identifiers; inspect the agent before retrying.", report)
        return _verify(client, config, created["version"], report)
    except LifecycleError:
        raise
    except Exception as exc:
        raise _failure("Creation or read-back", exc, report) from exc


def show_agent(client: Any, config: dict[str, Any], version: str) -> dict[str, Any]:
    config = validate_config(config)
    _text(version, "version")
    try:
        return _verify(client, config, version, {"definition_verified": False})
    except LifecycleError:
        raise
    except Exception as exc:
        raise _failure("Read-back", exc) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "create", "show"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
        if name != "validate":
            command.add_argument("--output", type=Path, help="New local JSON file; existing files are never overwritten.")
        if name == "show":
            command.add_argument("--version", required=True, help="Exact version, not latest.")
    args = parser.parse_args(argv)
    output = None
    try:
        config = load_config(args.config)
        if args.command == "validate":
            voice_type = config["definition"]["audio"]["output"]["voice_type"]
            avatar_type = config["definition"].get("avatar", {}).get("type")
            avatar = {"video_avatar": "with standard avatar", "photo_avatar": "with custom photo avatar"}.get(avatar_type, "without avatar")
            print(f"Configuration valid: native Knowledge + {voice_type} {avatar}. No Azure calls made.")
            return 0
        if args.command == "show" and args.version.lower() == "latest":
            raise ConfigurationError("Specify an exact version, not latest.")
        if args.output and (args.output.exists() or args.output.is_symlink()):
            raise ConfigurationError("Output already exists; choose a new local report path.")
        require_sdk()
        if args.output:
            output = args.output.open("x", encoding="utf-8")
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential

        with DefaultAzureCredential() as credential, AIProjectClient(
            endpoint=config["project_endpoint"], credential=credential, allow_preview=True, retry_total=0,
        ) as client:
            if args.command == "create":
                report = create_agent(client, config)
            else:
                report = show_agent(client, config, args.version)
        rendered = json.dumps(report, indent=2, allow_nan=False)
        print(rendered)
        if output:
            output.write(rendered + "\n")
        return 0
    except LifecycleError as exc:
        report = {**exc.report, "error": str(exc)}
        rendered = json.dumps(report, indent=2)
        print(rendered, file=sys.stderr)
        if output:
            output.write(rendered + "\n")
        return 1
    except (ConfigurationError, OSError, ValueError, ImportError) as exc:
        message = str(exc) if isinstance(exc, ConfigurationError) else type(exc).__name__
        print(f"Local configuration, output, or dependency error: {message}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(str(_failure("Client setup", exc)), file=sys.stderr)
        return 1
    finally:
        if output:
            output.close()


if __name__ == "__main__":
    raise SystemExit(main())
