"""Tests for the deterministic mock provider."""

from __future__ import annotations

import pytest

from zv67.domain import ChatCompletionRequest, ChatMessage, normalize_chat_request
from zv67.upstream.base import ProviderError, ProviderErrorKind
from zv67.upstream.mock import MOCK_MODEL_ID, MockProvider


@pytest.mark.anyio
async def test_mock_provider_is_deterministic():
    provider = MockProvider()
    normalized = normalize_chat_request(
        ChatCompletionRequest(
            model=MOCK_MODEL_ID,
            messages=[ChatMessage(role="user", content="ping")],
        )
    )

    first = await provider.complete(normalized)
    second = await provider.complete(normalized)

    assert first.text == second.text
    assert first.text == f"Mock response from {MOCK_MODEL_ID}: ping"
    assert first.upstream_session_id is None


@pytest.mark.anyio
async def test_mock_provider_requires_a_user_message():
    provider = MockProvider()
    normalized = normalize_chat_request(
        ChatCompletionRequest(
            model=MOCK_MODEL_ID,
            messages=[ChatMessage(role="system", content="only instructions")],
        )
    )

    with pytest.raises(ProviderError) as error:
        await provider.complete(normalized)

    assert error.value.kind is ProviderErrorKind.INVALID_REQUEST

