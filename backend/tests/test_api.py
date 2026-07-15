from httpx import ASGITransport, AsyncClient
import pytest

from app.main import app
from app.summarization.api import get_summarization_service
from app.summarization.errors import SummarizationConfigurationError
from app.summarization.models import SummarizationRequest
from app.summarization.service import SummarizationService
from conftest import FakeProvider


@pytest.mark.asyncio
async def test_summary_endpoint_returns_contract(message_factory, generated_summary):
    service = SummarizationService(
        primary=FakeProvider("groq", [generated_summary]),
        fallback=FakeProvider("gemini", [generated_summary]),
        retry_delay_seconds=0,
    )

    async def override_service():
        return service

    app.dependency_overrides[get_summarization_service] = override_service
    payload = SummarizationRequest(messages=[message_factory()]).model_dump(mode="json")

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/summaries", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["overview"] == generated_summary.overview
    assert body["source_message_ids"] == ["message-1"]
    assert body["request_id"] == response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_validation_error_does_not_echo_email_content(generated_summary):
    service = SummarizationService(
        primary=FakeProvider("groq", [generated_summary]),
        fallback=FakeProvider("gemini", [generated_summary]),
        retry_delay_seconds=0,
    )

    async def override_service():
        return service

    app.dependency_overrides[get_summarization_service] = override_service
    secret_body = "CONFIDENTIAL-INTERNAL-CONTENT"

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/summaries",
                json={"messages": [{"body_text": secret_body}]},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert secret_body not in response.text
    assert response.json()["code"] == "invalid_request"
    assert response.headers["X-Request-ID"] == response.json()["request_id"]


@pytest.mark.asyncio
async def test_dependency_errors_use_safe_typed_response():
    async def unavailable_service():
        raise SummarizationConfigurationError()

    app.dependency_overrides[get_summarization_service] = unavailable_service
    payload = {
        "messages": [
            {
                "message_id": "message-1",
                "subject": "Test",
                "sender": {"address": "alice@example.com"},
                "sent_at": "2026-07-15T09:00:00+07:00",
                "body_text": "A readable body",
            }
        ]
    }

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/summaries", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["code"] == "summarization_not_configured"
    assert response.json()["retryable"] is False


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
