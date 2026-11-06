#!/usr/bin/env python3
"""Create a poetry prompt subagent and voice agent with the Foundry SDK."""

from __future__ import annotations

import argparse
import shlex
import sys
import uuid

try:
    from azure.ai.projects import AIProjectClient, models
    from azure.core.exceptions import AzureError
    from azure.identity import DefaultAzureCredential
    from dotenv import load_dotenv
except ModuleNotFoundError as error:
    print(
        f"Missing Python dependency: {error.name}\n"
        "Set up this sample's virtual environment and run:\n"
        "  python -m pip install -r requirements.txt",
        file=sys.stderr,
    )
    raise SystemExit(1) from error

from sample_utils import project_endpoint_from_env, required_env


def prompt_definition(model: str) -> models.PromptAgentDefinition:
    return models.PromptAgentDefinition(
        model=model,
        instructions=(
            "You write original poems. Match the requested topic, tone, style, "
            "and length. Return only the poem."
        ),
    )


def voice_definition(
    model: str,
    subagent_name: str,
    voice: str,
) -> models.VoiceAgentDefinition:
    return models.VoiceAgentDefinition(
        model_type="managed",
        model=model,
        instructions=(
            "You are a concise poetry voice assistant. Your primary purpose "
            "is to help users create original poems. Keep spoken answers "
            "brief and natural, usually one or two sentences. When asked "
            "what you can do, emphasize that you can write poems based on a "
            "topic, mood, or style. Do not list broad, unrelated assistant "
            "capabilities. When the user requests a poem, ask the poetry "
            "specialist to write it. Present the poem naturally without "
            "mentioning specialists, delegation, tools, or internal agent "
            "names."
        ),
        store=True,
        audio=models.VoiceAgentAudioConfig(
            input=models.VoiceAgentAudioInputConfig(
                format=models.RealtimeAudioFormatsAudioPcm(rate=24000),
                turn_detection=models.VoiceAgentServerVadTurnDetection(
                    threshold=0.5,
                    prefix_padding_ms=300,
                    silence_duration_ms=500,
                ),
                transcription=models.VoiceAgentInputTranscription(
                    model="azure-speech",
                ),
            ),
            output=models.VoiceAgentAudioOutputConfig(
                format=models.RealtimeAudioFormatsAudioPcm(rate=24000),
                voice=voice,
                voice_type="azure-standard",
            ),
        ),
        output_modalities=["audio"],
        subagent_config=models.VoiceAgentSubagentConfig(
            subagents=[
                models.VoiceAgentSubagent(
                    agent_name=subagent_name,
                    agent_capabilities=(
                        "Writes original poems for a requested topic, mood, "
                        "or style."
                    ),
                    response_policy=models.VoiceAgentSubagentResponsePolicy(
                        immediate_ack=True,
                    ),
                )
            ],
        ),
    )


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    load_dotenv()
    endpoint = project_endpoint_from_env()
    voice_model = required_env("VOICE_MODEL_DEPLOYMENT", "gpt-realtime")
    subagent_model = required_env("SUBAGENT_MODEL_DEPLOYMENT")
    voice = required_env("VOICE_NAME", "en-US-Ava:DragonHDLatestNeural")
    suffix = uuid.uuid4().hex[:10]
    subagent_name = f"poetry-subagent-{suffix}"
    voice_agent_name = f"poetry-voice-agent-{suffix}"
    cleanup_command = (
        "python delete_agents.py "
        f"--voice-agent-name {shlex.quote(voice_agent_name)} "
        f"--subagent-name {shlex.quote(subagent_name)}"
    )
    print(f"Voice agent: {voice_agent_name}", flush=True)
    print(f"Subagent:    {subagent_name}", flush=True)
    print(f"\nDelete these agents when finished:\n  {cleanup_command}", flush=True)

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(
            endpoint=endpoint,
            credential=credential,
            allow_preview=True,
        ) as project,
    ):
        try:
            subagent = project.agents.create_version(
                agent_name=subagent_name,
                definition=prompt_definition(subagent_model),
                description="Poetry prompt subagent for the basic sample",
            )
            print(f"Created subagent: {subagent.name}:{subagent.version}", flush=True)
            voice_agent = project.agents.create_version(
                agent_name=voice_agent_name,
                definition=voice_definition(voice_model, subagent_name, voice),
                description="Voice agent for the basic subagent sample",
            )
            print(f"Created voice agent: {voice_agent.name}:{voice_agent.version}")
        except AzureError:
            print(
                "Creation failed; one or both agents may exist. "
                f"Clean up with:\n  {cleanup_command}",
                file=sys.stderr,
            )
            raise

    print("\nTalk to the voice agent:")
    print(
        "  ../client/.venv/bin/python ../client/voice_client.py "
        f"--project-endpoint {shlex.quote(endpoint)} "
        f"--agent-name {shlex.quote(voice_agent_name)}"
    )


if __name__ == "__main__":
    main()
