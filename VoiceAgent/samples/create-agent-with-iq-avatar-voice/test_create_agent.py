"""Offline validation, lifecycle, and real SDK HTTP-contract tests with fake assets."""

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import socket
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import create_agent as app


ROOT = Path(__file__).resolve().parent
try:
    from azure.ai.projects import AIProjectClient, __version__ as sdk_version
    from azure.ai.projects.models import (
        AgentDetails, AgentVersionDetails, VoiceAgentAudioOutputConfig,
        VoiceAgentAvatarConfig, VoiceAgentDefinition,
    )
    from azure.core.credentials import AccessToken
    from azure.core.pipeline.transport import HttpResponse, HttpTransport

    app.require_sdk()
    SDK_AVAILABLE = sdk_version == "2.7.0b1"
except (ImportError, app.ConfigurationError):
    SDK_AVAILABLE = False

SDK_REQUIRED = unittest.skipUnless(SDK_AVAILABLE, "Exact bundled Projects SDK dependencies are unavailable")


PERSONAL_MODELS = ("DragonLatestNeural", "DragonHDOmniLatestNeural")
PROTOCOLS = ("webrtc", "websocket")
AVATARS = ("none", "standard", "photo")
SEARCH_API_VERSIONS = ("2026-05-01-preview", "2026-08-01-preview", "2026-04-01", "2025-11-01-Preview")


def example_config(example="agent.example.json"):
    text = (ROOT / example).read_text(encoding="utf-8")
    for placeholder, value in {
        "<account>": "sample-account",
        "<project>": "sample-project",
        "<new-agent-name>": "sample-agent",
        "<search-service>": "sample-search",
        "<knowledge-base>": "sample-knowledge",
        "<search-api-version>": SEARCH_API_VERSIONS[0],
        "<project-connection-name>": "sample-connection",
        "<personal-voice-name>": "fake-personal-voice",
        "<custom-photo-avatar-name>": "fake-photo-avatar",
    }.items():
        text = text.replace(placeholder, value)
    return json.loads(text)


def config(*, personal=False, avatar="none", model=PERSONAL_MODELS[0], protocol=PROTOCOLS[0]):
    settings = example_config()
    output = settings["definition"]["audio"]["output"]
    if personal:
        output.update(voice_type="azure-personal", voice="fake-personal-voice", personal_voice_model=model)
    else:
        output.update(voice_type="azure-standard", voice="en-US-Andrew:DragonHDLatestNeural")
        output.pop("personal_voice_model", None)
    if avatar == "standard":
        settings["definition"]["avatar"] = {
            "type": "video_avatar", "character": "harry", "style": "business",
            "customized": False, "output_protocol": protocol,
        }
    elif avatar == "photo":
        settings["definition"]["avatar"] = {
            "type": "photo_avatar", "character": "fake-photo-avatar", "customized": True,
            "model": "vasa-1", "output_protocol": protocol,
        }
    elif avatar == "none":
        settings["definition"].pop("avatar", None)
    else:
        raise ValueError(f"Unknown test avatar: {avatar}")
    settings["definition"]["output_modalities"] = ["text", "audio"] + (["avatar"] if avatar != "none" else [])
    return settings


def combinations():
    for personal in (False, True):
        for avatar in AVATARS:
            for model in PERSONAL_MODELS if personal else (None,):
                for protocol in PROTOCOLS if avatar != "none" else (None,):
                    yield config(personal=personal, avatar=avatar, model=model, protocol=protocol)


def asset_mismatches(settings):
    definition = settings["definition"]
    replacements = {
        "avatar": {
            "type": "photo-avatar", "character": "fake-other-avatar", "customized": True,
            "style": "casual", "model": "other-model", "output_protocol": "websocket",
        },
        "output": {
            "voice_type": "azure-standard", "voice": "fake-other-voice",
            "personal_voice_model": "DragonHDOmniLatestNeural",
        },
    }
    for section, fields in replacements.items():
        original = definition.get("avatar", {}) if section == "avatar" else definition["audio"]["output"]
        for key, replacement in fields.items():
            if key not in original:
                continue
            if replacement == original[key]:
                replacement = {
                    "customized": False, "voice_type": "azure-personal",
                    "personal_voice_model": "DragonLatestNeural", "output_protocol": "webrtc",
                }[key]
            for mode in ("missing", "changed", "null"):
                actual = deepcopy(definition)
                target = actual["avatar"] if section == "avatar" else actual["audio"]["output"]
                if mode == "missing":
                    del target[key]
                else:
                    target[key] = replacement if mode == "changed" else None
                yield f"{section}.{key}.{mode}", actual
    for key in ("avatar", "output_modalities"):
        if key in definition:
            actual = deepcopy(definition)
            del actual[key]
            yield f"{key}.missing", actual
    if "avatar" in definition:
        actual = deepcopy(definition)
        actual["avatar"]["customized"] = int(actual["avatar"]["customized"])
        yield "avatar.customized.integer", actual
    actual = deepcopy(definition)
    actual["output_modalities"] = ["text", "audio"] if "avatar" in definition else ["text", "audio", "avatar"]
    yield "output_modalities.changed", actual


def service_error(status):
    from azure.core.exceptions import HttpResponseError

    error = HttpResponseError(message="Private service response must not be printed")
    error.status_code = status
    return error


def client_for(settings, *, exists=False):
    client = MagicMock()
    version = {
        "name": settings["agent_name"], "id": "version-object-id", "version": "7",
        "agent_guid": "service-agent-guid", "definition": deepcopy(settings["definition"]),
    }
    details = {"name": settings["agent_name"], "id": "agent-object-id", "state": "enabled", "agent_endpoint": None}
    client.agents.get.side_effect = [details, details] if exists else [service_error(404), details]
    client.agents.create_version.return_value = deepcopy(version)
    client.agents.get_version.return_value = deepcopy(version)
    return client


class ConfigurationTests(unittest.TestCase):
    def test_valid_without_sdk_credentials_or_network(self):
        with patch.object(socket, "socket", side_effect=AssertionError("network")):
            self.assertEqual(app.validate_config(config()), config())

    def test_validation_returns_independent_configuration(self):
        original = config()
        validated = app.validate_config(original)
        validated["definition"]["tools"].clear()
        self.assertEqual(len(original["definition"]["tools"]), 1)

    def test_six_combinations_and_models_and_protocols(self):
        for settings in combinations():
            with self.subTest(definition=settings["definition"]), patch.object(socket, "socket", side_effect=AssertionError("network")):
                self.assertEqual(app.validate_config(settings), settings)

    @SDK_REQUIRED
    def test_sdk_preserves_exact_native_payload_and_typed_assets(self):
        for settings in combinations():
            expected = settings["definition"]
            with self.subTest(output=expected["audio"]["output"], avatar=expected.get("avatar")):
                definition = app.build_definition(settings)
                self.assertIsInstance(definition, VoiceAgentDefinition)
                self.assertIsInstance(definition.audio.output, VoiceAgentAudioOutputConfig)
                for key, value in expected["audio"]["output"].items():
                    if key != "format":
                        self.assertEqual(getattr(definition.audio.output, key), value)
                if "avatar" in expected:
                    self.assertIsInstance(definition.avatar, VoiceAgentAvatarConfig)
                    for key, value in expected["avatar"].items():
                        self.assertEqual(getattr(definition.avatar, key), value)
                else:
                    self.assertIsNone(definition.avatar)
                self.assertEqual(definition.as_dict(), expected)

    def test_examples_require_placeholder_replacement(self):
        for filename in ("agent.example.json", "agent.personal.example.json"):
            with self.subTest(filename=filename), self.assertRaises(app.ConfigurationError):
                app.load_config(ROOT / filename)

    def test_default_example_selects_andrew_and_harry_business(self):
        settings = example_config()
        self.assertEqual(app.validate_config(settings), settings)
        self.assertEqual(settings["definition"]["audio"]["output"], {
            "format": {"type": "audio/pcm", "rate": 24000},
            "voice_type": "azure-standard", "voice": "en-US-Andrew:DragonHDLatestNeural",
        })
        self.assertEqual(settings["definition"]["avatar"], {
            "type": "video_avatar", "character": "harry", "style": "business",
            "customized": False, "output_protocol": "webrtc",
        })
        self.assertEqual(settings["definition"]["output_modalities"], ["text", "audio", "avatar"])

    def test_personal_example_valid_after_placeholder_replacement(self):
        settings = example_config("agent.personal.example.json")
        self.assertEqual(app.validate_config(settings), settings)
        self.assertEqual(settings["definition"]["audio"]["output"]["voice_type"], "azure-personal")
        self.assertEqual(settings["definition"]["audio"]["output"]["personal_voice_model"], "DragonLatestNeural")
        self.assertEqual(settings["definition"]["avatar"], {
            "type": "photo_avatar", "character": "fake-photo-avatar", "customized": True,
            "model": "vasa-1", "output_protocol": "webrtc",
        })

    def test_rejects_invalid_configurations(self):
        cases = [
            ([], "list"),
            ({**config(), "token": "not-a-token"}, "credential"),
            ({**config(), "agent_name": "path/name"}, "agent path"),
            ({**config(), "project_endpoint": "http://sample.services.ai.azure.com/api/projects/test"}, "http"),
            ({**config(), "project_endpoint": "https://sample.services.ai.azure.com.evil.invalid/api/projects/test"}, "foreign host"),
            ({**config(), "project_endpoint": "https://user:password@sample.services.ai.azure.com/api/projects/test"}, "userinfo"),
            ({**config(), "project_endpoint": "https://sample.services.ai.azure.com/api/projects/test?token=fake"}, "query"),
            ({**config(), "project_endpoint": "https://sample.services.ai.azure.com:bad/api/projects/test"}, "port"),
        ]
        for settings, label in cases:
            with self.subTest(label=label), self.assertRaises(app.ConfigurationError):
                app.validate_config(settings)

    def test_agent_name_matches_native_contract(self):
        for name in ("sample_agent", "sample-agent-", "-sample-agent", "a" * 64):
            settings = config()
            settings["agent_name"] = name
            with self.subTest(name=name), self.assertRaises(app.ConfigurationError):
                app.validate_config(settings)
        for name in ("a", "sample-agent", "a" * 63):
            settings = config()
            settings["agent_name"] = name
            self.assertEqual(app.validate_config(settings)["agent_name"], name)

    def test_rejects_unsupported_definition(self):
        for key, value in [("kind", "hosted"), ("model_type", "voice-live"), ("store", "false"), ("output_modalities", ["text"]), ("unknown", True)]:
            settings = config()
            settings["definition"][key] = value
            with self.subTest(key=key), self.assertRaises(app.ConfigurationError):
                app.validate_config(settings)

    def test_unsupported_voice_types_blocked_before_client_calls(self):
        for voice_type in ("avatar-voice-sync", "azure-custom", "openai", "azure-realtime-native", None):
            settings = config(personal=True)
            settings["definition"]["audio"]["output"]["voice_type"] = voice_type
            self.assert_rejected_before_client(settings)

    def assert_rejected_before_client(self, settings):
        client = MagicMock()
        with self.assertRaises(app.ConfigurationError):
            app.create_agent(client, settings)
        self.assertEqual(client.mock_calls, [])

    def test_personal_voice_requires_explicit_supported_model(self):
        for value in (None, "", "dragonlatestneural", "other-model", True, []):
            settings = config(personal=True)
            settings["definition"]["audio"]["output"]["personal_voice_model"] = value
            with self.subTest(value=value):
                self.assert_rejected_before_client(settings)
        settings = config(personal=True)
        del settings["definition"]["audio"]["output"]["personal_voice_model"]
        self.assert_rejected_before_client(settings)

    def test_standard_voice_rejects_personal_model_even_null(self):
        for value in (*PERSONAL_MODELS, None, ""):
            settings = config()
            settings["definition"]["audio"]["output"]["personal_voice_model"] = value
            with self.subTest(value=value):
                self.assert_rejected_before_client(settings)

    def test_runtime_assets_require_names_not_obvious_urls_or_paths(self):
        values = (
            None, "", " ", 42, "<replace-me>", "https://example.invalid/asset", "file:asset.wav",
            "/subscriptions/fake/resource", "./photo.png", "../photo.png", "photo/name",
            "C:\\fake\\voice.wav", "\\\\fake\\share", "www.example.invalid", "bad\nname",
        )
        for field in ("voice", "character"):
            for value in values:
                settings = config(personal=True, avatar="photo")
                asset = settings["definition"]["audio"]["output"] if field == "voice" else settings["definition"]["avatar"]
                asset[field] = value
                with self.subTest(field=field, value=value):
                    self.assert_rejected_before_client(settings)
            settings = config(personal=True, avatar="photo")
            asset = settings["definition"]["audio"]["output"] if field == "voice" else settings["definition"]["avatar"]
            del asset[field]
            self.assert_rejected_before_client(settings)

    def test_opaque_runtime_names_are_not_classified_as_known_ids(self):
        settings = config(personal=True, avatar="photo")
        # Local syntax cannot determine whether an opaque value is a valid runtime asset name.
        name = "00000000-0000-0000-0000-000000000000"
        settings["definition"]["audio"]["output"]["voice"] = name
        settings["definition"]["avatar"]["character"] = name
        self.assertEqual(app.validate_config(settings), settings)

    def test_avatar_fields_are_all_required(self):
        for avatar in ("standard", "photo"):
            for key in config(avatar=avatar)["definition"]["avatar"]:
                settings = config(avatar=avatar)
                del settings["definition"]["avatar"][key]
                with self.subTest(avatar=avatar, key=key):
                    self.assert_rejected_before_client(settings)
        for value in (None, {}, [], "photo_avatar", "video_avatar"):
            settings = config(avatar="standard")
            settings["definition"]["avatar"] = value
            with self.subTest(value=value):
                self.assert_rejected_before_client(settings)

    def test_avatar_values_are_strict_without_fallback(self):
        common = [
            ("type", "photo-avatar"), ("type", "video-avatar"), ("type", None), ("type", "unknown"),
            ("customized", None), ("customized", 0), ("customized", 1), ("customized", "false"),
            ("output_protocol", "WebRTC"), ("output_protocol", "https"), ("output_protocol", None),
        ]
        for avatar in ("standard", "photo"):
            cases = common + (
                [("type", "photo_avatar"), ("customized", True), ("model", "vasa-1"), ("model", None)]
                if avatar == "standard" else
                [("type", "video_avatar"), ("customized", False), ("model", "other-model"), ("model", None), ("style", "business"), ("style", None)]
            )
            for key, value in cases:
                settings = config(avatar=avatar)
                settings["definition"]["avatar"][key] = value
                with self.subTest(avatar=avatar, key=key, value=value):
                    self.assert_rejected_before_client(settings)

    def test_standard_avatar_requires_nonempty_style_and_runtime_character(self):
        for field in ("style", "character"):
            values = [None, "", " ", 42, [], {}, "<replace-me>", " business ", "${STYLE}"]
            if field == "character":
                values += ["https://example.invalid/avatar", "./photo.png", "bad\nname"]
            for value in values:
                settings = config(avatar="standard")
                settings["definition"]["avatar"][field] = value
                with self.subTest(field=field, value=value):
                    self.assert_rejected_before_client(settings)

    def test_standard_avatar_does_not_hardcode_a_platform_catalog(self):
        settings = config(avatar="standard")
        settings["definition"]["avatar"].update(character="lisa", style="casual-sitting")
        self.assertEqual(app.validate_config(settings), settings)

    def test_avatar_modality_matches_presence_exactly(self):
        for avatar in AVATARS:
            invalid = [["text"], ["audio"], ["audio", "text"], ["text", "audio", "avatar", "avatar"]]
            invalid.append(["text", "audio"] if avatar != "none" else ["text", "audio", "avatar"])
            for modalities in invalid:
                settings = config(avatar=avatar)
                settings["definition"]["output_modalities"] = modalities
                with self.subTest(avatar=avatar, modalities=modalities):
                    self.assert_rejected_before_client(settings)

    def test_asset_extra_fields_and_profile_remapping_rejected(self):
        for avatar in ("standard", "photo"):
            for section in ("voice", "avatar", "definition", "config"):
                for key, value in (
                    ("speakerProfileId", "fake-profile"), ("profileId", "fake-profile"),
                    ("photoAvatarId", "fake-id"), ("url", "https://example.invalid/photo.png"),
                    ("headers", {"Foundry-Features": "fake-override"}), ("extra_body", {}),
                    ("video", {}), ("scene", {}),
                ):
                    settings = config(personal=True, avatar=avatar)
                    target = {
                        "voice": settings["definition"]["audio"]["output"],
                        "avatar": settings["definition"]["avatar"],
                        "definition": settings["definition"], "config": settings,
                    }[section]
                    target[key] = value
                    with self.subTest(avatar=avatar, section=section, key=key):
                        self.assert_rejected_before_client(settings)

    def test_pcm_restriction_is_unchanged(self):
        for direction in ("input", "output"):
            for value in ({"type": "audio/pcm", "rate": 16000}, {"type": "audio/opus", "rate": 24000}):
                settings = config(personal=True, avatar="photo")
                settings["definition"]["audio"][direction]["format"] = value
                with self.subTest(direction=direction, value=value):
                    self.assert_rejected_before_client(settings)

    def test_mcp_credentials_and_references_rejected(self):
        for key, value in [
            ("headers", {"Authorization": "not-a-token"}), ("authorization", "not-a-token"),
            ("project_connection_id", "/subscriptions/example/connections/test"),
            ("allowed_tools", ["other_tool"]), ("require_approval", "always"),
            ("server_url", "https://sample-search.search.windows.net/knowledgebases/sample/mcp?api-version=2026-08-01-preview&sig=fake"),
        ]:
            settings = config()
            settings["definition"]["tools"][0][key] = value
            with self.subTest(key=key), self.assertRaises(app.ConfigurationError):
                app.validate_config(settings)

    def test_mcp_api_versions_are_preserved_without_a_version_allowlist(self):
        for version in SEARCH_API_VERSIONS:
            settings = example_config()
            tool = settings["definition"]["tools"][0]
            tool["server_url"] = tool["server_url"].split("?", 1)[0] + f"?api-version={version}"
            with self.subTest(version=version), patch.object(socket, "socket", side_effect=AssertionError("network")):
                self.assertEqual(app.validate_config(settings), settings)

    def test_mcp_requires_one_explicit_version_and_no_extra_parameters(self):
        queries = (
            "", "?", "?api-version=", "?api-version", "?other=2026-05-01-preview",
            "?api-version=latest", "?api-version=v1", "?api-version=2026-5-1-preview",
            "?api-version=２０２６-０５-０１-preview", "?api-version=<search-api-version>",
            "?api-version=2026-05-01-preview&api-version=2026-08-01-preview",
            "?api-version=2026-05-01-preview&api-version=2026-05-01-preview",
            "?api-version=2026-05-01-preview&sig=fake", "?api-version=2026-05-01-preview&token=fake",
            "?api-version=2026-05-01-preview&other=value", "?api-version=2026-05-01-preview&",
            "?api-version=2026-05-01-preview;sig=fake", "?api-version=2026-05-01-preview%26sig%3Dfake",
        )
        for query in queries:
            settings = example_config()
            tool = settings["definition"]["tools"][0]
            tool["server_url"] = tool["server_url"].split("?", 1)[0] + query
            with self.subTest(query=query):
                self.assert_rejected_before_client(settings)

    def test_mcp_host_path_and_credentials_remain_restricted(self):
        urls = (
            "http://sample-search.search.windows.net/knowledgebases/sample/mcp",
            "https://sample-search.search.windows.net.evil.invalid/knowledgebases/sample/mcp",
            "https://user:password@sample-search.search.windows.net/knowledgebases/sample/mcp",
            "https://sample-search.search.windows.net/indexes/sample/mcp",
            "https://sample-search.search.windows.net/knowledgebases/sample/retrieve",
        )
        for url in urls:
            settings = example_config()
            settings["definition"]["tools"][0]["server_url"] = url + "?api-version=2026-05-01-preview"
            with self.subTest(url=url):
                self.assert_rejected_before_client(settings)

    def test_invalid_vad_values(self):
        for key, value in [("threshold", True), ("threshold", float("nan")), ("threshold", 2), ("prefix_padding_ms", -1), ("silence_duration_ms", "500")]:
            settings = config()
            settings["definition"]["audio"]["input"]["turn_detection"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(app.ConfigurationError):
                app.validate_config(settings)

    def test_sdk_provenance_accepts_only_bundled_wheel(self):
        digest = "f857a1281e2fa3414f25e02aed95dfe2275495027b0a764f38921a8589f15e75"
        dist = MagicMock(version="2.7.0b1")
        dist.read_text.return_value = json.dumps({"archive_info": {"hashes": {"sha256": digest}}})
        with patch.object(app.metadata, "distribution", return_value=dist):
            app.require_sdk()
            dist.read_text.return_value = "{}"
            with self.assertRaises(app.ConfigurationError):
                app.require_sdk()

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.json"
            path.write_text('{"agent_name":"one","agent_name":"two"}', encoding="utf-8")
            with self.assertRaises(app.ConfigurationError):
                app.load_config(path)


@SDK_REQUIRED
class LifecycleTests(unittest.TestCase):
    def test_create_reads_exact_returned_version_and_real_ids(self):
        settings = config()
        client = client_for(settings)
        report = app.create_agent(client, settings)
        self.assertEqual(report["agent_id"], "agent-object-id")
        self.assertEqual(report["version_id"], "version-object-id")
        self.assertEqual(report["agent_guid"], "service-agent-guid")
        self.assertEqual(report["version"], "7")
        self.assertTrue(report["definition_verified"])
        client.agents.get_version.assert_called_once_with(agent_name="sample-agent", agent_version="7")
        self.assertEqual(client.agents.create_version.call_args.kwargs["retry_total"], 0)
        client.agents.enable.assert_not_called()
        client.agents.delete.assert_not_called()

    def test_existing_agent_is_not_versioned(self):
        client = client_for(config(), exists=True)
        with self.assertRaisesRegex(app.LifecycleError, "already exists"):
            app.create_agent(client, config())
        client.agents.create_version.assert_not_called()

    def test_permission_error_does_not_trigger_creation(self):
        client = client_for(config())
        client.agents.get.side_effect = service_error(403)
        with self.assertRaises(app.LifecycleError) as failure:
            app.create_agent(client, config())
        self.assertNotIn("Private service response", str(failure.exception))
        client.agents.create_version.assert_not_called()

    def test_indeterminate_creation_not_retried(self):
        client = client_for(config())
        client.agents.create_version.side_effect = service_error(503)
        with self.assertRaises(app.LifecycleError) as failure:
            app.create_agent(client, config())
        self.assertEqual(failure.exception.report["creation_status"], "unknown")
        self.assertEqual(client.agents.create_version.call_count, 1)

    def test_readback_failure_preserves_created_identifiers(self):
        client = client_for(config())
        client.agents.get_version.side_effect = service_error(403)
        with self.assertRaises(app.LifecycleError) as failure:
            app.create_agent(client, config())
        self.assertEqual(failure.exception.report["version_id"], "version-object-id")
        self.assertEqual(failure.exception.report["creation_status"], "created")

    def test_missing_identifiers_are_not_fabricated(self):
        client = client_for(config())
        del client.agents.create_version.return_value["id"]
        with self.assertRaises(app.LifecycleError) as failure:
            app.create_agent(client, config())
        self.assertIsNone(failure.exception.report["version_id"])

    def test_readback_identifier_mismatch_fails(self):
        for key, value in [("id", "other-version-id"), ("version", "8"), ("name", "other-agent")]:
            client = client_for(config())
            client.agents.get_version.return_value[key] = value
            with self.subTest(key=key), self.assertRaises(app.LifecycleError):
                app.create_agent(client, config())

    def test_readback_configuration_mismatch_fails(self):
        for key, value in [("model", "different-model"), ("tools", []), ("audio", {}), ("avatar", {"character": "unexpected"})]:
            client = client_for(config())
            client.agents.get_version.return_value["definition"][key] = value
            with self.subTest(key=key), self.assertRaises(app.LifecycleError):
                app.create_agent(client, config())

    def test_service_default_fields_do_not_cause_false_mismatch(self):
        for settings in combinations():
            client = client_for(settings)
            actual = client.agents.get_version.return_value["definition"]
            actual["max_output_tokens"] = 4096
            actual["audio"]["output"]["speed"] = 1
            if "avatar" not in actual:
                actual["avatar"] = None
            if actual["audio"]["output"]["voice_type"] == "azure-standard":
                actual["audio"]["output"]["personal_voice_model"] = None
            with self.subTest(settings=settings):
                self.assertTrue(app.create_agent(client, settings)["definition_verified"])

    def test_all_asset_readback_fields_must_match_the_request(self):
        for settings in combinations():
            for label, actual in asset_mismatches(settings):
                client = client_for(settings)
                client.agents.get_version.return_value["definition"] = actual
                with self.subTest(settings=settings, label=label), self.assertRaises(app.LifecycleError) as failure:
                    app.create_agent(client, settings)
                self.assertFalse(failure.exception.report["definition_verified"])
                self.assertEqual(failure.exception.report["creation_status"], "created")
                self.assertEqual(failure.exception.report["version_id"], "version-object-id")

    def test_unrequested_avatar_and_personal_model_injections_rejected(self):
        for personal in (False, True):
            for avatar in ({}, {"character": "fake-injected-avatar"}):
                settings = config(personal=personal)
                client = client_for(settings)
                client.agents.get_version.return_value["definition"]["avatar"] = avatar
                with self.subTest(personal=personal, avatar=avatar), self.assertRaises(app.LifecycleError):
                    app.create_agent(client, settings)
        for avatar in AVATARS:
            for model in ("", "DragonLatestNeural"):
                settings = config(avatar=avatar)
                client = client_for(settings)
                client.agents.get_version.return_value["definition"]["audio"]["output"]["personal_voice_model"] = model
                with self.subTest(avatar=avatar, model=model), self.assertRaises(app.LifecycleError):
                    app.create_agent(client, settings)

    def test_show_is_read_only(self):
        client = client_for(config(), exists=True)
        report = app.show_agent(client, config(), "7")
        self.assertEqual(report["agent_id"], "agent-object-id")
        client.agents.create_version.assert_not_called()
        client.agents.enable.assert_not_called()


if SDK_AVAILABLE:
    class FakeCredential:
        """Supply an inert token without invoking Azure Identity or any token endpoint."""

        def __init__(self):
            self.scopes = []

        def get_token(self, *scopes, **kwargs):
            self.scopes.append(scopes)
            return AccessToken("fake-offline-token", int(time.time()) + 3600)


    class MemoryResponse(HttpResponse):
        def __init__(self, request, status, payload):
            super().__init__(request, None)
            self.status_code = status
            self.headers = {"content-type": "application/json"}
            self.content_type = "application/json"
            self.reason = "OK" if status == 200 else "Fake service error"
            self._body = json.dumps(payload).encode("utf-8")

        def body(self):
            return self._body

        def json(self):
            return json.loads(self._body)


    class MemoryTransport(HttpTransport):
        """Return scripted JSON; unexpected routes or extra requests fail, never use sockets."""

        def __init__(self, steps):
            self.steps = list(steps)
            self.requests = []

        def open(self):
            pass

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

        def sleep(self, duration):
            raise AssertionError("No retry sleep is allowed in an offline contract test")

        def send(self, request, **kwargs):
            self.requests.append(request)
            if not self.steps:
                raise AssertionError("Unexpected extra SDK HTTP request")
            method, path, status, payload = self.steps.pop(0)
            if (request.method, urlsplit(request.url).path) != (method, path):
                raise AssertionError(f"Unexpected SDK route: {request.method} {request.url}")
            return MemoryResponse(request, status, payload)


@SDK_REQUIRED
class HttpContractTests(unittest.TestCase):
    # These identifiers are synthetic fixtures, not evidence of a cloud deployment.
    AGENT_ID = "fake-http-agent-id"
    VERSION_ID = "fake-http-version-id"
    AGENT_GUID = "00000000-0000-0000-0000-000000000000"
    VERSION = "7"
    PREVIEW_HEADER = (
        "WorkflowAgents=V1Preview,ExternalAgents=V1Preview,VoiceAgents=V1Preview,"
        "DraftAgents=V1Preview,AgentsOptimization=V2Preview,ModelRouterControls=V1Preview"
    )

    def setUp(self):
        for name in ("socket", "create_connection", "getaddrinfo"):
            guard = patch.object(socket, name, side_effect=AssertionError("Network is forbidden"))
            guard.start()
            self.addCleanup(guard.stop)

    def fixtures(self, settings, *, actual=None):
        version = {
            "object": "agent.version", "name": settings["agent_name"], "id": self.VERSION_ID,
            "version": self.VERSION, "agent_guid": self.AGENT_GUID, "created_at": 1700000000,
            "metadata": {}, "description": settings["description"], "definition": deepcopy(settings["definition"]),
        }
        saved = deepcopy(version)
        if actual is not None:
            saved["definition"] = deepcopy(actual)
        agent = {
            "object": "agent", "name": settings["agent_name"], "id": self.AGENT_ID,
            "state": "enabled", "versions": {"latest": deepcopy(version)}, "agent_endpoint": None,
        }
        return version, saved, agent

    def steps(self, settings, *, actual=None):
        version, saved, agent = self.fixtures(settings, actual=actual)
        path = f"/api/projects/sample-project/agents/{settings['agent_name']}"
        return [
            ("GET", path, 404, {"error": {"code": "NotFound", "message": "Fake missing agent"}}),
            ("POST", f"{path}/versions", 200, version),
            ("GET", f"{path}/versions/{self.VERSION}", 200, saved),
            ("GET", path, 200, agent),
        ]

    def client(self, settings, steps):
        transport = MemoryTransport(steps)
        credential = FakeCredential()
        client = AIProjectClient(
            endpoint=settings["project_endpoint"], credential=credential,
            allow_preview=True, retry_total=0, transport=transport,
        )
        self.addCleanup(client.close)
        return client, transport, credential

    def assert_requests(self, settings, transport):
        self.assertEqual(transport.steps, [])
        self.assertEqual(len(transport.requests), 4)
        for request in transport.requests:
            url = urlsplit(request.url)
            self.assertEqual(url.scheme, "https")
            self.assertEqual(url.netloc, "sample-account.services.ai.azure.com")
            self.assertEqual(parse_qs(url.query), {"api-version": ["v1"]})
            expected_header = self.PREVIEW_HEADER if request.method == "POST" else None
            self.assertEqual(request.headers.get("Foundry-Features"), expected_header)
            self.assertEqual(request.headers["Authorization"], "Bearer fake-offline-token")
            self.assertEqual(request.headers["Accept"], "application/json")
        request = transport.requests[1]
        self.assertEqual(request.headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(request.body), {
            "definition": settings["definition"], "description": settings["description"],
        })

    def test_real_sdk_create_readback_six_combinations_models_protocols(self):
        for settings in combinations():
            with self.subTest(settings=settings):
                client, transport, credential = self.client(settings, self.steps(settings))
                with patch.object(app, "_data", wraps=app._data) as data:
                    report = app.create_agent(client, settings)
                self.assert_requests(settings, transport)
                self.assertTrue(credential.scopes)
                self.assertEqual(report["agent_id"], self.AGENT_ID)
                self.assertEqual(report["version_id"], self.VERSION_ID)
                self.assertEqual(report["agent_guid"], self.AGENT_GUID)
                self.assertEqual(report["version"], self.VERSION)
                self.assertTrue(report["definition_verified"])
                created, saved, agent = [call.args[0] for call in data.call_args_list]
                self.assertIsInstance(agent, AgentDetails)
                for version in (created, saved):
                    self.assertIsInstance(version, AgentVersionDetails)
                    definition = version.definition
                    self.assertIsInstance(definition, VoiceAgentDefinition)
                    self.assertIsInstance(definition.audio.output, VoiceAgentAudioOutputConfig)
                    for key, value in settings["definition"]["audio"]["output"].items():
                        if key != "format":
                            self.assertEqual(getattr(definition.audio.output, key), value)
                    if "avatar" in settings["definition"]:
                        self.assertIsInstance(definition.avatar, VoiceAgentAvatarConfig)
                        for key, value in settings["definition"]["avatar"].items():
                            self.assertEqual(getattr(definition.avatar, key), value)
                    else:
                        self.assertIsNone(definition.avatar)
                    self.assertEqual(definition.as_dict(), settings["definition"])

    def test_real_sdk_preserves_mcp_api_version_in_create_and_show(self):
        for version in SEARCH_API_VERSIONS:
            settings = example_config()
            tool = settings["definition"]["tools"][0]
            tool["server_url"] = tool["server_url"].split("?", 1)[0] + f"?api-version={version}"
            with self.subTest(version=version):
                client, transport, _ = self.client(settings, self.steps(settings))
                self.assertTrue(app.create_agent(client, settings)["definition_verified"])
                self.assert_requests(settings, transport)
                client, transport, _ = self.client(settings, self.steps(settings)[2:])
                self.assertTrue(app.show_agent(client, settings, self.VERSION)["definition_verified"])
                self.assertEqual([request.method for request in transport.requests], ["GET", "GET"])
                self.assertEqual(transport.steps, [])

    def test_real_sdk_rejects_changed_mcp_api_version_on_readback(self):
        for version in SEARCH_API_VERSIONS:
            settings = example_config()
            tool = settings["definition"]["tools"][0]
            base_url = tool["server_url"].split("?", 1)[0]
            tool["server_url"] = base_url + f"?api-version={version}"
            replacement = "2026-08-01-preview" if version != "2026-08-01-preview" else "2026-05-01-preview"
            actual = deepcopy(settings["definition"])
            actual["tools"][0]["server_url"] = base_url + f"?api-version={replacement}"
            client, transport, _ = self.client(settings, self.steps(settings, actual=actual))
            with self.subTest(version=version), self.assertRaises(app.LifecycleError) as failure:
                app.create_agent(client, settings)
            self.assert_requests(settings, transport)
            self.assertFalse(failure.exception.report["definition_verified"])
            self.assertEqual(failure.exception.report["creation_status"], "created")
            self.assertEqual(failure.exception.report["version_id"], self.VERSION_ID)

    def test_real_sdk_default_template_create_and_show(self):
        settings = example_config()
        client, transport, _ = self.client(settings, self.steps(settings))
        self.assertTrue(app.create_agent(client, settings)["definition_verified"])
        self.assert_requests(settings, transport)
        client, transport, _ = self.client(settings, self.steps(settings)[2:])
        self.assertTrue(app.show_agent(client, settings, self.VERSION)["definition_verified"])
        self.assertEqual([request.method for request in transport.requests], ["GET", "GET"])
        self.assertEqual(transport.steps, [])

    def test_real_sdk_deserialized_asset_mismatches_preserve_partial_reports(self):
        for settings in combinations():
            for label, actual in asset_mismatches(settings):
                client, transport, _ = self.client(settings, self.steps(settings, actual=actual))
                with self.subTest(settings=settings, label=label), self.assertRaises(app.LifecycleError) as failure:
                    app.create_agent(client, settings)
                self.assert_requests(settings, transport)
                self.assertEqual(failure.exception.report["creation_status"], "created")
                self.assertEqual(failure.exception.report["version_id"], self.VERSION_ID)
                self.assertFalse(failure.exception.report["definition_verified"])

    def test_real_sdk_rejects_unrequested_asset_injection(self):
        cases = [(personal, "none", "avatar") for personal in (False, True)]
        cases += [(False, avatar, "personal_voice_model") for avatar in AVATARS]
        for personal, avatar, field in cases:
            settings = config(personal=personal, avatar=avatar)
            actual = deepcopy(settings["definition"])
            if field == "avatar":
                actual["avatar"] = config(avatar="photo")["definition"]["avatar"]
            else:
                actual["audio"]["output"][field] = "DragonLatestNeural"
            client, transport, _ = self.client(settings, self.steps(settings, actual=actual))
            with self.subTest(personal=personal, avatar=avatar), self.assertRaises(app.LifecycleError):
                app.create_agent(client, settings)
            self.assert_requests(settings, transport)

    def test_real_sdk_allows_unrelated_service_defaults(self):
        for settings in combinations():
            actual = deepcopy(settings["definition"])
            actual["max_output_tokens"] = 4096
            actual["audio"]["output"]["speed"] = 1
            client, transport, _ = self.client(settings, self.steps(settings, actual=actual))
            with self.subTest(settings=settings):
                self.assertTrue(app.create_agent(client, settings)["definition_verified"])
            self.assert_requests(settings, transport)

    def test_real_sdk_existing_name_never_posts(self):
        settings = config(personal=True, avatar="photo")
        steps = self.steps(settings)
        client, transport, _ = self.client(settings, [steps[-1]])
        with self.assertRaisesRegex(app.LifecycleError, "already exists"):
            app.create_agent(client, settings)
        self.assertEqual([request.method for request in transport.requests], ["GET"])
        self.assertEqual(transport.steps, [])

    def test_real_sdk_creation_failure_has_one_post_and_no_retry(self):
        settings = config(personal=True, avatar="photo")
        steps = self.steps(settings)[:2]
        method, path, _, _ = steps[1]
        steps[1] = (method, path, 503, {"error": {"code": "Unavailable", "message": "Fake private response"}})
        client, transport, _ = self.client(settings, steps)
        with self.assertRaises(app.LifecycleError) as failure:
            app.create_agent(client, settings)
        self.assertEqual([request.method for request in transport.requests], ["GET", "POST"])
        self.assertEqual(transport.steps, [])
        self.assertEqual(failure.exception.report["creation_status"], "unknown")
        self.assertIn("HTTP 503", str(failure.exception))
        self.assertNotIn("Fake private response", str(failure.exception))

    def test_real_sdk_show_uses_exact_version_and_only_gets(self):
        settings = config(personal=True, avatar="photo")
        client, transport, _ = self.client(settings, self.steps(settings)[2:])
        report = app.show_agent(client, settings, self.VERSION)
        self.assertTrue(report["definition_verified"])
        self.assertEqual(report["version"], self.VERSION)
        self.assertEqual([request.method for request in transport.requests], ["GET", "GET"])
        self.assertEqual(transport.steps, [])


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config_path = self.root / "agent.local.json"
        self.config_path.write_text(json.dumps(config()), encoding="utf-8")

    def run_cli(self, *args):
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            code = app.main([*args, "--config", str(self.config_path)])
        return code, out.getvalue(), err.getvalue()

    def test_validate_does_not_construct_clients(self):
        with patch.object(socket, "socket", side_effect=AssertionError("network")), patch.dict("sys.modules", {"azure.identity": None, "azure.ai.projects": None}):
            code, out, _ = self.run_cli("validate")
        self.assertEqual(code, 0)
        self.assertIn("No Azure calls", out)

    def test_validate_describes_each_requested_combination(self):
        for personal in (False, True):
            for avatar in AVATARS:
                settings = config(personal=personal, avatar=avatar)
                self.config_path.write_text(json.dumps(settings), encoding="utf-8")
                with self.subTest(personal=personal, avatar=avatar), patch.object(socket, "socket", side_effect=AssertionError("network")):
                    code, out, _ = self.run_cli("validate")
                self.assertEqual(code, 0)
                self.assertIn(settings["definition"]["audio"]["output"]["voice_type"], out)
                expected = {"none": "without avatar", "standard": "with standard avatar", "photo": "with custom photo avatar"}
                self.assertIn(expected[avatar], out)
                self.assertIn("No Azure calls", out)

    def test_missing_config_fails_without_network(self):
        self.config_path.unlink()
        with patch.object(socket, "socket", side_effect=AssertionError("network")):
            code, _, _ = self.run_cli("validate")
        self.assertEqual(code, 2)

    def test_latest_not_accepted(self):
        code, _, _ = self.run_cli("show", "--version", "latest")
        self.assertEqual(code, 2)

    def test_output_overwrite_rejected_before_credentials(self):
        output = self.root / "existing.json"
        output.write_text("preserve", encoding="utf-8")
        with patch.dict("sys.modules", {"azure.identity": None, "azure.ai.projects": None}):
            code, _, _ = self.run_cli("create", "--output", str(output))
        self.assertEqual(code, 2)
        self.assertEqual(output.read_text(encoding="utf-8"), "preserve")

    @SDK_REQUIRED
    def test_create_cli_writes_only_local_report(self):
        output = self.root / "report.json"
        client = client_for(config())
        with patch("azure.identity.DefaultAzureCredential"), patch("azure.ai.projects.AIProjectClient") as factory:
            factory.return_value.__enter__.return_value = client
            code, _, _ = self.run_cli("create", "--output", str(output))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.read_text())["version_id"], "version-object-id")
        self.assertTrue(factory.call_args.kwargs["allow_preview"])
        self.assertEqual(factory.call_args.kwargs["retry_total"], 0)

    @SDK_REQUIRED
    def test_cli_preserves_partial_creation_report(self):
        output = self.root / "report.json"
        client = client_for(config())
        client.agents.get_version.side_effect = service_error(403)
        with patch("azure.identity.DefaultAzureCredential"), patch("azure.ai.projects.AIProjectClient") as factory:
            factory.return_value.__enter__.return_value = client
            code, _, err = self.run_cli("create", "--output", str(output))
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.read_text())["version_id"], "version-object-id")
        self.assertNotIn("Private service response", err)


if __name__ == "__main__":
    unittest.main()
