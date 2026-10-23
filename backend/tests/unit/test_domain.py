"""Tests for request normalization and role preservation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from zv67.domain import (
    ChatCompletionRequest,
    ChatMessage,
    MockContentError,
    extract_text,
    normalize_chat_request,
)


def test_normalization_preserves_system_and_developer_instructions():
    request = ChatCompletionRequest(
        model="zv67-mock",
        messages=[
            ChatMessage(role="system", content="system rule"),
            ChatMessage(role="developer", content="developer rule"),
            ChatMessage(role="user", content="hello"),
        ],
    )

    normalized = normalize_chat_request(request)

    assert [message.role for message in normalized.messages] == [
        "system",
        "developer",
        "user",
    ]
    assert normalized.instructions == ("system rule", "developer rule")
    assert normalized.last_user_text == "hello"
    assert normalized.request_id.startswith("req_")


def test_text_parts_are_flattened_in_order():
    message = ChatMessage(
        role="user",
        content=[
            {"type": "text", "text": "first"},
            {"type": "text", "text": "second"},
        ],
    )

    assert extract_text(message, max_chars=100) == "first\nsecond"


def test_image_parts_are_rejected_explicitly():
    message = ChatMessage(
        role="user",
        content=[{"type": "image_url", "image_url": {"url": "data:image/png;base64,AA"}}],
    )

    with pytest.raises(MockContentError, match="image_url"):
        extract_text(message, max_chars=100)


def test_message_length_limit_is_enforced():
    with pytest.raises(MockContentError, match="character limit"):
        extract_text(ChatMessage(role="user", content="x" * 11), max_chars=10)


def test_conflicting_token_limits_are_rejected():
    with pytest.raises(ValidationError, match="not both"):
        ChatCompletionRequest(
            model="zv67-mock",
            messages=[ChatMessage(role="user", content="hi")],
            max_tokens=10,
            max_completion_tokens=20,
        )


def test_out_of_range_temperature_is_rejected():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(
            model="zv67-mock",
            messages=[ChatMessage(role="user", content="hi")],
            temperature=3,
        )

