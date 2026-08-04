"""Download Application Insights tracing for a voice conversation id."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

import requests
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

LOG_ANALYTICS_SCOPE = "https://api.loganalytics.io/.default"
LOG_ANALYTICS_RESOURCE_QUERY_BASE = "https://api.loganalytics.azure.com/v1"
TRACE_LOOKBACK = "7d"
TRACE_TIMEOUT_SECONDS = 300
TRACE_POLL_SECONDS = 10


def required_env(name: str) -> str:
    """Return a required environment variable or raise a clear error."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name} before running this sample.")
    return value


def build_trace_query(conversation_id: str) -> str:
    """Build KQL that finds and expands the conversation's trace operation."""
    conversation = json.dumps(conversation_id)

    return "\n".join(
        [
            f"let conversationId = {conversation};",
            "let matchingOperations =",
            "    union requests, dependencies, traces, exceptions",
            f"    | where timestamp > ago({TRACE_LOOKBACK})",
            "    | where tostring(",
            '        customDimensions["gen_ai.conversation.id"]',
            "      ) == conversationId",
            "    | distinct operation_Id;",
            "union withsource=TableName",
            "    requests, dependencies, traces, exceptions",
            f"| where timestamp > ago({TRACE_LOOKBACK})",
            "| where operation_Id in (matchingOperations)",
            "| project TimeGenerated=timestamp, TableName,",
            "          OperationId=operation_Id, ParentId=operation_ParentId,",
            "          Id=id, Name=name, Success=success,",
            "          ResultCode=resultCode, Duration=duration,",
            "          AppRoleName=cloud_RoleName,",
            "          Properties=customDimensions,",
            "          Measurements=customMeasurements",
            "| order by TimeGenerated asc",
        ]
    )


def parse_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert the Log Analytics table response into named JSON rows."""
    tables = payload.get("tables") or []
    if not tables:
        return []
    table = tables[0]
    columns = [
        str(column.get("name") or f"column_{index}")
        for index, column in enumerate(table.get("columns") or [])
    ]
    rows: list[dict[str, Any]] = []
    for values in table.get("rows") or []:
        row = {
            column: values[index] if index < len(values) else None
            for index, column in enumerate(columns)
        }
        for field in ("Properties", "Measurements"):
            value = row.get(field)
            if isinstance(value, str):
                try:
                    row[field] = json.loads(value)
                except json.JSONDecodeError:
                    pass
        rows.append(row)
    return rows


def query_traces(
    resource_id: str,
    query: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    """Poll Application Insights until matching trace rows are available."""
    query_url = (
        f"{LOG_ANALYTICS_RESOURCE_QUERY_BASE}"
        f"{resource_id.rstrip('/')}/query"
    )
    deadline = time.monotonic() + TRACE_TIMEOUT_SECONDS
    attempts = 0
    last_payload: dict[str, Any] = {}

    with DefaultAzureCredential() as credential:
        token = credential.get_token(LOG_ANALYTICS_SCOPE).token
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        while True:
            attempts += 1
            response = requests.post(
                query_url,
                headers=headers,
                json={"query": query},
                timeout=60,
            )
            try:
                payload = response.json()
            except ValueError:
                payload = {"raw_response": response.text[:2000]}
            if isinstance(payload, dict):
                last_payload = payload

            if response.ok:
                rows = parse_rows(last_payload)
                if rows:
                    return last_payload, rows, attempts
            elif response.status_code not in {429, 500, 502, 503, 504}:
                raise RuntimeError(
                    "Application Insights query failed "
                    f"({response.status_code}): {str(payload)[:1000]}"
                )

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    "Application Insights did not contain traces for the "
                    f"conversation within {TRACE_TIMEOUT_SECONDS} seconds."
                )
            time.sleep(min(TRACE_POLL_SECONDS, remaining))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "conversation_id",
        help="Persisted conversation id.",
    )
    args = parser.parse_args()

    conversation_id = args.conversation_id.strip()
    app_insights_resource_id = required_env(
        "AZURE_VOICE_AGENTS_APP_INSIGHTS_RESOURCE_ID"
    )
    query = build_trace_query(conversation_id)

    output_dir = (
        Path(os.getenv("AZURE_VOICE_AGENTS_OUTPUT_DIR", "voice-agent-output"))
        / conversation_id
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    query_path = output_dir / "trace-query.kql"
    query_path.write_text(query + "\n", encoding="utf-8")

    payload, rows, attempts = query_traces(
        app_insights_resource_id,
        query,
    )
    result = {
        "conversation_id": conversation_id,
        "app_insights_resource_id": app_insights_resource_id,
        "attempts": attempts,
        "rows": rows,
        "raw_response": payload,
    }
    output_path = output_dir / "traces.json"
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Downloaded {len(rows)} trace row(s).")
    print(f"Saved query: {query_path.resolve()}")
    print(f"Saved traces: {output_path.resolve()}")


if __name__ == "__main__":
    main()
