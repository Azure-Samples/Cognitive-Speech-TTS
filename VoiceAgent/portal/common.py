# Copyright (c) Microsoft. All rights reserved.
"""Public-project configuration for the standalone Voice Agent portal.

Ported from voice_demo/common.py; see UPSTREAM.json and CHANGELOG.md.
There are deliberately no internal backends, subscription discovery, or tokens
in browser configuration. An Azure Foundry project is required; credentials
are acquired lazily when the portal calls that project.
"""
from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote, urlsplit

from azure.identity import DefaultAzureCredential

TOKEN_SCOPE = "https://ai.azure.com/.default"
FOUNDRY_FEATURES = "VoiceAgents=V1Preview"
INPUT_TRANSCRIPTION_MODEL = "azure-speech"
REALTIME_MODELS = ["gpt-realtime", "gpt-realtime-mini", "gpt-realtime-1.5"]
CASCADED_MODELS = ["gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini"]
MODELS = REALTIME_MODELS + CASCADED_MODELS
OPENAI_VOICES = ["alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse", "marin", "cedar"]
AZURE_VOICES = [
    "en-US-AvaNeural",
    "en-US-Ava:DragonHDLatestNeural",
    "en-US-AndrewNeural",
    "en-US-EmmaNeural",
    "en-US-BrianNeural",
    "en-US-JennyNeural",
    "en-US-GuyNeural",
    "en-US-AvaMultilingualNeural",
    "zh-CN-XiaoxiaoNeural",
]
DEFAULT_AZURE_VOICE = AZURE_VOICES[0]


def deployment_names(variable: str) -> list[str]:
    """Only offer deployment names explicitly configured by this developer."""
    return list(dict.fromkeys(
        value.strip() for value in os.getenv(variable, "").split(",") if value.strip()
    ))


def validate_project_endpoint(endpoint: str) -> str:
    """Do not send the developer's Azure token to arbitrary URLs or HTTP hosts."""
    endpoint = endpoint.strip().rstrip("/")
    if not endpoint:
        raise ValueError(
            "An Azure Foundry project is required. Set AZURE_VOICE_AGENTS_ENDPOINT "
            "in the portal's .env or pass --project-endpoint "
            "https://<account>.services.ai.azure.com/api/projects/<project>."
        )
    parts = urlsplit(endpoint)
    if (
        parts.scheme != "https"
        or not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.services\.ai\.azure\.com", parts.hostname or "")
        or parts.username is not None
        or parts.password is not None
        or parts.port not in (None, 443)
        or not re.fullmatch(r"/api/projects/[A-Za-z0-9][A-Za-z0-9._-]*", parts.path)
        or parts.query
        or parts.fragment
    ):
        raise ValueError(
            "Set AZURE_VOICE_AGENTS_ENDPOINT or --project-endpoint to "
            "https://<account>.services.ai.azure.com/api/projects/<project>. "
            "Only Azure public-cloud HTTPS project endpoints are supported."
        )
    return endpoint


def build_voice_config(voice: str) -> dict[str, str]:
    """Classify the voice using the upstream descriptor; writes use flat fields."""
    return {"type": "openai" if "-" not in voice else "azure-standard", "name": voice}


@dataclass
class AgentsConfig:
    host: str
    account: str = field(init=False)
    project: str = field(init=False)
    subscription: str = ""
    resource_group: str = ""
    api_version: str = "v1"
    voice_model: str = "gpt-realtime"
    voice: str = DEFAULT_AZURE_VOICE
    _credential: Any = field(default=None, repr=False)
    _token: str | None = field(default=None, repr=False)
    _token_expires_on: float = field(default=0, repr=False)
    _lock: Any = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        self.host = validate_project_endpoint(self.host)
        parts = urlsplit(self.host)
        self.account = parts.hostname.split(".", 1)[0]
        self.project = parts.path.rsplit("/", 1)[-1]

    @classmethod
    def from_endpoint(cls, endpoint: str | None = None) -> AgentsConfig:
        return cls(
            host=endpoint if endpoint is not None else os.getenv("AZURE_VOICE_AGENTS_ENDPOINT", ""),
            voice_model=os.getenv("AZURE_VOICE_AGENTS_MODEL", "gpt-realtime"),
            voice=os.getenv("AZURE_VOICE_AGENTS_VOICE", DEFAULT_AZURE_VOICE),
            subscription=os.getenv("AZURE_SUBSCRIPTION_ID", ""),
            resource_group=os.getenv("AZURE_RESOURCE_GROUP", ""),
        )

    @property
    def backend(self) -> str:
        """Display the configured project, not a selectable runtime mode."""
        return self.project

    @property
    def agents_base(self) -> str:
        return self.host.rstrip("/")

    @property
    def ws_agents_base(self) -> str:
        return self.agents_base.replace("https://", "wss://", 1).replace("http://", "ws://", 1)

    def get_token(self, refresh: bool = False) -> str:
        with self._lock:
            if refresh or self._token is None or time.time() >= self._token_expires_on - 300:
                if self._credential is None:
                    self._credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
                token = self._credential.get_token(TOKEN_SCOPE)
                self._token = token.token
                self._token_expires_on = float(token.expires_on)
        return self._token

    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.get_token()}"}

    def ws_headers(self) -> dict[str, str]:
        return {**self.auth_headers(), "Foundry-Features": FOUNDRY_FEATURES}

    def rest_headers(self) -> dict[str, str]:
        return {**self.ws_headers(), "Accept": "application/json", "Content-Type": "application/json"}

    def agent_url(self, name: str) -> str:
        return f"{self.agents_base}/agents/{quote(name, safe='')}?api-version={self.api_version}"

    def close(self) -> None:
        if self._credential is not None:
            self._credential.close()


def list_byom_deployments(cfg: AgentsConfig) -> dict[str, Any]:
    """No implicit management-plane access; users supply their deployment names."""
    return {
        "realtime": [
            {"deployment": name, "model": None}
            for name in deployment_names("VOICE_PORTAL_REALTIME_DEPLOYMENTS")
        ],
        "cascaded": [
            {"deployment": name, "model": None}
            for name in deployment_names("VOICE_PORTAL_CASCADED_DEPLOYMENTS")
        ],
        "account": cfg.account,
        "source": "environment",
    }
