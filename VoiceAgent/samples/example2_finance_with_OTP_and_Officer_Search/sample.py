#!/usr/bin/env python3
"""Publish, verify, or run the Finance OTP and officer-search Voice Agent."""

from pathlib import Path
import sys

SAMPLES_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SAMPLES_DIR))

from voice_agent_sdk_common import sample_cli  # noqa: E402


if __name__ == "__main__":
    sample_cli(Path(__file__).resolve().parent, mode="typed")
