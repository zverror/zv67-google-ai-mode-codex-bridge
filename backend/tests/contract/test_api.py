"""HTTP contract tests for the T01 surface."""

from __future__ import annotations

import socket

import pytest
from fastapi.testclient import TestClient

from zv67.config import Settings
from zv67.main import create_app


def chat_payload(**overrides):
    payload = {
        "model": "zv67-mock",
        "messages": [{"role": "user", "content": "hello"}],
    }
    payload.update(overrides)
    return payload


def test_health_reports_mock_provider(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["mock"] is True
    assert body["provider"] == "mock"
    assert body["version"] == "0.1.0"


def test_models_expose_only_the_mock_model(client):
    response = client.get("/v1/models")

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "list"
    assert [model["id"] for model in body["data"]] == ["zv67-mock"]
    capabilities = body["data"][0]["zv67"]["capabilities"]
    assert capabilities["chat"] == "VERIFIED"
    assert capabilities["tool_calling"] == "UNSUPPORTED"


def test_chat_completion_returns_deterministic_content(client):
    first = client.post("/v1/chat/completions", json=chat_payload())
    second = client.post("/v1/chat/completions", json=chat_payload())

    assert first.status_code == 200
    body = first.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == "zv67-mock"
    assert body["choices"][0]["message"] == {
        "role": "assistant",
        "content": "Mock response from zv67-mock: hello",
    }
    assert body["usage"] is None
    assert first.json()["choices"][0]["message"] == second.json()["choices"][0]["message"]
    assert body["id"].startswith("chatcmpl-")
    assert body["zv67"]["request_id"].startswith("req_")


def test_unknown_model_returns_openai_error(client):
    response = client.post(
        "/v1/chat/completions",
        json=chat_payload(model="google-ai-mode"),
    )

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "model_not_found"
    assert error["param"] == "model"


def test_missing_messages_returns_structured_error(client):
    response = client.post("/v1/chat/completions", json={"model": "zv67-mock"})

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_request"
    assert "messages" in error["message"]


def test_empty_messages_are_rejected(client):
    response = client.post(
        "/v1/chat/completions",
        json=chat_payload(messages=[]),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_multiple_choices_return_explicit_unsupported_error(client):
    response = client.post("/v1/chat/completions", json=chat_payload(n=2))

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "unsupported_feature"
    assert error["param"] == "n"


def test_tools_are_accepted_but_not_executed(client):
    response = client.post(
        "/v1/chat/completions",
        json=chat_payload(
            tools=[
                {
                    "type": "function",
                    "function": {"name": "read_file", "parameters": {"type": "object"}},
                }
            ]
        ),
    )

    assert response.status_code == 200
    assert "Mock response" in response.json()["choices"][0]["message"]["content"]


def test_image_content_returns_unsupported_content(client):
    response = client.post(
        "/v1/chat/completions",
        json=chat_payload(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA"}}
                    ],
                }
            ]
        ),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_content"


def test_bearer_auth_is_enforced_when_configured(tmp_path):
    settings = Settings(
        api_key="local-secret",
        database_path=tmp_path / "zv67.sqlite3",
        data_dir=tmp_path,
        master_key_store="file",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/v1/models").status_code == 401
        assert (
            client.get("/v1/models", headers={"Authorization": "Bearer wrong"}).status_code
            == 401
        )
        response = client.get(
            "/v1/models",
            headers={"Authorization": "Bearer local-secret"},
        )
        assert response.status_code == 200


def test_chat_completion_works_with_network_connections_blocked(client, monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("the mock provider must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)

    response = client.post("/v1/chat/completions", json=chat_payload())

    assert response.status_code == 200

