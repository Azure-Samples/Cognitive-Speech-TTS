from __future__ import annotations

import os


# Agent-server imports configure OpenTelemetry for hosted runs. Unit tests don't
# export telemetry or probe the Azure instance-metadata endpoint.
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("AZURE_MONITOR_DISABLE_STATSBEAT", "true")
