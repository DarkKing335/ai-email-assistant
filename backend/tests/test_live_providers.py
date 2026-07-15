import os

import pytest

from app.config import Settings
from app.summarization.models import EmailMessageInput, EmailParticipant, SummarizationRequest
from app.summarization.preprocessing import normalize_request
from app.summarization.providers import (
    SYSTEM_PROMPT,
    GeminiSummaryProvider,
    GroqSummaryProvider,
    build_user_prompt,
)


def configured_provider(name: str):
    if os.getenv("RUN_LIVE_MODEL_TESTS") != "1":
        pytest.skip("set RUN_LIVE_MODEL_TESTS=1 to call external providers")

    settings = Settings()
    if name == "groq":
        if not settings.groq_api_key or not settings.groq_model:
            pytest.skip("Groq key and model are required")
        return GroqSummaryProvider(
            api_key=settings.groq_api_key.get_secret_value(),
            model=settings.groq_model,
            timeout=settings.summarizer_provider_timeout_seconds,
        )

    if not settings.gemini_api_key or not settings.gemini_model:
        pytest.skip("Gemini key and model are required")
    return GeminiSummaryProvider(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        timeout=settings.summarizer_provider_timeout_seconds,
    )


@pytest.mark.live
@pytest.mark.asyncio
@pytest.mark.parametrize("provider_name", ["groq", "gemini"])
async def test_provider_live_smoke_test(provider_name: str):
    provider = configured_provider(provider_name)
    request = SummarizationRequest(
        messages=[
            EmailMessageInput(
                message_id="live-smoke-1",
                subject="Project check-in",
                sender=EmailParticipant(address="alice@example.com"),
                to_recipients=[EmailParticipant(address="bob@example.com")],
                sent_at="2026-07-15T09:00:00+07:00",
                body_text="Please send the reviewed project plan by Friday.",
            )
        ]
    )
    normalized = normalize_request(request, max_messages=20, max_normalized_chars=100_000)

    result = await provider.generate(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_user_prompt(normalized.model_dump(mode="json")),
    )

    assert result.overview
    assert all(
        set(item.source_message_ids) == {"live-smoke-1"}
        for item in (*result.key_points, *result.action_items)
    )
