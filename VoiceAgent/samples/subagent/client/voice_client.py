#!/usr/bin/env python3
"""Talk to an existing Foundry voice agent using the Projects Python SDK."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from voice_client_common import AudioIO, load_audio_module, print_event

try:
    import aiohttp
    from azure.ai.projects import models
    from azure.ai.projects.aio import (
        AIProjectClient,
        AsyncRealtimeConnection,
        ServerEvent,
    )
    from azure.core.exceptions import AzureError
    from azure.identity.aio import DefaultAzureCredential
    from dotenv import load_dotenv
except ModuleNotFoundError as error:
    print(
        f"Missing Python dependency: {error.name}\n"
        "Set up the shared client environment and run:\n"
        "  python -m pip install -r requirements.txt",
        file=sys.stderr,
    )
    raise SystemExit(1) from error


def handle_event(event: ServerEvent, audio: AudioIO) -> str:
    if isinstance(event, models.RealtimeServerEventResponseAudioDelta):
        # The SDK already decodes base64 audio to PCM bytes.
        audio.queue_output(event.delta)
        return event.type
    payload = (
        event.as_dict()
        if isinstance(event, models.RealtimeServerEvent)
        else dict(event)
    )
    print_event(payload, audio)
    return str(payload.get("type") or "")


async def wait_until_ready(
    connection: AsyncRealtimeConnection, audio: AudioIO
) -> None:
    ready: set[str] = set()
    while ready != {"session.created", "session.updated"}:
        event_type = handle_event(await connection.recv(), audio)
        if event_type in {"session.created", "session.updated"}:
            ready.add(event_type)


async def send_microphone(
    connection: AsyncRealtimeConnection, audio: AudioIO
) -> None:
    while True:
        await connection.input_audio_buffer.append(audio=await audio.next_input())


async def receive_events(
    connection: AsyncRealtimeConnection, audio: AudioIO
) -> None:
    async for event in connection:
        handle_event(event, audio)


async def stream_audio(
    connection: AsyncRealtimeConnection, audio: AudioIO
) -> None:
    tasks = [
        asyncio.create_task(send_microphone(connection, audio)),
        asyncio.create_task(receive_events(connection, audio)),
    ]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def run_client(project_endpoint: str, agent_name: str) -> None:
    parsed = urlsplit(project_endpoint)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("PROJECT_ENDPOINT must be a valid HTTPS endpoint")
    pyaudio = load_audio_module()

    async with (
        DefaultAzureCredential() as credential,
        AIProjectClient(
            endpoint=project_endpoint,
            credential=credential,
            allow_preview=True,
        ) as project,
        project.realtime.connect(
            agent_name=agent_name, agent_session_id=uuid.uuid4().hex
        ) as connection,
    ):
        audio = AudioIO(pyaudio)
        try:
            # Use the saved agent configuration; do not send session.update.
            await asyncio.wait_for(wait_until_ready(connection, audio), timeout=60)
            audio.start()
            print(f"Connected to {agent_name}. Start speaking; press Ctrl+C to exit.")
            await stream_audio(connection, audio)
        finally:
            audio.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-name", required=True)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path.cwd() / ".env",
        help="Dotenv file to load; defaults to .env in the current directory.",
    )
    parser.add_argument(
        "--project-endpoint",
        help="Foundry project endpoint; overrides PROJECT_ENDPOINT.",
    )
    args = parser.parse_args()
    load_dotenv(args.env_file)
    endpoint = args.project_endpoint or os.environ.get("PROJECT_ENDPOINT", "")
    asyncio.run(run_client(endpoint.strip().rstrip("/"), args.agent_name))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDisconnected.")
    except (AzureError, ValueError, RuntimeError, OSError, aiohttp.ClientError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
