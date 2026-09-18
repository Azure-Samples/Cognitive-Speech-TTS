"""Environment configuration helpers for the SDK sample."""

from __future__ import annotations

import os
from urllib.parse import urlsplit


def project_endpoint_from_env() -> str:
    endpoint = os.environ.get("PROJECT_ENDPOINT", "").strip().rstrip("/")
    parsed = urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("PROJECT_ENDPOINT must be a valid HTTPS endpoint")
    return endpoint


def required_env(name: str, default: str = "") -> str:
    value = os.environ.get(name, default).strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value
