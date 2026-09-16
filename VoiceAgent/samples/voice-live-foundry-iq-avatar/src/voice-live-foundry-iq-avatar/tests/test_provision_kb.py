from __future__ import annotations

import json

import pytest

import provision_kb


class RecordingClient:
    def __init__(self, post_results: list[dict] | None = None) -> None:
        self.requests: list[tuple[str, dict]] = []
        self.post_results = list(post_results or [])

    def put(self, path: str, body: dict) -> None:
        self.requests.append((path, body))

    def post(
        self,
        path: str,
        body: dict,
        *,
        allow_not_found: bool = False,
    ) -> dict | None:
        self.requests.append((path, body))
        return self.post_results.pop(0) if self.post_results else {"value": []}


def test_validate_documents_normalizes_fields() -> None:
    documents = provision_kb.validate_documents(
        [
            {
                "id": " item-1 ",
                "title": " Title ",
                "content": " Content ",
                "source_url": " https://example.test/source ",
            }
        ]
    )

    assert documents == [
        {
            "id": "item-1",
            "title": "Title",
            "content": "Content",
            "source_url": "https://example.test/source",
        }
    ]


@pytest.mark.parametrize("value", [[], {}, None])
def test_validate_documents_rejects_empty_or_non_list_values(value) -> None:
    with pytest.raises(ValueError, match="non-empty JSON array"):
        provision_kb.validate_documents(value)


def test_validate_documents_rejects_duplicate_ids() -> None:
    document = {
        "id": "same",
        "title": "Title",
        "content": "Content",
        "source_url": "https://example.test/source",
    }

    with pytest.raises(ValueError, match="Duplicate document id"):
        provision_kb.validate_documents([document, document])


def test_validate_documents_rejects_more_than_small_corpus_limit() -> None:
    documents = [
        {
            "id": f"item-{index}",
            "title": "Title",
            "content": "Content",
            "source_url": "https://example.test/source",
        }
        for index in range(provision_kb.MAX_SYNC_DOCUMENTS + 1)
    ]

    with pytest.raises(ValueError, match="supports at most 1000 documents"):
        provision_kb.validate_documents(documents)


def test_load_documents_honors_environment_override(tmp_path, monkeypatch) -> None:
    path = tmp_path / "custom.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "custom",
                    "title": "Custom",
                    "content": "Custom content",
                    "source_url": "https://example.test/custom",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("KNOWLEDGE_DOCUMENTS_PATH", str(path))

    assert provision_kb.load_documents()[0]["id"] == "custom"


def test_knowledge_base_uses_minimal_extractive_retrieval() -> None:
    client = RecordingClient()

    provision_kb.create_knowledge_base(client, "sample-kb", "sample-source")

    path, body = client.requests[0]
    assert path == "knowledgebases/sample-kb"
    assert body["outputMode"] == "extractiveData"
    assert body["retrievalReasoningEffort"] == {"kind": "minimal"}
    assert body["knowledgeSources"] == [{"name": "sample-source"}]
    assert "models" not in body


def test_sync_documents_uploads_before_deleting_stale_ids() -> None:
    client = RecordingClient(
        post_results=[
            {
                "@odata.count": 2,
                "value": [{"id": "keep"}, {"id": "stale"}],
            },
            {"value": [{"key": "keep", "status": True, "statusCode": 200}]},
            {"value": [{"key": "stale", "status": True, "statusCode": 200}]},
        ]
    )
    documents = [
        {
            "id": "keep",
            "title": "Title",
            "content": "Content",
            "source_url": "https://example.test/keep",
        }
    ]

    provision_kb.sync_documents(client, "sample-index", documents)

    assert client.requests == [
        (
            "indexes/sample-index/docs/search",
            {"search": "*", "select": "id", "count": True, "top": 1000},
        ),
        (
            "indexes/sample-index/docs/index",
            {
                "value": [
                    {
                        "@search.action": "mergeOrUpload",
                        "id": "keep",
                        "title": "Title",
                        "content": "Content",
                        "source_url": "https://example.test/keep",
                    }
                ]
            },
        ),
        (
            "indexes/sample-index/docs/index",
            {"value": [{"@search.action": "delete", "id": "stale"}]},
        ),
    ]


def test_sync_documents_does_not_delete_stale_ids_when_upload_fails() -> None:
    client = RecordingClient(
        post_results=[
            {
                "@odata.count": 2,
                "value": [{"id": "keep"}, {"id": "stale"}],
            },
            {
                "value": [
                    {
                        "key": "keep",
                        "status": False,
                        "statusCode": 400,
                        "errorMessage": "invalid document",
                    }
                ]
            },
        ]
    )
    documents = [
        {
            "id": "keep",
            "title": "Title",
            "content": "Content",
            "source_url": "https://example.test/keep",
        }
    ]

    with pytest.raises(RuntimeError, match="invalid document"):
        provision_kb.sync_documents(client, "sample-index", documents)

    actions = [
        action
        for path, body in client.requests
        if path.endswith("/docs/index")
        for action in body["value"]
    ]
    assert [action["@search.action"] for action in actions] == ["mergeOrUpload"]


def test_list_document_ids_rejects_large_existing_index() -> None:
    client = RecordingClient(
        post_results=[
            {
                "@odata.count": provision_kb.MAX_SYNC_DOCUMENTS + 1,
                "value": [],
            }
        ]
    )

    with pytest.raises(RuntimeError, match="Use a dedicated sample index"):
        provision_kb.list_document_ids(client, "sample-index")


def test_main_rejects_large_existing_index_before_any_put(monkeypatch) -> None:
    client = RecordingClient(
        post_results=[
            {
                "@odata.count": provision_kb.MAX_SYNC_DOCUMENTS + 1,
                "value": [],
            }
        ]
    )

    class Credential:
        def get_token(self, _scope):
            return type("Token", (), {"token": "test-token"})()

        def close(self) -> None:
            pass

    monkeypatch.setenv("AZURE_SEARCH_ENDPOINT", "https://example.search.windows.net")
    monkeypatch.setenv("AZURE_SEARCH_INDEX_NAME", "sample-index")
    monkeypatch.setattr(provision_kb, "DefaultAzureCredential", Credential)
    monkeypatch.setattr(provision_kb, "SearchClient", lambda *_args: client)
    monkeypatch.setattr(
        provision_kb,
        "load_documents",
        lambda: [
            {
                "id": "keep",
                "title": "Title",
                "content": "Content",
                "source_url": "https://example.test/keep",
            }
        ],
    )

    assert provision_kb.main([]) == 1
    assert client.requests == [
        (
            "indexes/sample-index/docs/search",
            {"search": "*", "select": "id", "count": True, "top": 1000},
        )
    ]


def test_index_result_reports_partial_failure_details() -> None:
    with pytest.raises(RuntimeError, match=r"bad \(400\): invalid document"):
        provision_kb._check_index_result(
            {
                "value": [
                    {
                        "key": "bad",
                        "status": False,
                        "statusCode": 400,
                        "errorMessage": "invalid document",
                    }
                ]
            },
            1,
        )


def test_search_client_accepts_http_207_for_item_level_validation(monkeypatch) -> None:
    class Response:
        status_code = 207
        content = b"{}"
        text = "{}"

        @staticmethod
        def json() -> dict:
            return {"value": []}

    monkeypatch.setattr(provision_kb.requests, "post", lambda *args, **kwargs: Response())

    result = provision_kb.SearchClient("https://example.search.windows.net", "token").post(
        "indexes/sample/docs/index", {"value": []}
    )

    assert result == {"value": []}


def test_require_azd_env_fails_when_endpoint_cannot_be_stored(monkeypatch) -> None:
    class Credential:
        def get_token(self, _scope):
            return type("Token", (), {"token": "test-token"})()

        def close(self) -> None:
            pass

    monkeypatch.setenv("AZURE_SEARCH_ENDPOINT", "https://example.search.windows.net")
    monkeypatch.setattr(provision_kb, "DefaultAzureCredential", Credential)
    monkeypatch.setattr(provision_kb, "create_index", lambda *_args: None)
    monkeypatch.setattr(provision_kb, "sync_documents", lambda *_args: None)
    monkeypatch.setattr(provision_kb, "create_knowledge_source", lambda *_args: None)
    monkeypatch.setattr(provision_kb, "create_knowledge_base", lambda *_args: None)
    monkeypatch.setattr(provision_kb, "_set_azd_env", lambda *_args: False)

    assert provision_kb.main(["--require-azd-env"]) == 1
