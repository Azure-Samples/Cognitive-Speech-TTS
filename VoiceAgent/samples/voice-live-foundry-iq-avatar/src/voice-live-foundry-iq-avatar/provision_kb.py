# Copyright (c) Microsoft. All rights reserved.

"""Create the Azure AI Search resources used by this sample's knowledge base."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import requests
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

SEARCH_SCOPE = "https://search.azure.com/.default"
API_VERSION = "2026-08-01-preview"
SEMANTIC_CONFIG_NAME = "default-semantic-config"
DOCUMENTS_PATH = Path(__file__).with_name("knowledge") / "documents.json"
REQUIRED_DOCUMENT_FIELDS = ("id", "title", "content", "source_url")
INDEX_BATCH_SIZE = 1_000
MAX_SYNC_DOCUMENTS = INDEX_BATCH_SIZE


def validate_documents(value: Any) -> list[dict[str, str]]:
    """Validate the small checked-in document corpus."""
    if not isinstance(value, list) or not value:
        raise ValueError("documents.json must contain a non-empty JSON array.")
    if len(value) > MAX_SYNC_DOCUMENTS:
        raise ValueError(
            f"This small-corpus sample supports at most {MAX_SYNC_DOCUMENTS} documents."
        )

    documents: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for position, document in enumerate(value, start=1):
        if not isinstance(document, dict):
            raise ValueError(f"Document {position} must be a JSON object.")
        normalized: dict[str, str] = {}
        for field in REQUIRED_DOCUMENT_FIELDS:
            field_value = document.get(field)
            if not isinstance(field_value, str) or not field_value.strip():
                raise ValueError(
                    f"Document {position} requires a non-empty string '{field}'."
                )
            normalized[field] = field_value.strip()
        if normalized["id"] in seen_ids:
            raise ValueError(f"Duplicate document id: {normalized['id']!r}.")
        seen_ids.add(normalized["id"])
        documents.append(normalized)
    return documents


def load_documents(path: Path | None = None) -> list[dict[str, str]]:
    configured = os.environ.get("KNOWLEDGE_DOCUMENTS_PATH", "").strip()
    document_path = path or (Path(configured).expanduser() if configured else DOCUMENTS_PATH)
    with document_path.open(encoding="utf-8") as handle:
        return validate_documents(json.load(handle))


def _require(name: str, environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    value = env.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"Required environment variable {name} is not set.")
    return value


class SearchClient:
    def __init__(self, endpoint: str, token: str) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def put(self, path: str, body: dict[str, Any]) -> None:
        response = requests.put(
            f"{self._endpoint}/{path}?api-version={API_VERSION}",
            headers=self._headers,
            json=body,
            timeout=120,
        )
        if response.status_code not in (200, 201, 204):
            raise RuntimeError(
                f"PUT {path} failed ({response.status_code}): {response.text}"
            )

    def post(
        self,
        path: str,
        body: dict[str, Any],
        *,
        allow_not_found: bool = False,
    ) -> dict[str, Any] | None:
        response = requests.post(
            f"{self._endpoint}/{path}?api-version={API_VERSION}",
            headers=self._headers,
            json=body,
            timeout=120,
        )
        if allow_not_found and response.status_code == 404:
            return None
        if response.status_code not in (200, 201, 207):
            raise RuntimeError(
                f"POST {path} failed ({response.status_code}): {response.text}"
            )
        return response.json() if response.content else {}


def create_index(client: SearchClient, index_name: str) -> None:
    print(f"Creating index '{index_name}'...")
    client.put(
        f"indexes/{index_name}",
        {
            "name": index_name,
            "fields": [
                {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
                {"name": "title", "type": "Edm.String", "searchable": True, "retrievable": True},
                {"name": "content", "type": "Edm.String", "searchable": True, "retrievable": True},
                {"name": "source_url", "type": "Edm.String", "retrievable": True},
            ],
            "semantic": {
                "configurations": [
                    {
                        "name": SEMANTIC_CONFIG_NAME,
                        "prioritizedFields": {
                            "titleField": {"fieldName": "title"},
                            "prioritizedContentFields": [{"fieldName": "content"}],
                        },
                    }
                ]
            },
        },
    )


def _document_batches(documents: list[dict[str, Any]]):
    for start in range(0, len(documents), INDEX_BATCH_SIZE):
        yield documents[start : start + INDEX_BATCH_SIZE]


def _check_index_result(result: dict[str, Any], expected_count: int) -> None:
    items = result.get("value")
    if not isinstance(items, list) or len(items) != expected_count:
        raise RuntimeError(
            "Azure AI Search returned an incomplete document indexing result."
        )

    failed = [item for item in items if item.get("status") is not True]
    if not failed:
        return

    details = []
    for item in failed[:5]:
        key = item.get("key", "<unknown>")
        status_code = item.get("statusCode", "unknown")
        message = item.get("errorMessage") or "no error message"
        details.append(f"{key} ({status_code}): {message}")
    suffix = "" if len(failed) <= 5 else f"; plus {len(failed) - 5} more"
    raise RuntimeError(
        f"Azure AI Search rejected {len(failed)} document(s): "
        + "; ".join(details)
        + suffix
    )


def list_document_ids(
    client: SearchClient,
    index_name: str,
    *,
    allow_not_found: bool = False,
) -> set[str]:
    result = client.post(
        f"indexes/{index_name}/docs/search",
        {
            "search": "*",
            "select": "id",
            "count": True,
            "top": MAX_SYNC_DOCUMENTS,
        },
        allow_not_found=allow_not_found,
    )
    if result is None:
        return set()
    count = result.get("@odata.count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise RuntimeError("Azure AI Search returned an invalid document count.")
    if count > MAX_SYNC_DOCUMENTS:
        raise RuntimeError(
            f"Index contains {count} documents; this small-corpus sample synchronizes "
            f"at most {MAX_SYNC_DOCUMENTS}. Use a dedicated sample index."
        )

    values = result.get("value", [])
    if not isinstance(values, list) or len(values) != count:
        raise RuntimeError("Azure AI Search returned an incomplete document list.")
    document_ids = {
        item.get("id") for item in values if isinstance(item, dict)
    }
    if None in document_ids or "" in document_ids or len(document_ids) != count:
        raise RuntimeError("Azure AI Search returned invalid or duplicate document IDs.")
    return document_ids


def delete_documents(client: SearchClient, index_name: str, document_ids: set[str]) -> None:
    if not document_ids:
        return
    print(f"Deleting {len(document_ids)} stale document(s) from '{index_name}'...")
    documents = [
        {"@search.action": "delete", "id": document_id}
        for document_id in sorted(document_ids)
    ]
    for batch in _document_batches(documents):
        result = client.post(f"indexes/{index_name}/docs/index", {"value": batch})
        _check_index_result(result, len(batch))


def upload_documents(
    client: SearchClient,
    index_name: str,
    documents: list[dict[str, str]],
) -> None:
    print(f"Uploading {len(documents)} document(s) to '{index_name}'...")
    actions: list[dict[str, Any]] = [
        {"@search.action": "mergeOrUpload", **document} for document in documents
    ]
    for batch in _document_batches(actions):
        result = client.post(f"indexes/{index_name}/docs/index", {"value": batch})
        _check_index_result(result, len(batch))


def sync_documents(
    client: SearchClient,
    index_name: str,
    documents: list[dict[str, str]],
    *,
    existing_ids: set[str] | None = None,
) -> None:
    if existing_ids is None:
        existing_ids = list_document_ids(client, index_name)
    desired_ids = {document["id"] for document in documents}
    upload_documents(client, index_name, documents)
    delete_documents(client, index_name, existing_ids - desired_ids)


def create_knowledge_source(
    client: SearchClient,
    source_name: str,
    index_name: str,
) -> None:
    print(f"Creating knowledge source '{source_name}'...")
    client.put(
        f"knowledgesources/{source_name}",
        {
            "name": source_name,
            "kind": "searchIndex",
            "searchIndexParameters": {
                "searchIndexName": index_name,
                "semanticConfigurationName": SEMANTIC_CONFIG_NAME,
                "sourceDataFields": [
                    {"name": "title"},
                    {"name": "content"},
                    {"name": "source_url"},
                ],
                "searchFields": [],
            },
        },
    )


def create_knowledge_base(
    client: SearchClient,
    kb_name: str,
    source_name: str,
) -> None:
    print(f"Creating knowledge base '{kb_name}'...")
    client.put(
        f"knowledgebases/{kb_name}",
        {
            "name": kb_name,
            "description": "Earth-at-night knowledge for the Voice Live sample.",
            "knowledgeSources": [{"name": source_name}],
            "outputMode": "extractiveData",
            "retrievalReasoningEffort": {"kind": "minimal"},
        },
    )


def _set_azd_env(name: str, value: str) -> bool:
    azd = shutil.which("azd")
    if not azd:
        return False
    try:
        subprocess.run([azd, "env", "set", name, value], check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-azd-env",
        action="store_true",
        help="Fail unless KB_MCP_ENDPOINT is stored in the active azd environment.",
    )
    args = parser.parse_args(argv)

    load_dotenv(override=False)
    try:
        endpoint = _require("AZURE_SEARCH_ENDPOINT").rstrip("/")
        index_name = os.environ.get("AZURE_SEARCH_INDEX_NAME", "").strip() or "voice-live-night-index"
        source_name = os.environ.get("KNOWLEDGE_SOURCE_NAME", "").strip() or "voice-live-night-source"
        kb_name = os.environ.get("KNOWLEDGE_BASE_NAME", "").strip() or "voice-live-night-kb"
        documents = load_documents()

        credential = DefaultAzureCredential()
        try:
            token = credential.get_token(SEARCH_SCOPE).token
        finally:
            credential.close()
        client = SearchClient(endpoint, token)
        existing_ids = list_document_ids(
            client,
            index_name,
            allow_not_found=True,
        )
        create_index(client, index_name)
        sync_documents(
            client,
            index_name,
            documents,
            existing_ids=existing_ids,
        )
        create_knowledge_source(client, source_name, index_name)
        create_knowledge_base(client, kb_name, source_name)

        mcp_endpoint = (
            f"{endpoint}/knowledgebases/{kb_name}/mcp?api-version={API_VERSION}"
        )
        print(f"Knowledge base '{kb_name}' is ready.")
        print(f"MCP endpoint: {mcp_endpoint}")
        if _set_azd_env("KB_MCP_ENDPOINT", mcp_endpoint):
            print("Stored KB_MCP_ENDPOINT in the active azd environment.")
        elif args.require_azd_env:
            raise RuntimeError(
                "Could not store KB_MCP_ENDPOINT in the active azd environment."
            )
        else:
            print(f'Run: azd env set KB_MCP_ENDPOINT "{mcp_endpoint}"')
        return 0
    except (EnvironmentError, OSError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
