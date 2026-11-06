#!/usr/bin/env python3
"""Provision a Foundry IQ knowledge base from a local document folder."""

from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import requests
from azure.identity import AzureCliCredential
from dotenv import dotenv_values

VOICE_AGENT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENV_FILE = VOICE_AGENT_ROOT / "samples" / ".env"
DEFAULT_DOCS_DIR = VOICE_AGENT_ROOT / "samples" / "sample_foundry_iq_doc"

ARM_SCOPE = "https://management.azure.com/.default"
SEARCH_SCOPE = "https://search.azure.com/.default"
ARM_BASE = "https://management.azure.com"
RESOURCE_GRAPH_API_VERSION = "2024-04-01"
SUBSCRIPTIONS_API_VERSION = "2022-12-01"
COGNITIVE_API_VERSION = "2024-10-01"
PROJECT_API_VERSION = "2025-04-01-preview"
CONNECTION_API_VERSION = "2025-04-01-preview"
SEARCH_API_VERSION = "2026-05-01-preview"
ROLE_ASSIGNMENT_API_VERSION = "2022-04-01"
SEARCH_INDEX_DATA_READER_ROLE_ID = "1407120a-92aa-4202-b7e9-c0e197c71c8f"

SUPPORTED_SUFFIXES = {
    ".docx",
    ".html",
    ".htm",
    ".json",
    ".md",
    ".pdf",
    ".pptx",
    ".txt",
}
EMBEDDING_MODEL = "text-embedding-3-small"
RETRIEVAL_MODEL = "gpt-4.1-mini"
PREFERRED_RETRIEVAL_MODELS = (RETRIEVAL_MODEL,)


class ProvisioningError(RuntimeError):
    """A provisioning operation failed."""


@dataclass(frozen=True)
class FoundryEndpoint:
    account_name: str
    project_name: str


@dataclass(frozen=True)
class Deployment:
    name: str
    model_name: str


@dataclass(frozen=True)
class ProvisioningNames:
    knowledge_base: str
    knowledge_source: str
    connection: str


def parse_foundry_endpoint(value: str) -> FoundryEndpoint:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("AZURE_VOICE_AGENTS_ENDPOINT must be an HTTPS URL.")
    host_suffix = ".services.ai.azure.com"
    if not parsed.hostname.endswith(host_suffix):
        raise ValueError(
            "AZURE_VOICE_AGENTS_ENDPOINT must use a services.ai.azure.com host."
        )
    account_name = parsed.hostname[: -len(host_suffix)]
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) != 3 or path_parts[:2] != ["api", "projects"]:
        raise ValueError(
            "AZURE_VOICE_AGENTS_ENDPOINT must end in /api/projects/<project>."
        )
    return FoundryEndpoint(account_name=account_name, project_name=path_parts[2])


def resource_name(value: str, *, max_length: int = 48) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not normalized:
        normalized = "foundry-iq"
    if not normalized[0].isalpha():
        normalized = f"iq-{normalized}"
    return normalized[:max_length].rstrip("-")


def new_names(docs_dir: Path, requested_name: str | None) -> ProvisioningNames:
    if requested_name:
        knowledge_base = resource_name(requested_name)
    else:
        suffix = f"{time.strftime('%Y%m%d')}-{secrets.token_hex(3)}"
        knowledge_base = resource_name(f"{docs_dir.name}-{suffix}")
    return ProvisioningNames(
        knowledge_base=knowledge_base,
        knowledge_source=resource_name(f"ks-{knowledge_base}", max_length=64),
        connection=resource_name(f"kb-{knowledge_base}", max_length=64),
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


def uploaded_file_name(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix().replace("/", "__")


def response_body(response: requests.Response) -> str:
    body = response.text.strip()
    return body[:3000] + ("..." if len(body) > 3000 else "")


class AzureClient:
    def __init__(self, *, timeout_seconds: float = 120) -> None:
        self.timeout_seconds = timeout_seconds
        self.credential = AzureCliCredential()
        self.session = requests.Session()
        self._tokens: dict[str, str] = {}

    def token(self, scope: str) -> str:
        if scope not in self._tokens:
            self._tokens[scope] = self.credential.get_token(scope).token
        return self._tokens[scope]

    def request(
        self,
        method: str,
        url: str,
        *,
        scope: str = ARM_SCOPE,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        data: bytes | None = None,
        expected: set[int] | None = None,
        max_attempts: int = 1,
    ) -> requests.Response:
        accepted = expected or set(range(200, 300))
        for attempt in range(1, max_attempts + 1):
            request_headers = {
                "Authorization": f"Bearer {self.token(scope)}",
                "Accept": "application/json",
            }
            if headers:
                request_headers.update(headers)
            response = self.session.request(
                method,
                url,
                headers=request_headers,
                json=json_body,
                data=data,
                timeout=self.timeout_seconds,
            )
            if response.status_code in accepted:
                return response
            if response.status_code == 429 and attempt < max_attempts:
                retry_after = response.headers.get("Retry-After", "")
                wait_seconds = int(retry_after) if retry_after.isdigit() else 0
                time.sleep(max(wait_seconds, min(60, 2**attempt)))
                continue
            raise ProvisioningError(
                f"{method} {url} failed with HTTP {response.status_code}: "
                f"{response_body(response)}"
            )
        raise AssertionError("unreachable")

    def json(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        response = self.request(method, url, **kwargs)
        return response.json() if response.content else {}


class ArmProvisioner:
    def __init__(self, client: AzureClient) -> None:
        self.client = client

    def enabled_subscription_ids(self) -> list[str]:
        url = f"{ARM_BASE}/subscriptions?api-version={SUBSCRIPTIONS_API_VERSION}"
        body = self.client.json("GET", url)
        subscription_ids = [
            item["subscriptionId"]
            for item in body.get("value", [])
            if item.get("state") == "Enabled"
        ]
        if not subscription_ids:
            raise ProvisioningError("No enabled Azure subscriptions are visible.")
        return subscription_ids

    def query_resources(
        self, subscription_ids: list[str], resource_type: str, name: str
    ) -> list[dict[str, Any]]:
        escaped_name = name.replace("'", "''")
        escaped_type = resource_type.replace("'", "''")
        query = (
            "resources "
            f"| where type =~ '{escaped_type}' and name =~ '{escaped_name}' "
            "| project id, name, resourceGroup, subscriptionId, location, kind"
        )
        url = (
            f"{ARM_BASE}/providers/Microsoft.ResourceGraph/resources"
            f"?api-version={RESOURCE_GRAPH_API_VERSION}"
        )
        body = self.client.json(
            "POST",
            url,
            headers={"Content-Type": "application/json"},
            json_body={
                "subscriptions": subscription_ids,
                "query": query,
                "options": {"resultFormat": "objectArray"},
            },
        )
        return body.get("data") or []

    def find_resource(
        self, subscription_ids: list[str], resource_type: str, name: str
    ) -> dict[str, Any]:
        resources = self.query_resources(subscription_ids, resource_type, name)
        if len(resources) != 1:
            raise ProvisioningError(
                f"Expected one {resource_type} resource named {name!r}; "
                f"found {len(resources)}."
            )
        return resources[0]

    def get_project(self, account_id: str, project_name: str) -> dict[str, Any]:
        url = (
            f"{ARM_BASE}{account_id}/projects/{quote(project_name, safe='')}"
            f"?api-version={PROJECT_API_VERSION}"
        )
        return self.client.json("GET", url)

    def list_connections(self, account_id: str) -> list[dict[str, Any]]:
        url = (
            f"{ARM_BASE}{account_id}/connections"
            f"?api-version={CONNECTION_API_VERSION}"
        )
        return self.client.json("GET", url).get("value") or []

    def select_search_connection(
        self, connections: list[dict[str, Any]], requested_name: str | None
    ) -> tuple[dict[str, Any], str]:
        candidates: list[tuple[dict[str, Any], str]] = []
        for connection in connections:
            properties = connection.get("properties") or {}
            target = properties.get("target") or ""
            parsed = urlparse(target)
            if (
                str(properties.get("category", "")).lower() == "cognitivesearch"
                and parsed.hostname
                and parsed.hostname.endswith(".search.windows.net")
            ):
                candidates.append((connection, parsed.hostname.split(".")[0]))
        if requested_name:
            candidates = [
                item
                for item in candidates
                if item[0].get("name", "").split("/")[-1] == requested_name
            ]
        if len(candidates) != 1:
            names = [item[0].get("name", "").split("/")[-1] for item in candidates]
            raise ProvisioningError(
                "Expected exactly one Azure AI Search connection. "
                f"Candidates: {names or 'none'}. Use --search-connection-name."
            )
        return candidates[0]

    def list_deployments(self, account_id: str) -> list[Deployment]:
        url = (
            f"{ARM_BASE}{account_id}/deployments"
            f"?api-version={COGNITIVE_API_VERSION}"
        )
        items = self.client.json("GET", url).get("value") or []
        deployments = []
        for item in items:
            model = (item.get("properties") or {}).get("model") or {}
            name = str(item.get("name", "")).split("/")[-1]
            if name and model.get("name"):
                deployments.append(Deployment(name=name, model_name=model["name"]))
        return deployments

    def model_catalog(self, account: dict[str, Any]) -> list[dict[str, Any]]:
        url = (
            f"{ARM_BASE}/subscriptions/{account['subscriptionId']}"
            "/providers/Microsoft.CognitiveServices"
            f"/locations/{quote(account['location'], safe='')}/models"
            f"?api-version={COGNITIVE_API_VERSION}"
        )
        return self.client.json("GET", url).get("value") or []

    def model_deployment_spec(
        self,
        *,
        model_name: str,
        catalog: list[dict[str, Any]],
        sku_name: str,
        capacity: int | None,
    ) -> tuple[dict[str, Any], int]:
        offerings = [
            item.get("model") or {}
            for item in catalog
            if (item.get("model") or {}).get("name") == model_name
        ]
        defaults = [item for item in offerings if item.get("isDefaultVersion")]
        model = (defaults or offerings or [None])[0]
        if not model:
            raise ProvisioningError(
                f"Model {model_name!r} is not available in the Foundry region."
            )
        skus = [item for item in model.get("skus", []) if item.get("name") == sku_name]
        if not skus:
            available = sorted({item.get("name") for item in model.get("skus", [])})
            raise ProvisioningError(
                f"SKU {sku_name!r} is unavailable for {model_name!r}. "
                f"Available SKUs: {available}"
            )
        selected_capacity = capacity or (skus[0].get("capacity") or {}).get("default")
        if not selected_capacity:
            raise ProvisioningError(
                f"No default capacity is published for {model_name!r}/{sku_name!r}; "
                "provide --model-capacity."
            )
        return model, selected_capacity

    def create_model_deployment(
        self,
        *,
        account_id: str,
        deployment_name: str,
        model_name: str,
        catalog: list[dict[str, Any]],
        sku_name: str,
        capacity: int | None,
    ) -> Deployment:
        model, selected_capacity = self.model_deployment_spec(
            model_name=model_name,
            catalog=catalog,
            sku_name=sku_name,
            capacity=capacity,
        )
        url = (
            f"{ARM_BASE}{account_id}/deployments/{quote(deployment_name, safe='')}"
            f"?api-version={COGNITIVE_API_VERSION}"
        )
        self.client.request(
            "PUT",
            url,
            headers={"Content-Type": "application/json"},
            json_body={
                "sku": {"name": sku_name, "capacity": selected_capacity},
                "properties": {
                    "model": {
                        "format": model.get("format", "OpenAI"),
                        "name": model_name,
                        "version": model["version"],
                    }
                },
            },
        )
        return Deployment(name=deployment_name, model_name=model_name)

    def get_account_key(self, account_id: str) -> str:
        url = (
            f"{ARM_BASE}{account_id}/listKeys"
            f"?api-version={COGNITIVE_API_VERSION}"
        )
        key = self.client.json("POST", url).get("key1")
        if not key:
            raise ProvisioningError("The Foundry account did not return key1.")
        return key

    def ensure_search_reader_role(
        self, search_resource: dict[str, Any], principal_id: str
    ) -> None:
        scope = search_resource["id"]
        subscription_id = search_resource["subscriptionId"]
        role_definition_id = (
            f"/subscriptions/{subscription_id}"
            "/providers/Microsoft.Authorization/roleDefinitions/"
            f"{SEARCH_INDEX_DATA_READER_ROLE_ID}"
        )
        assignment_id = uuid.uuid5(
            uuid.NAMESPACE_URL, f"{scope}|{principal_id}|{role_definition_id}"
        )
        url = (
            f"{ARM_BASE}{scope}/providers/Microsoft.Authorization"
            f"/roleAssignments/{assignment_id}?api-version={ROLE_ASSIGNMENT_API_VERSION}"
        )
        response = self.client.request(
            "PUT",
            url,
            headers={"Content-Type": "application/json"},
            json_body={
                "properties": {
                    "principalId": principal_id,
                    "principalType": "ServicePrincipal",
                    "roleDefinitionId": role_definition_id,
                }
            },
            expected={200, 201, 409},
        )
        if response.status_code == 409 and "RoleAssignmentExists" not in response.text:
            raise ProvisioningError(
                f"Role assignment failed with HTTP 409: {response_body(response)}"
            )

    def put_connection(
        self,
        *,
        account_id: str,
        connection_name: str,
        knowledge_base_name: str,
        mcp_url: str,
    ) -> dict[str, Any]:
        url = (
            f"{ARM_BASE}{account_id}/connections/{quote(connection_name, safe='')}"
            f"?api-version={CONNECTION_API_VERSION}"
        )
        return self.client.json(
            "PUT",
            url,
            headers={"Content-Type": "application/json"},
            json_body={
                "properties": {
                    "authType": "ProjectManagedIdentity",
                    "category": "RemoteTool",
                    "group": "GenericProtocol",
                    "isDefault": False,
                    "isSharedToAll": False,
                    "metadata": {
                        "displayName": knowledge_base_name,
                        "knowledgeBaseName": knowledge_base_name,
                        "type": "knowledgeBase_MCP",
                    },
                    "target": mcp_url,
                    "useWorkspaceManagedIdentity": True,
                }
            },
        )


class SearchProvisioner:
    def __init__(self, client: AzureClient, search_service: str) -> None:
        self.client = client
        self.search_service = search_service
        self.base_url = f"https://{search_service}.search.windows.net"

    def knowledge_source_payload(
        self,
        *,
        name: str,
        account_name: str,
        embedding: Deployment,
        account_key: str,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "kind": "file",
            "description": "Local documents provisioned by the Foundry IQ skill.",
            "fileParameters": {
                "ingestionParameters": {
                    "contentExtractionMode": "minimal",
                    "embeddingModel": {
                        "kind": "azureOpenAI",
                        "azureOpenAIParameters": {
                            "resourceUri": f"https://{account_name}.openai.azure.com",
                            "deploymentId": embedding.name,
                            "apiKey": account_key,
                            "modelName": embedding.model_name,
                        },
                    },
                }
            },
        }

    def put_knowledge_source(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = payload["name"]
        url = (
            f"{self.base_url}/knowledgesources/{quote(name, safe='')}"
            f"?api-version={SEARCH_API_VERSION}"
        )
        response = self.client.request(
            "PUT",
            url,
            scope=SEARCH_SCOPE,
            headers={"Content-Type": "application/json"},
            json_body=payload,
        )
        return response.json() if response.content else self.get_knowledge_source(name)

    def get_knowledge_source(self, name: str) -> dict[str, Any]:
        url = (
            f"{self.base_url}/knowledgesources/{quote(name, safe='')}"
            f"?api-version={SEARCH_API_VERSION}"
        )
        return self.client.json("GET", url, scope=SEARCH_SCOPE)

    def list_files(self, source_name: str) -> list[dict[str, Any]]:
        url = (
            f"{self.base_url}/knowledgesources"
            f"('{quote(source_name, safe='')}')/files"
            f"?api-version={SEARCH_API_VERSION}"
        )
        return self.client.json("GET", url, scope=SEARCH_SCOPE).get("value") or []

    def delete_file(self, source_name: str, file_id: str) -> None:
        url = (
            f"{self.base_url}/knowledgesources"
            f"('{quote(source_name, safe='')}')/files"
            f"('{quote(file_id, safe='')}')?api-version={SEARCH_API_VERSION}"
        )
        self.client.request("DELETE", url, scope=SEARCH_SCOPE, expected={204})

    def upload_file(
        self,
        *,
        source_name: str,
        file_name: str,
        data: bytes,
        max_attempts: int,
    ) -> dict[str, Any]:
        url = (
            f"{self.base_url}/knowledgesources"
            f"('{quote(source_name, safe='')}')/files"
            f"?api-version={SEARCH_API_VERSION}"
        )
        return self.client.json(
            "POST",
            url,
            scope=SEARCH_SCOPE,
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Disposition": f'attachment; filename="{file_name}"',
            },
            data=data,
            expected={201},
            max_attempts=max_attempts,
        )

    def wait_for_ingestion(
        self,
        *,
        source_name: str,
        expected_names: set[str],
        timeout_seconds: float,
    ) -> tuple[list[dict[str, Any]], str]:
        deadline = time.monotonic() + timeout_seconds
        while True:
            files = self.list_files(source_name)
            errors = [item for item in files if item.get("errorMessage")]
            if errors:
                raise ProvisioningError(
                    "Knowledge source ingestion failed: "
                    + json.dumps(errors, ensure_ascii=False)[:3000]
                )
            actual_names = {item.get("fileName") for item in files}
            source = self.get_knowledge_source(source_name)
            created = ((source.get("fileParameters") or {}).get("createdResources") or {})
            index_name = created.get("index")
            if actual_names == expected_names and index_name:
                return files, index_name
            if time.monotonic() >= deadline:
                raise ProvisioningError(
                    "Timed out waiting for document ingestion. "
                    f"Expected files: {sorted(expected_names)}; actual: {sorted(actual_names)}"
                )
            time.sleep(5)

    def put_knowledge_base(
        self,
        *,
        name: str,
        source_name: str,
        account_name: str,
        retrieval: Deployment,
        account_key: str,
    ) -> dict[str, Any]:
        url = (
            f"{self.base_url}/knowledgebases/{quote(name, safe='')}"
            f"?api-version={SEARCH_API_VERSION}"
        )
        payload = {
            "name": name,
            "description": f"Foundry IQ knowledge base built from {source_name}.",
            "retrievalInstructions": (
                f"Use '{source_name}' to answer questions covered by the uploaded documents."
            ),
            "answerInstructions": (
                "Ground answers in the retrieved documents, preserve exact technical "
                "names, and identify the source file when possible."
            ),
            "outputMode": "extractiveData",
            "knowledgeSources": [{"name": source_name}],
            "models": [
                {
                    "kind": "azureOpenAI",
                    "azureOpenAIParameters": {
                        "resourceUri": f"https://{account_name}.openai.azure.com",
                        "deploymentId": retrieval.name,
                        "apiKey": account_key,
                        "modelName": retrieval.model_name,
                    },
                }
            ],
            "retrievalReasoningEffort": {"kind": "minimal"},
        }
        response = self.client.request(
            "PUT",
            url,
            scope=SEARCH_SCOPE,
            headers={"Content-Type": "application/json"},
            json_body=payload,
        )
        return response.json() if response.content else {"name": name}

    def mcp_url(self, knowledge_base_name: str) -> str:
        return (
            f"{self.base_url}/knowledgebases/{knowledge_base_name}/mcp"
            f"?api-version={SEARCH_API_VERSION}"
        )


def select_deployment(
    deployments: list[Deployment],
    requested_name: str | None,
    preferred_models: tuple[str, ...],
) -> Deployment | None:
    if requested_name:
        return next((item for item in deployments if item.name == requested_name), None)
    for model_name in preferred_models:
        match = next((item for item in deployments if item.model_name == model_name), None)
        if match:
            return match
    return None


def ensure_deployment(
    *,
    arm: ArmProvisioner,
    account: dict[str, Any],
    deployments: list[Deployment],
    requested_name: str | None,
    preferred_models: tuple[str, ...],
    model_for_creation: str,
    create_missing: bool,
    dry_run: bool,
    sku_name: str,
    capacity: int | None,
) -> Deployment:
    deployment = select_deployment(deployments, requested_name, preferred_models)
    if deployment:
        return deployment
    deployment_name = requested_name or model_for_creation
    if not create_missing:
        raise ProvisioningError(
            f"No suitable {model_for_creation!r} deployment exists in the endpoint "
            "Foundry account. Re-run with --create-missing-model-deployments after "
            "confirming model capacity and cost."
        )
    catalog = arm.model_catalog(account)
    arm.model_deployment_spec(
        model_name=model_for_creation,
        catalog=catalog,
        sku_name=sku_name,
        capacity=capacity,
    )
    if dry_run:
        return Deployment(name=deployment_name, model_name=model_for_creation)
    print(f"Creating model deployment: {deployment_name} ({model_for_creation})")
    return arm.create_model_deployment(
        account_id=account["id"],
        deployment_name=deployment_name,
        model_name=model_for_creation,
        catalog=catalog,
        sku_name=sku_name,
        capacity=capacity,
    )


def connection_resource_id(account_id: str, connection_name: str) -> str:
    return f"{account_id}/connections/{connection_name}"


def update_env_file(path: Path, values: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = text.splitlines()
    seen: set[str] = set()
    for index, line in enumerate(lines):
        for key, value in values.items():
            if re.match(rf"^{re.escape(key)}=", line):
                lines[index] = f"{key}={value}"
                seen.add(key)
    for key, value in values.items():
        if key not in seen:
            lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-dir", type=Path, default=DEFAULT_DOCS_DIR)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--name", help="Stable knowledge-base name; defaults to a unique name.")
    parser.add_argument("--search-connection-name")
    parser.add_argument("--embedding-deployment")
    parser.add_argument("--retrieval-deployment")
    parser.add_argument("--create-missing-model-deployments", action="store_true")
    parser.add_argument("--model-sku", default="GlobalStandard")
    parser.add_argument("--model-capacity", type=int)
    parser.add_argument("--max-upload-attempts", type=int, default=10)
    parser.add_argument("--upload-delay-seconds", type=float, default=2)
    parser.add_argument("--ingestion-timeout-seconds", type=float, default=900)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--update-env", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        env = dotenv_values(args.env_file)
        endpoint_value = env.get("AZURE_VOICE_AGENTS_ENDPOINT")
        if not endpoint_value:
            raise ValueError(
                f"AZURE_VOICE_AGENTS_ENDPOINT is missing from {args.env_file}."
            )
        endpoint = parse_foundry_endpoint(endpoint_value)
        documents = discover_documents(args.docs_dir)
        names = new_names(args.docs_dir, args.name)

        client = AzureClient()
        arm = ArmProvisioner(client)
        subscription_ids = arm.enabled_subscription_ids()
        account = arm.find_resource(
            subscription_ids,
            "microsoft.cognitiveservices/accounts",
            endpoint.account_name,
        )
        project = arm.get_project(account["id"], endpoint.project_name)
        principal_id = (project.get("identity") or {}).get("principalId")
        if not principal_id:
            raise ProvisioningError("The endpoint Foundry project has no managed identity.")

        connections = arm.list_connections(account["id"])
        _, search_service = arm.select_search_connection(
            connections, args.search_connection_name
        )
        search_resource = arm.find_resource(
            subscription_ids, "microsoft.search/searchservices", search_service
        )

        deployments = arm.list_deployments(account["id"])
        embedding = ensure_deployment(
            arm=arm,
            account=account,
            deployments=deployments,
            requested_name=args.embedding_deployment,
            preferred_models=(EMBEDDING_MODEL,),
            model_for_creation=EMBEDDING_MODEL,
            create_missing=args.create_missing_model_deployments,
            dry_run=args.dry_run,
            sku_name=args.model_sku,
            capacity=args.model_capacity,
        )
        retrieval = ensure_deployment(
            arm=arm,
            account=account,
            deployments=deployments,
            requested_name=args.retrieval_deployment,
            preferred_models=PREFERRED_RETRIEVAL_MODELS,
            model_for_creation=RETRIEVAL_MODEL,
            create_missing=args.create_missing_model_deployments,
            dry_run=args.dry_run,
            sku_name=args.model_sku,
            capacity=args.model_capacity,
        )

        search = SearchProvisioner(client, search_service)
        mcp_url = search.mcp_url(names.knowledge_base)
        connection_id = connection_resource_id(account["id"], names.connection)
        outputs = {
            "AZURE_VOICE_AGENTS_FOUNDRY_IQ_URL": mcp_url,
            "AZURE_VOICE_AGENTS_FOUNDRY_IQ_CONNECTION_ID": connection_id,
        }

        plan = {
            "dry_run": args.dry_run,
            "foundry_account": account["id"],
            "foundry_project": project.get("id"),
            "search_service": search_resource["id"],
            "knowledge_source": names.knowledge_source,
            "knowledge_base": names.knowledge_base,
            "connection": names.connection,
            "embedding_deployment": embedding.name,
            "retrieval_deployment": retrieval.name,
            "document_count": len(documents),
            "document_bytes": sum(path.stat().st_size for path in documents),
        }
        print(json.dumps(plan, indent=2))

        if not args.dry_run:
            account_key = arm.get_account_key(account["id"])
            source_payload = search.knowledge_source_payload(
                name=names.knowledge_source,
                account_name=endpoint.account_name,
                embedding=embedding,
                account_key=account_key,
            )
            source = search.put_knowledge_source(source_payload)
            print(f"Knowledge source ready: {source.get('name', names.knowledge_source)}")

            desired_sizes = {
                uploaded_file_name(args.docs_dir, path): path.stat().st_size
                for path in documents
            }
            reusable_names: set[str] = set()
            for existing in search.list_files(names.knowledge_source):
                file_name = existing.get("fileName")
                if (
                    file_name in desired_sizes
                    and existing.get("fileSizeBytes") == desired_sizes[file_name]
                    and not existing.get("errorMessage")
                ):
                    reusable_names.add(file_name)
                elif existing.get("fileId"):
                    search.delete_file(names.knowledge_source, existing["fileId"])

            pending = [
                path
                for path in documents
                if uploaded_file_name(args.docs_dir, path) not in reusable_names
            ]
            for index, path in enumerate(pending, start=1):
                search.upload_file(
                    source_name=names.knowledge_source,
                    file_name=uploaded_file_name(args.docs_dir, path),
                    data=path.read_bytes(),
                    max_attempts=args.max_upload_attempts,
                )
                print(f"[{index}/{len(pending)}] uploaded {path.relative_to(args.docs_dir)}")
                if args.upload_delay_seconds > 0 and index < len(pending):
                    time.sleep(args.upload_delay_seconds)

            expected_names = set(desired_sizes)
            files, index_name = search.wait_for_ingestion(
                source_name=names.knowledge_source,
                expected_names=expected_names,
                timeout_seconds=args.ingestion_timeout_seconds,
            )
            print(f"Verified {len(files)} indexed documents in {index_name}.")

            knowledge_base = search.put_knowledge_base(
                name=names.knowledge_base,
                source_name=names.knowledge_source,
                account_name=endpoint.account_name,
                retrieval=retrieval,
                account_key=account_key,
            )
            print(
                f"Knowledge base ready: "
                f"{knowledge_base.get('name', names.knowledge_base)}"
            )
            arm.ensure_search_reader_role(search_resource, principal_id)
            arm.put_connection(
                account_id=account["id"],
                connection_name=names.connection,
                knowledge_base_name=names.knowledge_base,
                mcp_url=mcp_url,
            )
            print(f"Foundry project connection ready: {names.connection}")

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
        requests.RequestException,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())