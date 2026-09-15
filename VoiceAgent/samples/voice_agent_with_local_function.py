"""Run a client-executed local function through a microphone voice session.

The created or supplied agent calls ``add_numbers``; this client executes the
Python function locally, sends ``function_call_output``, and plays the agent's
spoken result. Use the printed conversation id with the separate artifact
downloader for JSON and audio. The agent remains available after the sample exits.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import queue
import uuid
from typing import Any, Final, Optional

import aiohttp
from azure.ai.projects.aio import AIProjectClient, AsyncRealtimeConnection
from azure.ai.projects.models import (
    RealtimeAudioFormatsAudioPcm,
    RealtimeConversationItemFunctionCallOutput,
    RealtimeFunctionToolParameters,
    RealtimeServerEventType,
    VoiceAgentAudioConfig,
    VoiceAgentAudioInputConfig,
    VoiceAgentAudioOutputConfig,
    VoiceAgentDefinition,
    VoiceAgentFunctionTool,
    VoiceAgentInputTranscription,
    VoiceAgentNoiseReduction,
    VoiceAgentNoiseReductionType,
    VoiceAgentServerVadTurnDetection,
    VoiceOutputModality,
    VoiceType,
)
from azure.core.pipeline.transport import AioHttpTransport
from azure.identity.aio import DefaultAzureCredential
from dotenv import load_dotenv

from foundry_trace_url import build_foundry_trace_url


load_dotenv()

SAMPLE_RATE: Final = 24000
CHUNK_SAMPLES: Final = 1200

try:
    import pyaudio
except ImportError:  # pragma: no cover - required runtime dependency
    pyaudio = None  # type: ignore[assignment]


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name} before running this sample.")
    return value


def event_value(event: Any, name: str) -> Any:
    """Read a field from a typed Voice Agent event or an open mapping."""
    value = getattr(event, name, None)
    if value is None and hasattr(event, "get"):
        value = event.get(name)
    return value


def audio_bytes(delta: Any) -> bytes:
    """Normalize typed bytes and stable-v1 base64 audio deltas."""
    if isinstance(delta, bytes):
        return delta
    if isinstance(delta, str):
        return base64.b64decode(delta)
    raise RuntimeError("The service returned an unsupported audio delta.")


class AudioProcessor:
    """Capture microphone PCM and play response PCM with barge-in support."""

    def __init__(self, connection: AsyncRealtimeConnection) -> None:
        self.connection = connection
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.audio = pyaudio.PyAudio()
        self.playback_queue: "queue.Queue[tuple[int, Optional[bytes]]]" = (
            queue.Queue()
        )
        self.playback_base = 0
        self.next_sequence = 0
        self.input_stream = None
        self.output_stream = None

    def next_sequence_number(self) -> int:
        sequence = self.next_sequence
        self.next_sequence += 1
        return sequence

    def start_capture(self) -> None:
        """Stream PCM frames through the Voice Agent SDK input buffer."""
        self.loop = asyncio.get_running_loop()

        def callback(in_data, _frame_count, _time_info, _status):
            assert self.loop is not None
            asyncio.run_coroutine_threadsafe(
                self.connection.input_audio_buffer.append(audio=in_data),
                self.loop,
            )
            return (None, pyaudio.paContinue)

        self.input_stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SAMPLES,
            stream_callback=callback,
        )

    def start_playback(self) -> None:
        """Play queued agent audio without blocking the asyncio event loop."""
        remaining = b""

        def callback(_in_data, frame_count, _time_info, _status):
            nonlocal remaining
            wanted = frame_count * pyaudio.get_sample_size(pyaudio.paInt16)
            output = remaining[:wanted]
            remaining = remaining[wanted:]

            while len(output) < wanted:
                try:
                    sequence, data = self.playback_queue.get_nowait()
                except queue.Empty:
                    output += bytes(wanted - len(output))
                    continue
                if data is None:
                    break
                if sequence < self.playback_base:
                    remaining = b""
                    continue
                take = wanted - len(output)
                output += data[:take]
                remaining = data[take:]
            return (output, pyaudio.paContinue)

        self.output_stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            output=True,
            frames_per_buffer=CHUNK_SAMPLES,
            stream_callback=callback,
        )

    def queue_audio(self, pcm: bytes) -> None:
        self.playback_queue.put((self.next_sequence_number(), pcm))

    def skip_pending_audio(self) -> None:
        """Drop queued output immediately when the user barges in."""
        self.playback_base = self.next_sequence_number()

    def shutdown(self) -> None:
        if self.input_stream is not None:
            self.input_stream.stop_stream()
            self.input_stream.close()
        if self.output_stream is not None:
            self.skip_pending_audio()
            self.playback_queue.put((self.next_sequence_number(), None))
            self.output_stream.stop_stream()
            self.output_stream.close()
        self.audio.terminate()


async def run_microphone_session(
    client: AIProjectClient,
    agent_name: str,
) -> Optional[str]:
    """Run a hands-free session and return its persisted conversation id."""
    if pyaudio is None:
        raise RuntimeError("Install pyaudio to use the microphone sample.")

    conversation_id: Optional[str] = None
    function_argument_deltas: dict[str, list[str]] = {}
    pending_tool_outputs: list[RealtimeConversationItemFunctionCallOutput] = []

    async with client.realtime.connect(agent_name=agent_name) as connection:
        processor = AudioProcessor(connection)
        try:
            processor.start_playback()
            processor.start_capture()
            print("Speak now. Pause to let the agent answer.")
            print("Talk over the response to interrupt it. Press Ctrl-C to finish.")

            async for event in connection:
                event_type = event_value(event, "type")
                if (
                    event_type
                    == RealtimeServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED
                ):
                    processor.skip_pending_audio()
                    print("(listening...)")
                elif (
                    event_type
                    == RealtimeServerEventType.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED
                ):
                    print(f"You:   {event_value(event, 'transcript')}")
                elif event_type == RealtimeServerEventType.RESPONSE_OUTPUT_AUDIO_DELTA:
                    processor.queue_audio(
                        audio_bytes(event_value(event, "delta"))
                    )
                elif (
                    event_type
                    == RealtimeServerEventType.RESPONSE_OUTPUT_AUDIO_TRANSCRIPT_DONE
                ):
                    transcript = (
                        event_value(event, "transcript")
                        or event_value(event, "text")
                        or ""
                    )
                    print(f"Agent: {transcript}")
                elif event_type == RealtimeServerEventType.SESSION_CREATED:
                    conversation_id = event_value(event, "conversation_id")
                elif event_type == RealtimeServerEventType.ERROR:
                    error = event_value(event, "error")
                    print(
                        "Session error: "
                        f"{event_value(error, 'message') or 'unknown error'}"
                    )
                elif (
                    event_type
                    == RealtimeServerEventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DELTA
                ):
                    item_id = str(event_value(event, "item_id") or "")
                    delta = event_value(event, "delta")
                    if isinstance(delta, str):
                        function_argument_deltas.setdefault(
                            item_id, []
                        ).append(delta)
                elif (
                    event_type
                    == RealtimeServerEventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE
                ):
                    item_id = str(event_value(event, "item_id") or "")
                    call_id = str(event_value(event, "call_id") or "")
                    function_name = str(event_value(event, "name") or "")
                    arguments_raw = event_value(event, "arguments")
                    if not isinstance(arguments_raw, str):
                        arguments_raw = "".join(
                            function_argument_deltas.get(item_id, [])
                        )
                    function_argument_deltas.pop(item_id, None)
                    arguments = json.loads(arguments_raw or "{}")
                    if function_name != "add_numbers":
                        raise RuntimeError(
                            f"Unsupported local function: {function_name}"
                        )

                    output = {
                        "sum": float(arguments["a"]) + float(arguments["b"])
                    }
                    print(f"Local function: {function_name}")
                    print(
                        "Arguments:\n"
                        f"{json.dumps(arguments, indent=2)}"
                    )
                    print(
                        "Output:\n"
                        f"{json.dumps(output, indent=2)}"
                    )

                    pending_tool_outputs.append(
                        RealtimeConversationItemFunctionCallOutput(
                            call_id=call_id,
                            output=json.dumps(output),
                        )
                    )
                elif (
                    event_type == RealtimeServerEventType.RESPONSE_DONE
                    and pending_tool_outputs
                ):
                    # Wait for the function-call response to finish before
                    # submitting its outputs and requesting the follow-up.
                    # Otherwise response.create can race an active response.
                    for item in pending_tool_outputs:
                        await connection.conversation.item.create(item=item)
                    pending_tool_outputs.clear()
                    await connection.response.create()
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\nEnding session...")
        finally:
            processor.shutdown()

    return conversation_id


async def lifecycle(configured_agent_name: Optional[str] = None) -> None:
    endpoint = required_env("AZURE_VOICE_AGENTS_ENDPOINT").rstrip("/")
    model_type = os.getenv("AZURE_VOICE_AGENTS_MODEL_TYPE", "managed")
    model = os.getenv("AZURE_VOICE_AGENTS_MODEL", "gpt-realtime")
    agent_name = configured_agent_name or f"voice-local-function-{uuid.uuid4().hex[:8]}"
    create_new = configured_agent_name is None

    audio_config = VoiceAgentAudioConfig(
        input=VoiceAgentAudioInputConfig(
            format=RealtimeAudioFormatsAudioPcm(rate=SAMPLE_RATE),
            turn_detection=VoiceAgentServerVadTurnDetection(
                threshold=0.5,
                prefix_padding_ms=300,
                silence_duration_ms=700,
            ),
            noise_reduction=VoiceAgentNoiseReduction(
                type=VoiceAgentNoiseReductionType.AZURE_DEEP_NOISE_SUPPRESSION
            ),
            transcription=VoiceAgentInputTranscription(
                model="whisper-1",
                language="en-US",
            ),
        ),
        output=VoiceAgentAudioOutputConfig(
            format=RealtimeAudioFormatsAudioPcm(rate=SAMPLE_RATE),
            voice=os.getenv("AZURE_VOICE_AGENTS_VOICE", "en-US-AvaNeural"),
            voice_type=VoiceType.AZURE_STANDARD,
        ),
    )
    tool = VoiceAgentFunctionTool(
        name="add_numbers",
        description="Add two numbers using the client application.",
        parameters=RealtimeFunctionToolParameters(
            {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
                "additionalProperties": False,
            }
        ),
    )
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
        if create_new:
            await client.agents.create_version(
                agent_name=agent_name,
                description="Local function microphone lifecycle sample.",
                definition=VoiceAgentDefinition(
                    model_type=model_type,
                    model=model,
                    instructions=(
                        "Always use add_numbers for addition. After receiving the "
                        "function output, state the numeric result."
                    ),
                    audio=audio_config,
                    output_modalities=[
                        VoiceOutputModality.TEXT,
                        VoiceOutputModality.AUDIO,
                    ],
                    tools=[tool],
                    store=True,
                ),
            )
            print(f"Created voice agent: {agent_name}")

        else:
            await client.agents.get(agent_name=agent_name)
            print(f"Using existing voice agent: {agent_name}")

        conversation_id = await run_microphone_session(
            client,
            agent_name,
        )
        if conversation_id:
            print(f"Conversation id: {conversation_id}")
            print(
                "Download it later with: "
                f"python samples/download_conversation_artifacts.py "
                f"{agent_name} {conversation_id}"
            )
        else:
            print("No persisted conversation id was returned.")
        try:
            trace_url = await build_foundry_trace_url(
                endpoint, agent_name, credential
            )
        except Exception as error:  # URL discovery is non-critical
            print(f"Could not build the Foundry trace URL: {error}")
        else:
            if trace_url:
                print(f"View traces in Azure AI Foundry: {trace_url}")
            else:
                print("Could not find the Azure AI account for the trace URL.")
        print(f"Agent retained for further testing: {agent_name}")


def parse_agent_name() -> Optional[str]:
    """Read an optional existing agent name from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "agent_name",
        nargs="?",
        default=os.getenv("AZURE_VOICE_AGENTS_AGENT_NAME"),
        help="Existing agent name. Omit it to create a new agent.",
    )
    value = parser.parse_args().agent_name
    return (value or "").strip() or None


if __name__ == "__main__":
    try:
        asyncio.run(lifecycle(parse_agent_name()))
    except KeyboardInterrupt:
        print("\nInterrupted.")
