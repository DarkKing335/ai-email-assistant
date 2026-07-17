from functools import lru_cache
from fastapi import APIRouter, Depends, Request

from app.config import get_settings
from app.summarization.errors import ProviderConfigurationError, SummarizationConfigurationError
from app.summarization.models import SummarizationRequest, SummarizationResult
from app.summarization.providers import GeminiSummaryProvider, GroqSummaryProvider
from app.summarization.service import SummarizationService

router = APIRouter(prefix="/api/v1/summaries", tags=["summarization"])


@lru_cache
def _build_summarization_service() -> SummarizationService:
    settings = get_settings()
    primary = GroqSummaryProvider(
        api_key=settings.groq_api_key.get_secret_value() if settings.groq_api_key else None,
        model=settings.groq_model,
        timeout=settings.summarizer_provider_timeout_seconds,
    )
    fallback = GeminiSummaryProvider(
        api_key=settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None,
        model=settings.gemini_model,
        timeout=settings.summarizer_provider_timeout_seconds,
    )
    return SummarizationService(
        primary=primary,
        fallback=fallback,
        max_messages=settings.summarizer_max_messages,
        max_normalized_chars=settings.summarizer_max_normalized_chars,
        retry_delay_seconds=settings.summarizer_retry_delay_seconds,
    )


async def get_summarization_service() -> SummarizationService:
    try:
        return _build_summarization_service()
    except ProviderConfigurationError as exc:
        raise SummarizationConfigurationError() from exc


@router.post("", response_model=SummarizationResult)
async def summarize_email(
    payload: SummarizationRequest,
    request: Request,
    service: SummarizationService = Depends(get_summarization_service),
) -> SummarizationResult:
    return await service.summarize(payload, request_id=request.state.request_id)
