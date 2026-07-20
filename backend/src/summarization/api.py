from functools import lru_cache
from fastapi import APIRouter, Depends, Request

from src.config import get_settings
from src.summarization.errors import ProviderConfigurationError, SummarizationConfigurationError
from src.summarization.models import SummarizationRequest, SummarizationResult
from src.summarization.providers import GeminiSummaryProvider, GroqSummaryProvider
from src.summarization.service import SummarizationService

router = APIRouter(prefix="/api/v1/summaries", tags=["summarization"])


@lru_cache
def _build_summarization_service() -> SummarizationService:
    """Build the service from whichever providers are actually configured.

    Each provider constructor raises `ProviderConfigurationError` when it has no
    key, so building both unconditionally meant a Groq-only setup could not
    summarize at all — the *fallback* being absent broke the *primary*. Gemini
    is now genuinely optional; only having neither is fatal.
    """
    settings = get_settings()

    primary: GroqSummaryProvider | GeminiSummaryProvider | None = None
    fallback: GeminiSummaryProvider | None = None

    if settings.has_groq:
        primary = GroqSummaryProvider(
            api_key=settings.groq_api_key.get_secret_value(),
            model=settings.groq_model,
            timeout=settings.summarizer_provider_timeout_seconds,
        )

    if settings.has_gemini:
        gemini = GeminiSummaryProvider(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_model,
            timeout=settings.summarizer_provider_timeout_seconds,
        )
        # Gemini alone is a valid setup; it is only the *fallback* when Groq
        # is also present.
        if primary is None:
            primary = gemini
        else:
            fallback = gemini

    if primary is None:
        raise ProviderConfigurationError()

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
