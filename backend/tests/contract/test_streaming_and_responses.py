"""Streaming and Responses API contract tests."""

from __future__ import annotations

import json

from zv67.accounts.service import AccountService


def parse_sse(body: str) -> list[tuple[str | None, dict | str]]:
    events: list[tuple[str | None, dict | str]] = []
    for block in body.strip().split("\n\n"):
        event_name = None
        data_lines = []
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line[len("event: ") :]
            elif line.startswith("data: "):
                data_lines.append(line[len("data: ") :])
        if not data_lines:
            continue
        data = "\n".join(data_lines)
        if data == "[DONE]":
            events.append((event_name, data))
        else:
            events.append((event_name, json.loads(data)))
    return events


def test_chat_streaming_emits_deltas_and_done(client):
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "zv67-mock",
            "messages": [{"role": "user", "content": "stream me"}],
            "stream": True,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    assert events[-1] == (None, "[DONE]")

    chunks = [data for name, data in events if data != "[DONE]"]
    text = "".join(
        chunk["choices"][0]["delta"].get("content", "") for chunk in chunks
    )
    assert text == "Mock response from zv67-mock: stream me"
    assert chunks[0]["choices"][0]["delta"]["role"] == "assistant"
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
    assert response.headers["x-zv67-session-id"].startswith("sess_")


def test_chat_streaming_records_a_successful_request(client, app):
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "zv67-mock",
            "messages": [{"role": "user", "content": "count me"}],
            "stream": True,
        },
    )
    assert response.status_code == 200
    assert "data: [DONE]" in response.text

    summary = app.state.stats.summary(hours=1)
    assert summary.requests == 1
    assert summary.successes == 1
    assert summary.errors == 0


def test_responses_non_streaming_returns_message_output(client):
    response = client.post(
        "/v1/responses",
        json={
            "model": "zv67-mock",
            "instructions": "be brief",
            "input": [{"role": "user", "content": "hello responses"}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "response"
    assert body["status"] == "completed"
    assert body["id"].startswith("resp_")
    assert body["output"][0]["type"] == "message"
    assert body["output"][0]["content"][0]["type"] == "output_text"
    assert body["output"][0]["content"][0]["text"] == (
        "Mock response from zv67-mock: hello responses"
    )
    assert body["usage"] is None
    assert body["zv67"]["session_id"].startswith("sess_")


def test_responses_streaming_event_order(client):
    response = client.post(
        "/v1/responses",
        json={
            "model": "zv67-mock",
            "input": "streamed response",
            "stream": True,
        },
    )

    assert response.status_code == 200
    events = parse_sse(response.text)
    names = [name for name, _ in events]
    assert names[0] == "response.created"
    assert names[1] == "response.in_progress"
    assert "response.output_text.delta" in names
    assert names[-1] == "response.completed"
    completed = events[-1][1]["response"]
    assert completed["status"] == "completed"
    assert completed["output"][0]["content"][0]["text"] == (
        "Mock response from zv67-mock: streamed response"
    )


def test_responses_rejects_unsupported_features(client):
    tools = client.post(
        "/v1/responses",
        json={
            "model": "zv67-mock",
            "input": "hi",
            "tools": [{"type": "function", "name": "read_file"}],
        },
    )
    assert tools.status_code == 400
    assert tools.json()["error"]["param"] == "tools"

    previous = client.post(
        "/v1/responses",
        json={
            "model": "zv67-mock",
            "input": "hi",
            "previous_response_id": "resp_old",
        },
    )
    assert previous.status_code == 400
    assert previous.json()["error"]["param"] == "previous_response_id"

    function_output = client.post(
        "/v1/responses",
        json={
            "model": "zv67-mock",
            "input": [
                {"type": "function_call_output", "call_id": "call_1", "output": "x"}
            ],
        },
    )
    assert function_output.status_code == 400
    assert function_output.json()["error"]["code"] == "unsupported_content"


def test_session_history_persists_across_requests(client, app):
    first = client.post(
        "/v1/chat/completions",
        json={"model": "zv67-mock", "messages": [{"role": "user", "content": "one"}]},
    )
    session_id = first.json()["zv67"]["session_id"]

    second = client.post(
        "/v1/chat/completions",
        json={
            "model": "zv67-mock",
            "messages": [{"role": "user", "content": "two"}],
            "session_id": session_id,
        },
    )
    assert second.json()["zv67"]["session_id"] == session_id

    history = app.state.sessions.history(session_id)
    assert [turn.content for turn in history] == [
        "one",
        "Mock response from zv67-mock: one",
        "two",
        "Mock response from zv67-mock: two",
    ]


def test_account_routing_keeps_a_session_sticky(client, app):
    accounts = AccountService(app.state.database, app.state.credentials)
    first = accounts.add("First", concurrency_limit=2)
    second = accounts.add("Second", concurrency_limit=2)

    first_response = client.post(
        "/v1/chat/completions",
        json={"model": "zv67-mock", "messages": [{"role": "user", "content": "a"}]},
    )
    session_id = first_response.json()["zv67"]["session_id"]
    chosen = first_response.json()["zv67"]["account_id"]

    second_response = client.post(
        "/v1/chat/completions",
        json={
            "model": "zv67-mock",
            "messages": [{"role": "user", "content": "b"}],
            "session_id": session_id,
        },
    )

    assert chosen in {first.id, second.id}
    assert second_response.json()["zv67"]["account_id"] == chosen
    assert app.state.sessions.get(session_id).account_id == chosen


def test_all_accounts_disabled_returns_explicit_error(client, app):
    accounts = AccountService(app.state.database, app.state.credentials)
    account = accounts.add("Only")
    accounts.set_enabled(account.id, False)

    response = client.post(
        "/v1/chat/completions",
        json={"model": "zv67-mock", "messages": [{"role": "user", "content": "x"}]},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "no_account_available"

