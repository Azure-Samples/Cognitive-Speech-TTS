#!/usr/bin/env python3
"""Create a voice agent referencing a deployed hosted agent with the SDK."""

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


def voice_definition(
    model: str,
    hosted_agent_name: str,
    voice: str,
) -> models.VoiceAgentDefinition:
    return models.VoiceAgentDefinition(
        model_type="managed",
        model=model,
        instructions=(
            "You are a concise GitHub Copilot voice assistant. You help users "
            "search for information, analyze topics, study, and complete "
            "coding tasks. Keep spoken answers brief and natural. When a "
            "request needs these capabilities, ask the GitHub Copilot "
            "specialist to handle it. Present the result naturally without "
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
                    agent_name=hosted_agent_name,
                    agent_capabilities=(
                        "Searches for information, analyzes topics, supports "
                        "learning, and completes coding tasks."
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
    hosted_agent_name = required_env("HOSTED_SUBAGENT_NAME")
    voice = required_env("VOICE_NAME", "en-US-Ava:DragonHDLatestNeural")
    voice_agent_name = f"github-copilot-voice-agent-{uuid.uuid4().hex[:10]}"
    cleanup_command = (
        "python delete_voice_agent.py "
        f"--voice-agent-name {shlex.quote(voice_agent_name)}"
    )
    print(f"Voice agent:  {voice_agent_name}", flush=True)
    print(f"Hosted agent: {hosted_agent_name}", flush=True)
    print(f"\nDelete the voice agent when finished:\n  {cleanup_command}", flush=True)

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(
            endpoint=endpoint,
            credential=credential,
            allow_preview=True,
        ) as project,
    ):
        try:
            agent = project.agents.create_version(
                agent_name=voice_agent_name,
                definition=voice_definition(voice_model, hosted_agent_name, voice),
                description="Voice agent using a hosted GitHub Copilot subagent with the SDK",
            )
            print(f"Created voice agent: {agent.name}:{agent.version}")
        except AzureError:
            print(
                "Creation failed; the voice agent may exist. "
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
