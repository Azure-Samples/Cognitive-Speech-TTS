"""Create a simple voice agent with REST, or retrieve an existing one."""

from __future__ import annotations

import argparse
import os
import uuid
from urllib.parse import quote

import requests
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

PREVIEW_FEATURE = "VoiceAgents=V1Preview"
TOKEN_SCOPE = "https://ai.azure.com/.default"
API_VERSION = "v1"


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name} before running this sample.")
    return value


def build_definition() -> dict:
    """Build the simple voice-agent REST payload."""
    model_type = os.getenv("AZURE_VOICE_AGENTS_MODEL_TYPE", "managed")
    model = os.getenv("AZURE_VOICE_AGENTS_MODEL", "gpt-realtime")
    voice = os.getenv("AZURE_VOICE_AGENTS_VOICE", "en-US-AvaNeural")
    return {
        "kind": "voice",
        "model_type": model_type,
        "model": model,
        "instructions": (
            "You are a friendly voice assistant. Keep answers concise and natural."
        ),
        "audio": {
            "output": {
                "format": {"type": "audio/pcm", "rate": 24000},
                "voice": {"type": "azure-standard", "name": voice},
            }
        },
        "output_modalities": ["text", "audio"],
        "store": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "agent_name",
        nargs="?",
        default=os.getenv("AZURE_VOICE_AGENTS_AGENT_NAME"),
        help="Existing agent name. Omit it to create a new agent.",
    )
    args = parser.parse_args()

    endpoint = required_env("AZURE_VOICE_AGENTS_ENDPOINT").rstrip("/")
    configured_agent_name = (args.agent_name or "").strip() or None
    agent_name = configured_agent_name or f"voice-rest-{uuid.uuid4().hex[:8]}"
    create_new = configured_agent_name is None
    headers: dict[str, str]

    with DefaultAzureCredential() as credential:
        token = credential.get_token(TOKEN_SCOPE).token
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Foundry-Features": PREVIEW_FEATURE,
        }
        if create_new:
            response = requests.post(
                f"{endpoint}/voice_agents",
                params={"api-version": API_VERSION},
                headers=headers,
                json={
                    "name": agent_name,
                    "description": "Simple REST creation sample.",
                    "definition": build_definition(),
                },
                timeout=60,
            )
        else:
            response = requests.get(
                f"{endpoint}/voice_agents/{quote(agent_name, safe='')}",
                params={"api-version": API_VERSION},
                headers=headers,
                timeout=60,
            )
        response.raise_for_status()
        returned_name = response.json().get("name", agent_name)
        action = "Created" if create_new else "Using existing"
        print(f"{action} voice agent: {returned_name}")


if __name__ == "__main__":
    main()
