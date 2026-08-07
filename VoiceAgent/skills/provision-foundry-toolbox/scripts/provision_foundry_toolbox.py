#!/usr/bin/env python3
"""Create a Foundry Toolbox with Azure AI Search over local documents."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import sys
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, urlparse

import requests
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AISearchIndexResource,
    AzureAISearchToolboxTool,
    AzureAISearchToolResource,
)
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.identity import AzureCliCredential
from dotenv import dotenv_values

VOICE_AGENT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENV_FILE = VOICE_AGENT_ROOT / "samples" / ".env"
DEFAULT_DOCS_DIR = VOICE_AGENT_ROOT / "samples" / "sample_foundry_iq_doc"

SEARCH_SCOPE = "https://search.azure.com/.default"
SEARCH_API_VERSION = "2024-07-01"
SUPPORTED_SUFFIXES = {".html", ".htm", ".json", ".md", ".txt"}
MAX_CHUNK_CHARACTERS = 6_000
CHUNK_OVERLAP_CHARACTERS = 400


class ProvisioningError(RuntimeError):
    """A Toolbox or Search provisioning operation failed."""


@dataclass(frozen=True)
class ProvisioningNames:
    toolbox: str
    index: str
    tool: str


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def resource_name(value: str, *, max_length: int = 64) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not normalized:
        normalized = "foundry-toolbox"
    if not normalized[0].isalpha():
        normalized = f"toolbox-{normalized}"
    return normalized[:max_length].rstrip("-")


def new_names(docs_dir: Path, requested_name: str | None) -> ProvisioningNames:
    if requested_name:
        toolbox_name = resource_name(requested_name)
    else:
        suffix = f"{time.strftime('%Y%m%d')}-{secrets.token_hex(3)}"
        toolbox_name = resource_name(f"{docs_dir.name}-toolbox-{suffix}")
    return ProvisioningNames(
        toolbox=toolbox_name,
        index=resource_name(f"{toolbox_name}-index", max_length=120),
        tool="document_search",
    )


def discover_documents(root: Path) -> list[Path]:
    if not root.is_dir():
        raise ValueError(f"Document directory does not exist: {root}")
    documents = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and not any(part.startswith(".") for part in path.parts)
    )
    unsupported = [
        str(path.relative_to(root))
        for path in documents
        if path.suffix.lower() not in SUPPORTED_SUFFIXES
    ]
    if unsupported:
        raise ValueError("Unsupported documents: " + ", ".join(unsupported))
    if not documents:
        raise ValueError(f"No supported documents found under {root}")
    return documents


def read_document(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        text = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
    elif path.suffix.lower() in {".html", ".htm"}:
        extractor = _HTMLTextExtractor()
        extractor.feed(text)
        text = "\n".join(extractor.parts)
    return text.strip()


def document_title(path: Path, text: str) -> str:
    for line in text.splitlines():
        heading = re.match(r"^#\s+(.+)$", line.strip())
        if heading:
            return heading.group(1).strip()
    return path.stem.replace("-", " ").replace("_", " ").strip()


def split_text(
    text: str,
    *,
    max_characters: int = MAX_CHUNK_CHARACTERS,
    overlap_characters: int = CHUNK_OVERLAP_CHARACTERS,
) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + max_characters, len(normalized))
        if end < len(normalized):
            minimum_boundary = start + max_characters // 2
            paragraph_boundary = normalized.rfind("\n\n", minimum_boundary, end)
            line_boundary = normalized.rfind("\n", minimum_boundary, end)
            boundary = max(paragraph_boundary, line_boundary)
            if boundary > start:
                end = boundary
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(start + 1, end - overlap_characters)
    return chunks


def build_search_documents(root: Path, paths: Iterable[Path]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for path in paths:
        relative_path = path.relative_to(root).as_posix()
        text = read_document(path)
        chunks = split_text(text)
        if not chunks:
            raise ValueError(f"Document is empty: {relative_path}")
        title = document_title(path, text)
        for chunk_number, content in enumerate(chunks, start=1):
            digest = hashlib.sha256(
                f"{relative_path}:{chunk_number}".encode("utf-8")
            ).hexdigest()
            documents.append(
                {
                    "uid": digest,
                    "title": title,
                    "source_path": relative_path,
                    "chunk_number": chunk_number,
                    "content": content,
                }
            )
    return documents


def connection_type_value(connection: Any) -> str:
    value = getattr(connection.type, "value", connection.type)
    return re.sub(r"[^a-z]", "", str(value).lower())


def select_search_connection(
    project_client: AIProjectClient, requested_name: str | None
) -> Any:
    candidates = []
    for connection in project_client.connections.list():
        parsed = urlparse(connection.target or "")
        if (
            connection_type_value(connection) in {"azureaisearch", "cognitivesearch"}
            and parsed.hostname
            and parsed.hostname.endswith(".search.windows.net")
        ):
            candidates.append(connection)
    if requested_name:
        candidates = [item for item in candidates if item.name == requested_name]
    if len(candidates) != 1:
        names = [item.name for item in candidates]
        raise ProvisioningError(
            "Expected exactly one Azure AI Search project connection. "
            f"Candidates: {names or 'none'}. Use --search-connection-name."
        )
    return candidates[0]


def response_body(response: requests.Response) -> str:
    body = response.text.strip()
    return body[:3_000] + ("..." if len(body) > 3_000 else "")


class SearchIndexClient:
    def __init__(
        self,
        *,
        endpoint: str,
        credential: AzureCliCredential,
        timeout_seconds: float = 120,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.credential = credential
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any | None = None,
        expected: set[int] | None = None,
        max_attempts: int = 1,
        retry_statuses: set[int] | None = None,
    ) -> requests.Response:
        accepted = expected or set(range(200, 300))
        retryable = retry_statuses or {429}
        separator = "&" if "?" in path else "?"
        url = f"{self.endpoint}{path}{separator}api-version={SEARCH_API_VERSION}"
        for attempt in range(1, max_attempts + 1):
            token = self.credential.get_token(SEARCH_SCOPE).token
            response = self.session.request(
                method,
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=json_body,
                timeout=self.timeout_seconds,
            )
            if response.status_code in accepted:
                return response
            if response.status_code in retryable and attempt < max_attempts:
                retry_after = response.headers.get("Retry-After", "")
                wait_seconds = int(retry_after) if retry_after.isdigit() else 0
                time.sleep(max(wait_seconds, min(30, 2**attempt)))
                continue
            raise ProvisioningError(
                f"{method} {url} failed with HTTP {response.status_code}: "
                f"{response_body(response)}"
            )
        raise AssertionError("unreachable")

    def list_index_names(self) -> set[str]:
        response = self.request("GET", "/indexes?$select=name")
        return {item["name"] for item in response.json().get("value", [])}

    def create_index(self, name: str) -> None:
        fields = [
            {
                "name": "uid",
                "type": "Edm.String",
                "key": True,
                "filterable": True,
                "sortable": True,
            },
            {
                "name": "title",
                "type": "Edm.String",
                "searchable": True,
                "retrievable": True,
            },
            {
                "name": "source_path",
                "type": "Edm.String",
                "searchable": True,
                "filterable": True,
                "retrievable": True,
            },
            {
                "name": "chunk_number",
                "type": "Edm.Int32",
                "filterable": True,
                "sortable": True,
                "retrievable": True,
            },
            {
                "name": "content",
                "type": "Edm.String",
                "searchable": True,
                "retrievable": True,
            },
        ]
        self.request(
            "PUT",
            f"/indexes/{quote(name, safe='')}",
            json_body={"name": name, "fields": fields},
            expected={200, 201},
        )

    def upload_documents(self, index_name: str, documents: list[dict[str, Any]]) -> None:
        for batch_start in range(0, len(documents), 500):
            batch = documents[batch_start : batch_start + 500]
            actions = [
                {"@search.action": "upload", **document} for document in batch
            ]
            response = self.request(
                "POST",
                f"/indexes/{quote(index_name, safe='')}/docs/index",
                json_body={"value": actions},
                expected={200, 207},
                max_attempts=8,
                retry_statuses={404, 429, 503},
            )
            failed = [
                item
                for item in response.json().get("value", [])
                if not item.get("status")
            ]
            if failed:
                raise ProvisioningError(
                    "Search rejected document uploads: "
                    + json.dumps(failed, ensure_ascii=False)[:3_000]
                )

    def wait_for_document_count(
        self, index_name: str, expected_count: int, timeout_seconds: float
    ) -> int:
        deadline = time.monotonic() + timeout_seconds
        while True:
            response = self.request(
                "GET", f"/indexes/{quote(index_name, safe='')}/docs/$count"
            )
            count = int(response.text)
            if count == expected_count:
                return count
            if time.monotonic() >= deadline:
                raise ProvisioningError(
                    f"Timed out waiting for {expected_count} indexed chunks; "
                    f"Search reports {count}."
                )
            time.sleep(2)

    def verify_search(self, index_name: str) -> None:
        response = self.request(
            "POST",
            f"/indexes/{quote(index_name, safe='')}/docs/search",
            json_body={"search": "*", "top": 1, "select": "uid,title,source_path"},
        )
        if not response.json().get("value"):
            raise ProvisioningError("The new Search index returned no documents.")


def toolbox_uses_index(version: Any, connection_id: str, index_name: str) -> bool:
    for tool in version.tools or []:
        search = getattr(tool, "azure_ai_search", None)
        for index in getattr(search, "indexes", []) or []:
            if (
                index.project_connection_id == connection_id
                and index.index_name == index_name
            ):
                return True
    return False


def update_env_file(path: Path, values: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = text.splitlines()
    seen: set[str] = set()
    for line_number, line in enumerate(lines):
        for key, value in values.items():
            if re.match(rf"^{re.escape(key)}=", line):
                lines[line_number] = f"{key}={value}"
                seen.add(key)
    for key, value in values.items():
        if key not in seen:
            lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-dir", type=Path, default=DEFAULT_DOCS_DIR)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--name", help="New Toolbox name; defaults to a unique name.")
    parser.add_argument("--search-connection-name")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--indexing-timeout-seconds", type=float, default=120)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--update-env", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.top_k < 1:
            raise ValueError("--top-k must be at least 1.")
        env = dotenv_values(args.env_file)
        project_endpoint = env.get("AZURE_VOICE_AGENTS_ENDPOINT")
        if not project_endpoint:
            raise ValueError(
                f"AZURE_VOICE_AGENTS_ENDPOINT is missing from {args.env_file}."
            )
        documents = discover_documents(args.docs_dir)
        search_documents = build_search_documents(args.docs_dir, documents)
        names = new_names(args.docs_dir, args.name)

        credential = AzureCliCredential()
        with credential, AIProjectClient(
            endpoint=project_endpoint,
            credential=credential,
            allow_preview=True,
        ) as project_client:
            connection = select_search_connection(
                project_client, args.search_connection_name
            )
            search_client = SearchIndexClient(
                endpoint=connection.target,
                credential=credential,
            )
            existing_indexes = search_client.list_index_names()
            if names.index in existing_indexes:
                raise ProvisioningError(
                    f"Search index {names.index!r} already exists. Choose a new --name."
                )
            try:
                project_client.toolboxes.get(names.toolbox)
            except ResourceNotFoundError:
                pass
            else:
                raise ProvisioningError(
                    f"Toolbox {names.toolbox!r} already exists. Choose a new --name."
                )

            plan = {
                "dry_run": args.dry_run,
                "project_endpoint": project_endpoint,
                "document_folder": str(args.docs_dir.resolve()),
                "source_documents": len(documents),
                "search_chunks": len(search_documents),
                "search_connection": connection.name,
                "search_index": names.index,
                "toolbox_name": names.toolbox,
                "expected_toolbox_version": "1",
            }
            print(json.dumps(plan, indent=2))
            if args.dry_run:
                return 0

            search_client.create_index(names.index)
            search_client.upload_documents(names.index, search_documents)
            indexed_count = search_client.wait_for_document_count(
                names.index,
                len(search_documents),
                args.indexing_timeout_seconds,
            )
            search_client.verify_search(names.index)
            print(f"Search index ready: {names.index} ({indexed_count} chunks)")

            tool = AzureAISearchToolboxTool(
                name=names.tool,
                description="Search the documents supplied with the Voice Agent sample.",
                azure_ai_search=AzureAISearchToolResource(
                    indexes=[
                        AISearchIndexResource(
                            project_connection_id=connection.id,
                            index_name=names.index,
                            query_type="simple",
                            top_k=args.top_k,
                        )
                    ]
                ),
            )
            created = project_client.toolboxes.create_version(
                name=names.toolbox,
                description=(
                    "Azure AI Search Toolbox over the Voice Agent sample documents."
                ),
                tools=[tool],
                metadata={
                    "source": "sample_foundry_iq_doc",
                    "search_index": names.index,
                },
            )
            verified = project_client.toolboxes.get_version(
                name=created.name,
                version=created.version,
            )
            if not toolbox_uses_index(verified, connection.id, names.index):
                raise ProvisioningError(
                    "The created Toolbox version does not reference the new Search index."
                )
            print(f"Toolbox ready: {created.name} version {created.version}")

            outputs = {
                "AZURE_VOICE_AGENTS_TOOLBOX_NAME": created.name,
                "AZURE_VOICE_AGENTS_TOOLBOX_VERSION": created.version,
            }
            if args.update_env:
                update_env_file(args.env_file, outputs)
                print(f"Updated {args.env_file}")
            for key, value in outputs.items():
                print(f"{key}={value}")
        return 0
    except (
        OSError,
        ValueError,
        ProvisioningError,
        HttpResponseError,
        requests.RequestException,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())