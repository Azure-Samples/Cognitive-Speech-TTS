#!/usr/bin/env python3
"""Delete the sample's voice agent, leaving the hosted subagent untouched."""

from __future__ import annotations

import argparse
import sys

try:
    from azure.ai.projects import AIProjectClient
    from azure.core.exceptions import ResourceNotFoundError
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

from sample_utils import project_endpoint_from_env


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voice-agent-name", required=True)
    args = parser.parse_args()
    load_dotenv()

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(
            endpoint=project_endpoint_from_env(),
            credential=credential,
            allow_preview=True,
        ) as project,
    ):
        try:
            project.agents.delete(agent_name=args.voice_agent_name)
            print(f"Deleted voice agent: {args.voice_agent_name}")
        except ResourceNotFoundError:
            print(f"Voice agent already deleted: {args.voice_agent_name}")


if __name__ == "__main__":
    main()
