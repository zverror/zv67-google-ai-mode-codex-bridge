"""Static checks for Google model routing and answer cleanup."""

from __future__ import annotations

import pytest

from zv67.upstream.google import (
    GOOGLE_MODEL_ARV,
    GoogleAIModeProvider,
    _clean_text,
    _is_quota_message,
)

pytestmark = pytest.mark.anyio


async def test_google_models_map_to_arv_parameters():
    provider = GoogleAIModeProvider(lambda _: {})
    models = await provider.list_models()

    assert GOOGLE_MODEL_ARV == {
        "google-ai-mode": None,
        "google-ai-mode-3.8-flash": "2",
        "google-ai-mode-4-argon": "3",
    }
    assert {model.id for model in models} == set(GOOGLE_MODEL_ARV)
    assert next(m for m in models if m.id == "google-ai-mode").capabilities["chat"].value == "VERIFIED"
    assert (
        next(m for m in models if m.id == "google-ai-mode-4-argon").capabilities["chat"].value
        == "NOT TESTED"
    )


def test_clean_text_drops_google_ui_chrome():
    fragment = """
    <div>
      <div data-session-thread-id="thread-1"></div>
      <div class="CKgc1d"><h3>AI Mode reply for test</h3></div>
      <div class="n6owBd">Ответ по существу.</div>
      <div class="IQTBxd"><div><span>Википедия</span></div></div>
      <div><button>Копировать</button></div>
      <div>Общее</div>
      <div>0 файлов</div>
    </div>
    """

    text = _clean_text(fragment)

    assert "Ответ по существу." in text
    assert "AI Mode reply" not in text
    assert "0 файлов" not in text
    assert "Википедия" not in text


def test_quota_messages_are_detected_in_both_languages():
    assert _is_quota_message(
        "You have reached your daily limit for this model. Switch to the Auto model."
    )
    assert _is_quota_message(
        "Вы достигли дневного ограничения для этой модели. Переключитесь на модель «Быстро»."
    )
    assert not _is_quota_message("Столица Финляндии — Хельсинки.")
