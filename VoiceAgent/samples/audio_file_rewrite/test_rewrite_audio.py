"""Offline tests for file validation and the single-turn editing sequence."""

import asyncio
import json
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rewrite_audio import (
    SAMPLE_RATE,
    _create_agent,
    _definition,
    _parse_args,
    _process,
    _read_audio,
    _response_text,
    _run,
)


def _connection(events: list[dict]) -> SimpleNamespace:
    return SimpleNamespace(
        recv=AsyncMock(side_effect=events),
        input_audio_buffer=SimpleNamespace(append=AsyncMock(), commit=AsyncMock()),
        response=SimpleNamespace(create=AsyncMock()),
    )


def test_definition_uses_requested_models_and_manual_text_turn() -> None:
    definition = _definition().as_dict()
    assert definition["kind"] == "voice"
    assert definition["model"] == "gpt-5.4"
    assert definition["audio"]["input"]["transcription"]["model"] == "mai-transcribe-2"
    assert definition["audio"]["input"]["turn_detection"] is None
    assert definition["output_modalities"] == ["text"]
    assert definition["store"] is False


@pytest.mark.parametrize(
    "channels,rate,frames,valid",
    [
        (1, SAMPLE_RATE, 2400, True),
        (2, SAMPLE_RATE, 2400, False),
        (1, 16000, 2400, False),
        (1, SAMPLE_RATE, 0, False),
        (1, SAMPLE_RATE, SAMPLE_RATE * 61, False),
    ],
)
def test_read_audio_validates_format_and_duration(
    tmp_path: Path,
    channels: int,
    rate: int,
    frames: int,
    valid: bool,
) -> None:
    path = tmp_path / "input.wav"
    pcm = bytes(frames * channels * 2)
    with wave.open(str(path), "wb") as recording:
        recording.setparams((channels, 2, rate, 0, "NONE", "not compressed"))
        recording.writeframes(pcm)
    if valid:
        assert _read_audio(path) == pcm
    else:
        with pytest.raises(ValueError):
            _read_audio(path)


def test_process_waits_for_transcription_before_rewrite() -> None:
    events = [
        {"type": "session.created"},
        {
            "type": "session.updated",
            "session": {"audio": {"input": {"turn_detection": None}}},
        },
        {"type": "input_audio_buffer.committed"},
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "um please check it",
        },
        {"type": "response.output_text.delta", "delta": "Please review it."},
        {
            "type": "response.done",
            "response": {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {"type": "output_text", "text": "Please review it."}
                        ],
                    }
                ],
            },
        },
    ]
    connection = _connection(events)

    async def request_rewrite() -> None:
        assert connection.recv.await_count == 4
        connection.input_audio_buffer.commit.assert_awaited_once()

    connection.response.create.side_effect = request_rewrite
    result = asyncio.run(_process(connection, bytes(9600)))
    assert result == {
        "transcript": "um please check it",
        "rewritten_text": "Please review it.",
    }
    assert connection.input_audio_buffer.append.await_count == 2
    connection.response.create.assert_awaited_once()


@pytest.mark.parametrize(
    "event",
    [
        {"type": "error", "error": {"code": "unsupported_model"}},
        {
            "type": "conversation.item.input_audio_transcription.failed",
            "error": {"code": "failed"},
        },
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": " ",
        },
    ],
)
def test_process_does_not_rewrite_failed_transcription(event: dict) -> None:
    connection = _connection([{"type": "session.updated"}, event])
    with pytest.raises(RuntimeError):
        asyncio.run(_process(connection, bytes(4800)))
    connection.response.create.assert_not_awaited()


def test_process_rejects_automatic_turn_detection() -> None:
    connection = _connection(
        [
            {
                "type": "session.updated",
                "session": {
                    "turn_detection": {"type": "server_vad"},
                },
            }
        ]
    )
    with pytest.raises(RuntimeError, match="automatic turn detection"):
        asyncio.run(_process(connection, bytes(4800)))
    connection.input_audio_buffer.append.assert_not_awaited()


@pytest.mark.parametrize(
    "response",
    [
        {"status": "failed"},
        {"status": "incomplete"},
        {"status": "completed", "output": []},
    ],
)
def test_response_text_rejects_unsuccessful_or_empty_output(response: dict) -> None:
    with pytest.raises(RuntimeError):
        _response_text(response)


def test_definition_translate_uses_target_language_and_same_models() -> None:
    definition = _definition(mode="translate", target_language="French").as_dict()
    assert "Target language: French" in definition["instructions"]
    assert "translator" in definition["instructions"]
    assert "Preserve the original language" not in definition["instructions"]
    assert definition["model"] == "gpt-5.4"
    assert definition["audio"]["input"]["transcription"]["model"] == "mai-transcribe-2"


@pytest.mark.parametrize("language", [None, "", "   "])
def test_definition_translate_requires_target_language(language: str | None) -> None:
    with pytest.raises(ValueError, match="requires --target-language"):
        _definition(mode="translate", target_language=language)


def test_parse_args_defaults_to_rewrite(tmp_path: Path) -> None:
    args = _parse_args(
        argv=["recording.wav", "--output", str(tmp_path / "result.json")]
    )
    assert args.mode == "rewrite"
    assert args.target_language is None


@pytest.mark.parametrize(
    "arguments",
    [
        ["--mode", "translate"],
        ["--mode", "translate", "--target-language", "  "],
        ["--target-language", "French"],
        ["--mode", "unknown"],
    ],
)
def test_parse_args_rejects_invalid_mode_options(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        _parse_args(argv=["recording.wav", *arguments])
    assert error.value.code == 2


def test_parse_args_accepts_and_trims_target_language(tmp_path: Path) -> None:
    args = _parse_args(
        argv=[
            "recording.wav",
            "--mode",
            "translate",
            "--target-language",
            " French ",
            "--output",
            str(tmp_path / "result.json"),
        ]
    )
    assert args.mode == "translate"
    assert args.target_language == "French"


def test_process_translate_returns_translated_text() -> None:
    connection = _connection(
        [
            {"type": "session.updated"},
            {
                "type": "conversation.item.input_audio_transcription.completed",
                "transcript": "Please review it.",
            },
            {
                "type": "response.done",
                "response": {
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [
                                {"type": "output_text", "text": "Veuillez le vérifier."}
                            ],
                        }
                    ],
                },
            },
        ]
    )
    result = asyncio.run(_process(connection, bytes(4800), mode="translate"))
    assert result == {
        "transcript": "Please review it.",
        "translated_text": "Veuillez le vérifier.",
    }
    connection.response.create.assert_awaited_once()


def test_create_agent_publishes_translation_instructions() -> None:
    client = SimpleNamespace(
        agents=SimpleNamespace(create_version=AsyncMock(), enable=AsyncMock())
    )
    name = asyncio.run(
        _create_agent(client, mode="translate", target_language="Japanese")
    )
    published = client.agents.create_version.call_args.kwargs
    assert published["agent_name"] == name
    assert (
        "Target language: Japanese" in published["definition"].as_dict()["instructions"]
    )
    client.agents.enable.assert_awaited_once_with(name)


def test_run_saves_unicode_translation_and_mode_metadata(tmp_path: Path) -> None:
    args = _parse_args(
        argv=[
            "recording.wav",
            "--mode",
            "translate",
            "--target-language",
            "Japanese",
            "--output",
            str(tmp_path / "translation.json"),
        ]
    )
    client = MagicMock()
    project_context = AsyncMock()
    project_context.__aenter__.return_value = client
    connection_context = AsyncMock()
    client.beta.voice_agents.realtime.connect.return_value = connection_context
    with (
        patch("rewrite_audio._read_audio", return_value=bytes(4800)),
        patch.dict(
            "os.environ",
            {"AZURE_VOICE_AGENTS_ENDPOINT": "https://example.test/api/projects/test"},
        ),
        patch("rewrite_audio.DefaultAzureCredential", return_value=AsyncMock()),
        patch("rewrite_audio.AIProjectClient", return_value=project_context),
        patch(
            "rewrite_audio._create_agent",
            new_callable=AsyncMock,
            return_value="test-agent",
        ) as create,
        patch(
            "rewrite_audio._process",
            new_callable=AsyncMock,
            return_value={
                "transcript": "Please review it.",
                "translated_text": "ご確認ください。",
            },
        ) as process,
    ):
        asyncio.run(_run(args))
    create.assert_awaited_once_with(
        client, mode="translate", target_language="Japanese"
    )
    assert process.call_args.kwargs["mode"] == "translate"
    saved = json.loads(args.output.read_text(encoding="utf-8"))
    assert saved["translated_text"] == "ご確認ください。"
    assert saved["target_language"] == "Japanese"
    assert saved["mode"] == "translate"
    assert saved["agent_name"] == "test-agent"
