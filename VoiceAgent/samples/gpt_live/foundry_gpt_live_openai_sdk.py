#!/usr/bin/env python3
"""Create or reuse a Foundry GPT Live agent, then stream audio with the OpenAI SDK."""

import argparse
import asyncio
import base64
import contextlib
import os
import signal
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit
from uuid import uuid4

import httpx
from azure.core.exceptions import ClientAuthenticationError
from azure.identity.aio import AzureCliCredential, get_bearer_token_provider
from dotenv import load_dotenv
from openai import AsyncOpenAI
from openai.resources.live.live import AsyncLiveConnection
from websockets.exceptions import ConnectionClosed

from audio_common import Audio, AudioError, RATE
from transcript_common import TranscriptDisplay

PREVIEW = "VoiceAgents=V1Preview"
API_VERSION = "v1"
TOKEN_SCOPE = "https://ai.azure.com/.default"
ENGLISH_TEACHER_INSTRUCTIONS = (
    "You are a patient English teacher helping the learner practice spoken English. "
    "Ask one short question at a time and let the learner answer. Gently correct "
    "grammar or vocabulary mistakes with an improved sentence and a brief explanation. "
    "Keep replies concise and encouraging. Use English for practice; if the learner "
    "asks in Chinese, briefly explain in Chinese and then return to English."
)
BACKEND_INSTRUCTIONS = (
    "You are an expert English teacher supporting a spoken English lesson. "
    "Give one accurate, concise grammar explanation and one example or corrected sentence. "
    "Write guidance for the voice teacher, not a long essay."
)


class DemoError(Exception):
    pass


class EntraAuth(httpx.Auth):
    """Share automatically refreshed Azure CLI tokens between REST and the SDK."""

    def __init__(self, credential):
        self.token_provider = get_bearer_token_provider(credential, TOKEN_SCOPE)

    async def async_auth_flow(self, request):
        request.headers["Authorization"] = f"Bearer {await self.token_provider()}"
        yield request


# Agent configuration is intentionally fully visible here, separate from the SDK conversation.
def agent_payload(name):
    backend = required("GPT_LIVE_DELEGATION_DEPLOYMENT")
    instructions = ENGLISH_TEACHER_INSTRUCTIONS + (
        " Handle greetings and casual conversation yourself. For grammar corrections, "
        "grammar explanations, or lesson planning, always delegate to the Responses "
        "English-teacher backend first, then explain its guidance aloud."
    )
    return {
        "name": name,
        "definition": {
            "kind": "voice",
            "sub_protocol": "live",
            "model_type": "self_deployed",
            "model": required("GPT_LIVE_DEPLOYMENT"),
            "instructions": instructions,
            "audio": {
                "format": {"type": "audio/pcm", "rate": RATE},
                "output": {"voice": "marin"},
            },
            "delegation": {
                "type": "responses",
                "responses": {"model": backend, "instructions": BACKEND_INSTRUCTIONS},
            },
            # Persist in Foundry for the shared conversation downloader.
            "store": True,
        },
    }


async def converse(
    connection: AsyncLiveConnection,
    audio: Audio,
    transcript: TranscriptDisplay,
    backend_model: str,
) -> str | None:
    """The whole SDK event/audio loop is here so the sample can be read on its own."""
    events = connection.__aiter__()
    stop = transcript.stop_requested
    loop = asyncio.get_running_loop()
    old_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, lambda *_: loop.call_soon_threadsafe(stop.set))
    session_id = None
    conversation_id = None
    closed = close_sent = False
    audio_started = False
    replied = set()
    tasks = []

    async def observe(event):
        nonlocal closed
        if event.type == "error":
            raise DemoError(f"Live error: {event.error.message}")
        if event.type == "session.output_audio.delta":
            audio.play(base64.b64decode(event.delta, validate=True))
        elif event.type == "session.input_transcript.delta":
            transcript.append_user(event.delta)
        elif event.type == "session.output_transcript.delta":
            transcript.append_agent(event.delta)
        elif event.type == "session.delegation.created":
            delegation = event.delegation
            transcript.update_agent_activity(
                delegation.id,
                title=f"Delegation → {backend_model if delegation.target == 'responses' else delegation.target}",
                status="Delegation requested",
            )
            if delegation.target == "client" and delegation.id not in replied:
                replied.add(delegation.id)
                content = "This demo uses a Responses backend, not a client executor. Please continue the English lesson."
                await connection.session.commentary.append(
                    delegation_id=delegation.id,
                    content=content,
                )
        elif event.type == "response.event":
            # Backend guidance is not the spoken teacher transcript.
            backend = event.event
            kind = backend.get("type")
            activity_id = event.delegation_id or "uncorrelated-backend"
            statuses = {
                "response.created": "Backend response started",
                "response.in_progress": "Backend response in progress",
                "response.output_text.delta": "Receiving backend guidance",
                "response.completed": "Backend response completed",
                "response.failed": "Backend response failed",
                "response.incomplete": "Backend response incomplete",
                "error": "Backend error",
            }
            if kind in statuses:
                transcript.update_agent_activity(
                    activity_id,
                    title=f"{'Delegation' if event.delegation_id else 'Uncorrelated backend'} → {backend_model}",
                    status=statuses[kind],
                    delta=backend.get("delta", "")
                    if kind == "response.output_text.delta"
                    else "",
                )
            if kind in {
                "error",
                "response.failed",
                "response.incomplete",
            }:
                raise DemoError(
                    f"Teaching backend reported {backend['type']}; check its deployment and configuration."
                )
        elif event.type == "session.closed":
            closed = True
            transcript.set_status(
                f"Session closed: {event.reason}; cumulative Live usage: {event.usage.seconds} seconds"
            )
            if event.reason == "connection_lost":
                raise DemoError(
                    "Upstream connection was lost; native finalization is not confirmed."
                )

    async def receive():
        async for event in events:
            await observe(event)
            if closed:
                return
        raise DemoError(
            "WebSocket ended without session.closed; finalization is unconfirmed."
        )

    async def send_microphone():
        # audio.frames() yields PCM only; encoding and SDK calls belong to this sample.
        async for pcm in audio.frames(stop):
            encoded = base64.b64encode(pcm).decode("ascii")
            await connection.session.input_audio.append(audio=encoded)

    try:
        # Foundry owns session.start. Wait for service-owned readiness; do not start again.
        async with asyncio.timeout(30):
            async for event in events:
                await observe(event)
                if event.type == "session.started":
                    session_id = event.session.id
                    # Foundry adds this top-level field; it is not session.id.
                    # The OpenAI SDK preserves service-specific fields as extras.
                    value = getattr(event, "conversation_id", None)
                    if isinstance(value, str) and value.strip():
                        conversation_id = value
                    actual_format = event.session.audio.format
                    if actual_format and (actual_format.type, actual_format.rate) != (
                        "audio/pcm",
                        RATE,
                    ):
                        raise DemoError(
                            "The negotiated format is not the requested PCM16/24 kHz."
                        )
                    break
                if closed:
                    raise DemoError("Live closed before startup completed.")
            else:
                raise DemoError("WebSocket ended before session.started.")
        if not stop.is_set():
            transcript.set_status(
                f"Ready: {session_id}. Speak into your microphone; Ctrl+C ends the English lesson."
            )
            audio.start()
            audio_started = True
        receiver = asyncio.create_task(receive())
        sender = asyncio.create_task(send_microphone())
        stopped = asyncio.create_task(stop.wait())
        tasks.extend([receiver, sender, stopped])
        done, _ = await asyncio.wait(
            [receiver, sender, stopped], return_when=asyncio.FIRST_COMPLETED
        )
        if receiver in done:
            receiver.result()
        elif sender in done:
            sender.result()
        stop.set()
        audio.stop_microphone()
        sender.cancel()
        await asyncio.gather(sender, return_exceptions=True)
        if not receiver.done():
            transcript.set_status("Closing; waiting for session.closed...")
            close_sent = True
            async with asyncio.timeout(5):
                await connection.session.close()
            async with asyncio.timeout(15):
                await receiver
        if audio_started:
            await audio.drain()
        return conversation_id
    except ConnectionClosed as exc:
        raise DemoError(
            "WebSocket ended without session.closed; finalization is unconfirmed."
        ) from exc
    finally:
        stop.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if session_id and not closed and not close_sent:
            with contextlib.suppress(Exception):
                async with asyncio.timeout(3):
                    await connection.session.close()
        signal.signal(signal.SIGINT, old_sigint)


async def check_deployments(http, base, payload):
    """Check the configured model deployments with read-only requests."""
    definition = payload["definition"]
    deployments = {
        "GPT_LIVE_DEPLOYMENT": definition["model"],
    }
    delegation = definition.get("delegation") or {}
    if delegation.get("type") == "responses":
        deployments["GPT_LIVE_DELEGATION_DEPLOYMENT"] = delegation["responses"]["model"]
    for setting, name in deployments.items():
        response = await http.get(
            f"{base}/deployments/{quote(name, safe='')}",
            params={"api-version": API_VERSION},
        )
        if response.status_code == 404:
            raise DemoError(
                f"Deployment '{name}' was not found in this project. "
                f"Check the existing agent's deployment, or {setting} for a new agent."
            )
        check_response(response, f"Check deployment '{name}'")
        if response.json().get("name") != name:
            raise DemoError(f"Deployment readback did not match {setting}='{name}'.")
        print(f"Deployment verified: {setting}={name}", flush=True)


async def main(*, auto_delete: bool = False):
    base = project_endpoint()
    existing_agent = os.getenv("AGENT_NAME", "").strip()
    name = existing_agent or f"english-teacher-{uuid4().hex[:12]}"
    payload = None if existing_agent else agent_payload(name)
    agent_url = f"{base}/agents/{quote(name, safe='')}"
    created = False
    credential = project_credential()
    auth = EntraAuth(credential)
    async with (
        credential,
        httpx.AsyncClient(
            auth=auth,
            headers={"Foundry-Features": PREVIEW},
            timeout=30,
            follow_redirects=False,
        ) as http,
    ):
        if payload is not None:
            await check_deployments(http, base, payload)
        try:
            with Audio() as audio:
                if not existing_agent:
                    response = await http.post(
                        f"{base}/agents",
                        params={"api-version": API_VERSION},
                        json=payload,
                    )
                    check_response(response, "Create agent")
                    created = True
                    version = response.json()["versions"]["latest"]["version"]
                    print(
                        f"Created English teacher agent: {name}, version {version}",
                        flush=True,
                    )
                response = await http.get(
                    agent_url, params={"api-version": API_VERSION}
                )
                if existing_agent and response.status_code == 404:
                    raise DemoError(
                        f"Agent '{name}' was not found in this project. Check AGENT_NAME."
                    )
                check_response(response, "Read agent")
                latest = response.json()["versions"]["latest"]
                definition = latest["definition"]
                if definition.get("sub_protocol") != "live":
                    raise DemoError(
                        "The agent must use sub_protocol=live. "
                        "Check AGENT_NAME or the created agent definition."
                    )
                if existing_agent:
                    version = latest["version"]
                    print(f"Using existing agent: {name}, version {version}", flush=True)
                    await check_deployments(http, base, {"definition": definition})
                delegation = definition.get("delegation") or {}
                backend_model = (delegation.get("responses") or {}).get(
                    "model"
                ) or delegation.get("type", "client")

                # The SDK appends /live/sessions. Point it at the agent protocol,
                # not the model's /openai/v1 endpoint or a complete sessions URL.
                # api_key accepts an async Entra token provider, not a stored key.
                async with AsyncOpenAI(
                    api_key=auth.token_provider,
                    base_url=f"{agent_url}/endpoint/protocols/voice",
                    max_retries=0,
                ) as client:
                    async with client.live.connect(
                        extra_headers={"Foundry-Features": PREVIEW},
                        extra_query={
                            "api-version": API_VERSION,
                            "x-agent-version-override": str(version),
                        },
                        max_retries=0,
                        websocket_connection_options={
                            "open_timeout": 20,
                            "close_timeout": 5,
                            "max_size": 1024 * 1024,
                        },
                    ) as connection:
                        # Do NOT call connection.session.start(): Foundry does it.
                        async with TranscriptDisplay() as transcript:
                            conversation_id = await converse(
                                connection,
                                audio,
                                transcript,
                                backend_model,
                            )
            if conversation_id:
                print(f"Conversation id: {conversation_id}", flush=True)
                if created and auto_delete:
                    print(
                        "The agent will be deleted (--auto-delete). "
                        "Omit this option to download the conversation later.",
                        flush=True,
                    )
                else:
                    downloader = (
                        Path(__file__).resolve().parent.parent
                        / "download_conversation_artifacts.py"
                    )
                    command_prefix = "& " if os.name == "nt" else ""
                    print(
                        "Download it later with the shared downloader "
                        "(run from VoiceAgent):\n"
                        f"Set AZURE_VOICE_AGENTS_ENDPOINT to {base}.\n"
                        f'{command_prefix}"{sys.executable}" "{downloader}" '
                        f'"{name}" "{conversation_id}"',
                        flush=True,
                    )
            else:
                print("No persisted conversation id was returned.", flush=True)
        finally:
            if created and auto_delete:
                try:
                    response = await http.delete(
                        agent_url, params={"api-version": API_VERSION}
                    )
                    if response.status_code != 404:
                        check_response(response, "Delete demo agent")
                    print(f"Deleted temporary demo agent: {name}", flush=True)
                except Exception as exc:
                    print(
                        f"Cleanup failed ({type(exc).__name__}); delete agent {name} manually.",
                        flush=True,
                    )
            elif created:
                print(
                    f"Kept agent: {name}. Delete it in your Foundry project when finished.",
                    flush=True,
                )


# HTTP authentication, URL construction, and error handling stay in this sample.
def required(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise DemoError(f"Set {name} in .env or the process environment.")
    return value


def project_endpoint():
    value = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    if not value:
        raise DemoError(
            "Set FOUNDRY_PROJECT_ENDPOINT=https://YOUR-RESOURCE.services.ai.azure.com/api/projects/YOUR-PROJECT "
            "in .env. This creates a voice agent in an EXISTING project, not a new Azure project."
        )
    url = urlsplit(value.strip())
    local = url.hostname in {"localhost", "127.0.0.1", "::1"}
    path = url.path.rstrip("/")
    if (
        not url.hostname
        or url.username is not None
        or url.password is not None
        or url.query
        or url.fragment
        or (url.scheme != "https" and not (local and url.scheme == "http"))
        or not path.startswith("/api/projects/")
        or not path.removeprefix("/api/projects/")
        or "/" in path.removeprefix("/api/projects/")
    ):
        raise DemoError(
            "Use an HTTPS project endpoint ending in /api/projects/YOUR-PROJECT without credentials/query/fragment."
        )
    return urlunsplit((url.scheme, url.netloc, path, "", ""))


def project_credential():
    # Select the matching signed-in account without changing az's global default.
    subscription = os.getenv("AZURE_SUBSCRIPTION_ID", "").strip() or None
    return AzureCliCredential(subscription=subscription)


def check_response(response, action):
    if response.is_success:
        return
    hint = {
        401: "Run az login again and check AZURE_SUBSCRIPTION_ID.",
        403: "Check the signed-in identity's project permissions and preview access.",
        404: "Check the project endpoint and whether this service has the Live implementation.",
        409: "The generated agent name already exists; run the demo again.",
        429: "Deployment quota is exhausted; retry later.",
    }.get(response.status_code, "Check the request and service configuration.")
    raise DemoError(f"{action}: HTTP {response.status_code}. {hint}")


def run_cli():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument(
        "--auto-delete",
        action="store_true",
        default=False,
        help="Delete only the agent created by this run on exit (default: keep it).",
    )
    args = parser.parse_args()
    try:
        load_dotenv(Path(__file__).resolve().with_name(".env"), override=False)
        asyncio.run(main(auto_delete=args.auto_delete))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
    except ClientAuthenticationError:
        print(
            "\nAzure CLI authentication failed. Run az login with an account that "
            "can access this project, and check AZURE_SUBSCRIPTION_ID in .env.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    except (DemoError, AudioError) as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        response = getattr(exc, "response", None)
        status = getattr(exc, "status_code", None) or getattr(
            response, "status_code", None
        )
        detail = f" (HTTP {status})" if status else ""
        print(
            f"\n{type(exc).__name__}{detail}. Check your .env settings and endpoint access.",
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    run_cli()
