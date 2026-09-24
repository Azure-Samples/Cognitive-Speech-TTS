"""Shared audio devices and terminal output for the voice clients."""

from __future__ import annotations

import asyncio
import base64
import json
import queue
from dataclasses import dataclass
from typing import Any

SAMPLE_RATE = 24_000
CHANNELS = 1
CHUNK_FRAMES = 1_200


def load_audio_module() -> Any:
    try:
        import pyaudio
    except ImportError as error:
        raise RuntimeError(
            "PyAudio could not be loaded in this Python environment. Check "
            "the Python and PortAudio setup in client/README.md, then run "
            "with client/.venv/bin/python."
        ) from error
    return pyaudio


@dataclass(frozen=True)
class PlaybackPacket:
    generation: int
    data: bytes


class AudioIO:
    def __init__(self, pyaudio_module: Any) -> None:
        self._pyaudio = pyaudio_module
        self._audio = pyaudio_module.PyAudio()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._input_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=20)
        self._playback_queue: queue.Queue[PlaybackPacket] = queue.Queue()
        self._playback_generation = 0
        self._input_stream: Any = None
        self._output_stream: Any = None

    def start(self) -> None:
        self._loop = asyncio.get_running_loop()

        def capture_callback(
            data: bytes,
            _frame_count: int,
            _time_info: dict[str, Any],
            _status_flags: int,
        ) -> tuple[None, int]:
            assert self._loop is not None
            self._loop.call_soon_threadsafe(self._queue_input, bytes(data))
            return None, self._pyaudio.paContinue

        remaining = b""
        remaining_generation = self._playback_generation

        def playback_callback(
            _data: bytes | None,
            frame_count: int,
            _time_info: dict[str, Any],
            _status_flags: int,
        ) -> tuple[bytes, int]:
            nonlocal remaining, remaining_generation
            byte_count = frame_count * 2
            if remaining_generation < self._playback_generation:
                remaining = b""
                remaining_generation = self._playback_generation

            output = remaining[:byte_count]
            remaining = remaining[byte_count:]
            while len(output) < byte_count:
                try:
                    packet = self._playback_queue.get_nowait()
                except queue.Empty:
                    output += b"\0" * (byte_count - len(output))
                    break
                if packet.generation < self._playback_generation:
                    continue
                remaining_generation = packet.generation
                needed = byte_count - len(output)
                output += packet.data[:needed]
                remaining = packet.data[needed:]
            return output, self._pyaudio.paContinue

        self._output_stream = self._audio.open(
            format=self._pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            output=True,
            frames_per_buffer=CHUNK_FRAMES,
            stream_callback=playback_callback,
        )
        self._input_stream = self._audio.open(
            format=self._pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_FRAMES,
            stream_callback=capture_callback,
        )

    def _queue_input(self, data: bytes) -> None:
        if self._input_queue.full():
            self._input_queue.get_nowait()
        self._input_queue.put_nowait(data)

    async def next_input(self) -> bytes:
        return await self._input_queue.get()

    def queue_output(self, data: bytes) -> None:
        self._playback_queue.put(
            PlaybackPacket(self._playback_generation, data)
        )

    def interrupt_playback(self) -> None:
        self._playback_generation += 1
        while True:
            try:
                self._playback_queue.get_nowait()
            except queue.Empty:
                break

    def close(self) -> None:
        if self._input_stream is not None:
            self._input_stream.stop_stream()
            self._input_stream.close()
            self._input_stream = None
        if self._output_stream is not None:
            self.interrupt_playback()
            self._output_stream.stop_stream()
            self._output_stream.close()
            self._output_stream = None
        self._audio.terminate()


def print_event(event: dict[str, Any], audio: AudioIO) -> None:
    event_type = str(event.get("type") or "")
    if event_type in {
        "response.audio.delta",
        "response.output_audio.delta",
    }:
        delta = event.get("delta")
        if isinstance(delta, str) and delta:
            audio.queue_output(base64.b64decode(delta))
    elif event_type == "input_audio_buffer.speech_started":
        audio.interrupt_playback()
        print("\nListening...")
    elif event_type == "input_audio_buffer.speech_stopped":
        print("Processing...")
    elif event_type == "conversation.item.input_audio_transcription.completed":
        print(f'You: {event.get("transcript") or ""}')
    elif event_type in {
        "response.audio_transcript.done",
        "response.output_audio_transcript.done",
    }:
        print(f'Agent: {event.get("transcript") or ""}')
    elif event_type == "session.subagent.started":
        print(f'Subagent started: {event.get("subagent_name") or "unknown"}')
    elif event_type == "session.subagent.completed":
        print(
            f'Subagent completed: {event.get("subagent_name") or "unknown"}'
        )
    elif event_type in {"session.subagent.failed", "session.subagent.aborted"}:
        details = (
            event.get("error")
            or event.get("reason")
            or event.get("status_details")
        )
        suffix = (
            f": {json.dumps(details, ensure_ascii=False)}"
            if details
            else ""
        )
        print(f"Subagent ended: {event_type}{suffix}")
    elif event_type == "error":
        error = event.get("error") or {}
        raise RuntimeError(
            f"Voice endpoint error ({error.get('code', 'unknown')}): "
            f"{error.get('message') or json.dumps(event)}"
        )
