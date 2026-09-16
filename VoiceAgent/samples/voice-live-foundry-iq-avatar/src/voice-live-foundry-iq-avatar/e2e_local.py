# Copyright (c) Microsoft. All rights reserved.

"""Headless end-to-end test for the Voice Live + Foundry IQ sample."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import struct
import subprocess
import sys
import time
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

import websockets


def _foundry_url(
    project_endpoint: str,
    agent: str,
    session_id: str,
    api_version: str = "v1",
) -> str:
    parts = urlsplit(project_endpoint)
    if (
        parts.scheme not in ("https", "wss")
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
    ):
        raise ValueError("Foundry endpoint must use https or wss without user information.")
    _ = parts.port  # Reject malformed ports before requesting a token.
    project = parts.path.rstrip("/").rsplit("/", 1)[-1]
    query = urlencode(
        {
            "api-version": api_version,
            "agent_session_id": session_id,
        }
    )
    path = (
        f"/api/projects/{quote(project, safe='')}"
        f"/agents/{quote(agent, safe='')}"
        "/endpoint/protocols/invocations_ws"
    )
    return urlunsplit(
        (
            "wss",
            parts.netloc,
            path,
            query,
            "",
        )
    )


def _entra_token(resource: str = "https://ai.azure.com") -> str:
    result = subprocess.run(
        ["az", "account", "get-access-token", "--resource", resource, "-o", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)["accessToken"]


def _elapsed_ms(started: float) -> float:
    return (time.monotonic() - started) * 1000


async def _run(
    url: str,
    timeout: float,
    prompt: str,
    expected: str,
    headers: dict[str, str] | None = None,
    require_mcp: bool = True,
    require_avatar: bool = False,
) -> int:
    print(f"[e2e] connecting {url} ...", flush=True)

    started = time.monotonic()
    got_session = False
    got_audio_bytes = 0
    got_video_bytes = 0
    got_avatar_enabled = False
    got_mcp_completed = False
    got_response_done = False
    got_error: str | None = None
    transcript = ""
    greeting_expected = False
    got_greeting_completed = False
    prompt_sent = False
    timings: dict[str, float] = {}
    deadline = started + timeout

    async with websockets.connect(
        url,
        max_size=16 * 1024 * 1024,
        additional_headers=list((headers or {}).items()) or None,
    ) as websocket:

        async def send_prompt() -> None:
            nonlocal prompt_sent
            if prompt_sent:
                return
            print(f"[e2e] -> text: {prompt!r}", flush=True)
            await websocket.send(json.dumps({"type": "text", "content": prompt}))
            prompt_sent = True
            timings["question_sent_ms"] = _elapsed_ms(started)

        while time.monotonic() < deadline:
            try:
                raw = await asyncio.wait_for(
                    websocket.recv(), timeout=deadline - time.monotonic()
                )
            except (asyncio.TimeoutError, websockets.ConnectionClosed):
                break

            if isinstance(raw, (bytes, bytearray)):
                if not prompt_sent or len(raw) <= 8:
                    continue
                sample_rate, channels = struct.unpack("<II", raw[:8])
                if not got_audio_bytes:
                    timings["first_audio_ms"] = _elapsed_ms(started)
                    print(
                        f"[e2e] first audio: sr={sample_rate} ch={channels}",
                        flush=True,
                    )
                got_audio_bytes += len(raw) - 8
                continue

            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                print(f"[e2e] non-JSON text frame: {raw!r}", flush=True)
                continue

            event_type = message.get("type")
            if event_type == "video_data":
                try:
                    chunk = base64.b64decode(message.get("delta", ""), validate=True)
                except (ValueError, TypeError):
                    got_error = "Invalid Avatar media encoding."
                    continue
                # Idle animation and greeting media are not answer evidence.
                if prompt_sent:
                    if chunk and not got_video_bytes:
                        timings["first_video_ms"] = _elapsed_ms(started)
                    got_video_bytes += len(chunk)
                continue
            print(f"[e2e] event: {message}", flush=True)
            if event_type == "session_started":
                if not got_session:
                    got_session = True
                    got_avatar_enabled = message.get("avatar_enabled") is True
                    greeting_expected = message.get("greeting_pending") is True
                    timings["session_started_ms"] = _elapsed_ms(started)
                    if not greeting_expected:
                        await send_prompt()
            elif event_type == "mcp_status":
                if (
                    prompt_sent
                    and message.get("operation") == "call"
                    and message.get("status") == "completed"
                ):
                    got_mcp_completed = True
                    timings["mcp_completed_ms"] = _elapsed_ms(started)
            elif event_type == "bot_text":
                if prompt_sent:
                    transcript += str(message.get("delta") or "")
                    if message.get("final") and not transcript:
                        transcript = str(message.get("text") or "")
            elif event_type == "error":
                got_error = str(message)
            elif event_type == "response_done":
                if message.get("kind") == "greeting":
                    if not greeting_expected:
                        got_error = "Unexpected greeting completion."
                        break
                    if message.get("status") != "completed":
                        got_error = "Greeting did not complete successfully."
                        break
                    if not got_greeting_completed:
                        got_greeting_completed = True
                        timings["greeting_completed_ms"] = _elapsed_ms(started)
                        await send_prompt()
                    continue
                if not prompt_sent:
                    got_error = "Expected greeting completion before the answer."
                    break
                got_response_done = True
                timings["response_done_ms"] = _elapsed_ms(started)
                break

    expected_found = expected.lower() in transcript.lower()
    checks = {
        "session_started": got_session,
        "question_sent": prompt_sent,
        "knowledge_mcp_completed": got_mcp_completed if require_mcp else None,
        "expected_answer_text": expected_found,
        "audio_bytes_received": None if require_avatar else got_audio_bytes > 0,
        "response_done": got_response_done,
        "no_error": got_error is None,
    }

    if greeting_expected:
        checks["greeting_completed"] = got_greeting_completed

    if require_avatar:
        checks["avatar_enabled"] = got_avatar_enabled
        checks["avatar_media_received"] = got_video_bytes > 0

    print()
    for name, passed in checks.items():
        status = "SKIP" if passed is None else "PASS" if passed else "FAIL"
        print(f"[e2e] {name:27} {status}")
    print(f"[e2e] audio bytes:               {got_audio_bytes}")
    if require_avatar:
        print(f"[e2e] Avatar media bytes:        {got_video_bytes}")
        print("[e2e] Avatar playback:           NOT VALIDATED (manual browser test required)")
    print(f"[e2e] assistant transcript:      {transcript!r}")
    for name, milliseconds in timings.items():
        print(f"[e2e] {name:27} {milliseconds:.0f} ms")
    if got_error:
        print(f"[e2e] error:                     {got_error}")

    ok = all(passed is not False for passed in checks.values())
    skipped = any(passed is None for passed in checks.values())
    status = "FAIL" if not ok else "PASS (partial; checks skipped)" if skipped else "PASS"
    print(f"[e2e] result:                    {status}")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        help=(
            "Override the WebSocket URL. Defaults to the local agent, or to the "
            "Foundry URL constructed from --foundry and --agent."
        ),
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument(
        "--prompt",
        default="What can clusters of light over dark ocean water indicate?",
    )
    parser.add_argument(
        "--expected",
        default="vessel",
        help="Case-insensitive substring expected in the grounded response.",
    )
    parser.add_argument(
        "--foundry",
        help="Foundry project endpoint, such as https://<account>.services.ai.azure.com/api/projects/<project>.",
    )
    parser.add_argument(
        "--agent",
        default="voice-live-foundry-iq-avatar",
        help="Hosted agent name (Foundry mode only).",
    )
    parser.add_argument(
        "--skip-mcp",
        action="store_true",
        help="Do not require a completed MCP call (useful for protocol diagnostics only).",
    )
    parser.add_argument(
        "--require-avatar",
        action="store_true",
        help="Require Avatar media instead of audit PCM; playback needs a manual browser test.",
    )
    args = parser.parse_args()

    headers: dict[str, str] = {}
    if args.foundry:
        session_id = f"e2e-{int(time.time())}"
        try:
            foundry_url = _foundry_url(args.foundry.rstrip("/"), args.agent, session_id)
            url = args.url or foundry_url
            target = urlsplit(url)
            project = urlsplit(foundry_url)
            if (
                target.scheme != "wss"
                or target.username is not None
                or target.password is not None
                or target.hostname != project.hostname
                or (target.port or 443) != (project.port or 443)
            ):
                raise ValueError("Authenticated WebSocket URL must use wss on the Foundry project host and port without user information.")
        except ValueError as exc:
            parser.error(str(exc))
        headers["Authorization"] = f"Bearer {_entra_token()}"
    else:
        url = args.url or "ws://localhost:8088/invocations_ws"

    return asyncio.run(
        _run(
            url,
            args.timeout,
            args.prompt,
            args.expected,
            headers,
            require_mcp=not args.skip_mcp,
            require_avatar=args.require_avatar,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
