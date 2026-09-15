"""Download a persisted conversation, per-turn audio, and merged audio."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any

import aiohttp
from azure.ai.projects.aio import AIProjectClient
from azure.ai.projects.aio.operations import AgentEndpointConversationsOperations
from azure.ai.projects.models import VoiceConversation
from azure.core.exceptions import HttpResponseError
from azure.core.pipeline.transport import AioHttpTransport
from azure.identity.aio import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()


def required_env(name: str) -> str:
    """Return a required environment variable or raise a clear error."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name} before running this sample.")
    return value


def _json_value(value: Any) -> Any:
    """Convert SDK models and timestamps into JSON-serializable values."""
    if hasattr(value, "as_dict"):
        return _json_value(value.as_dict())
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _safe_filename(value: str) -> str:
    """Replace characters that are unsafe in Windows and POSIX filenames."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "item"


async def _write_stream(stream: Any, path: Path) -> None:
    """Write an async audio-content stream to disk."""
    with path.open("wb") as output:
        async for chunk in stream:
            output.write(chunk)
    print(f"Saved audio: {path.resolve()}")


async def _wait_for_completed_conversation(
    conversations: AgentEndpointConversationsOperations,
    agent_name: str,
    conversation_id: str,
    timeout_seconds: float,
) -> VoiceConversation:
    """Wait until persistence finishes before requesting final audio."""
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    last_status = "unknown"
    while asyncio.get_running_loop().time() < deadline:
        try:
            conversation = await conversations.get_agent_conversation(
                agent_name,
                conversation_id,
            )
        except HttpResponseError as error:
            if error.status_code != 404:
                raise
            await asyncio.sleep(2)
            continue

        status = getattr(
            conversation.status,
            "value",
            conversation.status,
        )
        last_status = str(status or "").lower()
        if last_status == "completed":
            return conversation
        await asyncio.sleep(2)
    raise TimeoutError(
        f"Conversation {conversation_id} did not complete; "
        f"last status was {last_status!r}."
    )


async def _save_item_audio(
    conversations: AgentEndpointConversationsOperations,
    agent_name: str,
    conversation_id: str,
    items: list[dict[str, Any]],
    turns_dir: Path,
) -> list[dict[str, Any]]:
    """Save the audio segment for every conversation item that has audio."""
    saved: list[dict[str, Any]] = []
    audio_index = 0

    for item in items:
        item_id = str(item.get("id") or "")
        if not item_id:
            continue
        try:
            metadata = await conversations.get_agent_conversation_item_audio(
                agent_name,
                conversation_id,
                item_id,
            )
        except HttpResponseError as error:
            # Text and tool items normally have no audio.
            if error.status_code == 404:
                continue
            raise

        audio_index += 1
        metadata_json = _json_value(metadata)
        role = str(metadata_json.get("role") or item.get("role") or "item")
        filename = (
            f"{audio_index:03d}_{_safe_filename(role)}_"
            f"{_safe_filename(item_id)}.wav"
        )
        output_path = turns_dir / filename

        if metadata.blob_uri:
            print(
                f"Turn audio for {item_id} is in customer storage: "
                f"{metadata.blob_uri}"
            )
        else:
            stream = await conversations.get_agent_conversation_item_audio_content(
                agent_name,
                conversation_id,
                item_id,
            )
            await _write_stream(stream, output_path)

        saved.append(
            {
                "item_id": item_id,
                "role": role,
                "file": None if metadata.blob_uri else str(output_path),
                "metadata": metadata_json,
            }
        )
    return saved


async def _save_merged_audio(
    conversations: AgentEndpointConversationsOperations,
    agent_name: str,
    conversation_id: str,
    output_path: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Save the final stereo recording, retrying while it is prepared."""
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        try:
            metadata = await conversations.get_agent_conversation_audio(
                agent_name,
                conversation_id,
            )
            metadata_json = _json_value(metadata)
            if metadata.blob_uri:
                print(
                    "Merged audio is in customer storage: "
                    f"{metadata.blob_uri}"
                )
                return {
                    "file": None,
                    "metadata": metadata_json,
                }

            stream = await conversations.get_agent_conversation_audio_content(
                agent_name,
                conversation_id,
            )
            await _write_stream(stream, output_path)
            return {
                "file": str(output_path),
                "metadata": metadata_json,
            }
        except HttpResponseError as error:
            # 404: not persisted yet. 409: session finalization still running.
            if error.status_code not in {404, 409}:
                raise
            await asyncio.sleep(2)

    raise TimeoutError(
        f"Merged audio for conversation {conversation_id} was not ready."
    )


async def download_conversation_artifacts(
    client: AIProjectClient,
    agent_name: str,
    conversation_id: str,
) -> Path:
    """Save JSON, per-turn audio, and the final merged stereo WAV.

    Output layout:

    ``voice-agent-output/<conversation-id>/conversation.json``
    ``voice-agent-output/<conversation-id>/turns/*.wav``
    ``voice-agent-output/<conversation-id>/merged.wav``
    """
    output_root = Path(
        os.getenv("AZURE_VOICE_AGENTS_OUTPUT_DIR", "voice-agent-output")
    )
    conversation_dir = output_root / _safe_filename(conversation_id)
    turns_dir = conversation_dir / "turns"
    turns_dir.mkdir(parents=True, exist_ok=True)

    conversations = client.agent_endpoint_conversations
    conversation = await _wait_for_completed_conversation(
        conversations,
        agent_name,
        conversation_id,
        timeout_seconds=120,
    )
    items = [
        _json_value(item)
        async for item in conversations.list_agent_conversation_items(
            agent_name,
            conversation_id,
            order="asc",
        )
    ]
    responses = [
        _json_value(response)
        async for response in conversations.list_agent_conversation_responses(
            agent_name,
            conversation_id,
            order="asc",
        )
    ]

    conversation_path = conversation_dir / "conversation.json"
    payload = {
        "agent_name": agent_name,
        "conversation": _json_value(conversation),
        "responses": responses,
        "items": items,
        "turn_audio": [],
        "merged_audio": None,
    }
    # Save transcript data before downloading audio so it is retained even if
    # a later audio download is interrupted.
    conversation_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Saved conversation: {conversation_path.resolve()}")

    print(f"Persisted conversation: {conversation.id} ({conversation.status})")
    for item in items:
        parts = [
            (part.get("transcript") or part.get("text") or "").strip()
            for part in (item.get("content") or [])
        ]
        text = " ".join(part for part in parts if part)
        if text:
            role = item.get("role", item.get("type", "item"))
            print(f"{role}: {text}")

    turn_audio = await _save_item_audio(
        conversations,
        agent_name,
        conversation_id,
        items,
        turns_dir,
    )
    merged_audio = await _save_merged_audio(
        conversations,
        agent_name,
        conversation_id,
        conversation_dir / "merged.wav",
        timeout_seconds=180,
    )

    payload["turn_audio"] = turn_audio
    payload["merged_audio"] = merged_audio
    conversation_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Updated conversation manifest: {conversation_path.resolve()}")
    return conversation_dir


async def download(agent_name: str, conversation_id: str) -> None:
    """Create an SDK client and download all persisted artifacts."""
    endpoint = required_env("AZURE_VOICE_AGENTS_ENDPOINT").rstrip("/")
    credential = DefaultAzureCredential()
    transport = AioHttpTransport(
        session=aiohttp.ClientSession(
            auto_decompress=False,
            headers={"Accept-Encoding": "gzip, deflate"},
        )
    )
    async with credential, AIProjectClient(
        endpoint=endpoint,
        credential=credential,
        allow_preview=True,
        transport=transport,
    ) as client:
        await download_conversation_artifacts(
            client,
            agent_name,
            conversation_id,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("agent_name", help="Name of the voice agent.")
    parser.add_argument(
        "conversation_id",
        help="Persisted conversation id returned by a voice session.",
    )
    args = parser.parse_args()
    asyncio.run(download(args.agent_name, args.conversation_id))


if __name__ == "__main__":
    main()
